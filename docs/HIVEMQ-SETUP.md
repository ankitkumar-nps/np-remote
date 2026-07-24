# HiveMQ Cloud — cluster + topic-permission setup for NP ac

Goal: three separate MQTT users, each allowed to touch **only** the topics it needs.
The public web app must be able to control the AC but **must not** reach the
remote-management (`/sys`) channel that can run code.

## Topic map (device `npac1`)

| Topic | Who publishes | Who subscribes |
|---|---|---|
| `npac/npac1/cmd`      | web, admin | **device** |
| `npac/npac1/state`    | **device** | web, admin |
| `npac/npac1/status`   | **device** (LWT) | web, admin |
| `npac/npac1/sys`      | **admin only** | **device** |
| `npac/npac1/sys/resp` | **device** | **admin only** |

## The three users

| User | Used by | Keep secret? |
|---|---|---|
| `npac-device` | the ESP32 (`config.py`) | yes |
| `npac-web`    | the public GitHub-Pages dashboard | no (it's in public JS) |
| `npac-admin`  | you / me, for remote code push | **yes — most sensitive** |

---

## 1. Create the cluster
1. hivemq.com → **Start Free → Serverless** → sign in → **Create Cluster**.
2. Copy the **Cluster URL** (e.g. `abc123.s1.eu.hivemq.cloud`).
3. Ports: **8883** = MQTT/TLS (ESP32), **8884** = MQTT over WSS (browser).

## 2. Add credentials with permissions
Open the cluster → **Access Management → Credentials**. For each user, add the
credential, then add **Permissions** (topic filter + Publish/Subscribe). HiveMQ
treats listed permissions as an allow-list — anything not listed is denied.

> Note: on the **free Serverless** tier the UI may only let you create credentials
> without fine-grained per-topic rules (per-topic ACLs are a Starter/Dedicated
> feature). If so, see **"Free-tier fallback"** below — you still get the key
> protection by keeping the `sys` topic name secret + `SYS_ENABLE` control.

### `npac-device`  (the ESP32)
| Topic filter | Permission |
|---|---|
| `npac/npac1/state`    | Publish |
| `npac/npac1/status`   | Publish |
| `npac/npac1/sys/resp` | Publish |
| `npac/npac1/cmd`      | Subscribe |
| `npac/npac1/sys`      | Subscribe |

(Or simply allow `npac/npac1/#` Publish+Subscribe — the device is trusted.)

### `npac-web`  (the public dashboard) — NO `/sys`
| Topic filter | Permission |
|---|---|
| `npac/npac1/cmd`    | Publish |
| `npac/npac1/state`  | Subscribe |
| `npac/npac1/status` | Subscribe |

That's it — it can send commands and read state, but **cannot publish or
subscribe to `npac/npac1/sys`**. Even though its password ships in public JS, the
worst anyone can do is control the AC, not run code.

### `npac-admin`  (remote management — keep private)
| Topic filter | Permission |
|---|---|
| `npac/npac1/sys`      | Publish |
| `npac/npac1/sys/resp` | Subscribe |
| `npac/npac1/state`    | Subscribe |
| `npac/npac1/status`   | Subscribe |

Use these creds only from a trusted machine (your PC / this Claude session) to push
code updates. Never put them in the web app.

## 3. Wire the users up
- **`config.py`** on the ESP32 → `MQTT_USER="npac-device"`, its password.
- **Dashboard** → right-click the **Cloud** button → enter host, `npac-web`, its
  password, device id `npac1`.
- **Admin** (`npac-admin`) → only in your local push script / given to me when needed.

## 4. Extra hardening (optional but recommended)
- Set **`SYS_ENABLE = False`** in `config.py` when you're not actively doing a
  remote update — flip it on only during a maintenance window. Even a leaked
  admin password can't run code while it's off.
- Use a **long random** password for `npac-device` and `npac-admin`.
- Multiple ACs later: keep the same pattern per device id
  (`npac/<id>/…`) and give `npac-web` `npac/+/cmd` (Publish) +
  `npac/+/state` (Subscribe) so one web user works for all, still no `/sys`.

## Free-tier fallback (if per-topic ACLs aren't available)
If the Serverless plan only allows a single all-topics credential:
1. Still make **two** users if the UI allows it (device + web); if not, use one.
2. **Rename the management topic to something unguessable**, e.g.
   `npac/npac1/sys-4f9c2a`, and set it in `main.py` (`T_SYS`). Obscurity is not
   real security, but combined with the next point it's adequate for a hobby setup.
3. Keep **`SYS_ENABLE = False`** except during updates. This is the real safeguard:
   with it off, the code-exec path simply doesn't exist at runtime.
4. When you outgrow the free tier, HiveMQ Starter adds proper per-topic ACLs — then
   apply the three-user table above.
