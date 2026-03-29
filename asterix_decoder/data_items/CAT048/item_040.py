from asterix_decoder.helpers.compute_target_lat_lon import compute_target_lat_lon
from asterix_decoder.data_items.length_type import LengthType, extract_octets
from asterix_decoder.data_items.data_item import DataItem

class Item040(DataItem):

    @staticmethod
    def get_item_id() -> str:
        return "I048/040"

    
    def __init__(self, item_name: str, length_str: str):
        super().__init__(item_name, length_str)

        self.data = {
            "RHO": None, # NM 
            "THETA": None, # DEG
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
            
        return data
    
    
    