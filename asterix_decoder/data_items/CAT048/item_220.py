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
            "ADDRESS_INT": None,
            "ADDRESS_HEX": None,
        }

    @extract_octets
    def decode(self, octets: bytes):
        self.ADDRESS = int.from_bytes(octets, byteorder="big", signed=False)
        
        self._bits_to_data()

    def _bits_to_data(self):
        self.data["ADDRESS_INT"] = self.ADDRESS
        self.data["ADDRESS_HEX"] = f"{self.ADDRESS:06X}"
