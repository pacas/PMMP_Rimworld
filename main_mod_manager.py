#!/usr/bin/python3
#-*- coding:utf-8 -*-

from PyQt5.QtWidgets import QAction, QMainWindow, QWidget, QSizePolicy, QLabel, QInputDialog, QLineEdit
from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem, QHBoxLayout, QVBoxLayout, QMessageBox
from PyQt5.QtWidgets import QPushButton, QHeaderView, QSpacerItem, QTextBrowser, QMenu
from PyQt5.QtCore import QSize, Qt, QEvent, pyqtSlot
from PyQt5.QtGui import QColor, QPixmap, QFont, QIcon
import os
import webbrowser
import feature_dnd as dnd
import platform
from subprocess import Popen
import logging
from glob import glob
import fuckit
from lxml import etree as ET
import langSelector as l
import files_const as pth
from collections import Counter


# keys for sorting
def sortedKey(mod):
    return mod.sortedKey


def prior(mod):
    return mod.prior


# mod storage structure
class Mod():
    def __init__(self, name, packageId, url, modID, supportedVersions, description, isEnabled, source, prior, modfile):
        self.name = name
        self.packageId = packageId
        self.url = url
        self.modID = modID
        self.supportedVersions = supportedVersions
        self.description = description
        self.isEnabled = isEnabled
        self.source = source
        self.prior = prior
        self.modfile = modfile
        self.sortedKey = name.encode('utf8', errors='ignore')


