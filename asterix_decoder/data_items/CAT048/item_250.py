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
    def decode(self, octets: bytes) -> dict[str, any]:
        REP = octets[0]
        BLOCKS = []
        
        pos = 1
        for _ in range(REP):
            BLOCK = octets[pos:pos + self.repetitive_block_size]
            BLOCKS.append(BLOCK)
            pos += self.repetitive_block_size
        return self._bits_to_data(self.data.copy(), BLOCKS)

    def _bits_to_data(self, data, BLOCKS) -> dict[str, any]:
        data["REP"] = len(BLOCKS)
        data["BLOCKS"] = []

        for BLOCK in BLOCKS:
            MB_DATA = BLOCK[:7]
            BDS_SELECTOR = BLOCK[7]
            BDS1 = (BDS_SELECTOR >> 4) & 0x0F
            BDS2 = BDS_SELECTOR & 0x0F
            BDS_CODE = f"{BDS1}.{BDS2}"

            block_info = {
                "BDS": BDS_CODE,
                "MB_DATA_HEX": MB_DATA.hex().upper(),
            }

            if BDS_CODE in self.SUPPORTED_BDS:
                block_info = {
                "BDS": BDS_CODE,
                "MB_DATA_HEX": MB_DATA.hex().upper(),
                }
                data["BLOCKS"].append(block_info)

        return data
