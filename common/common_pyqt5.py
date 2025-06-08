import math
import os
import re
import subprocess
import screeninfo
import screeninfo.common
from screeninfo import get_monitors
from PyQt5.QtCore import Qt, QEvent, QRect
from PyQt5.QtWidgets import QDesktopWidget, QComboBox, QLineEdit, QListWidget, QCheckBox, QListWidgetItem, QMessageBox, QStyledItemDelegate, QStyleOptionButton, QStyle, QApplication, QShortcut, QWidget, QTableWidget, QTableView, QLabel
from PyQt5.QtGui import QTextCursor, QFont, QColor, QKeySequence
from PyQt5.Qt import QFontMetrics


def custom_get_monitors():
    try:
        monitors = screeninfo.get_monitors()
    except screeninfo.common.ScreenInfoError:
        monitors = []

        class Monitor:
            def __init__(self, width: int, height: int):
                self.width = width
                self.height = height

        try:
            output = subprocess.check_output("xdpyinfo", shell=True).decode('utf-8').split('\n')

            for line in output:
                if my_match := re.match(r'^\s*dimensions:\s*(\d+)x(\d+)\s*pixels.*', line):
                    width = my_match.group(1)
                    height = my_match.group(2)
                    monitor = Monitor(int(width), int(height))
                    monitors.append(monitor)

        except Exception:
            monitors = [Monitor(1980, 1080)]

    return monitors


get_monitors = custom_get_monitors  # noqa: F811


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
    monitor = get_monitors()[0]

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
            self.view().setMinimumWidth(self.dropDownBoxWidthPixel + int(indicatorPixel))

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

        self.setEnabled(state)

    def setItemsCheckState(self, item_list, state):
        for text in item_list:
            for (i, qBox) in enumerate(self.checkBoxList):
                if qBox.text() == text:
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
    def __init__(self, wrap_columns=None, check_available: bool = False):
        super().__init__()
        self.wrap_columns = wrap_columns
        self.check_available = check_available
        self.icon_column = 3

    def paint(self, painter, option, index):
        col = index.column()
        text = index.data(Qt.DisplayRole)

        if text and self.wrap_columns and col in self.wrap_columns:
            painter.drawText(option.rect, Qt.TextWrapAnywhere | Qt.AlignVCenter, text)
        elif index.column() == self.icon_column and self.check_available:
            checkbox_option = QStyleOptionButton()
            checkbox_option.state = QStyle.State_Enabled | (QStyle.State_On if index.data(Qt.CheckStateRole) == Qt.Checked else QStyle.State_Off)
            checkbox_option.rect = QRect(option.rect.x() + 5, option.rect.y(), 20, option.rect.height())
            QApplication.style().drawControl(QStyle.CE_CheckBox, checkbox_option, painter)

            foreground = index.data(Qt.ForegroundRole)

            if foreground:
                painter.setPen(foreground.color())
            else:
                painter.setPen(QColor(0, 0, 0))

            text = index.data(Qt.DisplayRole)
            painter.drawText(option.rect.adjusted(25, 0, -20, 0), Qt.AlignLeft | Qt.AlignVCenter, text)

            icon = index.data(Qt.DecorationRole)

            if icon:
                icon_size = option.decorationSize
                x = option.rect.right() - icon_size.width()
                y = option.rect.center().y() - icon_size.height() // 2
                icon_rect = (x, y, icon_size.width(), icon_size.height())

                painter.save()
                icon.paint(painter, *icon_rect)
                painter.restore()
        else:
            super().paint(painter, option, index)


class WaitingWindow:
    def __init__(self, message="Loading, please wait"):
        self.worker_process = None
        self.message = message

    def run(self):
        self.worker_process = subprocess.Popen(f'python3 {os.getenv("IFP_INSTALL_PATH")}/tools/waiting_window.py -m "{self.message}"', shell=True)

    def close(self):
        if self.worker_process.poll() is None:
            self.worker_process.terminate()


class TableFilterRow(QWidget):

    def __init__(self, table, model=None, parent=None, filter_columns=None):
        super().__init__(parent)
        self.table = table
        self.setFixedHeight(32)

        # 支持自定义列过滤
        self.filter_columns = filter_columns
        self.filters = {}

        if isinstance(table, QTableWidget):
            self.is_widget = True
            self.model = None
            self.column_count = table.columnCount()
            self.row_count_func = table.rowCount
            self.data_func = lambda row, col: table.item(row, col).text() if table.item(row, col) else ""
            self.set_row_hidden = table.setRowHidden
            self.header_data = lambda col: table.horizontalHeaderItem(col).text() if table.horizontalHeaderItem(col) else f"Column {col}"
        elif isinstance(table, QTableView):
            self.is_widget = False
            self.model = model
            self.column_count = model.columnCount()
            self.row_count_func = model.rowCount
            self.data_func = lambda row, col: model.data(model.index(row, col))
            self.set_row_hidden = table.setRowHidden
            self.header_data = lambda col: model.headerData(col, Qt.Horizontal)
        else:
            raise TypeError("Table must be a QTableView or QTableWidget.")

        if self.filter_columns is None:
            self.filter_columns = list(range(self.column_count))

        self._init_filters()
        self.label = QLabel('* Press <Ctrl+F> to close filter', self)
        self.label.setStyleSheet("QLabel { color : gray; }")
        header = self.table.horizontalHeader()
        header.sectionResized.connect(self.update_filter_positions)
        self.table.horizontalScrollBar().valueChanged.connect(self.update_filter_positions)

        self.update_filter_positions()

        shortcut_parent = parent if parent else self
        self._shortcut = QShortcut(QKeySequence("Ctrl+F"), shortcut_parent)
        self._shortcut.activated.connect(self.toggle_visibility)

        self.show()

    def _init_filters(self):
        self.filters.clear()
        for col in self.filter_columns:
            edit = QLineEdit(self)
            header_text = self.header_data(col)
            edit.setPlaceholderText(str(header_text))
            edit.setFixedHeight(24)
            edit.textChanged.connect(self.apply_filter)
            self.filters[col] = edit

    def update_filter_positions(self):
        header = self.table.horizontalHeader()
        scroll_offset = self.table.horizontalScrollBar().value()
        left_margin = self.table.verticalHeader().width()
        x, w = 0, 0

        for col, edit in self.filters.items():
            x = header.sectionPosition(col) - scroll_offset + left_margin
            w = header.sectionSize(col)
            edit.setFixedWidth(w)
            edit.move(x, 4)

        self.label.move(x+w+10, 10)

    def apply_filter(self):
        patterns = {}
        for col, edit in self.filters.items():
            text = edit.text()
            if text:
                try:
                    patterns[col] = re.compile(text, re.IGNORECASE)
                except re.error:
                    patterns[col] = None
            else:
                patterns[col] = None

        row_count = self.row_count_func()
        for row in range(row_count):
            visible = True
            for col, pattern in patterns.items():
                if pattern:
                    value = self.data_func(row, col)
                    if not pattern.search(str(value)):
                        visible = False
                        break
            self.set_row_hidden(row, not visible)

    def toggle_visibility(self):
        if self.isVisible():
            self.hide()
            for row in range(self.row_count_func()):
                self.set_row_hidden(row, False)
            for edit in self.filters.values():
                edit.clear()
        else:
            self.show()
            self.update_filter_positions()
            if self.filters:
                first = next(iter(self.filters.values()))
                first.setFocus()
