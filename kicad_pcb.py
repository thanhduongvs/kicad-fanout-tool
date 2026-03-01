import re
from kipy import KiCad
from kipy.board import Board, BoardLayer
from kipy.board_types import FootprintInstance
from kipy.proto.board.board_types_pb2 import BoardLayer
from typing import Optional, List, Tuple
from dataclasses import dataclass

def natural_sort_key(footprint: FootprintInstance):
    text = footprint.reference_field.text.value
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', text)]

@dataclass
class LayerMap:
    name: str
    id: int

class KiCadPCB:
    def __init__(self):
        self.kicad: Optional[KiCad] = None
        self.board: Optional[Board] = None
        self.footprints: List[FootprintInstance] = []
        self.references: List[str] = []
        self.stackup: List[LayerMap] = []
        self.layers: List[str] = []
        self.connected: bool = False

    def connect_kicad(self) -> Tuple[bool, str]:
        try:
            self.kicad = KiCad()
            self.board = self.kicad.get_board()
            
            self.footprints = []
            self.references = []
            self.stackup = []
            self.layers = []
            
            all_footprints = self.board.get_footprints()
            for fp in all_footprints:
                if hasattr(fp, 'definition') and fp.definition is not None:
                    if len(fp.definition.pads) > 5:
                        self.footprints.append(fp)
            
            self.footprints.sort(key=natural_sort_key)
            self.references = [f.reference_field.text.value for f in self.footprints]

            stackup = self.board.get_stackup()
            for l in stackup.layers:
                if BoardLayer.BL_F_Cu <= l.layer <= BoardLayer.BL_B_Cu:
                    l_name = l.user_name if l.user_name else f"Layer {l.layer}"
                    self.stackup.append(LayerMap(l_name, l.layer))
            
            self.stackup.sort(key=lambda x: x.id)
            self.layers = [layer.name for layer in self.stackup]

            self.connected = True
            return True, "Connected to KiCad"
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.connected = False
            self.footprints = []
            self.references = []
            self.stackup = []
            self.layers = []
            return False, str(e)
