from asterix_decoder.data_items.length_type import LengthType, extract_octets
from asterix_decoder.data_items.data_item import DataItem


class Item010(DataItem):

    @staticmethod
    def get_item_id() -> str:
        return "I048/010"

    '''
        Name:       Data Source Identifier
        Definition: Identification of the radar station from which the data is received.
        Format:     Two-octet fixed length Data Item.
    '''

    def __init__(self, item_name: str, length_type):
        super().__init__(item_name, length_type)
        self.data = {
            "SAC": None,
            "SIC": None,
        }

    @extract_octets
    def decode(self, octets: bytes):
        self.SAC = octets[0]
        self.SIC = octets[1]
        
        self._bits_to_data()
    
    def _bits_to_data(self):
        self.data["SAC"] = self.SAC
        self.data["SIC"] = self.SIC
