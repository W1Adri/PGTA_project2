from asterix_decoder.data_items.length_type import LengthType, extract_octets
from asterix_decoder.data_items.data_item import DataItem


class Item200(DataItem):

    @staticmethod
    def get_item_id() -> str:
        return "I048/200"

    '''
        Name:       Calculated Track Velocity in Polar Co-ordinates
        Definition: Calculated track velocity expressed in polar co-ordinates.
        Format:     Four-octet fixed length Data Item.
    '''

    def __init__(self, item_name: str, length_type):
        super().__init__(item_name, length_type)
        self.data = {
            "GROUNDSPEED_NM_S": None,
            "HEADING_DEG": None,
        }

    @extract_octets
    def decode(self, octets: bytes):
        self.GROUNDSPEED = int.from_bytes(octets[0:2], byteorder="big", signed=False)
        self.HEADING = int.from_bytes(octets[2:4], byteorder="big", signed=False)
        
        self._bits_to_data()

    def _bits_to_data(self):
        groundspeed_nm_s = self.GROUNDSPEED / float(1 << 14)

        self.data["GROUNDSPEED_NM_S"] = groundspeed_nm_s
        self.data["HEADING_DEG"] = self.HEADING * 360.0 / 65536.0