class ModManager(QMainWindow):
    def __init__(self, first, conn, cursor, mainFolder, steamFolder, ignore, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # ------DB connection---------------
        self.conn = conn
        self.cursor = cursor
        self.localPath = mainFolder
        self.steamPath = steamFolder
        self.ignoredWarning = ignore
        # ------Lists and disk files--------
        self.get_Disk_Links()
        self.modList = list()
        self.steamIcon = QPixmap(pth.steam_pic)
        self.localIcon = QPixmap(pth.local_pic)
        self.filterList = list()
        # ------Logging---------------------
        if not os.path.exists(pth.logs_folder):
            os.mkdir(pth.logs_folder)
        self.logs = logging.getLogger("Rim-PMMP")
        handler = logging.FileHandler(filename=pth.logs_mm, mode="a+")
        formatter = logging.Formatter('%(asctime)s: %(message)s')
        handler.setFormatter(formatter)
        self.logs.setLevel(logging.ERROR)
        self.logs.addHandler(handler)
        # ------Creating modlist------------
        self.getModInfoFromFiles(first)
        self.getModList()
        self.getActivatedMods()
        # ------Backup list-----------------
        self.modListBackup = self.modList
        # ------UI setup--------------------
        self.setupUI()
        if self.ignoredWarning == '1':
            self.duplicateWarning()

    def setupUI(self):
        # ------Window setup----------------
        self.setMinimumSize(QSize(1200, 700))
        self.setWindowTitle(l.r.manager)
        self.setWindowIcon(QIcon(pth.logo))
        # ------Central widget--------------
        self.centralwidget = QWidget(self)
        self.horizontalLayout = QHBoxLayout(self.centralwidget)
        self.additionalLayout = QVBoxLayout()
        self.filterLayout = QHBoxLayout()
        self.centralwidget.setMinimumSize(QSize(1200, 700))
        self.centralwidget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # ------Table widget----------------
        self.table = dnd.TableWidgetDragRows()
        self.table.setColumnCount(3)
        self.header = self.table.horizontalHeader()
        self.header.setSectionResizeMode(0, QHeaderView.Stretch)
        self.header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.setColumnWidth(2, 20)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.table.setMinimumSize(QSize(800, 300))
        self.additionalLayout.addWidget(self.table, 0)
        self.verticalLayout = QVBoxLayout()
        self.dataDisplay(self.modList)
        self.table.cellDoubleClicked.connect(self.modSwitch)
        self.table.cellClicked.connect(self.displayModData)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.generateMenu)
        self.table.viewport().installEventFilter(self)
        self.table.setMouseTracking(True)
        self.current_hover = [0, 0]
        # ------Filter----------------------
        self.filterLabel = QLabel(l.r.search, self.centralwidget)
        self.filterLine = QLineEdit('', self.centralwidget)
        self.filterLine.textChanged.connect(self.on_textChanged)
        self.filterClean = QPushButton(l.r.clean, self.centralwidget)
        self.filterClean.clicked.connect(lambda: self.filterLine.setText(''))
        self.filterClean.setMaximumSize(QSize(75, 30))
        self.additionalLayout.addLayout(self.filterLayout)
        self.filterLayout.addWidget(self.filterLabel, 0)
        self.filterLayout.addWidget(self.filterLine, 1)
        self.filterLayout.addWidget(self.filterClean, 2)
        # ------Mod title label-------------
        self.modname = QLabel(l.r.modTitle, self.centralwidget)
        self.modname.setMinimumSize(QSize(320, 70))
        newfont = QFont('Times', 18, QFont.Bold)
        self.modname.setFont(newfont)
        self.modname.setWordWrap(True)
        self.modname.setAlignment(Qt.AlignHCenter)
        self.verticalLayout.addWidget(self.modname, 0, Qt.AlignHCenter | Qt.AlignVCenter)
        # ------Preview pic-----------------
        self.pic = QLabel()
        self.printModPreview(pth.nologo)
        self.verticalLayout.addWidget(self.pic, 0, Qt.AlignHCenter | Qt.AlignVCenter)
        self.verticalLayout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Fixed, QSizePolicy.Fixed))
        # ------Mod description-------------
        self.textBrowser = QTextBrowser(self.centralwidget)
        newfont = QFont('Verdana', 13, QFont.Bold)
        self.textBrowser.setFont(newfont)
        self.verticalLayout.addWidget(self.textBrowser, 0, Qt.AlignHCenter | Qt.AlignVCenter)
        # ------Links for buttons-----------
        self.verticalLayout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))
        self.linkButton = QPushButton(l.r.openBrowser, self.centralwidget)
        self.linkButton.setFixedSize(QSize(260, 30))
        self.verticalLayout.addWidget(self.linkButton, 0, Qt.AlignHCenter | Qt.AlignVCenter)
        # -------------
        self.linkSteamButton = QPushButton(l.r.openSteam, self.centralwidget)
        self.linkSteamButton.setFixedSize(QSize(260, 30))
        self.verticalLayout.addWidget(self.linkSteamButton, 0, Qt.AlignHCenter | Qt.AlignVCenter)
        self.verticalLayout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Fixed, QSizePolicy.Fixed))
        # -------------
        self.exitButton = QPushButton(l.r.exitLabel, self.centralwidget)
        self.exitButton.setFixedSize(QSize(260, 30))
        self.verticalLayout.addWidget(self.exitButton, 0, Qt.AlignHCenter | Qt.AlignVCenter)
        self.verticalLayout.addSpacerItem(QSpacerItem(10, 10, QSizePolicy.Fixed, QSizePolicy.Fixed))
        # ------Layout stuff----------------
        self.horizontalLayout.addLayout(self.additionalLayout)
        self.horizontalLayout.addLayout(self.verticalLayout)
        self.setCentralWidget(self.centralwidget)
        # ------Menu------------------------
        self.menu = self.menuBar()
        prMenu = self.menu.addMenu(l.r.programMenu)
        orderMenu = self.menu.addMenu(l.r.sortingMenu)
        self.foldersMenu = self.menu.addMenu(l.r.foldersMenu)
        backupMenu = self.menu.addMenu(l.r.backupsMenu)
        # ------Program---------------------
        dumpACT = QAction(l.r.saveOrder, self)
        dumpACT.setShortcut('Ctrl+S')
        dumpACT.triggered.connect(self.dumpLoadOrder)
        prMenu.addAction(dumpACT)
        # -------------
        reloadMods = QAction(l.r.reloadMods, self)
        reloadMods.setShortcut('Ctrl+S')
        reloadMods.triggered.connect(lambda: self.getModInfoFromFiles(0))
        prMenu.addAction(reloadMods)
        # -------------
        helpACT = QAction(l.r.helpLabel, self)
        helpACT.triggered.connect(self.getHelp)
        prMenu.addAction(helpACT)
        # -------------
        self.exitACT = QAction(l.r.exitLabel, self)
        prMenu.addAction(self.exitACT)
        # ------Sorting---------------------
        orderACT = QAction(l.r.sortAsc, self)
        orderACT.triggered.connect(lambda: self.sortByType(True))
        orderMenu.addAction(orderACT)
        # -------------
        order1ACT = QAction(l.r.sortDesc, self)
        order1ACT.triggered.connect(lambda: self.sortByType(False))
        orderMenu.addAction(order1ACT)
        # ------Folders---------------------
        gameFolder = QAction(l.r.openGameFolder, self)
        gameFolder.triggered.connect(lambda: self.folders_Opener(self.localPath))
        self.foldersMenu.addAction(gameFolder)
        # -------------
        docsFolder = QAction(l.r.openGameDocs, self)
        docsFolder.triggered.connect(lambda: self.folders_Opener(self.configFolder))
        self.foldersMenu.addAction(docsFolder)
        # -------------
        localModsFolder = QAction(l.r.openLocalMods, self)
        localModsFolder.triggered.connect(lambda: self.folders_Opener(self.localMods))
        self.foldersMenu.addAction(localModsFolder)
        # -------------
        if self.steamPath != '':
            steamModsFolder = QAction(l.r.openSteamMods, self)
            steamModsFolder.triggered.connect(lambda: self.folders_Opener(self.steamPath))
            self.foldersMenu.addAction(steamModsFolder)
        # ------Backups---------------------
        self.openBackupMenu = QAction(l.r.openBackups, self)
        backupMenu.addAction(self.openBackupMenu)
        # -------------
        reload = QAction(l.r.reloadModlist, self)
        reload.triggered.connect(self.reloadOrder)
        # not working right now
        # backupMenu.addAction(reload)

