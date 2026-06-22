# shredder-node-monitor

Hourly monitor for Remnawave nodes. It sends a compact Telegram report with:

- external TCP checks for important ports;
- HTTP fallback checks;
- SSH checks for Docker, `remnanode`, and Xray core;
- optional Remnawave panel status, if the configured API endpoint matches the panel.
- interactive Telegram polling: `/nodes` shows numbered node buttons; clicking a
  node runs deeper diagnostics for that exact node.

By default `NODE_MONITOR_RUN_ON_START=true`, so after the container starts it
sends the first report immediately and only then waits
`NODE_MONITOR_INTERVAL_SECONDS` before the next report.

By default `NODE_MONITOR_NODE_SOURCE=remnawave`, so the service takes the node
list from the Remnawave panel. `nodes.yaml` is only an optional override file:
use it for SSH aliases, extra HTTP checks, special expected status codes, or
`skip: true`.

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

The compose file mounts `./ssh` read-only so checks can use SSH aliases like
`ru6` or `nodehost.pl`. The deploy script creates that folder on the server.

## Deploy

Deploy to `sh.ydx.ru1` from your Mac:

```bash
/Users/zadkiel/scripts/deploy-shredder-node-monitor.sh
```

The script uploads project files, local `.env`, local `nodes.yaml`,
`~/.ssh/id_ed25519`, `~/.ssh/id_ed25519.pub`, and `~/.ssh/config`, then runs:

```bash
docker compose up -d --build
```

Default remote directory:

```text
/home/stasrised/shredder-node-monitor
```

Override target directory if needed:

```bash
REMOTE_DIR=/opt/shredder-node-monitor \
  /Users/zadkiel/scripts/deploy-shredder-node-monitor.sh sh.ydx.ru1
```

## Environment

```env
NODE_MONITOR_INTERVAL_SECONDS=3600
NODE_MONITOR_RUN_ON_START=true
NODE_MONITOR_NODE_SOURCE=remnawave
NODE_MONITOR_REMNAWAVE_FAIL_ON_DISCONNECTED=true
NODE_MONITOR_NODES_CONFIG=nodes.yaml

MI_VPN_BOT_TOKEN=123456:token
NODE_MONITOR_TELEGRAM_CHAT_ID=123456789
# or:
NODE_MONITOR_TELEGRAM_CHAT_IDS=123456789,987654321
NODE_MONITOR_TELEGRAM_POLLING_ENABLED=true

PANEL_URL=https://remnawave.example.com
RW_BEARER=...
NODE_MONITOR_REMNAWAVE_NODES_ENDPOINT=/api/nodes
```

If Telegram is not configured, the report is printed to stdout.
If Remnawave API is not configured or the endpoint does not fit the panel
version, node checks still run and the report marks the panel part as
unavailable.

## Node config overrides

```yaml
nodes:
  - name: Poland
    host: 153.76.122.197
    remnawave_name: Poland
    ports:
      - name: fallback-http-port
        host: pl.orpheous.ru
        port: 80
    http_checks:
      - name: fallback-http
        url: http://pl.orpheous.ru/
        expect_status: 204
    ssh:
      enabled: true
      host: nodehost.pl
      xray_required: true
```

When `NODE_MONITOR_NODE_SOURCE=remnawave`, each item in `nodes.yaml` is matched
against Remnawave by `name`, `host`, `remnawave_name`, or `remnawave_uuid`.
The generated node uses:

- Remnawave `address` as the host;
- Remnawave `port` as the node API TCP check;
- ports from `configProfile.activeInbounds` as inbound TCP checks.

`xray_required: true` means the SSH check fails if `xray=missing` is found.
For a freshly added node before Remnawave pushes its inbound config, temporarily
set it to `false`.
