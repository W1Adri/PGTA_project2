from asterix_decoder.data_items.length_type import LengthType, extract_octets
from asterix_decoder.data_items.data_item import DataItem


class Item040(DataItem):

    @staticmethod
    def get_item_id() -> str:
        return "I048/040"

    '''
        Name:       Measured Position in Polar Co-ordinates
        Definition: Measured position of an aircraft in local polar co-ordinates.
        Format:     Four-octet fixed length Data Item.
    '''

    def __init__(self, item_name: str, length_type):
        super().__init__(item_name, length_type)
        self.data = {
            "RHO_NM": None,
            "THETA_DEG": None,
        }

    @extract_octets
    def decode(self, octets: bytes):
        self.RHO = int.from_bytes(octets[0:2], byteorder="big", signed=False)
        self.THETA = int.from_bytes(octets[2:4], byteorder="big", signed=False)
        
        self._bits_to_data()

    def _bits_to_data(self):
        self.data["RHO_NM"] = self.RHO / 256.0
        self.data["THETA_DEG"] = self.THETA * 360.0 / 65536.0
