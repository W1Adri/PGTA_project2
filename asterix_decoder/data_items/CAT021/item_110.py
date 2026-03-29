from asterix_decoder.data_items.length_type import LengthType, extract_octets
from asterix_decoder.data_items.data_item import DataItem
from asterix_decoder.data_items.error_exceptions import AsterixDecodeError


class Item110(DataItem):

    @staticmethod
    def get_item_id() -> str:
        return "I021/110"

    '''

    '''

    def __init__(self, item_name: str, length_str: str):
        super().__init__(item_name, length_str)
        

    def extract_compound(self, unextracted_octets: bytes) -> tuple[bytes, int]:
        if len(unextracted_octets) < 1:
            raise AsterixDecodeError("Missing primary subfield")
        item_len = 1
        TIS_set = (unextracted_octets[0]>>7) & 0x1
        if TIS_set == 1:
            item_len += 1
        TID_set = (unextracted_octets[0]>>6) & 0x1
        if TID_set == 1:
            rep = unextracted_octets[item_len]
            item_len += 1 + 15*rep

        
        return unextracted_octets[:item_len], item_len

    @extract_octets
    def decode(self, octets: bytes) -> dict[str, any]:
        return {}

  
    

