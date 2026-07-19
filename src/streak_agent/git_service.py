from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CommitInfo:
    sha: str
    subject: str
    author_email: str
    author_name: str
    timestamp: datetime  # UTC-aware

    @property
    def is_agent_commit(self) -> bool:
        return self.subject.startswith("docs(streak-agent):")


class GitError(RuntimeError):
    pass


def _run(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(args, check=True, capture_output=True, text=True, cwd=cwd)
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else "(no stderr)"
        raise GitError(
            f"Git command failed: {' '.join(args)}\n"
            f"  Exit {exc.returncode}: {stderr}"
        ) from exc
    except FileNotFoundError as exc:
        raise GitError("Git not found. Make sure Git is installed and on your PATH.") from exc


def _parse_timestamp(unix_ts: str) -> datetime:
    try:
        return datetime.fromtimestamp(int(unix_ts.strip()), tz=timezone.utc)
    except (ValueError, OSError) as exc:
        raise GitError(f"Bad Git timestamp {unix_ts!r}: {exc}") from exc


class GitService:
    def __init__(
        self,
        repo_root: Path | None = None,
        agent_commit_prefix: str = "docs(streak-agent):",
    ) -> None:
        self._agent_prefix = agent_commit_prefix
        self._root = repo_root if repo_root is not None else self._resolve_root()

    def _resolve_root(self) -> Path:
        try:
            result = _run(["git", "rev-parse", "--show-toplevel"])
            return Path(result.stdout.strip())
        except GitError as exc:
            raise GitError(
                "Not inside a Git repository. Run the agent from the repo root.\n"
                f"Detail: {exc}"
            ) from exc

    def is_git_repo(self) -> bool:
        try:
            _run(["git", "rev-parse", "--git-dir"], cwd=self._root)
            return True
        except GitError:
            return False

    @property
    def root(self) -> Path:
        return self._root

    def get_repo_name(self) -> str:
        try:
            result = _run(["git", "remote", "get-url", "origin"], cwd=self._root)
            url = result.stdout.strip()
            name = url.rstrip("/").split("/")[-1]
            return name[:-4] if name.endswith(".git") else name or self._root.name
        except GitError:
            return self._root.name

    def get_recent_commits(self, max_count: int = 20) -> list[CommitInfo]:
        sep = "\x1f"
        fmt = sep.join(["%H", "%s", "%ae", "%an", "%at"])
        try:
            result = _run(
                ["git", "log", f"--max-count={max_count}", f"--format={fmt}"],
                cwd=self._root,
            )
        except GitError:
            logger.warning("Could not read commit history.")
            return []

        commits: list[CommitInfo] = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(sep)
            if len(parts) != 5:
                continue
            sha, subject, author_email, author_name, unix_ts = parts
            try:
                ts = _parse_timestamp(unix_ts)
            except GitError:
                continue
            commits.append(CommitInfo(sha=sha, subject=subject, author_email=author_email,
                                      author_name=author_name, timestamp=ts))
        return commits

    def _day_bounds(self, tz: ZoneInfo) -> tuple[datetime, datetime]:
        now = datetime.now(tz=tz)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
        end = now.replace(hour=23, minute=59, second=59, microsecond=999_999).astimezone(timezone.utc)
        return start, end

    def get_todays_commits(self, author_email: str, tz: ZoneInfo, max_count: int = 50) -> list[CommitInfo]:
        if not author_email:
            logger.warning("GIT_AUTHOR_EMAIL not set — can't filter today's commits.")
            return []
        all_commits = self.get_recent_commits(max_count=max_count)
        start, end = self._day_bounds(tz)
        return [
            c for c in all_commits
            if c.author_email.lower() == author_email.lower()
            and start <= c.timestamp <= end
        ]

    def has_genuine_user_commit_today(self, author_email: str, tz: ZoneInfo) -> bool:
        today = self.get_todays_commits(author_email=author_email, tz=tz)
        genuine = [c for c in today if not c.is_agent_commit]
        if genuine:
            logger.info("Found %d genuine commit(s) today by %s.", len(genuine), author_email)
        return bool(genuine)

    def has_agent_commit_today(self, author_email: str, tz: ZoneInfo) -> bool:
        today = self.get_todays_commits(author_email=author_email, tz=tz)
        agent = [c for c in today if c.is_agent_commit]
        if agent:
            logger.info("Agent commit already exists today (%s).", agent[0].sha[:8])
        return bool(agent)

    def get_recent_non_agent_subjects(self, max_count: int = 10) -> list[str]:
        all_commits = self.get_recent_commits(max_count=max_count * 3)
        return [c.subject for c in all_commits if not c.is_agent_commit][:max_count]

    def has_changes(self, target_file: str) -> bool:
        try:
            r1 = _run(["git", "diff", "--name-only", "HEAD", "--", target_file], cwd=self._root)
            r2 = _run(["git", "diff", "--name-only", "--", target_file], cwd=self._root)
            return bool(r1.stdout.strip()) or bool(r2.stdout.strip())
        except GitError:
            return True

    def stage_target_file(self, target_file: str) -> None:
        target_path = self._root / target_file
        if not target_path.exists():
            raise GitError(f"Cannot stage {target_file!r} — file not found at {target_path}.")
        _run(["git", "add", "--", target_file], cwd=self._root)
        logger.debug("Staged: %s", target_file)

    def verify_only_target_staged(self, target_file: str) -> None:
        result = _run(["git", "diff", "--cached", "--name-only"], cwd=self._root)
        staged = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        extra = [f for f in staged if f != target_file]
        if extra:
            raise GitError(f"Unexpected files staged: {extra}. Only {target_file!r} should be staged.")
        if not staged:
            raise GitError(f"{target_file!r} is not staged — nothing to commit.")

    def create_commit(self, date_str: str, author_name: str, author_email: str) -> str:
        message = f"docs(streak-agent): update development log for {date_str}"
        _run(["git", "config", "user.name", author_name], cwd=self._root)
        _run(["git", "config", "user.email", author_email], cwd=self._root)
        _run(["git", "commit", "--message", message], cwd=self._root)
        result = _run(["git", "rev-parse", "HEAD"], cwd=self._root)
        sha = result.stdout.strip()
        logger.info("Committed %s: %s", sha[:8], message)
        return sha

    def push(self) -> None:
        result = _run(["git", "branch", "--show-current"], cwd=self._root)
        branch = result.stdout.strip()
        if not branch:
            raise GitError("Can't determine current branch (detached HEAD?).")
        _run(["git", "push", "origin", branch], cwd=self._root)
        logger.info("Pushed to origin/%s.", branch)

    def get_current_branch(self) -> str:
        result = _run(["git", "branch", "--show-current"], cwd=self._root)
        return result.stdout.strip()

    def get_github_username(self) -> str | None:
        try:
            result = _run(["git", "remote", "get-url", "origin"], cwd=self._root)
            url = result.stdout.strip()
            if "github.com" in url:
                parts = url.split("github.com")[-1].lstrip(":").lstrip("/").split("/")
                if len(parts) >= 2:
                    return parts[0]
        except GitError:
            pass
        return None
