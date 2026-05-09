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
        return unextracted_octets[:rep], rep

    @extract_octets
    def decode(self, octets: bytes) -> dict[str, any]:
        data = self.data.copy()
        # Distinguish: "N/A" = field not present, "NV" = field present but invalid
        if len(octets) <= 1:
            data["BP"] = "N/A"  # Field not present in message
            return data
        BP_set = (octets[1]>>7) & 0x1
        if BP_set == 0:
            data["BP"] = "NV"   # Field present but invalid (status bit = 0)
            return data
        BP = int.from_bytes(octets[2:4], byteorder="big", signed=False)
        return self._bits_to_data(self.data.copy(), BP)

    def _bits_to_data(self, data, BP) -> dict[str, any]:
        # Convert raw 12-bit value to millibars (range 0-4095 × 0.1 + 800 = 800-1209.5 mb)
        data["BP"] = round(BP * 0.1 + 800, 1)
        return data

