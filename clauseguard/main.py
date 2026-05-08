"""ClauseGuard CLI — run the 5-agent pipeline from the command line."""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Ensure parent directory is in path so `clauseguard` package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from clauseguard.agents.orchestrator import run_pipeline
from clauseguard.config.settings import validate_config
from clauseguard.tools.file_tools import extract_text

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    """Entry point for the ClauseGuard CLI."""
    parser = argparse.ArgumentParser(
        description="ClauseGuard — AI-Powered Contract Clause Risk Analyzer"
    )
    parser.add_argument(
        "--file",
        type=str,
        required=True,
        help="Path to the contract file (PDF, TXT, or DOCX)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="report.md",
        help="Path for the output markdown report (default: report.md)",
    )
    args = parser.parse_args()

    try:
        validate_config()
    except ValueError as e:
        logger.error("Configuration error: %s", e)
        print(f"Error: {e}")
        print("Create a .env file with your model endpoint settings or set them as environment variables.")
        sys.exit(1)

    file_path = Path(args.file)
    if not file_path.exists():
        logger.error("File not found: %s", file_path)
        print(f"Error: File not found — {file_path}")
        sys.exit(1)

    try:
        file_bytes = file_path.read_bytes()
    except Exception as e:
        logger.error("Failed to read file: %s", e)
        print(f"Error: Could not read file — {e}")
        sys.exit(1)

    try:
        raw_text = extract_text(file_bytes, file_path.name)
    except ValueError as e:
        logger.error("File parsing error: %s", e)
        print(f"Error: {e}")
        sys.exit(1)

    print(f"Analyzing {file_path.name}...")
    print()

    try:
        report = asyncio.run(run_pipeline(raw_text, file_path.name))
    except Exception as e:
        logger.error("Pipeline failed: %s", e)
        print(f"Error: Analysis failed — {e}")
        sys.exit(1)

    output_path = Path(args.output)
    try:
        output_path.write_text(report.markdown_report, encoding="utf-8")
    except Exception as e:
        logger.error("Failed to write report: %s", e)
        print(f"Error: Could not write report — {e}")
        sys.exit(1)

    print("=" * 60)
    print(f"Report saved to: {output_path}")
    print(f"Overall Risk Score: {report.summary.overall_score}/10")
    print(f"Critical: {report.summary.critical_count} | High: {report.summary.high_count} | "
          f"Medium: {report.summary.medium_count} | Low: {report.summary.low_count}")
    print()
    print("Top 3 Actions Before Signing:")
    for i, action in enumerate(report.top_3_actions, 1):
        print(f"  {i}. {action}")
    print("=" * 60)


if __name__ == "__main__":
    main()
