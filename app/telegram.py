from __future__ import annotations

import asyncio
import json
import logging
from urllib import request
from urllib.error import HTTPError, URLError


class TelegramNotifier:
    def __init__(
        self,
        bot_token: str,
        chat_ids: list[int],
        timeout_seconds: int = 15,
    ) -> None:
        self._api = TelegramBotApi(bot_token=bot_token, timeout_seconds=timeout_seconds)
        self._chat_ids = chat_ids

    async def send(self, text: str) -> int:
        sent = 0
        chunks = _split_message(text)
        for chat_id in self._chat_ids:
            chat_ok = True
            for index, chunk in enumerate(chunks, start=1):
                if len(chunks) > 1:
                    chunk = f"<b>Part {index}/{len(chunks)}</b>\n\n{chunk}"
                ok = await self._api.send_message(chat_id=chat_id, text=chunk)
                chat_ok = chat_ok and ok
            if chat_ok:
                sent += 1
        return sent


class TelegramBotApi:
    def __init__(self, bot_token: str, timeout_seconds: int = 30) -> None:
        self._bot_token = bot_token
        self._timeout_seconds = timeout_seconds
        self._log = logging.getLogger(self.__class__.__name__)

    async def get_updates(self, offset: int | None = None, timeout: int = 25):
        payload = {
            "timeout": timeout,
            "allowed_updates": ["message", "callback_query"],
        }
        if offset is not None:
            payload["offset"] = offset
        result = await asyncio.to_thread(self._request, "getUpdates", payload)
        return result or []

    async def send_message(
        self,
        chat_id: int,
        text: str,
        reply_markup: dict | None = None,
    ) -> bool:
        payload = _message_payload(chat_id, text)
        if reply_markup:
            payload["reply_markup"] = reply_markup
        result = await asyncio.to_thread(self._request, "sendMessage", payload)
        return result is not None

    async def edit_message_text(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        reply_markup: dict | None = None,
    ) -> bool:
        payload = _message_payload(chat_id, text)
        payload["message_id"] = message_id
        if reply_markup:
            payload["reply_markup"] = reply_markup
        result = await asyncio.to_thread(self._request, "editMessageText", payload)
        return result is not None

    async def answer_callback_query(
        self,
        callback_query_id: str,
        text: str | None = None,
    ) -> None:
        payload = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
        await asyncio.to_thread(self._request, "answerCallbackQuery", payload)

    def _request(self, method: str, payload: dict):
        req = request.Request(
            f"https://api.telegram.org/bot{self._bot_token}/{method}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self._timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
                if 200 <= response.status < 300 and body.get("ok") is True:
                    return body.get("result")
                self._log.warning("telegram %s failed: %s", method, body)
                return None
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            self._log.warning(
                "telegram %s failed: HTTP %s body=%s",
                method,
                exc.code,
                body[:1000],
            )
            return None
        except URLError:
            self._log.exception("telegram %s failed", method)
            return None


def _message_payload(chat_id: int, text: str) -> dict:
    return {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }


def _split_message(text: str, limit: int = 3600) -> list[str]:
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for block in text.split("\n\n"):
        block_len = len(block) + 2
        if current and current_len + block_len > limit:
            chunks.append("\n\n".join(current))
            current = []
            current_len = 0

        if block_len > limit:
            for line in block.splitlines():
                line_len = len(line) + 1
                if current and current_len + line_len > limit:
                    chunks.append("\n".join(current))
                    current = []
                    current_len = 0
                current.append(line)
                current_len += line_len
            continue

        current.append(block)
        current_len += block_len

    if current:
        chunks.append("\n\n".join(current))
    return chunks
