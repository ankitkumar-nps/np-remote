/* ============================================================================
   NP ac  —  Mitsubishi MSY-GN22VF Remote Gateway   (ESP32-C3)
   Reconstructed from the original board's flash dump, + WiFi/MQTT added.

   WHAT IT DOES
     • Emulates the IR remote for the Mitsubishi split AC  (IR LED on pin D0)
     • BLE  : advertises as "NP ac" (Nordic UART Service) — in-room control,
              100% compatible with the existing GitHub web app.
     • WiFi : connects to your network(s)
     • MQTT : connects to HiveMQ Cloud (TLS) so the web app can control it
              from ANYWHERE and any number of users.

   Both transports (BLE + MQTT) accept the SAME text commands and both receive
   the SAME JSON state, so the UI never has to care which path it used.

   BOARD  : ESP32-C3, 4MB flash, native USB. (Arduino-ESP32 core 3.x)
   LIBRARIES to install in Arduino IDE / arduino-cli:
     • "IRremoteESP8266"  by David Conran (crankyoldgit)
     • "PubSubClient"     by Nick O'Leary
     (WiFi, WiFiClientSecure, BLE come with the ESP32 core.)
   ============================================================================ */

#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <IRremoteESP8266.h>
#include <IRsend.h>
#include <ir_Mitsubishi.h>

#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>

/* ===========================================================================
   ====== USER CONFIG — EDIT THIS BLOCK ======================================
   =========================================================================== */

// ---- IR output pin -------------------------------------------------------
// Original firmware printed "IR TX on D0". Set this to the GPIO your IR LED
// driver is wired to. On a Seeed XIAO ESP32-C3, silk "D0" = GPIO2.
// If your AC doesn't respond, this pin is the first thing to check.
#define IR_PIN            2        // GPIO number of the IR LED

// ---- WiFi (tries each in order; recovered from your board's NVS) ----------
struct WifiAp { const char* ssid; const char* pass; };
WifiAp WIFI_APS[] = {
  { "ghost",          "nowpurchase@123" },   // found stored on your chip
  { "Me3tings4ever",  "PUT_PASSWORD_HERE" }, // 2nd stored SSID — fill password
};

// ---- MQTT (HiveMQ Cloud Serverless — free tier) --------------------------
// Create a free cluster at hivemq.com -> Serverless, then paste values here.
#define MQTT_HOST         "xxxxxxxx.s1.eu.hivemq.cloud"  // your cluster URL
#define MQTT_PORT         8883                            // TLS
#define MQTT_USER         "npac-device"                   // an Access-Mgmt user
#define MQTT_PASS         "CHANGE_ME"
#define DEVICE_ID         "npac1"     // topic namespace / lets you run several

// ---- Bluetooth name (keep as-is for web-app compatibility) ---------------
#define BLE_NAME          "NP ac"

/* =========================================================================== */

// Nordic UART Service UUIDs (unchanged from original firmware)
#define NUS_SERVICE   "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
#define NUS_RX        "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"  // phone -> board (write)
#define NUS_TX        "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"  // board -> phone (notify)

// MQTT topics
String T_BASE   = String("npac/") + DEVICE_ID;
String T_CMD    = T_BASE + "/cmd";     // app -> board
String T_STATE  = T_BASE + "/state";   // board -> app (retained)
String T_STATUS = T_BASE + "/status";  // LWT online/offline (retained)

// ---- AC + radios ---------------------------------------------------------
IRMitsubishiAC ac(IR_PIN);
WiFiClientSecure netClient;
PubSubClient     mqtt(netClient);

BLECharacteristic* txChar = nullptr;
bool bleConnected = false;

// ---- Canonical AC state (values match what the web app expects) ----------
struct AcState {
  bool   power = false;
  int    temp  = 24;
  String mode  = "COOL";    // COOL HEAT DRY AUTO FAN
  String fan   = "AUTO";    // AUTO 1 2 3 MAX SILENT
  String vane  = "AUTO";    // AUTO SWING 1 2 3 4 5
  String last  = "None";
} st;

