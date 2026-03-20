from __future__ import annotations

from dataclasses import dataclass

from handlers.commands import (
    HandlerContext,
    health_handler,
    labs_handler,
    route_slash_command,
    scores_handler,
)


@dataclass
class FakeBackend:
    items: list[dict]
    pass_rates: list[dict]

    def get_items(self) -> list[dict]:
        return self.items

    def get_pass_rates(self, _: str) -> list[dict]:
        return self.pass_rates


@dataclass
class FakeLLM:
    response: str = "ok"

    def route(self, _: str) -> str:
        return self.response


def make_context() -> HandlerContext:
    backend = FakeBackend(
        items=[
            {"type": "lab", "title": "Lab 01"},
            {"type": "task", "title": "Task 1"},
        ],
        pass_rates=[
            {"task": "Task 1", "avg_score": 75.5, "attempts": 12},
        ],
    )
    return HandlerContext(backend=backend, llm=FakeLLM())


def test_health_handler_uses_item_count() -> None:
    assert health_handler(make_context()) == "Backend is healthy. 2 items available."


def test_labs_handler_filters_non_labs() -> None:
    assert labs_handler(make_context()) == "Available labs:\n- Lab 01"


def test_scores_handler_formats_pass_rates() -> None:
    assert (
        scores_handler(make_context(), "lab-01")
        == "Pass rates for lab-01:\n- Task 1: 75.5% (12 attempts)"
    )


def test_route_slash_command_unknown_command() -> None:
    assert (
        route_slash_command("/nope", make_context())
        == "Unknown command: /nope. Try /help."
    )
