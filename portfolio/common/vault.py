"""Vault access: note discovery, atomic writes, dashboard marker blocks.

The vault is a plain directory of markdown files (Obsidian's storage).
Nothing here talks to Obsidian's REST API — unattended jobs use the
filesystem/git path per plan F1; the REST API is for interactive sessions.
"""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from typing import Iterator

from . import frontmatter as fmt

SKIP_DIRS = {".obsidian", ".git", ".trash", ".sync"}


def iter_notes(vault: Path) -> Iterator[Path]:
    for path in sorted(vault.rglob("*.md")):
        if any(part in SKIP_DIRS for part in path.relative_to(vault).parts):
            continue
        yield path


def read_note(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_note_atomic(path: Path, text: str) -> None:
    """Write via a temp file + os.replace so a crash never truncates a note."""
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


_PROJECT_LINE = re.compile(r"^project\s*:\s*(?P<val>.+?)\s*$", re.MULTILINE)


def project_of(text: str) -> str | None:
    """Fast, parse-free read of the top-level `project:` value."""
    try:
        _, fm, _ = fmt.split_note(text)
    except fmt.FrontmatterError:
        return None
    m = _PROJECT_LINE.search(fm)
    if not m:
        return None
    val = m.group("val").split("#", 1)[0].strip()
    return val.strip("\"'") or None


def find_note_by_project(vault: Path, project: str) -> Path | None:
    direct = vault / f"{project}.md"
    if direct.exists() and project_of(read_note(direct)) in (project, None):
        return direct
    for path in iter_notes(vault):
        if project_of(read_note(path)) == project:
            return path
    return None


def list_projects(vault: Path) -> dict[str, Path]:
    out: dict[str, Path] = {}
    for path in iter_notes(vault):
        p = project_of(read_note(path))
        if p and p not in out:
            out[p] = path
    return out


# --- dashboard marker blocks -------------------------------------------------
# The sync jobs own only what sits between their HTML comment markers in the
# dashboard note; everything else on that note is human territory.

def replace_marker_block(text: str, marker: str, content: str) -> str:
    """Replace the content between ``<!-- marker -->`` and ``<!-- /marker -->``.

    Returns the updated text, or raises KeyError if the markers are absent
    (callers treat that as "dashboard not set up for this block" and skip).
    `content` should not include the marker lines themselves.
    """
    open_m, close_m = f"<!-- {marker} -->", f"<!-- /{marker} -->"
    pattern = re.compile(
        re.escape(open_m) + r".*?" + re.escape(close_m), re.DOTALL
    )
    if not pattern.search(text):
        raise KeyError(f"markers not found: {marker}")
    replacement = f"{open_m}\n{content.rstrip()}\n{close_m}"
    return pattern.sub(lambda _m: replacement, text, count=1)
