# CLAUDE.md

Guidance for Claude Code in this repository. Keep this file short — details live
in `books/`.

## Repository Scope

1. `h2/` — upstream H2 v2.x Java SQL database source (Maven, JDK 11+).
2. `books/` — Chinese source-code analysis book for H2 internals, plus the
   toolchain that audits the manuscript and renders HTML/PDF/EPUB.

## Commands

```bash
cd h2 && ./mvnw compile                       # engine build
python books/src/python/make.py check         # all quality gates (read-only)
python books/src/python/make.py build         # cover stats + merged md + HTML
python books/src/python/make.py test          # unit + integration tests
python books/src/python/make.py deliver       # build + PDF + verify + EPUB (on demand)
python books/src/python/make.py doctor        # optional deps (pandoc/playwright/pypdf)
```

## Where to Look

| Topic | Authoritative file |
|-------|--------------------|
| Directory structure, file ownership | `books/docs/managements/folder.md` |
| Launchers and virtualenv | `books/README.md` (快速开始), `books/scripts/{bk,launch,bootstrap}.*` |
| Script usage, gates, delivery steps | `books/docs/manuals/how-to-use.md` |
| Quality gates and verification commands | `books/docs/managements/testplan.md` |
| Writing and format conventions | `books/docs/managements/style-guide.md` |
| Content organisation (paths, chapter order) | `books/data/tmpl/book.toml` |
| Toolchain policy (thresholds, budgets, baselines) | `books/data/config/base.json`, `books/data/config/style.json` |

## Hard Rules

- Configuration lives only in `books/data/tmpl/book.toml`,
  `books/data/config/base.json` and `books/data/config/style.json`;
  scripts read it through `_config`.
- Manuscript sources live only in `books/data/manuscript/`.
- Delivery artifacts live only in `books/dist/` (gitignored, regenerated).
- Tooling lives in `books/src/python/` (thin launchers may live in `books/scripts/`);
  tests only in `books/src/test/`.
- No temporary repair scripts, archives, or `__pycache__` in git; session
  artifacts go to `.claude/`.
- No historical traces in docs or code comments (review rounds, batches, dated
  plans, completed-work ledgers); version history lives in `changelog.md` only.
  `make.py check` enforces this plus doc drift (paths, scripts, chapters,
  versions) through `audit/doc_traces.py`, `audit/code_traces.py`
  and `audit/doc_drift.py`.
