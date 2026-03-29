from asterix_decoder.data_items.length_type import LengthType, extract_octets
from asterix_decoder.data_items.data_item import DataItem
from asterix_decoder.data_items.error_exceptions import AsterixDecodeError


class ItemRE(DataItem):

    @staticmethod
    def get_item_id() -> str:
        return "I021/RE"

    '''

    '''

    def __init__(self, item_name: str, length_str: str):
        super().__init__(item_name, length_str)
        self.data = {
            "BP": None, #
        }

    def extract_compound(self, unextracted_octets: bytes) -> tuple[bytes, int]:
        if len(unextracted_octets) < 1:
            raise AsterixDecodeError("Missing primary subfield")
        
        
        rep = unextracted_octets[0]
        print(f"{len(unextracted_octets)} rep: {rep}")
        string_octets = "".join([f"{b:08b} " for b in unextracted_octets])
        print(f"string octets: {string_octets}")
        return unextracted_octets[:rep], rep

    @extract_octets
    def decode(self, octets: bytes) -> dict[str, any]:
        data = self.data.copy()
        data["BP"] = 1013.6
        if len(octets) <= 1:
            return data
        BP_set = (octets[1]<<7) & 0x1
        if BP_set == 0:
            return data
        BP = int.from_bytes(octets[2:4], byteorder="big", signed=False)
        return self._bits_to_data(self.data.copy(), BP)

    def _bits_to_data(self, data, BP) -> dict[str, any]:
        data["BP"] = BP*0.1 + 800
        return data

