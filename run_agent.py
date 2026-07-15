#!/usr/bin/env python3
"""Entry point for the GitHub Streak Backup Agent."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="run_agent",
        description="GitHub Streak Backup Agent -- checks today's commits and optionally adds a log entry.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview only; don't write anything.")
    parser.add_argument("--force", action="store_true", help="Skip genuine-commit check (testing only).")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    _setup_logging(verbose=args.verbose)

    logger = logging.getLogger(__name__)

    if args.dry_run:
        logger.info("Dry-run mode active.")
    if args.force:
        logger.warning("--force: genuine-commit check bypassed.")

    dry_run_override: bool | None = True if args.dry_run else None

    from src.streak_agent.main import run  # noqa: PLC0415

    result = run(force=args.force, dry_run_override=dry_run_override, repo_root=Path.cwd())

    status = "OK" if result.success else "FAIL"
    print(f"\n[{status}] {result.message}")

    if result.readme_changed:
        print(
            "\nREADME.md updated locally. Commit and push when ready:\n"
            "\n  git add README.md"
            "\n  git commit -m \"docs: update development log\""
            "\n  git push\n"
        )

    sys.exit(result.exit_code)


if __name__ == "__main__":
    main()
