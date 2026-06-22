from __future__ import annotations

import asyncio
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.models import CheckResult, HttpCheckConfig, NodeConfig, PortCheckConfig


class NodeChecker:
    def __init__(self, detail_limit: int = 500) -> None:
        self._detail_limit = detail_limit

    async def check_node(self, node: NodeConfig) -> list[CheckResult]:
        tasks: list[asyncio.Task[CheckResult]] = []
        for port in node.ports:
            tasks.append(asyncio.create_task(self.check_port(port)))
        for http_check in node.http_checks:
            tasks.append(asyncio.create_task(self.check_http(http_check)))
        if node.ssh.enabled:
            tasks.append(asyncio.create_task(self.check_ssh(node)))

        if not tasks:
            return [CheckResult(name="config", ok=False, detail="no checks configured")]
        return list(await asyncio.gather(*tasks))

    async def check_port(self, config: PortCheckConfig) -> CheckResult:
        host = config.host or "127.0.0.1"
        label = config.name or f"tcp:{host}:{config.port}"
        started = time.monotonic()
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, config.port),
                timeout=config.timeout_seconds,
            )
            writer.close()
            await writer.wait_closed()
            return CheckResult(
                name=label,
                ok=True,
                detail="open",
                latency_ms=_elapsed_ms(started),
            )
        except Exception as exc:
            return CheckResult(
                name=label,
                ok=False,
                detail=f"{type(exc).__name__}: {exc}",
                latency_ms=_elapsed_ms(started),
            )

    async def check_http(self, config: HttpCheckConfig) -> CheckResult:
        return await asyncio.to_thread(self._check_http_sync, config)

    async def check_ssh(self, node: NodeConfig) -> CheckResult:
        host = node.ssh.host or node.host
        command = node.ssh.command or "true"
        started = time.monotonic()
        process = await asyncio.create_subprocess_exec(
            "ssh",
            "-o",
            f"ConnectTimeout={min(node.ssh.timeout_seconds, 10)}",
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=accept-new",
            "-o",
            "UserKnownHostsFile=/tmp/shredder-node-monitor-known-hosts",
            host,
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=node.ssh.timeout_seconds,
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.communicate()
            return CheckResult(
                name=f"ssh:{host}",
                ok=False,
                detail=f"timeout after {node.ssh.timeout_seconds}s",
                latency_ms=_elapsed_ms(started),
            )

        out = stdout.decode(errors="replace").strip()
        err = stderr.decode(errors="replace").strip()
        combined = "\n".join(part for part in (out, err) if part)
        ok = process.returncode == 0
        if node.ssh.xray_required and "xray=missing" in combined:
            ok = False
        return CheckResult(
            name=f"ssh:{host}",
            ok=ok,
            detail=_compact(combined or f"exit={process.returncode}", self._detail_limit),
            latency_ms=_elapsed_ms(started),
        )

    def _check_http_sync(self, config: HttpCheckConfig) -> CheckResult:
        started = time.monotonic()
        req = Request(
            config.url,
            headers={"User-Agent": "shredder-node-monitor/0.1"},
            method="GET",
        )
        try:
            with urlopen(req, timeout=config.timeout_seconds) as response:
                status = response.status
                ok = config.expect_status is None or status == config.expect_status
                detail = f"HTTP {status}"
                if config.expect_status is not None and status != config.expect_status:
                    detail += f", expected {config.expect_status}"
                return CheckResult(
                    name=config.name,
                    ok=ok,
                    detail=detail,
                    latency_ms=_elapsed_ms(started),
                )
        except HTTPError as exc:
            ok = config.expect_status is not None and exc.code == config.expect_status
            return CheckResult(
                name=config.name,
                ok=ok,
                detail=f"HTTP {exc.code}",
                latency_ms=_elapsed_ms(started),
            )
        except URLError as exc:
            return CheckResult(
                name=config.name,
                ok=False,
                detail=f"URLError: {exc.reason}",
                latency_ms=_elapsed_ms(started),
            )
        except Exception as exc:
            return CheckResult(
                name=config.name,
                ok=False,
                detail=f"{type(exc).__name__}: {exc}",
                latency_ms=_elapsed_ms(started),
            )


def _elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


def _compact(value: str, limit: int = 500) -> str:
    value = " | ".join(line.strip() for line in value.splitlines() if line.strip())
    if len(value) <= limit:
        return value
    return value[: limit - 1] + "…"
