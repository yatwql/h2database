#!/usr/bin/env python3
"""Clone the configured source repository into ``data/srcref/``.

A book may point ``[sources].repo`` at a git URL instead of a local tree. This tool
fetches that repository once and keeps it under the book's own ``srcref`` directory,
so analysis reads a copy the book owns rather than a path outside the project.

    python core/fetch_source.py              # clone what [sources].repo names
    python core/fetch_source.py --update     # fetch and check out the configured ref
    python core/fetch_source.py --dry-run    # print the git commands, run nothing

Cloning is deliberately conservative: an existing directory is never overwritten
without ``--update``, and a half-finished clone is reported rather than reused.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

_sys = sys
_sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import _config, _fsutil  # noqa: E402


def clone_commands(repo: str, target: str, ref: str = '') -> list[list[str]]:
    """git commands that produce ``target`` from ``repo`` (first run)."""
    command = ['git', 'clone', '--depth', '1']
    if ref:
        command += ['--branch', ref]
    return [command + [repo, target]]


def update_commands(target: str, ref: str = '') -> list[list[str]]:
    """git commands that refresh an existing clone and land on ``ref``."""
    commands = [['git', '-C', target, 'fetch', '--all', '--tags', '--prune']]
    if ref:
        commands.append(['git', '-C', target, 'checkout', ref])
        commands.append(['git', '-C', target, 'pull', '--ff-only'])
    return commands


def run(command: list[str], dry_run: bool) -> int:
    """Execute one git command (or print it); returns its exit code."""
    printable = ' '.join(command)
    if dry_run:
        print(f'would run: {printable}')
        return 0
    print(f'run: {printable}')
    try:
        return subprocess.run(command, check=False).returncode
    except OSError as exc:
        print(f'error: 无法执行 git（{exc}）')
        return 127


def main(argv: list[str] | None = None) -> int:
    _fsutil.pin_stdout_utf8()
    parser = argparse.ArgumentParser(description='把 [sources].repo 克隆到 data/srcref/')
    parser.add_argument('--repo', default='', help='git URL（缺省取 book.toml [sources].repo）')
    parser.add_argument('--ref', default='', help='分支 / 标签 / 提交（缺省取 [sources].ref）')
    parser.add_argument('--dir', default='', help='克隆目标目录（缺省按仓库名推导）')
    parser.add_argument('--update', action='store_true', help='已存在时改为 fetch + checkout')
    parser.add_argument('--dry-run', action='store_true', help='只打印将执行的命令')
    parser.add_argument('--json', action='store_true', help='机器可读输出')
    args = parser.parse_args(argv)

    cfg = _config.current()
    repo = args.repo or cfg.source_repo()
    ref = args.ref or cfg.source_ref()
    if not repo:
        print('error: 没有配置 [sources].repo，也没有给 --repo')
        return 2
    target = args.dir or cfg.clone_target(repo)
    if not target:
        print(f'error: 无法从 {repo} 推导目标目录，请给 --dir')
        return 2

    exists = os.path.isdir(target)
    if exists and not args.update:
        print(f'已存在：{target}（要更新加 --update；要重建先删掉它）')
        return 0
    commands = update_commands(target, ref) if exists else clone_commands(repo, target, ref)
    for command in commands:
        code = run(command, args.dry_run)
        if code != 0:
            print(f'error: git 返回 {code}；目录保持原样，下次运行可重试')
            return code
    if args.json:
        print(json.dumps({'repo': repo, 'ref': ref, 'target': target,
                          'updated': exists, 'dry_run': args.dry_run},
                         ensure_ascii=False))
    else:
        print(f'源码就位：{target}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
