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
            "FL": None,
        }

    @extract_octets
    def decode(self, octets: bytes) -> dict[str, any]:
        FL = int.from_bytes(octets, byteorder="big", signed=True)
        return self._bits_to_data(self.data.copy(), FL)

    def _bits_to_data(self, data, FL: int) -> dict[str, any]:
        data["FL"] = FL*0.25
        return data


    