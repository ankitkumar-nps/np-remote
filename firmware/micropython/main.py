# ============================================================
#  NP ac  —  main application  (ESP32-C3 / MicroPython)
#
#  Reconstructed from the original board + WiFi/MQTT/remote-mgmt.
#    BLE  : advertises "NP ac" (Nordic UART) — in-room, works with web app
#    MQTT : HiveMQ Cloud (TLS) — control from anywhere, many users
#    /sys : push new code + reboot remotely (OTA-for-scripts)
#
#  Same text commands + same JSON state on both transports, so the
#  web app never cares which path it used.
# ============================================================
import network, time, json, machine, gc
import uasyncio as asyncio
from umqtt.robust import MQTTClient

import config
from mitsubishi_ir import MitsubishiIR

# ---- topics ------------------------------------------------
BASE     = "npac/" + config.DEVICE_ID
T_CMD    = BASE + "/cmd"
T_STATE  = BASE + "/state"
T_STATUS = BASE + "/status"
T_SYS    = BASE + "/sys"
T_SYSRSP = BASE + "/sys/resp"

# ---- state -------------------------------------------------
st = {"power": False, "temp": 24, "mode": "COOL",
      "fan": "AUTO", "vane": "AUTO", "last": "None"}

ir = MitsubishiIR(config.IR_PIN)
mqtt = None
ble_tx = None          # BLE notify callback set by ble module


def state_json():
    return json.dumps(st)


def push_state():
    j = state_json()
    if ble_tx:
        try:
            ble_tx(j)
        except Exception as e:
            print("BLE notify err:", e)
    if mqtt:
        try:
            mqtt.publish(T_STATE, j, retain=True)
        except Exception as e:
            print("MQTT pub err:", e)


def apply_ir():
    ir.send_state(st["power"], st["temp"], st["mode"], st["fan"], st["vane"])
    print("IR>> %s | Pwr:%s Temp:%dC Mode:%s Fan:%s Vane:%s" % (
        st["last"], "ON" if st["power"] else "OFF",
        st["temp"], st["mode"], st["fan"], st["vane"]))


# ---- command parser (shared by BLE + MQTT) -----------------
_FAN = {"fa": ("AUTO", "Fan Auto"), "f1": ("1", "Fan Low"), "f2": ("2", "Fan Med"),
        "f3": ("3", "Fan High"), "fmax": ("MAX", "Fan Max"), "fs": ("SILENT", "Fan Silent"),
        "fan:auto": ("AUTO", "Fan Auto"), "fan:1": ("1", "Fan Low"), "fan:2": ("2", "Fan Med"),
        "fan:3": ("3", "Fan High"), "fan:max": ("MAX", "Fan Max"), "fan:silent": ("SILENT", "Fan Silent")}
_MODE = {"cool": ("COOL", "Cool"), "heat": ("HEAT", "Heat"), "dry": ("DRY", "Dry"),
         "auto": ("AUTO", "Auto"), "fanonly": ("FAN", "Fan only")}
_VANE = {"vane:auto": ("AUTO", "Vane Auto"), "vane:swing": ("SWING", "Vane Swing"),
         "vane:1": ("1", "Vane 1"), "vane:2": ("2", "Vane 2"), "vane:3": ("3", "Vane 3"),
         "vane:4": ("4", "Vane 4"), "vane:5": ("5", "Vane 5")}


def handle_command(cmd, src="?"):
    cmd = cmd.strip().lower()
    if not cmd:
        return
    print("[%s] %s" % (src, cmd))
    send_ir = True

    if cmd == "on":
        st["power"] = True;  st["last"] = "Power ON"
    elif cmd == "off":
        st["power"] = False; st["last"] = "Power OFF"
    elif cmd == "t+":
        st["temp"] = min(31, st["temp"] + 1); st["last"] = "Temp %d" % st["temp"]
    elif cmd == "t-":
        st["temp"] = max(16, st["temp"] - 1); st["last"] = "Temp %d" % st["temp"]
    elif cmd.startswith("temp:"):
        try:
            t = int(cmd[5:])
        except:
            t = -1
        if 16 <= t <= 31:
            st["temp"] = t; st["last"] = "Temp %d" % t
        else:
            send_ir = False
    elif cmd in _MODE:
        st["mode"], st["last"] = _MODE[cmd]
    elif cmd in _FAN:
        st["fan"], st["last"] = _FAN[cmd]
    elif cmd in _VANE:
        st["vane"], st["last"] = _VANE[cmd]
    elif cmd in ("s", "status"):
        send_ir = False
    elif cmd == "resend":
        pass
    else:
        print("Unknown cmd:", cmd)
        return

    if send_ir:
        apply_ir()
    push_state()


