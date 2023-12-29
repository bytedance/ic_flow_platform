from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QDesktopWidget, QComboBox, QLineEdit, QListWidget, QCheckBox, QListWidgetItem, QAction, QMessageBox, QHeaderView, QStyledItemDelegate
from PyQt5.QtGui import QTextCursor


def center_window(window):
    """
    Move the input GUI window into the center of the computer windows.
    """
    qr = window.frameGeometry()
    cp = QDesktopWidget().availableGeometry().center()
    qr.moveCenter(cp)
    window.move(qr.topLeft())


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
        self.qLineEdit.setReadOnly(True)
        self.setLineEdit(self.qLineEdit)

        # self.checkBoxList is used to save QCheckBox items.
        self.checkBoxList = []

    def addCheckBoxItem(self, text):
        """
        Add QCheckBox format item into QListWidget(QComboCheckBox).
        """
        qItem = QListWidgetItem(self.qListWidget)
        qBox = QCheckBox(text)
        qBox.stateChanged.connect(self.updateLineEdit)
        self.checkBoxList.append(qBox)
        self.qListWidget.setItemWidget(qItem, qBox)

    def addCheckBoxItems(self, text_list):
        """
        Add multi QCheckBox format items.
        """
        for text in text_list:
            self.addCheckBoxItem(text)

    def updateLineEdit(self):
        """
        Update QComboCheckBox show message with self.qLineEdit.
        """
        selectedItemString = self.separator.join(self.selectedItems().values())
        self.qLineEdit.setReadOnly(False)
        self.qLineEdit.clear()
        self.qLineEdit.setText(selectedItemString)
        self.qLineEdit.setReadOnly(True)

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
