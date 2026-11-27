#!/usr/bin/env python3
"""Validate data/config/style.json before it can silently misconfigure the book.

Checks
  KEYS      only known top-level sections (a typo would otherwise be ignored)
  SHAPE     required keys present with the right types
  RANGE     thresholds are sane (min < max, ratios 0-100, positive budgets)

Exit 1 on any finding.

Usage:
  python style_schema.py
  python style_schema.py --json
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import _config, _errors, _fsutil

KNOWN_TEMPLATES = {"map_intro", "types_intro", "api_intro", "path_intro", "deep_dive"}
KNOWN_TOP = {
    "_note",
    "_schema",
    "captions",
    "claims",
    "diagrams",
    "evidence",
    "clusters",
    "quality",
    "prose",
    "style_rules",
    "content_depth",
    "generation",
    "limits",
    "thresholds",
}
REQUIRED = {
    "captions": ("leading_verbs", "vague_trailing", "presets"),
    "clusters": ("min_figures", "window_lines"),
    "quality": (
        "min_coords_per_chapter",
        "min_chapter_lines",
        "max_chapter_lines",
        "max_table_rows",
        "max_duplicate_ratio",
        "min_figures_per_section",
    ),
    "claims": ("markers",),
    "evidence": ("min_coords_per_1000_lines", "min_symbols_per_1000_lines",
                 "min_paragraph_coverage_pct"),
    "prose": ("avg_sentence_good", "avg_sentence_bad", "min_composite"),
    "generation": ("exercises_per_chapter", "checklist_items"),
    "limits": ("sources", "tests", "docs"),
}


def load() -> dict:
    path = _config.config_path("style.json")
    try:
        return json.loads(_fsutil.read_text(path))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"error: cannot read {path}: {exc}") from exc


def validate(style: dict) -> list[str]:
    """Everything wrong with one style.json, one group of checks at a time."""
    problems: list[str] = []
    problems += _check_top_level(style)
    problems += _check_captions(style)
    problems += _check_quality(style)
    problems += _check_prose(style)
    problems += _check_rules_and_depth(style)
    problems += _check_templates(style)
    problems += _check_limits(style)
    return problems


def _check_top_level(style: dict) -> list[str]:
    """Unknown keys and missing required sections."""
    problems: list[str] = []
    unknown = set(style) - KNOWN_TOP
    if unknown:
        problems.append(f"unknown top-level keys: {sorted(unknown)}")
    for section, keys in REQUIRED.items():
        payload = style.get(section)
        if not isinstance(payload, dict):
            problems.append(f"[{section}] missing or not an object")
            continue
        for key in keys:
            if key not in payload:
                problems.append(f"[{section}].{key} missing")

    return problems


def _check_captions(style: dict) -> list[str]:
    """The three caption presets and their ranges."""
    problems: list[str] = []
    presets = (style.get("captions") or {}).get("presets") or {}
    for name in ("strict", "normal", "loose"):
        preset = presets.get(name)
        if not isinstance(preset, dict):
            problems.append(f"[captions.presets].{name} missing")
            continue
        low, high = preset.get("min_chars"), preset.get("max_chars")
        if not isinstance(low, int) or not isinstance(high, int) or low >= high:
            problems.append(f"[captions.presets].{name}: min_chars must be < max_chars")
        if not isinstance(preset.get("fail_at"), int) or preset["fail_at"] < 0:
            problems.append(f"[captions.presets].{name}: fail_at must be >= 0")

    return problems


def _check_quality(style: dict) -> list[str]:
    """Chapter length and duplicate-ratio bounds."""
    problems: list[str] = []
    quality = style.get("quality") or {}
    if (
        isinstance(quality.get("min_chapter_lines"), int)
        and isinstance(quality.get("max_chapter_lines"), int)
        and quality["min_chapter_lines"] >= quality["max_chapter_lines"]
    ):
        problems.append("[quality]: min_chapter_lines must be < max_chapter_lines")
    ratio = quality.get("max_duplicate_ratio")
    if not isinstance(ratio, (int, float)) or not 0 <= ratio <= 100:
        problems.append("[quality].max_duplicate_ratio must be within 0-100")

    return problems


def _check_prose(style: dict) -> list[str]:
    """Prose targets and the per-section overrides."""
    problems: list[str] = []
    prose = style.get("prose") or {}
    for good, bad in (
        ("avg_sentence_good", "avg_sentence_bad"),
        ("dup_good", "dup_bad"),
        ("bullet_good", "bullet_bad"),
    ):
        if good in prose and bad in prose and prose[good] > prose[bad]:
            problems.append(f"[prose].{good} must be <= {bad}")
    for key in ("tone", "audience"):
        if not isinstance(prose.get(key), str) or not prose.get(key):
            problems.append(f"[prose].{key} must be a non-empty string")
    sections_cfg = prose.get("sections")
    if not isinstance(sections_cfg, dict) or set(sections_cfg) != {"body", "caption", "exercise"}:
        problems.append("[prose].sections must define body/caption/exercise")
    else:
        body = sections_cfg.get("body") or {}
        if body.get("avg_sentence_good", 0) > body.get("avg_sentence_bad", 0):
            problems.append("[prose.sections.body] good must be <= bad")
        caption = sections_cfg.get("caption") or {}
        if not isinstance(caption.get("max_chars"), int):
            problems.append("[prose.sections.caption].max_chars must be an int")
        exercise = sections_cfg.get("exercise") or {}
        if not isinstance(exercise.get("min_items"), int) or exercise["min_items"] < 1:
            problems.append("[prose.sections.exercise].min_items must be >= 1")
    composite = prose.get("min_composite")
    if not isinstance(composite, (int, float)) or not 0 < composite <= 100:
        problems.append("[prose].min_composite must be within (0, 100]")

    return problems


def _check_rules_and_depth(style: dict) -> list[str]:
    """Style rules and the content-depth floors."""
    problems: list[str] = []
    rules = style.get("style_rules")
    if not isinstance(rules, dict):
        problems.append("[style_rules] missing or not an object")
    else:
        terminology = rules.get("terminology")
        if terminology and not all(isinstance(g, list) and len(g) > 1 for g in terminology):
            problems.append("[style_rules].terminology must be a list of synonym groups")
        if not isinstance(rules.get("banned_link_text", []), list):
            problems.append("[style_rules].banned_link_text must be a list")
        if not isinstance((rules.get("heading") or {}), dict):
            problems.append("[style_rules].heading must be an object")

    depth = style.get("content_depth")
    if not isinstance(depth, dict):
        problems.append("[content_depth] missing or not an object")
    else:
        if not isinstance(depth.get("glossary_min_uses"), int) or depth["glossary_min_uses"] < 1:
            problems.append("[content_depth].glossary_min_uses must be >= 1")
        if not isinstance(depth.get("glossary_ignore", []), list):
            problems.append("[content_depth].glossary_ignore must be a list")
        if not isinstance(depth.get("excerpt_lines", 1), int):
            problems.append("[content_depth].excerpt_lines must be an int")

    return problems


def _check_templates(style: dict) -> list[str]:
    """The prose templates, which live outside style.json."""
    problems: list[str] = []
    templates = _config.templates()
    unknown_templates = set(templates) - KNOWN_TEMPLATES
    if unknown_templates:
        problems.append(f"templates: unknown keys {sorted(unknown_templates)}")
    for key in ("map_intro", "types_intro", "api_intro", "path_intro"):
        if not isinstance(templates.get(key), str) or "{" not in templates.get(key, ""):
            problems.append(f"templates.{key} must be a template string with placeholders")
    if templates and not isinstance(templates.get("deep_dive"), list):
        problems.append("templates.deep_dive must be a list of strings")
    if (style.get("generation") or {}).get("templates"):
        problems.append(
            "style.json must not carry prose templates (move to data/templates/templates.toml)"
        )
    if "project" in style:
        problems.append("style.json must not carry display copy (belongs to book.toml [project])")

    return problems


def _check_limits(style: dict) -> list[str]:
    """Per-kind file budgets."""
    problems: list[str] = []
    for kind, values in (style.get("limits") or {}).items():
        if not isinstance(values, dict) or "limit" not in values:
            problems.append(f"[limits].{kind} needs limit/warn")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    problems = validate(load())
    if args.json:
        print(
            json.dumps({"count": len(problems), "problems": problems}, ensure_ascii=False, indent=2)
        )
        return 0 if not problems else 1

    if not problems:
        print("✅ style.json 结构合规")
        return 0
    print(f"style.json 结构问题 {len(problems)} 处：")
    for problem in problems:
        print(f"  - {problem}")
    return 1


if __name__ == "__main__":
    sys.exit(_errors.run(main, sys.argv[1:]))
