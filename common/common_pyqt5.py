from PyQt5.QtWidgets import QDesktopWidget
from PyQt5.QtGui import QTextCursor


def move_gui_to_window_center(GUI):
    """
    Move specified GUI to the window center.
    """
    FG = GUI.frameGeometry()
    CENTER = QDesktopWidget().availableGeometry().center()
    FG.moveCenter(CENTER)
    GUI.move(FG.topLeft())


def set_text_cursor_position(textEdit_item, position='end'):
    """
    For QTextEdit widget, set cursor postion ('start' or 'end').
    """
    CURSOR = textEdit_item.textCursor()

    if position == 'start':
        CURSOR.movePosition(QTextCursor.Start)
    elif position == 'end':
        CURSOR.movePosition(QTextCursor.End)

    textEdit_item.setTextCursor(CURSOR)
    textEdit_item.ensureCursorVisible()
