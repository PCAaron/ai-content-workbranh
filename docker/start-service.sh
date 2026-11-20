#!/bin/sh
set -eu
umask 077
key="$PRESS_STATE/session.key"
case "$1" in
  web)
    if [ ! -e "$key" ]; then
      tmp=$(mktemp "$PRESS_STATE/.key.XXXXXX")
      trap 'rm -f "$tmp"' EXIT
      python -c 'import secrets; print(secrets.token_urlsafe(48))' > "$tmp"
      ln "$tmp" "$key" || test -s "$key"
      rm -f "$tmp"
      trap - EXIT
    fi
    ;;
  worker) ;;
  *) echo "Unknown service: $1" >&2; exit 2 ;;
esac
PRESS_SECRET=$(cat "$key")
[ "${#PRESS_SECRET}" -ge 50 ] || { echo "Invalid persistent session key: $key" >&2; exit 1; }
export PRESS_SECRET
if [ "$1" = worker ]; then
  exec python manage.py worker
fi
python manage.py migrate --noinput
exec gunicorn press.wsgi:application --bind 0.0.0.0:8000 --workers 1 --threads 4 --timeout 60