String bleRxBuf;
unsigned long lastMqttTry = 0;

// ===========================================================================
//  IR — translate canonical state into a Mitsubishi frame and transmit
// ===========================================================================
void configureAcFromState() {
  ac.setPower(st.power);
  ac.setTemp((float)st.temp);

  if      (st.mode == "COOL") ac.setMode(kMitsubishiAcCool);
  else if (st.mode == "HEAT") ac.setMode(kMitsubishiAcHeat);
  else if (st.mode == "DRY")  ac.setMode(kMitsubishiAcDry);
  else if (st.mode == "AUTO") ac.setMode(kMitsubishiAcAuto);
  else if (st.mode == "FAN")  ac.setMode(kMitsubishiAcFan);

  if      (st.fan == "AUTO")   ac.setFan(kMitsubishiAcFanAuto);
  else if (st.fan == "1")      ac.setFan(1);
  else if (st.fan == "2")      ac.setFan(2);
  else if (st.fan == "3")      ac.setFan(3);   // RealMax is 4
  else if (st.fan == "MAX")    ac.setFan(kMitsubishiAcFanMax);
  else if (st.fan == "SILENT") ac.setFan(kMitsubishiAcFanSilent);

  if      (st.vane == "AUTO")  ac.setVane(kMitsubishiAcVaneAuto);
  else if (st.vane == "SWING") ac.setVane(kMitsubishiAcVaneSwing);
  else if (st.vane == "1")     ac.setVane(kMitsubishiAcVaneHighest);
  else if (st.vane == "2")     ac.setVane(kMitsubishiAcVaneHigh);
  else if (st.vane == "3")     ac.setVane(kMitsubishiAcVaneMiddle);
  else if (st.vane == "4")     ac.setVane(kMitsubishiAcVaneLow);
  else if (st.vane == "5")     ac.setVane(kMitsubishiAcVaneLowest);
}

void sendIR() {
  configureAcFromState();
  ac.send();
  Serial.printf("IR>> %s | Pwr:%s Temp:%dC Mode:%s Fan:%s Vane:%s\n",
                st.last.c_str(), st.power ? "ON" : "OFF",
                st.temp, st.mode.c_str(), st.fan.c_str(), st.vane.c_str());
}

// ===========================================================================
//  State publishing — send JSON to whichever transports are connected
// ===========================================================================
String stateJson() {
  String j = "{";
  j += "\"power\":"; j += st.power ? "true" : "false";
  j += ",\"temp\":"; j += st.temp;
  j += ",\"mode\":\"" + st.mode + "\"";
  j += ",\"fan\":\""  + st.fan  + "\"";
  j += ",\"vane\":\"" + st.vane + "\"";
  j += ",\"last\":\"" + st.last + "\"}";
  return j;
}

void bleNotify(const String& s) {
  if (!bleConnected || !txChar) return;
  // write in <=20-byte chunks (classic BLE MTU), same as the web app expects
  for (size_t i = 0; i < s.length(); i += 20) {
    txChar->setValue((uint8_t*)s.c_str() + i, min((size_t)20, s.length() - i));
    txChar->notify();
    delay(6);
  }
}

void publishState() {
  String j = stateJson();
  bleNotify(j);
  if (mqtt.connected()) mqtt.publish(T_STATE.c_str(), j.c_str(), true); // retained
}

