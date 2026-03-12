from asterix_decoder.data_items.length_type import LengthType, extract_octets
from asterix_decoder.data_items.data_item import DataItem


class Item240(DataItem):

    @staticmethod
    def get_item_id() -> str:
        return "I048/240"

    '''
        Name:       Aircraft Identification
        Definition: Aircraft identification in 8 characters.
        Format:     Six-octet fixed length Data Item.
    '''

    def __init__(self, item_name: str, length_str: str):
        super().__init__(item_name, length_str)
        self.data = {
            "AIRCRAFT_ID": None,
        }

    @extract_octets
    def decode(self, octets: bytes):
        self.VALUE = int.from_bytes(octets, byteorder="big", signed=False)
        
        self._bits_to_data()

    def _bits_to_data(self):
        chars = []
        for shift in range(42, -1, -6):
            code = (self.VALUE >> shift) & 0x3F
            chars.append(self._decode_ia5_six_bit_char(code))

        self.data["AIRCRAFT_ID"] = "".join(chars).strip()

        
    def _decode_ia5_six_bit_char(self, value: int) -> str:
        if value == 32:
            return " "
        if 1 <= value <= 26:
            return chr(ord("A") + value - 1)
        if 48 <= value <= 57:
            return chr(ord("0") + value - 48)
        return ""
