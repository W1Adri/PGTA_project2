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
            "RAW_HEX": None,
            # Raw signed integers parsed from 4-octet two's-complement fields
            "RAW_INT_LAT": None,
            "RAW_INT_LON": None,
            # Degrees in decimal
            "LAT": None,
            "LON": None,
            # Human-readable strings
            "LAT_STR": None,
            "LON_STR": None,
        }

    @extract_octets
    def decode(self, octets: bytes) -> dict[str, any]:
        return self._bits_to_data(self.data.copy(), octets)

    def _bits_to_data(self, data, octets: bytes) -> dict[str, any]:
        # Expect exactly 8 octets: 4 for latitude, 4 for longitude
        data["RAW_HEX"] = octets.hex().upper()

        if len(octets) < 8:
            # Not enough data; handle gracefully by zero-padding on the right
            octets = octets.ljust(8, b"\x00")

        lat_raw = int.from_bytes(octets[0:4], byteorder="big", signed=True)
        lon_raw = int.from_bytes(octets[4:8], byteorder="big", signed=True)

        # LSB = 180 / 2^30 degrees
        scale = 180.0 / (1 << 30)

        lat = lat_raw * scale
        lon = lon_raw * scale

        data["RAW_INT_LAT"] = int(lat_raw)
        data["RAW_INT_LON"] = int(lon_raw)
        data["LAT"] = float(lat)
        data["LON"] = float(lon)
        data["LAT_STR"] = f"{lat:.7f}° N" if lat >= 0 else f"{abs(lat):.7f}° S"
        data["LON_STR"] = f"{lon:.7f}° E" if lon >= 0 else f"{abs(lon):.7f}° W"

        return data