// ===========================================================================
//  Command parser — shared by BLE and MQTT
//  Accepts the exact tokens the original firmware & web app use.
// ===========================================================================
void handleCommand(String cmd, const char* src) {
  cmd.trim();
  if (!cmd.length()) return;
  cmd.toLowerCase();
  Serial.printf("[%s] cmd: %s\n", src, cmd.c_str());

  bool changed = true;   // does this command require an IR shot?

  if      (cmd == "on")       { st.power = true;  st.last = "Power ON"; }
  else if (cmd == "off")      { st.power = false; st.last = "Power OFF"; }
  else if (cmd == "t+")       { st.temp = min(31, st.temp + 1); st.last = "Temp " + String(st.temp); }
  else if (cmd == "t-")       { st.temp = max(16, st.temp - 1); st.last = "Temp " + String(st.temp); }
  else if (cmd.startsWith("temp:")) {
    int t = cmd.substring(5).toInt();
    if (t >= 16 && t <= 31) { st.temp = t; st.last = "Temp " + String(t); }
    else changed = false;
  }
  // modes
  else if (cmd == "cool")     { st.mode = "COOL"; st.last = "Cool";     }
  else if (cmd == "heat")     { st.mode = "HEAT"; st.last = "Heat";     }
  else if (cmd == "dry")      { st.mode = "DRY";  st.last = "Dry";      }
  else if (cmd == "auto")     { st.mode = "AUTO"; st.last = "Auto";     }
  else if (cmd == "fanonly")  { st.mode = "FAN";  st.last = "Fan only"; }
  // fan (short forms from web app + long forms from original fw)
  else if (cmd == "fa"  || cmd == "fan:auto")   { st.fan = "AUTO";   st.last = "Fan Auto";   }
  else if (cmd == "f1"  || cmd == "fan:1")      { st.fan = "1";      st.last = "Fan Low";    }
  else if (cmd == "f2"  || cmd == "fan:2")      { st.fan = "2";      st.last = "Fan Med";    }
  else if (cmd == "f3"  || cmd == "fan:3")      { st.fan = "3";      st.last = "Fan High";   }
  else if (cmd == "fmax"|| cmd == "fan:max")    { st.fan = "MAX";    st.last = "Fan Max";    }
  else if (cmd == "fs"  || cmd == "fan:silent") { st.fan = "SILENT"; st.last = "Fan Silent"; }
  // vane
  else if (cmd == "vane:auto")  { st.vane = "AUTO";  st.last = "Vane Auto";  }
  else if (cmd == "vane:swing") { st.vane = "SWING"; st.last = "Vane Swing"; }
  else if (cmd == "vane:1")     { st.vane = "1";     st.last = "Vane 1"; }
  else if (cmd == "vane:2")     { st.vane = "2";     st.last = "Vane 2"; }
  else if (cmd == "vane:3")     { st.vane = "3";     st.last = "Vane 3"; }
  else if (cmd == "vane:4")     { st.vane = "4";     st.last = "Vane 4"; }
  else if (cmd == "vane:5")     { st.vane = "5";     st.last = "Vane 5"; }
  // no-IR commands
  else if (cmd == "s" || cmd == "status") { changed = false; }        // report only
  else if (cmd == "resend")               { /* re-send current state */ }
  else {
    Serial.printf("Unknown cmd: %s\n", cmd.c_str());
    return;
  }

  if (changed || cmd == "resend") sendIR();
  publishState();
}

// ===========================================================================
//  BLE
// ===========================================================================
class ServerCB : public BLEServerCallbacks {
  void onConnect(BLEServer*) override { bleConnected = true;  Serial.println("BLE connected");    }
  void onDisconnect(BLEServer* s) override {
    bleConnected = false; Serial.println("BLE disconnected");
    s->getAdvertising()->start();   // keep advertising for the next phone
  }
};

class RxCB : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic* c) override {
    bleRxBuf += c->getValue();               // may arrive in chunks
    int nl;
    while ((nl = bleRxBuf.indexOf('\n')) >= 0) {
      String line = bleRxBuf.substring(0, nl);
      bleRxBuf = bleRxBuf.substring(nl + 1);
      handleCommand(line, "BLE");
    }
    // also handle a chunk with no newline that already IS a full command
    if (bleRxBuf.length() && bleRxBuf.length() < 24 && bleRxBuf.indexOf(' ') < 0) {
      // heuristic flush handled on next newline; leave buffered otherwise
    }
  }
};

