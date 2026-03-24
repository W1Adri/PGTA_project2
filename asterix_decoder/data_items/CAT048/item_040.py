import math
from asterix_decoder.data_items.length_type import LengthType, extract_octets
from asterix_decoder.data_items.data_item import DataItem


class Item040(DataItem):

    @staticmethod
    def get_item_id() -> str:
        return "I048/040"

    def __init__(self, item_name: str, length_str: str):
        super().__init__(item_name, length_str)

        # Position of the radar (if known) - used for lat/lon calculation
        self.LAT_RADAR = 41.3006963
        
        self.LON_RADAR = 2.1020662
        # self.LAT_RADAR = self._dms_to_decimal(41, 18, 2.5284, "N")
        # self.LON_RADAR = self._dms_to_decimal(2, 6, 7.4095, "E")

        self.data = {
            "RHO": None, # NM 
            "THETA": None, # DEG
            "LAT": None, #
            "LON": None, #
        }

    @extract_octets
    def decode(self, octets: bytes) -> dict[str, any]:
        rho_raw = int.from_bytes(octets[0:2], byteorder="big", signed=False)
        theta_raw = int.from_bytes(octets[2:4], byteorder="big", signed=False)
        return self._bits_to_data(self.data.copy(), rho_raw, theta_raw)

    def _bits_to_data(self, data, rho_raw: int, theta_raw: int) -> dict[str, any]:
        rho_nm = rho_raw / 256.0
        theta_deg = theta_raw * 360.0 / 65536.0

        data["RHO"] = round(rho_nm, 6)
        data["THETA"] = round(theta_deg, 6)

        # Only calculate lat/lon if radar position is known
        if self.LAT_RADAR is not None and self.LON_RADAR is not None:
            lat, lon = self._polar_surface_to_latlon(
                radar_lat_deg=self.LAT_RADAR,
                radar_lon_deg=self.LON_RADAR,
                rho_nm=rho_nm,
                theta_deg=theta_deg
            )
            data["LAT"] = round(lat , 8)
            data["LON"] = round(lon, 8)

        return data

    def _polar_surface_to_latlon(self, radar_lat_deg: float, radar_lon_deg: float,
                                rho_nm: float, theta_deg: float) -> tuple[float, float]:
        """
        Conversión 2D: RHO/THETA -> LAT/LON sobre superficie.
        THETA se interpreta como azimut desde el norte, sentido horario.
        """

        # NM -> metros
        distance_m = rho_nm * 1852.0

        # Radio medio terrestre
        R = 6378137.0

        lat1 = math.radians(radar_lat_deg)
        lon1 = math.radians(radar_lon_deg)
        brng = math.radians(theta_deg)
        ang_dist = distance_m / R

        lat2 = math.asin(
            math.sin(lat1) * math.cos(ang_dist) +
            math.cos(lat1) * math.sin(ang_dist) * math.cos(brng)
        )

        lon2 = lon1 + math.atan2(
            math.sin(brng) * math.sin(ang_dist) * math.cos(lat1),
            math.cos(ang_dist) - math.sin(lat1) * math.sin(lat2)
        )

        return math.degrees(lat2), math.degrees(lon2)

    def _dms_to_decimal(self, deg: float, minutes: float, seconds: float, hemi: str) -> float:
        value = deg + minutes / 60.0 + seconds / 3600.0
        if hemi.upper() in ("S", "W"):
            value *= -1.0
        return value