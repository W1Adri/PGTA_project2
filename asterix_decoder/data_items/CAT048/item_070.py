from asterix_decoder.data_items.length_type import LengthType, extract_octets
from asterix_decoder.data_items.data_item import DataItem


class Item070(DataItem):

    @staticmethod
    def get_item_id() -> str:
        return "I048/070"

    '''
        Name:       Mode-3/A Code in Octal Representation
        Definition: Mode-3/A code converted into octal representation.
        Format:     Two-octet fixed length Data Item.
    '''

    def __init__(self, item_name: str, length_str: str):
        super().__init__(item_name, length_str)
        self.data = {
            "V": None,
            "G": None,
            "L": None,
            "MODE_3A_CODE": None,
        }

    @extract_octets
    def decode(self, octets: bytes):
        value = int.from_bytes(octets, byteorder="big", signed=False)
        
        self.V = (value >> 15) & 0x1
        self.G = (value >> 14) & 0x1
        self.L = (value >> 13) & 0x1
        self.CODE_BITS = value & 0x0FFF
        
        self._bits_to_data()

    def _bits_to_data(self):
        self.data["V"] = {
            0: "Code validated",
            1: "Code not validated",
        }.get(self.V, "Unknown")

        self.data["G"] = {
            0: "Default",
            1: "Garbled code",
        }.get(self.G, "Unknown")

        self.data["L"] = {
            0: "Mode-3/A code derived from the reply of the transponder",
            1: "Mode-3/A code not extracted during the last scan",
        }.get(self.L, "Unknown")

        a = (self.CODE_BITS >> 9) & 0x7
        b = (self.CODE_BITS >> 6) & 0x7
        c = (self.CODE_BITS >> 3) & 0x7
        d = self.CODE_BITS & 0x7
        self.data["MODE_3A_CODE"] = f"{a}{b}{c}{d}"