# ---------------------Setting paths of the game----------------------------------
    def get_Disk_Links(self):
        self.localMods = self.localPath + '\Mods'
        self.configFolder = os.getenv('LOCALAPPDATA') + 'Low\Ludeon Studios\RimWorld by Ludeon Studios'
        self.configFile = self.configFolder + '\Config\ModsConfig.xml'
        self.url = 'https://steamcommunity.com/sharedfiles/filedetails/?id='
        self.steam_url = 'steam://url/CommunityFilePage/'

    # for future linux/mac releases
    def folders_Opener(self, path):
        if platform.system() == "Windows":
            os.startfile(path)
        elif platform.system() == "Darwin":
            Popen(["open", path])
        else:
            Popen(["xdg-open", path])

# ---------------------Get modifications data------------------------------------
    def getModInfoFromFiles(self, firstLaunch):
        try:
            self.modsToAdd = list()
            self.modsToCheck = list()
            self.newValuesForMods = list()
            localModList = glob(self.localMods + '\*\About\About.xml')
            if self.steamPath != '':
                steamModList = glob(self.steamPath + '\*\About\About.xml')
                allModList = steamModList + localModList
            modsMatrix = []
            for mod in allModList:
                info = mod[:-9] + 'PublishedFileId.txt'
                if os.path.isfile(info):
                    with open(info, 'r') as file:
                        temp = file.read()
                    modsMatrix.append([mod, temp])
                else:
                    modsMatrix.append([mod, ''])
            if firstLaunch == 1:
                prior = 0
                for oneTwo in modsMatrix:
                    self.getModData(oneTwo[0], prior, 0, oneTwo[1])
                    prior += 1
            else:
                self.cursor.execute("SELECT COUNT (*) FROM mods")
                records = self.cursor.fetchall()
                prior = int(records[0][0])
                self.cursor.execute("SELECT * FROM mods")
                records = self.cursor.fetchall()
                for mod in records:
                    if mod[9] not in allModList:
                        tmp = mod[9]
                        tmp = tmp.replace("'", "''")
                        self.cursor.execute(f"DELETE FROM mods WHERE modfile = '{tmp}'")
                for oneTwo in modsMatrix:
                    tmp = oneTwo[0]
                    tmp = tmp.replace("'", "''")
                    self.cursor.execute(f"SELECT EXISTS(SELECT name FROM mods WHERE modfile = '{tmp}')")
                    records = self.cursor.fetchall()
                    if records[0][0] == 0:
                        self.getModData(oneTwo[0], prior, 0, oneTwo[1])
                        prior += 1
                    else:
                        self.modsToCheck.append(oneTwo)
                for mod in self.modsToCheck:
                    self.getModData(oneTwo[0], prior, 1, oneTwo[1])
            self.cursor.executemany("INSERT INTO mods VALUES (?,?,?,?,?,?,?,?,?,?)", self.modsToAdd)
            self.cursor.executemany("UPDATE mods SET name = ?, packageId = ?, url = ?, supportedVersions = ?, description = ? WHERE modfile = ?", self.newValuesForMods)
            self.conn.commit()
        except Exception as err:
            self.logs.error(err, exc_info=True)

    @fuckit
    def getModData(self, mod, prior, update, steamModID):
        try:
            if mod.find(r'RimWorld\Mods') == -1:
                source = 'steam'
            else:
                source = 'local'
            modID = steamModID
            parser = ET.XMLParser(remove_blank_text=True)
            tree = ET.parse(mod, parser)
            root = tree.getroot()
            name = root.findall("name")[0].text
            author = root.findall("author")[0].text
            packageId = ''
            packageId = root.findall("packageId")[0].text
            packageId = packageId.lower()
            if packageId == '':
                newPackage1 = author.lower()
                newPackage2 = name.lower()
                newPackage1 = ''.join(e for e in newPackage1 if e.isalnum())
                newPackage2 = ''.join(e for e in newPackage2 if e.isalnum())
                newPackage = newPackage1 + '.' + newPackage2
                if len(newPackage) > 59:
                    if len(newPackage1) < 50:
                        newPackage = newPackage1 + '.'
                        newPackage += newPackage2[:59 - len(newPackage)]
                    else:
                        newPackage = newPackage1[:30] + '.' + newPackage2[:7]
                self.SubElementWithText(root, 'packageId', newPackage)
                packageId = newPackage
                print(newPackage)
                tree.write(mod, pretty_print=True, xml_declaration=True)
            url = ''
            url = root.findall("url")[0].text
            description = ''
            description = root.findall("description")[0].text
            supportedVersionsList = root.findall("supportedVersions")[0]
            supportedVersions = ''
            if len(supportedVersionsList) > 1:
                for i in supportedVersionsList:
                    supportedVersions += i.text + r', '
            else:
                supportedVersions = supportedVersionsList[0].text
            supportedVersions = supportedVersions[:-2]
            if supportedVersions == '':
                supportedVersions = root.findall("targetVersion")[0].text
            mods = [name, packageId, url, modID, supportedVersions, description, 0, source, prior, mod]
            if update == 0:
                self.modsToAdd.append(mods)
            else:
                newVal = [name, packageId, url, supportedVersions, description, mod]
                self.newValuesForMods.append(newVal)
        except Exception as err:
            self.logs.error(err, exc_info=True)

