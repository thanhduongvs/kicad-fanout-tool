from kipy.board_types import FootprintInstance, Net, Pad, Track, Via, PadStack, DrillProperties
from kipy.geometry import Vector2
from collections import defaultdict
from kipy.proto.board.board_types_pb2 import ViaType, PadStackType
from dataclasses import dataclass
from kipy.geometry import Angle
from typing import Sequence

@dataclass
class TrackData:
    width: int
    layer: int
    net: Net
    start: Vector2
    end: Vector2

@dataclass
class ViaData:
    via_type: str
    via_diameter: int
    via_hole: int
    start_layer: int
    end_layer: int
    net: Net
    position: Vector2

def add_via(data: ViaData) -> Via:
    drill = DrillProperties()
    drill.start_layer = data.start_layer # BoardLayer.BL_F_Cu
    drill.end_layer = data.end_layer # BoardLayer.BL_B_Cu

    padstack = PadStack()
    padstack.type = PadStackType.PST_NORMAL
    padstack._proto.drill.CopyFrom(drill._proto)

    via = Via()
    via._proto.pad_stack.CopyFrom(padstack._proto)
    via.position = data.position # Vector2.from_xy(0, 0)
    via.net = data.net
    via.locked = False
    if data.via_type == "Micro":
        via.type = ViaType.VT_MICRO
    elif data.via_type == "Blind/Buried":
        via.type = ViaType.VT_BLIND_BURIED
    else:
        via.type = ViaType.VT_THROUGH
    via.diameter = data.via_diameter
    via.drill_diameter = data.via_hole
    return via

def add_track(data: TrackData) -> Track:
    track = Track()
    track.net = data.net
    track.layer = data.layer # BoardLayer.BL_F_Cu
    track.start = data.start # Vector2.from_xy(0, 0)
    track.end = data.end # Vector2.from_xy(0, 0)
    track.width = data.width
    return track

MIN_PITCH_NM = 50000 # 0.05mm

def calculate_group_pitch(pads: Sequence[Pad], axis='x'):
    """
    Calculate Pitch using the Grouping method (Exact Match).
    O(N) time complexity by using a Hash Dictionary.
    """
    groups = defaultdict(list)
    
    for pad in pads:
        # Get original coordinates (int/nm)
        p_x = pad.position.x
        p_y = pad.position.y
        
        if axis == 'x':
            # Calculate Pitch X -> Group by Y
            # Since no tolerance is used, use p_y directly as the key
            groups[p_y].append(p_x)
        else:
            # Calculate Pitch Y -> Group by X
            groups[p_x].append(p_y)

    all_deltas = []
    
    # Iterate through each row/column group
    for coords in groups.values():
        if len(coords) < 2: continue
        
        # Sort to calculate adjacent distances
        coords.sort()
        
        for i in range(len(coords) - 1):
            delta = coords[i+1] - coords[i]
            # Filter noise (if 2 pads overlap perfectly, delta=0)
            if delta > MIN_PITCH_NM: 
                all_deltas.append(delta)
    
    return min(all_deltas) if all_deltas else 0

def calculate_projected_pitch(pads: Sequence[Pad], axis='x'):
    """
    Calculate Pitch using the Projection method (Exact Match).
    """
    # Get a list of coordinates on the required axis
    if axis == 'x':
        coords = [p.position.x for p in pads]
    else:
        coords = [p.position.y for p in pads]
    
    # Sort
    coords.sort()
    
    unique_deltas = []
    if not coords: return 0
    
    last_val = coords[0]
    for val in coords[1:]:
        diff = val - last_val
        # Only accept if different (Diff > 0 and > Min Pitch)
        # Since tolerance is removed, diff > 0 is considered different. 
        # However, to be safe with overlapping pads, use MIN_PITCH_NM.
        if diff > MIN_PITCH_NM:
            unique_deltas.append(diff)
            last_val = val
            
    return min(unique_deltas) if unique_deltas else 0

def round_pitch(value_nm):
    # Round to the nearest thousand (1000nm = 1um)
    # Example: 799999 -> 800000
    return int(round(value_nm / 1000.0) * 1000)

def get_pitch_and_stagger_info(footprint: FootprintInstance):
    # Save the original angle
    original_angle = footprint.orientation.degrees
    
    # Rotate to 0 (to get definition pads in the correct orientation)
    if original_angle != 0.0:
        footprint.orientation = Angle.from_degrees(0.0)
    
    try:
        pads = footprint.definition.pads
        if not pads: return 0, 0, False
        
        # 1. Calculate Pitch
        real_pitch_x = calculate_group_pitch(pads, axis='x')
        real_pitch_y = calculate_group_pitch(pads, axis='y')
        
        proj_pitch_x = calculate_projected_pitch(pads, axis='x')
        proj_pitch_y = calculate_projected_pitch(pads, axis='y')

        # 2. Stagger Check
        staggered_x = False
        staggered_y = False

        if proj_pitch_x > MIN_PITCH_NM and real_pitch_x > (proj_pitch_x * 1.1):
            staggered_x = True
        if proj_pitch_y > MIN_PITCH_NM and real_pitch_y > (proj_pitch_y * 1.1):
            staggered_y = True
        x = round_pitch(real_pitch_x)
        y = round_pitch(real_pitch_y)
        return real_pitch_x, y, (staggered_x or staggered_y)

    finally:
        # Restore the original angle
        if original_angle != 0.0:
            footprint.orientation = Angle.from_degrees(original_angle)
