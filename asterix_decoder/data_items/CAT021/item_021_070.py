from asterix_decoder.data_items.length_type import LengthType, extract_octets
from asterix_decoder.data_items.data_item import DataItem


class Item070(DataItem):

    @staticmethod
    def get_item_id() -> str:
        return "I021/070"

    '''
        Name:       Mode 3/A Code
        Definition: Pending implementation according to CAT021 specification.
        Format:     2 octets.
    '''

    def __init__(self, item_name: str, length_str: str):
        super().__init__(item_name, length_str)
        self.data = {
            "RAW_HEX": None,
            # 16-bit raw integer (if 2 octets)
            "RAW_INT": None,
            # 12-bit Mode-3/A value (decimal)
            "CODE12": None,
            # Mode-3/A in 4-digit octal string (e.g. '1200')
            "MODE3_OCTAL": None,
            # Mode-3/A as integer (0-4095)
            "MODE3_DECIMAL": None,
            # Individual octal digits
            "D1": None,
            "D2": None,
            "D3": None,
            "D4": None,
        }

    @extract_octets
    def decode(self, octets: bytes) -> dict[str, any]:
        return self._bits_to_data(self.data.copy(), octets)

    def _bits_to_data(self, data, octets: bytes) -> dict[str, any]:
        data["RAW_HEX"] = octets.hex().upper()

        # Interpret up to 2 octets as big-endian
        if len(octets) < 2:
            raw_int = int.from_bytes(octets, byteorder="big")
        else:
            raw_int = int.from_bytes(octets[:2], byteorder="big")

        # Lower 12 bits hold the Mode-3/A code (4 octal digits)
        code12 = raw_int & 0x0FFF

        # Extract 4 octal digits from 12 bits (3 bits per digit)
        d1 = (code12 >> 9) & 0x7
        d2 = (code12 >> 6) & 0x7
        d3 = (code12 >> 3) & 0x7
        d4 = code12 & 0x7

        octal_str = f"{d1}{d2}{d3}{d4}"

        data["RAW_INT"] = int(raw_int)
        data["CODE12"] = int(code12)
        data["MODE3_OCTAL"] = octal_str
        data["MODE3_DECIMAL"] = int(code12)
        data["D1"] = int(d1)
        data["D2"] = int(d2)
        data["D3"] = int(d3)
        data["D4"] = int(d4)

        return data
