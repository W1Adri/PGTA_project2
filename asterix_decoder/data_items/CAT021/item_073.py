from asterix_decoder.data_items.length_type import LengthType, extract_octets
from asterix_decoder.data_items.data_item import DataItem


class Item073(DataItem):

    @staticmethod
    def get_item_id() -> str:
        return "I021/073"

    '''
        Name:       Time of Message Reception of Position
        Definition: Pending implementation according to CAT021 specification.
        Format:     3 octets.
    '''

    def __init__(self, item_name: str, length_str: str):
        super().__init__(item_name, length_str)
        self.data = {
            "TIME": None, #
        }

    @extract_octets
    def decode(self, octets: bytes) -> dict[str, any]:
        TIME = int.from_bytes(octets, byteorder="big", signed=False)
        return self._bits_to_data(self.data.copy(), TIME)

    def _bits_to_data(self, data, TIME) -> dict[str, any]:
        data["TIME"] = self._format_utc_from_seconds(TIME / 128.0)
        return data
    
    def _format_utc_from_seconds(self, total_seconds: float) -> str:
        hours = int(total_seconds // 3600) % 24
        minutes = int((total_seconds % 3600) // 60)
        seconds = total_seconds % 60
        miliseconds = total_seconds % 1
        return f"{hours:02d}:{minutes:02d}:{int(seconds):02d}:{round(miliseconds * 1000):03d}"
