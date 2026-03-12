from asterix_decoder.data_items.length_type import LengthType, extract_octets
from asterix_decoder.data_items.data_item import DataItem


class Item250(DataItem):

    @staticmethod
    def get_item_id() -> str:
        return "I048/250"

    '''
        Name:       Mode S MB Data
        Definition: Repetitive Mode S Comm-B payloads.
        Format:     REP + N blocks of 8 octets.

        Project scope taken from the uploaded guide:
        - Only BDS 4.0, 5.0 and 6.0 are explicitly requested.
        - The guide does not include the bit layout of those BDS registers, so this
          item extracts the repetitions, identifies the BDS register, and surfaces
          the raw MB payload for the supported BDS values.
    '''

    SUPPORTED_BDS = {"4.0", "5.0", "6.0"}

    def __init__(self, item_name: str, length_type):
        super().__init__(item_name, length_type)
        self.data = {
            "REP": None,
            "BLOCKS": None,
        }

    @extract_octets
    def decode(self, octets: bytes):
        self.REP = octets[0]
        self.BLOCKS = []
        
        pos = 1
        for _ in range(self.REP):
            block = octets[pos:pos + self.repetitive_block_size]
            self.BLOCKS.append(block)
            pos += self.repetitive_block_size
        
        self._bits_to_data()

    def _bits_to_data(self):
        self.data["BLOCKS"] = []

        for block in self.BLOCKS:
            mb_data = block[:7]
            bds_selector = block[7]
            bds1 = (bds_selector >> 4) & 0x0F
            bds2 = bds_selector & 0x0F
            bds_code = f"{bds1}.{bds2}"

            block_info = {
                "BDS": bds_code,
                "MB_DATA_HEX": mb_data.hex().upper(),
            }

            if bds_code in self.SUPPORTED_BDS:
                block_info = {
                "BDS": bds_code,
                "MB_DATA_HEX": mb_data.hex().upper(),
                }
                self.data["BLOCKS"].append(block_info)
