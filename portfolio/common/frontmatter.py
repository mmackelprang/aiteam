"""Byte-preserving frontmatter surgery.

The hard rules (CLAUDE.md #1/#2/#7) demand that writers touch ONLY the keys
they own and leave every other byte of the note exactly as a human left it —
including inline comments, quoting style, key order, and blank lines. A
parse→dump YAML round-trip cannot promise that, so this module never
serializes the whole frontmatter: it locates the line span of one top-level
key and splices replacement lines into the raw text (plan finding F6).

Reading is done with yaml.safe_load (read-only); writing is textual splice.
After any splice, callers should run `verify_untouched()` as a belt-and-
braces check that every key other than the ones they own still parses to
the same value.
"""

from __future__ import annotations

import datetime as _dt
import json
import re

import yaml


class FrontmatterError(ValueError):
    """Raised when a note's frontmatter cannot be handled safely."""


# --- splitting ---------------------------------------------------------------

def split_note(text: str) -> tuple[str, str, str]:
    """Split a note into (head, fm, tail), reassembling byte-identically.

    head = optional BOM + the opening ``---`` fence line
    fm   = raw frontmatter text between the fences (may be ``''``)
    tail = the closing fence line + the entire body

    ``head + fm + tail == text`` is guaranteed. Splice operations only ever
    rewrite ``fm``.
    """
    bom = ""
    t = text
    if t.startswith("\ufeff"):
        bom, t = "\ufeff", t[1:]
    lines = t.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != "---":
        raise FrontmatterError("note has no frontmatter (must start with ---)")
    for i in range(1, len(lines)):
        if lines[i].rstrip("\r\n") == "---":
            return bom + lines[0], "".join(lines[1:i]), "".join(lines[i:])
    raise FrontmatterError("unterminated frontmatter fence")


def join_note(head: str, fm: str, tail: str) -> str:
    return head + fm + tail


def parse(fm: str) -> dict:
    """Read-only YAML parse of the frontmatter text ('' -> {})."""
    data = yaml.safe_load(fm) if fm.strip() else {}
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise FrontmatterError("frontmatter is not a mapping")
    return data


def newline_of(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


# --- key spans ---------------------------------------------------------------

def key_span(fm: str, key: str) -> tuple[int, int] | None:
    """Line span [start, end) of top-level `key`'s block, or None.

    The block is the ``key:`` line plus every following line until the next
    line whose first character is non-whitespace (the next top-level key or
    a column-0 ``#`` comment). Trailing blank lines are excluded — they
    belong to the gap between blocks and must survive a replacement.
    """
    lines = fm.splitlines(keepends=True)
    pat = re.compile(rf"^{re.escape(key)}\s*:")
    start = None
    for i, ln in enumerate(lines):
        if pat.match(ln):
            start = i
            break
    if start is None:
        return None
    end = len(lines)
    for j in range(start + 1, len(lines)):
        stripped = lines[j].rstrip("\r\n")
        if stripped and not lines[j][0].isspace():
            end = j
            break
    while end - 1 > start and lines[end - 1].strip() == "":
        end -= 1
    return start, end


def get_block(fm: str, key: str) -> str | None:
    span = key_span(fm, key)
    if span is None:
        return None
    lines = fm.splitlines(keepends=True)
    return "".join(lines[span[0]:span[1]])


def replace_key_block(fm: str, key: str, block: str) -> str:
    """Replace top-level `key`'s block with `block` (append if absent).

    Every byte outside the replaced span is preserved. `block` must end
    with a newline.
    """
    if not block.endswith("\n"):
        raise FrontmatterError("replacement block must end with a newline")
    lines = fm.splitlines(keepends=True)
    span = key_span(fm, key)
    if span is None:
        base = fm if (fm == "" or fm.endswith("\n")) else fm + newline_of(fm)
        return base + block
    s, e = span
    return "".join(lines[:s]) + block + "".join(lines[e:])


def insert_block_after(fm: str, after_key: str, block: str) -> str:
    """Insert `block` immediately after `after_key`'s block (or append)."""
    if not block.endswith("\n"):
        raise FrontmatterError("inserted block must end with a newline")
    span = key_span(fm, after_key)
    if span is None:
        base = fm if (fm == "" or fm.endswith("\n")) else fm + newline_of(fm)
        return base + block
    lines = fm.splitlines(keepends=True)
    return "".join(lines[: span[1]]) + block + "".join(lines[span[1]:])


# --- single-line scalar edits ------------------------------------------------

_SCALAR_LINE = re.compile(
    r"^(?P<pre>[^\s][^:]*:[ ]?)(?P<val>[^#\r\n]*?)(?P<pad>[ \t]*)(?P<comment>#[^\r\n]*)?(?P<eol>\r?\n?)$"
)


def set_scalar(fm: str, key: str, value: str) -> str:
    """Set the value on a top-level single-line scalar key.

    Preserves any inline ``# comment`` (and its padding) on that line and
    every other byte of the frontmatter. Raises if the key is absent or its
    block spans multiple lines (use replace_key_block for those).
    """
    span = key_span(fm, key)
    if span is None:
        raise FrontmatterError(f"key not found: {key}")
    if span[1] - span[0] != 1:
        raise FrontmatterError(f"key {key!r} is not a single-line scalar")
    lines = fm.splitlines(keepends=True)
    m = _SCALAR_LINE.match(lines[span[0]])
    if not m:
        raise FrontmatterError(f"cannot parse line for key {key!r}")
    if m.group("comment"):
        pad = m.group("pad") if m.group("val") else " "
        new = f"{m.group('pre')}{value}{pad}{m.group('comment')}{m.group('eol')}"
    else:
        new = f"{m.group('pre')}{value}{m.group('eol')}"
    lines[span[0]] = new
    return "".join(lines)


# --- YAML emission (only for blocks a script owns wholesale) -----------------

_PLAIN = re.compile(r"^[A-Za-z0-9._/][A-Za-z0-9._/\-]*$")
_RESERVED = {"true", "false", "null", "yes", "no", "on", "off", "~"}


def emit_scalar(v) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, _dt.datetime):
        return v.replace(microsecond=0).isoformat(sep="T")
    if isinstance(v, _dt.date):
        return v.isoformat()
    s = str(v)
    if _PLAIN.match(s) and s.lower() not in _RESERVED and not _looks_numeric(s):
        return s
    return json.dumps(s, ensure_ascii=False)


