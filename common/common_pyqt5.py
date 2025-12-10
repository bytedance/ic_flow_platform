import math
import os
import re
import signal
import subprocess
import sys
import time
from collections import deque

import screeninfo
import screeninfo.common
from screeninfo import get_monitors
from PyQt5.QtCore import Qt, QEvent, QRect, QMutex, QTimer, QMutexLocker
from PyQt5.QtWidgets import QDesktopWidget, QComboBox, QLineEdit, QListWidget, QCheckBox, QListWidgetItem, QMessageBox, QStyledItemDelegate, QStyleOptionButton, QStyle, QApplication, QShortcut, QWidget, QTableWidget, QTableView, QLabel, QTextEdit
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
    def __init__(self, wrap_columns=None, check_available: bool = False, icon_columns=None, table_view=None):
        super().__init__()
        self.wrap_columns = wrap_columns
        self.check_available = check_available
        self.icon_columns = icon_columns
        self.table_view = table_view

    def editorEvent(self, event, model, option, index):
        if (self.icon_columns and index.column() in self.icon_columns and
                index.column() == 3 and event.type() == QEvent.MouseButtonRelease):

            checkbox_rect = QRect(option.rect.x() + 5, option.rect.y(), 20, option.rect.height())
            if checkbox_rect.contains(event.pos()):
                current_state = index.data(Qt.CheckStateRole)
                new_state = Qt.Unchecked if current_state == Qt.Checked else Qt.Checked
                return model.setData(index, new_state, Qt.CheckStateRole)

        return super().editorEvent(event, model, option, index)

    def paint(self, painter, option, index):
        col = index.column()
        text = index.data(Qt.DisplayRole)

        if not option.state & QStyle.State_Selected:
            row = index.row()
            span_group = 0
            current_row = 0

            while current_row <= row:
                span_size = self.table_view.rowSpan(current_row, 0)
                if span_size == 0:
                    span_size = 1

                if current_row <= row < current_row + span_size:
                    break

                span_group += 1
                current_row += span_size

            if span_group % 2 == 0:
                painter.fillRect(option.rect, QColor(255, 255, 255))
            else:
                painter.fillRect(option.rect, QColor(250, 250, 250))

        if text and self.wrap_columns and col in self.wrap_columns:
            painter.drawText(option.rect, Qt.TextWrapAnywhere | Qt.AlignVCenter, text)
        elif self.icon_columns and index.column() in self.icon_columns:
            if index.column() == 3:
                foreground = index.data(Qt.ForegroundRole)
                checkbox_option = QStyleOptionButton()
                checkbox_option.state = QStyle.State_Enabled | (QStyle.State_On if index.data(Qt.CheckStateRole) == Qt.Checked else QStyle.State_Off)
                checkbox_option.rect = QRect(option.rect.x() + 5, option.rect.y(), 20, option.rect.height())
                QApplication.style().drawControl(QStyle.CE_CheckBox, checkbox_option, painter)

                if foreground:
                    painter.setPen(foreground.color())
                else:
                    painter.setPen(QColor(0, 0, 0))

            if index.column() == 4:
                foreground = index.data(Qt.ForegroundRole)

                if foreground:
                    painter.setPen(foreground.color())
                else:
                    painter.setPen(QColor(0, 0, 0))

            text = index.data(Qt.DisplayRole)

            if index.column() == 3:
                painter.drawText(option.rect.adjusted(25, 0, -20, 0), Qt.AlignLeft | Qt.AlignVCenter, text)
            else:
                painter.drawText(option.rect.adjusted(0, 0, 0, 0), Qt.AlignLeft | Qt.AlignVCenter, text)

            icon = index.data(Qt.DecorationRole)

            if icon:
                icon_size = option.decorationSize
                x = option.rect.right() - icon_size.width()
                y = option.rect.center().y() - icon_size.height() // 2
                icon_rect = (x, y, icon_size.width(), icon_size.height())

                painter.save()
                icon.paint(painter, *icon_rect)
                painter.restore()

            painter.setPen(QColor(0, 0, 0))
        else:
            super().paint(painter, option, index)


class WaitingWindow:
    def __init__(self, message="Loading, please wait"):
        self.worker_process = None
        self.message = message

    def __enter__(self):
        self.run()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def run(self):
        try:
            cmd = [
                sys.executable or "python3",
                os.path.join(os.getenv("IFP_INSTALL_PATH"), "tools", "waiting_window.py"),
                "-m", self.message
            ]

            self.worker_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid
            )

            return True

        except Exception:
            return False

    def close(self):
        if not self.worker_process or self.worker_process.poll() is not None:
            return

        try:
            os.killpg(os.getpgid(self.worker_process.pid), signal.SIGTERM)

            try:
                self.worker_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(os.getpgid(self.worker_process.pid), signal.SIGKILL)
                self.worker_process.wait()

        except Exception as e:
            print(f"关闭等待窗口时出错: {e}")

        finally:
            self.worker_process = None


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


class BatchMessageBox(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.message_queue = deque()
        self.mutex = QMutex()

        self.batch_timer = QTimer()
        self.batch_timer.timeout.connect(self.flush_messages)
        self.batch_timer.setSingleShot(True)

        self.update_interval = 50
        self.max_queue_size = 1000

    def add_message(self, message, color='black', html=False):
        with QMutexLocker(self.mutex):
            if len(self.message_queue) >= self.max_queue_size:
                self.message_queue.popleft()

            self.message_queue.append({
                'message': message,
                'color': color,
                'html': html,
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
            })

        if not self.batch_timer.isActive():
            self.batch_timer.start(self.update_interval)

    def flush_messages(self):
        messages_to_process = []

        with QMutexLocker(self.mutex):
            while self.message_queue:
                messages_to_process.append(self.message_queue.popleft())

        if not messages_to_process:
            return

        self.blockSignals(True)

        try:
            cursor = self.textCursor()
            cursor.movePosition(QTextCursor.End)
            self.setTextCursor(cursor)

            for msg_info in messages_to_process:
                self._insert_message(msg_info)

            self.ensureCursorVisible()

        finally:
            self.blockSignals(False)

    def _insert_message(self, msg_info):
        if msg_info['html']:
            html_text = f"[{msg_info['timestamp']}] {msg_info['message']}<br>"
            self.insertHtml(html_text)
        else:
            text = f"[{msg_info['timestamp']}] {msg_info['message']}\n"
            self.insertPlainText(text)
