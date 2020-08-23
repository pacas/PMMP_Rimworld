#!/usr/bin/python3
#-*- coding:utf-8 -*-

from PyQt5.QtWidgets import QMainWindow, QWidget, QSizePolicy, QLabel
from PyQt5.QtWidgets import QPushButton, QMessageBox
from PyQt5.QtCore import QSize, QPoint, Qt
from PyQt5.QtGui import QIcon, QImage, QPalette, QBrush
import threading
import os
import langSelector as l
import design.styles as style
import files_const as pth


class Launcher(QMainWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # ----------------------------------
        self.setFixedSize(QSize(800, 600))
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setWindowTitle(l.r.launcher)
        self.setWindowIcon(QIcon(pth.logo))
        background = QImage(pth.background_launcher)
        self.centralwidget = QWidget(self)
        self.centralwidget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        palette = QPalette()
        palette.setBrush(QPalette.Window, QBrush(background))
        self.setPalette(palette)
        # ----------------------------------
        self.launch = QPushButton(l.r.launch, self.centralwidget)
        self.modmanager = QPushButton(l.r.modManager, self.centralwidget)
        self.options = QPushButton(l.r.options, self.centralwidget)
        self.exit = QPushButton(l.r.exitLabel, self.centralwidget)
        # ---layout-------------------------
        self.launch.setFixedSize(QSize(200, 70))
        self.launch.move(520, 200)
        self.modmanager.setFixedSize(QSize(200, 70))
        self.modmanager.move(520, 300)
        self.options.setFixedSize(QSize(200, 70))
        self.options.move(520, 400)
        self.exit.setFixedSize(QSize(200, 70))
        self.exit.move(520, 500)
        # ---launcher-version---------------
        self.version = QLabel('v1.0.0', self.centralwidget)
        p = self.geometry().bottomLeft() - self.version.geometry().bottomLeft() - QPoint(-10, 10)
        self.version.move(p)
        self.version.setStyleSheet(style.launcher_version)
        # ----------------------------------
        self.setCentralWidget(self.centralwidget)

    def gamestart(self, game):
        try:
            d = threading.Thread(name='daemon', target=os.startfile(game))
            d.setDaemon(True)
            d.start()
        except OSError as err:
            QMessageBox.about(self, l.r.warning, l.r.warningDesc1)
            print("OS error: {0}".format(err))
