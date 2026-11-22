#!/usr/bin/env python3
"""Run the test suite with a saved report, and pull the last failure back out.

Every run writes one dated directory under ``books/test-reports/`` and points
``latest.json`` at it, so a red build leaves behind the evidence instead of
scrolling away:

  test-reports/<timestamp>/junit.xml     pytest's machine-readable result
  test-reports/<timestamp>/pytest.log    the full console output
  test-reports/<timestamp>/report.json   counts, cases, machine info
  test-reports/<timestamp>/report.md     the same, for humans

Usage:
  python test_report.py run [--marker tier_fast] [--timeout 1800]
  python test_report.py last [--json]     # failing cases of the newest report
  python test_report.py list              # report directories, newest first
  python test_report.py prune [--dry-run]

Exit codes: 0 all green, 1 failures, 2 usage error.
"""
from __future__ import annotations

import argparse
import datetime
import glob
import json
import os
import platform
import shutil
import subprocess
import sys

from defusedxml import ElementTree as _safe_xml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import _config, _fsutil

STAMP_FMT = '%Y%m%d-%H%M%S'
DEFAULT_KEEP_DAYS = 30
PY = sys.executable
TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
TESTS_DIR = os.path.normpath(os.path.join(TOOLS_DIR, '..', 'test'))


def _write(path: str, text: str) -> None:
    """Write a report file, creating its directory first."""
    _fsutil.ensure_dir(path)
    _fsutil.write_text(path, text)


def settings() -> dict:
    """Report policy from ``base.json [reports]`` with conservative defaults."""
    raw = _config.POLICY.get('reports') or {}
    try:
        days = int(raw.get('retention_days', DEFAULT_KEEP_DAYS))
    except (TypeError, ValueError):
        days = DEFAULT_KEEP_DAYS
    return {'dir': str(raw.get('dir') or 'test-reports'), 'retention_days': max(1, days)}


def reports_root() -> str:
    return os.path.join(_config.BOOK_ROOT, settings()['dir'])


def latest_pointer() -> str:
    return os.path.join(reports_root(), 'latest.json')


def report_dirs() -> list[str]:
    """Every dated report directory, newest first."""
    root = reports_root()
    try:
        names = [name for name in os.listdir(root)
                 if os.path.isdir(os.path.join(root, name)) and name[:8].isdigit()]
    except OSError:
        return []
    return [os.path.join(root, name) for name in sorted(names, reverse=True)]


def newest_report() -> str | None:
    """The report directory ``latest.json`` points at, else the newest on disk."""
    pointer = latest_pointer()
    if os.path.isfile(pointer):
        try:
            name = json.loads(_fsutil.read_text(pointer)).get('dir')
        except (OSError, ValueError):
            name = None
        if name and os.path.isdir(os.path.join(reports_root(), name)):
            return os.path.join(reports_root(), name)
    found = report_dirs()
    return found[0] if found else None


def _cases(junit_path: str) -> tuple[list[dict], dict]:
    """Cases from pytest's junit XML, plus the totals it reports."""
    try:
        tree = _safe_xml.parse(junit_path)
    except (OSError, ValueError, SyntaxError):
        return [], {}
    root = tree.getroot()
    suites = root.iter('testsuite') if root.tag != 'testsuite' else [root]
    cases: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for suite in suites:
        for case in suite.iter('testcase'):
            key = (case.get('classname') or '', case.get('name') or '')
            if key in seen:
                continue
            seen.add(key)
            outcome = 'pass'
            message = ''
            for child in case:
                if child.tag in ('failure', 'error', 'skipped'):
                    outcome = {'failure': 'fail', 'error': 'error', 'skipped': 'skip'}[child.tag]
                    message = (child.get('message') or child.text or '').strip()
                    break
            cases.append({'id': f'{key[0]}::{key[1]}', 'outcome': outcome,
                          'seconds': float(case.get('time') or 0.0),
                          'message': message.splitlines()[0][:300] if message else ''})
    # Counts come from the cases themselves: pytest's own totals also count
    # unittest subtests, which makes "N tests" disagree with the case list.
    totals = {'tests': len(cases),
              'failures': sum(1 for c in cases if c['outcome'] == 'fail'),
              'errors': sum(1 for c in cases if c['outcome'] == 'error'),
              'skipped': sum(1 for c in cases if c['outcome'] == 'skip')}
    return cases, totals


