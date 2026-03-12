from asterix_decoder.data_items.length_type import LengthType, extract_octets
from asterix_decoder.data_items.data_item import DataItem

class Item090(DataItem):

    @staticmethod
    def get_item_id() -> str:
        return "I048/090"

    '''
        Name:       Flight Level in Binary Representation
        Definition: Flight level converted into binary representation.
        Format:     Two-octet fixed length Data Item.
    '''

    def __init__(self, item_name: str, length_type):
        super().__init__(item_name, length_type)
        self.data = {
            "V": None,
            "G": None,
            "FL": None,
        }

    @extract_octets
    def decode(self, octets: bytes):
        value = int.from_bytes(octets, byteorder="big", signed=False)
        
        self.V = (value >> 15) & 0x1
        self.G = (value >> 14) & 0x1
        self.FL_BITS = value & 0x3FFF
        
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

        fl_signed = self._twos_complement(self.FL_BITS, 14)
        self.data["FL"] = fl_signed / 4.0

    
    def _twos_complement(self, value: int, bits: int) -> int:
        if value & (1 << (bits - 1)):
            value -= 1 << bits
        return value

