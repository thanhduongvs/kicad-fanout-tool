from typing import Optional, Sequence
from kipy import KiCad
from kipy.board import Board, BoardLayer, BoardOriginType
from kipy.board_types import FootprintInstance, Field
from kipy.board_types import Field
from kipy.board_types import Net
from kipy.geometry import Vector2
from collections import defaultdict
from kipy.board_types import Track, Via, Pad, DrillProperties
from kipy.proto.board.board_types_pb2 import ViaType, PadStackType, BoardLayer
from kipy.util.units import from_mm
from dataclasses import dataclass
from typing import List, Union, Dict, Tuple
from kipy.geometry import Angle
from utils import ViaData, TrackData, add_via, add_track, get_pitch_and_stagger_info
import math

class Fanout:
    def __init__(self, footprint: FootprintInstance, board: Board,
                 via: ViaData, track: TrackData, package: str,
                 alignment: str, direction: str, unused_pad: bool):
        self.board = board
        self.footprint = footprint
        self.track = track
        self.via = via
        self.package = package
        self.alignment = alignment
        self.direction = direction
        self.x_dir = 1
        self.y_dir = 1
        print(f"package: {package}")
        print(f"alignment: {alignment}")
        print(f"direction: {direction}")

    def fanout(self):
        if self.package == "BGA":
            print(f"package0: {self.package}")
            match self.alignment:
                case "Quadrant":
                    self.fanout_quadrant()
                case "Diagonal":
                    self.fanout_diagonal()
                case "X-pattern":
                    self.fanout_xpattern()
                case "Staggered":
                    self.fanout_staggered()
        else:
            print(f"package1: {self.package}")
            print(self.detect_ic_shape())
            px, py = self.get_peripheral_pitch()
            print(f"x: {px}, y: {py}")
            self.fanout_peripheral()
    
    def fanout_quadrant(self):
        items: List[Union[Via, Track]] = []
        angle_rad = self.footprint.orientation.to_radians()
        #center = self.footprint.position
        px, py, is_stag = get_pitch_and_stagger_info(self.footprint)
        
        # 1. Tạo tập 4 ứng viên Offset (Hệ Local chưa xoay)
        if not is_stag:
            # Grid vuông: 4 khe nằm ở 4 góc chéo
            local_candidates = [
                (-px/2, -py/2), ( px/2, -py/2),
                ( px/2,  py/2), (-px/2,  py/2)
            ]
        else:
            # So le (Staggered): 4 khe nằm ở giữa các pad ngang/dọc
            local_candidates = [
                (-px/2, 0), ( px/2, 0),
                ( 0, -py/2), ( 0,  py/2)
            ]
            
        # Công thức xoay chuẩn KiCad
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)

        # Lưu trữ 4 ứng viên ĐÃ XOAY SẴN ra hệ Global
        global_candidates = []
        for lx, ly in local_candidates:
            gx = lx * cos_a + ly * sin_a
            gy = -lx * sin_a + ly * cos_a
            global_candidates.append((gx, gy))
        
        #min_x, max_x, min_y, max_y = self.get_xy_extremum(angle_rad)
        
        # Tâm của IC
        cx = clean_nm(self.footprint.position.x)
        cy = clean_nm(self.footprint.position.y)

        pads = self.footprint.definition.pads
        
        for pad in pads:
            # Bỏ qua pad không kết nối (nếu cần)
            #if not pad.net or pad.net.name == "": continue

            # Tính tọa độ mới (Đã làm tròn nanomet)
            #final_x = clean_nm(pad.position.x + best_dx)
            #final_y = clean_nm(pad.position.y + best_dy)
            #point = Vector2.from_xy(final_x, final_y)
            # 2. Tạo Vector Tỏa Ra Ngoài (Từ Tâm -> Pad)
            out_gx = clean_nm(pad.position.x) - cx
            out_gy = clean_nm(pad.position.y )- cy

            target_gx = out_gx * 1.01 + 0.001
            target_gy = out_gy
            
            best_dx = 0
            best_dy = 0
            max_score = -float('inf')
            
            # Vòng lặp nhỏ này chỉ dùng toàn phép nhân/cộng cơ bản (rất nhanh)
            # Dùng list global_candidates đã tính sẵn ở trên
            for gx, gy in global_candidates:
                score = (gx * target_gx) + (gy * target_gy)
                
                if score > max_score:
                    max_score = score
                    best_dx = gx
                    best_dy = gy
                    
            # Cộng Offset
            dest_x = clean_nm(pad.position.x + best_dx)
            dest_y = clean_nm(pad.position.y + best_dy)
            point = Vector2.from_xy(dest_x, dest_y)

            self.track.net = pad.net
            self.track.start = pad.position
            self.track.end = point
            self.via.net = pad.net
            self.via.position = point
            items.append(add_via(self.via))
            items.append(add_track(self.track))

        # Thêm vào board
        self.board.create_items(items)
        self.board.add_to_selection(items)

    def fanout_diagonal(self):
        """
        Hàm Fanout Diagonal thông minh:
        1. Đảm bảo via nằm chính xác trên đường chéo (hoặc đường ngang/dọc nếu là layout so le).
        2. Tự động chuyển góc và ưu tiên đi ngang (Horizontal Bias) tại các góc 45 độ.
        """
        items: List[Union[Via, Track]] = []
        angle_rad = self.footprint.orientation.to_radians()
        px, py, is_stag = get_pitch_and_stagger_info(self.footprint)
        
        # 1. Xác định Hướng Mục Tiêu trên Màn hình KiCad (Global Target)
        # KiCad: X âm (Trái), Y âm (Lên)
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
            
        # 2. Tạo tập hợp các Ứng viên Offset (Hệ tọa độ Local chưa xoay)
        if not is_stag:
            # Layout Grid Vuông góc: Đi chéo ra 4 góc
            candidates = [
                (-px/2, -py/2), # Local Top-Left
                ( px/2, -py/2), # Local Top-Right
                ( px/2,  py/2), # Local Bottom-Right
                (-px/2,  py/2)  # Local Bottom-Left
            ]
        else:
            # Layout So le (Staggered): Đi thẳng ra 4 khe ngang/dọc
            candidates = [
                (-px/2, 0),     # Local Left
                ( px/2, 0),     # Local Right
                ( 0, -py/2),    # Local Top
                ( 0,  py/2)     # Local Bottom
            ]
            
        # Công thức ma trận xoay (Khử lệch bẻ cong của KiCad)
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)
        
        best_dx = 0
        best_dy = 0
        max_score = -float('inf')
        
        # 3. Tìm ứng viên "Thuận hướng màn hình" nhất
        for lx, ly in candidates:
            # Xoay vector offset ra hệ Global
            gx = lx * cos_a + ly * sin_a
            gy = -lx * sin_a + ly * cos_a
            
            # Chấm điểm độ trùng khớp với hướng màn hình
            score = (gx * tx) + (gy * ty)
            
            if score > max_score:
                max_score = score
                best_dx = gx
                best_dy = gy

        pads = self.footprint.definition.pads
        
        for pad in pads:
            # Bỏ qua pad không kết nối (nếu cần)
            #if not pad.net or pad.net.name == "": continue

            # Tính tọa độ mới (Đã làm tròn nanomet)
            final_x = clean_nm(pad.position.x + best_dx)
            final_y = clean_nm(pad.position.y + best_dy)
            point = Vector2.from_xy(final_x, final_y)

            self.track.net = pad.net
            self.track.start = pad.position
            self.track.end = point
            self.via.net = pad.net
            self.via.position = point
            items.append(add_via(self.via))
            items.append(add_track(self.track))

        # Thêm vào board
        self.board.create_items(items)
        self.board.add_to_selection(items)

    def fanout_xpattern(self):
        """
        Hàm Fanout X-Pattern (Swirl):
        Tạo hiệu ứng xoáy chiều kim đồng hồ (Clockwise) hoặc ngược chiều (Counterclockwise).
        Đã FIX: Đi dây (via) cho toàn bộ các Pad trên đường chéo, không bỏ sót pad nào.
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
            # Bỏ qua pad không kết nối nếu cần
            # if not pad.net or pad.net.name == "": continue

            # 1. Vector từ Tâm -> Pad (Hệ Global)
            out_gx = clean_nm(pad.position.x) - cx
            out_gy = clean_nm(pad.position.y) - cy
            
            # 2. Xoay vector này về hệ Local
            lx_pad = out_gx * cos_a - out_gy * sin_a
            ly_pad = out_gx * sin_a + out_gy * cos_a

            # Chuẩn hóa tỷ lệ 
            nx = lx_pad / px if px != 0 else 0
            ny = ly_pad / py if py != 0 else 0

            # 3. Xác định Vùng Tam Giác (Region) của Pad
            # SỬA Ở ĐÂY: Dùng >= để các pad nằm chính xác trên đường chéo 
            # sẽ được gán vào vùng RIGHT hoặc LEFT một cách dứt khoát.
            if abs(nx) >= abs(ny):
                region = 'RIGHT' if nx >= 0 else 'LEFT'
            else:
                region = 'BOTTOM' if ny >= 0 else 'TOP'
                
            # 4. Gán Offset Local ĐÚNG để tạo dòng chảy xoáy liên tục (Không bị đè)
            lx, ly = 0, 0
            is_clockwise = (self.direction == 'Counterclock') 
            
            if not is_stag:
                # BGA Lưới Vuông (Grid)
                if is_clockwise:
                    if region == 'TOP':      lx, ly =  px/2, -py/2  # Đi lên-phải
                    elif region == 'RIGHT':  lx, ly =  px/2,  py/2  # Đi xuống-phải
                    elif region == 'BOTTOM': lx, ly = -px/2,  py/2  # Đi xuống-trái
                    elif region == 'LEFT':   lx, ly = -px/2, -py/2  # Đi lên-trái
                else: # Counter-Clockwise (Ngược chiều kim đồng hồ)
                    if region == 'TOP':      lx, ly = -px/2, -py/2  # Đi lên-trái
                    elif region == 'RIGHT':  lx, ly =  px/2, -py/2  # Đi lên-phải
                    elif region == 'BOTTOM': lx, ly =  px/2,  py/2  # Đi xuống-phải
                    elif region == 'LEFT':   lx, ly = -px/2,  py/2  # Đi xuống-trái
            else:
                # BGA So le (Staggered)
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

            # 5. Xoay Local Offset ra Global Offset
            best_dx = lx * cos_a + ly * sin_a
            best_dy = -lx * sin_a + ly * cos_a
            
            # 6. Tính tọa độ đích
            dest_x = clean_nm(pad.position.x + best_dx)
            dest_y = clean_nm(pad.position.y + best_dy)
            point = Vector2.from_xy(dest_x, dest_y)

            self.track.net = pad.net
            self.track.start = pad.position
            self.track.end = point
            self.via.net = pad.net
            self.via.position = point
            items.append(add_via(self.via))
            items.append(add_track(self.track))

        # Thêm vào board
        self.board.create_items(items)
        self.board.add_to_selection(items)

    def fanout_staggered(self):
        print("fanout_staggered")
        """
        Hàm Fanout Orthogonal (Ngang / Dọc):
        - Hỗ trợ cả IC Lưới vuông (Grid) và So le (Staggered).
        - Horizontal: Via nằm ngang, luân phiên Trái/Phải theo từng hàng.
        - Vertical: Via nằm dọc, luân phiên Lên/Dưới theo từng cột.
        """
        items: List[Union[Via, Track]] = []
        angle_rad = self.footprint.orientation.to_radians()
        px, py, is_stag = get_pitch_and_stagger_info(self.footprint)
        
        # Công thức lượng giác
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)
        
        # Tâm của IC
        cx = clean_nm(self.footprint.position.x)
        cy = clean_nm(self.footprint.position.y)
            
        pads = self.footprint.definition.pads
        
        is_horizontal = (self.alignment == 'Horizontal')
        
        for pad in pads:
            # Bỏ qua pad không kết nối nếu cần
            # if not pad.net or pad.net.name == "": continue

            # 1. Vector từ Tâm -> Pad (Hệ Global)
            out_gx = clean_nm(pad.position.x) - cx
            out_gy = clean_nm(pad.position.y) - cy
            
            # 2. Xoay vector này về hệ Local
            lx_pad = out_gx * cos_a - out_gy * sin_a
            ly_pad = out_gx * sin_a + out_gy * cos_a

            lx, ly = 0, 0
            
            # 3. Thuật toán Luân phiên (Alternating) thông minh
            if is_horizontal:
                # CHẾ ĐỘ NGANG
                if py != 0:
                    # Nếu so le (Staggered), các hàng đan xen nhau cách một nửa pitch (py/2)
                    row_step = (py / 2.0) if is_stag else py
                    row_idx = int(round(ly_pad / row_step))
                else:
                    row_idx = 0
                    
                # Hàng chẵn đi sang Phải (+px/2), hàng lẻ đi sang Trái (-px/2)
                if row_idx % 2 == 0:
                    lx = px / 2.0
                else:
                    lx = -px / 2.0
            else:
                # CHẾ ĐỘ DỌC
                if px != 0:
                    # Nếu so le (Staggered), các cột đan xen nhau cách một nửa pitch (px/2)
                    col_step = (px / 2.0) if is_stag else px
                    col_idx = int(round(lx_pad / col_step))
                else:
                    col_idx = 0
                    
                # Cột chẵn đi Lên trên (-py/2), cột lẻ đi Xuống dưới (+py/2)
                # Chú ý: Trục Y của KiCad hướng xuống dưới
                if col_idx % 2 == 0:
                    ly = -py / 2.0
                else:
                    ly = py / 2.0

            # 4. Xoay Local Offset ra Global Offset
            best_dx = lx * cos_a + ly * sin_a
            best_dy = -lx * sin_a + ly * cos_a
            
            # 5. Tính tọa độ đích
            dest_x = clean_nm(pad.position.x + best_dx)
            dest_y = clean_nm(pad.position.y + best_dy)
            point = Vector2.from_xy(dest_x, dest_y)

            # Vẽ Track
            track = TrackData(self.track)
            track.net = pad.net
            track.start = pad.position
            track.end = point
            items.append(track)

            # Vẽ Via
            via = ViaData(self.via)
            via.net = pad.net
            via.position = point
            items.append(via)

            #items.append(add_via(self.via))
            #items.append(add_track(self.track))

        # Thêm vào board
        self.board.create_items(items)
        self.board.add_to_selection(items)

    def get_peripheral_pitch(self):
        """
        Tính Pitch chuyên biệt cho IC viền (SOP, QFP, QFN).
        Sử dụng phương pháp xoay vật lý IC về 0 độ để tính toán tọa độ chính xác nhất.
        """
        # 1. Lưu lại góc xoay ban đầu
        original_angle = self.footprint.orientation
        
        try:
            # 2. Xoay vật lý IC về 0 độ
            if original_angle.degrees != 0.0:
                self.footprint.orientation = Angle.from_degrees(0.0)
            
            # Lúc này IC đã nằm thẳng đứng. Tâm và các Pad cũng đã được KiCad cập nhật lại.
            cx = clean_nm(self.footprint.position.x)
            cy = clean_nm(self.footprint.position.y)
            
            pads = self.footprint.definition.pads
            
            local_coords = []
            
            for pad in pads:
                # Trừ đi tâm để lấy tọa độ tương đối (Không cần sin/cos nữa vì góc đang là 0)
                lx = clean_nm(pad.position.x) - cx
                ly = clean_nm(pad.position.y) - cy
                
                # Bỏ qua Thermal Pad ở chính giữa tâm (cách tâm > 0.2mm)
                if abs(lx) > 200000 or abs(ly) > 200000:
                    local_coords.append((lx, ly))
                    
            if len(local_coords) < 2:
                return 0, 0

            # Dung sai 10um
            TOLERANCE = 10000
            
            px = float('inf')
            py = float('inf')

            # 3. Tìm khoảng cách ngắn nhất giữa các chân trên CÙNG 1 CẠNH
            for i in range(len(local_coords)):
                for j in range(i + 1, len(local_coords)):
                    lx1, ly1 = local_coords[i]
                    lx2, ly2 = local_coords[j]

                    # Nếu 2 chân cùng nằm trên mép TOP hoặc BOTTOM (Cùng Y)
                    if abs(ly1 - ly2) < TOLERANCE:
                        dist = abs(lx1 - lx2)
                        if TOLERANCE < dist < px:
                            px = dist

                    # Nếu 2 chân cùng nằm trên mép LEFT hoặc RIGHT (Cùng X)
                    if abs(lx1 - lx2) < TOLERANCE:
                        dist = abs(ly1 - ly2)
                        if TOLERANCE < dist < py:
                            py = dist

            if px == float('inf'): px = 0
            if py == float('inf'): py = 0

            # Nếu là IC 2 hàng (SOP), cân bằng px và py
            if px == 0 and py > 0: px = py
            if py == 0 and px > 0: py = px

            return int(round(px)), int(round(py))
            
        finally:
            # 4. CHỐT AN TOÀN: Bất chấp code chạy thành công hay báo lỗi,
            # IC luôn luôn được trả về góc xoay nguyên thủy.
            if self.footprint.orientation.degrees != original_angle.degrees:
                self.footprint.orientation = original_angle

    def detect_ic_shape(self):
        """
        Nhận diện hình dáng IC: 2-SIDED_H (SOP dọc), 2-SIDED_V (SOP ngang), hoặc 4-SIDED (QFP)
        Đã tối ưu: Xoay vật lý IC về 0 độ để loại bỏ hoàn toàn tính toán lượng giác (sin/cos).
        """
        original_angle = self.footprint.orientation
        
        try:
            # 1. Xoay IC về 0 độ để các pad nằm thẳng theo trục X, Y
            if original_angle.degrees != 0.0:
                self.footprint.orientation = Angle.from_degrees(0.0)
                
            cx = clean_nm(self.footprint.position.x)
            cy = clean_nm(self.footprint.position.y)
            pads = self.footprint.definition.pads
            
            local_xs = []
            local_ys = []
            
            for pad in pads:
                # 2. Lấy tọa độ tương đối cực kỳ đơn giản, không cần sin/cos
                lx = clean_nm(pad.position.x) - cx
                ly = clean_nm(pad.position.y) - cy
                
                # Bỏ qua Thermal Pad ở chính giữa tâm (xa tâm hơn 0.1mm)
                if abs(lx) > 100000 or abs(ly) > 100000: 
                    local_xs.append(lx)
                    local_ys.append(ly)
                    
            if not local_xs: 
                return 'UNKNOWN'

            TOLERANCE = 100000 
            
            # 3. Thuật toán đếm trục (Giữ nguyên)
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
            # 4. CHỐT AN TOÀN: Luôn trả IC về góc xoay cũ bất chấp mọi tình huống
            if self.footprint.orientation.degrees != original_angle.degrees:
                self.footprint.orientation = original_angle
    
    def fanout_peripheral(self):
        """
        Hàm Fanout dành riêng cho IC viền (SOP, QFP, QFN).
        Đã Fix Lỗi Đè Pad: Kéo dài đoạn Stub thoát chân (base_stub = pitch * 2.5) 
        và bẻ góc so le để đảm bảo Track luôn cách xa Pad và các Track khác.
        """
        items: List[Union[Via, Track]] = []
        angle_rad = self.footprint.orientation.to_radians()
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)
        
        px, py = self.get_peripheral_pitch()
        valid_pitches = [p for p in (px, py) if p > 0]
        pitch = min(valid_pitches) if valid_pitches else 500000
        
        cx = clean_nm(self.footprint.position.x)
        cy = clean_nm(self.footprint.position.y)
        pads = self.footprint.definition.pads

        ic_shape = self.detect_ic_shape()
        
        edges: Dict[str, List[Tuple[any, float, float]]] = {
            'LEFT': [], 'RIGHT': [], 'TOP': [], 'BOTTOM': []
        }
        
        # --- BƯỚC 1: LỌC EXPOSED PAD (EP) ---
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

        margin_x = max_x * 0.85
        margin_y = max_y * 0.85

        for pad, lx_pad, ly_pad in local_pads:
            edge = ''
            if abs(lx_pad) < margin_x and abs(ly_pad) < margin_y:
                continue

            if ic_shape == '2-SIDED_H': 
                edge = 'RIGHT' if lx_pad > 0 else 'LEFT'
            elif ic_shape == '2-SIDED_V': 
                edge = 'BOTTOM' if ly_pad > 0 else 'TOP'
            else: 
                if abs(lx_pad) >= abs(ly_pad): 
                    edge = 'RIGHT' if lx_pad > 0 else 'LEFT'
                else: 
                    edge = 'BOTTOM' if ly_pad > 0 else 'TOP'
                    
            if edge:
                edges[edge].append((pad, lx_pad, ly_pad))

        # --- GIẢI MÃ MA TRẬN TÊN GỌI ---
        is_multiple_rows = "Staggered" in self.alignment
        is_spreading = "Fan" in self.alignment

        spread_factor = 1.0 if ic_shape != '4-SIDED' else 0.25

        # Tăng khoảng cách thoát Pad lên 2.5 lần pitch để vượt qua chiều dài Pad vật lý
        base_stub = pitch * 2.5 

        # --- BƯỚC 2: TÍNH TOÁN 3 PHÂN ĐOẠN ---
        for edge, pad_list in edges.items():
            if not pad_list: 
                continue
            
            if edge in ['LEFT', 'RIGHT']: 
                pad_list.sort(key=lambda item: item[2])
            else: 
                pad_list.sort(key=lambda item: item[1])
                
            mid_idx = (len(pad_list) - 1) / 2.0
            
            # TÌM X CỦA HÀNG VIA TRONG CÙNG ĐỂ GIÓNG THẲNG
            max_p2_x = 0
            for i in range(len(pad_list)):
                v_y = (i - mid_idx) * pitch * spread_factor if is_spreading else 0
                
                # So le điểm bẻ góc (Outer track đi thẳng dài hơn Inner track 1.5 pitch)
                e_stub = (pitch * 1.5) if (is_multiple_rows and i % 2 != 0) else 0
                p2_x = base_stub + e_stub + abs(v_y)
                
                if p2_x > max_p2_x: 
                    max_p2_x = p2_x
                
            inner_via_x = max_p2_x + pitch * 0.5

            for pad_index, (pad, lx_pad, ly_pad) in enumerate(pad_list):
                
                via_local_y = 0
                if is_spreading:
                    via_local_y = (pad_index - mid_idx) * pitch * spread_factor
                
                # --- PHÂN ĐOẠN 1: Stub thoát Pad (Đã kéo dài và xếp so le) ---
                extra_stub = (pitch * 1.5) if (is_multiple_rows and pad_index % 2 != 0) else 0
                p1_local_x = base_stub + extra_stub
                p1_local_y = 0
                
                # --- PHÂN ĐOẠN 2: Bẻ 45 độ ---
                p2_local_x = p1_local_x + abs(via_local_y)
                p2_local_y = via_local_y
                
                # --- PHÂN ĐOẠN 3: Chạy ngang đến Via ---
                via_local_x = inner_via_x
                if is_multiple_rows and pad_index % 2 != 0:
                    via_local_x += pitch * 2.0 
                    
                p3_local_x = via_local_x
                p3_local_y = via_local_y

                # --- ĐẢO CHIỀU ---
                dir_m = -1.0 if self.direction == 'Inside' else 1.0
                if self.direction == 'Both sides':
                    dir_m = 1.0 if pad_index % 2 == 0 else -1.0
                    
                p1_local_x *= dir_m
                p2_local_x *= dir_m
                p3_local_x *= dir_m
                via_local_x *= dir_m

                # --- GẮN VÀO HỆ LOCAL ---
                lx1, ly1, lx2, ly2, lx3, ly3 = 0,0,0,0,0,0
                if edge == 'RIGHT':
                    lx1, ly1 = p1_local_x, p1_local_y
                    lx2, ly2 = p2_local_x, p2_local_y
                    lx3, ly3 = p3_local_x, p3_local_y
                elif edge == 'LEFT':
                    lx1, ly1 = -p1_local_x, p1_local_y
                    lx2, ly2 = -p2_local_x, p2_local_y
                    lx3, ly3 = -p3_local_x, p3_local_y
                elif edge == 'BOTTOM':
                    lx1, ly1 = p1_local_y, p1_local_x
                    lx2, ly2 = p2_local_y, p2_local_x
                    lx3, ly3 = p3_local_y, p3_local_x
                elif edge == 'TOP':
                    lx1, ly1 = p1_local_y, -p1_local_x
                    lx2, ly2 = p2_local_y, -p2_local_x
                    lx3, ly3 = p3_local_y, -p3_local_x

                # --- XOAY RA GLOBAL ---
                def to_global(lx, ly):
                    dx = lx * cos_a + ly * sin_a
                    dy = -lx * sin_a + ly * cos_a
                    return clean_nm(pad.position.x + dx), clean_nm(pad.position.y + dy)

                g_p1_x, g_p1_y = to_global(lx1, ly1)
                g_p2_x, g_p2_y = to_global(lx2, ly2)
                g_p3_x, g_p3_y = to_global(lx3, ly3)
                
                v_p1 = Vector2.from_xy(g_p1_x, g_p1_y)
                v_p2 = Vector2.from_xy(g_p2_x, g_p2_y)
                v_p3 = Vector2.from_xy(g_p3_x, g_p3_y)

                # --- VẼ LÊN BOARD ---
                # Track 1
                track1 = TrackData(
                    width=self.track.width, layer=self.track.layer,
                    net=pad.net, start=pad.position, end=v_p1
                )
                items.append(add_track(track1))

                # Track 2
                if is_spreading and via_local_y != 0:
                    track2 = TrackData(
                        width=self.track.width, layer=self.track.layer,
                        net=pad.net, start=v_p1, end=v_p2
                    )
                    items.append(add_track(track2))

                # Track 3
                if abs(p3_local_x) > abs(p2_local_x):
                    track3 = TrackData(
                        width=self.track.width, layer=self.track.layer,
                        net=pad.net, start=v_p2, end=v_p3
                    )
                    items.append(add_track(track3))

                # Via
                via = ViaData(
                    via_type=self.via.via_type, via_diameter=self.via.via_diameter,
                    via_hole=self.via.via_hole, start_layer=self.via.start_layer,
                    end_layer=self.via.end_layer, net=pad.net, position=v_p3
                )
                items.append(add_via(via))

        self.board.create_items(items)
        self.board.add_to_selection(items)
                
def clean_nm(value, grid=100):
    """
    Làm tròn số nanomet để loại bỏ sai số nhỏ.
    
    :param value: Giá trị cần làm tròn (49000002, -47999998,...)
    :param grid: Độ phân giải lưới (mặc định 100nm = 0.0001mm)
                 Nếu sai số lớn hơn, hãy tăng grid lên 1000 (1um)
    :return: Số nguyên (int) đã làm tròn
    """
    return int(round(value / grid) * grid)


# https://www.youtube.com/watch?v=yHuuwNH7QxU