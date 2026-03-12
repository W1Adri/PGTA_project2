from asterix_decoder.data_items.length_type import LengthType, extract_octets
from asterix_decoder.data_items.data_item import DataItem


class Item170(DataItem):

    @staticmethod
    def get_item_id() -> str:
        return "I048/170"

    '''
        Name:       Track Status
        Definition: Status of monoradar track (PSR and/or SSR updated).
        Format:     Variable length Data Item comprising a first part of one-octet,
                    followed by one-octet extents as necessary.
    '''

    def __init__(self, item_name: str, length_str: str):
        super().__init__(item_name, length_str)
        self.data = {
            "CNF": None,
            "RAD": None,
            "DOU": None,
            "MAH": None,
            "CDM": None,
            "TRE": None,
            "GHO": None,
            "SUP": None,
            "TCC": None
        }

    @extract_octets
    def decode(self, octets: bytes):
        o1 = octets[0]
        
        self.CNF = (o1 >> 7) & 0x1
        self.RAD = (o1 >> 5) & 0x3
        self.DOU = (o1 >> 4) & 0x1
        self.MAH = (o1 >> 3) & 0x1
        self.CDM = (o1 >> 1) & 0x3

        if len(octets) >= 2:
            o2 = octets[1]
            self.TRE = (o2 >> 7) & 0x1
            self.GHO = (o2 >> 6) & 0x1
            self.SUP = (o2 >> 5) & 0x1
            self.TCC = (o2 >> 4) & 0x1
        
        self._bits_to_data()

    def _bits_to_data(self):
        ### FIRST OCTET ###
        self.data["CNF"] = {
            0: "Confirmed Track",
            1: "Tentative Track",
        }.get(self.CNF, "Unknown")

        self.data["RAD"] = {
            0b00: "Combined Track",
            0b01: "PSR Track",
            0b10: "SSR/Mode S Track",
            0b11: "Invalid",
        }.get(self.RAD, "Unknown")

        self.data["DOU"] = {
            0: "Normal confidence",
            1: "Low confidence in plot to track association",
        }.get(self.DOU, "Unknown")

        self.data["MAH"] = {
            0: "No horizontal man. sensed",
            1: "Horizontal man. sensed",
        }.get(self.MAH, "Unknown")

        self.data["CDM"] = {
            0b00: "Maintaining",
            0b01: "Climbing",
            0b10: "Descending",
            0b11: "Unknown",
        }.get(self.CDM, "Unknown")

        ### SECOND OCTET ###
        if len(self.octets) == 1:
            return
        
        self.data["TRE"] = {
            0: "Track still alive",
            1: "End of track lifetime (last report for this track)",
        }.get(self.TRE, "Unknown")

        self.data["GHO"] = {
            0: "True target track",
            1: "Ghost target track",
        }.get(self.GHO, "Unknown")

        self.data["SUP"] = {
            0: "No",
            1: "Yes",
        }.get(self.SUP, "Unknown")

        self.data["TCC"] = {
            0: "Tracking performed in Radar Plane",
            1: "Slant range correction and projection into a 2D reference plane applied",
        }.get(self.TCC, "Unknown")

