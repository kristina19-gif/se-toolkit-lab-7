from __future__ import annotations

from dataclasses import dataclass

from services.backend_client import BackendClient, BackendError
from services.llm_client import LLMClient, LLMError


@dataclass(slots=True)
class HandlerContext:
    backend: BackendClient
    llm: LLMClient


COMMAND_HELP = {
    "/start": "Show a welcome message and quick actions.",
    "/help": "List commands and examples.",
    "/health": "Check whether the LMS backend is responding.",
    "/labs": "List available labs from the backend.",
    "/scores <lab>": "Show per-task pass rates for a lab, for example /scores lab-04.",
}

QUICK_ACTIONS = [
    [("/health", "/health"), ("/labs", "/labs")],
    [
        ("/scores lab-04", "/scores lab-04"),
        ("Ask a question", "what labs are available?"),
    ],
]


def start_handler(_: HandlerContext) -> str:
    return (
        "Welcome to the LMS bot.\n"
        "I can check backend health, list labs, show pass rates, and answer plain-language questions."
    )


def help_handler(_: HandlerContext) -> str:
    lines = ["Available commands:"]
    lines.extend(
        f"- {command} — {description}" for command, description in COMMAND_HELP.items()
    )
    lines.append("")
    lines.append(
        'You can also ask plain questions like "which lab has the lowest pass rate?"'
    )
    return "\n".join(lines)


def health_handler(ctx: HandlerContext) -> str:
    items = ctx.backend.get_items()
    return f"Backend is healthy. {len(items)} items available."


def labs_handler(ctx: HandlerContext) -> str:
    items = ctx.backend.get_items()
    labs = [item["title"] for item in items if item.get("type") == "lab"]
    if not labs:
        return "No labs are available yet."
    return "Available labs:\n" + "\n".join(f"- {lab}" for lab in labs)


def scores_handler(ctx: HandlerContext, lab: str | None) -> str:
    if not lab:
        return "Usage: /scores <lab>. Example: /scores lab-04"
    rows = ctx.backend.get_pass_rates(lab)
    if not rows:
        return f"No pass-rate data found for {lab}."
    lines = [f"Pass rates for {lab}:"]
    for row in rows:
        lines.append(
            f"- {row['task']}: {row['avg_score']}% ({row['attempts']} attempts)"
        )
    return "\n".join(lines)


def route_slash_command(text: str, ctx: HandlerContext) -> str:
    command, _, argument = text.strip().partition(" ")
    argument = argument.strip() or None
    try:
        if command == "/start":
            return start_handler(ctx)
        if command == "/help":
            return help_handler(ctx)
        if command == "/health":
            return health_handler(ctx)
        if command == "/labs":
            return labs_handler(ctx)
        if command == "/scores":
            return scores_handler(ctx, argument)
        return f"Unknown command: {command}. Try /help."
    except BackendError as exc:
        return str(exc)


def route_any_text(text: str, ctx: HandlerContext) -> str:
    if text.strip().startswith("/"):
        return route_slash_command(text, ctx)
    try:
        return ctx.llm.route(text)
    except (BackendError, LLMError) as exc:
        return str(exc)
