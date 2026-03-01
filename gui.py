# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'gui.ui'
##
## Created by: Qt User Interface Compiler version 6.10.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QGridLayout,
    QGroupBox, QHBoxLayout, QLabel, QLayout,
    QLineEdit, QMainWindow, QMenuBar, QPushButton,
    QSizePolicy, QStatusBar, QVBoxLayout, QWidget)

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(550, 497)
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.gridLayout_3 = QGridLayout(self.centralwidget)
        self.gridLayout_3.setObjectName(u"gridLayout_3")
        self.verticalLayout = QVBoxLayout()
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        self.horizontalLayout = QHBoxLayout()
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.gridLayout = QGridLayout()
        self.gridLayout.setObjectName(u"gridLayout")
        self.labelReference = QLabel(self.centralwidget)
        self.labelReference.setObjectName(u"labelReference")

        self.gridLayout.addWidget(self.labelReference, 8, 0, 1, 1)

        self.comboViaType = QComboBox(self.centralwidget)
        self.comboViaType.setObjectName(u"comboViaType")

        self.gridLayout.addWidget(self.comboViaType, 5, 1, 1, 1)

        self.checkViaInPad = QCheckBox(self.centralwidget)
        self.checkViaInPad.setObjectName(u"checkViaInPad")

        self.gridLayout.addWidget(self.checkViaInPad, 9, 0, 1, 1)

        self.checkSkipPad = QCheckBox(self.centralwidget)
        self.checkSkipPad.setObjectName(u"checkSkipPad")

        self.gridLayout.addWidget(self.checkSkipPad, 9, 1, 1, 1)

        self.labelViaType = QLabel(self.centralwidget)
        self.labelViaType.setObjectName(u"labelViaType")

        self.gridLayout.addWidget(self.labelViaType, 5, 0, 1, 1)

        self.comboEndLayer = QComboBox(self.centralwidget)
        self.comboEndLayer.setObjectName(u"comboEndLayer")

        self.gridLayout.addWidget(self.comboEndLayer, 7, 1, 1, 1)

        self.textViaDiameter = QLineEdit(self.centralwidget)
        self.textViaDiameter.setObjectName(u"textViaDiameter")

        self.gridLayout.addWidget(self.textViaDiameter, 3, 1, 1, 1)

        self.labelStartlayer = QLabel(self.centralwidget)
        self.labelStartlayer.setObjectName(u"labelStartlayer")

        self.gridLayout.addWidget(self.labelStartlayer, 6, 0, 1, 1)

        self.labelViaHole = QLabel(self.centralwidget)
        self.labelViaHole.setObjectName(u"labelViaHole")

        self.gridLayout.addWidget(self.labelViaHole, 4, 0, 1, 1)

        self.labelTrackWidth = QLabel(self.centralwidget)
        self.labelTrackWidth.setObjectName(u"labelTrackWidth")

        self.gridLayout.addWidget(self.labelTrackWidth, 2, 0, 1, 1)

        self.comboUnit = QComboBox(self.centralwidget)
        self.comboUnit.setObjectName(u"comboUnit")

        self.gridLayout.addWidget(self.comboUnit, 1, 1, 1, 1)

        self.labelViaDiameter = QLabel(self.centralwidget)
        self.labelViaDiameter.setObjectName(u"labelViaDiameter")

        self.gridLayout.addWidget(self.labelViaDiameter, 3, 0, 1, 1)

        self.textViaHole = QLineEdit(self.centralwidget)
        self.textViaHole.setObjectName(u"textViaHole")

        self.gridLayout.addWidget(self.textViaHole, 4, 1, 1, 1)

        self.labelEndlayer = QLabel(self.centralwidget)
        self.labelEndlayer.setObjectName(u"labelEndlayer")

        self.gridLayout.addWidget(self.labelEndlayer, 7, 0, 1, 1)

        self.textTrackWidth = QLineEdit(self.centralwidget)
        self.textTrackWidth.setObjectName(u"textTrackWidth")

        self.gridLayout.addWidget(self.textTrackWidth, 2, 1, 1, 1)

        self.comboReference = QComboBox(self.centralwidget)
        self.comboReference.setObjectName(u"comboReference")

        self.gridLayout.addWidget(self.comboReference, 8, 1, 1, 1)

        self.comboStartLayer = QComboBox(self.centralwidget)
        self.comboStartLayer.setObjectName(u"comboStartLayer")

        self.gridLayout.addWidget(self.comboStartLayer, 6, 1, 1, 1)

        self.labelUnit = QLabel(self.centralwidget)
        self.labelUnit.setObjectName(u"labelUnit")

        self.gridLayout.addWidget(self.labelUnit, 1, 0, 1, 1)


        self.horizontalLayout.addLayout(self.gridLayout)

        self.groupImagePreview = QGroupBox(self.centralwidget)
        self.groupImagePreview.setObjectName(u"groupImagePreview")
        self.groupImagePreview.setMinimumSize(QSize(0, 0))

        self.horizontalLayout.addWidget(self.groupImagePreview)

        self.horizontalLayout.setStretch(1, 1)

        self.verticalLayout.addLayout(self.horizontalLayout)

        self.gridLayout_2 = QGridLayout()
        self.gridLayout_2.setObjectName(u"gridLayout_2")
        self.labelPackage = QLabel(self.centralwidget)
        self.labelPackage.setObjectName(u"labelPackage")

        self.gridLayout_2.addWidget(self.labelPackage, 0, 0, 1, 1)

        self.labelDirection = QLabel(self.centralwidget)
        self.labelDirection.setObjectName(u"labelDirection")

        self.gridLayout_2.addWidget(self.labelDirection, 0, 2, 1, 1)

        self.comboAlignment = QComboBox(self.centralwidget)
        self.comboAlignment.setObjectName(u"comboAlignment")

        self.gridLayout_2.addWidget(self.comboAlignment, 1, 1, 1, 1)

        self.labelStaggerGap = QLabel(self.centralwidget)
        self.labelStaggerGap.setObjectName(u"labelStaggerGap")

        self.gridLayout_2.addWidget(self.labelStaggerGap, 2, 1, 1, 1)

        self.labelAlignment = QLabel(self.centralwidget)
        self.labelAlignment.setObjectName(u"labelAlignment")

        self.gridLayout_2.addWidget(self.labelAlignment, 0, 1, 1, 1)

        self.comboPackage = QComboBox(self.centralwidget)
        self.comboPackage.setObjectName(u"comboPackage")

        self.gridLayout_2.addWidget(self.comboPackage, 1, 0, 1, 1)

        self.labelFanoutLength = QLabel(self.centralwidget)
        self.labelFanoutLength.setObjectName(u"labelFanoutLength")

        self.gridLayout_2.addWidget(self.labelFanoutLength, 2, 0, 1, 1)

        self.labelViaPitch = QLabel(self.centralwidget)
        self.labelViaPitch.setObjectName(u"labelViaPitch")

        self.gridLayout_2.addWidget(self.labelViaPitch, 2, 2, 1, 1)

        self.textViaPitch = QLineEdit(self.centralwidget)
        self.textViaPitch.setObjectName(u"textViaPitch")

        self.gridLayout_2.addWidget(self.textViaPitch, 3, 2, 1, 1)

        self.textStaggerGap = QLineEdit(self.centralwidget)
        self.textStaggerGap.setObjectName(u"textStaggerGap")

        self.gridLayout_2.addWidget(self.textStaggerGap, 3, 1, 1, 1)

        self.textFanoutLength = QLineEdit(self.centralwidget)
        self.textFanoutLength.setObjectName(u"textFanoutLength")

        self.gridLayout_2.addWidget(self.textFanoutLength, 3, 0, 1, 1)

        self.comboDirection = QComboBox(self.centralwidget)
        self.comboDirection.setObjectName(u"comboDirection")

        self.gridLayout_2.addWidget(self.comboDirection, 1, 2, 1, 1)


        self.verticalLayout.addLayout(self.gridLayout_2)

        self.horizontalLayout_2 = QHBoxLayout()
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.buttonClose = QPushButton(self.centralwidget)
        self.buttonClose.setObjectName(u"buttonClose")

        self.horizontalLayout_2.addWidget(self.buttonClose)

        self.buttonConnect = QPushButton(self.centralwidget)
        self.buttonConnect.setObjectName(u"buttonConnect")

        self.horizontalLayout_2.addWidget(self.buttonConnect)

        self.buttonUndo = QPushButton(self.centralwidget)
        self.buttonUndo.setObjectName(u"buttonUndo")

        self.horizontalLayout_2.addWidget(self.buttonUndo)

        self.buttonFanout = QPushButton(self.centralwidget)
        self.buttonFanout.setObjectName(u"buttonFanout")

        self.horizontalLayout_2.addWidget(self.buttonFanout)


        self.verticalLayout.addLayout(self.horizontalLayout_2)


        self.gridLayout_3.addLayout(self.verticalLayout, 0, 0, 1, 1)

        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(MainWindow)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 550, 23))
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName(u"statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.retranslateUi(MainWindow)

        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"MainWindow", None))
        self.labelReference.setText(QCoreApplication.translate("MainWindow", u"Reference:", None))
        self.checkViaInPad.setText(QCoreApplication.translate("MainWindow", u"Via in Pad", None))
        self.checkSkipPad.setText(QCoreApplication.translate("MainWindow", u"Skip Unused Pads", None))
        self.labelViaType.setText(QCoreApplication.translate("MainWindow", u"ViaType:", None))
        self.labelStartlayer.setText(QCoreApplication.translate("MainWindow", u"Start Layer:", None))
        self.labelViaHole.setText(QCoreApplication.translate("MainWindow", u"Via Hole:", None))
        self.labelTrackWidth.setText(QCoreApplication.translate("MainWindow", u"Track Width:", None))
        self.labelViaDiameter.setText(QCoreApplication.translate("MainWindow", u"Via Diameter:", None))
        self.labelEndlayer.setText(QCoreApplication.translate("MainWindow", u"End Layer:", None))
        self.labelUnit.setText(QCoreApplication.translate("MainWindow", u"Unit:", None))
        self.groupImagePreview.setTitle(QCoreApplication.translate("MainWindow", u"Preview:", None))
        self.labelPackage.setText(QCoreApplication.translate("MainWindow", u"Package:", None))
        self.labelDirection.setText(QCoreApplication.translate("MainWindow", u"Direction:", None))
        self.labelStaggerGap.setText(QCoreApplication.translate("MainWindow", u"Stagger Gap:", None))
        self.labelAlignment.setText(QCoreApplication.translate("MainWindow", u"Alignment:", None))
        self.labelFanoutLength.setText(QCoreApplication.translate("MainWindow", u"Fanout Length:", None))
        self.labelViaPitch.setText(QCoreApplication.translate("MainWindow", u"Via Pitch:", None))
        self.buttonClose.setText(QCoreApplication.translate("MainWindow", u"Close", None))
        self.buttonConnect.setText(QCoreApplication.translate("MainWindow", u"Connect to KiCad", None))
        self.buttonUndo.setText(QCoreApplication.translate("MainWindow", u"Undo", None))
        self.buttonFanout.setText(QCoreApplication.translate("MainWindow", u"Fanout", None))
    # retranslateUi

