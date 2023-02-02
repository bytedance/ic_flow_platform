#!EXPECTED_PYTHON
# -*- coding: utf-8 -*-
################################
# File Name   : process_tracer.py
# Author      : liyanqing
# Created On  : 2021-11-30 17:25:47
# Description :
################################
import os
import sys
import argparse

from PyQt5.QtWidgets import QApplication, QMainWindow, QTabWidget, QFrame, QGridLayout, QLabel
from PyQt5.QtCore import Qt

if 'LSFMONITOR_INSTALL_PATH' not in os.environ:
    os.environ['LSFMONITOR_INSTALL_PATH'] = 'LSFMONITOR_INSTALL_PATH_STRING'

sys.path.insert(0, str(os.environ['LSFMONITOR_INSTALL_PATH']) + '/monitor')
from common import pyqt5_common

os.environ['PYTHONUNBUFFERED'] = '1'


def read_args():
    """
    Read in arguments.
    """
    parser = argparse.ArgumentParser()

    parser.add_argument('-t', '--title',
                        default='Message',
                        help='Specify message title, default is "Message".')
    parser.add_argument('-m', '--message',
                        required=True,
                        default='',
                        help='Required argument, specified message (text).')

    args = parser.parse_args()

    return(args.title, args.message)


class ShowMessage(QMainWindow):
    def __init__(self, title, message):
        super().__init__()
        self.title = title
        self.message = message

        self.init_ui()

    def init_ui(self):
        # Add main_tab
        self.main_tab = QTabWidget(self)
        self.setCentralWidget(self.main_tab)

        self.main_frame = QFrame(self.main_tab)

        # Grid
        main_grid = QGridLayout()
        main_grid.addWidget(self.main_frame, 0, 0)
        self.main_tab.setLayout(main_grid)

        # Generate main_table
        self.gen_main_frame()

        # Show main window
        self.setWindowTitle(self.title)
        self.resize(400, 50)
        pyqt5_common.center_window(self)

    def gen_main_frame(self):
        self.message_label = QLabel(self.main_frame)
        self.message_label.setText(self.message)
        self.message_label.setAlignment(Qt.AlignCenter)

        # Grid
        main_frame_grid = QGridLayout()
        main_frame_grid.addWidget(self.message_label, 0, 0)
        self.main_frame.setLayout(main_frame_grid)


################
# Main Process #
################
def main():
    (title, message) = read_args()
    app = QApplication(sys.argv)
    my_show_message = ShowMessage(title, message)
    my_show_message.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
