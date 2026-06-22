from __future__ import annotations

import asyncio
import logging
from html import escape

from app.config import Settings
from app.monitor import Monitor
from app.report import format_node_detail
from app.telegram import TelegramBotApi


class NodeMonitorBot:
    def __init__(
        self,
        settings: Settings,
        api: TelegramBotApi,
        load_nodes,
        remnawave_client,
    ) -> None:
        self._settings = settings
        self._api = api
        self._load_nodes = load_nodes
        self._remnawave_client = remnawave_client
        self._allowed_chat_ids = set(settings.telegram_chat_ids)
        self._message_thread_id = settings.telegram_message_thread_id
        self._log = logging.getLogger(self.__class__.__name__)
        self._offset: int | None = None

    async def run_forever(self) -> None:
        self._log.info("telegram polling started")
        while True:
            try:
                updates = await self._api.get_updates(
                    offset=self._offset,
                    timeout=25,
                )
                for update in updates:
                    self._offset = int(update["update_id"]) + 1
                    await self._handle_update(update)
            except asyncio.CancelledError:
                raise
            except Exception:
                self._log.exception("telegram polling failed")
                await asyncio.sleep(self._settings.telegram_poll_interval_seconds)

    async def _handle_update(self, update: dict) -> None:
        if "message" in update:
            await self._handle_message(update["message"])
        elif "callback_query" in update:
            await self._handle_callback(update["callback_query"])

    async def _handle_message(self, message: dict) -> None:
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        if not self._is_allowed(chat_id):
            return

        text = (message.get("text") or "").strip()
        if text in {"/start", "/nodes", "/status"}:
            await self._send_nodes_menu(chat_id)
        elif text == "/help":
            await self._api.send_message(
                chat_id=chat_id,
                text=(
                    "<b>Commands</b>\n"
                    "/nodes - список нод с кнопками\n"
                    "/status - то же самое\n"
                    "Нажми на ноду, чтобы получить подробную диагностику."
                ),
                message_thread_id=self._message_thread_id,
            )
        else:
            await self._api.send_message(
                chat_id=chat_id,
                text="Напиши /nodes, чтобы выбрать сервер для диагностики.",
                message_thread_id=self._message_thread_id,
            )

    async def _handle_callback(self, callback: dict) -> None:
        callback_id = callback.get("id")
        message = callback.get("message") or {}
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        message_id = message.get("message_id")
        data = callback.get("data") or ""

        if not self._is_allowed(chat_id):
            if callback_id:
                await self._api.answer_callback_query(callback_id, "Not allowed")
            return

        if callback_id:
            await self._api.answer_callback_query(callback_id, "Проверяю...")

        if data == "nodes:refresh":
            await self._send_nodes_menu(chat_id, message_id=message_id)
            return

        if not data.startswith("node:"):
            return

        try:
            index = int(data.split(":", 1)[1])
        except ValueError:
            return

        nodes = await self._load_nodes()
        if index < 0 or index >= len(nodes):
            await self._api.send_message(
                chat_id,
                "Нода не найдена, обнови список /nodes",
                message_thread_id=self._message_thread_id,
            )
            return

        node = nodes[index]
        monitor = Monitor(
            nodes=[node],
            remnawave_client=self._remnawave_client,
            fail_on_remnawave_disconnected=(
                self._settings.remnawave_fail_on_disconnected
            ),
            detail_limit=2500,
        )
        report = await monitor.collect()
        text = format_node_detail(report.nodes[0], index=index, total=len(nodes))
        await self._api.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=_node_detail_keyboard(index),
            message_thread_id=self._message_thread_id,
        )

    async def _send_nodes_menu(
        self,
        chat_id: int,
        message_id: int | None = None,
    ) -> None:
        nodes = await self._load_nodes()
        panel_nodes = {}
        if self._remnawave_client is not None:
            panel_nodes, _ = await self._remnawave_client.fetch_nodes()
        text = _format_nodes_menu(nodes, panel_nodes)
        keyboard = _nodes_keyboard(nodes, panel_nodes)
        if message_id is not None:
            ok = await self._api.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=keyboard,
            )
            if ok:
                return
        await self._api.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=keyboard,
            message_thread_id=self._message_thread_id,
        )

    def _is_allowed(self, chat_id) -> bool:
        return isinstance(chat_id, int) and chat_id in self._allowed_chat_ids


def _format_nodes_menu(nodes, panel_nodes: dict) -> str:
    lines = [
        "<b>Выбери ноду для диагностики</b>",
        "🟢 connected · 🟡 connecting/offline · 🔴 disabled",
        "",
    ]
    for index, node in enumerate(nodes, start=1):
        state = _panel_state(node, panel_nodes)
        lines.append(
            f"{index}. {state} <b>{escape(node.name)}</b>\n"
            f"   <code>{escape(node.host)}</code>"
        )
    return "\n".join(lines)


def _nodes_keyboard(nodes, panel_nodes: dict) -> dict:
    rows = []
    current = []
    for index, node in enumerate(nodes):
        state = _panel_state(node, panel_nodes)
        current.append(
            {
                "text": f"{index + 1}. {state} {node.name[:18]}",
                "callback_data": f"node:{index}",
            }
        )
        if len(current) == 2:
            rows.append(current)
            current = []
    if current:
        rows.append(current)
    rows.append([{"text": "Обновить список", "callback_data": "nodes:refresh"}])
    return {"inline_keyboard": rows}


def _node_detail_keyboard(index: int) -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "Обновить эту ноду", "callback_data": f"node:{index}"},
                {"text": "Список нод", "callback_data": "nodes:refresh"},
            ]
        ]
    }


def _panel_state(node, panel_nodes: dict) -> str:
    for key in (node.remnawave_name, node.name, node.host, node.remnawave_uuid):
        if key and key.lower() in panel_nodes:
            panel = panel_nodes[key.lower()]
            if panel.get("isDisabled"):
                return "🔴"
            if panel.get("isConnected"):
                return "🟢"
            return "🟡"
    return "⚪"
