from asterix_decoder.data_items.length_type import LengthType, extract_octets
from asterix_decoder.data_items.data_item import DataItem


class Item250(DataItem):

    @staticmethod
    def get_item_id() -> str:
        return "I048/250"

    '''
        Name:       Mode S MB Data
        Definition: Repetitive Mode S Comm-B payloads.
        Format:     REP + N blocks of 8 octets.

        Decoded registers (per the Mode S DAPs Implementation & Operations Guidance):
          · BDS 4.0 – Selected Vertical Intention
          · BDS 5.0 – Track and Turn Report
          · BDS 6.0 – Heading and Speed Report

        Bit helpers use 1-based indexing with MSB = bit 1.
    '''

    SUPPORTED_BDS = {"4.0", "5.0", "6.0"}

    def __init__(self, item_name: str, length_type):
        super().__init__(item_name, length_type)
        self.data = {
            "MCP_ALT":                    None, #
            "FMS_ALT":                    None, # 
            "BP":                         None, # Baro Pressure
            "VNAV":                       None, # 
            "ALT_HOLD":                   None, #
            "APP":                        None, # Aproach mode
            "RA":                         None, # Roll Angle
            "TTA":                        None, # True Track Angle degree
            "GS":                         None, # Ground Speed kt
            "TAR":                        None, # Track Angle Rate degree/s
            "TAS":                         None, # True Airspeed kt
            "HDG":                          None, # Magnetic Heading degree [-180 - 180]
            "IAS":                          None, # Indicated Airspeed kt
            "MACH":                         None, #
            "BAR":                          None, # Barometric Altitude Rate ft/min
            "IVV":                          None, # Inertial Vertical Velocity ft/min
            
        }

    @extract_octets
    def decode(self, octets: bytes) -> dict[str, any]:
        REP = octets[0]
        BLOCKS = []

        pos = 1
        for _ in range(REP):
            BLOCK = octets[pos:pos + self.repetitive_block_size]
            BLOCKS.append(BLOCK)
            pos += self.repetitive_block_size

        return self._bits_to_data(self.data.copy(), BLOCKS)

    # ------------------------------------------------------------------
    # Top-level dispatch
    # ------------------------------------------------------------------

    def _bits_to_data(self, data, BLOCKS) -> dict[str, any]:
        for BLOCK in BLOCKS:
            MB_DATA = BLOCK[:7]          # 56 bits of payload
            BDS_SELECTOR = BLOCK[7]
            BDS1 = (BDS_SELECTOR >> 4) & 0x0F
            BDS2 = BDS_SELECTOR & 0x0F
            BDS_CODE = f"{BDS1}.{BDS2}"

            if BDS_CODE not in self.SUPPORTED_BDS:
                continue

            if BDS_CODE == "4.0":
                block_info = self._decode_bds40(MB_DATA)
            elif BDS_CODE == "5.0":
                block_info = self._decode_bds50(MB_DATA)
            elif BDS_CODE == "6.0":
                block_info = self._decode_bds60(MB_DATA)

            data.update(block_info)

        return data

    # ------------------------------------------------------------------
    # Bit utilities  (1-based, MSB = bit 1, field width = 56 bits)
    # ------------------------------------------------------------------

    @staticmethod
    def _bit(value: int, n: int) -> int:
        """Return the value of bit n (1-based, MSB = bit 1) in a 56-bit integer."""
        return (value >> (56 - n)) & 1

    @staticmethod
    def _bits_range(value: int, start: int, end: int) -> int:
        """Return the unsigned integer formed by bits start..end (inclusive, 1-based)."""
        width = end - start + 1
        return (value >> (56 - end)) & ((1 << width) - 1)

    # ------------------------------------------------------------------
    # BDS 4.0 – Selected Vertical Intention
    #
    # Bit layout (56 bits):
    #   1        : MCP/FCU altitude status
    #   2 – 13   : MCP/FCU selected altitude   (×16 ft,      range 0–65 520 ft)
    #   14       : FMS altitude status
    #   15 – 26  : FMS selected altitude        (×16 ft,      range 0–65 520 ft)
    #   27       : Barometric pressure status
    #   28 – 39  : Barometric pressure setting  (×0.1 + 800 mb, range 0–410 mb)
    #   40       : Reserved
    #   41       : VNAV mode flag
    #   42       : Alt-Hold mode flag
    #   43       : Approach mode flag
    #   44 – 47  : Reserved
    #   48       : Target altitude source status
    #   49 – 51  : Target altitude source value (3 bits)
    #   52 – 56  : Reserved
    # ------------------------------------------------------------------

    def _decode_bds40(self, mb_data: bytes) -> dict:
        BITS = int.from_bytes(mb_data, 'big')

        # ── MCP/FCU Selected Altitude ──────────────────────────────────
        MCP_STATUS   = self._bit(BITS, 1)
        MCP_RAW      = self._bits_range(BITS, 2, 13)
        MCP_ALTITUDE_FT = MCP_RAW * 16 if MCP_STATUS else None

        # ── FMS Selected Altitude ──────────────────────────────────────
        FMS_STATUS   = self._bit(BITS, 14)
        FMS_RAW      = self._bits_range(BITS, 15, 26)
        FMS_ALTITUDE_FT = FMS_RAW * 16 if FMS_STATUS else None

        # ── Barometric Pressure Setting ────────────────────────────────
        BARO_STATUS  = self._bit(BITS, 27)
        BARO_RAW     = self._bits_range(BITS, 28, 39)
        BARO_SETTING_MB = round(BARO_RAW * 0.1 + 800, 1) if BARO_STATUS else None

        # ── Autopilot Mode Flags ───────────────────────────────────────
        VNAV_MODE     = int(self._bit(BITS, 41))
        ALT_HOLD_MODE = int(self._bit(BITS, 42))
        APPROACH_MODE = int(self._bit(BITS, 43))

        # ── Target Altitude Source ─────────────────────────────────────
        TARGET_ALT_SOURCE_STATUS = int(self._bit(BITS, 54))

        return {
            "MCP_ALT":                        MCP_ALTITUDE_FT,
            "FMS_ALT":                    FMS_ALTITUDE_FT,
            "BP":                         BARO_SETTING_MB,
            "VNAV":                       VNAV_MODE,
            "ALT_HOLD":                   ALT_HOLD_MODE,
            "APP":                        APPROACH_MODE,
            "TARGET_ALT_SOURCE":          TARGET_ALT_SOURCE_STATUS,
        }

    # ------------------------------------------------------------------
    # BDS 5.0 – Track and Turn Report
    #
    # Bit layout (56 bits):
    #   1        : Roll angle status
    #   2        : Roll angle sign      (0 = right/positive, 1 = left/negative)
    #   3 – 11   : Roll angle value     (×45/256 °,  range ±90°)
    #   12       : True track angle status
    #   13       : TTA sign             (0 = 0–180°,  1 = 180–360°)
    #   14 – 23  : TTA value            (×90/512 °)
    #   24       : Ground speed status
    #   25 – 34  : Ground speed value   (×2 kt,       range 0–2046 kt)
    #   35       : Track angle rate status
    #   36       : TAR sign             (0 = right/positive, 1 = left/negative)
    #   37 – 45  : TAR value            (×8/256 °/s,  range ±16 °/s)
    #   46       : True airspeed status
    #   47 – 56  : TAS value            (×2 kt,       range 0–2046 kt)
    # ------------------------------------------------------------------

    def _decode_bds50(self, mb_data: bytes) -> dict:
        BITS = int.from_bytes(mb_data, 'big')

        # ── Roll Angle ─────────────────────────────────────────────────
        ROLL_STATUS   = self._bit(BITS, 1)
        ROLL_RAW      = self._twos_complement(self._bits_range(BITS, 2, 11), 10)
        ROLL_ANGLE_DEG = round(ROLL_RAW * (45 / 256), 3)
        ROLL_ANGLE_DEG = ROLL_ANGLE_DEG if ROLL_STATUS else "NV"
        
        # ── True Track Angle ───────────────────────────────────────────
        TTA_STATUS = self._bit(BITS, 12)
        TTA_RAW    = self._twos_complement(self._bits_range(BITS, 13, 23), 11)
        TRUE_TRACK_ANGLE_DEG = round(TTA_RAW * (90 / 512), 3)
        TRUE_TRACK_ANGLE_DEG = TRUE_TRACK_ANGLE_DEG if TTA_STATUS else "NV"

        # ── Ground Speed ───────────────────────────────────────────────
        GS_STATUS     = self._bit(BITS, 24)
        GS_RAW        = self._bits_range(BITS, 25, 34)
        GROUND_SPEED_KT = GS_RAW * 2 if GS_STATUS else "NV"

        # ── Track Angle Rate ───────────────────────────────────────────
        TAR_STATUS = self._bit(BITS, 35)
        TAR_RAW    = self._twos_complement(self._bits_range(BITS, 36, 45), 10)
        TRACK_ANGLE_RATE_DEG_S = round(TAR_RAW * (8 / 256), 3)
        TRACK_ANGLE_RATE_DEG_S = TRACK_ANGLE_RATE_DEG_S if TAR_STATUS else "NV"

        # ── True Airspeed ──────────────────────────────────────────────
        TAS_STATUS    = self._bit(BITS, 46)
        TAS_RAW       = self._bits_range(BITS, 47, 56)
        TRUE_AIRSPEED_KT = TAS_RAW * 2 if TAS_STATUS else "NV"

        return {
            "RA":                         ROLL_ANGLE_DEG,
            "TTA":                        TRUE_TRACK_ANGLE_DEG,
            "GS":                         GROUND_SPEED_KT,
            "TAR":                        TRACK_ANGLE_RATE_DEG_S,
            "TAS":                        TRUE_AIRSPEED_KT,
        }

    # ------------------------------------------------------------------
    # BDS 6.0 – Heading and Speed Report
    #
    # Bit layout (56 bits):
    #   1        : Magnetic heading status
    #   2        : MH sign              (0 = 0–180°,   1 → 360 − value)
    #   3 – 12   : MH value             (×90/512 °)
    #   13       : IAS status
    #   14 – 23  : IAS value            (×1 kt,        range 0–1023 kt)
    #   24       : Mach status
    #   25 – 34  : Mach value           (×0.004,       range 0–4.092)
    #   35       : Barometric alt rate status
    #   36       : Baro alt rate sign   (0 = climb/positive, 1 = descend/negative)
    #   37 – 45  : Baro alt rate value  (×32 ft/min,   range ±16 352 ft/min)
    #   46       : Inertial vert velocity status
    #   47       : IVV sign             (0 = climb/positive, 1 = descend/negative)
    #   48 – 56  : IVV value            (×32 ft/min,   range ±16 352 ft/min)
    # ------------------------------------------------------------------

    def _decode_bds60(self, mb_data: bytes) -> dict:
        BITS = int.from_bytes(mb_data, 'big')

        # ── Magnetic Heading ───────────────────────────────────────────
        MH_STATUS = self._bit(BITS, 1)
        MH_RAW    = self._twos_complement(self._bits_range(BITS, 2, 12), 11)

        MAGNETIC_HEADING_DEG = round((MH_RAW * (90 / 512)), 6)
        MAGNETIC_HEADING_DEG = MAGNETIC_HEADING_DEG if MH_STATUS else "NV"

        # ── Indicated Airspeed ─────────────────────────────────────────
        IAS_STATUS  = self._bit(BITS, 13)
        IAS_RAW     = self._bits_range(BITS, 14, 23)
        INDICATED_AIRSPEED_KT = IAS_RAW if IAS_STATUS else "NV"

        # ── Mach Number ────────────────────────────────────────────────
        MACH_STATUS = self._bit(BITS, 24)
        MACH_RAW    = self._bits_range(BITS, 25, 34)
        MACH_NUMBER = round(MACH_RAW * 0.004, 3) if MACH_STATUS else "NV"

        # ── Barometric Altitude Rate ───────────────────────────────────
        BAR_STATUS = self._bit(BITS, 35)
        BAR_RAW    = self._twos_complement(self._bits_range(BITS, 37, 45), 9)
        BARO_ALT_RATE_FPM = BAR_RAW * 32
        BARO_ALT_RATE_FPM = BARO_ALT_RATE_FPM if BAR_STATUS else "NV"
        

        # ── Inertial Vertical Velocity ─────────────────────────────────
        IVV_STATUS = self._bit(BITS, 46)
        IVV_RAW    = self._twos_complement(self._bits_range(BITS, 47, 56), 10)
        INERTIAL_VERT_VELOCITY_FPM = IVV_RAW * 32
        INERTIAL_VERT_VELOCITY_FPM = INERTIAL_VERT_VELOCITY_FPM if IVV_STATUS else "NV"

        return {
            "HDG":                          MAGNETIC_HEADING_DEG,
            "IAS":                          INDICATED_AIRSPEED_KT,
            "MACH":                         MACH_NUMBER,
            "BAR":                          BARO_ALT_RATE_FPM,
            "IVV":                          INERTIAL_VERT_VELOCITY_FPM,
        }
    


    def _twos_complement(self, value: int, bits: int) -> int:
        if value & (1 << (bits - 1)):
            value -= 1 << bits
        return value