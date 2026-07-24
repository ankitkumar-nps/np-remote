# Giving live remote access (logs + fixes) in the future

You asked: *"in future I want to give live access to check logs and let Claude Code
fix/modify the code so it works without issues."* This is built in. No SSH, no
port-forwarding — everything rides the MQTT broker the device already connects to.

## What the device exposes

| Topic | What it's for | Gated by |
|---|---|---|
| `npac/<id>/log`      | **live log stream** — every log line the device prints | always on (read-only) |
| `npac/<id>/state`    | current AC state | always on |
| `npac/<id>/status`   | online / offline | always on |
| `npac/<id>/sys`      | **remote management** — push files, exec, reset, dump logs | `SYS_ENABLE = True` |
| `npac/<id>/sys/resp` | replies to `/sys` requests | — |

So **logs are always watchable** (safe, read-only). The **code-changing** channel
(`/sys`) is off by default and you switch it on only when you want work done.

## How to give access (3 steps)

1. Keep the device **online** (WiFi + MQTT connected).
2. In `config.py` set **`SYS_ENABLE = True`** and re-upload it
   (`mpremote connect COMx fs cp config.py :` then reset) — or push it remotely once
   it's on. Turn it back to `False` when the work is done.
3. Share the **broker admin credentials** (host + username + password) with whoever
   is helping (e.g. paste them into a Claude Code session on an internet-connected PC).

That's it. From then on they can:

```bash
# watch live logs for 30s
python tools/remote_admin.py <host> <user> <pass> npac1 watch 30

# ask the device for state / recent logs / memory
python tools/remote_admin.py <host> <user> <pass> npac1 sys '{"cmd":"info"}'
python tools/remote_admin.py <host> <user> <pass> npac1 sys '{"cmd":"logs"}'

# push a fixed file and reboot into it (OTA-for-scripts)
python tools/remote_admin.py <host> <user> <pass> npac1 sys '{"cmd":"put","path":"mitsubishi_ir.py","data":"<new file contents>"}'
python tools/remote_admin.py <host> <user> <pass> npac1 sys '{"cmd":"reset"}'
```

Because it's MicroPython, a "fix" is just replacing a `.py` file and rebooting —
seconds, no reflash, no cable.

## Security notes
- Treat the admin credentials like a password to your device. Use a **separate**
  MQTT user for the public web app that can't publish to `/sys` (see `HIVEMQ-SETUP.md`).
- Leave `SYS_ENABLE = False` during normal use; enable it only for a maintenance window.
- Logs never expose credentials (the firmware doesn't print them).

## Alternative: Tailscale
If you'd rather have direct shell/WebREPL access on your Tailnet, we can add MicroPython
WebREPL and reach the device over Tailscale instead. MQTT is simpler and NAT-friendly,
so it's the default here.
