# ============================================================
#  NP ac  —  configuration
#  Everything you might change lives here. Edit and re-upload
#  just this file (config.py) to reconfigure the device.
# ============================================================

# ---- IR ----------------------------------------------------
IR_PIN      = 2        # GPIO wired to the IR LED signal ("D0"). D0=GPIO2 on XIAO C3.

# ---- WiFi (tried in order) --------------------------------
WIFI_APS = [
    ("ghost",         "nowpurchase@123"),
    ("Me3tings4ever", "Me3tings4ever"),     # SSID == password (confirmed)
]

# ---- MQTT (HiveMQ Cloud Serverless, free) -----------------
MQTT_HOST   = "xxxxxxxx.s1.eu.hivemq.cloud"   # <-- your cluster URL
MQTT_PORT   = 8883                            # TLS
MQTT_USER   = "npac-device"                   # device credentials
MQTT_PASS   = "CHANGE_ME"
DEVICE_ID   = "npac1"                         # topic namespace

# ---- BLE ---------------------------------------------------
# BLE + WiFi + TLS together is heavy on the C3. If the board gets
# unstable / low on memory, set this False (WiFi/MQTT is the main path).
BLE_ENABLE  = True
BLE_NAME    = "NP ac"

# ---- Remote management ------------------------------------
# Enables the npac/<id>/sys topic for pushing code + reboot from afar.
# Powerful = keep this device's MQTT user private; give the web app a
# separate, restricted user that cannot publish to /sys.
SYS_ENABLE  = True
