from __future__ import annotations

import asyncio
import logging

from app.models import CheckResult
from app.checks import NodeChecker
from app.models import MonitorReport, NodeConfig, NodeReport
from app.remnawave import RemnawaveClient


class Monitor:
    def __init__(
        self,
        nodes: list[NodeConfig],
        remnawave_client: RemnawaveClient | None = None,
        fail_on_remnawave_disconnected: bool = True,
        detail_limit: int = 500,
    ) -> None:
        self._nodes = nodes
        self._remnawave_client = remnawave_client
        self._fail_on_remnawave_disconnected = fail_on_remnawave_disconnected
        self._checker = NodeChecker(detail_limit=detail_limit)
        self._log = logging.getLogger(self.__class__.__name__)

    async def collect(self) -> MonitorReport:
        remnawave_nodes: dict[str, dict] = {}
        remnawave_error: str | None = None
        if self._remnawave_client is not None:
            remnawave_nodes, remnawave_error = await self._remnawave_client.fetch_nodes()

        reports = await asyncio.gather(
            *(self._check_node(node, remnawave_nodes) for node in self._nodes)
        )
        return MonitorReport.now(list(reports), remnawave_error=remnawave_error)

    async def _check_node(
        self,
        node: NodeConfig,
        remnawave_nodes: dict[str, dict],
    ) -> NodeReport:
        self._log.info("checking node %s", node.name)
        checks = await self._checker.check_node(node)
        remnawave = _match_remnawave_node(node, remnawave_nodes)
        if remnawave is not None:
            checks = [
                _remnawave_check(remnawave, self._fail_on_remnawave_disconnected),
                *checks,
            ]
        return NodeReport(
            node=node,
            ok=all(check.ok for check in checks if check.severity == "error"),
            checks=checks,
            remnawave=remnawave,
        )


def _match_remnawave_node(node: NodeConfig, remnawave_nodes: dict[str, dict]):
    keys = [
        node.remnawave_name,
        node.name,
        node.host,
    ]
    for key in keys:
        if key and key.lower() in remnawave_nodes:
            return remnawave_nodes[key.lower()]
    return None


def _remnawave_check(node: dict, fail_on_disconnected: bool) -> CheckResult:
    disabled = bool(node.get("isDisabled"))
    connected = node.get("isConnected")
    status_message = node.get("lastStatusMessage")
    ok = not disabled
    severity = "error"
    if fail_on_disconnected and connected is not True:
        ok = False
        severity = "warning"

    detail = f"panel status={_panel_status(node)}"
    if status_message:
        detail += f" message={status_message}"
    return CheckResult(
        name="remnawave",
        ok=ok,
        detail=detail,
        severity=severity,
    )


def _panel_status(node: dict) -> str:
    if node.get("isDisabled"):
        return "disabled"
    if node.get("isConnected"):
        return "connected"
    if node.get("isConnecting"):
        return "connecting"
    return "disconnected"
