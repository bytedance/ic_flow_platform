# -*- coding: utf-8 -*-
################################
# File Name   : view_checklist_report.py
# Author      : liyanqing.1987
# Created On  : 2021-12-22 17:04:30
# Description :
################################
import os
import re
import sys
import argparse
from threading import Thread
from PyQt5.QtWidgets import QApplication, QWidget, QMainWindow, QTabWidget, QTableWidget, QTableWidgetItem, QFrame, QGridLayout, QPushButton, QHeaderView
from PyQt5.QtGui import QBrush
from PyQt5.QtCore import Qt

sys.path.append(str(os.environ['IFP_INSTALL_PATH']) + '/common')
import common
import common_pyqt5

os.environ['PYTHONUNBUFFERED'] = '1'
CWD = os.getcwd()


def read_args():
    """
    Read in arguments.
    """
    parser = argparse.ArgumentParser()

    parser.add_argument('-i', '--input',
                        required=True,
                        default='',
                        help='Specify the checklist report, default is "./file_check.rpt" or "file_check/file_check.rpt".')

    args = parser.parse_args()

    if args.input == '':
        checklist_file = str(CWD) + '/file_check.rpt'

        if os.path.exists(checklist_file):
            args.input = checklist_file
        else:
            checklist_file = str(CWD) + '/file_check/file_check.rpt'

            if os.path.exists(checklist_file):
                args.input = checklist_file
            else:
                print('*Error*: No checklist report is specified.')
                sys.exit(1)
    else:
        if (not os.path.exists(args.input)) or (not os.path.isfile(args.input)):
            print('*Error*: ' + str(args.input) + ': No such file.')
            sys.exit(1)

    return(args.input)


def parse_checklist_report(checklist_report):
    """
    Parse checklist report.
    Every item check result is saved as a dict.
    All item dict are saved as a list.
    [
     {'result' : <result>; 'description' : <description>; 'log_file' : <log_file>},
     ...,
    ]
    """
    checklist_dic_list = []

    with open(checklist_report, 'r') as CR:
        for line in CR.readlines():
            if re.match('^\s*PASSED\s*:\s*(.+?)\s*$', line):
                my_match = re.match('^\s*PASSED\s*:\s*(.+?)\s*$', line)
                description = my_match.group(1)

                item_dic = {'result': 'PASSED',
                            'description': description,
                            'log_file': ''}

                checklist_dic_list.append(item_dic)
            elif re.match('^\s*(.+?)\s*:\s*(.+?)\s+\(details please see (.*)\)\s*$', line):
                my_match = re.match('^\s*(.+?)\s*:\s*(.+?)\s+\(details please see (.*)\)\s*$', line)
                result = my_match.group(1)
                description = my_match.group(2)
                log_file = my_match.group(3)

                item_dic = {'result': result,
                            'description': description,
                            'log_file': log_file}

                checklist_dic_list.append(item_dic)

    return(checklist_dic_list)


class MainWindow(QMainWindow):
    def __init__(self, checklist_report):
        super().__init__()
        self.checklist_report = checklist_report
        self.checklist_dic_list = parse_checklist_report(checklist_report)

        self.init_ui()

    def init_ui(self):
        self.gen_main_tab()
        self.resize(685, 350)
        common_pyqt5.move_gui_to_window_center(self)
        self.setWindowTitle(self.checklist_report)

    def gen_main_tab(self):
        self.main_tab = QTabWidget(self)
        self.setCentralWidget(self.main_tab)

        self.main_frame = QFrame(self.main_tab)

        # Grid
        main_tab_grid = QGridLayout()
        main_tab_grid.addWidget(self.main_frame, 0, 0)
        self.main_tab.setLayout(main_tab_grid)

        self.gen_main_frame()

    def gen_main_frame(self):
        self.main_table = QTableWidget(self.main_frame)

        # Grid
        main_frame_grid = QGridLayout()
        main_frame_grid.addWidget(self.main_table, 0, 0)
        self.main_frame.setLayout(main_frame_grid)

        self.gen_main_table()

    def gen_main_table(self):
        self.main_table.setShowGrid(True)
        self.main_table.setColumnCount(3)
        self.main_table_title_list = ['Result', 'Description', 'Detail']
        self.main_table.setHorizontalHeaderLabels(self.main_table_title_list)
        self.main_table.setColumnWidth(0, 70)
        self.main_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.main_table.setColumnWidth(2, 70)
        self.main_table.setRowCount(len(self.checklist_dic_list))

        for (row, checklist_dic) in enumerate(self.checklist_dic_list):
            result = checklist_dic['result']
            item = QTableWidgetItem()
            item.setText(result)

            if result == 'PASSED':
                item.setForeground(QBrush(Qt.green))
            elif result == 'FAILED':
                item.setForeground(QBrush(Qt.red))
            elif result == 'REVIEW':
                item.setForeground(QBrush(Qt.magenta))

            self.main_table.setItem(row, 0, item)

            description = checklist_dic['description']
            self.main_table.setItem(row, 1, QTableWidgetItem(description))

            log_file = checklist_dic['log_file']

            if os.path.exists(log_file):
                self.main_table.setCellWidget(row, 2, self.button_for_check_view(log_file))

    def button_for_check_view(self, log_file):
        widget = QWidget()

        view_button = QPushButton('view')
        view_button.setStyleSheet('text-align : center; backgroud-color : LightCoral;')
        view_button.clicked.connect(lambda: self.show_checklist(log_file))

        # Grid
        widget_grid = QGridLayout()
        widget_grid.addWidget(view_button, 0, 0)
        widget.setLayout(widget_grid)

        return(widget)

    def open_log_file(self, log_file):
        command = '/usr/bin/xterm -T ' + str(log_file) + ' -e "/usr/bin/vim ' + str(log_file) + '"'
        (returnCode, stdout, stderr) = common.run_command(command)

        if returnCode != 0:
            self.message_text.insertPlainText('*Error*: Failed on showing check item log file "' + str(log_file) + '": ' + str(stderr, 'utf-8'))

    def show_checklist(self, log_file):
        thread = Thread(target=self.open_log_file, args=(log_file,))
        thread.start()


################
# Main Process #
################
def main():
    (checklist_report) = read_args()

    app = QApplication(sys.argv)
    mw = MainWindow(checklist_report)
    mw.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
