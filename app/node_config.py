from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.models import HttpCheckConfig, NodeConfig, PortCheckConfig, SshCheckConfig


DEFAULT_SSH_COMMAND = (
    "set -e; "
    "DOCKER=docker; "
    "if ! docker ps >/dev/null 2>&1 && command -v sudo >/dev/null 2>&1; then "
    "DOCKER='sudo docker'; fi; "
    "$DOCKER inspect -f 'remnanode={{.State.Status}} restarts={{.RestartCount}}' "
    "remnanode; "
    "if $DOCKER exec remnanode sh -c 'pgrep -x xray >/dev/null || "
    "pgrep -x rw-core >/dev/null' >/dev/null 2>&1 || "
    "pgrep -x xray >/dev/null || pgrep -x rw-core >/dev/null; then "
    "echo xray=running; else echo xray=missing; fi; "
    "$DOCKER exec remnanode sh -c 'supervisorctl status 2>/dev/null || true'; "
    "(ss -lntp 2>/dev/null || sudo ss -lntp 2>/dev/null || true) | "
    "grep -E ':(80|443|9000|2222)\\b' || true"
)


def load_node_overrides(path: Path) -> dict[str, NodeConfig]:
    if not path.exists():
        return {}

    nodes = load_nodes(path)
    result: dict[str, NodeConfig] = {}
    for node in nodes:
        for key in (node.name, node.host, node.remnawave_name, node.remnawave_uuid):
            if key:
                result[key.lower()] = node
    return result


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
        remnawave_uuid=_optional_str(raw, "remnawave_uuid"),
        ports=ports,
        ignore_generated_ports=_parse_int_list(raw.get("ignore_generated_ports", [])),
        http_checks=http_checks,
        ssh=ssh,
        skip=bool(raw.get("skip", False)),
    )


def nodes_from_remnawave(
    remnawave_nodes: list[dict[str, Any]],
    overrides: dict[str, NodeConfig] | None = None,
) -> list[NodeConfig]:
    overrides = overrides or {}
    nodes: list[NodeConfig] = []

    for raw in remnawave_nodes:
        uuid = _raw_str(raw, "uuid")
        name = _raw_str(raw, "name") or uuid or "unknown"
        host = _raw_str(raw, "address") or _raw_str(raw, "host") or _raw_str(raw, "hostname")
        if not host:
            continue

        override = _find_override(overrides, uuid, name, host)
        if override and override.skip:
            continue

        node_port = _raw_int(raw, "port")
        ports: list[PortCheckConfig] = []
        if node_port:
            ports.append(PortCheckConfig(name="remnanode-api", host=host, port=node_port))
        for inbound_port in _extract_inbound_ports(raw):
            if inbound_port != node_port:
                ports.append(
                    PortCheckConfig(
                        name=f"inbound:{inbound_port}",
                        host=host,
                        port=inbound_port,
                    )
                )

        http_checks: list[HttpCheckConfig] = []
        ssh = SshCheckConfig(enabled=True)
        if override:
            if override.ignore_generated_ports:
                ignored = set(override.ignore_generated_ports)
                ports = [port for port in ports if port.port not in ignored]
            ports = _merge_ports(ports, override.ports, default_host=host)
            http_checks = override.http_checks
            ssh = override.ssh

        nodes.append(
            NodeConfig(
                name=name,
                host=host,
                remnawave_name=name,
                remnawave_uuid=uuid,
                ports=ports,
                ignore_generated_ports=(
                    override.ignore_generated_ports if override else []
                ),
                http_checks=http_checks,
                ssh=ssh,
            )
        )

    return nodes


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


def _parse_int_list(raw: Any) -> list[int]:
    if raw in (None, ""):
        return []
    if not isinstance(raw, list):
        raise ValueError("ignore_generated_ports must be a list")
    return [int(item) for item in raw]


def _parse_ssh(raw: dict[str, Any]) -> SshCheckConfig:
    if not raw:
        return SshCheckConfig()
    if not isinstance(raw, dict):
        raise ValueError("ssh check must be an object")
    return SshCheckConfig(
        enabled=bool(raw.get("enabled", False)),
        host=_optional_str(raw, "host"),
        users=_parse_users(raw.get("users")),
        command=_optional_str(raw, "command") or DEFAULT_SSH_COMMAND,
        timeout_seconds=int(raw.get("timeout_seconds", 20)),
        xray_required=bool(raw.get("xray_required", True)),
    )


def _parse_users(raw: Any) -> tuple[str, ...]:
    if raw in (None, ""):
        return ("root", "stasrised")
    if not isinstance(raw, list):
        raise ValueError("ssh.users must be a list")
    users = tuple(str(item).strip() for item in raw if str(item).strip())
    if not users:
        raise ValueError("ssh.users must not be empty")
    return users


def _find_override(
    overrides: dict[str, NodeConfig],
    *keys: str | None,
) -> NodeConfig | None:
    for key in keys:
        if key and key.lower() in overrides:
            return overrides[key.lower()]
    return None


def _merge_ports(
    generated: list[PortCheckConfig],
    override_ports: list[PortCheckConfig],
    default_host: str,
) -> list[PortCheckConfig]:
    result = list(generated)
    existing = {(port.host or default_host, port.port) for port in result}
    for port in override_ports:
        host = port.host or default_host
        if (host, port.port) in existing:
            continue
        result.append(port)
        existing.add((host, port.port))
    return result


def _extract_inbound_ports(raw: dict[str, Any]) -> list[int]:
    profile = raw.get("configProfile")
    if not isinstance(profile, dict):
        return []
    inbounds = profile.get("activeInbounds")
    if not isinstance(inbounds, list):
        return []

    ports: list[int] = []
    for inbound in inbounds:
        if isinstance(inbound, dict):
            port = _raw_int(inbound, "port")
            if port:
                ports.append(port)
    return sorted(set(ports))


def _raw_str(raw: dict[str, Any], key: str) -> str | None:
    value = raw.get(key)
    if value in (None, ""):
        return None
    return str(value)


def _raw_int(raw: dict[str, Any], key: str) -> int | None:
    value = raw.get(key)
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


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
