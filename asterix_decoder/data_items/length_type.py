from enum import Enum, auto
from functools import wraps
from typing import Any, Callable


# ============================================================
# LENGTH TYPES
# ============================================================

class LengthType(Enum):
    FIXED = auto()
    VARIABLE = auto()      # for FX
    REPETITIVE = auto()    # for REP
    COMPOUND = auto()


# ============================================================
# EXCEPTION
# ============================================================

class AsterixDecodeError(Exception):
    pass


# ============================================================
# DECORATOR
# ============================================================

def auto_extract_and_decode(func: Callable) -> Callable:
    """
    Decorator para el método decode() de cada DataItem.

    Flujo:
    1. Mira self.length_type
    2. Extrae raw_bytes desde coded_bytes usando self.cursor
    3. Guarda self.raw_bytes
    4. Guarda self.next_cursor
    5. Llama al decode real del item con raw_bytes
    """
    @wraps(func)
    def wrapper(self: "DataItem", unextracted_bytes: bytes) -> dict[str, Any]:
        if not isinstance(self.length_type, LengthType):
            raise AsterixDecodeError(
                f"{self.item_id}: length_type inválido -> {self.length_type}"
            )

        # ---- EXTRACT DEPENDS ON THE TYPE----
        if self.length_type == LengthType.FIXED:
            raw_bytes, next_cursor = self._extract_fixed(unextracted_bytes)

        elif self.length_type == LengthType.VARIABLE:
            raw_bytes, next_cursor = self._extract_variable(unextracted_bytes)

        elif self.length_type == LengthType.REPETITIVE:
            raw_bytes, next_cursor = self._extract_repetitive(unextracted_bytes)

        elif self.length_type == LengthType.COMPOUND:
            raw_bytes, next_cursor = self.extract_compound(unextracted_bytes)

        else:
            raise AsterixDecodeError(
                f"{self.item_id}: length_type not supported -> {self.length_type}"
            )

        self.raw_bytes = raw_bytes

        # Llama al decode REAL del item con los bytes recortados
        func(self, raw_bytes)

        return next_cursor

    return wrapper


