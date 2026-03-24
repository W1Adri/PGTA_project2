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

    def __init__(self, item_name: str, length_str: str):
        super().__init__(item_name, length_str)
        self.data = {
            "V_090": None, #
            "G_090": None, #
            "FL": None, #
            "H(m)": None, #
            "H(ft)": None, #
        }

    @extract_octets
    def decode(self, octets: bytes) -> dict[str, any]:
        value = int.from_bytes(octets, byteorder="big", signed=False)
        
        V = (value >> 15) & 0x1
        G = (value >> 14) & 0x1
        FL = value & 0x3FFF
        
        return self._bits_to_data(self.data.copy(), V, G, FL)

    def _bits_to_data(self, data, V, G, FL) -> dict[str, any]:
        data["V_090"] = {
            0: "Code validated",
            1: "Code not validated",
        }.get(V, "Unknown")

        data["G_090"] = {
            0: "Default",
            1: "Garbled code",
        }.get(G, "Unknown")

        fl_signed = self._twos_complement(FL, 14)
        data["FL"] = fl_signed / 4.0
        data["H(ft)"] = int(data["FL"] * 100)  # Convert flight level to feet
        data["H(m)"] = float(f"{(data['H(ft)'] * 0.3048):.1f}")  # Convert feet to meters
        return data
    
    def _twos_complement(self, value: int, bits: int) -> int:
        if value & (1 << (bits - 1)):
            value -= 1 << bits
        return value