# ----------------------------Get final data-------------------------------------
    def getActivatedMods(self):
        try:
            parser = ET.XMLParser(remove_blank_text=True)
            self.tree = ET.parse(self.configFile, parser)
            self.root = self.tree.getroot()
            self.activeModsList = self.root.findall("activeMods")[0]
            activeMods = list()
            for i in self.activeModsList:
                tmp = i.text
                tmp = tmp.lower()
                activeMods.append(tmp)
            activeMods.remove('ludeon.rimworld')
            if 'ludeon.rimworld.royalty' in activeMods:
                activeMods.remove('ludeon.rimworld.royalty')
            priorCounter = 0
            modListSplitter = list()
            for package in activeMods:
                duplicateFlag = 0
                check = len(modListSplitter)
                if '_steam' in package:
                    package = package[:-6]
                    duplicateFlag = 1
                for mod in self.modList:
                    if package == mod.packageId:
                        if duplicateFlag == 1 and mod.source == 'steam':
                            mod.prior = priorCounter
                            mod.isEnabled = 1
                            modListSplitter.append(mod)
                            break
                        elif duplicateFlag == 1 and mod.source == 'local':
                            continue
                        else:
                            mod.prior = priorCounter
                            mod.isEnabled = 1
                            modListSplitter.append(mod)
                            break
                if check != len(modListSplitter):
                    priorCounter += 1
            notActiveModsList = [i for i in self.modList if i not in modListSplitter]
            for mod in notActiveModsList:
                mod.prior = priorCounter
                priorCounter += 1
            self.modList = modListSplitter + notActiveModsList
            self.diplicateModTestList = list()
            for mod in self.modList:
                self.diplicateModTestList.append(mod.packageId)
            self.duplicatesList = [item for item, count in Counter(self.diplicateModTestList).items() if count > 1]
            self.duplicateResolver()
            self.saveInDB()
        except Exception as err:
            self.logs.error(err, exc_info=True)

    def pairConstructor(self, target):
        for i in range(len(self.modList)):
            if self.modList[i].prior == target:
                return i

    def getModList(self):
        try:
            self.cursor.execute("SELECT * FROM mods")
            records = self.cursor.fetchall()
            for row in records:
                mod = Mod(row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8], row[9])
                self.modList.append(mod)
            self.modList.sort(key=prior)
        except Exception as err:
            self.logs.error(err, exc_info=True)

