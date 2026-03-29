from asterix_decoder.data_items.length_type import LengthType, extract_octets
from asterix_decoder.data_items.data_item import DataItem


class Item040(DataItem):

    @staticmethod
    def get_item_id() -> str:
        return "I021/040"

    '''
        Name:       Target Report Descriptor
        Definition: Pending implementation according to CAT021 specification.
        Format:     1+ octets.
    '''

    def __init__(self, item_name: str, length_str: str):
        super().__init__(item_name, length_str)
        self.data = {
            "GBS": None,
        }

    @extract_octets
    def decode(self, octets: bytes) -> dict[str, any]:
        GBS = None
        if len(octets) >= 1:
            GBS = (octets[1] >> 6) & 0x1
        return self._bits_to_data(self.data.copy(), GBS)

    def _bits_to_data(self, data, GBS = None) -> dict[str, any]:
        data["GBS"] = GBS
        return data
