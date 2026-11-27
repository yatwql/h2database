"""Editorial profile: which elements a book must carry, and how densely.

Every well-made technical book carries the same handful of elements — learning goals,
a bulleted recap, common pitfalls, numbered listings, term pairs, tables, admonitions —
but publishers trade them off differently: a manual is sparse, a tutorial leans on
learning goals, a hands-on book on pitfalls and worked paths. The trade-off therefore
belongs to the book, not to the toolchain:

    book.toml [editing]        the book's own profile and any per-element override
    PRESETS (below)            the three shapes a book can start from

An element that a profile leaves out is *not* a defect — the audit reports the measured
count and says the element is not enabled, rather than inventing a floor nobody agreed
to. Nothing here reads config at import time: one book's profile must never leak into
another book's run.
"""

from lib import _config

# The three shapes. A book picks one by name and overrides only what it disagrees with.
# `heading` is the section the element lives in, in this book's language; a book in
# another language sets its own through the override table.
PRESETS: dict[str, dict[str, dict]] = {
    "manual": {
        "learning_goals": {"enabled": False, "heading": "学习目标", "min_items": 3},
        "key_points": {"enabled": True, "heading": "本章小结", "min_items": 3},
        "pitfalls": {"enabled": False, "heading": "常见误区", "min_items": 1},
        "table_density": {"enabled": False, "min_per_1000_lines": 1.0},
    },
    "tutorial": {
        "learning_goals": {"enabled": True, "heading": "学习目标", "min_items": 3},
        "key_points": {"enabled": True, "heading": "本章小结", "min_items": 4},
        "pitfalls": {"enabled": True, "heading": "常见误区", "min_items": 1},
        "table_density": {"enabled": True, "min_per_1000_lines": 1.5},
    },
    "hands-on": {
        "learning_goals": {"enabled": True, "heading": "学习目标", "min_items": 2},
        "key_points": {"enabled": False, "heading": "本章小结", "min_items": 3},
        "pitfalls": {"enabled": True, "heading": "常见误区", "min_items": 2},
        "table_density": {"enabled": True, "min_per_1000_lines": 2.0},
    },
}

DEFAULT_PROFILE = "manual"


def label(rule: dict) -> str:
    """The section label for one element: the book's own wording, else the language pack.

    Presets carry a section *key*, never a label: the wording of a recap heading is the
    manuscript language's business, and a book that keeps its goals in a different block
    says so through its own `heading` override.
    """
    if rule.get('heading'):
        return str(rule['heading'])
    key = str(rule.get('section') or '')
    sections = _config.language().get('sections') or {}
    return str(sections.get(key) or key)


def _read() -> dict:
    """The `[editing]` table of this book; empty when the book declares none."""
    return _config.current().book_section("editing")


def load_profile() -> dict[str, object]:
    """The element rules in force for this book: preset first, overrides on top.

    A book with no `[editing]` table gets the default preset, so the toolchain works out of
    the box; a book that names an unknown profile gets the default plus a problem,
    because silently substituting a different shape would be worse than a loud fallback.
    """
    data = _read()
    chosen = str((data.get("profile") or {}).get("name") or DEFAULT_PROFILE)
    problems: list[str] = []
    if chosen not in PRESETS:
        problems.append(f'unknown editorial profile "{chosen}"; using {DEFAULT_PROFILE}')
        chosen = DEFAULT_PROFILE
    rules = {name: dict(rule) for name, rule in PRESETS[chosen].items()}
    for name, override in (data.get("elements") or {}).items():
        if name not in rules:
            problems.append(f'unknown element "{name}" in [editing]')
            continue
        rules[name].update(override)
    return {"profile": chosen, "rules": rules, "problems": problems}
