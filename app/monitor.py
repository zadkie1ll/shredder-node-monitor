from __future__ import annotations

import asyncio
import logging

from app.checks import NodeChecker
from app.models import MonitorReport, NodeConfig, NodeReport
from app.remnawave import RemnawaveClient


class Monitor:
    def __init__(
        self,
        nodes: list[NodeConfig],
        remnawave_client: RemnawaveClient | None = None,
    ) -> None:
        self._nodes = nodes
        self._remnawave_client = remnawave_client
        self._checker = NodeChecker()
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
        return NodeReport(
            node=node,
            ok=all(check.ok for check in checks),
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
