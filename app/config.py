from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _get_str(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value in (None, ""):
        return default
    return value


def _get_first_str(*names: str, default: str | None = None) -> str | None:
    for name in names:
        value = _get_str(name)
        if value is not None:
            return value
    return default


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value in (None, ""):
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


def _get_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value in (None, ""):
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _get_int_list(*names: str) -> list[int]:
    raw = ",".join(os.getenv(name, "") for name in names)
    if not raw:
        return []

    values: list[int] = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            values.append(int(item))
        except ValueError as exc:
            raise ValueError(f"{names[0]} must contain Telegram chat ids") from exc
    return values


@dataclass(frozen=True)
class Settings:
    log_level: str
    interval_seconds: int
    run_once: bool
    run_on_start: bool
    nodes_config_path: Path
    node_source: str
    remnawave_fail_on_disconnected: bool
    telegram_bot_token: str | None
    telegram_chat_ids: list[int]
    remnawave_url: str | None
    remnawave_bearer: str | None
    remnawave_nodes_endpoint: str

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            log_level=_get_str("NODE_MONITOR_LOG_LEVEL", "info") or "info",
            interval_seconds=_get_int("NODE_MONITOR_INTERVAL_SECONDS", 3600),
            run_once=_get_bool("NODE_MONITOR_RUN_ONCE"),
            run_on_start=_get_bool("NODE_MONITOR_RUN_ON_START", True),
            nodes_config_path=Path(
                _get_str("NODE_MONITOR_NODES_CONFIG", "nodes.yaml") or "nodes.yaml"
            ),
            node_source=_get_str("NODE_MONITOR_NODE_SOURCE", "remnawave") or "remnawave",
            remnawave_fail_on_disconnected=_get_bool(
                "NODE_MONITOR_REMNAWAVE_FAIL_ON_DISCONNECTED",
                True,
            ),
            telegram_bot_token=_get_first_str(
                "NODE_MONITOR_TELEGRAM_BOT_TOKEN",
                "MI_VPN_BOT_TOKEN",
            ),
            telegram_chat_ids=_get_int_list(
                "NODE_MONITOR_TELEGRAM_CHAT_IDS",
                "NODE_MONITOR_TELEGRAM_CHAT_ID",
            ),
            remnawave_url=_get_first_str(
                "NODE_MONITOR_REMNAWAVE_URL",
                "PANEL_URL",
            ),
            remnawave_bearer=_get_first_str(
                "NODE_MONITOR_REMNAWAVE_BEARER",
                "RW_BEARER",
            ),
            remnawave_nodes_endpoint=_get_str(
                "NODE_MONITOR_REMNAWAVE_NODES_ENDPOINT",
                "/api/nodes",
            )
            or "/api/nodes",
        )

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_ids)

    @property
    def remnawave_enabled(self) -> bool:
        return bool(self.remnawave_url and self.remnawave_bearer)
