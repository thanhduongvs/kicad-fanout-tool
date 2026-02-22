import re
import csv
import os
import sys
from typing import Optional, Sequence
from kipy import KiCad
from kipy.board import Board, BoardLayer, BoardOriginType
from kipy.board_types import FootprintInstance, Field
from kipy.board_types import Field
from kipy.board_types import Net
from kipy.geometry import Vector2
from kipy.proto.board.board_types_pb2 import FootprintMountingStyle
from collections import defaultdict
from kipy.board_types import Track, Via, PadStack, DrillProperties
from kipy.proto.board.board_types_pb2 import ViaType, PadStackType, BoardLayer
from kipy.util.units import from_mm
from dataclasses import dataclass
import re
from typing import Optional, Sequence, List, Tuple, Union
from kipy.geometry import Angle

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

def via_in_pad(footprint: FootprintInstance, board: Board, data: ViaData):
    items: List[Via] = []
    pads = footprint.definition.pads
    for pad in pads:
        data.position = pad.position
        data.net = pad.net
        items.append(add_via(data))
    board.create_items(items)
    board.add_to_selection(items)



MIN_PITCH_NM = 50000 # 0.05mm

def calculate_group_pitch(pads, axis='x'):
    """
    Tính Pitch theo phương pháp Gom nhóm (Exact Match).
    Tốc độ O(N) nhờ dùng Dictionary Hash.
    """
    groups = defaultdict(list)
    
    for pad in pads:
        # Lấy tọa độ nguyên bản (int/nm)
        p_x = pad.position.x
        p_y = pad.position.y
        
        if axis == 'x':
            # Tính Pitch X -> Gom theo Y
            # Vì không dùng Tolerance, ta dùng p_y làm key trực tiếp
            groups[p_y].append(p_x)
        else:
            # Tính Pitch Y -> Gom theo X
            groups[p_x].append(p_y)

    all_deltas = []
    
    # Duyệt qua từng nhóm hàng/cột
    for coords in groups.values():
        if len(coords) < 2: continue
        
        # Sắp xếp để tính khoảng cách liền kề
        coords.sort()
        
        for i in range(len(coords) - 1):
            delta = coords[i+1] - coords[i]
            # Lọc nhiễu (nếu 2 pad trùng vị trí hoàn toàn delta=0)
            if delta > MIN_PITCH_NM: 
                all_deltas.append(delta)
    
    return min(all_deltas) if all_deltas else 0

def calculate_projected_pitch(pads, axis='x'):
    """
    Tính Pitch theo phương pháp Chiếu (Exact Match).
    """
    # Lấy danh sách tọa độ trên trục cần tính
    if axis == 'x':
        coords = [p.position.x for p in pads]
    else:
        coords = [p.position.y for p in pads]
    
    # Sắp xếp
    coords.sort()
    
    unique_deltas = []
    if not coords: return 0
    
    last_val = coords[0]
    for val in coords[1:]:
        diff = val - last_val
        # Chỉ lấy nếu khác nhau (Diff > 0 và > Min Pitch)
        # Vì bỏ Tolerance, chỉ cần diff > 0 là coi như khác nhau. 
        # Nhưng để an toàn với pad trùng, ta dùng MIN_PITCH_NM.
        if diff > MIN_PITCH_NM:
            unique_deltas.append(diff)
            last_val = val
            
    return min(unique_deltas) if unique_deltas else 0

def round_pitch(value_nm):
    # Làm tròn đến hàng nghìn gần nhất (1000nm = 1um)
    # Ví dụ: 799999 -> 800000
    return int(round(value_nm / 1000.0) * 1000)

def get_pitch_and_stagger_info(footprint: FootprintInstance):
    # Lưu góc cũ
    original_angle = footprint.orientation.degrees
    
    # Xoay về 0 (để lấy definition pads đúng hướng)
    if original_angle != 0.0:
        footprint.orientation = Angle.from_degrees(0.0)
    
    try:
        pads = footprint.definition.pads
        if not pads: return 0, 0, False
        
        # 1. Tính Pitch
        real_pitch_x = calculate_group_pitch(pads, axis='x')
        real_pitch_y = calculate_group_pitch(pads, axis='y')
        
        proj_pitch_x = calculate_projected_pitch(pads, axis='x')
        proj_pitch_y = calculate_projected_pitch(pads, axis='y')

        # 2. So le Check
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
        # Khôi phục góc cũ
        if original_angle != 0.0:
            footprint.orientation = Angle.from_degrees(original_angle)
