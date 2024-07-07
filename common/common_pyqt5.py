import screeninfo
from PyQt5.QtCore import Qt, QEvent
from PyQt5.QtWidgets import QDesktopWidget, QComboBox, QLineEdit, QListWidget, QCheckBox, QListWidgetItem, QAction, QMessageBox, QHeaderView, QStyledItemDelegate
from PyQt5.QtGui import QTextCursor, QFont
from PyQt5.Qt import QFontMetrics
from PyQt5 import QtGui


def center_window(window):
    """
    Move the input GUI window into the center of the computer windows.
    """
    qr = window.frameGeometry()
    cp = QDesktopWidget().availableGeometry().center()
    qr.moveCenter(cp)
    window.move(qr.topLeft())

def auto_resize(window, width=0, height=0):
    """
    Scaling down the window size if screen resolution is smaller than window resolution.
    input:  Window: Original window; Width: window width; Height: window height
    output: Window: Scaled window
    """
    # Get default width/height setting.
    monitor = screeninfo.get_monitors()[0]

    if not width:
        width = monitor.width

    if not height:
        height = monitor.height

    # If the screen size is too small, automatically obtain the appropriate length and width value.
    if (monitor.width < width) or (monitor.height < height):
        width_rate = math.floor((monitor.width / width) * 100)
        height_rate = math.floor((monitor.height / height) * 100)
        min_rate = min(width_rate, height_rate)
        width = int((width * min_rate) / 100)
        height = int((height * min_rate) / 100)

    # Resize with auto width/height value.
    window.resize(width, height)


def text_edit_visible_position(text_edit_item, position='End'):
    """
    For QTextEdit widget, show the 'Start' or 'End' part of the text.
    """
    cursor = text_edit_item.textCursor()

    if position == 'Start':
        cursor.movePosition(QTextCursor.Start)
    elif position == 'End':
        cursor.movePosition(QTextCursor.End)

    text_edit_item.setTextCursor(cursor)
    text_edit_item.ensureCursorVisible()


