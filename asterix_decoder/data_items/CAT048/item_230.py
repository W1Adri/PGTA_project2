from asterix_decoder.data_items.length_type import LengthType, extract_octets
from asterix_decoder.data_items.data_item import DataItem


class Item230(DataItem):

    @staticmethod
    def get_item_id() -> str:
        return "I048/230"

    '''
        Name:       Communications/ACAS Capability and Flight Status
        Definition: Communications capability of the transponder, capability of the
                    on-board ACAS equipment and flight status.
        Format:     Two-octet fixed length Data Item.
    '''

    def __init__(self, item_name: str, length_type):
        super().__init__(item_name, length_type)
        self.data = {
            "COM": None,
            "STAT": None,
            "SI": None,
            "MSSC": None,
            "ARC": None,
            "AIC": None,
            "B1A": None,
            "B1B": None,
        }

    @extract_octets
    def decode(self, octets: bytes):
        value = int.from_bytes(octets, byteorder="big", signed=False)
        
        self.COM = (value >> 13) & 0x7
        self.STAT = (value >> 10) & 0x7
        self.SI = (value >> 9) & 0x1
        self.MSSC = (value >> 7) & 0x1
        self.ARC = (value >> 6) & 0x1
        self.AIC = (value >> 5) & 0x1
        self.B1A = (value >> 4) & 0x1
        self.B1B = value & 0x0F
        
        self._bits_to_data()

    def _bits_to_data(self):
        self.data["COM"] = {
            0: "No communications capability (surveillance only)",
            1: "Comm. A and Comm. B capability",
            2: "Comm. A, Comm. B and Uplink ELM",
            3: "Comm. A, Comm. B, Uplink ELM and Downlink ELM",
            4: "Level 5 Transponder capability",
            5: "Not assigned",
            6: "Not assigned",
            7: "Not assigned",
        }.get(self.COM, "Unknown")

        self.data["STAT"] = {
            0: "No alert, no SPI, aircraft airborne",
            1: "No alert, no SPI, aircraft on ground",
            2: "Alert, no SPI, aircraft airborne",
            3: "Alert, no SPI, aircraft on ground",
            4: "Alert, SPI, aircraft airborne or on ground",
            5: "No alert, SPI, aircraft airborne or on ground",
            6: "Not assigned",
            7: "Unknown",
        }.get(self.STAT, "Unknown")

        self.data["SI"] = {
            0: "SI-Code Capable",
            1: "II-Code Capable",
        }.get(self.SI, "Unknown")

        self.data["MSSC"] = {
            0: "No",
            1: "Yes",
        }.get(self.MSSC, "Unknown")

        self.data["ARC"] = {
            0: "100 ft resolution",
            1: "25 ft resolution",
        }.get(self.ARC, "Unknown")

        self.data["AIC"] = {
            0: "No",
            1: "Yes",
        }.get(self.AIC, "Unknown")

        self.data["B1A"] = self.B1A
        self.data["B1B"] = self.B1B