def _escape(text: str) -> str:
    return (text or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def _html_report(summary: dict, cases: list[dict]) -> str:
    """Self-contained HTML report: failures first, one row per case."""
    totals = summary['totals']
    failing = [case for case in cases if case['outcome'] in ('fail', 'error')]
    ordered = failing + [case for case in cases if case not in failing]
    rows = []
    for case in ordered:
        css = {'fail': 'bad', 'error': 'bad', 'skip': 'muted'}.get(case['outcome'], 'ok')
        rows.append(
            f'<tr class="{css}"><td>{case["outcome"]}</td>'
            f'<td><code>{_escape(case["id"])}</code></td>'
            f'<td>{case["seconds"]:.3f}s</td>'
            f'<td>{_escape(case["message"])}</td></tr>')
    failed = bool(totals.get('failures') or totals.get('errors'))
    verdict = '失败' if failed else '通过'
    return f'''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>测试报告 {summary['stamp']}</title>
<style>body{{font-family:system-ui;margin:2rem;color:#222}}
th,td{{border:1px solid #ddd;padding:6px 10px;text-align:left;font-size:14px}}
th{{background:#1565C0;color:#fff}}table{{border-collapse:collapse;width:100%}}
tr.ok td{{background:#f6fff6}}tr.bad td{{background:#fff2f2}}tr.muted td{{color:#888}}
code{{font-size:13px}}.verdict{{font-weight:600;color:{'#c62828' if failed else '#2e7d32'}}}</style></head>
<body><h1>测试报告 {summary['stamp']}</h1>
<p>结果：<span class="verdict">{verdict}</span> · 标记 <code>{_escape(summary['marker'])}</code> ·
退出码 {summary['code']} · 用时 {summary['seconds']:.1f}s</p>
<p>用例 {totals.get('tests', 0)} 个，失败 {totals.get('failures', 0)}，
错误 {totals.get('errors', 0)}，跳过 {totals.get('skipped', 0)}<br>
机器：{_escape(summary['machine'])}</p>
<table><thead><tr><th>结果</th><th>用例</th><th>耗时</th><th>失败信息</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>
<p>完整输出：<code>{_escape(os.path.relpath(summary['log'], _config.BOOK_ROOT))}</code></p>
</body></html>
'''


def _write_reports(target: str, summary: dict, cases: list[dict]) -> None:
    _write(os.path.join(target, 'report.json'),
                       json.dumps({**summary, 'cases': cases}, ensure_ascii=False,
                                  indent=2) + '\n')
    failing = [case for case in cases if case['outcome'] in ('fail', 'error')]
    lines = [f"# 测试报告 {summary['stamp']}", '',
             f"- 标记：`{summary['marker']}`",
             f"- 退出码：{summary['code']}",
             f"- 用例：{summary['totals'].get('tests', 0)} 个，"
             f"失败 {summary['totals'].get('failures', 0)}，"
             f"错误 {summary['totals'].get('errors', 0)}，"
             f"跳过 {summary['totals'].get('skipped', 0)}",
             f"- 用时：{summary['seconds']:.1f}s",
             f"- 机器：{summary['machine']}", '']
    if failing:
        lines += ['## 失败用例', '']
        for case in failing[:40]:
            lines += [f"- `{case['id']}` — {case['outcome']}", f"  `{case['message']}`"]
    else:
        lines += ['## 失败用例', '', '无。']
    lines += ['', f"完整输出见 `{os.path.relpath(summary['log'], _config.BOOK_ROOT)}`"]
    _write(os.path.join(target, 'report.md'), '\n'.join(lines) + '\n')
    _write(os.path.join(target, 'report.html'), _html_report(summary, cases))


def run(marker: str = 'tier_fast', timeout: int = 1800, tests: str | None = None) -> dict:
    """Run the suite, write the report directory, and return its summary."""
    stamp = datetime.datetime.now().strftime(STAMP_FMT)
    target = os.path.join(reports_root(), stamp)
    _fsutil.ensure_dir(os.path.join(target, 'pytest.log'))
    junit = os.path.join(target, 'junit.xml')
    log = os.path.join(target, 'pytest.log')
    command = [PY, '-m', 'pytest', tests or TESTS_DIR, '-q',
               f'--junitxml={junit}']
    if marker:
        command += ['-m', marker]
    started = datetime.datetime.now()
    code = 0
    with open(log, 'w', encoding='utf-8') as sink:
        try:
            proc = subprocess.run(command, cwd=_config.BOOK_ROOT, text=True,
                                  stdout=sink, stderr=subprocess.STDOUT,
                                  timeout=timeout, check=False)
            code = proc.returncode
        except subprocess.TimeoutExpired:
            code = 124
            sink.write(f'\n=== timed out after {timeout}s ===\n')
    seconds = (datetime.datetime.now() - started).total_seconds()
    cases, totals = _cases(junit)
    summary = {'stamp': stamp, 'marker': marker, 'code': code, 'seconds': seconds,
               'totals': totals, 'dir': target, 'log': log, 'junit': junit,
               'machine': f'{platform.python_version()} on {platform.platform()}'}
    _write_reports(target, summary, cases)
    _write(latest_pointer(), json.dumps({'dir': stamp}, ensure_ascii=False) + '\n')
    prune()
    return summary


def collect() -> dict:
    """Count test cases per tier by reading the modules, without executing them.

    Markers live in each module's ``TAGS`` tuple and are applied by the suite's
    conftest, so ``pytest -m`` cannot filter at collection time. Reading the
    declaration is both faster and closer to the truth the tiers select.
    """
    import ast

    tiers = {'fast': 0, 'slow': 0, 'untiered': 0}
    per_file: dict[str, dict] = {}
    for path in sorted(TESTS_DIR and glob.glob(os.path.join(TESTS_DIR, 'test_*.py'))):
        name = os.path.basename(path)
        try:
            tree = ast.parse(_fsutil.read_text(path))
        except (OSError, SyntaxError):
            continue
        tags: tuple[str, ...] = ()
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(
                    getattr(target, 'id', '') == 'TAGS' for target in node.targets):
                try:
                    tags = tuple(ast.literal_eval(node.value))
                except ValueError:
                    tags = ()
        tests = 0
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                    and node.name.startswith('test_'):
                tests += 1
            elif isinstance(node, ast.ClassDef) and node.name.startswith('Test'):
                for child in node.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                            and child.name.startswith('test_'):
                        tests += 1
        if not tests:
            continue
        tier = 'fast' if 'tier:fast' in tags else ('slow' if 'tier:slow' in tags else 'untiered')
        tiers[tier] += tests
        per_file[name] = {'tests': tests, 'tier': tier, 'tags': list(tags)}
    tiers['total'] = sum(tiers.values())
    payload = {'stamp': datetime.datetime.now().strftime(STAMP_FMT),
               'counts': tiers, 'files': per_file}
    target = os.path.join(reports_root(), f"collect-{payload['stamp']}.json")
    _write(target, json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
    return {**payload, 'path': target}


def perf_window(limit: int = 20) -> dict:
    """Latest run versus the median of the runs before it, per step."""
    history = os.path.join(_config.BOOK_ROOT, 'logs', 'perf-history.jsonl')
    runs: list[dict] = []
    if os.path.isfile(history):
        for line in _fsutil.read_lines(history):
            line = line.strip()
            if not line:
                continue
            try:
                runs.append(json.loads(line))
            except ValueError:
                continue
    recent = runs[-limit:]
    if len(recent) < 2:
        return {'runs': len(recent), 'total': 0.0, 'steps': [],
                'last': recent[-1] if recent else {}}

    def timings(run: dict) -> dict[str, float]:
        found: dict[str, float] = {}
        for step in run.get('steps') or []:
            if isinstance(step, dict):
                name = str(step.get('step') or '')
                try:
                    found[name] = float(step.get('seconds') or 0.0)
                except (TypeError, ValueError):
                    continue
        return found

    previous, latest = recent[:-1], recent[-1]
    seen: dict[str, list[float]] = {}
    for run in previous:
        for name, seconds in timings(run).items():
            seen.setdefault(name, []).append(seconds)
    factor, slack = _perf_thresholds()
    rows = []
    for name, seconds in timings(latest).items():
        samples = seen.get(name) or []
        median = _median(samples) if samples else None
        regressed = median is not None and seconds > median * factor + slack
        rows.append({'step': name, 'seconds': seconds, 'median': median,
                     'regressed': regressed})
    return {'runs': len(recent), 'total': float(latest.get('seconds') or 0.0),
            'steps': rows, 'last': latest}


def _median(samples: list[float]) -> float:
    ordered = sorted(samples)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def _perf_thresholds() -> tuple[float, float]:
    """Same knobs the gate reads; the report only displays, the gate judges."""
    quality = _config.STYLE_POLICY.get('quality') or {}
    return (float(quality.get('perf_regression_factor', 1.5)),
            float(quality.get('perf_regression_slack_s', 5.0)))


def prune(dry_run: bool = False) -> list[str]:
    """Drop report directories older than the retention window."""
    keep_days = settings()['retention_days']
    cutoff = datetime.datetime.now() - datetime.timedelta(days=keep_days)
    removed: list[str] = []
    for path in report_dirs():
        name = os.path.basename(path)
        try:
            when = datetime.datetime.strptime(name, STAMP_FMT)
        except ValueError:
            continue
        if when >= cutoff:
            continue
        removed.append(name)
        if dry_run:
            continue
        try:
            shutil.rmtree(path)
        except OSError as exc:
            print(f'  [warn] 无法清理旧报告 {path}: {exc}', file=sys.stderr)
    return removed


def _module_of(case_id: str) -> str:
    """Test module name from a junit case id (`...test_x.Class::test_y`)."""
    classname = case_id.split('::', 1)[0]
    for part in classname.split('.'):
        if part.startswith('test_'):
            return part
    return classname.split('.')[-1] if classname else ''


def last_failures(report: str | None = None) -> dict:
    """Failing cases of one report, read back from its own saved result.

    The report directory holds everything needed (``report.json`` with the case
    list, plus the raw ``pytest.log`` for context), so this tool needs no other
    layer and no second copy of the failure parser.
    """
    target = report or newest_report()
    if not target:
        return {'report': '', 'failures': [], 'rerun': ''}
    payload_path = os.path.join(target, 'report.json')
    try:
        payload = json.loads(_fsutil.read_text(payload_path))
    except (OSError, ValueError):
        return {'report': os.path.relpath(target, _config.BOOK_ROOT),
                'failures': [], 'rerun': ''}
    failing = [case for case in payload.get('cases') or []
               if case.get('outcome') in ('fail', 'error')]
    tests_rel = os.path.relpath(TESTS_DIR, os.path.dirname(_config.BOOK_ROOT))
    modules = sorted({_module_of(case['id']) for case in failing if case.get('id')})
    rerun = ''
    if modules:
        rerun = ('python -m pytest '
                 + ' '.join(os.path.join(tests_rel, f'{name}.py') for name in modules)
                 + ' -q')
    return {'report': os.path.relpath(target, _config.BOOK_ROOT),
            'failures': failing, 'rerun': rerun}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)

    run_parser = sub.add_parser('run', help='run the suite and save a report')
    run_parser.add_argument('--marker', default='tier_fast',
                            help='pytest marker expression (empty string = everything)')
    run_parser.add_argument('--timeout', type=int, default=1800)
    run_parser.add_argument('--tests', help='test path override')

    last_parser = sub.add_parser('last', help='failures of the newest report')
    last_parser.add_argument('--json', action='store_true')
    last_parser.add_argument('--report', help='specific report directory')

    collect_parser = sub.add_parser('collect', help='count cases per marker, no execution')
    collect_parser.add_argument('--json', action='store_true')

    perf_parser = sub.add_parser('perf', help='latest step timings versus the previous runs')
    perf_parser.add_argument('--json', action='store_true')
    perf_parser.add_argument('--limit', type=int, default=20)

    sub.add_parser('list', help='report directories, newest first')
    prune_parser = sub.add_parser('prune', help='drop reports past the retention window')
    prune_parser.add_argument('--dry-run', action='store_true')

    args = parser.parse_args(argv)

    if args.command == 'run':
        summary = run(args.marker, args.timeout, args.tests)
        totals = summary['totals']
        print(f"report -> {os.path.relpath(summary['dir'], _config.BOOK_ROOT)}"
              f"  ({totals.get('tests', 0)} cases, {totals.get('failures', 0)} failed,"
              f" {seconds_text(summary['seconds'])})")
        return 0 if summary['code'] == 0 else 1

    if args.command == 'collect':
        payload = collect()
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            for marker, count in payload['counts'].items():
                print(f'  {marker:<10} {count} 个用例')
            print(f"快照 -> {os.path.relpath(payload['path'], _config.BOOK_ROOT)}")
        return 0

    if args.command == 'perf':
        payload = perf_window(args.limit)
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0
        if not payload['steps']:
            print('没有足够的历史数据（perf-history.jsonl 至少需要两次运行）')
            return 0
        print(f"最近 {payload['runs']} 次运行；本次总耗时 {payload['total']:.1f}s")
        for row in payload['steps']:
            delta = ''
            if row['median'] is not None:
                delta = f"{row['seconds'] - row['median']:+.1f}s"
            flag = ' ⚠ 回退' if row['regressed'] else ''
            print(f"  {row['step']:<18}{row['seconds']:>7.1f}s  {delta}{flag}")
        return 0

    if args.command == 'list':
        for path in report_dirs():
            print(os.path.relpath(path, _config.BOOK_ROOT))
        return 0

    if args.command == 'prune':
        removed = prune(args.dry_run)
        verb = '将清理' if args.dry_run else '已清理'
        print(f'{verb} {len(removed)} 份过期报告'
              f'（保留 {settings()["retention_days"]} 天）')
        return 0

    payload = last_failures(args.report)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if not payload['failures'] else 1
    if not payload['report']:
        print('没有测试报告；先跑 python books/src/python/test_report.py run')
        return 2
    print(f"报告：{payload['report']}")
    if not payload['failures']:
        print('没有失败用例。')
        return 0
    for item in payload['failures']:
        print(f"  {item.get('id') or item.get('name')}  {item.get('reason', '')}")
    if payload['rerun']:
        print(f"\n只重跑这些模块：\n  {payload['rerun']}")
    return 1


def seconds_text(seconds: float) -> str:
    return f'{seconds:.1f}s'


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
