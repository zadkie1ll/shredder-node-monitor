# shredder-node-monitor

Hourly monitor for Remnawave nodes. It sends a compact Telegram report with:

- external TCP checks for important ports;
- HTTP fallback checks;
- SSH checks for Docker, `remnanode`, and Xray core;
- optional Remnawave panel status, if the configured API endpoint matches the panel.

By default `NODE_MONITOR_RUN_ON_START=true`, so after the container starts it
sends the first report immediately and only then waits
`NODE_MONITOR_INTERVAL_SECONDS` before the next report.

## Run locally

```bash
cd /Users/zadkiel/apps/shredder-node-monitor
cp .env.example .env
cp nodes.example.yaml nodes.yaml
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
NODE_MONITOR_RUN_ONCE=true python -m app.main
```

## Docker

```bash
cd /Users/zadkiel/apps/shredder-node-monitor
cp .env.example .env
cp nodes.example.yaml nodes.yaml
docker compose up -d --build
docker compose logs -f
```

The compose file mounts `~/.ssh` read-only so checks can use existing SSH
aliases like `ru6` or `nodehost.pl`.

## Environment

```env
NODE_MONITOR_INTERVAL_SECONDS=3600
NODE_MONITOR_RUN_ON_START=true
NODE_MONITOR_NODES_CONFIG=nodes.yaml

MI_VPN_BOT_TOKEN=123456:token
NODE_MONITOR_TELEGRAM_CHAT_ID=123456789

PANEL_URL=https://remnawave.example.com
RW_BEARER=...
NODE_MONITOR_REMNAWAVE_NODES_ENDPOINT=/api/nodes
```

If Telegram is not configured, the report is printed to stdout.
If Remnawave API is not configured or the endpoint does not fit the panel
version, node checks still run and the report marks the panel part as
unavailable.

## Node config

```yaml
nodes:
  - name: pl
    host: pl.orpheous.ru
    remnawave_name: pl
    ports:
      - 80
      - 2222
      - 443
    http_checks:
      - name: fallback-http
        url: http://pl.orpheous.ru/
        expect_status: 204
    ssh:
      enabled: true
      host: nodehost.pl
      xray_required: true
```

`xray_required: true` means the SSH check fails if `xray=missing` is found.
For a freshly added node before Remnawave pushes its inbound config, temporarily
set it to `false`.
