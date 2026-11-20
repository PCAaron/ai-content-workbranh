#!/bin/sh
set -eu
cd "$(dirname "$0")"
if ! docker compose version >/dev/null 2>&1; then
  echo "请先安装并启动支持 Compose V2 的 Docker，再运行本脚本。" >&2
  exit 1
fi
docker compose up --build --wait -d
if [ -t 0 ] && [ -t 1 ]; then
  docker compose exec web python manage.py first_reviewer
else
  docker compose exec -T web python manage.py first_reviewer
fi
echo "工作台已就绪：http://127.0.0.1:8000/"
