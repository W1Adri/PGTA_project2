from asterix_decoder.data_items.length_type import LengthType, extract_octets
from asterix_decoder.data_items.data_item import DataItem


class Item170(DataItem):

    @staticmethod
    def get_item_id() -> str:
        return "I021/170"

    '''
        Name:       Target Identification
        Definition: Target (aircraft or vehicle) identification in 8 characters,
                    coded on 6 bits per character (IA-5 / Table 3-9). Characters
                    are packed MSB-first across six octets (48 bits total).
        Format:     Six-octet fixed length Data Item.
    '''

    def __init__(self, item_name: str, length_str: str):
        super().__init__(item_name, length_str)
        self.data = {
            "RAW_HEX": None,
            # 48-bit raw integer representation of the 6 octets
            "RAW_INT": None,
            # Target Identification string (up to 8 chars)
            "TI": None,
            # Individual decoded characters as list
            "CHARS": None,
        }

    @extract_octets
    def decode(self, octets: bytes) -> dict[str, any]:
        VALUE = int.from_bytes(octets, byteorder="big", signed=False)
        return self._bits_to_data(self.data.copy(), VALUE)

    def _bits_to_data(self, data, VALUE: int) -> dict[str, any]:
        chars = []
        for shift in range(42, -1, -6):
            code = (VALUE >> shift) & 0x3F
            chars.append(self._decode_ia5_six_bit_char(code))

        data["TARGET_IDENTIFICATION"] = "".join(chars).rstrip()
        return data

    def _decode_ia5_six_bit_char(self, value: int) -> str:
        if value == 32:
            return " "
        if 1 <= value <= 26:
            return chr(ord("A") + value - 1)
        if 48 <= value <= 57:
            return chr(ord("0") + value - 48)
        return ""
