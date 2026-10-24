#!/bin/bash
CONF="/home/hbpc/.battery-monitor.conf"
[ -f "$CONF" ] && source "$CONF"
THRESHOLD="${THRESHOLD:-20}"
WEBHOOK_URL="${WEBHOOK_URL:-http://192.168.1.114:8644/webhooks/power-alert}"
WEBHOOK_SECRET="${WEBHOOK_SECRET:-Mj_5T5DnhhruDritRwkgRnRi5pN87EmO9QdDs2qxMQw}"
WEBSEND_ENABLED="${WEBSEND_ENABLED:-false}"
WEBSEND_URL="${WEBSEND_URL:-}"
WEBSEND_LOW="${WEBSEND_LOW:-20}"
WEBSEND_HIGH="${WEBSEND_HIGH:-80}"
WEBSEND_CMD_ON="${WEBSEND_CMD_ON:-Power%20ON}"
WEBSEND_CMD_OFF="${WEBSEND_CMD_OFF:-Power%20OFF}"
STATE_FILE="/tmp/battery_alert_state"
WS_STATE="/tmp/battery_websend_state"

mkdir -p "$(dirname "$STATE_FILE")"

cap=$(cat /sys/class/power_supply/BAT0/capacity 2>/dev/null || echo 100)
status=$(cat /sys/class/power_supply/BAT0/status 2>/dev/null || echo Unknown)
status_lc=$(echo "$status" | tr '[:upper:]' '[:lower:]')
online=$(cat /sys/class/power_supply/AC0/online 2>/dev/null || echo 0)

# ── Webhook Alert ──
need_alert=0
if [ "$online" = "0" ] && [ "$cap" -lt "$THRESHOLD" ]; then
    need_alert=1
fi

if [ "$need_alert" -eq 0 ]; then
    rm -f "$STATE_FILE"
elif [ -f "$STATE_FILE" ] && [ "$(cat "$STATE_FILE")" = "$cap" ]; then
    :
else
    curl -s --connect-timeout 5 --proxy http://192.168.1.7:7890 -X POST "$WEBHOOK_URL" \
        -H "Content-Type: application/json" \
        -d "{\"msgtype\":\"text\",\"text\":{\"content\":\"[$(hostname)] 电量低: ${cap}% (${status_lc})\"}}" >/dev/null 2>&1
    echo "$cap" > "$STATE_FILE"
fi

# ── WebSend Tasmota ──
if [ "$WEBSEND_ENABLED" = "true" ] && [ -n "$WEBSEND_URL" ]; then
    if [ "$cap" -le "$WEBSEND_LOW" ]; then
        if curl -sf -m 8 "${WEBSEND_URL}?cmnd=${WEBSEND_CMD_ON}" >/dev/null 2>&1; then
            echo "on" > "$WS_STATE"
            logger -t battery-monitor "Tasmota ON sent (cap=${cap} status=${status_lc} ac=${online})"
        else
            rm -f "$WS_STATE"
            logger -t battery-monitor "Tasmota ON FAILED (cap=${cap} status=${status_lc} ac=${online})"
        fi
    elif [ "$cap" -ge "$WEBSEND_HIGH" ]; then
        if curl -sf -m 8 "${WEBSEND_URL}?cmnd=${WEBSEND_CMD_OFF}" >/dev/null 2>&1; then
            echo "off" > "$WS_STATE"
            logger -t battery-monitor "Tasmota OFF sent (cap=${cap} status=${status_lc} ac=${online})"
        else
            rm -f "$WS_STATE"
            logger -t battery-monitor "Tasmota OFF FAILED (cap=${cap} status=${status_lc} ac=${online})"
        fi
    fi
fi