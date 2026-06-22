from __future__ import annotations

from html import escape
from typing import Any
from zoneinfo import ZoneInfo

from app.models import MonitorReport, NodeConfig, NodeReport


def format_report(report: MonitorReport, tz_name: str = "Europe/Moscow") -> str:
    tz = ZoneInfo(tz_name)
    created_at = report.created_at.astimezone(tz).strftime("%Y-%m-%d %H:%M:%S %Z")
    lines = [
        f"<b>Shredder node monitor: {'OK' if report.ok else 'FAIL'}</b>",
        f"Time: <code>{escape(created_at)}</code>",
        f"Nodes: <b>{_ok_count(report)}/{len(report.nodes)}</b> ok",
    ]
    if report.remnawave_error:
        lines.append(f"Remnawave: <code>{escape(report.remnawave_error)}</code>")

    for node_report in report.nodes:
        lines.extend(["", _format_node(node_report)])
    return "\n".join(lines)


def format_node_detail(
    report: NodeReport,
    index: int | None = None,
    total: int | None = None,
) -> str:
    prefix = ""
    if index is not None and total is not None:
        prefix = f"#{index + 1}/{total} "

    status = "OK" if report.ok else "FAIL"
    lines = [
        f"<b>{prefix}{escape(report.node.name)}: {status}</b>",
        f"Host: <code>{escape(report.node.host)}</code>",
    ]
    if report.node.remnawave_uuid:
        lines.append(f"UUID: <code>{escape(report.node.remnawave_uuid)}</code>")

    if report.remnawave:
        lines.append("")
        lines.append("<b>Remnawave</b>")
        for key in (
            "name",
            "address",
            "port",
            "isConnected",
            "isConnecting",
            "isDisabled",
            "lastStatusMessage",
            "xrayVersion",
            "nodeVersion",
            "xrayUptime",
            "usersOnline",
            "trafficUsedBytes",
            "updatedAt",
        ):
            value = report.remnawave.get(key)
            if value is not None:
                lines.append(f"{key}: <code>{escape(str(value))}</code>")

    lines.append("")
    lines.append("<b>Checks</b>")
    for check in report.checks:
        check_status = "OK" if check.ok else "FAIL"
        latency = f" ({check.latency_ms}ms)" if check.latency_ms is not None else ""
        lines.append(
            f"{check_status} <code>{escape(check.name)}</code>{latency}\n"
            f"<pre>{escape(check.detail)}</pre>"
        )

    return "\n".join(lines)


def _format_node(report: NodeReport) -> str:
    status = "OK" if report.ok else "FAIL"
    lines = [
        f"<b>{status}</b> <b>{escape(report.node.name)}</b> "
        f"<code>{escape(report.node.host)}</code>"
    ]
    remna = _format_remnawave(report.node, report.remnawave)
    if remna:
        lines.append(f"  Remnawave: {remna}")

    for check in report.checks:
        check_status = "OK" if check.ok else "FAIL"
        latency = f" {check.latency_ms}ms" if check.latency_ms is not None else ""
        lines.append(
            "  "
            f"{check_status} <code>{escape(check.name)}</code>: "
            f"{escape(check.detail)}{latency}"
        )
    return "\n".join(lines)


def _format_remnawave(node: NodeConfig, value: dict[str, Any] | None) -> str:
    if value is None:
        return ""

    parts: list[str] = []
    for key in ("name", "nodeName", "isConnected", "isOnline", "status", "address"):
        item = value.get(key)
        if item is not None:
            parts.append(f"{key}={item}")
    if not parts:
        parts.append(f"matched={node.remnawave_name or node.name}")
    return "<code>" + escape(", ".join(parts)) + "</code>"


def _ok_count(report: MonitorReport) -> int:
    return sum(1 for node in report.nodes if node.ok)
