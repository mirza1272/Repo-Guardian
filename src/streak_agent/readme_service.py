from __future__ import annotations

import logging
import re
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

LOG_START_MARKER = "STREAK_AGENT_LOG_START"
LOG_END_MARKER = "STREAK_AGENT_LOG_END"
PLACEHOLDER_LINE = "No automated development entries yet"

_ENTRY_RE = re.compile(r"^- \d{4}-\d{2}-\d{2}: .+$")


class ReadmeError(RuntimeError):
    pass


def _extract_section_body(content: str) -> str:
    start = content.index(LOG_START_MARKER) + len(LOG_START_MARKER)
    end = content.index(LOG_END_MARKER)
    return content[start:end]


def _parse_existing_entries(section_body: str) -> list[str]:
    entries = []
    for line in section_body.splitlines():
        line = line.strip()
        if _ENTRY_RE.match(line):
            entries.append(line[2:])  # strip leading "- "
    return entries


def _build_section_body(entries: list[str]) -> str:
    if not entries:
        return f"\n{PLACEHOLDER_LINE}\n\n"
    return "\n" + "\n".join(f"- {e}" for e in entries) + "\n\n"


class ReadmeService:
    def __init__(self, target_file: Path, max_entries: int = 30) -> None:
        self._path = target_file
        self._max_entries = max_entries

    def read(self) -> str:
        if not self._path.exists():
            raise ReadmeError(f"README not found at {self._path}.")
        try:
            content = self._path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ReadmeError(f"Cannot read {self._path}: {exc}") from exc
        if not content.strip():
            raise ReadmeError(f"{self._path} is empty.")
        return content

    def has_markers(self, content: str) -> bool:
        return LOG_START_MARKER in content and LOG_END_MARKER in content

    def get_existing_entries(self, content: str) -> list[str]:
        if not self.has_markers(content):
            return []
        try:
            return _parse_existing_entries(_extract_section_body(content))
        except (ValueError, IndexError):
            return []

    def get_previous_sentences(self, content: str) -> list[str]:
        sentences = []
        for entry in self.get_existing_entries(content):
            colon = entry.find(": ")
            if colon != -1:
                sentences.append(entry[colon + 2:])
        return sentences

    def entry_already_present(self, content: str, date_str: str) -> bool:
        return any(e.startswith(f"{date_str}:") for e in self.get_existing_entries(content))

    def _validate_markers(self, content: str) -> None:
        start_count = content.count(LOG_START_MARKER)
        end_count = content.count(LOG_END_MARKER)
        if start_count == 0 and end_count == 0:
            return
        if start_count != 1 or end_count != 1:
            raise ReadmeError(
                f"README marker integrity check failed — "
                f"found {start_count} start and {end_count} end marker(s). "
                "Each must appear exactly once."
            )
        if content.index(LOG_START_MARKER) > content.index(LOG_END_MARKER):
            raise ReadmeError(
                "Log start marker appears after the end marker. "
                "Please restore the correct order."
            )

    def build_updated_content(self, original_content: str, new_entry: str, date_str: str) -> str:
        self._validate_markers(original_content)
        formatted = f"{date_str}: {new_entry}"
        if self.has_markers(original_content):
            return self._update_existing_section(original_content, formatted, date_str)
        return self._add_new_section(original_content, formatted)

    def _update_existing_section(self, content: str, formatted_entry: str, date_str: str) -> str:
        existing = self.get_existing_entries(content)
        for entry in existing:
            if entry.startswith(f"{date_str}:"):
                logger.info("Entry for %s already in README — skipping.", date_str)
                return content

        updated = [formatted_entry] + existing
        updated = updated[: self._max_entries]
        new_body = _build_section_body(updated)

        start_end = content.index(LOG_START_MARKER) + len(LOG_START_MARKER)
        end_start = content.index(LOG_END_MARKER)
        return content[:start_end] + new_body + content[end_start:]

    def _add_new_section(self, content: str, formatted_entry: str) -> str:
        logger.info("No log markers found — adding Automated Development Log section.")
        new_body = _build_section_body([formatted_entry])
        section = (
            "\n\n## Automated Development Log\n\n"
            + LOG_START_MARKER
            + new_body
            + LOG_END_MARKER
            + "\n"
        )
        if not content.endswith("\n"):
            content += "\n"
        return content + section

    def write_atomic(self, new_content: str, original_content: str) -> None:
        if not new_content.strip():
            raise ReadmeError("Refusing to write: new README content is empty.")

        if self.has_markers(original_content):
            sc = new_content.count(LOG_START_MARKER)
            ec = new_content.count(LOG_END_MARKER)
            if sc != 1 or ec != 1:
                raise ReadmeError(
                    f"Post-update marker check failed (start={sc}, end={ec})."
                )

        self._verify_no_external_changes(original_content, new_content)

        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", suffix=".tmp",
                dir=self._path.parent, delete=False,
            ) as tmp:
                tmp.write(new_content)
                tmp_path = Path(tmp.name)
            tmp_path.replace(self._path)
        except OSError as exc:
            raise ReadmeError(f"Failed writing {self._path}: {exc}") from exc

        logger.info("README updated: %s", self._path)

    def _verify_no_external_changes(self, original: str, updated: str) -> None:
        def split(text: str) -> tuple[str, str, str]:
            if LOG_START_MARKER not in text or LOG_END_MARKER not in text:
                return text, "", ""
            s = text.index(LOG_START_MARKER)
            e = text.index(LOG_END_MARKER) + len(LOG_END_MARKER)
            return text[:s], text[s:e], text[e:]

        ob, _, oa = split(original)
        nb, _, na = split(updated)

        if ob != nb:
            raise ReadmeError("Content BEFORE the log markers changed — aborting write.")
        if oa != na:
            raise ReadmeError("Content AFTER the log markers changed — aborting write.")
