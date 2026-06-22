from __future__ import annotations

import asyncio
import logging

from app.config import Settings
from app.monitor import Monitor
from app.node_config import load_node_overrides, load_nodes, nodes_from_remnawave
from app.remnawave import RemnawaveClient
from app.report import format_report
from app.telegram import TelegramNotifier


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


async def run(settings: Settings) -> None:
    configure_logging(settings.log_level)
    log = logging.getLogger("node-monitor")

    remnawave = None
    if settings.remnawave_enabled:
        remnawave = RemnawaveClient(
            base_url=settings.remnawave_url or "",
            bearer=settings.remnawave_bearer or "",
            nodes_endpoint=settings.remnawave_nodes_endpoint,
        )

    nodes = await _load_nodes(settings, remnawave, log)

    notifier = None
    if settings.telegram_enabled:
        notifier = TelegramNotifier(
            bot_token=settings.telegram_bot_token or "",
            chat_ids=settings.telegram_chat_ids,
        )

    monitor = Monitor(
        nodes=nodes,
        remnawave_client=remnawave,
        fail_on_remnawave_disconnected=settings.remnawave_fail_on_disconnected,
    )
    log.info(
        "started node monitor: nodes=%s interval=%ss telegram=%s remnawave=%s",
        len(nodes),
        settings.interval_seconds,
        notifier is not None,
        remnawave is not None,
    )
    if settings.run_once:
        log.info("run-once mode: collecting a single report now")
    elif settings.run_on_start:
        log.info(
            "run-on-start is enabled: sending first report now, then every %ss",
            settings.interval_seconds,
        )
    else:
        log.info(
            "run-on-start is disabled: first report will be sent after %ss",
            settings.interval_seconds,
        )

    first = True
    while True:
        if first and not settings.run_on_start and not settings.run_once:
            await asyncio.sleep(settings.interval_seconds)
        first = False

        report = await monitor.collect()
        text = format_report(report)
        log.info("report collected: ok=%s nodes=%s", report.ok, len(report.nodes))

        if notifier is not None:
            sent = await notifier.send(text)
            log.info("telegram report sent to %s chat(s)", sent)
        else:
            print(text)

        if settings.run_once:
            return
        await asyncio.sleep(settings.interval_seconds)


async def _load_nodes(
    settings: Settings,
    remnawave: RemnawaveClient | None,
    log: logging.Logger,
):
    source = settings.node_source.lower()
    if source not in {"remnawave", "yaml"}:
        raise ValueError("NODE_MONITOR_NODE_SOURCE must be 'remnawave' or 'yaml'")

    if source == "yaml":
        return load_nodes(settings.nodes_config_path)

    if remnawave is None:
        raise ValueError(
            "NODE_MONITOR_NODE_SOURCE=remnawave requires PANEL_URL and RW_BEARER"
        )

    remnawave_nodes, error = await remnawave.fetch_node_list()
    if error:
        raise RuntimeError(f"cannot load nodes from Remnawave: {error}")

    overrides = load_node_overrides(settings.nodes_config_path)
    nodes = nodes_from_remnawave(remnawave_nodes, overrides=overrides)
    log.info(
        "loaded nodes from Remnawave: total=%s overrides=%s",
        len(nodes),
        len(overrides),
    )
    return nodes


if __name__ == "__main__":
    asyncio.run(run(Settings.from_env()))
