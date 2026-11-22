# CLAUDE.md

Guidance for Claude Code in this repository. Keep this file short — details live
in `books/`.

## Repository Scope

1. `h2/` — upstream H2 v2.x Java SQL database source (Maven, JDK 11+).
2. `books/` — Chinese source-code analysis book for H2 internals, plus the
   toolchain that audits the manuscript and renders HTML/PDF/EPUB.

## Commands

`books/scripts/bookctl` resolves the project virtualenv itself; use it instead of
a bare `python` (only `books/.venv` may run the toolchain).

```bash
cd h2 && ./mvnw compile                    # engine build
books/scripts/bookctl check                # every quality gate (read-only)
books/scripts/bookctl build                # cover stats + merged md + HTML + daily archive
books/scripts/bookctl test                 # fast tier (~25s); --full adds browser + pandoc
books/scripts/bookctl deliver              # PDF + TOC links + verify + EPUB + verify + archive
books/scripts/bookctl make cover           # coverage ratchet and per-file floor
books/scripts/bookctl doctor               # optional dependencies
```

## Where to Look

| Topic | Authoritative file |
| --- | --- |
| Directory structure, file ownership | `books/docs/managements/folder.md` |
| Commands: everyday use | `books/README.md`（快速开始） |
| Commands: verification | `books/docs/managements/testplan.md` §1 |
| Workflow: what to do in what order | `books/docs/manuals/how-to-use.md` |
| Gate criteria and levels | `books/docs/managements/testplan.md` §2 |
| Writing and format conventions | `books/docs/managements/style-guide.md` |
| Content organisation (paths, chapter order) | `books/data/tmpl/book.toml` |
| Toolchain policy (thresholds, budgets, baselines) | `books/data/config/base.json`, `books/data/config/style.json` |
| Iteration designs and plans | `books/docs/plan/<topic>/` (`design.md`, `plan.md`) |

## Working Rhythm

- **Measure, then run the smallest command that decides the question.** Read the
  order of magnitude first (`--collect-only`, one file, a `--durations` subset).
  The whole fast suite is ~25s, so anything taking minutes means one test is stuck;
  a single file or case beats the full run, and the full run happens once, at the end.
- **One heavy job at a time, and never in the foreground for long.** Anything past
  ~2 minutes runs in the background with its expected time stated, then waits for
  the exit signal — no `sleep` polling. A step killed at its timeout leaves its
  child alive: `ps`, kill the orphan, then start again.
- **Debug a red test from its report, not from a rerun.** `python
  books/src/python/test_report.py run` writes `books/test-reports/<stamp>/` and
  `test_report.py last` prints the failing cases plus the command that reruns only
  those modules. Fix, rerun that case, only then take the full suite again.
- **CI is a separate task.** Push and return to the work at hand: the local gates
  are the verification. Do not poll `gh run` unless the user asks about CI.
- **A finished change ships itself.** Unless the operator says otherwise, end every
  change by recording it in `books/docs/managements/changelog.md`, committing with a
  message that explains the why, and pushing.

## Hard Rules

- Configuration lives only in `books/data/tmpl/book.toml`,
  `books/data/config/base.json`, `books/data/config/style.json` and
  `books/data/language/*.json`; scripts read it through `_config`.
- Manuscript sources live only in `books/data/manuscript/`.
- Delivery artifacts live only in `books/dist/` (gitignored, regenerated).
- Tooling lives in `books/src/python/` (thin launchers may live in `books/scripts/`);
  tests only in `books/src/test/`.
- Session artifacts (scratch scripts, drafts, exports) go to `books/data/tmp/`
  (gitignored). `.claude/` belongs to the agent's own runtime data, not to the
  repository, so nothing is written there on purpose.
- Evidence directories are dated copies, not content: `books/test-reports/` and
  `books/data/archive/` are gitignored and excluded from every gate through
  `_config.excluded_dirs()`; never judge them as manuscript or docs.
- No historical traces in docs or code comments (review rounds, batches, dated
  plans, completed-work ledgers); version history lives in `changelog.md` only.
  Tracker ids (`rf-N`, `plan-N`) belong to `review-findings.md` / `plan.md`: no
  other document and no code comment may cite them, and no identifier or file name
  may encode one. `audit/traces.py` (docs and code ranges) and `audit/doc_drift.py`
  enforce this and the surrounding drift rules (paths, scripts, chapters, versions).
