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
            "CNF_170": None, #
            "RAD_170": None, #
            "DOU_170": None, #
            "MAH_170": None, #
            "CDM_170": None, #
            "TRE_170": None, #
            "GHO_170": None, #
            "SUP_170": None, #
            "TCC_170": None, #
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
        data["CNF_170"] = {
            0: "Confirmed track",
            1: "Tentative track",
        }.get(CNF, None)

        data["RAD_170"] = {
            0b00: "Combined",
            0b01: "PSR",
            0b10: "SSR/MODE S",
            0b11: "Invalid",
        }.get(RAD, None)

        data["DOU_170"] = {
            0: "Normal confidence",
            1: "Low confidence",
        }.get(DOU, None)

        data["MAH_170"] = {
            0: "No horizontal man.sensed",
            1: "Horizontal man.sensed",
        }.get(MAH, None)

        data["CDM_170"] = {
            0b00: "Maintaining",
            0b01: "Climbing",
            0b10: "Descending",
            0b11: "Unknown",
        }.get(CDM, None)

        ### SECOND OCTET ###
        if OCTETS_LEN == 1:
            return data
        
        data["TRE_170"] = {
            0: "Track still alive",
            1: "Last report",
        }.get(TRE, None)

        data["GHO_170"] = {
            0: "True target",
            1: "Ghost target",
        }.get(GHO, None)

        data["SUP_170"] = {
            0: "NO",
            1: "YES",
        }.get(SUP, None)

        data["TCC_170"] = {
            0: "Tracking performed", #in Radar Plane
            1: "Slat range correction",
        }.get(TCC, None)
        return data

