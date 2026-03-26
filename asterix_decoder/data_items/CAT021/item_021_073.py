from asterix_decoder.data_items.length_type import LengthType, extract_octets
from asterix_decoder.data_items.data_item import DataItem


class Item073(DataItem):

    @staticmethod
    def get_item_id() -> str:
        return "I021/073"

    '''
        Name:       Time of Message Reception of Position
        Definition: Pending implementation according to CAT021 specification.
        Format:     3 octets.
    '''

    def __init__(self, item_name: str, length_str: str):
        super().__init__(item_name, length_str)
        self.data = {
            "RAW_HEX": None,
            # Integer value of the 24-bit field
            "RAW_INT": None,
            # Seconds since midnight (float, resolution 1/128 s)
            "SECONDS": None,
            # Human readable UTC time (HH:MM:SS.sss)
            "TIME_UTC": None,
            "HOUR": None,
            "MINUTE": None,
            "SECOND": None,
            "MILLISECOND": None,
        }

    @extract_octets
    def decode(self, octets: bytes) -> dict[str, any]:
        return self._bits_to_data(self.data.copy(), octets)

    def _bits_to_data(self, data, octets: bytes) -> dict[str, any]:
        data["RAW_HEX"] = octets.hex().upper()

        # Expect exactly 3 octets per specification
        if len(octets) < 3:
            # If shorter, interpret whatever is present as big-endian
            raw_int = int.from_bytes(octets, byteorder="big")
        else:
            raw_int = int.from_bytes(octets[:3], byteorder="big")

        # LSB unit is 2^-7 s = 1/128 s
        seconds = raw_int / 128.0

        # Break into hh:mm:ss.mmm (UTC time since midnight)
        total_seconds = int(seconds)
        frac = seconds - total_seconds

        hour = (total_seconds // 3600) % 24
        minute = (total_seconds % 3600) // 60
        sec = total_seconds % 60
        msec = int(round(frac * 1000))
        # handle rounding overflow (e.g., .9995 -> 1000 ms)
        if msec >= 1000:
            msec = 0
            sec += 1
            if sec >= 60:
                sec = 0
                minute += 1
                if minute >= 60:
                    minute = 0
                    hour = (hour + 1) % 24

        time_utc = f"{hour:02d}:{minute:02d}:{sec:02d}.{msec:03d}"

        data["RAW_INT"] = raw_int
        data["SECONDS"] = seconds
        data["TIME_UTC"] = time_utc
        data["HOUR"] = int(hour)
        data["MINUTE"] = int(minute)
        data["SECOND"] = int(sec)
        data["MILLISECOND"] = int(msec)

        return data
