from PySide6.QtWidgets import QMainWindow, QMessageBox, QVBoxLayout
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtCore import QTimer
from gui import Ui_MainWindow
from version import version
from kicad_pcb import KiCadPCB
from utils import ViaData, TrackData
from package import get_packages
from fanout import Fanout
import os

IU_PER_MM = 1000000
IU_PER_MILS = 25400

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowTitle(f"Fanout Tool v{version}")

        self.trackWidth: int = 0
        self.viaDiameter: int = 0
        self.viaHole: int = 0
        self.fanout_length: int = 0
        self.stagger_gap: int = 0
        self.via_pitch: int = 0
        self.packages = get_packages()
        self.unit: int = IU_PER_MILS
        self.pcb = KiCadPCB()

        self.ui.textTrackWidth.setText("8")
        self.ui.textViaDiameter.setText("10")
        self.ui.textViaHole.setText("5")
        self.ui.textFanoutLength.setText("40")
        self.ui.textStaggerGap.setText("40")
        self.ui.textViaPitch.setText("20")
        self.ui.comboUnit.addItems(["mils", "mm"])
        self.ui.comboViaType.addItems(["Through", "Micro", "Blind/Buried"])
        self.ui.textFanoutLength.setDisabled(True)
        self.ui.textStaggerGap.setDisabled(True)
        self.ui.textViaPitch.setDisabled(True)
        
        self.fanout = Fanout(
            footprint=None, 
            board=None, 
            via=None, 
            track=None, 
            package="", 
            alignment="", 
            direction="",
            in_pad=False,
            unused_pad=False,
            fanout_length=0, 
            stagger_gap=0, 
            via_pitch=0
        )
        self.set_package()
        base_dir = os.path.dirname(__file__)
        init_img = os.path.join(base_dir, "preview", "quadrant.svg")
        self.svg_widget = QSvgWidget(init_img)

        if self.ui.groupImagePreview.layout() is None:
            layout = QVBoxLayout(self.ui.groupImagePreview)
            layout.setContentsMargins(0, 0, 0, 0) 
        else:
            layout = self.ui.groupImagePreview.layout()
        layout.addWidget(self.svg_widget)

        # Delay initialization (500ms) to ensure UI is ready before connecting to KiCad
        QTimer.singleShot(500, self.load_initial_data)

        self.ui.comboUnit.currentIndexChanged.connect(self.on_unit_changed)
        self.ui.comboViaType.currentIndexChanged.connect(self.on_via_type_changed)
        self.ui.comboPackage.currentIndexChanged.connect(self.on_package_changed)
        self.ui.comboAlignment.currentIndexChanged.connect(self.on_alignment_changed)
        self.ui.comboDirection.currentIndexChanged.connect(self.on_direction_changed)
        self.ui.buttonClose.clicked.connect(self.button_close_clicked)
        self.ui.buttonConnect.clicked.connect(self.load_initial_data)
        self.ui.buttonUndo.clicked.connect(self.button_undo_clicked)
        self.ui.buttonFanout.clicked.connect(self.button_fanout_clicked)

    def load_initial_data(self):
        connected, status = self.pcb.connect_kicad()
        if connected:
            self.ui.comboReference.addItems(self.pcb.references)
            self.ui.comboStartLayer.addItems(self.pcb.layers)
            self.ui.comboEndLayer.addItems(self.pcb.layers)
            self.ui.comboEndLayer.setCurrentText(self.pcb.layers[len(self.pcb.layers)-1])
            self.ui.comboStartLayer.setEnabled(False)
            self.ui.comboEndLayer.setEnabled(False)
            self.ui.statusbar.showMessage(f"Connected to KiCad {self.pcb.kicad.get_version()}")
            print(f"Connected to KiCad {self.pcb.kicad.get_version()}")
            print(f"Opening file {self.pcb.board.document.board_filename}")
        else:
            self.ui.statusbar.showMessage(status)
            QMessageBox.information(self, "Message", status)
    
    def on_unit_changed(self):
        unit = self.ui.comboUnit.currentText()
        self.change_unit(unit)
        if unit == "mm":
            self.unit = IU_PER_MM
        else:
            self.unit = IU_PER_MILS
    
    def on_via_type_changed(self):
        type = self.ui.comboViaType.currentText()
        if type == "Through":
            self.ui.comboStartLayer.setCurrentText(self.pcb.layers[0])
            self.ui.comboEndLayer.setCurrentText(self.pcb.layers[len(self.pcb.layers)-1])
            self.ui.comboStartLayer.setEnabled(False)
            self.ui.comboEndLayer.setEnabled(False)
        else:
            self.ui.comboStartLayer.setEnabled(True)
            self.ui.comboEndLayer.setEnabled(True)

    def button_close_clicked(self):
        self.close()

    def button_undo_clicked(self):
        self.fanout.remove_items()
    
    def button_fanout_clicked(self):
        connected, status = self.pcb.connect_kicad()
        if not connected:
            self.ui.statusbar.showMessage(status)
            QMessageBox.information(self, "Message", status)
            return
        if not self.parse_input():
            return
        index = self.ui.comboReference.currentIndex()
        if index < 0:
            return
        via_type = self.ui.comboViaType.currentText()
        footprint = self.pcb.footprints[index]
        start = self.ui.comboStartLayer.currentIndex()
        end = self.ui.comboEndLayer.currentIndex()
        start_layer = self.pcb.stackup[start].id
        end_layer = self.pcb.stackup[end].id
        
        via = ViaData(
            via_type = via_type,
            via_diameter = self.viaDiameter,
            via_hole = self.viaHole,
            start_layer = start_layer,
            end_layer = end_layer,
            net = None,
            position = None
        )

        track = TrackData(
            width = self.trackWidth,
            layer = start_layer,
            net = None,
            start = None,
            end = None
        )

        in_pad = self.ui.checkViaInPad.isChecked()
        package = self.ui.comboPackage.currentText()
        alignment = self.ui.comboAlignment.currentText()
        direction = self.ui.comboDirection.currentText()
        unused_pad = self.ui.checkSkipPad.isChecked()

        self.fanout = Fanout(footprint, self.pcb.board, via, track, 
                        package, alignment, direction, in_pad, unused_pad,
                        self.fanout_length, self.stagger_gap, self.via_pitch)
        self.fanout.fanout()

    def on_package_changed(self):
        index = self.ui.comboPackage.currentIndex()
        value = self.ui.comboPackage.currentText()
        package = self.packages[index]
        alignments = []
        directions = []
        for i, ali in enumerate(package.alignments, 0):
            alignments.append(ali.name)
            if i == 0:
                for direc in ali.directions:
                    directions.append(direc.name)
        self.ui.comboAlignment.blockSignals(True)
        self.ui.comboDirection.blockSignals(True)
        self.ui.comboAlignment.clear()
        self.ui.comboDirection.clear()
        
        self.ui.comboDirection.clear()
        self.ui.comboAlignment.addItems(alignments)
        self.ui.comboDirection.addItems(directions)
        self.ui.comboAlignment.blockSignals(False)
        self.ui.comboDirection.blockSignals(False)
        image = self.packages[index].alignments[0].directions[0].image
        self.update_image(image)

        if value == 'BGA':
            self.ui.textFanoutLength.setDisabled(True)
            self.ui.textStaggerGap.setDisabled(True)
            self.ui.textViaPitch.setDisabled(True)
        if value == 'SOIC/QFN':
            self.ui.textFanoutLength.setDisabled(False)
            self.ui.textStaggerGap.setDisabled(True)
            self.ui.textViaPitch.setDisabled(True)
        else:
            self.ui.textFanoutLength.setDisabled(False)
            self.ui.textStaggerGap.setDisabled(False)
            self.ui.textViaPitch.setDisabled(False)

    def on_alignment_changed(self):
        self.ui.comboDirection.blockSignals(True)
        x = self.ui.comboPackage.currentIndex()
        y = self.ui.comboAlignment.currentIndex()
        directions = []
        direcs = self.packages[x].alignments[y].directions
        for direc in direcs:
            directions.append(direc.name)
        image = direcs[0].image
        self.ui.comboDirection.clear()
        self.ui.comboDirection.addItems(directions)
        self.update_image(image)
        self.ui.comboDirection.blockSignals(False)

        package = self.ui.comboPackage.currentText()
        alignment = self.ui.comboAlignment.currentText()

        if package == 'SOIC/QFN':
            if alignment == 'Linear Escape':
                self.ui.textFanoutLength.setDisabled(False)
                self.ui.textStaggerGap.setDisabled(True)
                self.ui.textViaPitch.setDisabled(True)
            elif alignment == 'Staggered Linear':
                self.ui.textFanoutLength.setDisabled(False)
                self.ui.textStaggerGap.setDisabled(False)
                self.ui.textViaPitch.setDisabled(True)
            elif alignment == 'Fan Escape':
                self.ui.textFanoutLength.setDisabled(False)
                self.ui.textStaggerGap.setDisabled(True)
                self.ui.textViaPitch.setDisabled(False)
            elif alignment == 'Staggered Fan':
                self.ui.textFanoutLength.setDisabled(False)
                self.ui.textStaggerGap.setDisabled(False)
                self.ui.textViaPitch.setDisabled(False)

    def on_direction_changed(self):
        x = self.ui.comboPackage.currentIndex()
        y = self.ui.comboAlignment.currentIndex()
        i = self.ui.comboDirection.currentIndex()
        image = self.packages[x].alignments[y].directions[i].image
        self.update_image(image)
    
    def update_image(self, path):
        abs_path = os.path.join(os.path.dirname(__file__), path)
        if os.path.exists(abs_path):
            self.svg_widget.load(abs_path)
        else:
            print(f"No preview image found for {abs_path}")

    def change_unit(self, uint):
        width = parse_float(self.ui.textTrackWidth.text())
        if width == None:
            QMessageBox.information(self, "Error", "Error: Invalid Track Width")
            return
        diameter = parse_float(self.ui.textViaDiameter.text())
        if diameter == None:
            QMessageBox.information(self, "Error", "Error: Invalid Via Diameter")
            return
        hole = parse_float(self.ui.textViaHole.text())
        if hole == None:
            QMessageBox.information(self, "Error", "Error: Invalid Via Hole")
            return
        fanout_length = parse_float(self.ui.textFanoutLength.text())
        if fanout_length == None:
            QMessageBox.information(self, "Error", "Error: Invalid Fanout Length")
            return
        stagger_gap = parse_float(self.ui.textStaggerGap.text())
        if stagger_gap == None:
            QMessageBox.information(self, "Error", "Error: Invalid Stagger Gap")
            return
        via_pitch = parse_float(self.ui.textViaPitch.text())
        if via_pitch == None:
            QMessageBox.information(self, "Error", "Error: Invalid Via Pitch")
            return

        if uint == "mm":
            self.ui.textTrackWidth.setText(f"{width*IU_PER_MILS/IU_PER_MM}")
            self.ui.textViaDiameter.setText(f"{diameter*IU_PER_MILS/IU_PER_MM}")
            self.ui.textViaHole.setText(f"{hole*IU_PER_MILS/IU_PER_MM}")
            self.ui.textFanoutLength.setText(f"{fanout_length*IU_PER_MILS/IU_PER_MM}")
            self.ui.textStaggerGap.setText(f"{stagger_gap*IU_PER_MILS/IU_PER_MM}")
            self.ui.textViaPitch.setText(f"{via_pitch*IU_PER_MILS/IU_PER_MM}")
        else:
            self.ui.textTrackWidth.setText(f"{width*IU_PER_MM/IU_PER_MILS}")
            self.ui.textViaDiameter.setText(f"{diameter*IU_PER_MM/IU_PER_MILS}")
            self.ui.textViaHole.setText(f"{hole*IU_PER_MM/IU_PER_MILS}")
            self.ui.textFanoutLength.setText(f"{fanout_length*IU_PER_MM/IU_PER_MILS}")
            self.ui.textStaggerGap.setText(f"{stagger_gap*IU_PER_MM/IU_PER_MILS}")
            self.ui.textViaPitch.setText(f"{via_pitch*IU_PER_MM/IU_PER_MILS}")

    def parse_input(self) -> bool:
        width = parse_float(self.ui.textTrackWidth.text())
        if width == None:
            QMessageBox.information(self, "Error", "Error: Invalid Track Width")
            return False
        diameter = parse_float(self.ui.textViaDiameter.text())
        if diameter == None:
            QMessageBox.information(self, "Error", "Error: Invalid Via Diameter")
            return False
        hole = parse_float(self.ui.textViaHole.text())
        if hole == None:
            QMessageBox.information(self, "Error", "Error: Invalid Via Hole")
            return False
        fanout_length = parse_float(self.ui.textFanoutLength.text())
        if fanout_length == None:
            QMessageBox.information(self, "Error", "Error: Invalid Fanout Length")
            return False
        stagger_gap = parse_float(self.ui.textStaggerGap.text())
        if stagger_gap == None:
            QMessageBox.information(self, "Error", "Error: Invalid Stagger Gap")
            return False
        via_pitch = parse_float(self.ui.textViaPitch.text())
        if via_pitch == None:
            QMessageBox.information(self, "Error", "Error: Invalid Via Pitch")
            return False
        self.trackWidth = int(self.unit*width)
        self.viaDiameter = int(self.unit*diameter)
        self.viaHole = int(self.unit*hole)
        self.fanout_length = int(self.unit*fanout_length)
        self.stagger_gap = int(self.unit*stagger_gap)
        self.via_pitch = int(self.unit*via_pitch)
        return True

    def set_package(self):
        default = 0 #bga
        packages = []
        alignments = []
        for package in self.packages:
            packages.append(package.name)
            if package.name == 'BGA':
                for alig in package.alignments:
                    alignments.append(alig.name)
        self.ui.comboPackage.addItems(packages)
        self.ui.comboAlignment.addItems(alignments)
        self.ui.comboPackage.setCurrentIndex(default)

def parse_float(text: str) -> float | None:
    try:
        clean_text = text.replace(',', '.').strip()
        return float(clean_text)
    except ValueError:
        return None
