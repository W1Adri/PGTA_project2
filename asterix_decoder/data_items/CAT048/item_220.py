from asterix_decoder.data_items.length_type import LengthType, extract_octets
from asterix_decoder.data_items.data_item import DataItem


class Item220(DataItem):

    @staticmethod
    def get_item_id() -> str:
        return "I048/220"

    '''
        Name:       Aircraft Address
        Definition: Aircraft address (24-bit Mode S address) assigned uniquely to each aircraft.
        Format:     Three-octet fixed length Data Item.
    '''

    def __init__(self, item_name: str, length_str: str):
        super().__init__(item_name, length_str)
        self.data = {
            "TA": None, #
            # "TI": None, #
        }

    @extract_octets
    def decode(self, octets: bytes) -> dict[str, any]:
        ADDRESS = int.from_bytes(octets, byteorder="big", signed=False)
        return self._bits_to_data(self.data.copy(), ADDRESS)

    def _bits_to_data(self, data, ADDRESS) -> dict[str, any]:
        data["TA"] = f"{ADDRESS:06X}"
        # data["TI"] = ADDRESS
        return data
