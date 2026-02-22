from typing import Optional, Sequence
from kipy import KiCad
from kipy.board import Board, BoardLayer, BoardOriginType
from kipy.board_types import FootprintInstance, Field
from kipy.board_types import Field
from kipy.board_types import Net
from kipy.geometry import Vector2
from collections import defaultdict
from kipy.board_types import Track, Via, PadStack, DrillProperties
from kipy.proto.board.board_types_pb2 import ViaType, PadStackType, BoardLayer
from kipy.util.units import from_mm
from dataclasses import dataclass
from typing import List, Union
from kipy.geometry import Angle
from utils import ViaData, TrackData, add_via, add_track, get_pitch_and_stagger_info
import math

class BGA:
    def __init__(self, footprint: FootprintInstance, board: Board,
                 via: ViaData, track: TrackData,
                 alignment: str, direction: str, unused_pad: bool):
        self.board = board
        self.footprint = footprint
        self.track = track
        self.via = via
        self.alignment = alignment
        self.direction = direction
        self.x_dir = 1
        self.y_dir = 1
        print(f"alignment: {alignment}")
        print(f"direction: {direction}")

    def fanout(self):
        match self.alignment:
            case "Quadrant":
                self.fanout_quadrant()
            case "Diagonal":
                self.fanout_diagonal()
            case "X-pattern":
                self.fanout_xpattern()
            case "Staggered":
                self.fanout_staggered()
    
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