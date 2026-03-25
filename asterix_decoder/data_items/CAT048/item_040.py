import math
from asterix_decoder.data_items.length_type import LengthType, extract_octets
from asterix_decoder.data_items.data_item import DataItem
from asterix_decoder.data_items.helpers.lat_lon import compute_target

class Item040(DataItem):

    @staticmethod
    def get_item_id() -> str:
        return "I048/040"

    def __init__(self, item_name: str, length_str: str):
        super().__init__(item_name, length_str)

        # Position of the radar (if known) - used for lat/lon calculation
        self.LAT_RADAR = 41.30070234
        self.LON_RADAR = 2.10205817
        self.H_RADAR     = 27.09296262

        self.data = {
            "RHO": None, # NM 
            "THETA": None, # DEG
            "LAT": None, #
            "LON": None, #
        }

    @extract_octets
    def decode(self, octets: bytes, **kwargs) -> dict[str, any]:
        rho_raw = int.from_bytes(octets[0:2], byteorder="big", signed=False)
        theta_raw = int.from_bytes(octets[2:4], byteorder="big", signed=False)
        FL = kwargs.get("FL", None)
        return self._bits_to_data(self.data.copy(), rho_raw, theta_raw, FL)

    def _bits_to_data(self, data, rho_raw: int, theta_raw: int, FL: float|None) -> dict[str, any]:
        rho_nm = rho_raw / 256.0
        theta_deg = theta_raw * 360.0 / 65536.0

        data["RHO"] = round(rho_nm, 6)
        data["THETA"] = round(theta_deg, 6)

        # Only calculate lat/lon if radar position is known
        if FL is not None:
            lat, lon = compute_target(
                lat_ref_deg=self.LAT_RADAR,
                lon_ref_deg=self.LON_RADAR,
                h_ref_m=self.H_RADAR,
                rho_nm=rho_nm,
                theta_deg=theta_deg,
                FL_target=FL
            )
            data["LAT"] = round(lat, 8)
            data["LON"] = round(lon, 8)

        return data