# ----------------------Table and other visual-----------------------------------
    def dataDisplay(self, modList):
        self.retrieveData()
        self.modList = modList
        self.table.setRowCount(0)
        self.table.setRowCount(len(modList))
        labels = [l.r.name, l.r.version, l.r.modType]
        self.table.setHorizontalHeaderLabels(labels)
        for i in range(3):
            self.table.horizontalHeaderItem(i).setTextAlignment(Qt.AlignHCenter)
        counter = 0
        for mod in modList:
            mod.prior = counter
            # ----------------------------------
            self.table.setItem(counter, 0, QTableWidgetItem(mod.name))
            # ----------------------------------
            vs = QTableWidgetItem(mod.supportedVersions)
            vs.setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            self.table.setItem(counter, 1, vs)
            # ----------------------------------
            image = QTableWidgetItem()
            if mod.source == 'steam':
                image.setData(Qt.DecorationRole, self.steamIcon)
            else:
                image.setData(Qt.DecorationRole, self.localIcon)
            image.setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            self.table.setItem(counter, 2, image)
            # ----------------------------------
            if mod.isEnabled == 1:
                for i in range(3):
                    self.table.item(counter, i).setBackground(QColor.fromRgb(191, 245, 189))
            # ----------------------------------
            counter += 1
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

    def retrieveData(self):
        modListNew = []
        rowCount = self.table.rowCount()
        for tableItem in range(rowCount):
            item = self.table.item(tableItem, 0)
            ID = item.text()
            for mod in self.modList:
                if mod.name == ID:
                    mod.prior = tableItem
                    modListNew.append(mod)
                    break
        modListNew.sort(key=lambda x: x.prior, reverse=False)
        self.modList = modListNew

    def printModPreview(self, image):
        if os.path.isfile(image):
            tmp = QPixmap(image)
        else:
            tmp = QPixmap(pth.nologo)
        tmp = tmp.scaled(256, 256, Qt.KeepAspectRatio)
        self.pic.setPixmap(tmp)

# ----------------------Switching mods state-------------------------------------
    def modSwitch(self, row, column):
        # Single
        self.retrieveData()
        try:
            clr = self.modList[row].isEnabled
            if clr == 0:
                for i in range(3):
                    self.table.item(row, i).setBackground(QColor.fromRgb(191, 245, 189))
                self.modList[row].isEnabled = 1
            else:
                for i in range(3):
                    self.table.item(row, i).setBackground(QColor('white'))
                self.modList[row].isEnabled = 0
        except Exception as err:
            self.logs.error(err, exc_info=True)

    def modSwitchAll(self, tp):
        # All
        self.retrieveData()
        try:
            for i in range(len(self.modList)):
                self.modList[i].isEnabled = tp
                if tp == 0:
                    for j in range(3):
                        self.table.item(i, j).setBackground(QColor('white'))
                else:
                    for j in range(3):
                        self.table.item(i, j).setBackground(QColor.fromRgb(191, 245, 189))
        except Exception as err:
            self.logs.error(err, exc_info=True)

# -----------------------------Moving mods---------------------------------------
    def moveMod(self, row, column, tp):
        try:
            if tp == 0:
                newpos, okPressed = QInputDialog.getText(self, ' ', l.r.newPos, QLineEdit.Normal, '')
                try:
                    newpos = int(newpos)
                    if okPressed and newpos >= 0 and newpos < len(self.modList):
                        if newpos > row:
                            self.modList.insert(newpos, self.modList[row])
                            self.modList.pop(row)
                        else:
                            self.modList.insert(newpos, self.modList[row])
                            self.modList.pop(row + 1)
                        self.dataDisplay(self.modList)
                    else:
                        QMessageBox.about(self, l.r.error, l.r.errorPos)
                except Exception:
                    QMessageBox.about(self, l.r.error, l.r.errorPos)
            elif tp == 1 and row != 0:
                self.modList.insert(0, self.modList[row])
                self.modList.pop(row + 1)
                self.dataDisplay(self.modList)
            elif tp == 2 and row != len(self.modList):
                self.modList.insert(len(self.modList), self.modList[row])
                self.modList.pop(row)
                self.dataDisplay(self.modList)
            else:
                pass
        except Exception as err:
            self.logs.error(err, exc_info=True)

