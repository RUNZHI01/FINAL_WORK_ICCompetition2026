#!/bin/bash
# launches tcp_server detached via setsid
pkill -f 'tcp_server.py' 2>/dev/null
sleep 1
setsid bash -c 'MLKEM_AUTH_ENABLED=0 exec /home/user/anaconda3/envs/mlkem/bin/python -u /home/user/tcp_server.py --host 0.0.0.0 --port 9527 --status-port 8080 --suite SM4_GCM >/tmp/ts_manual.log 2>&1' </dev/null >/dev/null 2>&1
disown 2>/dev/null
sleep 4
echo ALIVE=$(pgrep -fc tcp_server.py)
pgrep -af tcp_server.py | head -2
echo ---status---
curl -s http://127.0.0.1:8080/status
echo
echo ---log---
tail -5 /tmp/ts_manual.log
