from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv(override=True)


@dataclass(frozen=True)
class AgentConfig:
    groq_api_key: str
    groq_model: str
    git_author_name: str
    git_author_email: str
    timezone: ZoneInfo
    target_file: str
    max_log_words: int
    dry_run: bool
    log_level: str
    github_username: str

    agent_commit_prefix: str = field(default="docs(streak-agent):", init=False, compare=False)
    max_readme_context_chars: int = field(default=4_000, init=False, compare=False)
    max_recent_commits: int = field(default=10, init=False, compare=False)
    max_log_entries: int = field(default=30, init=False, compare=False)

    def __post_init__(self) -> None:
        if not self.groq_api_key:
            raise ValueError(
                "GROQ_API_KEY is missing.\n"
                "  Locally: add it to your .env file.\n"
                "  GitHub Actions: add it as a repository Secret named GROQ_API_KEY."
            )
        if self.max_log_words < 5:
            raise ValueError("MAX_LOG_WORDS must be at least 5.")


def _parse_bool(value: str, name: str) -> bool:
    normalised = value.strip().lower()
    if normalised in {"true", "1", "yes"}:
        return True
    if normalised in {"false", "0", "no"}:
        return False
    raise ValueError(f"{name}={value!r} is not a valid boolean. Use 'true' or 'false'.")


def _parse_timezone(tz_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, KeyError) as exc:
        raise ValueError(
            f"TIMEZONE={tz_name!r} is not a valid IANA timezone name. "
            f"Example: 'Asia/Karachi'. Error: {exc}"
        ) from exc


def load_config() -> AgentConfig:
    groq_api_key = os.environ.get("GROQ_API_KEY", "").strip()
    groq_model = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile").strip()
    git_author_name = os.environ.get("GIT_AUTHOR_NAME", "Streak Agent").strip()
    git_author_email = os.environ.get("GIT_AUTHOR_EMAIL", "").strip()
    timezone_name = os.environ.get("TIMEZONE", "Asia/Karachi").strip()
    target_file = os.environ.get("TARGET_FILE", "README.md").strip()
    log_level = os.environ.get("LOG_LEVEL", "INFO").strip().upper()

    raw_max_words = os.environ.get("MAX_LOG_WORDS", "18").strip()
    try:
        max_log_words = int(raw_max_words)
    except ValueError as exc:
        raise ValueError(f"MAX_LOG_WORDS={raw_max_words!r} must be an integer.") from exc

    dry_run = _parse_bool(os.environ.get("DRY_RUN", "true").strip(), "DRY_RUN")
    timezone = _parse_timezone(timezone_name)

    if not git_author_email:
        logger.warning(
            "GIT_AUTHOR_EMAIL is not set — commit detection won't work correctly."
        )

    github_username = (
        os.environ.get("USERNAME", "").strip()
        or os.environ.get("GH_USERNAME", "").strip()
        or os.environ.get("GITHUB_USERNAME", "").strip()
    )

    cfg = AgentConfig(
        groq_api_key=groq_api_key,
        groq_model=groq_model,
        git_author_name=git_author_name,
        git_author_email=git_author_email,
        timezone=timezone,
        target_file=target_file,
        max_log_words=max_log_words,
        dry_run=dry_run,
        log_level=log_level,
        github_username=github_username,
    )
    logger.debug(
        "Config: model=%s tz=%s file=%s dry_run=%s",
        cfg.groq_model, timezone_name, cfg.target_file, cfg.dry_run,
    )
    return cfg
