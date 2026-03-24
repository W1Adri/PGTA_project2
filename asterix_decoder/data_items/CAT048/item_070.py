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
            "V_070": None, #
            "G_070": None, #
            # "L": None,
            "MODE_3/A": None, #
        }

    @extract_octets
    def decode(self, octets: bytes) -> dict[str, any]:
        value = int.from_bytes(octets, byteorder="big", signed=False)
        
        V = (value >> 15) & 0x1
        G = (value >> 14) & 0x1
        # L = (value >> 13) & 0x1
        CODE_BITS = value & 0x0FFF
        return self._bits_to_data(self.data.copy(), V, G, CODE_BITS)

    def _bits_to_data(self, data, V, G, CODE_BITS) -> dict[str, any]:
        data["V_070"] = {
            0: "Code validated",
            1: "Code not validated",
        }.get(V, None)

        data["G_070"] = {
            0: "Default",
            1: "Garbled code",
        }.get(G, None)

        # data["L"] = {
        #     0: "Mode-3/A code derived from the reply of the transponder",
        #     1: "Mode-3/A code not extracted during the last scan",
        # }.get(L, None)

        a = (CODE_BITS >> 9) & 0x7
        b = (CODE_BITS >> 6) & 0x7
        c = (CODE_BITS >> 3) & 0x7
        d = CODE_BITS & 0x7
        data["MODE_3/A"] = f"{a}{b}{c}{d}"
        return data
