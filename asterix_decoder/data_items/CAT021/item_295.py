from asterix_decoder.data_items.length_type import LengthType, extract_octets
from asterix_decoder.data_items.data_item import DataItem
from asterix_decoder.data_items.error_exceptions import AsterixDecodeError


class Item295(DataItem):

    @staticmethod
    def get_item_id() -> str:
        return "I021/295"

    '''

    '''

    def __init__(self, item_name: str, length_str: str):
        super().__init__(item_name, length_str)
        

    def extract_compound(self, unextracted_octets: bytes) -> tuple[bytes, int]:
        if len(unextracted_octets) < 1:
            raise AsterixDecodeError("Missing primary subfield")
        item_len = 1
        
        oct_1 = (unextracted_octets[0] >> 1) & 0x7F
        item_len += oct_1.bit_count()
        if unextracted_octets[0] & 0x1 == 0:
            return unextracted_octets[:item_len], item_len
        
        oct_2 = (unextracted_octets[1] >> 1) & 0x7F
        item_len += oct_2.bit_count()+1
        if unextracted_octets[1] & 0x1 == 0:
            return unextracted_octets[:item_len], item_len
        
        oct_3 = (unextracted_octets[2] >> 1) & 0x7F
        item_len += oct_3.bit_count()+1
        if unextracted_octets[2] & 0x1 == 0:
            return unextracted_octets[:item_len], item_len
        
        oct_4 = (unextracted_octets[3] >> 1) & 0x7F
        item_len += oct_4.bit_count()+1

        return unextracted_octets[:item_len], item_len


    @extract_octets
    def decode(self, octets: bytes) -> dict[str, any]:
        return {}

  
    

