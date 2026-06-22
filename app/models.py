from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class PortCheckConfig:
    port: int
    host: str | None = None
    name: str | None = None
    timeout_seconds: float = 5.0


@dataclass(frozen=True)
class HttpCheckConfig:
    name: str
    url: str
    expect_status: int | None = None
    timeout_seconds: float = 10.0


@dataclass(frozen=True)
class SshCheckConfig:
    enabled: bool = False
    host: str | None = None
    command: str | None = None
    timeout_seconds: int = 20
    xray_required: bool = True


@dataclass(frozen=True)
class NodeConfig:
    name: str
    host: str
    remnawave_name: str | None = None
    remnawave_uuid: str | None = None
    ports: list[PortCheckConfig] = field(default_factory=list)
    ignore_generated_ports: list[int] = field(default_factory=list)
    http_checks: list[HttpCheckConfig] = field(default_factory=list)
    ssh: SshCheckConfig = field(default_factory=SshCheckConfig)
    skip: bool = False


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str
    latency_ms: int | None = None
    severity: str = "error"


@dataclass(frozen=True)
class NodeReport:
    node: NodeConfig
    ok: bool
    checks: list[CheckResult]
    remnawave: dict[str, Any] | None = None

    @property
    def hard_ok(self) -> bool:
        return all(check.ok for check in self.checks if check.severity == "error")

    @property
    def has_warning(self) -> bool:
        return any(not check.ok and check.severity == "warning" for check in self.checks)


@dataclass(frozen=True)
class MonitorReport:
    created_at: datetime
    nodes: list[NodeReport]
    remnawave_error: str | None = None

    @classmethod
    def now(cls, nodes: list[NodeReport], remnawave_error: str | None = None):
        return cls(
            created_at=datetime.now(timezone.utc),
            nodes=nodes,
            remnawave_error=remnawave_error,
        )

    @property
    def ok(self) -> bool:
        return all(node.hard_ok for node in self.nodes)
