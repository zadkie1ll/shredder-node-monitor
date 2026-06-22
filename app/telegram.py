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
        for chat_id in self._chat_ids:
            if await asyncio.to_thread(self._send_sync, chat_id, text):
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
