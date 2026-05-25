#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/config.yaml"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "错误: 找不到 $CONFIG_FILE"
    echo "请先复制 config_example.yaml 为 config.yaml 并修改配置。"
    exit 1
fi

PORT=$(python3 -c "
import yaml
with open('$CONFIG_FILE', 'r') as f:
    cfg = yaml.safe_load(f)
print(cfg['listen_port'])
")

echo "使用端口: $PORT"
echo "配置文件: $CONFIG_FILE"

cd "$SCRIPT_DIR"
exec gunicorn \
    -w 4 \
    -b "127.0.0.1:$PORT" \
    --access-logfile - \
    --error-logfile - \
    wsgi:application