class MyCheckBox(QCheckBox):
    """
    Re-Write eventFilter function for QCheckBox.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.installEventFilter(self)

    def eventFilter(self, watched, event):
        """
        Make sure clicking on the blank section still takes effect.
        """
        if (watched == self) and (event.type() == QEvent.MouseButtonPress):
            if self.rect().contains(event.pos()):
                self.toggle()
                return True

        return super().eventFilter(watched, event)


class QComboCheckBox(QComboBox):
    """
    QComboCheckBox is a QComboBox with checkbox.
    """
    def __init__(self, parent):
        super(QComboCheckBox, self).__init__(parent)

        self.separator = ' '

        # self.qLineWidget is used to load QCheckBox items.
        self.qListWidget = QListWidget()
        self.setModel(self.qListWidget.model())
        self.setView(self.qListWidget)

        # self.qLineEdit is used to show selected items on QLineEdit.
        self.qLineEdit = QLineEdit()
        self.qLineEdit.textChanged.connect(self.validQLineEditValue)
        self.qLineEdit.setReadOnly(True)
        self.setLineEdit(self.qLineEdit)

        # self.checkBoxList is used to save QCheckBox items.
        self.checkBoxList = []

        # Adjust width for new item.
        self.dropDownBoxWidthPixel = self.width()

    def validQLineEditValue(self):
        """
        Make sure value of self.qLineEdit always match selected items.
        """
        selectedItemString = self.separator.join(self.selectedItems().values())

        if self.qLineEdit.text() != selectedItemString:
            self.updateLineEdit()

    def addCheckBoxItems(self, text_list):
        """
        Add multi QCheckBox format items.
        """
        for text in text_list:
            self.addCheckBoxItem(text)

    def addCheckBoxItem(self, text):
        """
        Add QCheckBox format item into QListWidget(QComboCheckBox).
        """
        qItem = QListWidgetItem(self.qListWidget)
        qBox = MyCheckBox(text)
        qBox.stateChanged.connect(self.qBoxStateChanged)
        self.checkBoxList.append(qBox)
        self.qListWidget.setItemWidget(qItem, qBox)
        self.updateDropDownBoxWidth(text, qBox)

    def updateLineEdit(self):
        """
        Update QComboCheckBox show message with self.qLineEdit.
        """
        selectedItemString = self.separator.join(self.selectedItems().values())
        self.qLineEdit.setReadOnly(False)
        self.qLineEdit.clear()
        self.qLineEdit.setText(selectedItemString)
        self.qLineEdit.setReadOnly(True)

    def updateDropDownBoxWidth(self, text, qBox):
        """
        Update self.dropDownBoxWidthPixel.
        """
        fm = QFontMetrics(QFont())
        textPixel = fm.width(text)
        indicatorPixel = qBox.iconSize().width() * 1.4

        if textPixel > self.dropDownBoxWidthPixel:
            self.dropDownBoxWidthPixel = textPixel
            self.view().setMinimumWidth(self.dropDownBoxWidthPixel + indicatorPixel)

    def updateItemSelectedState(self, itemText, checkState):
        """
        If "ALL" is selected, unselect other items.
        If other item is selected, unselect "ALL" item.
        """
        if checkState != 0:
            selectedItemDic = self.selectedItems()
            selectedItemList = list(selectedItemDic.values())

            if itemText == 'ALL':
                if len(selectedItemList) > 1:
                    for (i, qBox) in enumerate(self.checkBoxList):
                        if (qBox.text() in selectedItemList) and (qBox.text() != 'ALL'):
                            self.checkBoxList[i].setChecked(False)
            else:
                if 'ALL' in selectedItemList:
                    for (i, qBox) in enumerate(self.checkBoxList):
                        if qBox.text() == 'ALL':
                            self.checkBoxList[i].setChecked(False)
                            break

    def selectedItems(self):
        """
        Get all selected items (location and value).
        """
        selectedItemDic = {}

        for (i, qBox) in enumerate(self.checkBoxList):
            if qBox.isChecked() is True:
                selectedItemDic.setdefault(i, qBox.text())

        return selectedItemDic

    def selectAllItems(self):
        """
        Select all items.
        """
        for (i, qBox) in enumerate(self.checkBoxList):
            if qBox.isChecked() is False:
                self.checkBoxList[i].setChecked(True)

    def unselectAllItems(self):
        """
        Unselect all items.
        """
        for (i, qBox) in enumerate(self.checkBoxList):
            if qBox.isChecked() is True:
                self.checkBoxList[i].setChecked(False)

    def clear(self):
        """
        Clear all items.
        """
        super().clear()
        self.checkBoxList = []

    def setItemsCheckStatus(self, item_list=[], item_state=Qt.Checked):
        """
        set check state Qt.Checked or Qt.Unchecked
        """
        for (i, qBox) in enumerate(self.checkBoxList):
            if qBox.text() in item_list:
                qBox.setCheckState(item_state)

    def stateChangedconnect(self, func=None):
        if func:
            for (i, qBox) in enumerate(self.checkBoxList):
                qBox.stateChanged.connect(func)

    def setEditLineSeparator(self, separator=' '):
        if separator:
            self.separator = separator

    def selectItems(self, item_list):
        for text in item_list:
            for (i, qBox) in enumerate(self.checkBoxList):
                if qBox.text() == text:
                    self.checkBoxList[i].setChecked(True)

    def qBoxStateChanged(self, checkState):
        """
        Post process for qBox state change.
        """
        itemText = self.sender().text()

        self.updateItemSelectedState(itemText, checkState)
        self.updateLineEdit()

    def setItemsCheckEnable(self, state):
        for (i, qBox) in enumerate(self.checkBoxList):
            self.checkBoxList[i].setEnabled(state)


class Dialog:
    def __init__(self, title, info, icon=QMessageBox.Critical):
        msgbox = QMessageBox()
        msgbox.setText(info)
        msgbox.setWindowTitle(title)
        msgbox.setIcon(icon)
        msgbox.setStandardButtons(QMessageBox.Ok)
        reply = msgbox.exec()

        if reply == QMessageBox.Ok:
            return


class CustomDelegate(QStyledItemDelegate):
    def __init__(self, wrap_columns=None):
        super().__init__()
        self.wrap_columns = wrap_columns

    def paint(self, painter, option, index):
        col = index.column()
        text = index.data(Qt.DisplayRole)
        if text and self.wrap_columns:
            if col in self.wrap_columns:
                painter.drawText(option.rect, Qt.TextWrapAnywhere | Qt.AlignVCenter, text)
            else:
                super().paint(painter, option, index)
                return
        else:
            super().paint(painter, option, index)
            return
