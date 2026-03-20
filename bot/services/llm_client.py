from __future__ import annotations

import json
import sys
from typing import Any, Callable

import httpx

from services.backend_client import BackendClient, BackendError

ToolHandler = Callable[..., Any]


class LLMError(Exception):
    pass


class LLMClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None,
        model: str,
        backend: BackendClient,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.backend = backend
        self.timeout = timeout
        self.tools = self._build_tools()
        self.tool_handlers = self._build_tool_handlers()

    def _build_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_items",
                    "description": "List labs and tasks available in the LMS.",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_learners",
                    "description": "List enrolled learners and their groups.",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_scores",
                    "description": "Get the score distribution histogram for a lab.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "lab": {
                                "type": "string",
                                "description": "Lab identifier such as lab-04.",
                            }
                        },
                        "required": ["lab"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_pass_rates",
                    "description": "Get per-task average scores and attempt counts for a lab.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "lab": {
                                "type": "string",
                                "description": "Lab identifier such as lab-04.",
                            }
                        },
                        "required": ["lab"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_timeline",
                    "description": "Get submissions per day for a lab.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "lab": {
                                "type": "string",
                                "description": "Lab identifier such as lab-04.",
                            }
                        },
                        "required": ["lab"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_groups",
                    "description": "Compare group performance for a lab.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "lab": {
                                "type": "string",
                                "description": "Lab identifier such as lab-04.",
                            }
                        },
                        "required": ["lab"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_top_learners",
                    "description": "Get the top learners by average score for a lab.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "lab": {
                                "type": "string",
                                "description": "Lab identifier such as lab-04.",
                            },
                            "limit": {
                                "type": "integer",
                                "description": "How many learners to return.",
                                "default": 5,
                            },
                        },
                        "required": ["lab"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_completion_rate",
                    "description": "Get the completion rate summary for a lab.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "lab": {
                                "type": "string",
                                "description": "Lab identifier such as lab-04.",
                            }
                        },
                        "required": ["lab"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "trigger_sync",
                    "description": "Refresh LMS data from the autochecker pipeline.",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
        ]

    def _build_tool_handlers(self) -> dict[str, ToolHandler]:
        return {
            "get_items": self.backend.get_items,
            "get_learners": self.backend.get_learners,
            "get_scores": self.backend.get_scores,
            "get_pass_rates": self.backend.get_pass_rates,
            "get_timeline": self.backend.get_timeline,
            "get_groups": self.backend.get_groups,
            "get_top_learners": self.backend.get_top_learners,
            "get_completion_rate": self.backend.get_completion_rate,
            "trigger_sync": self.backend.trigger_sync,
        }

    def _completion(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        if not self.api_key:
            raise LLMError("LLM error: API key is missing.")

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1,
        }
        if tools is not None:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        try:
            response = httpx.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text.strip()
            raise LLMError(
                f"LLM error: HTTP {exc.response.status_code} {exc.response.reason_phrase}. {detail}"
            ) from exc
        except httpx.HTTPError as exc:
            raise LLMError(f"LLM error: {exc}") from exc
        return response.json()

    def route(self, user_text: str) -> str:
        system_prompt = (
            "You are an LMS Telegram bot assistant. Use the available tools whenever the "
            "user asks for course data. If the request is ambiguous, ask a short clarifying "
            "question. If the user greets you or sends gibberish, respond helpfully and "
            "briefly. Prefer concrete numbers from tool results. Never invent data. "
            "Avoid emojis and keep formatting console-friendly."
        )
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ]

        for _ in range(8):
            response = self._completion(messages, tools=self.tools)
            message = response["choices"][0]["message"]
            tool_calls = message.get("tool_calls", [])

            if tool_calls:
                messages.append(
                    {
                        "role": "assistant",
                        "content": message.get("content") or "",
                        "tool_calls": tool_calls,
                    }
                )
                for tool_call in tool_calls:
                    name = tool_call["function"]["name"]
                    arguments = tool_call["function"].get("arguments") or "{}"
                    parsed_args = json.loads(arguments)
                    print(
                        f"[tool] LLM called: {name}({json.dumps(parsed_args)})",
                        file=sys.stderr,
                    )
                    handler = self.tool_handlers[name]
                    try:
                        result = handler(**parsed_args)
                    except BackendError as exc:
                        result = {"error": str(exc)}
                    count = len(result) if isinstance(result, list) else 1
                    print(f"[tool] Result: {count} record(s)", file=sys.stderr)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "name": name,
                            "content": json.dumps(result),
                        }
                    )
                print(
                    f"[summary] Feeding {len(tool_calls)} tool result(s) back to LLM",
                    file=sys.stderr,
                )
                continue

            content = (message.get("content") or "").strip()
            if content:
                return content

        raise LLMError("LLM error: tool-calling loop exceeded the safety limit.")
