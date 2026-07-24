#!/usr/bin/env python3
"""
NP ac — remote admin / live-log tool.

Lets you (or Claude Code) watch the device live and push fixes over MQTT,
from anywhere, with no physical access. Requires the broker credentials.

Usage:
  # Watch live logs + state for N seconds (read-only; works even if SYS_ENABLE=False)
  python remote_admin.py <host> <user> <pass> <dev> watch [seconds]

  # Send an AC command (same tokens as the app: on, off, temp:24, cool, f3, ...)
  python remote_admin.py <host> <user> <pass> <dev> cmd  "temp:24"

  # Remote management (needs SYS_ENABLE=True on the device)
  python remote_admin.py <host> <user> <pass> <dev> sys  '{"cmd":"info"}'
  python remote_admin.py <host> <user> <pass> <dev> sys  '{"cmd":"logs"}'
  python remote_admin.py <host> <user> <pass> <dev> sys  '{"cmd":"reset"}'
  # Push a new file, then reboot to run it:
  #   sys '{"cmd":"put","path":"main.py","data":"<...full file...>"}'
  #   sys '{"cmd":"reset"}'
"""
import sys, time, json
import paho.mqtt.client as mqtt

host, user, pw, dev, action = sys.argv[1:6]
arg = sys.argv[6] if len(sys.argv) > 6 else ""
base = f"npac/{dev}"

def on_connect(c, u, f, rc, props=None):
    print("connected rc=", rc)
    c.subscribe(base + "/#")               # log, state, status, sys/resp
    if action == "cmd":
        c.publish(base + "/cmd", arg); print("-> cmd:", arg)
    elif action == "sys":
        c.publish(base + "/sys", arg); print("-> sys:", arg)

def on_message(c, u, msg):
    print(f"  {msg.topic}: {msg.payload.decode(errors='replace')}")

cli = mqtt.Client(protocol=mqtt.MQTTv311)
cli.username_pw_set(user, pw)
cli.tls_set()
cli.on_connect = on_connect
cli.on_message = on_message
cli.connect(host, 8883, 30)
cli.loop_start()
secs = int(arg) if (action == "watch" and arg.isdigit()) else 8
print(f"listening on {base}/# for {secs}s ...")
time.sleep(secs)
cli.loop_stop()
