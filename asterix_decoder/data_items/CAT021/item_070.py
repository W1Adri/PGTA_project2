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
            "MODE_3/A": None, #
        }

    @extract_octets
    def decode(self, octets: bytes) -> dict[str, any]:
        value = int.from_bytes(octets, byteorder="big", signed=False)
        MODE_3A = value & 0x0FFF
        return self._bits_to_data(self.data.copy(), MODE_3A)

    def _bits_to_data(self, data, MODE_3A: int) -> dict[str, any]:
        # Extract individual octal digits from the 12-bit value
        a = (MODE_3A >> 9) & 0x7
        b = (MODE_3A >> 6) & 0x7
        c = (MODE_3A >> 3) & 0x7
        d = MODE_3A & 0x7
        data["MODE_3/A"] = f"{a}{b}{c}{d}"
        return data
 