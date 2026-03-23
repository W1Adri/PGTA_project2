from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable
from .length_type import LengthType, extract_octets
from .error_exceptions import AsterixDecodeError

# ============================================================
# ABSTRACT BASE CLASS
# ============================================================

class DataItem(ABC):
    """
    Abstract base class for any ASTERIX Data Item.
    """
    
    @staticmethod
    @abstractmethod
    def get_item_id() -> str:
        """
        Returns the item_id of the concrete DataItem class.
        Used for mapping in the decoder.
        """
        ...
    

    def __init__(self, item_name: str, length_str: str):
        self.item_id = self.get_item_id()
        self.item_name = item_name
        self.length_type = self.extract_length_type(length_str)

        # Common outputs
        self.octets: bytes = b""
        self.data: dict[str, Any] = {}
        
        
    def extract_length_type(self, length_str: str) -> 'LengthType':
        length_type = LengthType.FIXED
        
        if (length_str == "1+"):
            length_type = LengthType.VARIABLE
        
        elif (length_str == "1+1+"):
            length_type = LengthType.COMPOUND
        
        elif ("n" in length_str.lower()): #example: 1+8*n 
            length_type = LengthType.REPETITIVE
            self.repetitive_block_size = int(length_str.lower().split("+")[1].replace("n", "").replace("*", "").strip())
            
        try:  
            if length_type==LengthType.FIXED and int(length_str)>0:
                self.fixed_length = int(length_str)            
        except:
            raise AsterixDecodeError(f"Invalid length type in CSV: {length_str}")    
        
        return length_type

    @abstractmethod
    def decode(self, octets) -> dict[str, any]: 
        """
        This method unextracted_octets as input, extracts the relevant octets with the decorator, decodes them, and stores the decoded values in self.data.
        The actual extraction logic is handled
        """
        ...



    # --------------------------------------------------------
    # HOOK FOR COMPOUND
    # --------------------------------------------------------

    def extract_compound(self, unextracted_octets: bytes) -> tuple[bytes, int]:
        """
        Only implemented by concrete compound items.
        """
        raise NotImplementedError(
            f"{self.item_id}: extract_compound() not implemented"
        )
    
    def copy(self) -> DataItem:
        """
        Creates a copy of the DataItem instance. Useful for handling repetitions.
        """
        return self.__class__(self.item_name, self.length_str)
        
        
class ItemXXX(DataItem):
    
    @staticmethod
    def get_item_id() -> str:
        return "IXXX/XXX"
    
    def __init__(self, item_name: str, length_str: str, item_id: str):
        super().__init__(item_name, length_str)
        self.item_id = self.get_item_id()+"-"+item_id

    @extract_octets
    def decode(self, octets: bytes):
        # Implement the decoding logic for this item
        return {}