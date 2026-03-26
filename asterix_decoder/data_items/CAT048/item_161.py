from asterix_decoder.data_items.length_type import LengthType, extract_octets
from asterix_decoder.data_items.data_item import DataItem


class Item161(DataItem):

    @staticmethod
    def get_item_id() -> str:
        return "I048/161"

    '''
        Name:       Track Number
        Definition: An integer value representing a unique reference to a track record within a particular track file.
        Format:     Two-octet fixed length Data Item.
    '''

    def __init__(self, item_name: str, length_str: str):
        super().__init__(item_name, length_str)
        self.data = {
            "TN": None,
        }

    @extract_octets
    def decode(self, octets: bytes) -> dict[str, any]:
        # Combina los dos octetos en un entero (16 bits)
        track_number = (octets[0] << 8) | octets[1]
        return self._bits_to_data(self.data.copy(), track_number)

    def _bits_to_data(self, data, track_number) -> dict[str, any]:
        data["TN"] = track_number
        return data