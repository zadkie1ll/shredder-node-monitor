from __future__ import annotations

from html import escape
from typing import Any
from zoneinfo import ZoneInfo

from app.models import MonitorReport, NodeConfig, NodeReport


def format_report(report: MonitorReport, tz_name: str = "Europe/Moscow") -> str:
    tz = ZoneInfo(tz_name)
    created_at = report.created_at.astimezone(tz).strftime("%Y-%m-%d %H:%M:%S %Z")
    ok_nodes = [node for node in report.nodes if node.hard_ok and not node.has_warning]
    warn_nodes = [node for node in report.nodes if node.hard_ok and node.has_warning]
    fail_nodes = [node for node in report.nodes if not node.hard_ok]

    lines = [
        f"{_status_icon(report)} <b>Shredder Node Monitor</b>",
        f"Time: <code>{escape(created_at)}</code>",
        (
            "Summary: "
            f"🟢 <b>{len(ok_nodes)}</b> ok · "
            f"🟡 <b>{len(warn_nodes)}</b> warn · "
            f"🔴 <b>{len(fail_nodes)}</b> fail"
        ),
    ]
    if report.remnawave_error:
        lines.append(f"Panel: 🔴 <code>{escape(report.remnawave_error)}</code>")

    for title, nodes in (
        ("🔴 Needs attention", fail_nodes),
        ("🟡 Panel warning, checks alive", warn_nodes),
        ("🟢 Healthy", ok_nodes),
    ):
        if not nodes:
            continue
        lines.extend(["", f"<b>{title}</b>"])
        for node_report in nodes:
            lines.append(_format_node_summary(node_report))

    lines.extend(["", "Use <b>/nodes</b> to open per-node diagnostics."])
    return "\n".join(lines)


def format_node_detail(
    report: NodeReport,
    index: int | None = None,
    total: int | None = None,
) -> str:
    prefix = ""
    if index is not None and total is not None:
        prefix = f"#{index + 1}/{total} "

    lines = [
        f"{_node_icon(report)} <b>{prefix}{escape(report.node.name)}</b>",
        f"Status: <b>{_node_label(report)}</b>",
        f"Host: <code>{escape(report.node.host)}</code>",
    ]
    if report.node.remnawave_uuid:
        lines.append(f"UUID: <code>{escape(report.node.remnawave_uuid)}</code>")

    if report.remnawave:
        lines.extend(["", "<b>Panel</b>"])
        for key in (
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
                lines.append(f"{_field_name(key)}: <code>{escape(str(value))}</code>")

    checks_by_kind = _split_checks(report)
    for title, checks in (
        ("🔴 Failed checks", checks_by_kind["failed"]),
        ("🟡 Warnings", checks_by_kind["warnings"]),
        ("🟢 Passed checks", checks_by_kind["passed"]),
    ):
        if not checks:
            continue
        lines.extend(["", f"<b>{title}</b>"])
        for check in checks:
            latency = f" · {check.latency_ms}ms" if check.latency_ms is not None else ""
            lines.append(
                f"{_check_icon(check)} <code>{escape(check.name)}</code>{latency}\n"
                f"<pre>{escape(check.detail)}</pre>"
            )

    return "\n".join(lines)


def _format_node_summary(report: NodeReport) -> str:
    checks = _split_checks(report)
    remna = _remnawave_short(report.remnawave)
    suffix = f" · {remna}" if remna else ""
    return (
        f"{_node_icon(report)} <b>{escape(report.node.name)}</b> "
        f"<code>{escape(report.node.host)}</code>\n"
        f"   checks: 🟢 {len(checks['passed'])} · "
        f"🟡 {len(checks['warnings'])} · 🔴 {len(checks['failed'])}{suffix}"
    )


def _split_checks(report: NodeReport) -> dict[str, list]:
    passed = [check for check in report.checks if check.ok]
    warnings = [
        check for check in report.checks
        if not check.ok and check.severity == "warning"
    ]
    failed = [
        check for check in report.checks
        if not check.ok and check.severity == "error"
    ]
    return {"passed": passed, "warnings": warnings, "failed": failed}


def _node_icon(report: NodeReport) -> str:
    if not report.hard_ok:
        return "🔴"
    if report.has_warning:
        return "🟡"
    return "🟢"


def _node_label(report: NodeReport) -> str:
    if not report.hard_ok:
        return "FAIL"
    if report.has_warning:
        return "WARN: actual checks are alive, panel disagrees"
    return "OK"


def _status_icon(report: MonitorReport) -> str:
    if any(not node.hard_ok for node in report.nodes):
        return "🔴"
    if any(node.has_warning for node in report.nodes):
        return "🟡"
    return "🟢"


def _check_icon(check) -> str:
    if check.ok:
        return "🟢"
    if check.severity == "warning":
        return "🟡"
    return "🔴"


def _remnawave_short(value: dict[str, Any] | None) -> str:
    if not value:
        return ""
    connected = value.get("isConnected")
    connecting = value.get("isConnecting")
    users_online = value.get("usersOnline")
    parts = [f"panel connected={connected}"]
    if connecting:
        parts.append("connecting=true")
    if users_online is not None:
        parts.append(f"online={users_online}")
    return "<code>" + escape(", ".join(parts)) + "</code>"


def _field_name(key: str) -> str:
    names = {
        "isConnected": "Connected",
        "isConnecting": "Connecting",
        "isDisabled": "Disabled",
        "lastStatusMessage": "Last message",
        "xrayVersion": "Xray",
        "nodeVersion": "Remnanode",
        "xrayUptime": "Xray uptime",
        "usersOnline": "Users online",
        "trafficUsedBytes": "Traffic used",
        "updatedAt": "Updated",
    }
    return names.get(key, key)
