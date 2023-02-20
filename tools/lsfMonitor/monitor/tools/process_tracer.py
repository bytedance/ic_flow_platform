# -*- coding: utf-8 -*-
################################
# File Name   : process_tracer.py
# Author      : liyanqing
# Created On  : 2021-11-30 00:00:00
# Description :
################################
import os
import re
import sys
import argparse

from PyQt5.QtWidgets import QApplication, QMainWindow, QTabWidget, QFrame, QGridLayout, QTableWidget, QTableWidgetItem, QHeaderView, QAction, qApp, QMessageBox
from PyQt5.QtCore import QTimer

sys.path.insert(0, str(os.environ['LSFMONITOR_INSTALL_PATH']) + '/monitor')
from common import common
from common import common_lsf
from common import common_pyqt5

os.environ['PYTHONUNBUFFERED'] = '1'


def read_args():
    """
    Read in arguments.
    """
    parser = argparse.ArgumentParser()

    parser.add_argument('-j', '--job',
                        default='',
                        help='Specify the LSF jobid you want to trace on remote host.')
    parser.add_argument('-p', '--pid',
                        default='',
                        help='Specify the pid you want to trace on local host.')

    args = parser.parse_args()

    if (not args.job) and (not args.pid):
        common.print_error('*Error*: "--job" or "--pid" must be specified.')
        sys.exit(1)

    return (args.job, args.pid)


