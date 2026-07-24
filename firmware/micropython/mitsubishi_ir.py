# ============================================================
#  Mitsubishi Electric A/C  —  IR frame builder + transmitter
#  Ported from the IRremoteESP8266 IRMitsubishiAC (144-bit) protocol.
#
#  Bit layout (18-byte frame), verified against the library header:
#    Byte 0-4 : 0x23 0xCB 0x26 0x01 0x00   (fixed signature)
#    Byte 5   : bit5 = Power
#    Byte 6   : bits3-5 = Mode
#    Byte 7   : bits0-3 = Temp (deg-16), bit4 = HalfDegree
#    Byte 8   : bits4-7 = WideVane (horizontal, left as default)
#    Byte 9   : bits0-2 = Fan, bits3-5 = Vane, bit6 = VaneBit, bit7 = FanAuto
#    Byte 10-16: feature/timer defaults
#    Byte 17  : checksum = sum(byte 0..16) & 0xFF
#
#  Timing (us): header 3400/1750, bit mark 450, one 1300, zero 420,
#  gap 15500, carrier 38 kHz, LSB-first, frame sent twice.
# ============================================================
import time
from machine import Pin
from esp32 import RMT

# canonical -> Mitsubishi field values
_MODE = {"COOL": 0b011, "HEAT": 0b001, "DRY": 0b010, "AUTO": 0b100, "FAN": 0b111}
# fan: over-the-air field value (VERIFY on bench; SILENT/MAX may need a tweak)
_FAN  = {"AUTO": 0, "1": 1, "2": 2, "3": 3, "MAX": 4, "SILENT": 6}
_VANE = {"AUTO": 0, "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "SWING": 7}

# timing constants (microseconds)
HDR_MARK, HDR_SPACE = 3400, 1750
BIT_MARK = 450
ONE_SPACE, ZERO_SPACE = 1300, 420
GAP = 15500


def build_frame(power, temp, mode, fan, vane):
    b = bytearray([0x23, 0xCB, 0x26, 0x01, 0x00,
                   0x20, 0x08, 0x06, 0x30, 0x45, 0x67,
                   0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
    # Power (byte5 bit5)
    if power:
        b[5] |= 0x20
    else:
        b[5] &= ~0x20 & 0xFF
    # Mode (byte6 bits3-5)
    b[6] = (b[6] & ~0x38 & 0xFF) | ((_MODE.get(mode, 0b011) & 0x7) << 3)
    # Temp (byte7 bits0-3), clamp 16..31, no half-degree
    t = max(16, min(31, int(temp)))
    b[7] = (b[7] & ~0x0F & 0xFF) | ((t - 16) & 0x0F)
    # Fan / Vane (byte9)
    fan_v = _FAN.get(fan, 0)
    fanauto = 1 if fan == "AUTO" else 0
    vane_v = _VANE.get(vane, 0)
    b[9] = (fan_v & 0x7) | ((vane_v & 0x7) << 3) | (1 << 6) | (fanauto << 7)
    # Checksum (byte17)
    b[17] = sum(b[0:17]) & 0xFF
    return b


def _frame_to_pulses(frame):
    # alternating on/off durations, starting with the header mark (carrier ON)
    p = [HDR_MARK, HDR_SPACE]
    for byte in frame:
        for i in range(8):              # LSB first
            p.append(BIT_MARK)
            p.append(ONE_SPACE if (byte >> i) & 1 else ZERO_SPACE)
    p.append(BIT_MARK)                  # final mark
    return p


class MitsubishiIR:
    def __init__(self, pin):
        # clock_div=80 -> 1 us tick; 38 kHz carrier, 33% duty, active-high
        self.rmt = RMT(0, pin=Pin(pin), clock_div=80,
                       tx_carrier=(38000, 33, 1))
        self.last_frame = None

    def send_state(self, power, temp, mode, fan, vane):
        frame = build_frame(power, temp, mode, fan, vane)
        self.last_frame = frame
        pulses = _frame_to_pulses(frame)
        # the A/C wants the message twice
        for _ in range(2):
            self.rmt.write_pulses(pulses, 1)   # start level = 1 (carrier on)
            time.sleep_us(GAP)
        return frame

    def send_raw(self, pulses, start=1):
        """Fallback: replay a captured raw pulse list (guaranteed-correct path)."""
        self.rmt.write_pulses(pulses, start)
