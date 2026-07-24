# boot.py — runs before main.py. Kept minimal on purpose.
import gc
gc.collect()
# WiFi is brought up inside main.py so we can also fall back to BLE-only.