class ProcessTracer(QMainWindow):
    def __init__(self, job, pid):
        super().__init__()
        self.job = job
        self.pid = pid

        self.preprocess()
        self.init_ui()

    def preprocess(self):
        self.job_dic = {}
        self.pid_list = []

        if self.job:
            (self.job_dic, self.pid_list) = self.check_job(self.job)
        elif self.pid:
            self.pid_list = self.check_pid(self.pid)

    def check_job(self, job):
        command = 'bjobs -UF ' + str(job)
        job_dic = common_lsf.get_lsf_bjobs_uf_info(command)

        if job_dic[job]['status'] != 'RUN':
            common.print_error('*Error*: Job "' + str(job) + '" is not running, cannot get process status.')
            sys.exit(1)
        else:
            if not job_dic[job]['pids']:
                common.print_error('*Error*: Not find PIDs information for job "' + str(job) + '".')
                sys.exit(1)

        return (job_dic, job_dic[job]['pids'])

    def check_pid(self, pid):
        pid_list = []
        command = 'pstree -p ' + str(pid)

        (return_code, stdout, stderr) = common.run_command(command)

        for line in str(stdout, 'utf-8').split('\n'):
            line = line.strip()

            if re.findall(r'\((\d+)\)', line):
                tmp_pid_list = re.findall(r'\((\d+)\)', line)

                if tmp_pid_list:
                    pid_list.extend(tmp_pid_list)

        if not pid_list:
            common.print_error('*Error*: No valid pid was found.')
            sys.exit(1)

        return (pid_list)

    def get_process_info(self):
        process_dic = {
                       'user': [],
                       'pid': [],
                       'cpu': [],
                       'mem': [],
                       'stat': [],
                       'started': [],
                       'command': [],
                      }

        command = 'ps -o ruser=userForLongName -o pid,%cpu,%mem,stat,start,command -f' + ','.join(self.pid_list)

        if self.job:
            bsub_command = self.get_bsub_command()
            command = str(bsub_command) + " '" + str(command) + "'"

        (return_code, stdout, stderr) = common.run_command(command)

        for line in str(stdout, 'utf-8').split('\n'):
            line = line.strip()

            if re.match(r'^(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+([a-zA-Z]{3} \d{2}|\d{2}:\d{2}:\d{2})\s(.+)$', line):
                my_match = re.match(r'^(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+([a-zA-Z]{3} \d{2}|\d{2}:\d{2}:\d{2})\s(.+)$', line)
                user = my_match.group(1)
                pid = my_match.group(2)
                cpu = my_match.group(3)
                mem = my_match.group(4)
                stat = my_match.group(5)
                started = my_match.group(6)
                command = my_match.group(7)

                process_dic['user'].append(user)
                process_dic['pid'].append(pid)
                process_dic['cpu'].append(cpu)
                process_dic['mem'].append(mem)
                process_dic['stat'].append(stat)
                process_dic['started'].append(started)
                process_dic['command'].append(command)
            else:
                continue

        return (process_dic)

    def get_bsub_command(self):
        bsub_command = 'bsub -Is '
        queue = self.job_dic[self.job]['queue']
        started_on = self.job_dic[self.job]['started_on']

        if queue:
            bsub_command = str(bsub_command) + ' -q ' + str(queue)

        if started_on:
            started_on_list = started_on.split()
            bsub_command = str(bsub_command) + ' -m ' + str(started_on_list[0])

        return (bsub_command)

    def init_ui(self):
        # Gen menubar
        self.gen_menubar()

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
        if self.job:
            self.setWindowTitle('Process Tracer (job:' + str(self.job) + ')')
        elif self.pid:
            self.setWindowTitle('Process Tracer (pid:' + str(self.pid) + ')')

        self.resize(1200, 300)
        common_pyqt5.center_window(self)

    def gen_menubar(self):
        menubar = self.menuBar()

        # File
        exit_action = QAction('Exit', self)
        exit_action.triggered.connect(qApp.quit)

        file_menu = menubar.addMenu('File')
        file_menu.addAction(exit_action)

        # Setup
        fresh_action = QAction('Fresh', self)
        fresh_action.triggered.connect(self.gen_main_table)
        self.periodic_fresh_timer = QTimer(self)
        periodic_fresh_action = QAction('Periodic Fresh (1 min)', self, checkable=True)
        periodic_fresh_action.triggered.connect(self.periodic_fresh)

        setup_menu = menubar.addMenu('Setup')
        setup_menu.addAction(fresh_action)
        setup_menu.addAction(periodic_fresh_action)

        # Help
        about_action = QAction('About process_tracer', self)
        about_action.triggered.connect(self.show_about)

        help_menu = menubar.addMenu('Help')
        help_menu.addAction(about_action)

    def periodic_fresh(self, state):
        """
        Fresh the GUI every 60 seconds.
        """
        if state:
            self.periodic_fresh_timer.timeout.connect(self.gen_main_table)
            self.periodic_fresh_timer.start(60000)
        else:
            self.periodic_fresh_timer.stop()

    def show_about(self):
        """
        Show process_tracer about information.
        """
        about_message = 'process_tracer is used to get process tree and trace pid status.'
        QMessageBox.about(self, 'About process_tracer', about_message)

    def gen_main_frame(self):
        self.main_table = QTableWidget(self.main_frame)

        # Grid
        main_frame_grid = QGridLayout()
        main_frame_grid.addWidget(self.main_table, 0, 0)
        self.main_frame.setLayout(main_frame_grid)

        self.gen_main_table()

    def gen_main_table(self):
        self.main_table.setShowGrid(True)
        self.main_table.setColumnCount(0)
        self.main_table.setColumnCount(7)
        self.main_table.setHorizontalHeaderLabels(['USER', 'PID', '%CPU', '%MEM', 'STAT', 'STARTED', 'COMMAND'])

        # Set column width
        self.main_table.setColumnWidth(1, 70)
        self.main_table.setColumnWidth(2, 60)
        self.main_table.setColumnWidth(3, 60)
        self.main_table.setColumnWidth(4, 60)
        self.main_table.setColumnWidth(5, 80)
        self.main_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.Stretch)

        # Set click behavior
        self.main_table.itemClicked.connect(self.main_tab_check_click)

        # Set item
        self.process_dic = self.get_process_info()
        self.main_table.setRowCount(len(self.process_dic['pid']))

        title_list = ['user', 'pid', 'cpu', 'mem', 'stat', 'started', 'command']

        for (row, pid) in enumerate(self.process_dic['pid']):
            for (column, title) in enumerate(title_list):
                item = QTableWidgetItem()
                item.setText(self.process_dic[title][row])
                self.main_table.setItem(row, column, item)

    def main_tab_check_click(self, item=None):
        if item is not None:
            if item.column() == 1:
                current_row = self.main_table.currentRow()
                pid = self.main_table.item(current_row, 1).text()

                command = 'xterm -e "strace -tt -p ' + str(pid) + '"'

                if self.job:
                    bsub_command = self.get_bsub_command()
                    command = str(bsub_command) + " '" + str(command) + "'"

                os.system(command)


################
# Main Process #
################
def main():
    (job, pid) = read_args()
    app = QApplication(sys.argv)
    my_process_tracer = ProcessTracer(job, pid)
    my_process_tracer.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
