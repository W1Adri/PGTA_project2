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
    def decode(self, octets: bytes) -> dict[str, any]:
        PRIMARY = octets[0]

        SRL_PRESENT = (PRIMARY >> 7) & 0x1
        SRR_PRESENT = (PRIMARY >> 6) & 0x1
        SAM_PRESENT = (PRIMARY >> 5) & 0x1
        PRL_PRESENT = (PRIMARY >> 4) & 0x1
        PAM_PRESENT = (PRIMARY >> 3) & 0x1
        RPD_PRESENT = (PRIMARY >> 2) & 0x1
        APD_PRESENT = (PRIMARY >> 1) & 0x1

        pos = 1
        SRL = None
        SRR = None
        SAM = None
        PRL = None
        PAM = None
        RPD = None
        APD = None

        if SRL_PRESENT:
            SRL = octets[pos]
            pos += 1
        if SRR_PRESENT:
            SRR = octets[pos]
            pos += 1
        if SAM_PRESENT:
            SAM = octets[pos]
            pos += 1
        if PRL_PRESENT:
            PRL = octets[pos]
            pos += 1
        if PAM_PRESENT:
            PAM = octets[pos]
            pos += 1
        if RPD_PRESENT:
            RPD = octets[pos]
            pos += 1
        if APD_PRESENT:
            APD = octets[pos]
            pos += 1

        return self._bits_to_data(self.data.copy(), SRL, SRR, SAM, PRL, PAM, RPD, APD)

    def _bits_to_data(self, data, SRL, SRR, SAM, PRL, PAM, RPD, APD) -> dict[str, any]:
        if SRL is not None:
            data["SRL_DEG"] = SRL * 360.0 / 8192.0

        if SRR is not None:
            data["SRR"] = SRR

        if SAM is not None:
            data["SAM_DBM"] = self._twos_complement(SAM, 8)

        if PRL is not None:
            data["PRL_DEG"] = PRL * 360.0 / 8192.0

        if PAM is not None:
            data["PAM_DBM"] = self._twos_complement(PAM, 8)

        if RPD is not None:
            data["RPD_NM"] = self._twos_complement(RPD, 8) / 256.0

        if APD is not None:
            data["APD_DEG"] = self._twos_complement(APD, 8) * 360.0 / 16384.0
        return data


    def _twos_complement(self, value: int, bits: int) -> int:
        if value & (1 << (bits - 1)):
            value -= 1 << bits
        return value