# ---- remote management (/sys) ------------------------------
def sys_reply(obj):
    if mqtt:
        try:
            mqtt.publish(T_SYSRSP, json.dumps(obj))
        except Exception as e:
            print("sys reply err:", e)


def handle_sys(payload):
    try:
        msg = json.loads(payload)
    except Exception as e:
        sys_reply({"ok": False, "err": "bad json: %s" % e}); return
    c = msg.get("cmd")
    try:
        if c == "put":                       # write/replace a file
            with open(msg["path"], "w") as f:
                f.write(msg["data"])
            sys_reply({"ok": True, "wrote": msg["path"], "len": len(msg["data"])})
        elif c == "get":                     # read a file back
            with open(msg["path"]) as f:
                sys_reply({"ok": True, "path": msg["path"], "data": f.read()})
        elif c == "eval":                    # run a snippet, return repr
            sys_reply({"ok": True, "result": repr(eval(msg["code"]))})
        elif c == "exec":                    # run statements
            exec(msg["code"]); sys_reply({"ok": True})
        elif c == "info":
            sys_reply({"ok": True, "freemem": gc.mem_free(),
                       "ip": network.WLAN(network.STA_IF).ifconfig()[0],
                       "state": st})
        elif c in ("reset", "reload"):
            sys_reply({"ok": True, "resetting": True})
            time.sleep(1); machine.reset()
        else:
            sys_reply({"ok": False, "err": "unknown sys cmd"})
    except Exception as e:
        sys_reply({"ok": False, "err": str(e)})


# ---- MQTT --------------------------------------------------
def mqtt_cb(topic, payload):
    topic = topic.decode() if isinstance(topic, bytes) else topic
    payload = payload.decode() if isinstance(payload, bytes) else payload
    if topic == T_CMD:
        handle_command(payload, "MQTT")
    elif topic == T_SYS and config.SYS_ENABLE:
        handle_sys(payload)


def mqtt_connect():
    global mqtt
    c = MQTTClient(client_id="npac-" + config.DEVICE_ID,
                   server=config.MQTT_HOST, port=config.MQTT_PORT,
                   user=config.MQTT_USER, password=config.MQTT_PASS,
                   keepalive=30, ssl=True,
                   ssl_params={"server_hostname": config.MQTT_HOST})
    c.set_last_will(T_STATUS, "offline", retain=True)
    c.set_callback(mqtt_cb)
    c.connect()
    c.publish(T_STATUS, "online", retain=True)
    c.subscribe(T_CMD)
    if config.SYS_ENABLE:
        c.subscribe(T_SYS)
    mqtt = c
    push_state()
    print("MQTT connected:", config.MQTT_HOST)


# ---- WiFi --------------------------------------------------
def wifi_connect():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if wlan.isconnected():
        return True
    for ssid, pw in config.WIFI_APS:
        print("WiFi: trying", ssid)
        wlan.connect(ssid, pw)
        for _ in range(40):
            if wlan.isconnected():
                print("WiFi:", wlan.ifconfig()[0])
                return True
            time.sleep_ms(200)
    print("WiFi: none — BLE only")
    return False


# ---- async loops -------------------------------------------
async def net_task():
    wifi_connect()
    while True:
        try:
            if mqtt is None:
                if network.WLAN(network.STA_IF).isconnected():
                    mqtt_connect()
                else:
                    wifi_connect()
            else:
                mqtt.check_msg()          # non-blocking poll
        except Exception as e:
            print("net err:", e)
            globals()["mqtt"] = None      # force reconnect
        await asyncio.sleep_ms(200)


async def main():
    print("================================")
    print(" NP ac - MicroPython gateway")
    print("  BLE:", config.BLE_NAME, "| IR GPIO:", config.IR_PIN)
    print("  cmd :", T_CMD)
    print("  sys :", T_SYS if config.SYS_ENABLE else "(disabled)")
    print("================================")

    tasks = [net_task()]
    if config.BLE_ENABLE:
        try:
            import ble_nus
            global ble_tx
            ble_tx = ble_nus.start(config.BLE_NAME, handle_command)
            print("BLE advertising as", config.BLE_NAME)
        except Exception as e:
            print("BLE disabled (err):", e)

    await asyncio.gather(*tasks)


try:
    asyncio.run(main())
finally:
    asyncio.new_event_loop()
