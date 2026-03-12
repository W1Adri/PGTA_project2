from asterix_decoder.data_items.length_type import LengthType, extract_octets
from asterix_decoder.data_items.data_item import DataItem
from asterix_decoder.data_items.error_exceptions import AsterixDecodeError


class Item130(DataItem):

    @staticmethod
    def get_item_id() -> str:
        return "I048/130"

    '''
        Name:       Radar Plot Characteristics
        Definition: Additional information on the quality of the target report.
        Format:     Compound Data Item.

        Project scope:
        - The uploaded guide shows one primary subfield with seven optional one-octet
          subfields.
        - No additional primary-subfield extensions are defined in the guide, so FX=1
          is treated as unsupported here.
    '''

    def __init__(self, item_name: str, length_str: str):
        super().__init__(item_name, length_str)
        self.data = {
            "SRL_DEG": None,
            "SRR": None,
            "SAM_DBM": None,
            "PRL_DEG": None,
            "PAM_DBM": None,
            "RPD_NM": None,
            "APD_DEG": None,
        }

    def extract_compound(self, unextracted_octets: bytes) -> tuple[bytes, int]:
        if len(unextracted_octets) < 1:
            raise AsterixDecodeError("Missing primary subfield")

        primary = unextracted_octets[0]

        subfield_presence = [
            (primary >> 7) & 0x1,  # SRL
            (primary >> 6) & 0x1,  # SRR
            (primary >> 5) & 0x1,  # SAM
            (primary >> 4) & 0x1,  # PRL
            (primary >> 3) & 0x1,  # PAM
            (primary >> 2) & 0x1,  # RPD
            (primary >> 1) & 0x1,  # APD
        ]

        total_len = 1 + sum(subfield_presence)
        if total_len > len(unextracted_octets):
            raise AsterixDecodeError("Not enough bytes for all present subfields")

        return unextracted_octets[:total_len], total_len

    @extract_octets
    def decode(self, octets: bytes):
        self.PRIMARY = octets[0]
        
        # Store presence flags
        self.SRL_PRESENT = (self.PRIMARY >> 7) & 0x1
        self.SRR_PRESENT = (self.PRIMARY >> 6) & 0x1
        self.SAM_PRESENT = (self.PRIMARY >> 5) & 0x1
        self.PRL_PRESENT = (self.PRIMARY >> 4) & 0x1
        self.PAM_PRESENT = (self.PRIMARY >> 3) & 0x1
        self.RPD_PRESENT = (self.PRIMARY >> 2) & 0x1
        self.APD_PRESENT = (self.PRIMARY >> 1) & 0x1
        
        # Store raw values
        pos = 1
        self.SRL = None
        self.SRR = None
        self.SAM = None
        self.PRL = None
        self.PAM = None
        self.RPD = None
        self.APD = None
        
        if self.SRL_PRESENT:
            self.SRL = octets[pos]
            pos += 1
        if self.SRR_PRESENT:
            self.SRR = octets[pos]
            pos += 1
        if self.SAM_PRESENT:
            self.SAM = octets[pos]
            pos += 1
        if self.PRL_PRESENT:
            self.PRL = octets[pos]
            pos += 1
        if self.PAM_PRESENT:
            self.PAM = octets[pos]
            pos += 1
        if self.RPD_PRESENT:
            self.RPD = octets[pos]
            pos += 1
        if self.APD_PRESENT:
            self.APD_RAW = octets[pos]
            pos += 1
        
        self._bits_to_data()

    def _bits_to_data(self):
        if self.SRL is not None:
            self.data["SRL_DEG"] = self.SRL * 360.0 / 8192.0

        if self.SRR is not None:
            self.data["SRR"] = self.SRR

        if self.SAM is not None:
            self.data["SAM_DBM"] = self._twos_complement(self.SAM, 8)

        if self.PRL is not None:
            self.data["PRL_DEG"] = self.PRL * 360.0 / 8192.0

        if self.PAM is not None:
            self.data["PAM_DBM"] = self._twos_complement(self.PAM, 8)

        if self.RPD is not None:
            self.data["RPD_NM"] = self._twos_complement(self.RPD, 8) / 256.0

        if self.APD is not None:
            self.data["APD_DEG"] = self._twos_complement(self.APD, 8) * 360.0 / 16384.0


    def _twos_complement(self, value: int, bits: int) -> int:
        if value & (1 << (bits - 1)):
            value -= 1 << bits
        return value
