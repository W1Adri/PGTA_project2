from asterix_decoder.data_items.length_type import LengthType, extract_octets
from asterix_decoder.data_items.data_item import DataItem


class Item145(DataItem):

    @staticmethod
    def get_item_id() -> str:
        return "I021/145"

    '''
        Name:       Flight Level
        Definition: Flight level from barometric measurements, not QNH corrected.
                    Encoded in two's complement form over two octets. The
                    least significant bit represents 1/4 FL (i.e. 0.25 FL = 25 ft).
                    Valid range: -15 FL .. 1500 FL.
        Format:     Two-octet fixed length data item.
    '''

    def __init__(self, item_name: str, length_str: str):
        super().__init__(item_name, length_str)
        self.data = {
            "RAW_HEX": None,
            # Unsigned raw integer (16-bit)
            "RAW_INT": None,
            # Signed integer after two's complement interpretation
            "SIGNED_INT": None,
            # Flight level in FL (float, e.g. 350.0)
            "FL": None,
            # Altitude in feet (approx, FL * 100)
            "ALT_FT": None,
        }

    @extract_octets
    def decode(self, octets: bytes) -> dict[str, any]:
        return self._bits_to_data(self.data.copy(), octets)

    def _bits_to_data(self, data, octets: bytes) -> dict[str, any]:
        data["RAW_HEX"] = octets.hex().upper()

        # Expect 2 octets; interpret as 16-bit big-endian two's complement
        if len(octets) < 2:
            raw_int = int.from_bytes(octets, byteorder="big")
        else:
            raw_int = int.from_bytes(octets[:2], byteorder="big")

        # Convert to signed 16-bit
        if raw_int & 0x8000:
            signed = raw_int - 0x10000
        else:
            signed = raw_int

        # Each LSB = 1/4 FL
        fl = signed * 0.25

        # Altitude in feet (1 FL = 100 ft)
        alt_ft = fl * 100.0

        data["RAW_INT"] = int(raw_int)
        data["SIGNED_INT"] = int(signed)
        data["FL"] = float(fl)
        data["ALT_FT"] = float(alt_ft)

        return data
