#!/bin/bash
CONF="/home/hbpc/.battery-monitor.conf"
[ -f "$CONF" ] && source "$CONF"
THRESHOLD="${THRESHOLD:-20}"
WEBHOOK_URL="${WEBHOOK_URL:-http://192.168.1.114:8644/webhooks/power-alert}"
WEBHOOK_SECRET="${WEBHOOK_SECRET:-Mj_5T5DnhhruDritRwkgRnRi5pN87EmO9QdDs2qxMQw}"
STATE_FILE="/tmp/battery_alert_state"

mkdir -p "$(dirname "$STATE_FILE")"

cap=$(cat /sys/class/power_supply/BAT0/capacity 2>/dev/null || echo 100)
status=$(cat /sys/class/power_supply/BAT0/status 2>/dev/null || echo Unknown)
# Convert to lowercase for webhook
status_lc=$(echo "$status" | tr '[:upper:]' '[:lower:]')
online=$(cat /sys/class/power_supply/AC0/online 2>/dev/null || echo 0)

if [ "$online" = "1" ]; then
    rm -f "$STATE_FILE"
    exit 0
fi

need_alert=0
if [ "$cap" -lt "$THRESHOLD" ]; then
    need_alert=1
fi

if [ "$need_alert" -eq 0 ]; then
    rm -f "$STATE_FILE"
    exit 0
fi

if [ -f "$STATE_FILE" ] && [ "$(cat "$STATE_FILE")" = "$cap" ]; then
    exit 0
fi

curl -s -X POST "$WEBHOOK_URL" \
    -H "Content-Type: application/json" \
    -H "X-Webhook-Secret: $WEBHOOK_SECRET" \
    -d "{\"host\":\"$(hostname)\",\"level\":$cap,\"status\":\"$status_lc\"}" >/dev/null 2>&1

echo "$cap" > "$STATE_FILE"