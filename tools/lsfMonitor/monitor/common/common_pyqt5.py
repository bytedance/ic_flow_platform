import re
import math
import datetime
import screeninfo

from PyQt5.QtWidgets import QDesktopWidget, QComboBox, QLineEdit, QListWidget, QCheckBox, QListWidgetItem, QCompleter
from PyQt5.QtGui import QTextCursor, QFont
from PyQt5.Qt import QFontMetrics
from PyQt5.QtCore import Qt, QEvent, QObject
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5 import NavigationToolbar2QT
from matplotlib.dates import num2date


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


def get_completer(item_list):
    """
    Instantiate and config QCompleter.
    """
    completer_ins = QCompleter(item_list)

    # Enable Qt.MatchContains mode (just like re.search()), not Qt.MatchStartsWith or Qt.MatchEndsWith.
    completer_ins.setFilterMode(Qt.MatchContains)
    # Match upper/lower case.
    completer_ins.setCaseSensitivity(Qt.CaseInsensitive)

    # Adjust the appropriate size of the item.
    if item_list:
        list_view = completer_ins.popup()
        max_length = max(len(item) for item in item_list)
        popup_width = list_view.fontMetrics().width('w' * max_length)
        list_view.setFixedWidth(popup_width)

    return completer_ins


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


class ComboBoxEventFilter(QObject):
    def __init__(self, comboBox, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.comboBox = comboBox
        self.droppedDown = False

    def eventFilter(self, obj, event):
        # MouseButtonPress
        if event.type() == 3:
            self.droppedDown = True
        # MouseLeave
        elif event.type() == 11:
            self.droppedDown = False

        return super().eventFilter(obj, event)


class QComboCheckBox(QComboBox):
    """
    QComboCheckBox is a QComboBox with checkbox.
    """
    def __init__(self, parent):
        super(QComboCheckBox, self).__init__(parent)

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

        self.eventFilter = ComboBoxEventFilter(self)
        self.view().viewport().installEventFilter(self.eventFilter)

    def hidePopup(self):
        if self.eventFilter.droppedDown:
            return
        else:
            return super().hidePopup()

    def validQLineEditValue(self):
        """
        Make sure value of self.qLineEdit always match selected items.
        """
        selectedItemString = ' '.join(self.selectedItems().values())

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
        self.updateDropDownBoxHeight()

    def qBoxStateChanged(self, checkState):
        """
        Post process for qBox state change.
        """
        itemText = self.sender().text()

        self.updateItemSelectedState(itemText, checkState)
        self.updateLineEdit()

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

    def updateLineEdit(self):
        """
        Update QComboCheckBox show message with self.qLineEdit.
        """
        selectedItemString = ' '.join(self.selectedItems().values())
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
        indicatorPixel = int(qBox.iconSize().width() * 1.4)

        if textPixel > self.dropDownBoxWidthPixel:
            self.dropDownBoxWidthPixel = textPixel
            self.view().setMinimumWidth(self.dropDownBoxWidthPixel + indicatorPixel)

    def updateDropDownBoxHeight(self):
        fm = QFontMetrics(QFont())
        fontPixel = fm.height() + 2
        self.setStyleSheet(f"""
            QComboBox QAbstractItemView::item {{
                min-height: {fontPixel}px;
                padding: 0px;
                margin: 0px;
            }}
        """)

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


class FigureCanvasQTAgg(FigureCanvasQTAgg):
    """
    Generate a new figure canvas.
    """
    def __init__(self):
        self.figure = Figure()
        self.axes = None
        super().__init__(self.figure)


class NavigationToolbar2QT(NavigationToolbar2QT):
    """
    Enhancement for NavigationToolbar2QT, can get and show label value.
    """
    def __init__(self, canvas, parent, coordinates=True, x_is_date=True):
        super().__init__(canvas, parent, coordinates)
        self.x_is_date = x_is_date

    @staticmethod
    def bisection(event_xdata, xdata_list):
        xdata = None
        index = None
        lower = 0
        upper = len(xdata_list) - 1
        bisection_index = (upper - lower) // 2

        if xdata_list:
            if event_xdata > xdata_list[upper]:
                xdata = xdata_list[upper]
                index = upper
            elif (event_xdata < xdata_list[lower]) or (len(xdata_list) <= 2):
                xdata = xdata_list[lower]
                index = lower
            elif event_xdata in xdata_list:
                xdata = event_xdata
                index = xdata_list.index(event_xdata)

            while xdata is None:
                if upper - lower == 1:
                    if event_xdata - xdata_list[lower] <= xdata_list[upper] - event_xdata:
                        xdata = xdata_list[lower]
                        index = lower
                    else:
                        xdata = xdata_list[upper]
                        index = upper

                    break

                if event_xdata > xdata_list[bisection_index]:
                    lower = bisection_index
                elif event_xdata < xdata_list[bisection_index]:
                    upper = bisection_index

                bisection_index = (upper - lower) // 2 + lower

        return xdata, index

    def _mouse_event_to_message(self, event):
        if event.inaxes and event.inaxes.get_navigate():
            try:
                if self.x_is_date:
                    event_xdata = num2date(event.xdata).strftime('%Y,%m,%d,%H,%M,%S')
                else:
                    event_xdata = event.xdata
            except (ValueError, OverflowError):
                pass
            else:
                if self.x_is_date and (len(event_xdata.split(',')) == 6):
                    (year, month, day, hour, minute, second) = event_xdata.split(',')
                    event_xdata = datetime.datetime(int(year), int(month), int(day), int(hour), int(minute), int(second))

                xdata_list = list(self.canvas.figure.gca().get_lines()[0].get_xdata())
                (xdata, index) = self.bisection(event_xdata, sorted(xdata_list))

                if xdata is not None:
                    info_list = []

                    for line in self.canvas.figure.gca().get_lines():
                        label = line.get_label()
                        ydata_string = line.get_ydata()
                        ydata_list = list(ydata_string)
                        ydata = ydata_list[index]

                        info_list.append('%s=%s' % (label, ydata))

                    info_string = '  '.join(info_list)

                    if self.x_is_date:
                        xdata_string = xdata.strftime('%Y-%m-%d %H:%M:%S')
                        xdata_string = re.sub(r' 00:00:00', '', xdata_string)
                        info_string = '[%s]\n%s' % (xdata_string, info_string)

                    return info_string
        return ''
