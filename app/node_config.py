from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.models import HttpCheckConfig, NodeConfig, PortCheckConfig, SshCheckConfig


DEFAULT_SSH_COMMAND = (
    "set -e; "
    "docker inspect -f 'remnanode={{.State.Status}} restarts={{.RestartCount}}' "
    "remnanode; "
    "if docker exec remnanode sh -c 'pgrep -x xray >/dev/null || "
    "pgrep -x rw-core >/dev/null' >/dev/null 2>&1 || "
    "pgrep -x xray >/dev/null || pgrep -x rw-core >/dev/null; then "
    "echo xray=running; else echo xray=missing; fi; "
    "docker exec remnanode sh -c 'supervisorctl status 2>/dev/null || true'; "
    "ss -lntp | grep -E ':(80|443|9000|2222)\\b' || true"
)


def load_nodes(path: Path) -> list[NodeConfig]:
    if not path.exists():
        raise FileNotFoundError(f"nodes config not found: {path}")

    raw = yaml.safe_load(path.read_text()) or {}
    nodes_raw = raw.get("nodes", [])
    if not isinstance(nodes_raw, list):
        raise ValueError("nodes config must contain a list under 'nodes'")

    nodes: list[NodeConfig] = []
    for item in nodes_raw:
        if not isinstance(item, dict):
            raise ValueError("each node must be an object")
        nodes.append(_parse_node(item))
    return nodes


def _parse_node(raw: dict[str, Any]) -> NodeConfig:
    name = _required_str(raw, "name")
    host = _required_str(raw, "host")
    ports = [_parse_port(item, host) for item in raw.get("ports", [])]
    http_checks = [_parse_http(item) for item in raw.get("http_checks", [])]
    ssh = _parse_ssh(raw.get("ssh", {}))

    return NodeConfig(
        name=name,
        host=host,
        remnawave_name=_optional_str(raw, "remnawave_name"),
        ports=ports,
        http_checks=http_checks,
        ssh=ssh,
    )


def _parse_port(raw: Any, default_host: str) -> PortCheckConfig:
    if isinstance(raw, int):
        return PortCheckConfig(port=raw, host=default_host)
    if not isinstance(raw, dict):
        raise ValueError("port check must be an integer or object")
    return PortCheckConfig(
        name=_optional_str(raw, "name"),
        host=_optional_str(raw, "host") or default_host,
        port=int(raw["port"]),
        timeout_seconds=float(raw.get("timeout_seconds", 5.0)),
    )


def _parse_http(raw: dict[str, Any]) -> HttpCheckConfig:
    if not isinstance(raw, dict):
        raise ValueError("http check must be an object")
    return HttpCheckConfig(
        name=_required_str(raw, "name"),
        url=_required_str(raw, "url"),
        expect_status=(
            int(raw["expect_status"]) if raw.get("expect_status") is not None else None
        ),
        timeout_seconds=float(raw.get("timeout_seconds", 10.0)),
    )


def _parse_ssh(raw: dict[str, Any]) -> SshCheckConfig:
    if not raw:
        return SshCheckConfig()
    if not isinstance(raw, dict):
        raise ValueError("ssh check must be an object")
    return SshCheckConfig(
        enabled=bool(raw.get("enabled", False)),
        host=_optional_str(raw, "host"),
        command=_optional_str(raw, "command") or DEFAULT_SSH_COMMAND,
        timeout_seconds=int(raw.get("timeout_seconds", 20)),
        xray_required=bool(raw.get("xray_required", True)),
    )


def _required_str(raw: dict[str, Any], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} is required")
    return value


def _optional_str(raw: dict[str, Any], key: str) -> str | None:
    value = raw.get(key)
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")
    return value
