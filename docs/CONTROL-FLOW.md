# How NP ac is controlled — MQTT flow & user control

## The big picture

```
   ┌── in the room ──────────────┐        ┌── anywhere on the internet ──┐
   │  Phone/PC (Chrome/Edge)     │        │  Any phone/PC, any browser   │
   │        │  BLE                │        │        │  HTTPS + wss        │
   │        ▼                     │        │        ▼                     │
   │   ESP32-C3  ◄────────────────┼────────┼──►  HiveMQ Cloud (broker)    │
   │   (D0 IR ─► Mitsubishi AC)   │  mqtts │        (free serverless)     │
   └──────────────────────────────┘  8883  └──────────────────────────────┘
```

- **In the room:** the web app talks straight to the ESP32 over **Bluetooth**. No
  internet needed. This is the original path, unchanged.
- **From anywhere:** the web app and the ESP32 both connect out to **HiveMQ Cloud**.
  They never connect to each other directly — the broker relays messages. Because
  both sides dial *out*, it works through any home router with no port-forwarding.

The web app auto-picks: **if Cloud is connected it uses Cloud; otherwise BLE.**

## What "HiveMQ controls it" actually means

HiveMQ is just a **message relay (broker)**. It doesn't know anything about ACs.
Control happens by publishing tiny text messages to **topics** (like channels):

| Topic | Direction | Example payload |
|---|---|---|
| `npac/npac1/cmd`    | app → AC | `on`, `off`, `temp:24`, `cool`, `f3`, `vane:swing` |
| `npac/npac1/state`  | AC → app | `{"power":true,"temp":24,"mode":"COOL","fan":"AUTO","vane":"AUTO"}` |
| `npac/npac1/status` | AC → app | `online` / `offline` |

Flow of a single button press (e.g. user taps **Cool**):
1. Web app publishes `cool` to `npac/npac1/cmd`.
2. HiveMQ delivers it to the ESP32 (which subscribed to that topic).
3. ESP32 fires the Mitsubishi IR code out of pin D0 → the AC changes.
4. ESP32 publishes the new `{...state...}` to `npac/npac1/state` (retained).
5. HiveMQ delivers it to **every** connected web app → all screens update together.

Because `state` is **retained**, a user who opens the app later instantly sees the
current AC state without pressing anything.

## How the users control it (step by step)

1. Open the web app URL (your GitHub Pages link) in any browser.
2. Tap **Cloud** (first time: right-click / long-press to enter the broker host +
   the `npac-web` username/password + device id — saved on their device).
3. Once it says **Cloud ✓**, every control works from anywhere:
   - Power ring, temperature slider/buttons, Mode, Fan, Vane
   - Voice commands ("turn on", "set temperature to 22")
   - Smart presets (Sleep / Turbo / Eco / …)
4. Multiple users can be connected at once — they all see the same live state.
5. In the same room, they can instead tap **BLE** for an instant, offline connection.

## Who can do what (security)

- Normal users get the **`npac-web`** login → can send commands + read state, nothing
  else. (Its password lives in public web-app code, which is fine — worst case is
  someone changes your AC temperature.)
- **Remote code updates** go through a separate `npac/npac1/sys` topic, reachable only
  by the private **`npac-admin`** login. Regular users can't touch it.
- See `HIVEMQ-SETUP.md` for the exact per-user topic permissions.

## Adding more ACs later

Give each unit its own `DEVICE_ID` (`npac2`, `npac3`, …). Topics become
`npac/npac2/cmd`, etc. One `npac-web` user with `npac/+/cmd` + `npac/+/state`
permissions controls them all; the app's device-id field selects which one.
