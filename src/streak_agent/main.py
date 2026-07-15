from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import AgentConfig, load_config
from .git_service import GitError, GitService
from .llm_service import LLMService, build_llm_context
from .readme_service import ReadmeError, ReadmeService

logger = logging.getLogger(__name__)

EXIT_SUCCESS = 0
EXIT_CONFIG_ERROR = 1
EXIT_GIT_ERROR = 2
EXIT_README_ERROR = 3
EXIT_GENERATION_ERROR = 4
EXIT_UNEXPECTED_ERROR = 5


@dataclass
class AgentResult:
    success: bool
    exit_code: int
    message: str
    proposed_entry: str | None = None
    readme_changed: bool = False


class StreakAgent:
    def __init__(
        self,
        config: AgentConfig,
        repo_root: Path | None = None,
        force: bool = False,
        dry_run_override: bool | None = None,
    ) -> None:
        self._config = config
        self._force = force
        self._dry_run = dry_run_override if dry_run_override is not None else config.dry_run
        self._git = GitService(repo_root=repo_root, agent_commit_prefix=config.agent_commit_prefix)
        self._readme = ReadmeService(
            target_file=self._git.root / config.target_file,
            max_entries=config.max_log_entries,
        )
        self._llm = LLMService(config)

    def _today(self) -> str:
        return datetime.now(tz=self._config.timezone).strftime("%Y-%m-%d")

    def run(self) -> AgentResult:
        try:
            return self._run_internal()
        except GitError as exc:
            logger.error("Git error: %s", exc)
            return AgentResult(success=False, exit_code=EXIT_GIT_ERROR, message=str(exc))
        except ReadmeError as exc:
            logger.error("README error: %s", exc)
            return AgentResult(success=False, exit_code=EXIT_README_ERROR, message=str(exc))
        except RuntimeError as exc:
            logger.error("Generation error: %s", exc)
            return AgentResult(success=False, exit_code=EXIT_GENERATION_ERROR, message=str(exc))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected error.")
            return AgentResult(success=False, exit_code=EXIT_UNEXPECTED_ERROR, message=str(exc))

    def _run_internal(self) -> AgentResult:
        cfg = self._config
        tz: ZoneInfo = cfg.timezone

        if not self._git.is_git_repo():
            raise GitError("Not inside a Git repository. Run from the repo root.")

        logger.info("Repo: %s  |  Root: %s", self._git.get_repo_name(), self._git.root)

        date_str = self._today()
        logger.info("Date (%s): %s", cfg.timezone.key, date_str)

        if not self._force and cfg.git_author_email:
            if self._git.has_genuine_user_commit_today(cfg.git_author_email, tz):
                msg = f"Genuine commit already exists for {date_str} — nothing to do."
                logger.info(msg)
                return AgentResult(success=True, exit_code=EXIT_SUCCESS, message=msg)
        elif not self._force:
            logger.warning("GIT_AUTHOR_EMAIL not set — skipping genuine-commit check.")

        if cfg.git_author_email and self._git.has_agent_commit_today(cfg.git_author_email, tz):
            msg = f"Agent commit already exists for {date_str} — nothing to do."
            logger.info(msg)
            return AgentResult(success=True, exit_code=EXIT_SUCCESS, message=msg)

        readme_content = self._readme.read()

        if self._readme.entry_already_present(readme_content, date_str):
            msg = f"README already has an entry for {date_str} — nothing to do."
            logger.info(msg)
            return AgentResult(success=True, exit_code=EXIT_SUCCESS, message=msg)

        repo_name = self._git.get_repo_name()
        recent_subjects = self._git.get_recent_non_agent_subjects(max_count=cfg.max_recent_commits)
        existing_entries = self._readme.get_existing_entries(readme_content)
        previous_sentences = self._readme.get_previous_sentences(readme_content)

        llm_ctx = build_llm_context(
            repo_name=repo_name,
            current_date=date_str,
            readme_content=readme_content,
            recent_commit_subjects=recent_subjects,
            previous_log_entries=existing_entries,
            max_readme_chars=cfg.max_readme_context_chars,
        )

        logger.info("Generating log sentence...")
        sentence = self._llm.generate(ctx=llm_ctx, previous_sentences=previous_sentences)
        logger.info("Sentence: %r", sentence)

        new_content = self._readme.build_updated_content(
            original_content=readme_content,
            new_entry=sentence,
            date_str=date_str,
        )

        proposed_entry = f"- {date_str}: {sentence}"

        if self._dry_run:
            logger.info("[DRY-RUN] Would add: %s", proposed_entry)
            self._show_diff(readme_content, new_content)
            return AgentResult(
                success=True, exit_code=EXIT_SUCCESS,
                message="Dry-run complete. No files modified.",
                proposed_entry=sentence, readme_changed=False,
            )

        self._readme.write_atomic(new_content=new_content, original_content=readme_content)
        logger.info("README updated: %s", proposed_entry)

        return AgentResult(
            success=True, exit_code=EXIT_SUCCESS,
            message=f"README updated — {proposed_entry}",
            proposed_entry=sentence, readme_changed=True,
        )

    @staticmethod
    def _show_diff(original: str, updated: str) -> None:
        import difflib
        diff = list(difflib.unified_diff(
            original.splitlines(keepends=True),
            updated.splitlines(keepends=True),
            fromfile="README.md (before)",
            tofile="README.md (after)",
            n=3,
        ))
        if diff:
            output = "\n--- diff ---\n" + "".join(diff) + "--- end ---\n"
            # Safe print for Windows terminals that don't support UTF-8
            sys.stdout.buffer.write(output.encode("utf-8", errors="replace"))
            sys.stdout.buffer.flush()
        else:
            print("[DRY-RUN] No diff detected.")


def run(
    force: bool = False,
    dry_run_override: bool | None = None,
    repo_root: Path | None = None,
) -> AgentResult:
    try:
        config = load_config()
    except ValueError as exc:
        logger.error("Config error: %s", exc)
        return AgentResult(success=False, exit_code=EXIT_CONFIG_ERROR, message=str(exc))

    return StreakAgent(config=config, repo_root=repo_root, force=force,
                       dry_run_override=dry_run_override).run()


if __name__ == "__main__":
    result = run()
    sys.exit(result.exit_code)
