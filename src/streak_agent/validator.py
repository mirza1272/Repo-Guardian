from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

MAX_CHARS = 250

BANNED_PHRASES: tuple[str, ...] = (
    "github streak",
    "contribution graph",
    "automatic commit",
    "automated commit",
    "maintained my streak",
    "bot generated",
    "as an ai",
    "i am an ai",
    "i completed",
    "deployed successfully",
    "fixed all bugs",
    "all tests pass",
    "pushed to production",
    "shipped",
    "merged pr",
    "opened a pull request",
    "created an issue",
    "streak agent",
    "language model",
    "llm",
    "groq",
    "langchain",
)

_URL_RE = re.compile(r"https?://|www\.\S+", re.IGNORECASE)
_HTML_RE = re.compile(r"<[a-z][^>]*>|</[a-z]+>", re.IGNORECASE)
_CODE_FENCE_RE = re.compile(r"```|~~~")
_DATE_PREFIX_RE = re.compile(r"^\s*\d{4}-\d{2}-\d{2}\s*:")
_BULLET_RE = re.compile(r"^\s*[-*]\s+")
_MULTI_SPACE_RE = re.compile(r"[ \t]{2,}")


class ValidationError(ValueError):
    pass


@dataclass
class Validator:
    max_words: int = 18
    previous_entries: list[str] = field(default_factory=list)

    def validate(self, raw: str) -> str:
        if not raw or not raw.strip():
            raise ValidationError("LLM output is empty.")

        normalised = _MULTI_SPACE_RE.sub(" ", raw).strip()
        lines = [line.strip() for line in normalised.splitlines() if line.strip()]

        if len(lines) == 0:
            raise ValidationError("LLM output contains no non-empty lines.")
        if len(lines) > 1:
            raise ValidationError(
                f"LLM output contains {len(lines)} lines; expected exactly 1. Output: {raw!r}"
            )

        sentence = lines[0]

        if _CODE_FENCE_RE.search(sentence):
            raise ValidationError(f"LLM output contains code fences: {sentence!r}")

        if _BULLET_RE.match(sentence):
            raise ValidationError(f"LLM output begins with a markdown bullet: {sentence!r}")

        if _DATE_PREFIX_RE.match(sentence):
            raise ValidationError(
                f"LLM output begins with a date prefix: {sentence!r}. "
                "The date is added automatically."
            )

        if _URL_RE.search(sentence):
            raise ValidationError(f"LLM output contains a URL: {sentence!r}")

        if _HTML_RE.search(sentence):
            raise ValidationError(f"LLM output contains HTML tags: {sentence!r}")

        words = sentence.split()
        if len(words) == 0:
            raise ValidationError("LLM output has no words after normalisation.")
        if len(words) > self.max_words:
            raise ValidationError(
                f"LLM output has {len(words)} words; limit is {self.max_words}. Output: {sentence!r}"
            )

        if len(sentence) > MAX_CHARS:
            raise ValidationError(
                f"LLM output is {len(sentence)} chars; limit is {MAX_CHARS}. Output: {sentence!r}"
            )

        lower = sentence.lower()
        for phrase in BANNED_PHRASES:
            if phrase in lower:
                raise ValidationError(f"LLM output contains banned phrase {phrase!r}: {sentence!r}")

        if sentence.lower() in [p.lower() for p in self.previous_entries]:
            raise ValidationError(f"LLM output is identical to an existing log entry: {sentence!r}")

        logger.debug("Validation passed: %r (%d words)", sentence, len(words))
        return sentence
