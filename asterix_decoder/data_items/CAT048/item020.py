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
    
    def __init__(self, item_name: str, length_type):
        super().__init__(item_name, length_type)
        self.data = {
            "TYP": None,    
            "SIM": None,  
            "RDP": None, 
            "SPI": None,   
            "RAB": None,   
            "TST": None,   
            "ERR": None,   
            "XPP": None, 
            "ME": None,     
            "MI": None,
            "FOE_FRI": None,
            "ADSB_EP": None,  #On-Site ADS-B Information
            "ADSB_VAL": None,
            "SCN_EP": None,   #Surveillance Cluster Network Information
            "SCN_VAL": None,
            "PA_EP": None,  #Passive Acquisition Interface Information
            "PA_VAL": None,   
        }

    @extract_octets
    def decode(self, octets):
         
        o1 = octets[0]
        self.TYP = (o1 >> 5) & 0b111
        self.SIM = (o1 >> 4) & 0b1
        self.RDP = (o1 >> 3) & 0b1
        self.SPI = (o1 >> 2) & 0b1
        self.RAB = (o1 >> 1) & 0b1

        if len(octets) >= 2:
            o2 = self.octets[1]
            self.TST = (o2 >> 7) & 0b1
            self.ERR = (o2 >> 6) & 0b1
            self.XPP = (o2 >> 5) & 0b1
            self.ME = (o2 >> 4) & 0b1
            self.MI = (o2 >> 3) & 0b1
            self.FOE_FRI = (o2 >> 1) & 0b11
        if len(octets) >= 3:
            o3 = self.octets[2]
            self.ADSB_EP = (o3 >> 7) & 0b1
            self.ADSB_VAL = (o3 >> 6) & 0b1
            self.SCN_EP = (o3 >> 5) & 0b1
            self.SCN_VAL = (o3 >> 4) & 0b1
            self.PA_EP = (o3 >> 3) & 0b1
            self.PA_VAL = (o3 >> 2) & 0b1
            self.SPARE = (o3 >> 1) & 0b1 #This must be 0
            
        self._bits_to_data()
            
    def _bits_to_data(self):
        
        ### FIRST OCTET ###
        self.data["TYP"] = {
            0b000: "No detection",
            0b001: "Single PSR detection",
            0b010: "Single SSR detection",
            0b011: "SSR + PSR detection",
            0b100: "Single ModeS All-Call",
            0b101: "Single ModeS Roll-Call",
            0b110: "ModeS All-Call + PSR",
            0b111: "ModeS Roll-Call + PSR",
        }.get(self.TYP, "Unknown")
        
        self.data["SIM"] = {
            0b0: "Actual target report",
            0b1: "Simulated target report",
        }.get(self.SIM, "Unknown")
        
        self.data["RDP"] = {
            0b0: "Report from RDP Chain 1",
            0b1: "Report from RDP Chain 2",
        }.get(self.RDP, "Unknown")
        
        self.data["SPI"] = {
            0b0: "Absence of SPI",
            0b1: "Special Position Identification",
        }.get(self.SPI, "Unknown")
        
        self.data["RAB"] = {
            0b0: "Report from aircraft transponder",
            0b1: "Report from field monitor (fixed transponder)",
        }.get(self.RAB, "Unknown")
        
        ### SECOND OCTET ###
        if len(self.octets) == 1:
            return

        self.data["TST"] = {
            0b0: "Real target report",
            0b1: "Test target report",
        }.get(self.TST, "Unknown")

        self.data["ERR"] = {
            0b0: "No Extended Range",
            0b1: "Extended Range present",
        }.get(self.ERR, "Unknown")

        self.data["XPP"] = {
            0b0: "No X-Pulse present",
            0b1: "X-Pulse present",
        }.get(self.XPP, "Unknown")

        self.data["ME"] = {
            0b0: "No military emergency",
            0b1: "Military emergency",
        }.get(self.ME, "Unknown")

        self.data["MI"] = {
            0b0: "No military identification",
            0b1: "Military identification",
        }.get(self.MI, "Unknown")
        
        self.data["FOE_FRI"] = {
            0b00: "No Mode 4 interrogation",
            0b01: "Freindly target",
            0b10: "Unknown target",
            0b11: "No reply",
        }.get(self.FOE_FRI, "Unknown")

        ### THIRD OCTET ###
        if len(self.octets) == 2:
            return
        
        self.data["ADSB_EP"] = {
            0b0: "ADSB not populated",
            0b1: "ADSB populated",
        }.get(self.ADSB_EP, "Unknown")
        
        self.data["ADSB_VAL"] = {
            0b0: "not available",
            0b1: "available",
        }.get(self.ADSB_VAL, "Unknown")
        
        self.data["SCN_EP"] = {
            0b0: "SCN not populated",
            0b1: "SCN populated",
        }.get(self.SCN_EP, "Unknown")
        
        self.data["SCN_VAL"] = {
            0b0: "not available",
            0b1: "available",
        }.get(self.SCN_VAL, "Unknown")
        
        self.data["PA_EP"] = {
            0b0: "PA not populated",
            0b1: "PA populated",
        }.get(self.PA_EP, "Unknown")    
        
        self.data["PA_VAL"] = {
            0b0: "not available",
            0b1: "available",
        }.get(self.PA_VAL, "Unknown")
        
        

        