# -----------------------------RMB event-----------------------------------------
    def eventFilter(self, source, event):
        try:
            if(event.type() == QEvent.MouseButtonPress and event.buttons() == Qt.RightButton and source is self.table.viewport()):
                item = self.table.itemAt(event.pos())
                if item is not None:
                    self.rcmenu = QMenu(self)
                    # -------------------move mod------------------
                    mMod = QAction(l.r.moveTo, self)
                    mMod.triggered.connect(lambda: self.moveMod(item.row(), item.column(), 0))
                    self.rcmenu.addAction(mMod)
                    # -------------------move mod------------------
                    mMod = QAction(l.r.moveTop, self)
                    mMod.triggered.connect(lambda: self.moveMod(item.row(), item.column(), 1))
                    self.rcmenu.addAction(mMod)
                    # -------------------move mod------------------
                    mMod = QAction(l.r.moveBottom, self)
                    mMod.triggered.connect(lambda: self.moveMod(item.row(), item.column(), 2))
                    self.rcmenu.addAction(mMod)
                    # -------------------one mod-------------------
                    enableMod = QAction(l.r.switchState, self)
                    enableMod.triggered.connect(lambda: self.modSwitch(item.row(), item.column()))
                    self.rcmenu.addAction(enableMod)
                    # -------------------all mods-enable-----------
                    enableAllMod = QAction(l.r.enableAll, self)
                    enableAllMod.triggered.connect(lambda: self.modSwitchAll(1))
                    self.rcmenu.addAction(enableAllMod)
                    # -------------------all mods-disable----------
                    disableAllMod = QAction(l.r.disableAll, self)
                    disableAllMod.triggered.connect(lambda: self.modSwitchAll(0))
                    self.rcmenu.addAction(disableAllMod)
            return super(ModManager, self).eventFilter(source, event)
        except Exception as err:
            self.logs.error(err, exc_info=True)

    def generateMenu(self, pos):
        self.rcmenu.exec_(self.table.mapToGlobal(pos))

# -----------------------------Search method-------------------------------------
    @pyqtSlot(str)
    def on_textChanged(self, text):
        try:
            text = text.lower()
            for item in range(len(self.modList)):
                filteredText = self.modList[item].name.lower()
                if text in filteredText and text != '' and len(text) > 1:
                    self.filterList.append(self.modList[item].packageId)
                    for i in range(3):
                        self.table.item(item, i).setBackground(QColor('yellow'))
                else:
                    if self.modList[item].packageId in self.filterList:
                        if self.modList[item].isEnabled == 1:
                            for i in range(3):
                                self.table.item(item, i).setBackground(QColor.fromRgb(191, 245, 189))
                            self.filterList.remove(self.modList[item].packageId)
                        else:
                            for i in range(3):
                                self.table.item(item, i).setBackground(QColor('white'))
                            self.filterList.remove(self.modList[item].packageId)
        except Exception as err:
            self.logs.error(err, exc_info=True)

# -----------------------------Additional mod info-------------------------------
    def displayModData(self, row, column):
        try:
            self.retrieveData()
            self.modname.setText(self.modList[row].name)
            texttags = str(self.modList[row].description)
            self.linkButton.disconnect()
            self.linkSteamButton.disconnect()
            self.linkButton.clicked.connect(lambda: webbrowser.open(self.modList[row].url))
            self.linkSteamButton.clicked.connect(lambda: webbrowser.open(self.modList[row].url))
            try:
                self.printModPreview(self.modList[row].modfile[:-9] + '\preview.png')
            except Exception:
                self.printModPreview(pth.nologo)
            if self.modList[row].source == 'local':
                self.linkButton.setVisible(0)
                self.linkSteamButton.setVisible(0)
            else:
                self.linkButton.setVisible(1)
                self.linkSteamButton.setVisible(1)
            self.textBrowser.setText(texttags)
            self.textBrowser.setMinimumSize(QSize(280, 35 + texttags.count('\n') * 25))
        except Exception as err:
            self.logs.error(err, exc_info=True)

