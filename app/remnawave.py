from __future__ import annotations

import logging
from typing import Any

import httpx


class RemnawaveClient:
    def __init__(
        self,
        base_url: str,
        bearer: str,
        nodes_endpoint: str = "/api/nodes",
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._bearer = bearer
        self._nodes_endpoint = nodes_endpoint
        self._log = logging.getLogger(self.__class__.__name__)

    async def fetch_node_list(self) -> tuple[list[dict[str, Any]], str | None]:
        url = f"{self._base_url}{self._nodes_endpoint}"
        headers = {"Authorization": f"Bearer {self._bearer}"}
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:
            self._log.warning("failed to fetch Remnawave nodes: %s", exc)
            return [], f"{type(exc).__name__}: {exc}"

        return [
            node for node in _extract_nodes(payload)
            if isinstance(node, dict)
        ], None

    async def fetch_nodes(self) -> tuple[dict[str, dict[str, Any]], str | None]:
        nodes, error = await self.fetch_node_list()
        if error:
            return {}, error
        return _index_nodes(nodes), None


def _index_nodes(payload: Any) -> dict[str, dict[str, Any]]:
    nodes = payload if isinstance(payload, list) else _extract_nodes(payload)
    result: dict[str, dict[str, Any]] = {}
    for node in nodes:
        if not isinstance(node, dict):
            continue
        for key in ("name", "nodeName", "address", "host", "hostname", "uuid"):
            value = node.get(key)
            if isinstance(value, str) and value:
                result[value.lower()] = node
    return result


def _extract_nodes(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in ("nodes", "response", "data", "items"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            nested = _extract_nodes(value)
            if nested:
                return nested
    return []
