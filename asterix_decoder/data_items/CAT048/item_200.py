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

    def __init__(self, item_name: str, length_str: str):
        super().__init__(item_name, length_str)
        self.data = {
            "GS_KT": None, #
            "HEADING": None, #
        }

    @extract_octets
    def decode(self, octets: bytes) -> dict[str, any]:
        GROUNDSPEED = int.from_bytes(octets[0:2], byteorder="big", signed=False)
        HEADING = int.from_bytes(octets[2:4], byteorder="big", signed=False)
        return self._bits_to_data(self.data.copy(), GROUNDSPEED, HEADING)

    def _bits_to_data(self, data, GROUNDSPEED, HEADING) -> dict[str, any]:
        GROUNDSPEED_KT = GROUNDSPEED / float(1 << 14)

        data["GS_KT"] = round(GROUNDSPEED_KT * 0.22, 1)
        data["HEADING"] = round(HEADING * 360.0 / 65536.0, 4)
        return data
