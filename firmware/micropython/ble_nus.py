# ============================================================
#  BLE Nordic-UART service — advertises "NP ac", handles the same
#  text commands as MQTT. Compatible with the existing web app.
# ============================================================
import bluetooth
import uasyncio as asyncio
import aioble

_UART = bluetooth.UUID("6E400001-B5A3-F393-E0A9-E50E24DCCA9E")
_RX   = bluetooth.UUID("6E400002-B5A3-F393-E0A9-E50E24DCCA9E")  # phone -> board
_TX   = bluetooth.UUID("6E400003-B5A3-F393-E0A9-E50E24DCCA9E")  # board -> phone


def start(name, on_cmd):
    """Register the service, start advertising, return a notify(str) fn."""
    svc = aioble.Service(_UART)
    rx = aioble.Characteristic(svc, _RX, write=True, capture=True)
    tx = aioble.Characteristic(svc, _TX, notify=True)
    aioble.register_services(svc)

    holder = {"conn": None, "buf": ""}

    def notify(s):
        conn = holder["conn"]
        if conn and conn.is_connected():
            for i in range(0, len(s), 20):          # 20-byte BLE chunks
                tx.notify(conn, s[i:i + 20])

    async def rx_task():
        while True:
            try:
                conn, data = await rx.written()
                holder["buf"] += data.decode()
                # the web app terminates every command with '\n'
                while "\n" in holder["buf"]:
                    line, _, holder["buf"] = holder["buf"].partition("\n")
                    on_cmd(line, "BLE")
                # guard against a stuck partial (no newline ever) growing forever
                if len(holder["buf"]) > 64:
                    holder["buf"] = ""
            except Exception as e:
                print("BLE rx err:", e)
                await asyncio.sleep_ms(200)

    async def adv_task():
        while True:
            try:
                conn = await aioble.advertise(250_000, name=name, services=[_UART])
                print("BLE connected:", conn.device)
                holder["conn"] = conn
                await conn.disconnected()
                print("BLE disconnected")
                holder["conn"] = None
            except Exception as e:
                print("BLE adv err:", e)
                await asyncio.sleep_ms(500)

    asyncio.create_task(rx_task())
    asyncio.create_task(adv_task())
    return notify
