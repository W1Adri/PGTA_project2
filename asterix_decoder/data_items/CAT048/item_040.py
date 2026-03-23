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

    def __init__(self, item_name: str, length_str: str):
        super().__init__(item_name, length_str)
        self.data = {
            "RHO_NM": None,
            "THETA_DEG": None,
        }

    @extract_octets
    def decode(self, octets: bytes) -> dict[str, any]:
        RHO = int.from_bytes(octets[0:2], byteorder="big", signed=False)
        THETA = int.from_bytes(octets[2:4], byteorder="big", signed=False)
        return self._bits_to_data(self.data.copy(), RHO, THETA)

    def _bits_to_data(self, data, RHO, THETA) -> dict[str, any]:
        data["RHO_NM"] = RHO / 256.0
        data["THETA_DEG"] = THETA * 360.0 / 65536.0
        return data
