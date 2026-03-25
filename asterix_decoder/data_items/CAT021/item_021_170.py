from asterix_decoder.data_items.length_type import LengthType, extract_octets
from asterix_decoder.data_items.data_item import DataItem


class Item170(DataItem):

    @staticmethod
    def get_item_id() -> str:
        return "I021/170"

    '''
        Name:       Target Identification
        Definition: Pending implementation according to CAT021 specification.
        Format:     6 octets.
    '''

    def __init__(self, item_name: str, length_str: str):
        super().__init__(item_name, length_str)
        self.data = {
            "RAW_HEX": None,
        }

    @extract_octets
    def decode(self, octets: bytes) -> dict[str, any]:
        return self._bits_to_data(self.data.copy(), octets)

    def _bits_to_data(self, data, octets: bytes) -> dict[str, any]:
        data["RAW_HEX"] = octets.hex().upper()
        return data
