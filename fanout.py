from kipy.board import Board
from kipy.board_types import Track, Via, FootprintInstance, Pad
from kipy.geometry import Angle, Vector2
from typing import List, Union, Dict, Tuple
from utils import ViaData, TrackData, add_via, add_track, get_pitch_and_stagger_info
import math

class Fanout:
    def __init__(self, footprint: FootprintInstance, board: Board,
                 via: ViaData, track: TrackData, package: str,
                 alignment: str, direction: str, in_pad: bool, unused_pad: bool,
                 fanout_length: int, stagger_gap: int, via_pitch: int):
        self.board = board
        self.footprint = footprint
        self.track = track
        self.via = via
        self.package = package
        self.alignment = alignment
        self.direction = direction
        self.in_pad = in_pad
        self.unused_pad = unused_pad
        self.fanout_length= fanout_length
        self.stagger_gap = stagger_gap
        self.via_pitch = via_pitch
        self.items: List[Union[Via, Track]] = []
        print(f"package: {package}")
        print(f"alignment: {alignment}")
        print(f"direction: {direction}")

    def remove_items(self):
        if self.board is None:
            return
        self.board.remove_items(self.items)
        self.items = []

    def fanout(self):
        self.items = []
        if self.in_pad:
            self.fanout_via_in_pad()
            return
        if self.package == "BGA":
            match self.alignment:
                case "Quadrant":
                    self.fanout_bga_quadrant()
                case "Diagonal":
                    self.fanout_bga_diagonal()
                case "X-pattern":
                    self.fanout_bga_xpattern()
                case "Staggered":
                    self.fanout_bga_staggered()
        elif self.package == "SOIC/QFN":
            match self.alignment:
                case "Linear Escape":
                    self.fanout_soic_linear_escape()
                case "Fan Escape":
                    self.fanout_soic_fan_escape()
                case "Staggered Linear":
                    self.fanout_soic_staggered_linear()
                case "Staggered Fan":
                    self.fanout_soic_staggered_fan()
        else:
            print("Connector/FPC")

    def fanout_via_in_pad(self):
        items: List[Via] = []
        pads = self.footprint.definition.pads
        for pad in pads:
            if self.unused_pad:
                net_name = pad.net.name.lower()
                if net_name == "" or "unconnected" in net_name: continue
            via = ViaData(
                via_type = self.via.via_type,
                via_diameter = self.via.via_diameter,
                via_hole = self.via.via_hole,
                start_layer = self.via.start_layer,
                end_layer = self.via.end_layer,
                net = pad.net,
                position = pad.position
            )
            items.append(add_via(via))

        self.items = self.board.create_items(items)
        self.board.add_to_selection(self.items)

    def fanout_bga_quadrant(self):
        items: List[Union[Via, Track]] = []
        angle_rad = self.footprint.orientation.to_radians()
        px, py, is_stag = get_pitch_and_stagger_info(self.footprint)
        
        # 1. Create a set of 4 Offset candidates (Local system, unrotated)
        if not is_stag:
            # Square grid: 4 slots located at 4 diagonal corners
            local_candidates = [
                (-px/2, -py/2), ( px/2, -py/2),
                ( px/2,  py/2), (-px/2,  py/2)
            ]
        else:
            # Staggered: 4 slots located between horizontal/vertical pads
            local_candidates = [
                (-px/2, 0), ( px/2, 0),
                ( 0, -py/2), ( 0,  py/2)
            ]
            
        # Standard KiCad rotation formula
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)

        # Store the 4 PRE-ROTATED candidates in the Global system
        global_candidates = []
        for lx, ly in local_candidates:
            gx = lx * cos_a + ly * sin_a
            gy = -lx * sin_a + ly * cos_a
            global_candidates.append((gx, gy))
        
        # Center of the IC
        cx = clean_nm(self.footprint.position.x)
        cy = clean_nm(self.footprint.position.y)

        pads = self.footprint.definition.pads
        
        for pad in pads:
            if self.unused_pad:
                net_name = pad.net.name.lower()
                if net_name == "" or "unconnected" in net_name:
                    continue

            out_gx = clean_nm(pad.position.x) - cx
            out_gy = clean_nm(pad.position.y )- cy

            target_gx = out_gx * 1.01 + 0.001
            target_gy = out_gy
            
            best_dx = 0
            best_dy = 0
            max_score = -float('inf')
            
            # This small loop uses only basic math operations (very fast)
            # Utilizing the pre-calculated global_candidates list above
            for gx, gy in global_candidates:
                score = (gx * target_gx) + (gy * target_gy)
                
                if score > max_score:
                    max_score = score
                    best_dx = gx
                    best_dy = gy
                    
            # Add Offset
            dest_x = clean_nm(pad.position.x + best_dx)
            dest_y = clean_nm(pad.position.y + best_dy)
            point = Vector2.from_xy(dest_x, dest_y)

            track = TrackData(
                width = self.track.width,
                layer = self.track.layer,
                net = pad.net,
                start = pad.position,
                end = point
            )

            via = ViaData(
                via_type = self.via.via_type,
                via_diameter = self.via.via_diameter,
                via_hole = self.via.via_hole,
                start_layer = self.via.start_layer,
                end_layer = self.via.end_layer,
                net = pad.net,
                position = point
            )
            items.append(add_track(track))
            items.append(add_via(via))

        self.items = self.board.create_items(items)
        self.board.add_to_selection(self.items)

    def fanout_bga_diagonal(self):
        """
        Smart Diagonal Fanout function:
        1. Ensures vias are placed exactly on the diagonal (or horizontal/vertical lines if layout is staggered).
        2. Automatically shifts angles and prioritizes horizontal routing (Horizontal Bias) at 45-degree corners.
        """
        items: List[Union[Via, Track]] = []
        angle_rad = self.footprint.orientation.to_radians()
        px, py, is_stag = get_pitch_and_stagger_info(self.footprint)
        
        # 1. Determine the Target Direction on the KiCad Screen (Global Target)
        # KiCad: Negative X (Left), Negative Y (Up)
        if self.direction == 'TopLeft':
            tx, ty = -1.01, -1
        elif self.direction == 'TopRight':
            tx, ty = 1.01, -1
        elif self.direction == 'BottomRight':
            tx, ty = 1.01, 1
        elif self.direction == 'BottomLeft':
            tx, ty = -1.01, 1
        else:
            tx, ty = -1.01, -1
            
        # 2. Create a set of Offset Candidates (Unrotated Local coordinate system)
        if not is_stag:
            # Orthogonal Grid Layout: Route diagonally to 4 corners
            candidates = [
                (-px/2, -py/2), # Local Top-Left
                ( px/2, -py/2), # Local Top-Right
                ( px/2,  py/2), # Local Bottom-Right
                (-px/2,  py/2)  # Local Bottom-Left
            ]
        else:
            # Staggered Layout: Route straight to 4 horizontal/vertical slots
            candidates = [
                (-px/2, 0),     # Local Left
                ( px/2, 0),     # Local Right
                ( 0, -py/2),    # Local Top
                ( 0,  py/2)     # Local Bottom
            ]
            
        # Rotation matrix formula (Eliminates KiCad's bending deviation)
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)
        
        best_dx = 0
        best_dy = 0
        max_score = -float('inf')
        
        # 3. Find the most "Screen-aligned" candidate
        for lx, ly in candidates:
            # Rotate the offset vector to the Global system
            gx = lx * cos_a + ly * sin_a
            gy = -lx * sin_a + ly * cos_a
            
            # Score the alignment with the target screen direction
            score = (gx * tx) + (gy * ty)
            
            if score > max_score:
                max_score = score
                best_dx = gx
                best_dy = gy

        pads = self.footprint.definition.pads
        
        for pad in pads:
            if self.unused_pad:
                net_name = pad.net.name.lower()
                if net_name == "" or "unconnected" in net_name:
                    continue

            # Calculate new coordinates (Rounded to nanometers)
            final_x = clean_nm(pad.position.x + best_dx)
            final_y = clean_nm(pad.position.y + best_dy)
            point = Vector2.from_xy(final_x, final_y)

            track = TrackData(
                width = self.track.width,
                layer = self.track.layer,
                net = pad.net,
                start = pad.position,
                end = point
            )

            via = ViaData(
                via_type = self.via.via_type,
                via_diameter = self.via.via_diameter,
                via_hole = self.via.via_hole,
                start_layer = self.via.start_layer,
                end_layer = self.via.end_layer,
                net = pad.net,
                position = point
            )
            items.append(add_track(track))
            items.append(add_via(via))

        self.items = self.board.create_items(items)
        self.board.add_to_selection(self.items)

    def fanout_bga_xpattern(self):
        """
        X-Pattern (Swirl) Fanout function:
        Creates a Clockwise or Counterclockwise swirl effect.
        """
        items: List[Union[Via, Track]] = []
        angle_rad = self.footprint.orientation.to_radians()
        px, py, is_stag = get_pitch_and_stagger_info(self.footprint)
        
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)
        
        cx = clean_nm(self.footprint.position.x)
        cy = clean_nm(self.footprint.position.y)
            
        pads = self.footprint.definition.pads
        
        for pad in pads:
            if self.unused_pad:
                net_name = pad.net.name.lower()
                if net_name == "" or "unconnected" in net_name:
                    continue

            # 1. Vector from Center -> Pad (Global System)
            out_gx = clean_nm(pad.position.x) - cx
            out_gy = clean_nm(pad.position.y) - cy
            
            # 2. Rotate this vector to the Local system
            lx_pad = out_gx * cos_a - out_gy * sin_a
            ly_pad = out_gx * sin_a + out_gy * cos_a

            # Normalize the ratio
            nx = lx_pad / px if px != 0 else 0
            ny = ly_pad / py if py != 0 else 0

            # 3. Determine the Triangular Region of the Pad
            # FIX HERE: Use >= so pads lying exactly on the diagonal 
            # are decisively assigned to the RIGHT or LEFT region.
            if abs(nx) >= abs(ny):
                region = 'RIGHT' if nx >= 0 else 'LEFT'
            else:
                region = 'BOTTOM' if ny >= 0 else 'TOP'
                
            # 4. Assign CORRECT Local Offset to create a continuous swirl flow (No overlap)
            lx, ly = 0, 0
            is_clockwise = (self.direction == 'Counterclock') 
            
            if not is_stag:
                # BGA Square Grid
                if is_clockwise:
                    if region == 'TOP':      lx, ly =  px/2, -py/2  # Up-Right
                    elif region == 'RIGHT':  lx, ly =  px/2,  py/2  # Down-Right
                    elif region == 'BOTTOM': lx, ly = -px/2,  py/2  # Down-Left
                    elif region == 'LEFT':   lx, ly = -px/2, -py/2  # Up-Left
                else: # Counter-Clockwise
                    if region == 'TOP':      lx, ly = -px/2, -py/2  # Up-Left
                    elif region == 'RIGHT':  lx, ly =  px/2, -py/2  # Up-Right
                    elif region == 'BOTTOM': lx, ly =  px/2,  py/2  # Down-Right
                    elif region == 'LEFT':   lx, ly = -px/2,  py/2  # Down-Left
            else:
                # BGA Staggered
                if is_clockwise:
                    if region == 'TOP':      lx, ly =  px/2, 0      
                    elif region == 'RIGHT':  lx, ly =  0,    py/2   
                    elif region == 'BOTTOM': lx, ly = -px/2, 0      
                    elif region == 'LEFT':   lx, ly =  0,   -py/2   
                else:
                    if region == 'TOP':      lx, ly = -px/2, 0      
                    elif region == 'RIGHT':  lx, ly =  0,   -py/2   
                    elif region == 'BOTTOM': lx, ly =  px/2, 0      
                    elif region == 'LEFT':   lx, ly =  0,    py/2   

            # 5. Rotate Local Offset to Global Offset
            best_dx = lx * cos_a + ly * sin_a
            best_dy = -lx * sin_a + ly * cos_a
            
            # 6. Calculate target coordinates
            dest_x = clean_nm(pad.position.x + best_dx)
            dest_y = clean_nm(pad.position.y + best_dy)
            point = Vector2.from_xy(dest_x, dest_y)

            track = TrackData(
                width = self.track.width,
                layer = self.track.layer,
                net = pad.net,
                start = pad.position,
                end = point
            )

            via = ViaData(
                via_type = self.via.via_type,
                via_diameter = self.via.via_diameter,
                via_hole = self.via.via_hole,
                start_layer = self.via.start_layer,
                end_layer = self.via.end_layer,
                net = pad.net,
                position = point
            )
            items.append(add_track(track))
            items.append(add_via(via))

        self.items = self.board.create_items(items)
        self.board.add_to_selection(self.items)

    def fanout_bga_staggered(self):
        print("fanout_staggered")
        """
        Orthogonal Fanout function (Horizontal / Vertical):
        - Supports both Square Grid and Staggered ICs.
        - Horizontal: Vias are placed horizontally, alternating Left/Right row by row.
        - Vertical: Vias are placed vertically, alternating Up/Down column by column.
        """
        items: List[Union[Via, Track]] = []
        angle_rad = self.footprint.orientation.to_radians()
        px, py, is_stag = get_pitch_and_stagger_info(self.footprint)
        
        # Trigonometric formula
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)
        
        # Center of the IC
        cx = clean_nm(self.footprint.position.x)
        cy = clean_nm(self.footprint.position.y)
            
        pads = self.footprint.definition.pads
        
        is_horizontal = (self.alignment == 'Horizontal')
        
        for pad in pads:
            if self.unused_pad:
                net_name = pad.net.name.lower()
                if net_name == "" or "unconnected" in net_name:
                    continue

            # 1. Vector from Center -> Pad (Global System)
            out_gx = clean_nm(pad.position.x) - cx
            out_gy = clean_nm(pad.position.y) - cy
            
            # 2. Rotate this vector to the Local system
            lx_pad = out_gx * cos_a - out_gy * sin_a
            ly_pad = out_gx * sin_a + out_gy * cos_a

            lx, ly = 0, 0
            
            # 3. Smart Alternating algorithm
            if is_horizontal:
                # HORIZONTAL MODE
                if py != 0:
                    # If staggered, rows interleave by half a pitch (py/2)
                    row_step = (py / 2.0) if is_stag else py
                    row_idx = int(round(ly_pad / row_step))
                else:
                    row_idx = 0
                    
                # Even rows go Right (+px/2), odd rows go Left (-px/2)
                if row_idx % 2 == 0:
                    lx = px / 2.0
                else:
                    lx = -px / 2.0
            else:
                # VERTICAL MODE
                if px != 0:
                    # If staggered, columns interleave by half a pitch (px/2)
                    col_step = (px / 2.0) if is_stag else px
                    col_idx = int(round(lx_pad / col_step))
                else:
                    col_idx = 0
                    
                # Even columns go Up (-py/2), odd columns go Down (+py/2)
                # Note: KiCad's Y axis points downwards
                if col_idx % 2 == 0:
                    ly = -py / 2.0
                else:
                    ly = py / 2.0

            # 4. Rotate Local Offset to Global Offset
            best_dx = lx * cos_a + ly * sin_a
            best_dy = -lx * sin_a + ly * cos_a
            
            # 5. Calculate target coordinates
            dest_x = clean_nm(pad.position.x + best_dx)
            dest_y = clean_nm(pad.position.y + best_dy)
            point = Vector2.from_xy(dest_x, dest_y)

            track = TrackData(
                width = self.track.width,
                layer = self.track.layer,
                net = pad.net,
                start = pad.position,
                end = point
            )

            via = ViaData(
                via_type = self.via.via_type,
                via_diameter = self.via.via_diameter,
                via_hole = self.via.via_hole,
                start_layer = self.via.start_layer,
                end_layer = self.via.end_layer,
                net = pad.net,
                position = point
            )
            items.append(add_track(track))
            items.append(add_via(via))

        self.items = self.board.create_items(items)
        self.board.add_to_selection(self.items)
    
    # SOIC/QFN
    def get_peripheral_pitch(self):
        """
        Calculate specialized Pitch for peripheral ICs (SOP, QFP, QFN).
        Uses the method of physically rotating the IC to 0 degrees to calculate coordinates most accurately.
        """
        # 1. Save the initial rotation angle
        original_angle = self.footprint.orientation
        
        try:
            # 2. Physically rotate the IC to 0 degrees
            if original_angle.degrees != 0.0:
                self.footprint.orientation = Angle.from_degrees(0.0)
            
            # At this point, the IC is upright. The Center and Pads have been updated by KiCad.
            cx = clean_nm(self.footprint.position.x)
            cy = clean_nm(self.footprint.position.y)
            
            pads = self.footprint.definition.pads
            
            local_coords = []
            
            for pad in pads:
                # Subtract the center to get relative coordinates (No sin/cos needed since angle is 0)
                lx = clean_nm(pad.position.x) - cx
                ly = clean_nm(pad.position.y) - cy
                
                # Skip the Thermal Pad in the exact center (distance from center > 0.2mm)
                if abs(lx) > 200000 or abs(ly) > 200000:
                    local_coords.append((lx, ly))
                    
            if len(local_coords) < 2:
                return 0, 0

            # 10um Tolerance
            TOLERANCE = 10000
            
            px = float('inf')
            py = float('inf')

            # 3. Find the shortest distance between pads on the SAME EDGE
            for i in range(len(local_coords)):
                for j in range(i + 1, len(local_coords)):
                    lx1, ly1 = local_coords[i]
                    lx2, ly2 = local_coords[j]

                    # If 2 pads are on the TOP or BOTTOM edge (Same Y)
                    if abs(ly1 - ly2) < TOLERANCE:
                        dist = abs(lx1 - lx2)
                        if TOLERANCE < dist < px:
                            px = dist

                    # If 2 pads are on the LEFT or RIGHT edge (Same X)
                    if abs(lx1 - lx2) < TOLERANCE:
                        dist = abs(ly1 - ly2)
                        if TOLERANCE < dist < py:
                            py = dist

            if px == float('inf'): px = 0
            if py == float('inf'): py = 0

            # If it's a 2-row IC (SOP), balance px and py
            if px == 0 and py > 0: px = py
            if py == 0 and px > 0: py = px

            return int(round(px)), int(round(py))
            
        finally:
            # 4. FAILSAFE: Whether the code succeeds or errors out,
            # always return the IC to its original rotation.
            if self.footprint.orientation.degrees != original_angle.degrees:
                self.footprint.orientation = original_angle

    def detect_ic_shape(self):
        """
        Detect IC shape: 2-SIDED_H (Vertical SOP), 2-SIDED_V (Horizontal SOP), or 4-SIDED (QFP)
        Optimized: Physically rotates the IC to 0 degrees to completely eliminate trigonometric calculations (sin/cos).
        """
        original_angle = self.footprint.orientation
        
        try:
            # 1. Rotate IC to 0 degrees so pads align straight along X, Y axes
            if original_angle.degrees != 0.0:
                self.footprint.orientation = Angle.from_degrees(0.0)
                
            cx = clean_nm(self.footprint.position.x)
            cy = clean_nm(self.footprint.position.y)
            pads = self.footprint.definition.pads
            
            local_xs = []
            local_ys = []
            
            for pad in pads:
                # 2. Get relative coordinates extremely simply, no sin/cos needed
                lx = clean_nm(pad.position.x) - cx
                ly = clean_nm(pad.position.y) - cy
                
                # Skip Thermal Pad in the exact center (further than 0.1mm from center)
                if abs(lx) > 100000 or abs(ly) > 100000: 
                    local_xs.append(lx)
                    local_ys.append(ly)
                    
            if not local_xs: 
                return 'UNKNOWN'

            TOLERANCE = 100000 
            
            # 3. Axis counting algorithm (Kept as is)
            def count_unique_lines(coords):
                if not coords: return 0
                sorted_c = sorted(coords)
                count = 1
                base = sorted_c[0]
                for c in sorted_c[1:]:
                    if c - base > TOLERANCE:
                        count += 1
                        base = c
                return count

            unique_x_lines = count_unique_lines(local_xs)
            unique_y_lines = count_unique_lines(local_ys)

            if unique_x_lines <= 2 and unique_y_lines > 2:
                return '2-SIDED_H'
            elif unique_y_lines <= 2 and unique_x_lines > 2:
                return '2-SIDED_V'
            elif unique_x_lines <= 2 and unique_y_lines <= 2:
                span_x = max(local_xs) - min(local_xs)
                span_y = max(local_ys) - min(local_ys)
                return '2-SIDED_H' if span_x >= span_y else '2-SIDED_V'
            else:
                return '4-SIDED'
                
        finally:
            # 4. FAILSAFE: Always return IC to the old rotation angle regardless of the situation
            if self.footprint.orientation.degrees != original_angle.degrees:
                self.footprint.orientation = original_angle
    
    def _prepare_soic_qfn_data(self):
        """Helper function: Prepare data and classify pads into 4 edges."""
        angle_rad = self.footprint.orientation.to_radians()
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)
        
        px, py = self.get_peripheral_pitch()
        valid_pitches = [p for p in (px, py) if p > 0]
        ic_pitch = min(valid_pitches) if valid_pitches else 500000
        
        cx = clean_nm(self.footprint.position.x)
        cy = clean_nm(self.footprint.position.y)
        pads = self.footprint.definition.pads
        ic_shape = self.detect_ic_shape()
        
        edges: Dict[str, List[Tuple[any, float, float]]] = {
            'LEFT': [], 'RIGHT': [], 'TOP': [], 'BOTTOM': []
        }
        
        local_pads = []
        max_x, max_y = 0, 0
        for pad in pads:
            out_gx = clean_nm(pad.position.x) - cx
            out_gy = clean_nm(pad.position.y) - cy
            lx = out_gx * cos_a - out_gy * sin_a
            ly = out_gx * sin_a + out_gy * cos_a
            local_pads.append((pad, lx, ly))
            if abs(lx) > max_x: max_x = abs(lx)
            if abs(ly) > max_y: max_y = abs(ly)

        margin_x, margin_y = max_x * 0.85, max_y * 0.85

        for pad, lx_pad, ly_pad in local_pads:
            if abs(lx_pad) < margin_x and abs(ly_pad) < margin_y: continue
            edge = ''
            if ic_shape == '2-SIDED_H': edge = 'RIGHT' if lx_pad > 0 else 'LEFT'
            elif ic_shape == '2-SIDED_V': edge = 'BOTTOM' if ly_pad > 0 else 'TOP'
            else: 
                if abs(lx_pad) >= abs(ly_pad): edge = 'RIGHT' if lx_pad > 0 else 'LEFT'
                else: edge = 'BOTTOM' if ly_pad > 0 else 'TOP'
            if edge: edges[edge].append((pad, lx_pad, ly_pad))

        spread_factor = 1.0 if ic_shape != '4-SIDED' else 0.25
        base_stub = self.fanout_length
        stagger_gap = self.stagger_gap
        effective_via_pitch = self.via_pitch if self.via_pitch > 0 else ic_pitch

        return edges, ic_pitch, spread_factor, base_stub, stagger_gap, effective_via_pitch, cos_a, sin_a

    def fanout_soic_linear_escape(self):
        edges, ic_pitch, _, base_stub, _, _, cos_a, sin_a = self._prepare_soic_qfn_data()
        items: List[Union[Via, Track]] = []

        for edge, pad_list in edges.items():
            pad_list: List[Tuple[Pad, float, float]]
            if not pad_list: continue
            if edge in ['LEFT', 'RIGHT']: pad_list.sort(key=lambda item: item[2])
            else: pad_list.sort(key=lambda item: item[1])

            for pad_index, (pad, lx_pad, ly_pad) in enumerate(pad_list):
                # --- SKIP UNCONNECTED PADS ---
                if self.unused_pad:
                    net_name = pad.net.name.lower()
                    if net_name == "" or "unconnected" in net_name: continue

                p1_local_x = base_stub
                p1_local_y = 0
                via_local_x = base_stub
                via_local_y = 0
                
                # Calculate segments
                p2_local_x = via_local_x
                p2_local_y = 0
                p3_local_x = via_local_x
                p3_local_y = 0

                # Direction & Rotate & Draw
                dir_m = -1.0 if self.direction == 'Inside' else 1.0
                if self.direction == 'Both sides': dir_m = 1.0 if pad_index % 2 == 0 else -1.0
                
                p1_local_x *= dir_m; p2_local_x *= dir_m; p3_local_x *= dir_m; via_local_x *= dir_m
                
                lx1, ly1, lx2, ly2, lx3, ly3 = 0,0,0,0,0,0
                if edge == 'RIGHT': lx1, ly1 = p1_local_x, p1_local_y; lx2, ly2 = p2_local_x, p2_local_y; lx3, ly3 = p3_local_x, p3_local_y
                elif edge == 'LEFT': lx1, ly1 = -p1_local_x, p1_local_y; lx2, ly2 = -p2_local_x, p2_local_y; lx3, ly3 = -p3_local_x, p3_local_y
                elif edge == 'BOTTOM': lx1, ly1 = p1_local_y, p1_local_x; lx2, ly2 = p2_local_y, p2_local_x; lx3, ly3 = p3_local_y, p3_local_x
                elif edge == 'TOP': lx1, ly1 = p1_local_y, -p1_local_x; lx2, ly2 = p2_local_y, -p2_local_x; lx3, ly3 = p3_local_y, -p3_local_x

                g_p1_x, g_p1_y = to_global(lx1, ly1, pad.position, cos_a, sin_a)
                
                items.append(add_track(TrackData(self.track.width, self.track.layer, pad.net, pad.position, Vector2.from_xy(g_p1_x, g_p1_y))))
                items.append(add_via(ViaData(self.via.via_type, self.via.via_diameter, self.via.via_hole, self.via.start_layer, self.via.end_layer, pad.net, Vector2.from_xy(g_p1_x, g_p1_y))))

        self.items = self.board.create_items(items)
        self.board.add_to_selection(self.items)

    def fanout_soic_staggered_linear(self):
        edges, ic_pitch, _, base_stub, stagger_gap, _, cos_a, sin_a = self._prepare_soic_qfn_data()
        items: List[Union[Via, Track]] = []

        for edge, pad_list in edges.items():
            pad_list: List[Tuple[Pad, float, float]]
            if not pad_list: continue
            if edge in ['LEFT', 'RIGHT']: pad_list.sort(key=lambda item: item[2])
            else: pad_list.sort(key=lambda item: item[1])

            for pad_index, (pad, lx_pad, ly_pad) in enumerate(pad_list):
                # --- SKIP UNCONNECTED PADS ---
                if self.unused_pad:
                    net_name = pad.net.name.lower()
                    if net_name == "" or "unconnected" in net_name: continue

                via_local_x = base_stub + stagger_gap if pad_index % 2 != 0 else base_stub
                p1_local_x = via_local_x
                p1_local_y = 0
                via_local_y = 0

                # Calculate segments
                p2_local_x = via_local_x
                p2_local_y = 0
                p3_local_x = via_local_x
                p3_local_y = 0

                # Direction & Rotate & Draw
                dir_m = -1.0 if self.direction == 'Inside' else 1.0
                if self.direction == 'Both sides': dir_m = 1.0 if pad_index % 2 == 0 else -1.0
                
                p1_local_x *= dir_m; p2_local_x *= dir_m; p3_local_x *= dir_m; via_local_x *= dir_m
                
                lx1, ly1, lx2, ly2, lx3, ly3 = 0,0,0,0,0,0
                if edge == 'RIGHT': lx1, ly1 = p1_local_x, p1_local_y; lx2, ly2 = p2_local_x, p2_local_y; lx3, ly3 = p3_local_x, p3_local_y
                elif edge == 'LEFT': lx1, ly1 = -p1_local_x, p1_local_y; lx2, ly2 = -p2_local_x, p2_local_y; lx3, ly3 = -p3_local_x, p3_local_y
                elif edge == 'BOTTOM': lx1, ly1 = p1_local_y, p1_local_x; lx2, ly2 = p2_local_y, p2_local_x; lx3, ly3 = p3_local_y, p3_local_x
                elif edge == 'TOP': lx1, ly1 = p1_local_y, -p1_local_x; lx2, ly2 = p2_local_y, -p2_local_x; lx3, ly3 = p3_local_y, -p3_local_x

                g_p1_x, g_p1_y = to_global(lx1, ly1, pad.position, cos_a, sin_a)
                
                items.append(add_track(TrackData(self.track.width, self.track.layer, pad.net, pad.position, Vector2.from_xy(g_p1_x, g_p1_y))))
                items.append(add_via(ViaData(self.via.via_type, self.via.via_diameter, self.via.via_hole, self.via.start_layer, self.via.end_layer, pad.net, Vector2.from_xy(g_p1_x, g_p1_y))))

        self.items = self.board.create_items(items)
        self.board.add_to_selection(self.items)

    def fanout_soic_fan_escape(self):
        edges, ic_pitch, spread_factor, base_stub, _, effective_via_pitch, cos_a, sin_a = self._prepare_soic_qfn_data()
        items: List[Union[Via, Track]] = []
        safe_stub = ic_pitch * 1.5 

        for edge, pad_list in edges.items():
            pad_list: List[Tuple[Pad, float, float]]
            if not pad_list: continue
            
            if edge in ['LEFT', 'RIGHT']: 
                pad_list.sort(key=lambda item: item[2])
                pad_coords = [item[2] for item in pad_list]
            else: 
                pad_list.sort(key=lambda item: item[1])
                pad_coords = [item[1] for item in pad_list]
                
            mid_idx = (len(pad_list) - 1) / 2.0
            mid_coord = (pad_coords[0] + pad_coords[-1]) / 2.0

            for pad_index, (pad, lx_pad, ly_pad) in enumerate(pad_list):
                # --- SKIP UNCONNECTED PADS ---
                if self.unused_pad:
                    net_name = pad.net.name.lower()
                    if net_name == "" or "unconnected" in net_name: continue

                target_coord = mid_coord + (pad_index - mid_idx) * effective_via_pitch * spread_factor
                via_local_y = target_coord - pad_coords[pad_index]
                via_local_x = base_stub
                p1_local_x = safe_stub
                p1_local_y = 0

                # Calculate segments
                if via_local_y != 0:
                    p2_local_x = p1_local_x + abs(via_local_y)
                    p2_local_y = via_local_y
                else:
                    p2_local_x = p1_local_x
                    p2_local_y = 0

                if p2_local_x > via_local_x: # Fix Overshoot
                    p2_local_x = via_local_x
                    p1_local_x = max(0, via_local_x - abs(via_local_y))
                    
                p3_local_x = via_local_x
                p3_local_y = via_local_y

                # Direction & Rotate & Draw
                dir_m = -1.0 if self.direction == 'Inside' else 1.0
                if self.direction == 'Both sides': dir_m = 1.0 if pad_index % 2 == 0 else -1.0
                p1_local_x *= dir_m; p2_local_x *= dir_m; p3_local_x *= dir_m; via_local_x *= dir_m
                
                lx1, ly1, lx2, ly2, lx3, ly3 = 0,0,0,0,0,0
                if edge == 'RIGHT': lx1, ly1 = p1_local_x, p1_local_y; lx2, ly2 = p2_local_x, p2_local_y; lx3, ly3 = p3_local_x, p3_local_y
                elif edge == 'LEFT': lx1, ly1 = -p1_local_x, p1_local_y; lx2, ly2 = -p2_local_x, p2_local_y; lx3, ly3 = -p3_local_x, p3_local_y
                elif edge == 'BOTTOM': lx1, ly1 = p1_local_y, p1_local_x; lx2, ly2 = p2_local_y, p2_local_x; lx3, ly3 = p3_local_y, p3_local_x
                elif edge == 'TOP': lx1, ly1 = p1_local_y, -p1_local_x; lx2, ly2 = p2_local_y, -p2_local_x; lx3, ly3 = p3_local_y, -p3_local_x

                v_p1 = Vector2.from_xy(*to_global(lx1, ly1, pad.position, cos_a, sin_a))
                v_p2 = Vector2.from_xy(*to_global(lx2, ly2, pad.position, cos_a, sin_a))
                v_p3 = Vector2.from_xy(*to_global(lx3, ly3, pad.position, cos_a, sin_a))
                
                items.append(add_track(TrackData(self.track.width, self.track.layer, pad.net, pad.position, v_p1)))
                if via_local_y != 0: items.append(add_track(TrackData(self.track.width, self.track.layer, pad.net, v_p1, v_p2)))
                if abs(p3_local_x) > abs(p2_local_x): items.append(add_track(TrackData(self.track.width, self.track.layer, pad.net, v_p2, v_p3)))
                items.append(add_via(ViaData(self.via.via_type, self.via.via_diameter, self.via.via_hole, self.via.start_layer, self.via.end_layer, pad.net, v_p3)))

        self.items = self.board.create_items(items)
        self.board.add_to_selection(self.items)

    def fanout_soic_staggered_fan(self):
        edges, ic_pitch, spread_factor, base_stub, stagger_gap, effective_via_pitch, cos_a, sin_a = self._prepare_soic_qfn_data()
        items: List[Union[Via, Track]] = []
        safe_stub = ic_pitch * 1.5 

        for edge, pad_list in edges.items():
            pad_list: List[Tuple[Pad, float, float]]
            if not pad_list: continue
            
            if edge in ['LEFT', 'RIGHT']: 
                pad_list.sort(key=lambda item: item[2])
                pad_coords = [item[2] for item in pad_list]
            else: 
                pad_list.sort(key=lambda item: item[1])
                pad_coords = [item[1] for item in pad_list]
                
            mid_idx = (len(pad_list) - 1) / 2.0
            mid_coord = (pad_coords[0] + pad_coords[-1]) / 2.0

            for pad_index, (pad, lx_pad, ly_pad) in enumerate(pad_list):
                # --- SKIP UNCONNECTED PADS ---
                if self.unused_pad:
                    net_name = pad.net.name.lower()
                    if net_name == "" or "unconnected" in net_name: continue

                target_coord = mid_coord + (pad_index - mid_idx) * effective_via_pitch * spread_factor
                via_local_y = target_coord - pad_coords[pad_index]
                
                via_local_x = base_stub + stagger_gap if pad_index % 2 != 0 else base_stub
                p1_local_x = safe_stub + stagger_gap * 0.5 if pad_index % 2 != 0 else safe_stub
                p1_local_y = 0

                # Calculate segments
                if via_local_y != 0:
                    p2_local_x = p1_local_x + abs(via_local_y)
                    p2_local_y = via_local_y
                else:
                    p2_local_x = p1_local_x
                    p2_local_y = 0

                if p2_local_x > via_local_x: # Fix Overshoot
                    p2_local_x = via_local_x
                    p1_local_x = max(0, via_local_x - abs(via_local_y))

                p3_local_x = via_local_x
                p3_local_y = via_local_y

                # Direction & Rotate & Draw
                dir_m = -1.0 if self.direction == 'Inside' else 1.0
                if self.direction == 'Both sides': dir_m = 1.0 if pad_index % 2 == 0 else -1.0
                p1_local_x *= dir_m; p2_local_x *= dir_m; p3_local_x *= dir_m; via_local_x *= dir_m
                
                lx1, ly1, lx2, ly2, lx3, ly3 = 0,0,0,0,0,0
                if edge == 'RIGHT': lx1, ly1 = p1_local_x, p1_local_y; lx2, ly2 = p2_local_x, p2_local_y; lx3, ly3 = p3_local_x, p3_local_y
                elif edge == 'LEFT': lx1, ly1 = -p1_local_x, p1_local_y; lx2, ly2 = -p2_local_x, p2_local_y; lx3, ly3 = -p3_local_x, p3_local_y
                elif edge == 'BOTTOM': lx1, ly1 = p1_local_y, p1_local_x; lx2, ly2 = p2_local_y, p2_local_x; lx3, ly3 = p3_local_y, p3_local_x
                elif edge == 'TOP': lx1, ly1 = p1_local_y, -p1_local_x; lx2, ly2 = p2_local_y, -p2_local_x; lx3, ly3 = p3_local_y, -p3_local_x

                v_p1 = Vector2.from_xy(*to_global(lx1, ly1, pad.position, cos_a, sin_a))
                v_p2 = Vector2.from_xy(*to_global(lx2, ly2, pad.position, cos_a, sin_a))
                v_p3 = Vector2.from_xy(*to_global(lx3, ly3, pad.position, cos_a, sin_a))
                
                items.append(add_track(TrackData(self.track.width, self.track.layer, pad.net, pad.position, v_p1)))
                if via_local_y != 0: items.append(add_track(TrackData(self.track.width, self.track.layer, pad.net, v_p1, v_p2)))
                if abs(p3_local_x) > abs(p2_local_x): items.append(add_track(TrackData(self.track.width, self.track.layer, pad.net, v_p2, v_p3)))
                items.append(add_via(ViaData(self.via.via_type, self.via.via_diameter, self.via.via_hole, self.via.start_layer, self.via.end_layer, pad.net, v_p3)))

        self.items = self.board.create_items(items)
        self.board.add_to_selection(self.items)
                
def clean_nm(value, grid=100):
    """
    Round nanometers to eliminate small floating-point inaccuracies.
    
    :param value: Value to be rounded (49000002, -47999998,...)
    :param grid: Resolution grid (default 100nm = 0.0001mm)
                 If the error is larger, increase grid to 1000 (1um)
    :return: Rounded integer (int)
    """
    return int(round(value / grid) * grid)

def to_global(lx: float, ly: float, pad_position: Vector2, cos_a: float, sin_a: float) -> tuple[int, int]:
    """
    Helper function: Convert Local coordinates (lx, ly) to Global coordinates on the KiCad board
    based on the IC's rotation angle (cos_a, sin_a) and the Pad's coordinates.
    """
    dx = lx * cos_a + ly * sin_a
    dy = -lx * sin_a + ly * cos_a
    return clean_nm(pad_position.x + dx), clean_nm(pad_position.y + dy)

# https://www.youtube.com/watch?v=yHuuwNH7QxU