void setupBLE() {
  BLEDevice::init(BLE_NAME);
  BLEServer* server = BLEDevice::createServer();
  server->setCallbacks(new ServerCB());

  BLEService* svc = server->createService(NUS_SERVICE);

  BLECharacteristic* rx = svc->createCharacteristic(
      NUS_RX, BLECharacteristic::PROPERTY_WRITE | BLECharacteristic::PROPERTY_WRITE_NR);
  rx->setCallbacks(new RxCB());

  txChar = svc->createCharacteristic(
      NUS_TX, BLECharacteristic::PROPERTY_NOTIFY);

  svc->start();

  BLEAdvertising* adv = BLEDevice::getAdvertising();
  adv->addServiceUUID(NUS_SERVICE);
  adv->setScanResponse(true);
  BLEDevice::startAdvertising();
}

// ===========================================================================
//  WiFi + MQTT
// ===========================================================================
void connectWiFi() {
  for (auto& ap : WIFI_APS) {
    Serial.printf("WiFi: trying \"%s\" ...\n", ap.ssid);
    WiFi.mode(WIFI_STA);
    WiFi.begin(ap.ssid, ap.pass);
    unsigned long t0 = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - t0 < 8000) delay(200);
    if (WiFi.status() == WL_CONNECTED) {
      Serial.printf("WiFi: connected to %s, IP %s\n", ap.ssid, WiFi.localIP().toString().c_str());
      return;
    }
  }
  Serial.println("WiFi: no network — running BLE-only for now");
}

void mqttCallback(char* topic, byte* payload, unsigned int len) {
  String msg;
  for (unsigned int i = 0; i < len; i++) msg += (char)payload[i];
  handleCommand(msg, "MQTT");
}

void mqttReconnect() {
  if (WiFi.status() != WL_CONNECTED) return;
  if (millis() - lastMqttTry < 5000) return;    // throttle
  lastMqttTry = millis();

  Serial.print("MQTT: connecting...");
  String cid = String("npac-") + DEVICE_ID + "-" + String((uint32_t)ESP.getEfuseMac(), HEX);
  // connect with Last-Will = "offline" (retained) on the status topic
  if (mqtt.connect(cid.c_str(), MQTT_USER, MQTT_PASS,
                   T_STATUS.c_str(), 0, true, "offline")) {
    Serial.println(" connected");
    mqtt.publish(T_STATUS.c_str(), "online", true);
    mqtt.subscribe(T_CMD.c_str());
    publishState();                              // push current state on connect
  } else {
    Serial.printf(" failed rc=%d\n", mqtt.state());
  }
}

// ===========================================================================
//  Setup / loop
// ===========================================================================
void setup() {
  Serial.begin(115200);
  delay(300);

  ac.begin();
  configureAcFromState();

  connectWiFi();

  netClient.setInsecure();   // HiveMQ uses a public CA; skip cert pinning (hobby)
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setBufferSize(512);
  mqtt.setCallback(mqttCallback);

  setupBLE();

  Serial.println("================================");
  Serial.println(" NP ac - BLE + WiFi/MQTT Remote");
  Serial.printf ("  Bluetooth name : %s\n", BLE_NAME);
  Serial.printf ("  IR TX on GPIO  : %d\n", IR_PIN);
  Serial.printf ("  MQTT cmd topic : %s\n", T_CMD.c_str());
  Serial.printf ("  MQTT state     : %s\n", T_STATE.c_str());
  Serial.println("  Waiting for phone / cloud...");
  Serial.println("================================");
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    static unsigned long lastWifiTry = 0;
    if (millis() - lastWifiTry > 20000) { lastWifiTry = millis(); connectWiFi(); }
  }
  if (!mqtt.connected()) mqttReconnect();
  else                   mqtt.loop();
}
