# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## Repository Scope

This repository contains two distinct work areas:

1. **H2 Database Engine** (`h2/`): upstream H2 v2.x Java SQL database source. Build with Maven and JDK 11+.
2. **H2 Source Code Analysis** (`docs-stm/`): Chinese-language source-code analysis book for H2 internals. The authoritative source files, generated merged Markdown, delivery tools, and optional HTML/PDF outputs are all under `docs-stm/`.

## Project Session Files

Keep this project's session artifacts only under the repository-local `.claude/` directory. Do not create or preserve project session files in external/global session locations when working on this repository.

## H2 Engine Commands

Run from the repository root unless noted:

```bash
cd h2 && ./mvnw compile
```

Primary build configuration is `h2/pom.xml`.

## Documentation Layout

Canonical documentation files are in `docs-stm/`:

```text
docs-stm/
  cover.md
  front/                     # Book front matter (preface, copyright, reading guide)
  ch1-2-architecture.md
  ch3-packages.md
  ch4-5-modules-processes.md
  ch6-1-data-structures.md
  ch6-2-storage-algorithms.md
  ch6-3-query-algorithms.md
  ch7-8-sql-optimizer.md
  ch9-10-persistence-locking.md
  ch11-12-guide-summary.md
  back/                      # Book back matter (glossary, references, index)
  management/                # Project management documents
  ├── requirements.md
  ├── plan.md
  ├── testplan.md
  ├── changelog.md
  └── review-findings.md
  h2-source-code-analysis.md
  tools/
```

Generated HTML/PDF outputs are ignored by git and should be regenerated from source when needed.

## Documentation Workflow

Run the standard documentation pipeline after every source-document change:

```bash
python docs-stm/tools/cover_stats.py
python docs-stm/tools/rebuild_merged.py
python docs-stm/tools/generate_html.py
python docs-stm/tools/_audit_smart.py
python docs-stm/tools/final_check.py
```

PDF generation is on demand only and should be the final delivery step:

```bash
python docs-stm/tools/generate_pdf.py
python docs-stm/tools/add_pdf_toc_links.py
python docs-stm/tools/verify_pdf.py
```

## Documentation Conventions

- Figure captions use `**图 X-Y: Title**` on their own line, outside code fences.
- ASCII diagrams use ` ```text ` fences; Java snippets use ` ```java `; SQL snippets use ` ```sql `.
- Source paths use `org/h2/...` format, not `h2/src/main/...`.
- Cross references use `详见第X章《章节标题》` and must match actual H1 titles.
- Management document versions stay aligned across `cover.md`, `requirements.md`, `plan.md`, `testplan.md`, and `changelog.md`.

## Management Document Authority

- `requirements.md`: current scope and deliverables only.
- `plan.md`: current workflow, maintenance strategy, risks, and future work only.
- `docs-stm/management/testplan.md`: quality gates and verification commands; this is the authoritative validation reference.
- `docs-stm/management/changelog.md`: version history.
- `docs-stm/management/review-findings.md`: review issue tracker and closure state only.

Avoid duplicating long command blocks or historical issue details across management documents. Prefer references to the authoritative file above.

## Review Workflow

For formal documentation reviews, use four perspectives in parallel: architect, documentation engineer, programmer/source-reference reviewer, and book editor. Track findings in `docs-stm/management/review-findings.md` with CRITICAL/HIGH/MEDIUM/LOW severity, and record completed changes in `docs-stm/management/changelog.md`.

## Cleanup Rules

Do not commit temporary repair scripts, archives, Python `__pycache__`, or process-only session artifacts. Formal delivery scripts belong in `docs-stm/tools/`; repository-local session artifacts belong in `.claude/`.
