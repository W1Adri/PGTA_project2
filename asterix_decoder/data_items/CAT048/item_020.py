from asterix_decoder.data_items.length_type import LengthType, extract_octets
from asterix_decoder.data_items.data_item import DataItem

class Item020(DataItem):
    
    @staticmethod
    def get_item_id() -> str:
        return "I048/020"
    
    '''
        Name:       Target Report Descriptor
        Definition: Type and properties of the target report.
        Format:     Variable length Data Item comprising a first part of one-octet,
                    followed by one-octet extents as necessary
    '''
    
    def __init__(self, item_name: str, length_str: str):
        super().__init__(item_name, length_str)
        self.data = {
            "TYP_020": None, #
            "SIM_020": None, #
            "RDP_020": None, #
            "SPI_020": None, #  
            "RAB_020": None, #  
            "TST_020": None, #  
            "ERR_020": None, #   
            "XPP_020": None, #
            "ME_020": None, #   
            "MI_020": None, #
            "FOE_FRI_020": None, #
            "ADSB_EP": None,  #On-Site ADS-B Information
            "ADSB_VAL": None,
            "SCN_EP": None,   #Surveillance Cluster Network Information
            "SCN_VAL": None,
            "PA_EP": None,  #Passive Acquisition Interface Information
            "PA_VAL": None,   
        }

    @extract_octets
    def decode(self, octets) -> dict[str, any]:
         
        o1 = octets[0]
        TYP = (o1 >> 5) & 0b111
        SIM = (o1 >> 4) & 0b1
        RDP = (o1 >> 3) & 0b1
        SPI = (o1 >> 2) & 0b1
        RAB = (o1 >> 1) & 0b1

        TST = ERR = XPP = ME = MI = FOE_FRI = None
        ADSB_EP = ADSB_VAL = SCN_EP = SCN_VAL = PA_EP = PA_VAL = None

        if len(octets) >= 2:
            o2 = octets[1]
            TST = (o2 >> 7) & 0b1
            ERR = (o2 >> 6) & 0b1
            XPP = (o2 >> 5) & 0b1
            ME = (o2 >> 4) & 0b1
            MI = (o2 >> 3) & 0b1
            FOE_FRI = (o2 >> 1) & 0b11
        if len(octets) >= 3:
            o3 = octets[2]
            ADSB_EP = (o3 >> 7) & 0b1
            ADSB_VAL = (o3 >> 6) & 0b1
            SCN_EP = (o3 >> 5) & 0b1
            SCN_VAL = (o3 >> 4) & 0b1
            PA_EP = (o3 >> 3) & 0b1
            PA_VAL = (o3 >> 2) & 0b1

        return self._bits_to_data(
            self.data.copy(),
            len(octets),
            TYP,
            SIM,
            RDP,
            SPI,
            RAB,
            TST,
            ERR,
            XPP,
            ME,
            MI,
            FOE_FRI,
            ADSB_EP,
            ADSB_VAL,
            SCN_EP,
            SCN_VAL,
            PA_EP,
            PA_VAL,
        )
            

    def _bits_to_data(self, data, OCTETS_LEN, TYP, SIM, RDP, SPI, RAB, TST, ERR, XPP, ME, MI, FOE_FRI, ADSB_EP, ADSB_VAL, SCN_EP, SCN_VAL, PA_EP, PA_VAL) -> dict[str, any]:
        
        ### FIRST OCTET ###
        data["TYP_020"] = {
            0b000: "No detection",
            0b001: "Single PSR detection",
            0b010: "Single SSR detection",
            0b011: "SSR + PSR detection",
            0b100: "Single ModeS All-Call",
            0b101: "Single ModeS Roll-Call",
            0b110: "ModeS All-Call + PSR",
            0b111: "ModeS Roll-Call + PSR",
        }.get(TYP, "Unknown")
        
        data["SIM_020"] = {
            0b0: "Actual target report",
            0b1: "Simulated target report",
        }.get(SIM, "Unknown")
        
        data["RDP_020"] = {
            0b0: "Report from RDP Chain 1",
            0b1: "Report from RDP Chain 2",
        }.get(RDP, "Unknown")
        
        data["SPI_020"] = {
            0b0: "Absence of SPI",
            0b1: "Special Position Identification",
        }.get(SPI, "Unknown")
        
        data["RAB_020"] = {
            0b0: "Report from aircraft transponder",
            0b1: "Report from field monitor (fixed transponder)",
        }.get(RAB, "Unknown")
        
        ### SECOND OCTET ###
        if OCTETS_LEN == 1:
            return data

        data["TST_020"] = {
            0b0: "Real target report",
            0b1: "Test target report",
        }.get(TST, "Unknown")

        data["ERR_020"] = {
            0b0: "No Extended Range",
            0b1: "Extended Range present",
        }.get(ERR, "Unknown")

        data["XPP_020"] = {
            0b0: "No X-Pulse present",
            0b1: "X-Pulse present",
        }.get(XPP, "Unknown")

        data["ME_020"] = {
            0b0: "No military emergency",
            0b1: "Military emergency",
        }.get(ME, "Unknown")

        data["MI_020"] = {
            0b0: "No military identification",
            0b1: "Military identification",
        }.get(MI, "Unknown")
        
        data["FOE_FRI_020"] = {
            0b00: "No Mode 4 interrogation",
            0b01: "Freindly target",
            0b10: "Unknown target",
            0b11: "No reply",
        }.get(FOE_FRI, "Unknown")

        ### THIRD OCTET ###
        if OCTETS_LEN == 2:
            return data
        
        data["ADSB_EP"] = {
            0b0: "ADSB not populated",
            0b1: "ADSB populated",
        }.get(ADSB_EP, "Unknown")
        
        data["ADSB_VAL"] = {
            0b0: "not available",
            0b1: "available",
        }.get(ADSB_VAL, "Unknown")
        
        data["SCN_EP"] = {
            0b0: "SCN not populated",
            0b1: "SCN populated",
        }.get(SCN_EP, "Unknown")
        
        data["SCN_VAL"] = {
            0b0: "not available",
            0b1: "available",
        }.get(SCN_VAL, "Unknown")
        
        data["PA_EP"] = {
            0b0: "PA not populated",
            0b1: "PA populated",
        }.get(PA_EP, "Unknown")    
        
        data["PA_VAL"] = {
            0b0: "not available",
            0b1: "available",
        }.get(PA_VAL, "Unknown")
        return data
        
        

        