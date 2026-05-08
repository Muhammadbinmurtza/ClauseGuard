"""Report formatting utilities for ClauseGuard."""

from clauseguard.models.findings import Severity
from clauseguard.models.report import FinalReport

SEVERITY_EMOJI_MAP = {
    Severity.CRITICAL: "🔴",
    Severity.HIGH: "🟠",
    Severity.MEDIUM: "🟡",
    Severity.LOW: "🟢",
    Severity.INFO: "ℹ️",
}

SEVERITY_COLOR_MAP = {
    Severity.CRITICAL: "#FF0000",
    Severity.HIGH: "#FF8C00",
    Severity.MEDIUM: "#FFD700",
    Severity.LOW: "#32CD32",
    Severity.INFO: "#1E90FF",
}


def severity_badge(severity: Severity) -> str:
    """Return the emoji badge for a severity level.

    Alias for severity_emoji — matches PRD specification.

    Args:
        severity: The Severity enum value.

    Returns:
        The corresponding emoji string.
    """
    return SEVERITY_EMOJI_MAP.get(severity, "⚪")


def severity_emoji(severity: Severity) -> str:
    """Return the emoji representation for a severity level.

    Args:
        severity: The Severity enum value.

    Returns:
        The corresponding emoji string.
    """
    return severity_badge(severity)


def risk_color(severity: Severity) -> str:
    """Return the hex color code for a severity level.

    Alias for severity_color — matches PRD specification.

    Args:
        severity: The Severity enum value.

    Returns:
        The corresponding hex color string.
    """
    return SEVERITY_COLOR_MAP.get(severity, "#808080")


def severity_color(severity: Severity) -> str:
    """Return the hex color code for a severity level.

    Args:
        severity: The Severity enum value.

    Returns:
        The corresponding hex color string.
    """
    return risk_color(severity)


def format_markdown(report: FinalReport) -> str:
    """Convert a FinalReport to a formatted markdown string.

    Args:
        report: The FinalReport to format.

    Returns:
        The fully formatted markdown report string.
    """
    return report.markdown_report