def _looks_numeric(s: str) -> bool:
    try:
        float(s)
        return True
    except ValueError:
        return False


def emit_mapping_block(key: str, value: dict, *, comments: dict[str, str] | None = None,
                       order: list[str] | None = None, nl: str = "\n", indent: int = 0) -> str:
    """Emit ``key:`` and its nested mapping as block YAML (2-space indents).

    Scalars inline; lists of scalars as flow (``["a", "b"]``); lists of
    mappings as one flow mapping per line; nested dicts recurse. `comments`
    adds a stable inline comment after named child keys. Output is plain
    YAML, loadable by yaml.safe_load, deterministic across runs.
    """
    comments = comments or {}
    pad = " " * indent
    out = [f"{pad}{key}:{nl}"]
    keys = list(value.keys())
    if order:
        keys = [k for k in order if k in value] + [k for k in keys if k not in order]
    for k in keys:
        v = value[k]
        cpad = " " * (indent + 2)
        comment = f"    # {comments[k]}" if k in comments else ""
        if isinstance(v, dict):
            out.append(emit_mapping_block(k, v, nl=nl, indent=indent + 2))
        elif isinstance(v, list):
            if all(isinstance(i, dict) for i in v) and v:
                out.append(f"{cpad}{k}:{comment}{nl}")
                for item in v:
                    inner = ", ".join(f"{ik}: {emit_scalar(iv)}" for ik, iv in item.items())
                    out.append(f"{cpad}  - {{ {inner} }}{nl}")
            else:
                flow = ", ".join(emit_scalar(i) for i in v)
                out.append(f"{cpad}{k}: [{flow}]{comment}{nl}")
        else:
            sval = emit_scalar(v)
            sep = " " if sval else ""
            out.append(f"{cpad}{k}:{sep}{sval}{comment}{nl}")
    return "".join(out)


# --- safety net --------------------------------------------------------------

def verify_untouched(before_fm: str, after_fm: str, owned_keys: set[str]) -> None:
    """Assert that no key outside `owned_keys` changed between two
    frontmatter texts (parsed comparison). Raises FrontmatterError on drift —
    callers must abort the write. This is the last line of defence for hard
    rule #2; the primary defence is that we never rewrite unowned bytes.
    """
    b = {k: v for k, v in parse(before_fm).items() if k not in owned_keys}
    a = {k: v for k, v in parse(after_fm).items() if k not in owned_keys}
    if b != a:
        drifted = sorted(set(b) ^ set(a) | {k for k in set(b) & set(a) if b[k] != a[k]})
        raise FrontmatterError(f"refusing write: unowned keys would change: {drifted}")
