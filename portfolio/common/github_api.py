"""GitHub data acquisition — one concern: turning a repo name into RepoFacts.

Two sources, one interface:

- ``GitHubSource`` — the real REST client (stdlib urllib, no extra deps).
  ⚠ LIVE-UNVERIFIED: written off-site against the documented REST v3 API;
  exercise it against the real API at Stage 3 before trusting nightly runs
  (this cloud session's GitHub scope can't enumerate the account — plan F5).
- ``FixtureSource`` — reads the same facts from a JSON file, which is what
  the tests use and what lets a throwaway vault be synced at home with no
  network at all (``--source fixture:PATH``).

Consumers (sync, bootstrap, unclaimed) never talk to the network
themselves; they accept either source.
"""

from __future__ import annotations

import datetime as dt
import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .confidence import RepoFacts

API_VERSION = "2022-11-28"
USER_AGENT = "aiteam-portfolio-sync"


class SourceError(RuntimeError):
    """A repo's facts could not be fetched; callers skip the note, never write."""


def _to_date(value) -> dt.date | None:
    if value in (None, ""):
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    s = str(value)
    return dt.date.fromisoformat(s[:10])


def facts_from_dict(repo: str, d: dict) -> RepoFacts:
    """Build RepoFacts from a plain dict (fixture files, cached enumerations)."""
    known = {f for f in RepoFacts.__dataclass_fields__}
    kwargs = {}
    for k, v in d.items():
        if k not in known or k == "repo":
            kwargs.setdefault("extra", {})[k] = v
            continue
        if k in ("last_commit", "readme_last_commit", "roadmap_last_updated", "pushed_at"):
            v = _to_date(v)
        kwargs[k] = v
    return RepoFacts(repo=repo, **kwargs)


def facts_to_dict(f: RepoFacts) -> dict:
    out = {}
    for name in RepoFacts.__dataclass_fields__:
        if name in ("repo", "extra"):
            continue
        v = getattr(f, name)
        if isinstance(v, dt.date):
            v = v.isoformat()
        out[name] = v
    return out


class FixtureSource:
    """Offline source: ``{"repos": {"owner/name": {facts...}, ...}}``."""

    def __init__(self, path: str | Path):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        self._repos: dict[str, dict] = data["repos"]

    def fetch(self, repo: str) -> RepoFacts:
        try:
            return facts_from_dict(repo, self._repos[repo])
        except KeyError as exc:
            raise SourceError(f"fixture has no entry for {repo}") from exc

    def list_repos(self, user: str | None = None, orgs: tuple[str, ...] = (),
                   check_roadmap: bool = False) -> list[RepoFacts]:
        return [facts_from_dict(name, d) for name, d in sorted(self._repos.items())]


def parse_source_arg(arg: str, token: str | None = None):
    """``fixture:PATH`` -> FixtureSource; ``github`` -> GitHubSource."""
    if arg.startswith("fixture:"):
        return FixtureSource(arg.split(":", 1)[1])
    if arg == "github":
        return GitHubSource(token=token)
    raise ValueError(f"unknown source {arg!r} (use 'github' or 'fixture:PATH')")