# -----------------------------Technical stuff-----------------------------------
    def duplicateWarning(self):
        if len(self.diplicateModTestList) != len(set(self.diplicateModTestList)):
            print("\a")
            msg = QMessageBox.question(self, l.r.attention,
            l.r.duplicates, QMessageBox.Ok |
            QMessageBox.Ignore, QMessageBox.Ok)
            if msg == QMessageBox.Ignore:
                self.ignoredWarning = 0
                with open(pth.ini_file, 'r', encoding='UTF-8') as settings:
                    data = settings.read()
                    data = data.replace('multipackage_warning=1', 'multipackage_warning=0')
                with open(pth.ini_file, 'w', encoding='UTF-8') as settings:
                    settings.write(data)
    
    def duplicateResolver(self):
        for mod in self.modList:
            if mod.packageId in self.duplicatesList:
                if '(St)' not in mod.name:
                    if '(L)' not in mod.name:
                        if mod.source == 'steam':
                            mod.name = mod.name + ' (St)'
                        else:
                            mod.name = mod.name + ' (L)'

    def SubElementWithText(self, parent, tag, text):
        data = ET.SubElement(parent, tag)
        data.text = text

    def reloadOrder(self):
        try:
            self.modList = self.modListBackup
            self.dataDisplay(self.modList)
        except Exception as err:
            self.logs.error(err, exc_info=True)

    def sortByType(self, btype):
        self.modList.sort(key=sortedKey, reverse=btype)
        self.dataDisplay(self.modList)

    def dumpLoadOrder(self):
        try:
            self.retrieveData()
            self.saveInDB()
            self.saveInGame()
        except Exception as err:
            self.logs.error(err, exc_info=True)

    def getHelp(self):
        QMessageBox.about(self, l.r.helpLabel, l.r.helpContent)

# ----------------------Saving modlist to the game and DB------------------------
    def saveInDB(self):
        allFile = list()
        self.cursor.execute('DELETE FROM mods')
        for mod in self.modList:
            md = list()
            try:
                md.append(mod.name)
                md.append(mod.packageId)
                md.append(mod.url)
                md.append(mod.modID)
                md.append(mod.supportedVersions)
                md.append(mod.description)
                md.append(mod.isEnabled)
                md.append(mod.source)
                md.append(mod.prior)
                md.append(mod.modfile)
            except KeyError:
                pass
            allFile.append(md)
        self.cursor.executemany("INSERT INTO mods VALUES (?,?,?,?,?,?,?,?,?,?)", allFile)
        self.conn.commit()

    def saveInGame(self):
        try:
            try:
                self.DLC = self.root.findall("knownExpansions")[0]
                self.DLC = self.DLC[0]
                noDLC = 0
            except Exception:
                noDLC = 1
            self.activeModsList.clear()
            tempList = self.modList
            for mod in tempList:
                if mod.packageId == 'brrainz.harmony' and mod.isEnabled == 1:
                    self.SubElementWithText(self.activeModsList, 'li', 'brrainz.harmony')
                    tempList.remove(mod)
                    continue
                if mod.packageId == 'automatic.startupimpact' and mod.isEnabled == 1:
                    self.SubElementWithText(self.activeModsList, 'li', 'automatic.startupimpact')
                    tempList.remove(mod)
                    continue
            self.SubElementWithText(self.activeModsList, 'li', 'ludeon.rimworld')
            if noDLC == 0:
                self.SubElementWithText(self.activeModsList, 'li', 'ludeon.rimworld.royalty')
            tempList.sort(key=lambda x: x.prior, reverse=False)
            for mod in tempList:
                if mod.isEnabled == 1:
                    if mod.packageId in self.duplicatesList:
                        if mod.source == 'steam':
                            self.SubElementWithText(self.activeModsList, 'li', mod.packageId + '_steam')
                        else:
                            # требуется тест
                            self.SubElementWithText(self.activeModsList, 'li', mod.packageId)
                    else:
                        self.SubElementWithText(self.activeModsList, 'li', mod.packageId)
            self.tree.write(self.configFile, pretty_print=True, xml_declaration=True)
        except Exception as err:
            self.logs.error(err, exc_info=True)
