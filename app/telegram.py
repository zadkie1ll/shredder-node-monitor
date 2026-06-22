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
        self._bot_token = bot_token
        self._chat_ids = chat_ids
        self._timeout_seconds = timeout_seconds
        self._log = logging.getLogger(self.__class__.__name__)

    async def send(self, text: str) -> int:
        sent = 0
        chunks = _split_message(text)
        for chat_id in self._chat_ids:
            chat_ok = True
            for index, chunk in enumerate(chunks, start=1):
                if len(chunks) > 1:
                    chunk = f"<b>Part {index}/{len(chunks)}</b>\n\n{chunk}"
                ok = await asyncio.to_thread(self._send_sync, chat_id, chunk)
                chat_ok = chat_ok and ok
            if chat_ok:
                sent += 1
        return sent

    def _send_sync(self, chat_id: int, text: str) -> bool:
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        req = request.Request(
            f"https://api.telegram.org/bot{self._bot_token}/sendMessage",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self._timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
                return 200 <= response.status < 300 and body.get("ok") is True
        except HTTPError as exc:
            self._log.warning("telegram send failed: HTTP %s", exc.code)
            return False
        except URLError:
            self._log.exception("telegram send failed")
            return False


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
            lines = block.splitlines()
            for line in lines:
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
