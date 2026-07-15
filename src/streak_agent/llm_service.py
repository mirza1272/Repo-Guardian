from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from .config import AgentConfig
from .validator import ValidationError, Validator

logger = logging.getLogger(__name__)

SAFE_FALLBACKS: tuple[str, ...] = (
    "Reviewed repository documentation and organized the next development steps.",
    "Revisited the project structure and clarified upcoming implementation priorities.",
    "Reviewed existing project notes and refined the planned development workflow.",
    "Organized repository documentation to keep future development work clearly structured.",
    "Examined the current project state and outlined the upcoming tasks for review.",
    "Reviewed project files and confirmed the overall development direction.",
    "Checked the repository structure and updated the approach for upcoming work.",
)


@dataclass
class LLMContext:
    repo_name: str
    current_date: str
    readme_excerpt: str
    recent_commit_subjects: list[str] = field(default_factory=list)
    previous_log_entries: list[str] = field(default_factory=list)


def _build_system_prompt(max_words: int) -> str:
    return f"""\
You generate one short development-log sentence for a software repository.

Use only the supplied repository context.

Rules:
- Return exactly one plain-text sentence.
- Maximum {max_words} words.
- Do not return markdown bullets.
- Do not include a date.
- Do not use quotation marks.
- Do not mention GitHub streaks.
- Do not mention automation, bots, agents, commits or contribution graphs.
- Do not claim that code was written, fixed, tested, deployed or completed unless the supplied context proves it.
- Do not invent technologies, features, bugs or achievements.
- Avoid repeating previous log entries.
- Prefer a modest documentation, review, planning or organization statement when evidence of implementation work is unavailable.
- Do not use exaggerated wording.
- Do not use emojis.
- Return only the sentence."""


def _build_human_message(ctx: LLMContext) -> str:
    commits = (
        "\n".join(f"  - {s}" for s in ctx.recent_commit_subjects)
        if ctx.recent_commit_subjects else "  (none)"
    )
    prev = (
        "\n".join(f"  - {e}" for e in ctx.previous_log_entries)
        if ctx.previous_log_entries else "  (none)"
    )
    return f"""\
Repository: {ctx.repo_name}
Date: {ctx.current_date}

README:
{ctx.readme_excerpt}

Recent commits:
{commits}

Previous log entries (do not repeat):
{prev}"""


class LLMService:
    def __init__(self, config: AgentConfig) -> None:
        self._config = config
        self._llm = ChatGroq(
            model=config.groq_model,
            temperature=0.2,
            max_retries=2,
            timeout=30,
        )

    def _call_llm(self, ctx: LLMContext) -> str:
        system = SystemMessage(content=_build_system_prompt(self._config.max_log_words))
        human = HumanMessage(content=_build_human_message(ctx))
        response = self._llm.invoke([system, human])
        raw = str(response.content) if hasattr(response, "content") else str(response)
        return raw.strip()

    def _select_fallback(self, previous_sentences: list[str]) -> str | None:
        lower_prev = {s.lower() for s in previous_sentences}
        for fb in SAFE_FALLBACKS:
            if fb.lower() not in lower_prev:
                return fb
        return None

    def generate(self, ctx: LLMContext, previous_sentences: list[str]) -> str:
        validator = Validator(max_words=self._config.max_log_words, previous_entries=previous_sentences)

        try:
            raw = self._call_llm(ctx)
            logger.debug("LLM output: %r", raw)
            sentence = validator.validate(raw)
            logger.info("LLM sentence accepted.")
            return sentence
        except ValidationError as exc:
            logger.warning("LLM output rejected: %s", exc)
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM call failed: %s", exc)

        if ctx.recent_commit_subjects:
            candidate = self._sentence_from_subject(ctx.recent_commit_subjects[0])
            if candidate:
                try:
                    return validator.validate(candidate)
                except ValidationError:
                    pass

        fallback = self._select_fallback(previous_sentences)
        if fallback is not None:
            try:
                return validator.validate(fallback)
            except ValidationError as exc:
                logger.warning("Fallback rejected: %s", exc)

        raise RuntimeError(
            "Could not generate a valid log sentence — "
            "LLM failed and all fallbacks are already in the log."
        )

    @staticmethod
    def _sentence_from_subject(subject: str) -> str | None:
        cleaned = re.sub(r"^[a-z]+(\([^)]+\))?:\s*", "", subject, flags=re.IGNORECASE).strip()
        if len(cleaned.split()) < 2:
            return None
        return f"Reviewed progress on {cleaned.lower().rstrip('.')}."


def build_llm_context(
    repo_name: str,
    current_date: str,
    readme_content: str,
    recent_commit_subjects: list[str],
    previous_log_entries: list[str],
    max_readme_chars: int = 4_000,
) -> LLMContext:
    if len(readme_content) > max_readme_chars:
        excerpt = readme_content[:max_readme_chars] + "\n[truncated]"
    else:
        excerpt = readme_content

    return LLMContext(
        repo_name=repo_name,
        current_date=current_date,
        readme_excerpt=excerpt,
        recent_commit_subjects=recent_commit_subjects[:10],
        previous_log_entries=previous_log_entries[:10],
    )
