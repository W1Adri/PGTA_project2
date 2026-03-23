from enum import Enum, auto
from functools import wraps
from typing import Any, Callable
from .error_exceptions import AsterixDecodeError


# ============================================================
# LENGTH TYPES
# ============================================================

class LengthType(Enum):
    FIXED = auto()
    VARIABLE = auto()      # for FX
    REPETITIVE = auto()    # for REP
    COMPOUND = auto()


# ============================================================
# DECORATOR
# ============================================================

def extract_octets(func: Callable) -> Callable:
    """
    Decorator for the decode() method of each DataItem.

    Flow:
    1. Checks self.length_type
    2. Extracts raw_bytes from coded_bytes using self.cursor
    3. Stores self.raw_bytes
    4. Stores self.next_cursor
    5. Calls the item's real decode with raw_bytes
    """
    @wraps(func)
    def wrapper(self, unextracted_octets: bytes) -> int:
        if not isinstance(self.length_type, LengthType):
            raise AsterixDecodeError(
                f"{self.item_id}: invalid length_type -> {self.length_type}"
            )

        # ---- EXTRACT DEPENDS ON THE TYPE----
        extract_type = self.length_type.name
        try:
            if self.length_type == LengthType.FIXED:
                octets, next_cursor = _extract_fixed(
                    unextracted_octets,
                    self.fixed_length,
                )

            elif self.length_type == LengthType.VARIABLE:
                octets, next_cursor = _extract_variable(unextracted_octets)

            elif self.length_type == LengthType.REPETITIVE:
                octets, next_cursor = _extract_repetitive(
                    unextracted_octets,
                    self.repetitive_block_size,
                )

            elif self.length_type == LengthType.COMPOUND:
                octets, next_cursor = self.extract_compound(unextracted_octets)

            else:
                raise AsterixDecodeError(
                    f"{self.item_id}: length_type not supported -> {self.length_type}"
                )
        except AsterixDecodeError as exc:
            raise AsterixDecodeError(
                f"{self.item_id}: extract_type {extract_type} failed -> {exc}"
            ) from exc

        # Calls the REAL decode of the item with the trimmed bytes
        decoded_data = func(self, octets)

        return next_cursor, decoded_data

    return wrapper

def _extract_fixed(
    unextracted_octets: bytes,
    fixed_length: int,
) -> tuple[bytes, int]:

    if fixed_length > len(unextracted_octets):
        raise AsterixDecodeError(
            "Not enough bytes for FIXED"
        )

    return unextracted_octets[:fixed_length], fixed_length

def _extract_variable(unextracted_octets: bytes) -> tuple[bytes, int]:
    """
    Variable length via FX.
    Reads octet by octet until FX = 0 is found.
    FX is assumed to be in the least significant bit (bit 1).
    """
    
    pos = 0

    while True:
        if pos >= len(unextracted_octets):
            raise AsterixDecodeError(
                "Unexpected end in VARIABLE"
            )

        octet = unextracted_octets[pos]
        pos += 1

        fx = octet & 0x01
        if fx == 0:
            break

    return unextracted_octets[:pos], pos

def _extract_repetitive(
    unextracted_octets: bytes,
    repetitive_block_size: int,
) -> tuple[bytes, int]:
    """
    Format:
        [REP][BLOCK][BLOCK][BLOCK]...
    where each BLOCK has a fixed size of repetitive_block_size
    """

    if 0 >= len(unextracted_octets):
        raise AsterixDecodeError(
            "Missing REP byte"
        )

    rep = unextracted_octets[0]
    total_len = 1 + rep * repetitive_block_size

    if total_len > len(unextracted_octets):
        raise AsterixDecodeError(
            "Not enough bytes for REPETITIVE"
        )

    return unextracted_octets[:total_len], total_len



