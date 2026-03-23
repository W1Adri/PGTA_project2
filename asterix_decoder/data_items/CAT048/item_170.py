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
    def decode(self, octets: bytes) -> dict[str, any]:
        o1 = octets[0]
        
        CNF = (o1 >> 7) & 0x1
        RAD = (o1 >> 5) & 0x3
        DOU = (o1 >> 4) & 0x1
        MAH = (o1 >> 3) & 0x1
        CDM = (o1 >> 1) & 0x3

        TRE = GHO = SUP = TCC = None

        if len(octets) >= 2:
            o2 = octets[1]
            TRE = (o2 >> 7) & 0x1
            GHO = (o2 >> 6) & 0x1
            SUP = (o2 >> 5) & 0x1
            TCC = (o2 >> 4) & 0x1

        return self._bits_to_data(self.data.copy(), len(octets), CNF, RAD, DOU, MAH, CDM, TRE, GHO, SUP, TCC)

    def _bits_to_data(self, data, OCTETS_LEN, CNF, RAD, DOU, MAH, CDM, TRE, GHO, SUP, TCC) -> dict[str, any]:
        ### FIRST OCTET ###
        data["CNF"] = {
            0: "Confirmed Track",
            1: "Tentative Track",
        }.get(CNF, "Unknown")

        data["RAD"] = {
            0b00: "Combined Track",
            0b01: "PSR Track",
            0b10: "SSR/Mode S Track",
            0b11: "Invalid",
        }.get(RAD, "Unknown")

        data["DOU"] = {
            0: "Normal confidence",
            1: "Low confidence in plot to track association",
        }.get(DOU, "Unknown")

        data["MAH"] = {
            0: "No horizontal man. sensed",
            1: "Horizontal man. sensed",
        }.get(MAH, "Unknown")

        data["CDM"] = {
            0b00: "Maintaining",
            0b01: "Climbing",
            0b10: "Descending",
            0b11: "Unknown",
        }.get(CDM, "Unknown")

        ### SECOND OCTET ###
        if OCTETS_LEN == 1:
            return data
        
        data["TRE"] = {
            0: "Track still alive",
            1: "End of track lifetime (last report for this track)",
        }.get(TRE, "Unknown")

        data["GHO"] = {
            0: "True target track",
            1: "Ghost target track",
        }.get(GHO, "Unknown")

        data["SUP"] = {
            0: "No",
            1: "Yes",
        }.get(SUP, "Unknown")

        data["TCC"] = {
            0: "Tracking performed in Radar Plane",
            1: "Slant range correction and projection into a 2D reference plane applied",
        }.get(TCC, "Unknown")
        return data

