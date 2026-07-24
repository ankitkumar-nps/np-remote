# ============================================================
#  NP ac  —  configuration TEMPLATE
#  Copy this file to  config.py  and fill in your values.
#    cp config.example.py config.py      (Windows: copy config.example.py config.py)
#  config.py is gitignored so your credentials never get pushed.
# ============================================================

# ---- IR ----------------------------------------------------
IR_PIN      = 2        # GPIO wired to the IR LED signal ("D0" = GPIO2 on XIAO C3)

# ---- WiFi (tried in order) --------------------------------
WIFI_APS = [
    ("YOUR_WIFI_SSID", "YOUR_WIFI_PASSWORD"),
    # ("second-network", "its-password"),
]

# ---- MQTT (HiveMQ Cloud Serverless, free) -----------------
MQTT_HOST   = "xxxxxxxx.s1.eu.hivemq.cloud"   # your cluster URL
MQTT_PORT   = 8883                            # TLS
MQTT_USER   = "npac-device"                   # Access-Management username
MQTT_PASS   = "CHANGE_ME"                     # Access-Management password
DEVICE_ID   = "npac1"                         # topic namespace

# ---- BLE ---------------------------------------------------
BLE_ENABLE  = False        # WiFi-only recommended: BLE + WiFi share one radio on the C3
                           # and conflict. Keep False so WiFi/cloud is reliable.
BLE_NAME    = "NP ac"

# ---- Remote management ------------------------------------
SYS_ENABLE  = False        # OFF by default (safe for a public shareable link).
                           # Flip True only during a maintenance window for OTA code push.

# ---- Home Assistant ---------------------------------------
HA_DISCOVERY = True        # auto-register as an HA climate entity (-> Google/Apple Home)
