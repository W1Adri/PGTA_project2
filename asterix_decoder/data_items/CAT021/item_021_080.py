from asterix_decoder.data_items.length_type import LengthType, extract_octets
from asterix_decoder.data_items.data_item import DataItem


class Item080(DataItem):

    @staticmethod
    def get_item_id() -> str:
        return "I021/080"

    '''
        Name:       Target Address
        Definition: Pending implementation according to CAT021 specification.
        Format:     3 octets.
    '''

    def __init__(self, item_name: str, length_str: str):
        super().__init__(item_name, length_str)
        self.data = {
            "RAW_HEX": None,
            "TARGET_ADDRESS": None,
            "TARGET_ADDRESS_HEX": None,
        }

    @extract_octets
    def decode(self, octets: bytes) -> dict[str, any]:
        return self._bits_to_data(self.data.copy(), octets)

    def _bits_to_data(self, data, octets: bytes) -> dict[str, any]:
        # Expect 3 octets representing a 24-bit target address (A23..A0)
        data["RAW_HEX"] = octets.hex().upper()
        if len(octets) >= 1:
            # interpret up to 3 octets as big-endian integer
            data["TARGET_ADDRESS"] = int.from_bytes(octets[:3], byteorder="big")
            data["TARGET_ADDRESS_HEX"] = f"{data['TARGET_ADDRESS']:06X}"
        return data
