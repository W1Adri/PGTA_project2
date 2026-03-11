from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable
from .length_type import LengthType, AsterixDecodeError

# ============================================================
# CLASE ABSTRACTA BASE
# ============================================================

class DataItem(ABC):
    """
    Clase abstracta base para cualquier Data Item ASTERIX.
    """

    def __init__(
        self,
        item_id: str,
        item_name: str,
        length_type: LengthType,
        cursor: int,
        fixed_length: int | None = None,
        repetitive_block_size: int | None = None,
    ):
        self.item_id = item_id
        self.item_name = item_name
        self.length_type = length_type
        
        # For FIXED
        self.fixed_length = fixed_length

        # For REPETITIVE
        self.repetitive_block_size = repetitive_block_size

        # Salidas comunes
        self.raw_bytes: bytes = b""
        self.data: dict[str, Any] = {}

    @abstractmethod
    def decode(self, raw_bytes: bytes) -> dict[str, Any]:
        """
        Este método recibe SIEMPRE los bytes ya recortados por el decorator.
        """
        ...

    def get_data(self) -> dict[str, Any]:
        return self.data

    def get_raw_bytes(self) -> bytes:
        return self.raw_bytes

    def get_next_cursor(self) -> int:
        return self.next_cursor

    # --------------------------------------------------------
    # EXTRACTORES GENÉRICOS
    # --------------------------------------------------------

    def _extract_fixed(self, coded_bytes: bytes) -> tuple[bytes, int]:
        if self.fixed_length is None:
            raise AsterixDecodeError(
                f"{self.item_id}: fixed_length no definido"
            )

        start = self.cursor
        end = start + self.fixed_length

        if end > len(coded_bytes):
            raise AsterixDecodeError(
                f"{self.item_id}: no hay suficientes bytes para FIXED"
            )

        return coded_bytes[start:end], end

    def _extract_variable(self, coded_bytes: bytes) -> tuple[bytes, int]:
        """
        Variable por FX.
        Lee octeto a octeto hasta encontrar FX = 0.
        Se asume FX en el bit menos significativo (bit 1).
        """
        start = self.cursor
        pos = start

        while True:
            if pos >= len(coded_bytes):
                raise AsterixDecodeError(
                    f"{self.item_id}: fin inesperado en VARIABLE"
                )

            octet = coded_bytes[pos]
            pos += 1

            fx = octet & 0x01
            if fx == 0:
                break

        return coded_bytes[start:pos], pos

    def _extract_repetitive(self, coded_bytes: bytes) -> tuple[bytes, int]:
        """
        Formato:
            [REP][BLOCK][BLOCK][BLOCK]...
        donde cada BLOCK tiene tamaño fijo repetitive_block_size
        """
        if self.repetitive_block_size is None:
            raise AsterixDecodeError(
                f"{self.item_id}: repetitive_block_size no definido"
            )

        start = self.cursor

        if start >= len(coded_bytes):
            raise AsterixDecodeError(
                f"{self.item_id}: no hay byte REP"
            )

        rep = coded_bytes[start]
        total_len = 1 + rep * self.repetitive_block_size
        end = start + total_len

        if end > len(coded_bytes):
            raise AsterixDecodeError(
                f"{self.item_id}: no hay suficientes bytes para REPETITIVE"
            )

        return coded_bytes[start:end], end

    # --------------------------------------------------------
    # HOOK PARA COMPOUND
    # --------------------------------------------------------

    def extract_compound(self, coded_bytes: bytes) -> tuple[bytes, int]:
        """
        Solo lo implementan los items compound concretos.
        """
        raise NotImplementedError(
            f"{self.item_id}: extract_compound() no implementado"
        )