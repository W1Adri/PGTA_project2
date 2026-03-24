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

    def __init__(self, item_name: str, length_str: str):
        super().__init__(item_name, length_str)
        self.data = {
            "COM_230": None,
            "STAT_230": None,
            "SI_230": None,
            "MSSC_230": None,
            "ARC_230": None,
            "AIC_230": None,
            "B1A_230": None,
            "B1B_230": None,
        }

    @extract_octets
    def decode(self, octets: bytes) -> dict[str, any]:
        value = int.from_bytes(octets, byteorder="big", signed=False)
        
        COM = (value >> 13) & 0x7
        STAT = (value >> 10) & 0x7
        SI = (value >> 9) & 0x1
        MSSC = (value >> 7) & 0x1
        ARC = (value >> 6) & 0x1
        AIC = (value >> 5) & 0x1
        B1A = (value >> 4) & 0x1
        B1B = value & 0x0F

        return self._bits_to_data(self.data.copy(), COM, STAT, SI, MSSC, ARC, AIC, B1A, B1B)

    def _bits_to_data(self, data, COM, STAT, SI, MSSC, ARC, AIC, B1A, B1B) -> dict[str, any]:
        data["COM_230"] = {
            0: "No communications capability (surveillance only)",
            1: "Comm. A and Comm. B capability",
            2: "Comm. A, Comm. B and Uplink ELM",
            3: "Comm. A, Comm. B, Uplink ELM and Downlink ELM",
            4: "Level 5 Transponder capability",
            5: "Not assigned",
            6: "Not assigned",
            7: "Not assigned",
        }.get(COM, None)

        data["STAT_230"] = {
            0: "No alert, no SPI, aircraft airborne",
            1: "No alert, no SPI, aircraft on ground",
            2: "Alert, no SPI, aircraft airborne",
            3: "Alert, no SPI, aircraft on ground",
            4: "Alert, SPI, aircraft airborne or on ground",
            5: "No alert, SPI, aircraft airborne or on ground",
            6: "Not assigned",
            7: "Unknown",
        }.get(STAT, None)

        data["SI_230"] = {
            0: "SI-Code Capable",
            1: "II-Code Capable",
        }.get(SI, None)

        data["MSSC_230"] = {
            0: "No",
            1: "Yes",
        }.get(MSSC, None)

        data["ARC_230"] = {
            0: "100 ft resolution",
            1: "25 ft resolution",
        }.get(ARC, None)

        data["AIC_230"] = {
            0: "No",
            1: "Yes",
        }.get(AIC, None)

        data["B1A_230"] = B1A
        data["B1B_230"] = B1B
        return data
