"""The prompt a drafting task uses: the book's, else its language's, else built in.

A prompt is language and voice, so it is not the toolchain's to decide. Resolution has one
order — `book.toml [llm.prompts]`, then the language pack's `prompts`, then an English
default — and this module exists so the ingest code stays about chapters rather than about
where configuration comes from.
"""

# Last resort when neither the book nor its language pack states a prompt. It is English on
# purpose: a book that wants another language says so, instead of inheriting one silently.
FALLBACKS = {
    "lead": ("Write two sentences as the chapter lead: the chapter covers {pkgs} packages and "
             "{lines} lines of implementation, its title is \"{title}\". Output prose only — "
             "no lists, headings or code."),
    "summary": ("Write two sentences as the chapter summary: the chapter covers {pkgs} packages "
                "and {lines} lines; the largest package is {top}. Output prose only — no lists, "
                "headings or code."),
}


def template(kind: str) -> str:
    """The template for one drafting task, before the facts are filled in.

    `_config` is imported here rather than at module level: a long-lived process (tests, the
    TUI) switches books by rebinding `lib._config`, and a module-level name would keep
    answering for the book that was active when this module first loaded.
    """
    from lib import _config  # noqa: PLC0415 - follows the active book

    prompts = (_config.current().book_section("llm").get("prompts") or {})
    if isinstance(prompts.get(kind), str) and prompts[kind].strip():
        return str(prompts[kind])
    language = _config.current().language().get("prompts") or {}
    if isinstance(language.get(kind), str) and language[kind].strip():
        return str(language[kind])
    return FALLBACKS.get(kind, "")


class _KeepUnknown(dict):
    """Fill the placeholders we have; leave the rest visible instead of raising."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def render(kind: str, facts: dict) -> str:
    """The prompt with the caller's facts filled in.

    A placeholder without a fact stays as written: the template is configuration, and a typo
    there should be visible in the text rather than fatal to the ingest.
    """
    try:
        return template(kind).format_map(_KeepUnknown(facts))
    except (IndexError, ValueError):
        return template(kind)
