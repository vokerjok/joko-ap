#!/usr/bin/env bash
set -e
CODE_DIR="/joko-app"
BASE_DIR="${BASE_DIR:-/joko-app/data}"
export CODE_DIR BASE_DIR
export PYTHONUNBUFFERED=1
echo "=================================================="
echo " JOKO BOT TERMINAL "
echo " CODE_DIR : $CODE_DIR"
echo " BASE_DIR : $BASE_DIR"
echo " MODE     : NO PANEL "
echo "=================================================="
mkdir -p "$BASE_DIR/chrome_profiles" "$BASE_DIR/screenshots" "$BASE_DIR/snapshots"
touch "$BASE_DIR/email.txt" "$BASE_DIR/emailshare.txt" "$BASE_DIR/mapping_profil.txt"
touch "$BASE_DIR/bot_log.txt" "$BASE_DIR/login_log.txt" "$BASE_DIR/loop_log.txt" "$BASE_DIR/buat_l>
rm -f /tmp/.X99-lock || true
if [ ! -t 0 ] || [ ! -t 1 ]; then
  echo "Container ini butuh mode interaktif."
  echo "Run pakai: docker run -it --privileged --name joko-terminal joko-terminal-pro"
  sleep 3
fi
exec "$CODE_DIR/menu.sh"