from asterix_decoder.data_items.length_type import LengthType, auto_extract_and_decode
from asterix_decoder.data_items.data_item import DataItem

class Item020(DataItem):
    def __init__(self, cursor: int):
        super().__init__(
            item_id="I048/020",
            length_type=LengthType.VARIABLE,
            cursor=cursor
        )

    @auto_extract_and_decode
    def decode(self, raw_bytes: bytes) -> dict[str, Any]:
        o1 = raw_bytes[0]

        data = {
            "TYP": (o1 >> 5) & 0b111,
            "SIM": (o1 >> 4) & 0b1,
            "RDP": (o1 >> 3) & 0b1,
            "SPI": (o1 >> 2) & 0b1,
            "RAB": (o1 >> 1) & 0b1,
        }

        if len(raw_bytes) >= 2:
            o2 = raw_bytes[1]
            data.update({
                "TST": (o2 >> 7) & 0b1,
                "ERR": (o2 >> 6) & 0b1,
                "XPP": (o2 >> 5) & 0b1,
                "ME":  (o2 >> 4) & 0b1,
                "MI":  (o2 >> 3) & 0b1,
            })

        return data