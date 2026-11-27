"""The contract a drafted paragraph must satisfy, and the ledger that makes runs auditable.

A model may draft prose for chapter leads and section recaps; it may not add facts. Two
mechanisms keep that honest:

    contract   `data/book/llm-tasks.toml` declares, per task, the length window and whether
               digits from outside the supplied facts are allowed. A draft that breaks the
               contract is rejected, and the deterministic text stands in for it.
    ledger     every attempt — accepted or rejected — appends one line to
               `data/state/llm-ledger.jsonl` with the prompt digest, the response digest,
               the model and a fingerprint of the resolved configuration. Same inputs give
               the same digests, so a run can be reproduced or explained later.

Both are configuration-driven: a book with no `llm-tasks.toml` gets the defaults below,
which are the toolchain's idea of a safe draft, not any particular book's style.
"""

import hashlib
import json
import os
import re
import sys

from lib import _config

DEFAULT_TASK = {
    "min_chars": 20,
    "max_chars": 220,
    "allow_unknown_digits": False,
    "single_paragraph": True,
}

DIGITS_RE = re.compile(r"\d+")
LEDGER_NAME = "llm-ledger.jsonl"


def task_config() -> str:
    """Where this book declares its drafting contracts, resolved when it is used."""
    return _config.book_path("llm-tasks.toml")


def ledger_path() -> str:
    """The append-only call ledger, resolved when it is used (state, not source)."""
    return os.path.join(_config.state_dir(), LEDGER_NAME)


def contract(task: str) -> dict:
    """The rule set in force for one drafting task."""
    import tomllib

    rules = dict(DEFAULT_TASK)
    try:
        with open(task_config(), "rb") as fh:
            data = tomllib.load(fh)
    except FileNotFoundError:
        return rules
    except tomllib.TOMLDecodeError as exc:
        raise SystemExit(f"error: invalid TOML in {task_config()}: {exc}") from exc
    defaults = data.get("default") or {}
    rules.update({key: defaults[key] for key in DEFAULT_TASK if key in defaults})
    overrides = (data.get("tasks") or {}).get(task) or {}
    rules.update({key: overrides[key] for key in DEFAULT_TASK if key in overrides})
    return rules


def check(task: str, text: str, facts: dict) -> list[str]:
    """Contract violations in a drafted paragraph; empty means the draft may be used.

    A number that is not in the supplied facts is the dangerous case: it reads like
    evidence and is not one, so it is rejected unless the task explicitly allows it.
    """
    rules = contract(task)
    problems: list[str] = []
    body = text.strip()
    if len(body) < int(rules["min_chars"]):
        problems.append(f"shorter than {rules['min_chars']} characters")
    if len(body) > int(rules["max_chars"]):
        problems.append(f"longer than {rules['max_chars']} characters")
    if rules["single_paragraph"] and "\n\n" in body:
        problems.append("more than one paragraph")
    if not rules["allow_unknown_digits"]:
        known = set()
        for value in facts.values():
            known.update(DIGITS_RE.findall(str(value)))
        invented = sorted(set(DIGITS_RE.findall(body)) - known)
        if invented:
            problems.append("numbers absent from the facts: " + ", ".join(invented))
    return problems


def enforce(task: str, prompt: str, cleaned: str, facts: dict) -> str:
    """Record the attempt and return the text to keep, or '' when it must be dropped.

    The ledger records both outcomes, so a rejected draft stays explainable: the digest
    of what the model actually wrote survives even though the prose does not.
    """
    if len(cleaned) < int(contract(task)["min_chars"]):
        record(task, prompt, cleaned, "provider", ["too short to use"])
        return ""
    problems = check(task, cleaned, facts)
    record(task, prompt, cleaned, "provider", problems)
    if problems:
        print(
            f"  [warn] drafted {task} violates its contract ({'; '.join(problems)}); "
            "using deterministic text",
            file=sys.stderr,
        )
        return ""
    return cleaned


def digest(value: str) -> str:
    """Stable short digest, used for both sides of a call."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def record(task: str, prompt: str, response: str, model: str, problems: list[str]) -> None:
    """Append one attempt to the ledger; a ledger failure never breaks the ingest."""
    entry = {
        "task": task,
        "prompt": digest(prompt),
        "response": digest(response),
        "model": model,
        "accepted": not problems,
        "problems": problems,
        "config": _config.fingerprint(),
    }
    path = ledger_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
    except OSError as exc:
        print(f"  [warn] cannot write the LLM ledger ({exc})")
