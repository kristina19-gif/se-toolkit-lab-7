from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx


class BackendError(Exception):
    pass


class BackendClient:
    def __init__(self, base_url: str, api_key: str, timeout: float = 15.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    def close(self) -> None:
        self._client.close()

    def _friendly_error(self, exc: Exception, path: str) -> BackendError:
        if isinstance(exc, httpx.ConnectError):
            parsed = urlparse(self.base_url)
            host = parsed.hostname or self.base_url
            port = parsed.port or ("443" if parsed.scheme == "https" else "80")
            return BackendError(
                f"Backend error: connection refused ({host}:{port}) while requesting {path}. "
                "Check that the services are running."
            )
        if isinstance(exc, httpx.HTTPStatusError):
            status = exc.response.status_code
            phrase = exc.response.reason_phrase
            return BackendError(
                f"Backend error: HTTP {status} {phrase} while requesting {path}. "
                "The backend service may be down."
            )
        if isinstance(exc, httpx.TimeoutException):
            return BackendError(
                f"Backend error: request timed out while requesting {path}. "
                "Check that the backend is responding."
            )
        return BackendError(f"Backend error: {exc}")

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        try:
            response = self._client.request(
                method,
                path,
                params=params,
                json=json_body,
            )
            response.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            raise self._friendly_error(exc, path) from exc
        return response.json()

    def get_items(self) -> list[dict[str, Any]]:
        return self._request("GET", "/items/")

    def get_learners(self) -> list[dict[str, Any]]:
        return self._request("GET", "/learners/")

    def get_scores(self, lab: str) -> list[dict[str, Any]]:
        return self._request("GET", "/analytics/scores", params={"lab": lab})

    def get_pass_rates(self, lab: str) -> list[dict[str, Any]]:
        return self._request("GET", "/analytics/pass-rates", params={"lab": lab})

    def get_timeline(self, lab: str) -> list[dict[str, Any]]:
        return self._request("GET", "/analytics/timeline", params={"lab": lab})

    def get_groups(self, lab: str) -> list[dict[str, Any]]:
        return self._request("GET", "/analytics/groups", params={"lab": lab})

    def get_top_learners(self, lab: str, limit: int = 5) -> list[dict[str, Any]]:
        return self._request(
            "GET",
            "/analytics/top-learners",
            params={"lab": lab, "limit": limit},
        )

    def get_completion_rate(self, lab: str) -> dict[str, Any]:
        return self._request("GET", "/analytics/completion-rate", params={"lab": lab})

    def trigger_sync(self) -> dict[str, Any]:
        return self._request("POST", "/pipeline/sync", json_body={})