class GitHubSource:
    """REST v3 client. ⚠ LIVE-UNVERIFIED — see module docstring."""

    def __init__(self, token: str | None = None, api: str = "https://api.github.com",
                 opener=None, timeout: int = 30):
        self.token = token
        self.api = api.rstrip("/")
        self._urlopen = opener or urllib.request.urlopen
        self.timeout = timeout

    # -- transport ------------------------------------------------------------
    def _get(self, path: str, params: dict | None = None):
        url = self.api + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": USER_AGENT,
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(url, headers=headers)
        try:
            with self._urlopen(req, timeout=self.timeout) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (404, 409):  # missing / empty repo — callers decide
                return e.code, None
            if e.code == 403:
                raise SourceError(
                    f"GitHub 403 for {path} — likely rate limit or token scope; "
                    "check GITHUB_TOKEN"
                ) from e
            raise SourceError(f"GitHub {e.code} for {path}") from e
        except urllib.error.URLError as e:
            raise SourceError(f"network error for {path}: {e.reason}") from e

    # -- facts for one repo ---------------------------------------------------
    def fetch(self, repo: str) -> RepoFacts:
        status, info = self._get(f"/repos/{repo}")
        if status != 200 or info is None:
            raise SourceError(f"repo not found or inaccessible: {repo}")
        f = RepoFacts(
            repo=repo,
            default_branch=info.get("default_branch") or "main",
            description=info.get("description") or "",
            language=info.get("language"),
            visibility="private" if info.get("private") else "public",
            archived=bool(info.get("archived")),
            fork=bool(info.get("fork")),
            pushed_at=_to_date(info.get("pushed_at")),
        )

        st, commits = self._get(f"/repos/{repo}/commits", {"per_page": 1})
        if st == 200 and commits:
            f.last_commit = _to_date(commits[0]["commit"]["committer"]["date"])

        st, res = self._get(
            "/search/issues",
            {"q": f"repo:{repo} is:issue state:open", "per_page": 1},
        )
        if st == 200 and res is not None:
            f.open_issues = int(res.get("total_count", 0))
        else:  # search can be unavailable; fall back (counts PRs too — noted)
            f.open_issues = int(info.get("open_issues_count", 0))

        st, rel = self._get(f"/repos/{repo}/releases/latest")
        if st == 200 and rel:
            f.latest_release = rel.get("tag_name")
            f.releases_present = True
        else:
            st, tags = self._get(f"/repos/{repo}/tags", {"per_page": 1})
            if st == 200 and tags:
                f.latest_release = tags[0].get("name")
                f.releases_present = True

        st, readme = self._get(f"/repos/{repo}/readme")
        if st == 200 and readme:
            f.readme_present = True
            st2, rc = self._get(
                f"/repos/{repo}/commits", {"per_page": 1, "path": readme.get("path", "README.md")}
            )
            if st2 == 200 and rc:
                f.readme_last_commit = _to_date(rc[0]["commit"]["committer"]["date"])

        st, root = self._get(f"/repos/{repo}/contents/")
        names: dict[str, str] = {}
        if st == 200 and isinstance(root, list):
            names = {e["name"].lower(): e.get("type", "file") for e in root}
        f.contributing_present = "contributing.md" in names
        f.architecture_present = "architecture.md" in names
        f.tests_dir = any(
            names.get(n) == "dir" for n in ("test", "tests", "spec", "specs", "__tests__")
        )
        roadmap_entry = next((n for n in names if n == "roadmap.md"), None)
        if roadmap_entry:
            f.roadmap_present = True
            st2, rc = self._get(f"/repos/{repo}/commits", {"per_page": 1, "path": "ROADMAP.md"})
            if st2 == 200 and rc:
                f.roadmap_last_updated = _to_date(rc[0]["commit"]["committer"]["date"])

        st, wf = self._get(f"/repos/{repo}/contents/.github/workflows")
        f.ci_config = (
            (st == 200 and isinstance(wf, list) and len(wf) > 0)
            or ".gitlab-ci.yml" in names
            or ".circleci" in names
        )
        return f

    # -- account enumeration --------------------------------------------------
    def list_repos(self, user: str | None = None, orgs: tuple[str, ...] = (),
                   check_roadmap: bool = False) -> list[RepoFacts]:
        """Light records for every repo on the account(s) (bootstrap Task 1).

        `check_roadmap=True` adds one contents call per repo — fine at ~20
        repos, skip it for bigger sweeps.
        """
        records: list[RepoFacts] = []
        endpoints = []
        if user:
            endpoints.append(f"/users/{user}/repos")
        for org in orgs:
            endpoints.append(f"/orgs/{org}/repos")
        if not endpoints:
            endpoints.append("/user/repos")  # token owner's repos, incl. private
        for ep in endpoints:
            page = 1
            while True:
                st, batch = self._get(ep, {"per_page": 100, "page": page, "sort": "pushed"})
                if st != 200 or not batch:
                    break
                for info in batch:
                    f = RepoFacts(
                        repo=info["full_name"],
                        description=info.get("description") or "",
                        language=info.get("language"),
                        visibility="private" if info.get("private") else "public",
                        archived=bool(info.get("archived")),
                        fork=bool(info.get("fork")),
                        pushed_at=_to_date(info.get("pushed_at")),
                        default_branch=info.get("default_branch") or "main",
                    )
                    if check_roadmap and not f.archived:
                        st2, _ = self._get(f"/repos/{f.repo}/contents/ROADMAP.md")
                        f.roadmap_present = st2 == 200
                    records.append(f)
                if len(batch) < 100:
                    break
                page += 1
        return records
