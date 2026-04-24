from asterix_decoder.data_items.length_type import LengthType, extract_octets
from asterix_decoder.data_items.data_item import DataItem


class Item131(DataItem):

    @staticmethod
    def get_item_id() -> str:
        return "I021/131"

    '''
        Name:       Position in WGS-84 co-ordinates, high res.
        Definition: Position in WGS-84 coordinates in high resolution.
                    Encoded as two 32-bit two's-complement integers: first
                    32 bits = Latitude (bits 64..33), next 32 bits = Longitude
                    (bits 32..1). Values are in degrees where LSB = 180/2^30
                    degrees (≈ 1.6764e-7 deg ≈ 2 cm). Positive longitude = East,
                    positive latitude = North.
        Format:     Eight-octet fixed length Data Item.
    '''

    def __init__(self, item_name: str, length_str: str):
        super().__init__(item_name, length_str)
        self.data = {

            "LAT": None,
            "LON": None,
        }

    @extract_octets
    def decode(self, octets: bytes) -> dict[str, any]:
        LAT = int.from_bytes(octets[0:4], byteorder="big", signed=True)
        LON = int.from_bytes(octets[4:8], byteorder="big", signed=True)
        return self._bits_to_data(self.data.copy(), LAT, LON)

    def _bits_to_data(self, data, LAT: int, LON: int) -> dict[str, any]:
        # Expect exactly 8 octets: 4 for latitude, 4 for longitude
        data["LAT"] = round(LAT * 180/2**30, 8)
        data["LON"] = round(LON * 180/2**30, 8)

        return data
