# -*- coding: utf-8 -*-

import os
import re
import sys
import stat
import copy
import time
import getpass
import datetime
import argparse

from PyQt5.QtWidgets import QApplication, QWidget, QMainWindow, QAction, qApp, QTextEdit, QTabWidget, QFrame, QGridLayout, QTableWidget, QTableWidgetItem, QPushButton, QLabel, QMessageBox, QLineEdit, QComboBox, QHeaderView, QDateEdit, QFileDialog, QMenu
from PyQt5.QtGui import QIcon, QBrush, QFont
from PyQt5.QtCore import Qt, QThread, QDate

sys.path.append(str(os.environ['LSFMONITOR_INSTALL_PATH']) + '/monitor')
from common import common
from common import common_lsf
from common import common_license
from common import common_pyqt5
from common import common_sqlite3
from conf import config

# Import local config file if exists.
local_config_dir = str(os.environ['HOME']) + '/.lsfMonitor/conf'
local_config = str(local_config_dir) + '/config.py'

if os.path.exists(local_config):
    sys.path.append(local_config_dir)
    import config

os.environ['PYTHONUNBUFFERED'] = '1'
VERSION = 'V1.5'
VERSION_DATE = '2024.06.14'

# Solve some unexpected warning message.
if 'XDG_RUNTIME_DIR' not in os.environ:
    user = getpass.getuser()
    os.environ['XDG_RUNTIME_DIR'] = '/tmp/runtime-' + str(user)

    if not os.path.exists(os.environ['XDG_RUNTIME_DIR']):
        os.makedirs(os.environ['XDG_RUNTIME_DIR'])

    os.chmod(os.environ['XDG_RUNTIME_DIR'], stat.S_IRWXU+stat.S_IRWXG+stat.S_IRWXO)


def read_args():
    """
    Read arguments.
    """
    parser = argparse.ArgumentParser()

    parser.add_argument("-j", "--jobid",
                        type=int,
                        help='Specify the jobid which show it\'s information on "JOB" tab.')
    parser.add_argument("-u", "--user",
                        default='',
                        help='Specify the user show how\'s job information on "JOBS" tab.')
    parser.add_argument("-f", "--feature",
                        default='',
                        help='Specify license feature which you want to see on "LICENSE" tab.')
    parser.add_argument("-t", "--tab",
                        default='',
                        choices=['JOB', 'JOBS', 'HOSTS', 'QUEUES', 'LOAD', 'UTILIZATION', 'LICENSE'],
                        help='Specify current tab, default is "JOBS" tab.')
    parser.add_argument("-dl", "--disable_license",
                        action='store_true',
                        default=False,
                        help='Disable license check function.')

    args = parser.parse_args()

    # Make sure specified job exists.
    if args.jobid:
        if not args.tab:
            args.tab = 'JOB'

        command = 'bjobs -w ' + str(args.jobid)
        job_dic = common_lsf.get_bjobs_info(command)

        if not job_dic:
            args.jobid = ''

    # Set default tab for args.feature.
    if args.feature and (not args.tab):
        args.tab = 'LICENSE'

    # Set default tab for args.user.
    if args.user and (not args.tab):
        args.tab = 'JOBS'

    # Set default tab.
    if not args.tab:
        args.tab = 'JOBS'

    return args.jobid, args.user, args.feature, args.tab, args.disable_license


class MainWindow(QMainWindow):
    """
    Main window of lsfMonitor.
    """
    def __init__(self, specified_job, specified_user, specified_feature, specified_tab, disable_license):
        super().__init__()

        # Check cluster info.
        cluster = self.check_cluster_info()

        # Set db_path.
        self.db_path = str(config.db_path) + '/monitor'

        if cluster and os.path.exists(str(config.db_path) + '/' + str(cluster)):
            self.db_path = str(config.db_path) + '/' + str(cluster)

        # Init variables.
        self.specified_job = specified_job
        self.specified_user = specified_user
        self.specified_feature = specified_feature
        self.disable_license = disable_license

        self.lsf_unit_for_limits = common_lsf.get_lsf_unit_for_limits()

        # Enable detail information on QUEUE/UTILIZATION tab.
        self.enable_queue_detail = False
        self.enable_utilization_detail = False

        # Init LSF information related variables.
        self.bhosts_dic = {}
        self.lsload_dic = {}
        self.queues_dic = {}
        self.lshosts_dic = {}
        self.queue_host_dic = {}
        self.host_queue_dic = {}
        self.bhosts_load_dic = {}

        # Set self.lsf_info_dic for how to get LSF information.
        self.lsf_info_dic = {'bhosts': {'exec_cmd': 'self.bhosts_dic = common_lsf.get_bhosts_info()', 'update_second': 0},
                             'lsload': {'exec_cmd': 'self.lsload_dic = common_lsf.get_lsload_info()', 'update_second': 0},
                             'bqueues': {'exec_cmd': 'self.queues_dic = common_lsf.get_bqueues_info()', 'update_second': 0},
                             'busers': {'exec_cmd': 'self.users_dic = common_lsf.get_busers_info()', 'update_second': 0},
                             'lshosts': {'exec_cmd': 'self.lshosts_dic = common_lsf.get_lshosts_info()', 'update_second': 0},
                             'queue_host': {'exec_cmd': 'self.queue_host_dic = common_lsf.get_queue_host_info()', 'update_second': 0},
                             'host_queue': {'exec_cmd': 'self.host_queue_dic = common_lsf.get_host_queue_info()', 'update_second': 0},
                             'bhosts_load': {'exec_cmd': 'self.bhosts_load_dic = common_lsf.get_bhosts_load_info()', 'update_second': 0}}

        # Get license information.
        self.license_dic = {}
        self.license_dic_second = 0
        self.get_license_dic()

        # Generate GUI.
        self.init_ui()

        # Switch tab.
        self.switch_tab(specified_tab)

    def check_cluster_info(self):
        """
        Make sure LSF or Openlava environment exists.
        """
        (tool, tool_version, cluster, master) = common_lsf.get_lsid_info()

        if tool == '':
            common.bprint('Not find any LSF or Openlava environment!', date_format='%Y-%m-%d %H:%M:%S', level='Error')
            sys.exit(1)

        common.bprint(str(tool) + ' (' + str(tool_version) + ')', date_format='%Y-%m-%d %H:%M:%S')
        common.bprint('My cluster name is "' + str(cluster) + '"', date_format='%Y-%m-%d %H:%M:%S')
        common.bprint('My master name is "' + str(master) + '"', date_format='%Y-%m-%d %H:%M:%S')
        common.bprint('', date_format='%Y-%m-%d %H:%M:%S')

        return cluster

    def fresh_lsf_info(self, lsf_info):
        """
        Get LSF information with functions on common_lsf.
        If the information is updated in 30 seconds, will not update it again.
        """
        if lsf_info in self.lsf_info_dic:
            current_second = int(time.time())

            if current_second - self.lsf_info_dic[lsf_info]['update_second'] > 30:
                common.bprint('Loading LSF ' + str(lsf_info) + ' information, please wait a moment ...', date_format='%Y-%m-%d %H:%M:%S')
                my_show_message = ShowMessage('Info', 'Loading LSF ' + str(lsf_info) + ' information, please wait a moment ...')
                my_show_message.start()

                exec(self.lsf_info_dic[lsf_info]['exec_cmd'])
                self.lsf_info_dic[lsf_info]['update_second'] = current_second

                time.sleep(0.01)
                my_show_message.terminate()

    def get_license_dic(self):
        if self.disable_license:
            return

        # Not update license_dic repeatedly in 300 seconds.
        current_second = int(time.time())

        if current_second - self.license_dic_second <= 300:
            common.bprint('Will not get license information repeatedly in 300 seconds.', date_format='%Y-%m-%d %H:%M:%S', level='Warning')
            return

        self.license_dic_second = current_second

        # Print loading license message.
        common.bprint('Loading License information, please wait a moment ...', date_format='%Y-%m-%d %H:%M:%S')

        my_show_message = ShowMessage('Info', 'Loading license information, please wait a moment ...')
        my_show_message.start()

        # Get self.license_dic.
        if ('LM_LICENSE_FILE' in os.environ) and os.environ['LM_LICENSE_FILE']:
            if config.lmstat_path:
                my_get_license_info = common_license.GetLicenseInfo(lmstat_path=config.lmstat_path, bsub_command=config.lmstat_bsub_command)
            else:
                my_get_license_info = common_license.GetLicenseInfo(bsub_command=config.lmstat_bsub_command)

            self.license_dic = my_get_license_info.get_license_info()

        time.sleep(0.01)
        my_show_message.terminate()

        if not self.license_dic:
            common.bprint('Not find any valid license information.', date_format='%Y-%m-%d %H:%M:%S', level='Warning')

    def init_ui(self):
        """
        Main process, draw the main graphic frame.
        """
        # Add menubar.
        self.gen_menubar()

        # Define main Tab widget
        self.main_tab = QTabWidget(self)
        self.setCentralWidget(self.main_tab)

        # Define sub-tabs
        self.job_tab = QWidget()
        self.jobs_tab = QWidget()
        self.hosts_tab = QWidget()
        self.queues_tab = QWidget()
        self.load_tab = QWidget()
        self.utilization_tab = QWidget()
        self.license_tab = QWidget()

        # Add the sub-tabs into main Tab widget
        self.main_tab.addTab(self.job_tab, 'JOB')
        self.main_tab.addTab(self.jobs_tab, 'JOBS')
        self.main_tab.addTab(self.hosts_tab, 'HOSTS')
        self.main_tab.addTab(self.queues_tab, 'QUEUES')
        self.main_tab.addTab(self.load_tab, 'LOAD')
        self.main_tab.addTab(self.utilization_tab, 'UTILIZATION')
        self.main_tab.addTab(self.license_tab, 'LICENSE')

        # Generate the sub-tabs
        self.gen_job_tab()
        self.gen_jobs_tab()
        self.gen_hosts_tab()
        self.gen_queues_tab()
        self.gen_load_tab()
        self.gen_utilization_tab()
        self.gen_license_tab()

        # Show main window
        common_pyqt5.auto_resize(self, 1200, 610)
        self.setWindowTitle('lsfMonitor ' + str(VERSION))
        self.setWindowIcon(QIcon(str(os.environ['LSFMONITOR_INSTALL_PATH']) + '/data/pictures/monitor.ico'))
        common_pyqt5.center_window(self)

    def switch_tab(self, specified_tab):
        """
        Switch to the specified Tab.
        """
        tab_dic = {'JOB': self.job_tab,
                   'JOBS': self.jobs_tab,
                   'HOSTS': self.hosts_tab,
                   'QUEUES': self.queues_tab,
                   'LOAD': self.load_tab,
                   'UTILIZATION': self.utilization_tab,
                   'LICENSE': self.license_tab}

        self.main_tab.setCurrentWidget(tab_dic[specified_tab])

    def gen_menubar(self):
        """
        Generate menubar.
        """
        menubar = self.menuBar()

        # File
        export_jobs_table_action = QAction('Export jobs table', self)
        export_jobs_table_action.setIcon(QIcon(str(os.environ['LSFMONITOR_INSTALL_PATH']) + '/data/pictures/save.png'))
        export_jobs_table_action.triggered.connect(self.export_jobs_table)

        export_hosts_table_action = QAction('Export hosts table', self)
        export_hosts_table_action.setIcon(QIcon(str(os.environ['LSFMONITOR_INSTALL_PATH']) + '/data/pictures/save.png'))
        export_hosts_table_action.triggered.connect(self.export_hosts_table)

        export_queues_table_action = QAction('Export queues table', self)
        export_queues_table_action.setIcon(QIcon(str(os.environ['LSFMONITOR_INSTALL_PATH']) + '/data/pictures/save.png'))
        export_queues_table_action.triggered.connect(self.export_queues_table)

        export_utilization_table_action = QAction('Export utilization table', self)
        export_utilization_table_action.setIcon(QIcon(str(os.environ['LSFMONITOR_INSTALL_PATH']) + '/data/pictures/save.png'))
        export_utilization_table_action.triggered.connect(self.export_utilization_table)

        export_license_feature_table_action = QAction('Export license feature table', self)
        export_license_feature_table_action.setIcon(QIcon(str(os.environ['LSFMONITOR_INSTALL_PATH']) + '/data/pictures/save.png'))
        export_license_feature_table_action.triggered.connect(self.export_license_feature_table)

        export_license_expires_table_action = QAction('Export license expires table', self)
        export_license_expires_table_action.setIcon(QIcon(str(os.environ['LSFMONITOR_INSTALL_PATH']) + '/data/pictures/save.png'))
        export_license_expires_table_action.triggered.connect(self.export_license_expires_table)

        exit_action = QAction('Exit', self)
        exit_action.setIcon(QIcon(str(os.environ['LSFMONITOR_INSTALL_PATH']) + '/data/pictures/exit.png'))
        exit_action.triggered.connect(qApp.quit)

        file_menu = menubar.addMenu('File')
        file_menu.addAction(export_jobs_table_action)
        file_menu.addAction(export_hosts_table_action)
        file_menu.addAction(export_queues_table_action)
        file_menu.addAction(export_utilization_table_action)
        file_menu.addAction(export_license_feature_table_action)
        file_menu.addAction(export_license_expires_table_action)
        file_menu.addAction(exit_action)

        # Setup
        enable_queue_detail_action = QAction('Enable queue detail', self, checkable=True)
        enable_queue_detail_action.triggered.connect(self.func_enable_queue_detail)

        enable_utilization_detail_action = QAction('Enable utilization detail', self, checkable=True)
        enable_utilization_detail_action.triggered.connect(self.func_enable_utilization_detail)

        setup_menu = menubar.addMenu('Setup')
        setup_menu.addAction(enable_queue_detail_action)
        setup_menu.addAction(enable_utilization_detail_action)

        # Function
        check_pend_reason_action = QAction('Check Pend reason', self)
        check_pend_reason_action.setIcon(QIcon(str(os.environ['LSFMONITOR_INSTALL_PATH']) + '/data/pictures/pend.png'))
        check_pend_reason_action.triggered.connect(self.check_pend_reason)
        check_slow_reason_action = QAction('Check Slow reason', self)
        check_slow_reason_action.setIcon(QIcon(str(os.environ['LSFMONITOR_INSTALL_PATH']) + '/data/pictures/slow.png'))
        check_slow_reason_action.triggered.connect(self.check_slow_reason)
        check_fail_reason_action = QAction('Check Fail reason', self)
        check_fail_reason_action.setIcon(QIcon(str(os.environ['LSFMONITOR_INSTALL_PATH']) + '/data/pictures/fail.png'))
        check_fail_reason_action.triggered.connect(self.check_fail_reason)

        function_menu = menubar.addMenu('Function')
        function_menu.addAction(check_pend_reason_action)
        function_menu.addAction(check_slow_reason_action)
        function_menu.addAction(check_fail_reason_action)

        # Help
        version_action = QAction('Version', self)
        version_action.setIcon(QIcon(str(os.environ['LSFMONITOR_INSTALL_PATH']) + '/data/pictures/version.png'))
        version_action.triggered.connect(self.show_version)

        about_action = QAction('About lsfMonitor', self)
        about_action.setIcon(QIcon(str(os.environ['LSFMONITOR_INSTALL_PATH']) + '/data/pictures/about.png'))
        about_action.triggered.connect(self.show_about)

        help_menu = menubar.addMenu('Help')
        help_menu.addAction(version_action)
        help_menu.addAction(about_action)

    def func_enable_queue_detail(self, state):
        """
        Show detail information for RUN/PEND curve on QUEUE tab.
        """
        if state:
            self.enable_queue_detail = True
            self.queues_tab_begin_date_edit.setDate(QDate.currentDate().addDays(-7))
        else:
            self.enable_queue_detail = False
            self.queues_tab_begin_date_edit.setDate(QDate.currentDate().addMonths(-1))

    def func_enable_utilization_detail(self, state):
        """
        Show detail information for utilization curve on UTILIZATION tab.
        """
        if state:
            self.enable_utilization_detail = True
            self.utilization_tab_begin_date_edit.setDate(QDate.currentDate().addDays(-7))
        else:
            self.enable_utilization_detail = False
            self.utilization_tab_begin_date_edit.setDate(QDate.currentDate().addMonths(-1))

    def check_pend_reason(self):
        """
        Call a separate script to check job pend reason.
        """
        self.my_check_issue_reason = CheckIssueReason(issue='PEND')
        self.my_check_issue_reason.start()

    def check_slow_reason(self):
        """
        Call a separate script to check job slow reason.
        """
        self.my_check_issue_reason = CheckIssueReason(issue='SLOW')
        self.my_check_issue_reason.start()

    def check_fail_reason(self):
        """
        Call a separate script to check job fail reason.
        """
        self.my_check_issue_reason = CheckIssueReason(issue='FAIL')
        self.my_check_issue_reason.start()

    def show_version(self):
        """
        Show lsfMonitor version information.
        """
        QMessageBox.about(self, 'lsfMonitor', 'Version: ' + str(VERSION) + ' (' + str(VERSION_DATE) + ')')

    def show_about(self):
        """
        Show lsfMonitor about information.
        """
        about_message = """
Thanks for downloading lsfMonitor.

lsfMonitor is an open source software for LSF information data-collection, data-analysis and data-display.

Please contact with liyanqing1987@163.com with any question."""

        QMessageBox.about(self, 'lsfMonitor', about_message)

# Common sub-functions (begin) #
    def gui_warning(self, warning_message):
        """
        Show the specified warning message on both of command line and GUI window.
        """
        common.bprint(warning_message, date_format='%Y-%m-%d %H:%M:%S', level='Warning')
        QMessageBox.warning(self, 'lsfMonitor Warning', warning_message)
# Common sub-functions (end) #

# For job TAB (begin) #
    def gen_job_tab(self):
        """
        Generate the job tab on lsfMonitor GUI, show job informations.
        """
        # Init var
        self.job_tab_current_job = ''
        self.job_tab_current_job_dic = {}

        # self.job_tab
        self.job_tab_frame0 = QFrame(self.job_tab)
        self.job_tab_frame1 = QFrame(self.job_tab)
        self.job_tab_frame2 = QFrame(self.job_tab)
        self.job_tab_frame3 = QFrame(self.job_tab)

        self.job_tab_frame0.setFrameShadow(QFrame.Raised)
        self.job_tab_frame0.setFrameShape(QFrame.Box)
        self.job_tab_frame1.setFrameShadow(QFrame.Raised)
        self.job_tab_frame1.setFrameShape(QFrame.Box)
        self.job_tab_frame2.setFrameShadow(QFrame.Raised)
        self.job_tab_frame2.setFrameShape(QFrame.Box)
        self.job_tab_frame3.setFrameShadow(QFrame.Raised)
        self.job_tab_frame3.setFrameShape(QFrame.Box)

        # self.job_tab - Grid
        job_tab_grid = QGridLayout()

        job_tab_grid.addWidget(self.job_tab_frame0, 0, 0)
        job_tab_grid.addWidget(self.job_tab_frame1, 1, 0)
        job_tab_grid.addWidget(self.job_tab_frame2, 2, 0, 1, 2)
        job_tab_grid.addWidget(self.job_tab_frame3, 0, 1, 2, 1)

        job_tab_grid.setRowStretch(0, 1)
        job_tab_grid.setRowStretch(1, 14)
        job_tab_grid.setRowStretch(2, 6)

        job_tab_grid.setColumnStretch(0, 1)
        job_tab_grid.setColumnStretch(1, 10)

        job_tab_grid.setColumnMinimumWidth(0, 250)

        self.job_tab.setLayout(job_tab_grid)

        # Generate sub-frames
        self.gen_job_tab_frame0()
        self.gen_job_tab_frame1()
        self.gen_job_tab_frame2()
        self.gen_job_tab_frame3()

        if self.specified_job:
            self.job_tab_job_line.setText(str(self.specified_job))
            self.check_job_on_job_tab()

    def gen_job_tab_frame0(self):
        # self.job_tab_frame0
        # "Job" item.
        job_tab_job_label = QLabel(self.job_tab_frame0)
        job_tab_job_label.setStyleSheet("font-weight: bold;")
        job_tab_job_label.setText('Job')

        self.job_tab_job_line = QLineEdit()
        self.job_tab_job_line.returnPressed.connect(self.check_job_on_job_tab)

        # "Check" button.
        job_tab_check_button = QPushButton('Check', self.job_tab_frame0)
        job_tab_check_button.setStyleSheet('''QPushButton:hover{background:rgb(0, 85, 255);}''')
        job_tab_check_button.clicked.connect(self.check_job_on_job_tab)

        # "Check" button.
        job_tab_kill_button = QPushButton('Kill', self.job_tab_frame0)
        job_tab_kill_button.setStyleSheet('''QPushButton:hover{background:rgb(0, 85, 255);}''')
        job_tab_kill_button.clicked.connect(self.kill_job_on_job_tab)

        # "Check" button.
        job_tab_trace_button = QPushButton('Trace', self.job_tab_frame0)
        job_tab_trace_button.setStyleSheet('''QPushButton:hover{background:rgb(0, 85, 255);}''')
        job_tab_trace_button.clicked.connect(self.trace_job_on_job_tab)

        # self.job_tab_frame0 - Grid
        job_tab_frame0_grid = QGridLayout()

        job_tab_frame0_grid.addWidget(job_tab_job_label, 0, 0)
        job_tab_frame0_grid.addWidget(self.job_tab_job_line, 0, 1, 1, 2)
        job_tab_frame0_grid.addWidget(job_tab_check_button, 1, 0)
        job_tab_frame0_grid.addWidget(job_tab_kill_button, 1, 1)
        job_tab_frame0_grid.addWidget(job_tab_trace_button, 1, 2)

        self.job_tab_frame0.setLayout(job_tab_frame0_grid)

    def gen_job_tab_frame1(self):
        # self.job_tab_frame1
        # "Status" item.
        job_tab_status_label = QLabel('Status', self.job_tab_frame1)
        job_tab_status_label.setStyleSheet("font-weight: bold;")

        self.job_tab_status_line = QLineEdit()

        # "User" item.
        job_tab_user_label = QLabel('User', self.job_tab_frame1)
        job_tab_user_label.setStyleSheet("font-weight: bold;")

        self.job_tab_user_line = QLineEdit()

        # "Project" item.
        job_tab_project_label = QLabel('Project', self.job_tab_frame1)
        job_tab_project_label.setStyleSheet("font-weight: bold;")

        self.job_tab_project_line = QLineEdit()

        # "Queue" item.
        job_tab_queue_label = QLabel('Queue', self.job_tab_frame1)
        job_tab_queue_label.setStyleSheet("font-weight: bold;")

        self.job_tab_queue_line = QLineEdit()

        # "Host" item.
        job_tab_started_on_label = QLabel('Host', self.job_tab_frame1)
        job_tab_started_on_label.setStyleSheet("font-weight: bold;")

        self.job_tab_started_on_line = QLineEdit()

        # "Start Time" item.
        job_tab_started_time_label = QLabel('Start Time', self.job_tab_frame1)
        job_tab_started_time_label.setStyleSheet("font-weight: bold;")

        self.job_tab_started_time_line = QLineEdit()

        # "Finish Time" item.
        job_tab_finished_time_label = QLabel('Finish Time', self.job_tab_frame1)
        job_tab_finished_time_label.setStyleSheet("font-weight: bold;")

        self.job_tab_finished_time_line = QLineEdit()

        # "Processors" item.
        job_tab_processors_requested_label = QLabel('Processors', self.job_tab_frame1)
        job_tab_processors_requested_label.setStyleSheet("font-weight: bold;")

        self.job_tab_processors_requested_line = QLineEdit()

        # "Rusage" item.
        job_tab_rusage_mem_label = QLabel('Rusage', self.job_tab_frame1)
        job_tab_rusage_mem_label.setStyleSheet("font-weight: bold;")

        self.job_tab_rusage_mem_line = QLineEdit()

        # "Mem (now)" item.
        job_tab_mem_label = QLabel('Mem (now)', self.job_tab_frame1)
        job_tab_mem_label.setStyleSheet("font-weight: bold;")

        self.job_tab_mem_line = QLineEdit()

        # "Mem (max)" item.
        job_tab_max_mem_label = QLabel('Mem (max)', self.job_tab_frame1)
        job_tab_max_mem_label.setStyleSheet("font-weight: bold;")

        self.job_tab_max_mem_line = QLineEdit()

        # self.job_tab_frame1 - Grid
        job_tab_frame1_grid = QGridLayout()

        job_tab_frame1_grid.addWidget(job_tab_status_label, 0, 0)
        job_tab_frame1_grid.addWidget(self.job_tab_status_line, 0, 1)
        job_tab_frame1_grid.addWidget(job_tab_user_label, 1, 0)
        job_tab_frame1_grid.addWidget(self.job_tab_user_line, 1, 1)
        job_tab_frame1_grid.addWidget(job_tab_project_label, 2, 0)
        job_tab_frame1_grid.addWidget(self.job_tab_project_line, 2, 1)
        job_tab_frame1_grid.addWidget(job_tab_queue_label, 3, 0)
        job_tab_frame1_grid.addWidget(self.job_tab_queue_line, 3, 1)
        job_tab_frame1_grid.addWidget(job_tab_started_on_label, 4, 0)
        job_tab_frame1_grid.addWidget(self.job_tab_started_on_line, 4, 1)
        job_tab_frame1_grid.addWidget(job_tab_started_time_label, 5, 0)
        job_tab_frame1_grid.addWidget(self.job_tab_started_time_line, 5, 1)
        job_tab_frame1_grid.addWidget(job_tab_finished_time_label, 6, 0)
        job_tab_frame1_grid.addWidget(self.job_tab_finished_time_line, 6, 1)
        job_tab_frame1_grid.addWidget(job_tab_processors_requested_label, 7, 0)
        job_tab_frame1_grid.addWidget(self.job_tab_processors_requested_line, 7, 1)
        job_tab_frame1_grid.addWidget(job_tab_rusage_mem_label, 8, 0)
        job_tab_frame1_grid.addWidget(self.job_tab_rusage_mem_line, 8, 1)
        job_tab_frame1_grid.addWidget(job_tab_mem_label, 9, 0)
        job_tab_frame1_grid.addWidget(self.job_tab_mem_line, 9, 1)
        job_tab_frame1_grid.addWidget(job_tab_max_mem_label, 10, 0)
        job_tab_frame1_grid.addWidget(self.job_tab_max_mem_line, 10, 1)

        self.job_tab_frame1.setLayout(job_tab_frame1_grid)

    def gen_job_tab_frame2(self):
        # self.job_tab_frame2
        self.job_tab_job_info_text = QTextEdit(self.job_tab_frame2)

        # self.job_tab_frame2 - Grid
        job_tab_frame2_grid = QGridLayout()
        job_tab_frame2_grid.addWidget(self.job_tab_job_info_text, 0, 0)
        self.job_tab_frame2.setLayout(job_tab_frame2_grid)

    def gen_job_tab_frame3(self):
        # self.job_tab_frame3
        self.job_tab_mem_canvas = common_pyqt5.FigureCanvasQTAgg()
        self.job_tab_mem_toolbar = common_pyqt5.NavigationToolbar2QT(self.job_tab_mem_canvas, self, x_is_date=False)

        # self.job_tab_frame3 - Grid
        job_tab_frame3_grid = QGridLayout()
        job_tab_frame3_grid.addWidget(self.job_tab_mem_toolbar, 0, 0)
        job_tab_frame3_grid.addWidget(self.job_tab_mem_canvas, 1, 0)
        self.job_tab_frame3.setLayout(job_tab_frame3_grid)

    def check_job_on_job_tab(self):
        """
        Get job information with "bjobs -UF <job_id>", save the infomation into dict self.job_tab_current_job_dic.
        Update self.job_tab_frame1 and self.job_tab_frame3.
        """
        # Initicalization JOB tab.
        self.update_job_tab_frame1(init=True)
        self.update_job_tab_frame2(init=True)
        self.update_job_tab_frame3(init=True)

        # Get real jobid and check it.
        self.job_tab_current_job = self.job_tab_job_line.text().strip()

        if not re.match(r'^(\d+)(\[\d+\])?$', self.job_tab_current_job):
            warning_message = '*Warning*: No valid job is specified!'
            self.gui_warning(warning_message)
            return

        my_match = re.match(r'^(\d+)(\[\d+\])?$', self.job_tab_current_job)
        current_job = my_match.group(1)

        common.bprint('Checking job "' + str(current_job) + '".', date_format='%Y-%m-%d %H:%M:%S')

        # Get job info
        common.bprint('Getting LSF job information for "' + str(current_job) + '", please wait a moment ...', date_format='%Y-%m-%d %H:%M:%S')

        my_show_message = ShowMessage('Info', 'Getting LSF job information for "' + str(current_job) + '", please wait a moment ...')
        my_show_message.start()

        self.job_tab_current_job_dic = common_lsf.get_bjobs_uf_info(command='bjobs -UF ' + str(current_job))

        time.sleep(0.01)
        my_show_message.terminate()

        if not self.job_tab_current_job_dic:
            warning_message = '*Warning*: Not find job information for job "' + str(current_job) + '".'
            self.gui_warning(warning_message)
            return

        # Update JOB tab with latest job info.
        self.update_job_tab_frame1()
        self.update_job_tab_frame2()
        self.update_job_tab_frame3()

    def kill_job_on_job_tab(self):
        """
        Kill job, update self.job_tab.
        """
        if self.job_tab_current_job:
            return_code = self.kill_job(self.job_tab_current_job)

            if return_code == 0:
                self.check_job_on_job_tab()

    def kill_job(self, jobid=None):
        """
        Kill job with "bkill".
        """
        if jobid:
            common.bprint('Kill job "' + str(jobid) + '".', date_format='%Y-%m-%d %H:%M:%S')

            command = 'bkill ' + str(jobid)
            (return_code, stdout, stderr) = common.run_command(command)

            if return_code == 0:
                common.bprint('Kill ' + str(jobid) + ' successfully!', date_format='%Y-%m-%d %H:%M:%S')
                my_show_message = ShowMessage('Info', 'Kill ' + str(jobid) + ' successfully!')
                my_show_message.start()
                time.sleep(5)
                my_show_message.terminate()
            else:
                common.bprint('Failed on killing ' + str(jobid) + '.', date_format='%Y-%m-%d %H:%M:%S')
                common.bprint(str(stderr, 'utf-8').strip(), date_format='%Y-%m-%d %H:%M:%S')
                my_show_message = ShowMessage('Kill ' + str(jobid) + ' fail', str(str(stderr, 'utf-8')).strip())
                my_show_message.run()

            return return_code

        return -1

    def trace_job_on_job_tab(self):
        """
        Trace job on self.job_tab.
        """
        if self.job_tab_current_job:
            self.trace_job(self.job_tab_current_job)

    def trace_job(self, jobid=None):
        """
        Trace job process with tool process_tracer.
        """
        if jobid:
            self.my_process_tracer = ProcessTracer(jobid)
            self.my_process_tracer.start()

    def update_job_tab_frame1(self, init=False):
        """
        Update self.job_tab_frame1 with job infos.
        """
        # Fill "Status" item.
        if init:
            self.job_tab_status_line.setText('')
        else:
            self.job_tab_status_line.setText(self.job_tab_current_job_dic[self.job_tab_current_job]['status'])
            self.job_tab_status_line.setCursorPosition(0)

        # Fill "User" item.
        if init:
            self.job_tab_user_line.setText('')
        else:
            self.job_tab_user_line.setText(self.job_tab_current_job_dic[self.job_tab_current_job]['user'])
            self.job_tab_user_line.setCursorPosition(0)

        # Fill "Project" item.
        if init:
            self.job_tab_project_line.setText('')
        else:
            self.job_tab_project_line.setText(self.job_tab_current_job_dic[self.job_tab_current_job]['project'])
            self.job_tab_project_line.setCursorPosition(0)

        # Fill "Queue" item.
        if init:
            self.job_tab_queue_line.setText('')
        else:
            self.job_tab_queue_line.setText(self.job_tab_current_job_dic[self.job_tab_current_job]['queue'])
            self.job_tab_queue_line.setCursorPosition(0)

        # Fill "Host" item.
        if init:
            self.job_tab_started_on_line.setText('')
        else:
            self.job_tab_started_on_line.setText(self.job_tab_current_job_dic[self.job_tab_current_job]['started_on'])
            self.job_tab_started_on_line.setCursorPosition(0)

        # Fill "Started Time" item.
        if init:
            self.job_tab_started_time_line.setText('')
        else:
            self.job_tab_started_time_line.setText(self.job_tab_current_job_dic[self.job_tab_current_job]['started_time'])
            self.job_tab_started_time_line.setCursorPosition(0)

        # Fill "Finished Time" item.
        if init:
            self.job_tab_finished_time_line.setText('')
        else:
            self.job_tab_finished_time_line.setText(self.job_tab_current_job_dic[self.job_tab_current_job]['finished_time'])
            self.job_tab_finished_time_line.setCursorPosition(0)

        # Fill "Processors" item.
        if init:
            self.job_tab_processors_requested_line.setText('')
        else:
            self.job_tab_processors_requested_line.setText(self.job_tab_current_job_dic[self.job_tab_current_job]['processors_requested'])
            self.job_tab_processors_requested_line.setCursorPosition(0)

        # Fill "Rusage" item.
        if init:
            self.job_tab_rusage_mem_line.setText('')
        else:
            if self.job_tab_current_job_dic[self.job_tab_current_job]['rusage_mem'] != '':
                rusage_mem_value = self.job_tab_current_job_dic[self.job_tab_current_job]['rusage_mem']

                if self.lsf_unit_for_limits == 'KB':
                    rusage_mem_value = round(int(rusage_mem_value)/1024/1024, 1)
                elif self.lsf_unit_for_limits == 'MB':
                    rusage_mem_value = round(int(rusage_mem_value)/1024, 1)
                elif self.lsf_unit_for_limits == 'GB':
                    rusage_mem_value = round(float(rusage_mem_value), 1)
                elif self.lsf_unit_for_limits == 'TB':
                    rusage_mem_value = round(int(rusage_mem_value)*1024, 1)

                self.job_tab_rusage_mem_line.setText(str(rusage_mem_value) + ' G')
                self.job_tab_rusage_mem_line.setCursorPosition(0)

        # Fill "Mem" item.
        if init:
            self.job_tab_mem_line.setText('')
        else:
            if self.job_tab_current_job_dic[self.job_tab_current_job]['mem'] != '':
                mem_value = round(float(self.job_tab_current_job_dic[self.job_tab_current_job]['mem'])/1024, 1)
                self.job_tab_mem_line.setText(str(mem_value) + ' G')
                self.job_tab_mem_line.setCursorPosition(0)

        # Fill "max_mem" item.
        if init:
            self.job_tab_max_mem_line.setText('')
        else:
            if self.job_tab_current_job_dic[self.job_tab_current_job]['max_mem'] != '':
                max_mem_value = round(float(self.job_tab_current_job_dic[self.job_tab_current_job]['max_mem'])/1024, 1)
                self.job_tab_max_mem_line.setText(str(max_mem_value) + ' G')
                self.job_tab_max_mem_line.setCursorPosition(0)

    def update_job_tab_frame2(self, init=False):
        """
        Show job detailed description info on self.job_tab_frame2/self.job_tab_job_info_text.
        """
        self.job_tab_job_info_text.clear()

        if not init:
            self.job_tab_job_info_text.insertPlainText(self.job_tab_current_job_dic[self.job_tab_current_job]['job_info'])
            common_pyqt5.text_edit_visible_position(self.job_tab_job_info_text, 'Start')

    def get_job_mem_list(self):
        """
        Get job sample-time mem list for self.job_tab_current_job.
        """
        runtime_list = []
        real_mem_list = []

        job_range_dic = common.get_job_range_dic([self.job_tab_current_job, ])
        job_range_list = list(job_range_dic.keys())
        job_range = job_range_list[0]
        job_db_file = str(self.db_path) + '/job/' + str(job_range) + '.db'

        if not os.path.exists(job_db_file):
            common.bprint('Job memory usage information is missing for "' + str(self.job_tab_current_job) + '".', date_format='%Y-%m-%d %H:%M:%S', level='Warning')
        else:
            (job_db_file_connect_result, job_db_conn) = common_sqlite3.connect_db_file(job_db_file)

            if job_db_file_connect_result == 'failed':
                common.bprint('Failed on connecting job database file "' + str(job_db_file) + '".', date_format='%Y-%m-%d %H:%M:%S', level='Warning')
            else:
                table_name = 'job_' + str(self.job_tab_current_job)
                data_dic = common_sqlite3.get_sql_table_data(job_db_file, job_db_conn, table_name, ['sample_time', 'mem'])

                if not data_dic:
                    common.bprint('Job memory usage information is empty for "' + str(self.job_tab_current_job) + '".', date_format='%Y-%m-%d %H:%M:%S', level='Warning')
                else:
                    sample_time_list = data_dic['sample_time']
                    mem_list = data_dic['mem']
                    first_sample_time = datetime.datetime.strptime(str(sample_time_list[0]), '%Y%m%d_%H%M%S').timestamp()

                    for i in range(len(sample_time_list)):
                        sample_time = sample_time_list[i]
                        current_time = datetime.datetime.strptime(str(sample_time), '%Y%m%d_%H%M%S').timestamp()
                        runtime = int((current_time-first_sample_time)/60)
                        runtime_list.append(runtime)
                        mem = mem_list[i]

                        if mem == '':
                            mem = '0'

                        real_mem = round(float(mem)/1024, 1)
                        real_mem_list.append(real_mem)

                job_db_conn.close()

        return runtime_list, real_mem_list

    def update_job_tab_frame3(self, init=False):
        """
        Draw memory curve for current job on self.job_tab_frame3.
        """
        fig = self.job_tab_mem_canvas.figure
        fig.clear()
        self.job_tab_mem_canvas.draw()

        if not init:
            if self.job_tab_current_job_dic[self.job_tab_current_job]['status'] != 'PEND':
                (runtime_list, mem_list) = self.get_job_mem_list()

                if runtime_list and mem_list:
                    self.draw_job_tab_mem_curve(fig, runtime_list, mem_list)

    def draw_job_tab_mem_curve(self, fig, runtime_list, mem_list):
        """
        Draw memory curve for specified job.
        """
        fig.subplots_adjust(bottom=0.2)
        axes = fig.add_subplot(111)
        axes.set_title('memory usage for job "' + str(self.job_tab_current_job) + '"')
        axes.set_xlabel('Runtime (Minutes)')
        axes.set_ylabel('Memory Usage (G)')
        axes.plot(runtime_list, mem_list, 'go-', label='MEM', linewidth=0.1, markersize=0.1)
        axes.fill_between(runtime_list, mem_list, color='green', alpha=0.5)
        axes.legend(loc='upper right')
        axes.grid()
        self.job_tab_mem_canvas.draw()
# For job TAB (end) #

# For jobs TAB (start) #
    def gen_jobs_tab(self):
        """
        Generate the jobs tab on lsfMonitor GUI, show jobs informations.
        """
        # self.jobs_tab
        self.jobs_tab_frame0 = QFrame(self.jobs_tab)
        self.jobs_tab_frame0.setFrameShadow(QFrame.Raised)
        self.jobs_tab_frame0.setFrameShape(QFrame.Box)

        self.jobs_tab_table = QTableWidget(self.jobs_tab)
        self.jobs_tab_table.itemClicked.connect(self.jobs_tab_check_click)
        self.jobs_tab_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.jobs_tab_table.customContextMenuRequested.connect(self.gen_jobs_tab_menu)

        # self.jobs_tab - Grid
        jobs_tab_grid = QGridLayout()

        jobs_tab_grid.addWidget(self.jobs_tab_frame0, 0, 0)
        jobs_tab_grid.addWidget(self.jobs_tab_table, 1, 0)

        jobs_tab_grid.setRowStretch(0, 1)
        jobs_tab_grid.setRowStretch(1, 20)

        self.jobs_tab.setLayout(jobs_tab_grid)

        # Generate sub-frame
        self.gen_jobs_tab_frame0()

        if self.specified_user:
            self.jobs_tab_user_line.setText(str(self.specified_user))

        self.gen_jobs_tab_table()

    def gen_jobs_tab_frame0(self):
        # self.jobs_tab_frame0
        # "Status" item.
        jobs_tab_status_label = QLabel('Status', self.jobs_tab_frame0)
        jobs_tab_status_label.setStyleSheet("font-weight: bold;")
        jobs_tab_status_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.jobs_tab_status_combo = common_pyqt5.QComboCheckBox(self.jobs_tab_frame0)
        self.set_jobs_tab_status_combo()

        # "Queue" item.
        jobs_tab_queue_label = QLabel('Queue', self.jobs_tab_frame0)
        jobs_tab_queue_label.setStyleSheet("font-weight: bold;")
        jobs_tab_queue_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.jobs_tab_queue_combo = common_pyqt5.QComboCheckBox(self.jobs_tab_frame0)
        self.set_jobs_tab_queue_combo()

        # "Host" item.
        jobs_tab_started_on_label = QLabel('Host', self.jobs_tab_frame0)
        jobs_tab_started_on_label.setStyleSheet("font-weight: bold;")
        jobs_tab_started_on_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.jobs_tab_host_combo = common_pyqt5.QComboCheckBox(self.jobs_tab_frame0)
        self.set_jobs_tab_host_combo()

        # "User" item.
        jobs_tab_user_label = QLabel('User', self.jobs_tab_frame0)
        jobs_tab_user_label.setStyleSheet("font-weight: bold;")
        jobs_tab_user_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.jobs_tab_user_line = QLineEdit()
        self.jobs_tab_user_line.returnPressed.connect(self.gen_jobs_tab_table)

        self.fresh_lsf_info('busers')
        jobs_tab_user_line_completer = common_pyqt5.get_completer(self.users_dic['USER/GROUP'])
        self.jobs_tab_user_line.setCompleter(jobs_tab_user_line_completer)

        # "Check" button.
        jobs_tab_check_button = QPushButton('Check', self.jobs_tab_frame0)
        jobs_tab_check_button.setStyleSheet('''QPushButton:hover{background:rgb(0, 85, 255);}''')
        jobs_tab_check_button.clicked.connect(self.gen_jobs_tab_table)

        # self.jobs_tab_frame0 - Grid
        jobs_tab_frame0_grid = QGridLayout()

        jobs_tab_frame0_grid.addWidget(jobs_tab_status_label, 0, 0)
        jobs_tab_frame0_grid.addWidget(self.jobs_tab_status_combo, 0, 1)
        jobs_tab_frame0_grid.addWidget(jobs_tab_queue_label, 0, 2)
        jobs_tab_frame0_grid.addWidget(self.jobs_tab_queue_combo, 0, 3)
        jobs_tab_frame0_grid.addWidget(jobs_tab_started_on_label, 0, 4)
        jobs_tab_frame0_grid.addWidget(self.jobs_tab_host_combo, 0, 5)
        jobs_tab_frame0_grid.addWidget(jobs_tab_user_label, 0, 6)
        jobs_tab_frame0_grid.addWidget(self.jobs_tab_user_line, 0, 7)
        jobs_tab_frame0_grid.addWidget(jobs_tab_check_button, 0, 8)

        jobs_tab_frame0_grid.setColumnStretch(1, 1)
        jobs_tab_frame0_grid.setColumnStretch(2, 1)
        jobs_tab_frame0_grid.setColumnStretch(3, 1)
        jobs_tab_frame0_grid.setColumnStretch(4, 1)
        jobs_tab_frame0_grid.setColumnStretch(5, 1)
        jobs_tab_frame0_grid.setColumnStretch(6, 1)
        jobs_tab_frame0_grid.setColumnStretch(7, 1)
        jobs_tab_frame0_grid.setColumnStretch(8, 1)

        self.jobs_tab_frame0.setLayout(jobs_tab_frame0_grid)

    def gen_jobs_tab_table(self):
        # self.jobs_tab_table
        self.jobs_tab_table.setShowGrid(True)
        self.jobs_tab_table.setSortingEnabled(True)
        self.jobs_tab_table.setColumnCount(0)
        self.jobs_tab_table.setColumnCount(11)
        self.jobs_tab_table_title_list = ['Job', 'User', 'Status', 'Queue', 'Host', 'Started', 'Project', 'Slot', 'Rusage (G)', 'Mem (G)', 'Command']
        self.jobs_tab_table.setHorizontalHeaderLabels(self.jobs_tab_table_title_list)

        self.jobs_tab_table.setColumnWidth(0, 80)
        self.jobs_tab_table.setColumnWidth(1, 120)
        self.jobs_tab_table.setColumnWidth(2, 60)
        self.jobs_tab_table.setColumnWidth(3, 125)
        self.jobs_tab_table.setColumnWidth(4, 120)
        self.jobs_tab_table.setColumnWidth(5, 150)
        self.jobs_tab_table.setColumnWidth(6, 100)
        self.jobs_tab_table.setColumnWidth(7, 40)
        self.jobs_tab_table.setColumnWidth(8, 80)
        self.jobs_tab_table.setColumnWidth(9, 70)
        self.jobs_tab_table.horizontalHeader().setSectionResizeMode(10, QHeaderView.Stretch)

        # Get specified user related jobs.
        command = 'bjobs -UF '
        specified_user = self.jobs_tab_user_line.text().strip()

        if re.match(r'^\s*$', specified_user):
            command = str(command) + ' -u all'
        else:
            command = str(command) + ' -u ' + str(specified_user)

        # Get specified queue related jobs.
        specified_queue_list = self.jobs_tab_queue_combo.currentText().strip().split()

        if (len(specified_queue_list) == 1) and (specified_queue_list[0] != 'ALL'):
            command = str(command) + ' -q ' + str(specified_queue_list[0])

        # Get specified status (RUN/PEND/ALL) related jobs.
        specified_status_list = self.jobs_tab_status_combo.currentText().strip().split()

        if (len(specified_status_list) == 1) and (specified_status_list[0] == 'RUN'):
            command = str(command) + ' -r'
        elif (len(specified_status_list) == 1) and (specified_status_list[0] == 'PEND'):
            command = str(command) + ' -p'
        else:
            command = str(command) + ' -a'

        # Get specified host related jobs.
        specified_host_list = self.jobs_tab_host_combo.currentText().strip().split()

        if (len(specified_host_list) == 1) and (specified_host_list[0] != 'ALL'):
            command = str(command) + ' -m ' + str(specified_host_list[0])

        # Run command to get expected jobs information.
        common.bprint('Loading LSF jobs information, please wait a moment ...', date_format='%Y-%m-%d %H:%M:%S')

        my_show_message = ShowMessage('Info', 'Loading LSF jobs information, please wait a moment ...')
        my_show_message.start()

        job_dic = common_lsf.get_bjobs_uf_info(command)

        time.sleep(0.01)
        my_show_message.terminate()

        # Filter job_dic.
        job_list = list(job_dic.keys())

        for job in job_list:
            if ('ALL' not in specified_status_list) and (job_dic[job]['status'] not in specified_status_list):
                del job_dic[job]
                continue

            if ('ALL' not in specified_queue_list) and (len(specified_queue_list) > 1) and (job_dic[job]['queue'] not in specified_queue_list):
                del job_dic[job]
                continue

            if ('ALL' not in specified_host_list) and (len(specified_host_list) > 1):
                find_host = False
                started_on_list = job_dic[job]['started_on'].strip().split()

                for specified_host in specified_host_list:
                    if specified_host in started_on_list:
                        find_host = True
                        break

                if not find_host:
                    del job_dic[job]
                    continue

        # Fill self.jobs_tab_table items.
        self.jobs_tab_table.setRowCount(0)
        self.jobs_tab_table.setRowCount(len(job_dic.keys()))

        # Don't remove below setting!!!
        job_list = list(job_dic.keys())

        for i in range(len(job_list)):
            # Fill "Job" item.
            job = job_list[i]
            j = 0
            item = QTableWidgetItem(job)
            item.setFont(QFont('song', 9, QFont.Bold))
            self.jobs_tab_table.setItem(i, j, item)

            # Fill "User" item.
            j = j+1
            item = QTableWidgetItem(job_dic[job]['user'])
            self.jobs_tab_table.setItem(i, j, item)

            # Fill "Status" item.
            j = j+1
            item = QTableWidgetItem(job_dic[job]['status'])
            item.setFont(QFont('song', 9, QFont.Bold))

            if (job_dic[job]['status'] == 'PEND') or (job_dic[job]['status'] == 'EXIT'):
                item.setBackground(QBrush(Qt.red))

            self.jobs_tab_table.setItem(i, j, item)

            # Fill "Queue" item.
            j = j+1
            item = QTableWidgetItem(job_dic[job]['queue'])
            self.jobs_tab_table.setItem(i, j, item)

            # Fill "Host" item.
            j = j+1
            item = QTableWidgetItem(job_dic[job]['started_on'])
            self.jobs_tab_table.setItem(i, j, item)

            # Fill "Started" item.
            j = j+1
            start_time = self.switch_job_start_time(job_dic[job]['started_time'])
            item = QTableWidgetItem(start_time)
            self.jobs_tab_table.setItem(i, j, item)

            # Fill "Project" item.
            j = j+1

            if str(job_dic[job]['project']) != '':
                item = QTableWidgetItem()
                item.setData(Qt.DisplayRole, job_dic[job]['project'])
                self.jobs_tab_table.setItem(i, j, item)

            # Fill "Slot" item.
            j = j+1

            if str(job_dic[job]['processors_requested']) != '':
                item = QTableWidgetItem()
                item.setData(Qt.DisplayRole, int(job_dic[job]['processors_requested']))
                self.jobs_tab_table.setItem(i, j, item)

            # Fill "Rusage" item.
            j = j+1

            if str(job_dic[job]['rusage_mem']) != '':
                item = QTableWidgetItem()
                rusage_mem_value = job_dic[job]['rusage_mem']

                if self.lsf_unit_for_limits == 'KB':
                    rusage_mem_value = round(int(rusage_mem_value)/1024/1024, 1)
                elif self.lsf_unit_for_limits == 'MB':
                    rusage_mem_value = round(int(rusage_mem_value)/1024, 1)
                elif self.lsf_unit_for_limits == 'GB':
                    rusage_mem_value = round(float(rusage_mem_value), 1)
                elif self.lsf_unit_for_limits == 'TB':
                    rusage_mem_value = round(int(rusage_mem_value)*1024, 1)

                item.setData(Qt.DisplayRole, rusage_mem_value)
                self.jobs_tab_table.setItem(i, j, item)

            # Fill "Mem" item.
            j = j+1

            if str(job_dic[job]['mem']) != '':
                item = QTableWidgetItem()
                mem_value = round(float(job_dic[job]['mem'])/1024, 1)
                item.setData(Qt.DisplayRole, mem_value)
                self.jobs_tab_table.setItem(i, j, item)

                if ((not job_dic[job]['rusage_mem']) and (mem_value > 0)) or (job_dic[job]['rusage_mem'] and (mem_value > rusage_mem_value)):
                    item.setBackground(QBrush(Qt.red))

            # Fill "Command" item.
            j = j+1
            item = QTableWidgetItem(job_dic[job]['command'])
            self.jobs_tab_table.setItem(i, j, item)

    def gen_jobs_tab_menu(self, pos):
        """
        Generate right click menu on self.jobs_tab_table.
        """
        item = self.jobs_tab_table.itemAt(pos)

        if item and (item.column() == 0):
            menu = QMenu(self.jobs_tab_table)

            kill_job_action = QAction('Kill', self)
            kill_job_action.setIcon(QIcon(str(os.environ['LSFMONITOR_INSTALL_PATH']) + '/data/pictures/gun.png'))
            kill_job_action.triggered.connect(lambda: self.kill_job_on_jobs_tab(item.text()))
            menu.addAction(kill_job_action)

            trace_job_action = QAction('Trace', self)
            trace_job_action.setIcon(QIcon(str(os.environ['LSFMONITOR_INSTALL_PATH']) + '/data/pictures/trace.png'))
            trace_job_action.triggered.connect(lambda: self.trace_job(item.text()))
            menu.addAction(trace_job_action)

            menu.exec_(self.jobs_tab_table.mapToGlobal(pos))

    def kill_job_on_jobs_tab(self, jobid=None):
        """
        Kill job, update self.jobs_tab_table.
        """
        return_code = self.kill_job(jobid)

        if return_code == 0:
            self.gen_jobs_tab_table()

    def switch_job_start_time(self, start_time):
        """
        Switch start_time from "%Y %b %d %H:%M:%S" into "%Y-%m-%d %H:%M:%S".
        """
        new_start_time = start_time

        if start_time and (start_time != 'N/A'):
            # Switch start_time to start_seconds.
            current_year = datetime.date.today().year
            start_time_list = start_time.split()

            start_time_with_year = str(current_year) + ' ' + str(start_time_list[1]) + ' ' + str(start_time_list[2]) + ' ' + str(start_time_list[3])
            start_seconds = time.mktime(time.strptime(start_time_with_year, '%Y %b %d %H:%M:%S'))
            current_seconds = time.time()

            if int(start_seconds) > int(current_seconds):
                current_year = int(datetime.date.today().year) - 1
                start_time_with_year = str(current_year) + ' ' + str(start_time_list[1]) + ' ' + str(start_time_list[2]) + ' ' + str(start_time_list[3])
                start_seconds = time.mktime(time.strptime(start_time_with_year, '%Y %b %d %H:%M:%S'))

            # Switch start_seconds to expected time format.
            new_start_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(start_seconds))

        return new_start_time

    def jobs_tab_check_click(self, item=None):
        """
        If click the Job id, jump to the JOB tab and show the job information.
        If click the "PEND" Status, show the job pend reasons on a QMessageBox.information().
        """
        if item is not None:
            current_row = self.jobs_tab_table.currentRow()
            job = self.jobs_tab_table.item(current_row, 0).text().strip()

            if item.column() == 0:
                if job != '':
                    self.job_tab_job_line.setText(job)
                    self.check_job_on_job_tab()
                    self.main_tab.setCurrentWidget(self.job_tab)
            elif item.column() == 2:
                job_status = self.jobs_tab_table.item(current_row, 2).text().strip()

                if job_status == 'PEND':
                    common.bprint('Getting job pend reason for "' + str(job) + '", please wait a moment ...', date_format='%Y-%m-%d %H:%M:%S')
                    self.my_check_issue_reason = CheckIssueReason(job=job, issue='PEND')
                    self.my_check_issue_reason.start()
                elif job_status == 'RUN':
                    common.bprint('Getting job process information for "' + str(job) + '", please wait a moment ...', date_format='%Y-%m-%d %H:%M:%S')
                    self.my_check_issue_reason = CheckIssueReason(job=job, issue='SLOW')
                    self.my_check_issue_reason.start()
                elif (job_status == 'DONE') or (job_status == 'EXIT'):
                    common.bprint('Getting job fail reason for "' + str(job) + '", please wait a moment ...', date_format='%Y-%m-%d %H:%M:%S')
                    self.my_check_issue_reason = CheckIssueReason(job=job, issue='FAIL')
                    self.my_check_issue_reason.start()

    def set_jobs_tab_status_combo(self, status_list=[]):
        """
        Set (initialize) self.jobs_tab_status_combo.
        """
        self.jobs_tab_status_combo.clear()

        if not status_list:
            status_list = ['RUN', 'PEND', 'DONE', 'EXIT', 'ALL']

        for status in status_list:
            self.jobs_tab_status_combo.addCheckBoxItem(status)

        # Set "ALL" as checked status.
        for (i, qBox) in enumerate(self.jobs_tab_status_combo.checkBoxList):
            if (qBox.text() == 'RUN') and (qBox.isChecked() is False):
                self.jobs_tab_status_combo.checkBoxList[i].setChecked(True)
                break

    def set_jobs_tab_queue_combo(self, queue_list=[]):
        """
        Set (initialize) self.jobs_tab_queue_combo.
        """
        self.jobs_tab_queue_combo.clear()
        self.fresh_lsf_info('bqueues')

        if not queue_list:
            queue_list = copy.deepcopy(self.queues_dic['QUEUE_NAME'])
            queue_list.sort()
            queue_list.insert(0, 'ALL')

        for queue in queue_list:
            self.jobs_tab_queue_combo.addCheckBoxItem(queue)

        # Set "ALL" as checked status.
        for (i, qBox) in enumerate(self.jobs_tab_queue_combo.checkBoxList):
            if (qBox.text() == 'ALL') and (qBox.isChecked() is False):
                self.jobs_tab_queue_combo.checkBoxList[i].setChecked(True)
                break

    def set_jobs_tab_host_combo(self, host_list=[]):
        """
        Set (initialize) self.jobs_tab_host_combo.
        """
        self.jobs_tab_host_combo.clear()

        if not host_list:
            self.fresh_lsf_info('bhosts')
            host_list = copy.deepcopy(self.bhosts_dic['HOST_NAME'])
            host_list.insert(0, 'ALL')

        for host in host_list:
            self.jobs_tab_host_combo.addCheckBoxItem(host)

        # Set "ALL" as checked status.
        for (i, qBox) in enumerate(self.jobs_tab_host_combo.checkBoxList):
            if (qBox.text() == 'ALL') and (qBox.isChecked() is False):
                self.jobs_tab_host_combo.checkBoxList[i].setChecked(True)
                break
# For jobs TAB (end) #

# For hosts TAB (start) #
    def gen_hosts_tab(self):
        """
        Generate the hosts tab on lsfMonitor GUI, show hosts informations.
        """
        # self.hosts_tab_table
        self.hosts_tab_frame0 = QFrame(self.hosts_tab)
        self.hosts_tab_frame0.setFrameShadow(QFrame.Raised)
        self.hosts_tab_frame0.setFrameShape(QFrame.Box)

        self.hosts_tab_table = QTableWidget(self.hosts_tab)
        self.hosts_tab_table.itemClicked.connect(self.hosts_tab_check_click)
        self.hosts_tab_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.hosts_tab_table.customContextMenuRequested.connect(self.gen_hosts_tab_menu)

        # self.hosts_tab_table - Grid
        hosts_tab_grid = QGridLayout()

        hosts_tab_grid.addWidget(self.hosts_tab_frame0, 0, 0)
        hosts_tab_grid.addWidget(self.hosts_tab_table, 1, 0)

        hosts_tab_grid.setRowStretch(0, 1)
        hosts_tab_grid.setRowStretch(1, 20)

        self.hosts_tab.setLayout(hosts_tab_grid)

        # Generate sub-fram
        self.gen_hosts_tab_frame0()
        self.gen_hosts_tab_table()

    def gen_hosts_tab_frame0(self):
        # self.hosts_tab_frame0
        # "Status" item.
        hosts_tab_status_label = QLabel('Status', self.hosts_tab_frame0)
        hosts_tab_status_label.setStyleSheet("font-weight: bold;")
        hosts_tab_status_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.hosts_tab_status_combo = common_pyqt5.QComboCheckBox(self.hosts_tab_frame0)
        self.set_hosts_tab_status_combo()

        # "Queue" item.
        hosts_tab_queue_label = QLabel('Queue', self.hosts_tab_frame0)
        hosts_tab_queue_label.setStyleSheet("font-weight: bold;")
        hosts_tab_queue_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.hosts_tab_queue_combo = common_pyqt5.QComboCheckBox(self.hosts_tab_frame0)
        self.set_hosts_tab_queue_combo()

        # "MAX" item.
        hosts_tab_max_label = QLabel('MAX', self.hosts_tab_frame0)
        hosts_tab_max_label.setStyleSheet("font-weight: bold;")
        hosts_tab_max_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.hosts_tab_max_combo = common_pyqt5.QComboCheckBox(self.hosts_tab_frame0)
        self.set_hosts_tab_max_combo()

        # "MaxMem" item.
        hosts_tab_maxmem_label = QLabel('MaxMem', self.hosts_tab_frame0)
        hosts_tab_maxmem_label.setStyleSheet("font-weight: bold;")
        hosts_tab_maxmem_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.hosts_tab_maxmem_combo = common_pyqt5.QComboCheckBox(self.hosts_tab_frame0)
        self.set_hosts_tab_maxmem_combo()

        # "Host" item.
        hosts_tab_host_label = QLabel('Host', self.hosts_tab_frame0)
        hosts_tab_host_label.setStyleSheet("font-weight: bold;")
        hosts_tab_host_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.hosts_tab_host_line = QLineEdit()
        self.hosts_tab_host_line.returnPressed.connect(self.gen_hosts_tab_table)

        hosts_tab_host_line_completer = common_pyqt5.get_completer(self.bhosts_dic['HOST_NAME'])
        self.hosts_tab_host_line.setCompleter(hosts_tab_host_line_completer)

        # "Check" button.
        hosts_tab_check_button = QPushButton('Check', self.hosts_tab_frame0)
        hosts_tab_check_button.setStyleSheet('''QPushButton:hover{background:rgb(0, 85, 255);}''')
        hosts_tab_check_button.clicked.connect(self.gen_hosts_tab_table)

        # self.hosts_tab_frame0 - Grid
        hosts_tab_frame0_grid = QGridLayout()

        hosts_tab_frame0_grid.addWidget(hosts_tab_status_label, 0, 0)
        hosts_tab_frame0_grid.addWidget(self.hosts_tab_status_combo, 0, 1)
        hosts_tab_frame0_grid.addWidget(hosts_tab_queue_label, 0, 2)
        hosts_tab_frame0_grid.addWidget(self.hosts_tab_queue_combo, 0, 3)
        hosts_tab_frame0_grid.addWidget(hosts_tab_max_label, 0, 4)
        hosts_tab_frame0_grid.addWidget(self.hosts_tab_max_combo, 0, 5)
        hosts_tab_frame0_grid.addWidget(hosts_tab_maxmem_label, 0, 6)
        hosts_tab_frame0_grid.addWidget(self.hosts_tab_maxmem_combo, 0, 7)
        hosts_tab_frame0_grid.addWidget(hosts_tab_host_label, 0, 8)
        hosts_tab_frame0_grid.addWidget(self.hosts_tab_host_line, 0, 9)
        hosts_tab_frame0_grid.addWidget(hosts_tab_check_button, 0, 10)

        hosts_tab_frame0_grid.setColumnStretch(1, 1)
        hosts_tab_frame0_grid.setColumnStretch(2, 1)
        hosts_tab_frame0_grid.setColumnStretch(3, 1)
        hosts_tab_frame0_grid.setColumnStretch(4, 1)
        hosts_tab_frame0_grid.setColumnStretch(5, 1)
        hosts_tab_frame0_grid.setColumnStretch(6, 1)
        hosts_tab_frame0_grid.setColumnStretch(7, 1)
        hosts_tab_frame0_grid.setColumnStretch(8, 1)
        hosts_tab_frame0_grid.setColumnStretch(9, 1)
        hosts_tab_frame0_grid.setColumnStretch(10, 1)

        self.hosts_tab_frame0.setLayout(hosts_tab_frame0_grid)

    def gen_hosts_tab_table(self):
        # self.hosts_tab_table
        self.hosts_tab_table.setShowGrid(True)
        self.hosts_tab_table.setSortingEnabled(True)
        self.hosts_tab_table.setColumnCount(0)
        self.hosts_tab_table.setColumnCount(11)
        self.hosts_tab_table_title_list = ['Host', 'Status', 'Queue', 'MAX', 'Njobs', 'Ut (%)', 'MaxMem (G)', 'Mem (G)', 'MaxSwp (G)', 'Swp (G)', 'Tmp (G)']
        self.hosts_tab_table.setHorizontalHeaderLabels(self.hosts_tab_table_title_list)

        self.hosts_tab_table.setColumnWidth(0, 150)
        self.hosts_tab_table.setColumnWidth(1, 90)
        self.hosts_tab_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.hosts_tab_table.setColumnWidth(3, 60)
        self.hosts_tab_table.setColumnWidth(4, 60)
        self.hosts_tab_table.setColumnWidth(5, 60)
        self.hosts_tab_table.setColumnWidth(6, 100)
        self.hosts_tab_table.setColumnWidth(7, 75)
        self.hosts_tab_table.setColumnWidth(8, 100)
        self.hosts_tab_table.setColumnWidth(9, 75)
        self.hosts_tab_table.setColumnWidth(10, 75)

        # Fill self.hosts_tab_table items.
        hosts_tab_specified_host_list = self.get_hosts_tab_specified_host_list()
        self.hosts_tab_table.setRowCount(0)
        self.hosts_tab_table.setRowCount(len(hosts_tab_specified_host_list))

        # Fresh LSF bhosts/lsload/lshosts/host_queue/bhosts_load information.
        self.fresh_lsf_info('bhosts')
        self.fresh_lsf_info('lsload')
        self.fresh_lsf_info('lshosts')
        self.fresh_lsf_info('host_queue')
        self.fresh_lsf_info('bhosts_load')

        for (i, host) in enumerate(hosts_tab_specified_host_list):
            fatal_error = False

            # Fill "Host" item.
            j = 0
            item = QTableWidgetItem(host)
            item.setFont(QFont('song', 9, QFont.Bold))

            if host == 'lost_and_found':
                fatal_error = True

            if fatal_error:
                item.setBackground(QBrush(Qt.red))

            self.hosts_tab_table.setItem(i, j, item)

            # Fill "Status" item.
            j = j+1
            index = self.bhosts_dic['HOST_NAME'].index(host)
            status = self.bhosts_dic['STATUS'][index]
            item = QTableWidgetItem(status)

            if (str(status) == 'unavail') or (str(status) == 'unreach') or (str(status) == 'closed_LIM'):
                fatal_error = True

            if fatal_error:
                item.setBackground(QBrush(Qt.red))

            self.hosts_tab_table.setItem(i, j, item)

            # Fill "Queue" item.
            j = j+1
            queues = ''

            if host in self.host_queue_dic.keys():
                queues = ' '.join(self.host_queue_dic[host])

            item = QTableWidgetItem(queues)

            if fatal_error:
                item.setBackground(QBrush(Qt.red))

            self.hosts_tab_table.setItem(i, j, item)

            # Fill "MAX" item.
            j = j+1
            index = self.bhosts_dic['HOST_NAME'].index(host)
            max = self.bhosts_dic['MAX'][index]

            if not re.match(r'^[0-9]+$', max):
                common.bprint('Host(' + str(host) + ') MAX info "' + str(max) + '": invalid value, reset it to "0".', date_format='%Y-%m-%d %H:%M:%S', level='Warning')
                max = 0

            item = QTableWidgetItem()
            item.setData(Qt.DisplayRole, int(max))

            if fatal_error:
                item.setBackground(QBrush(Qt.red))

            self.hosts_tab_table.setItem(i, j, item)

            # Fill "Njobs" item.
            j = j+1
            index = self.bhosts_dic['HOST_NAME'].index(host)
            njobs = self.bhosts_dic['NJOBS'][index]

            if not re.match(r'^[0-9]+$', njobs):
                common.bprint('Host(' + str(host) + ') NJOBS info "' + str(njobs) + '": invalid value, reset it to "0".', date_format='%Y-%m-%d %H:%M:%S', level='Warning')
                njobs = 0

            item = QTableWidgetItem()
            item.setData(Qt.DisplayRole, int(njobs))
            item.setFont(QFont('song', 9, QFont.Bold))

            if fatal_error:
                item.setBackground(QBrush(Qt.red))

            self.hosts_tab_table.setItem(i, j, item)

            # Fill "Ut" item.
            j = j+1

            if (host in self.bhosts_load_dic) and ('Total' in self.bhosts_load_dic[host]) and ('ut' in self.bhosts_load_dic[host]['Total']) and (self.bhosts_load_dic[host]['Total']['ut'] != '-'):
                ut = self.bhosts_load_dic[host]['Total']['ut']
            else:
                index = self.lsload_dic['HOST_NAME'].index(host)
                ut = self.lsload_dic['ut'][index]

            ut = re.sub(r'%', '', ut)

            if not re.match(r'^[0-9]+$', ut):
                common.bprint('Host(' + str(host) + ') ut info "' + str(ut) + '": invalid value, reset it to "0".', date_format='%Y-%m-%d %H:%M:%S', level='Warning')
                ut = 0

            item = QTableWidgetItem()
            item.setData(Qt.DisplayRole, int(ut))

            if fatal_error or (int(ut) > 90):
                item.setBackground(QBrush(Qt.red))

            self.hosts_tab_table.setItem(i, j, item)

            # Fill "MaxMem" item.
            j = j+1
            maxmem = '0'

            if host in self.lshosts_dic['HOST_NAME']:
                index = self.lshosts_dic['HOST_NAME'].index(host)
                maxmem = self.lshosts_dic['maxmem'][index]

            if re.search(r'M', maxmem):
                maxmem = float(re.sub(r'M', '', maxmem))/1024
            elif re.search(r'G', maxmem):
                maxmem = re.sub(r'G', '', maxmem)
            elif re.search(r'T', maxmem):
                maxmem = float(re.sub(r'T', '', maxmem))*1024
            else:
                common.bprint('Host(' + str(host) + ') maxmem info "' + str(maxmem) + '": unrecognized unit, reset it to "0".', date_format='%Y-%m-%d %H:%M:%S', level='Warning')
                maxmem = 0

            item = QTableWidgetItem()
            item.setData(Qt.DisplayRole, int(float(maxmem)))

            if fatal_error or (maxmem == 0):
                item.setBackground(QBrush(Qt.red))

            self.hosts_tab_table.setItem(i, j, item)

            # Fill "Mem" item.
            j = j+1

            if (host in self.bhosts_load_dic) and ('Total' in self.bhosts_load_dic[host]) and ('mem' in self.bhosts_load_dic[host]['Total']) and (self.bhosts_load_dic[host]['Total']['mem'] != '-'):
                mem = self.bhosts_load_dic[host]['Total']['mem']
            else:
                index = self.lsload_dic['HOST_NAME'].index(host)
                mem = self.lsload_dic['mem'][index]

            if re.search(r'M', mem):
                mem = float(re.sub(r'M', '', mem))/1024
            elif re.search(r'G', mem):
                mem = re.sub(r'G', '', mem)
            elif re.search(r'T', mem):
                mem = float(re.sub(r'T', '', mem))*1024
            else:
                common.bprint('Host(' + str(host) + ') mem info "' + str(mem) + '": unrecognized unit, reset it to "0".', date_format='%Y-%m-%d %H:%M:%S', level='Warning')
                mem = 0

            item = QTableWidgetItem()
            item.setData(Qt.DisplayRole, int(float(mem)))

            if fatal_error or (maxmem and (float(mem)/float(maxmem) < 0.1)):
                item.setBackground(QBrush(Qt.red))

            self.hosts_tab_table.setItem(i, j, item)

            # Fill "MaxSwp" item.
            j = j+1
            maxswp = '0'

            if host in self.lshosts_dic['HOST_NAME']:
                index = self.lshosts_dic['HOST_NAME'].index(host)
                maxswp = self.lshosts_dic['maxswp'][index]

            if re.search(r'M', maxswp):
                maxswp = float(re.sub(r'M', '', maxswp))/1024
            elif re.search(r'G', maxswp):
                maxswp = re.sub(r'G', '', maxswp)
            elif re.search(r'T', maxswp):
                maxswp = float(re.sub(r'T', '', maxswp))*1024
            else:
                common.bprint('Host(' + str(host) + ') maxswp info "' + str(maxswp) + '": unrecognized unit, reset it to "0".', date_format='%Y-%m-%d %H:%M:%S', level='Warning')
                maxswp = 0

            item = QTableWidgetItem()
            item.setData(Qt.DisplayRole, int(float(maxswp)))

            if fatal_error:
                item.setBackground(QBrush(Qt.red))

            self.hosts_tab_table.setItem(i, j, item)

            # Fill "Swp" item.
            j = j+1

            if (host in self.bhosts_load_dic) and ('Total' in self.bhosts_load_dic[host]) and ('swp' in self.bhosts_load_dic[host]['Total']) and (self.bhosts_load_dic[host]['Total']['swp'] != '-'):
                swp = self.bhosts_load_dic[host]['Total']['swp']
            else:
                index = self.lsload_dic['HOST_NAME'].index(host)
                swp = self.lsload_dic['swp'][index]

            if re.search(r'M', swp):
                swp = float(re.sub(r'M', '', swp))/1024
            elif re.search(r'G', swp):
                swp = re.sub(r'G', '', swp)
            elif re.search(r'T', swp):
                swp = float(re.sub(r'T', '', swp))*1024
            else:
                common.bprint('Host(' + str(host) + ') swp info "' + str(swp) + '": unrecognized unit, reset it to "0".', date_format='%Y-%m-%d %H:%M:%S', level='Warning')
                swp = 0

            item = QTableWidgetItem()
            item.setData(Qt.DisplayRole, int(float(swp)))

            if fatal_error:
                item.setBackground(QBrush(Qt.red))

            self.hosts_tab_table.setItem(i, j, item)

            # Fill "Tmp" item.
            j = j+1

            if (host in self.bhosts_load_dic) and ('Total' in self.bhosts_load_dic[host]) and ('tmp' in self.bhosts_load_dic[host]['Total']) and (self.bhosts_load_dic[host]['Total']['tmp'] != '-'):
                tmp = self.bhosts_load_dic[host]['Total']['tmp']
            else:
                index = self.lsload_dic['HOST_NAME'].index(host)
                tmp = self.lsload_dic['tmp'][index]

            if re.search(r'M', tmp):
                tmp = float(re.sub(r'M', '', tmp))/1024
            elif re.search(r'G', tmp):
                tmp = re.sub(r'G', '', tmp)
            elif re.search(r'T', tmp):
                tmp = float(re.sub(r'T', '', tmp))*1024
            else:
                common.bprint('Host(' + str(host) + ') tmp info "' + str(tmp) + '": unrecognized unit, reset it to "0".', date_format='%Y-%m-%d %H:%M:%S', level='Warning')
                tmp = 0

            item = QTableWidgetItem()
            item.setData(Qt.DisplayRole, int(float(tmp)))

            if fatal_error or (int(float(tmp)) == 0):
                item.setBackground(QBrush(Qt.red))

            self.hosts_tab_table.setItem(i, j, item)

    def gen_hosts_tab_menu(self, pos):
        """
        Generate right click menu on self.hosts_tab_table.
        """
        item = self.hosts_tab_table.itemAt(pos)

        if item and (item.column() == 0):
            menu = QMenu(self.hosts_tab_table)

            open_host_action = QAction('Open', self)
            open_host_action.setIcon(QIcon(str(os.environ['LSFMONITOR_INSTALL_PATH']) + '/data/pictures/open.png'))
            open_host_action.triggered.connect(lambda: self.manage_host_on_hosts_tab(item.text(), 'open'))
            menu.addAction(open_host_action)

            close_host_action = QAction('Close', self)
            close_host_action.setIcon(QIcon(str(os.environ['LSFMONITOR_INSTALL_PATH']) + '/data/pictures/close.png'))
            close_host_action.triggered.connect(lambda: self.manage_host_on_hosts_tab(item.text(), 'close'))
            menu.addAction(close_host_action)

            menu.exec_(self.hosts_tab_table.mapToGlobal(pos))

    def manage_host_on_hosts_tab(self, host_name, behavior):
        """
        Manage specified host with specified behavior(open/close).
        """
        if host_name:
            command = ''

            if behavior == 'open':
                command = 'badmin hopen ' + str(host_name)
            elif behavior == 'close':
                command = 'badmin hclose ' + str(host_name)

            if command:
                common.bprint(command, date_format='%Y-%m-%d %H:%M:%S')
                (return_code, stdout, stderr) = common.run_command(command)

                if return_code == 0:
                    common.bprint(str(behavior) + ' ' + str(host_name) + ' successfully!', date_format='%Y-%m-%d %H:%M:%S')
                    my_show_message = ShowMessage('Info', str(behavior) + ' ' + str(host_name) + ' successfully!')
                    my_show_message.start()
                    time.sleep(5)
                    my_show_message.terminate()
                    self.gen_hosts_tab_table()
                else:
                    common.bprint('Failed on ' + str(behavior) + 'ing host "' + str(host_name) + '".', date_format='%Y-%m-%d %H:%M:%S')
                    common.bprint(str(stderr, 'utf-8').strip(), date_format='%Y-%m-%d %H:%M:%S')
                    my_show_message = ShowMessage(str(behavior) + ' ' + str(host_name) + ' fail', str(str(stderr, 'utf-8')).strip())
                    my_show_message.run()

    def get_hosts_tab_specified_host_list(self):
        """
        Filter host list with specified queue/status/max/maxmem/host.
        """
        specified_status_list = self.hosts_tab_status_combo.currentText().strip().split()
        specified_queue_list = self.hosts_tab_queue_combo.currentText().strip().split()
        specified_max_list = self.hosts_tab_max_combo.currentText().strip().split()
        specified_maxmem_list = self.hosts_tab_maxmem_combo.currentText().strip().split()
        specified_host = self.hosts_tab_host_line.text().strip()
        hosts_tab_specified_host_list = []

        # Fresh LSF bhosts/lshosts/host_queue information.
        self.fresh_lsf_info('bhosts')
        self.fresh_lsf_info('lshosts')
        self.fresh_lsf_info('host_queue')

        for host in self.bhosts_dic['HOST_NAME']:
            # Filter with specified_status_list.
            index = self.bhosts_dic['HOST_NAME'].index(host)
            status = self.bhosts_dic['STATUS'][index]

            if 'ALL' not in specified_status_list:
                continue_mark = True

                for specified_status in specified_status_list:
                    if specified_status == status:
                        continue_mark = False
                        break

                if continue_mark:
                    continue

            # Filter with specified_queue_list.
            if 'ALL' not in specified_queue_list:
                continue_mark = True

                for specified_queue in specified_queue_list:
                    if (host in self.host_queue_dic) and (specified_queue in self.host_queue_dic[host]):
                        continue_mark = False
                        break

                if continue_mark:
                    continue

            # Filter with specified_max_list.
            index = self.bhosts_dic['HOST_NAME'].index(host)
            max = self.bhosts_dic['MAX'][index]

            if not re.match(r'^[0-9]+$', max):
                max = 0

            if 'ALL' not in specified_max_list:
                continue_mark = True

                for specified_max in specified_max_list:
                    if specified_max == str(max):
                        continue_mark = False
                        break

                if continue_mark:
                    continue

            # Filter with specified_maxmem_list.
            if host not in self.lshosts_dic['HOST_NAME']:
                maxmem = 0
            else:
                index = self.lshosts_dic['HOST_NAME'].index(host)
                maxmem = self.lshosts_dic['maxmem'][index]

                if re.search(r'M', maxmem):
                    maxmem = int(float(re.sub(r'M', '', maxmem))/1024)
                elif re.search(r'G', maxmem):
                    maxmem = int(float(re.sub(r'G', '', maxmem)))
                elif re.search(r'T', maxmem):
                    maxmem = int(float(re.sub(r'T', '', maxmem))*1024)
                else:
                    maxmem = 0

            if 'ALL' not in specified_maxmem_list:
                continue_mark = True

                for specified_maxmem in specified_maxmem_list:
                    specified_maxmem = re.sub(r'G', '', specified_maxmem)

                    if specified_maxmem == str(maxmem):
                        continue_mark = False
                        break

                if continue_mark:
                    continue

            # Filter with specified_host.
            if specified_host and (not re.search(specified_host, host)):
                continue

            hosts_tab_specified_host_list.append(host)

        return hosts_tab_specified_host_list

    def hosts_tab_check_click(self, item=None):
        """
        If click the Host name, jump to the LOAD Tab and show the host load inforamtion.
        If click the non-zero Njobs number, jump to the JOBS tab and show the host related jobs information.
        """
        if item is not None:
            current_row = self.hosts_tab_table.currentRow()
            host = self.hosts_tab_table.item(current_row, 0).text().strip()
            njobs_num = self.hosts_tab_table.item(current_row, 5).text().strip()

            if item.column() == 0:
                self.fresh_lsf_info('bhosts')
                host_list = copy.deepcopy(self.bhosts_dic['HOST_NAME'])
                host_list.remove(host)
                host_list.insert(0, host)
                self.set_load_tab_host_combo(host_list)
                self.update_load_tab_load_info()
                self.main_tab.setCurrentWidget(self.load_tab)
            elif item.column() == 4:
                if int(njobs_num) > 0:
                    self.set_jobs_tab_status_combo()
                    self.set_jobs_tab_queue_combo()
                    self.set_jobs_tab_host_combo()

                    for (i, qBox) in enumerate(self.jobs_tab_host_combo.checkBoxList):
                        if qBox.text() == host:
                            self.jobs_tab_host_combo.checkBoxList[i].setChecked(True)
                        else:
                            self.jobs_tab_host_combo.checkBoxList[i].setChecked(False)

                    self.jobs_tab_user_line.setText('')
                    self.gen_jobs_tab_table()
                    self.main_tab.setCurrentWidget(self.jobs_tab)

    def set_hosts_tab_status_combo(self):
        """
        Set (initialize) self.hosts_tab_status_combo.
        """
        self.hosts_tab_status_combo.clear()
        self.fresh_lsf_info('bhosts')

        status_list = ['ALL', ]

        for host in self.bhosts_dic['HOST_NAME']:
            index = self.bhosts_dic['HOST_NAME'].index(host)
            status = self.bhosts_dic['STATUS'][index]

            if status not in status_list:
                status_list.append(status)

        for status in status_list:
            self.hosts_tab_status_combo.addCheckBoxItem(status)

        # Set "ALL" as checked status.
        for (i, qBox) in enumerate(self.hosts_tab_status_combo.checkBoxList):
            if (qBox.text() == 'ALL') and (qBox.isChecked() is False):
                self.hosts_tab_status_combo.checkBoxList[i].setChecked(True)
                break

    def set_hosts_tab_queue_combo(self):
        """
        Set (initialize) self.hosts_tab_queue_combo.
        """
        self.hosts_tab_queue_combo.clear()
        self.fresh_lsf_info('bqueues')

        queue_list = copy.deepcopy(self.queues_dic['QUEUE_NAME'])
        queue_list.sort()
        queue_list.insert(0, 'ALL')

        for queue in queue_list:
            self.hosts_tab_queue_combo.addCheckBoxItem(queue)

        # Set "ALL" as checked status.
        for (i, qBox) in enumerate(self.hosts_tab_queue_combo.checkBoxList):
            if (qBox.text() == 'ALL') and (qBox.isChecked() is False):
                self.hosts_tab_queue_combo.checkBoxList[i].setChecked(True)
                break

    def set_hosts_tab_max_combo(self):
        """
        Set (initialize) self.hosts_tab_max_combo.
        """
        self.hosts_tab_max_combo.clear()
        self.fresh_lsf_info('bhosts')

        max_list = []

        for host in self.bhosts_dic['HOST_NAME']:
            index = self.bhosts_dic['HOST_NAME'].index(host)
            max = self.bhosts_dic['MAX'][index]

            if not re.match(r'^[0-9]+$', max):
                max = 0

            if int(max) not in max_list:
                max_list.append(int(max))

        max_list.sort()
        max_list.insert(0, 'ALL')

        for max in max_list:
            self.hosts_tab_max_combo.addCheckBoxItem(str(max))

        # Set "ALL" as checked status.
        for (i, qBox) in enumerate(self.hosts_tab_max_combo.checkBoxList):
            if (qBox.text() == 'ALL') and (qBox.isChecked() is False):
                self.hosts_tab_max_combo.checkBoxList[i].setChecked(True)
                break

    def set_hosts_tab_maxmem_combo(self):
        """
        Set (initialize) self.hosts_tab_maxmem_combo.
        """
        self.hosts_tab_maxmem_combo.clear()
        self.fresh_lsf_info('bhosts')
        self.fresh_lsf_info('lshosts')

        maxmem_list = []

        for host in self.bhosts_dic['HOST_NAME']:
            if host not in self.lshosts_dic['HOST_NAME']:
                maxmem = 0
            else:
                index = self.lshosts_dic['HOST_NAME'].index(host)
                maxmem = self.lshosts_dic['maxmem'][index]

                # Switch maxmem unit to "G".
                if re.search(r'M', maxmem):
                    maxmem = int(float(re.sub(r'M', '', maxmem))/1024)
                elif re.search(r'G', maxmem):
                    maxmem = int(float(re.sub(r'G', '', maxmem)))
                elif re.search(r'T', maxmem):
                    maxmem = int(float(re.sub(r'T', '', maxmem))*1024)
                else:
                    maxmem = 0

            if maxmem not in maxmem_list:
                maxmem_list.append(maxmem)

        maxmem_list.sort()

        for (i, maxmem) in enumerate(maxmem_list):
            if maxmem == '0':
                maxmem_list[i] = '-'
            else:
                maxmem_list[i] = str(maxmem) + 'G'

        maxmem_list.insert(0, 'ALL')

        for maxmem in maxmem_list:
            self.hosts_tab_maxmem_combo.addCheckBoxItem(maxmem)

        # Set "ALL" as checked status.
        for (i, qBox) in enumerate(self.hosts_tab_maxmem_combo.checkBoxList):
            if (qBox.text() == 'ALL') and (qBox.isChecked() is False):
                self.hosts_tab_maxmem_combo.checkBoxList[i].setChecked(True)
                break

# For hosts TAB (end) #

# For queues TAB (start) #
    def gen_queues_tab(self):
        """
        Generate the queues tab on lsfMonitor GUI, show queues informations.
        """
        # self.queues_tab
        self.queues_tab_table = QTableWidget(self.queues_tab)
        self.queues_tab_table.itemClicked.connect(self.queues_tab_check_click)

        self.queues_tab_frame0 = QFrame(self.queues_tab)
        self.queues_tab_frame0.setFrameShadow(QFrame.Raised)
        self.queues_tab_frame0.setFrameShape(QFrame.Box)

        self.queues_tab_frame1 = QFrame(self.queues_tab)
        self.queues_tab_frame1.setFrameShadow(QFrame.Raised)
        self.queues_tab_frame1.setFrameShape(QFrame.Box)

        self.queues_tab_frame2 = QFrame(self.queues_tab)
        self.queues_tab_frame2.setFrameShadow(QFrame.Raised)
        self.queues_tab_frame2.setFrameShape(QFrame.Box)

        # self.queues_tab - Grid
        queues_tab_grid = QGridLayout()

        queues_tab_grid.addWidget(self.queues_tab_table, 0, 0, 2, 1)
        queues_tab_grid.addWidget(self.queues_tab_frame0, 0, 1)
        queues_tab_grid.addWidget(self.queues_tab_frame1, 1, 1)
        queues_tab_grid.addWidget(self.queues_tab_frame2, 2, 0, 1, 2)

        queues_tab_grid.setRowStretch(0, 1)
        queues_tab_grid.setRowStretch(1, 14)
        queues_tab_grid.setRowStretch(2, 6)

        queues_tab_grid.setColumnStretch(0, 1)
        queues_tab_grid.setColumnStretch(1, 10)

        queues_tab_grid.setColumnMinimumWidth(0, 330)

        self.queues_tab.setLayout(queues_tab_grid)

        # Generate sub-frame
        self.gen_queues_tab_table()
        self.gen_queues_tab_frame0()
        self.gen_queues_tab_frame1()
        self.gen_queues_tab_frame2()

    def gen_queues_tab_table(self):
        self.queues_tab_table.setShowGrid(True)
        self.queues_tab_table.setColumnCount(0)
        self.queues_tab_table.setColumnCount(4)
        self.queues_tab_table_title_list = ['QUEUE', 'SLOTS', 'PEND', 'RUN']
        self.queues_tab_table.setHorizontalHeaderLabels(self.queues_tab_table_title_list)

        self.queues_tab_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.queues_tab_table.setColumnWidth(1, 60)
        self.queues_tab_table.setColumnWidth(2, 60)
        self.queues_tab_table.setColumnWidth(3, 60)

        # Fresh LSF bhosts/queues/queue_host information.
        self.fresh_lsf_info('bhosts')
        self.fresh_lsf_info('bqueues')
        self.fresh_lsf_info('queue_host')

        # Hide the vertical header
        self.queues_tab_table.verticalHeader().setVisible(False)

        # Fill self.queues_tab_table items.
        self.queues_tab_table.setRowCount(0)
        self.queues_tab_table.setRowCount(len(self.queues_dic['QUEUE_NAME'])+1)

        queue_list = copy.deepcopy(self.queues_dic['QUEUE_NAME'])
        queue_list.sort()
        queue_list.append('ALL')

        pend_sum = 0
        run_sum = 0

        for i in range(len(queue_list)):
            queue = queue_list[i]
            index = 0

            if i < len(queue_list)-1:
                index = self.queues_dic['QUEUE_NAME'].index(queue)

            # Fill "QUEUE" item.
            j = 0
            item = QTableWidgetItem(queue)
            self.queues_tab_table.setItem(i, j, item)

            # Fill "SLOTS" item.
            j = j+1
            total = 0

            if queue == 'ALL':
                for max in self.bhosts_dic['MAX']:
                    if re.match(r'^\d+$', max):
                        total += int(max)
            elif queue == 'lost_and_found':
                total = 'N/A'
            else:
                for queue_host in self.queue_host_dic[queue]:
                    host_index = self.bhosts_dic['HOST_NAME'].index(queue_host)
                    host_max = self.bhosts_dic['MAX'][host_index]

                    if re.match(r'^\d+$', host_max):
                        total += int(host_max)

            item = QTableWidgetItem(str(total))
            item.setFont(QFont('song', 9, QFont.Bold))

            if queue == 'lost_and_found':
                item.setForeground(QBrush(Qt.red))

            self.queues_tab_table.setItem(i, j, item)

            # Fill "PEND" item.
            j = j+1

            if i == len(queue_list)-1:
                pend = str(pend_sum)
            else:
                pend = self.queues_dic['PEND'][index]
                pend_sum += int(pend)

            item = QTableWidgetItem(pend)
            item.setFont(QFont('song', 9, QFont.Bold))

            if int(pend) > 0:
                item.setForeground(QBrush(Qt.red))

            self.queues_tab_table.setItem(i, j, item)

            # Fill "RUN" item.
            j = j+1

            if i == len(queue_list)-1:
                run = str(run_sum)
            else:
                run = self.queues_dic['RUN'][index]
                run_sum += int(run)

            item = QTableWidgetItem(run)
            item.setFont(QFont('song', 9, QFont.Bold))
            self.queues_tab_table.setItem(i, j, item)

    def gen_queues_tab_frame0(self):
        # "Begin_Date" item.
        queues_tab_begin_date_label = QLabel('Begin_Date', self.queues_tab_frame0)
        queues_tab_begin_date_label.setStyleSheet("font-weight: bold;")
        queues_tab_begin_date_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.queues_tab_begin_date_edit = QDateEdit(self.queues_tab_frame0)
        self.queues_tab_begin_date_edit.setDisplayFormat('yyyy-MM-dd')
        self.queues_tab_begin_date_edit.setMinimumDate(QDate.currentDate().addDays(-3652))
        self.queues_tab_begin_date_edit.setCalendarPopup(True)
        self.queues_tab_begin_date_edit.setDate(QDate.currentDate().addMonths(-1))

        # "End_Date" item.
        queues_tab_end_date_label = QLabel('End_Date', self.queues_tab_frame0)
        queues_tab_end_date_label.setStyleSheet("font-weight: bold;")
        queues_tab_end_date_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.queues_tab_end_date_edit = QDateEdit(self.queues_tab_frame0)
        self.queues_tab_end_date_edit.setDisplayFormat('yyyy-MM-dd')
        self.queues_tab_end_date_edit.setMinimumDate(QDate.currentDate().addDays(-3652))
        self.queues_tab_end_date_edit.setCalendarPopup(True)
        self.queues_tab_end_date_edit.setDate(QDate.currentDate())

        # self.queues_tab_frame0 - Grid
        queues_tab_frame0_grid = QGridLayout()

        queues_tab_frame0_grid.addWidget(queues_tab_begin_date_label, 0, 0)
        queues_tab_frame0_grid.addWidget(self.queues_tab_begin_date_edit, 0, 1)
        queues_tab_frame0_grid.addWidget(queues_tab_end_date_label, 0, 2)
        queues_tab_frame0_grid.addWidget(self.queues_tab_end_date_edit, 0, 3)

        queues_tab_frame0_grid.setColumnStretch(1, 1)
        queues_tab_frame0_grid.setColumnStretch(2, 1)
        queues_tab_frame0_grid.setColumnStretch(3, 1)

        self.queues_tab_frame0.setLayout(queues_tab_frame0_grid)

    def gen_queues_tab_frame1(self):
        # self.queues_tab_frame1
        self.queues_tab_num_canvas = common_pyqt5.FigureCanvasQTAgg()
        self.queues_tab_num_toolbar = common_pyqt5.NavigationToolbar2QT(self.queues_tab_num_canvas, self)

        # self.queues_tab_frame1 - Grid
        queues_tab_frame1_grid = QGridLayout()
        queues_tab_frame1_grid.addWidget(self.queues_tab_num_toolbar, 0, 0)
        queues_tab_frame1_grid.addWidget(self.queues_tab_num_canvas, 1, 0)
        self.queues_tab_frame1.setLayout(queues_tab_frame1_grid)

    def gen_queues_tab_frame2(self):
        # self.queues_tab_frame2
        self.queues_tab_text = QTextEdit(self.queues_tab_frame2)

        # self.queues_tab_frame2 - Grid
        queues_tab_frame2_grid = QGridLayout()
        queues_tab_frame2_grid.addWidget(self.queues_tab_text, 0, 0)
        self.queues_tab_frame2.setLayout(queues_tab_frame2_grid)

    def queues_tab_check_click(self, item=None):
        """
        If click the QUEUE name, show queue information on QUEUE tab.
        If click the PEND number, jump to the JOBS Tab and show the queue PEND jobs.
        If click the RUN number, jump to the JOB Tab and show the queue RUN jobs.
        """
        if item is not None:
            current_row = self.queues_tab_table.currentRow()
            queue = self.queues_tab_table.item(current_row, 0).text().strip()
            pend_num = self.queues_tab_table.item(current_row, 2).text().strip()
            run_num = self.queues_tab_table.item(current_row, 3).text().strip()

            if item.column() == 0:
                common.bprint('Checking queue "' + str(queue) + '".', date_format='%Y-%m-%d %H:%M:%S')

                self.update_queues_tab_frame1(queue)
                self.update_queues_tab_frame2(queue)
            elif item.column() == 2:
                if (pend_num != '') and (int(pend_num) > 0):
                    self.set_jobs_tab_status_combo()

                    for (i, qBox) in enumerate(self.jobs_tab_status_combo.checkBoxList):
                        if qBox.text() == 'PEND':
                            self.jobs_tab_status_combo.checkBoxList[i].setChecked(True)
                        else:
                            self.jobs_tab_status_combo.checkBoxList[i].setChecked(False)

                    self.set_jobs_tab_queue_combo()

                    for (i, qBox) in enumerate(self.jobs_tab_queue_combo.checkBoxList):
                        if qBox.text() == queue:
                            self.jobs_tab_queue_combo.checkBoxList[i].setChecked(True)
                        else:
                            self.jobs_tab_queue_combo.checkBoxList[i].setChecked(False)

                    self.set_jobs_tab_host_combo()
                    self.jobs_tab_user_line.setText('')
                    self.gen_jobs_tab_table()
                    self.main_tab.setCurrentWidget(self.jobs_tab)
            elif item.column() == 3:
                if (run_num != '') and (int(run_num) > 0):
                    self.set_jobs_tab_status_combo()
                    self.set_jobs_tab_queue_combo()

                    for (i, qBox) in enumerate(self.jobs_tab_queue_combo.checkBoxList):
                        if qBox.text() == queue:
                            self.jobs_tab_queue_combo.checkBoxList[i].setChecked(True)
                        else:
                            self.jobs_tab_queue_combo.checkBoxList[i].setChecked(False)

                    self.set_jobs_tab_host_combo()
                    self.jobs_tab_user_line.setText('')
                    self.gen_jobs_tab_table()
                    self.main_tab.setCurrentWidget(self.jobs_tab)

            # Update queue information first.
            self.gen_queues_tab_table()

    def update_queues_tab_frame1(self, queue):
        """
        Draw queue (PEND/RUN) job number current job on self.queues_tab_frame1.
        """
        fig = self.queues_tab_num_canvas.figure
        fig.clear()
        self.queues_tab_num_canvas.draw()

        (date_list, total_list, pend_list, run_list) = self.get_queue_job_num_list(queue)

        if date_list and pend_list and run_list:
            for i in range(len(date_list)):
                if self.enable_queue_detail:
                    date_list[i] = datetime.datetime.strptime(date_list[i], '%Y%m%d_%H%M%S')
                else:
                    date_list[i] = datetime.datetime.strptime(date_list[i], '%Y%m%d')

            self.draw_queues_tab_num_curve(fig, queue, date_list, total_list, pend_list, run_list)

    def update_queues_tab_frame2(self, queue):
        """
        Show queue detailed informations on self.queues_tab_text.
        """
        self.queues_tab_text.clear()

        command = 'bqueues -l ' + str(queue)
        (return_code, stdout, stderr) = common.run_command(command)

        for (i, line) in enumerate(str(stdout, 'utf-8').split('\n')):
            line = line.strip()

            if (not line) and (i == 0):
                continue

            self.queues_tab_text.insertPlainText(str(line) + '\n')

        common_pyqt5.text_edit_visible_position(self.queues_tab_text, 'Start')

    def get_queue_job_num_list(self, queue):
        """
        Draw (PEND/RUN) job number curve for specified queueu.
        """
        date_list = []
        total_list = []
        pend_list = []
        run_list = []
        queue_db_file = str(self.db_path) + '/queue.db'

        if not os.path.exists(queue_db_file):
            common.bprint('Queue pend/run job number information is missing for "' + str(queue) + '".', date_format='%Y-%m-%d %H:%M:%S', level='Warning')
        else:
            (queue_db_file_connect_result, queue_db_conn) = common_sqlite3.connect_db_file(queue_db_file)

            if queue_db_file_connect_result == 'failed':
                common.bprint('Failed on connecting queue database file "' + str(self.queue_db_file) + '".', date_format='%Y-%m-%d %H:%M:%S', level='Warning')
            else:
                table_name = 'queue_' + str(queue)
                begin_date = self.queues_tab_begin_date_edit.date().toString(Qt.ISODate)
                begin_time = str(begin_date) + ' 00:00:00'
                begin_second = time.mktime(time.strptime(begin_time, '%Y-%m-%d %H:%M:%S'))
                end_date = self.queues_tab_end_date_edit.date().toString(Qt.ISODate)
                end_time = str(end_date) + ' 23:59:59'
                end_second = time.mktime(time.strptime(end_time, '%Y-%m-%d %H:%M:%S'))
                select_condition = 'WHERE sample_second>=' + str(begin_second) + ' AND sample_second<=' + str(end_second)

                data_dic = common_sqlite3.get_sql_table_data(queue_db_file, queue_db_conn, table_name, ['sample_time', 'TOTAL', 'PEND', 'RUN'], select_condition)

                if not data_dic:
                    common.bprint('Queue pend/run job number information is empty for "' + str(queue) + '".', date_format='%Y-%m-%d %H:%M:%S', level='Warning')
                else:
                    if self.enable_queue_detail:
                        date_list = data_dic['sample_time']
                        total_list = [int(i) for i in data_dic['TOTAL']]
                        pend_list = [int(i) for i in data_dic['PEND']]
                        run_list = [int(i) for i in data_dic['RUN']]
                    else:
                        tmp_total_list = []
                        tmp_pend_list = []
                        tmp_run_list = []

                        for i in range(len(data_dic['sample_time'])):
                            sample_time = data_dic['sample_time'][i]
                            date = re.sub(r'_.*', '', sample_time)
                            total_num = data_dic['TOTAL'][i]
                            pend_num = data_dic['PEND'][i]
                            run_num = data_dic['RUN'][i]

                            if (i != 0) and ((i == len(data_dic['sample_time'])-1) or (date not in date_list)):
                                total_avg = int(sum(tmp_total_list)/len(tmp_total_list))
                                total_list.append(total_avg)
                                pend_avg = int(sum(tmp_pend_list)/len(tmp_pend_list))
                                pend_list.append(pend_avg)
                                run_avg = int(sum(tmp_run_list)/len(tmp_run_list))
                                run_list.append(run_avg)

                            if date not in date_list:
                                date_list.append(date)
                                tmp_total_list = []
                                tmp_pend_list = []
                                tmp_run_list = []

                            tmp_total_list.append(int(total_num))
                            tmp_pend_list.append(int(pend_num))
                            tmp_run_list.append(int(run_num))

                    queue_db_conn.close()

        return date_list, total_list, pend_list, run_list

    def draw_queues_tab_num_curve(self, fig, queue, date_list, total_list, pend_list, run_list):
        """
        Draw RUN/PEND job num curve for specified queue.
        """
        fig.subplots_adjust(bottom=0.25)
        axes = fig.add_subplot(111)
        axes.set_title('Trends of RUN/PEND number for queue "' + str(queue) + '"')

        if self.enable_queue_detail:
            axes.set_xlabel('Sample Time')
            expected_linewidth = 0.1
            expected_markersize = 0.1
        else:
            axes.set_xlabel('Sample Date')
            expected_linewidth = 1
            expected_markersize = 1

        axes.set_ylabel('Num')
        axes.plot(date_list, total_list, 'bo-', label='SLOTS', linewidth=expected_linewidth, markersize=expected_markersize)
        axes.fill_between(date_list, total_list, color='lightblue', alpha=0.3)
        axes.plot(date_list, run_list, 'go-', label='RUN', linewidth=expected_linewidth, markersize=expected_markersize)
        axes.fill_between(date_list, run_list, color='green', alpha=0.3)
        axes.plot(date_list, pend_list, 'ro-', label='PEND', linewidth=expected_linewidth, markersize=expected_markersize)
        axes.fill_between(date_list, pend_list, color='red', alpha=0.5)
        axes.legend(loc='upper right')
        axes.tick_params(axis='x', rotation=15)
        axes.grid()
        self.queues_tab_num_canvas.draw()
# For queues TAB (end) #

# For load TAB (start) #
    def gen_load_tab(self):
        """
        Generate the load tab on lsfMonitor GUI, show host load (ut/mem) information.
        """
        # self.load_tab
        self.load_tab_frame0 = QFrame(self.load_tab)
        self.load_tab_frame1 = QFrame(self.load_tab)
        self.load_tab_frame2 = QFrame(self.load_tab)

        self.load_tab_frame0.setFrameShadow(QFrame.Raised)
        self.load_tab_frame0.setFrameShape(QFrame.Box)
        self.load_tab_frame1.setFrameShadow(QFrame.Raised)
        self.load_tab_frame1.setFrameShape(QFrame.Box)
        self.load_tab_frame2.setFrameShadow(QFrame.Raised)
        self.load_tab_frame2.setFrameShape(QFrame.Box)

        # self.load_tab - Grid
        load_tab_grid = QGridLayout()

        load_tab_grid.addWidget(self.load_tab_frame0, 0, 0)
        load_tab_grid.addWidget(self.load_tab_frame1, 1, 0)
        load_tab_grid.addWidget(self.load_tab_frame2, 2, 0)

        load_tab_grid.setRowStretch(0, 1)
        load_tab_grid.setRowStretch(1, 10)
        load_tab_grid.setRowStretch(2, 10)

        self.load_tab.setLayout(load_tab_grid)

        # Generate sub-frame
        self.gen_load_tab_frame0()
        self.gen_load_tab_frame1()
        self.gen_load_tab_frame2()

    def gen_load_tab_frame0(self):
        # self.load_tab_frame0
        # "Host" item.
        load_tab_host_label = QLabel('Host', self.load_tab_frame0)
        load_tab_host_label.setStyleSheet("font-weight: bold;")
        load_tab_host_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.load_tab_host_combo = QComboBox(self.load_tab_frame0)
        self.set_load_tab_host_combo()
        self.load_tab_host_combo.activated.connect(self.update_load_tab_load_info)

        # "Begin_Date" item.
        load_tab_begin_date_label = QLabel('Begin_Date', self.load_tab_frame0)
        load_tab_begin_date_label.setStyleSheet("font-weight: bold;")
        load_tab_begin_date_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.load_tab_begin_date_edit = QDateEdit(self.load_tab_frame0)
        self.load_tab_begin_date_edit.setDisplayFormat('yyyy-MM-dd')
        self.load_tab_begin_date_edit.setMinimumDate(QDate.currentDate().addDays(-3652))
        self.load_tab_begin_date_edit.setCalendarPopup(True)
        self.load_tab_begin_date_edit.setDate(QDate.currentDate().addDays(-7))

        # "End_Date" item.
        load_tab_end_date_label = QLabel('End_Date', self.load_tab_frame0)
        load_tab_end_date_label.setStyleSheet("font-weight: bold;")
        load_tab_end_date_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.load_tab_end_date_edit = QDateEdit(self.load_tab_frame0)
        self.load_tab_end_date_edit.setDisplayFormat('yyyy-MM-dd')
        self.load_tab_end_date_edit.setMinimumDate(QDate.currentDate().addDays(-3652))
        self.load_tab_end_date_edit.setCalendarPopup(True)
        self.load_tab_end_date_edit.setDate(QDate.currentDate())

        # "Check" button.
        load_tab_check_button = QPushButton('Check', self.load_tab_frame0)
        load_tab_check_button.setStyleSheet('''QPushButton:hover{background:rgb(0, 85, 255);}''')
        load_tab_check_button.clicked.connect(self.update_load_tab_load_info)

        # self.load_tab_frame0 - Grid
        load_tab_frame0_grid = QGridLayout()

        load_tab_frame0_grid.addWidget(load_tab_host_label, 0, 0)
        load_tab_frame0_grid.addWidget(self.load_tab_host_combo, 0, 1)
        load_tab_frame0_grid.addWidget(load_tab_begin_date_label, 0, 2)
        load_tab_frame0_grid.addWidget(self.load_tab_begin_date_edit, 0, 3)
        load_tab_frame0_grid.addWidget(load_tab_end_date_label, 0, 4)
        load_tab_frame0_grid.addWidget(self.load_tab_end_date_edit, 0, 5)
        load_tab_frame0_grid.addWidget(load_tab_check_button, 0, 6)

        load_tab_frame0_grid.setColumnStretch(1, 1)
        load_tab_frame0_grid.setColumnStretch(2, 1)
        load_tab_frame0_grid.setColumnStretch(3, 1)
        load_tab_frame0_grid.setColumnStretch(4, 1)
        load_tab_frame0_grid.setColumnStretch(5, 1)
        load_tab_frame0_grid.setColumnStretch(6, 1)

        self.load_tab_frame0.setLayout(load_tab_frame0_grid)

    def gen_load_tab_frame1(self):
        # self.load_tab_frame1
        self.load_tab_ut_canvas = common_pyqt5.FigureCanvasQTAgg()
        self.host_tab_ut_toolbar = common_pyqt5.NavigationToolbar2QT(self.load_tab_ut_canvas, self)

        # self.load_tab_frame1 - Grid
        load_tab_frame1_grid = QGridLayout()
        load_tab_frame1_grid.addWidget(self.host_tab_ut_toolbar, 0, 0)
        load_tab_frame1_grid.addWidget(self.load_tab_ut_canvas, 1, 0)
        self.load_tab_frame1.setLayout(load_tab_frame1_grid)

    def gen_load_tab_frame2(self):
        # self.load_tab_frame2
        self.load_tab_mem_canvas = common_pyqt5.FigureCanvasQTAgg()
        self.host_tab_mem_toolbar = common_pyqt5.NavigationToolbar2QT(self.load_tab_mem_canvas, self)

        # self.load_tab_frame2 - Grid
        load_tab_frame2_grid = QGridLayout()
        load_tab_frame2_grid.addWidget(self.host_tab_mem_toolbar, 0, 0)
        load_tab_frame2_grid.addWidget(self.load_tab_mem_canvas, 1, 0)
        self.load_tab_frame2.setLayout(load_tab_frame2_grid)

    def set_load_tab_host_combo(self, host_list=[]):
        """
        Set (initialize) self.load_tab_host_combo.
        """
        self.load_tab_host_combo.clear()

        if not host_list:
            self.fresh_lsf_info('bhosts')
            host_list = copy.deepcopy(self.bhosts_dic['HOST_NAME'])
            host_list.insert(0, '')

        for host in host_list:
            self.load_tab_host_combo.addItem(host)

    def update_load_tab_load_info(self):
        """
        Update self.load_tab_frame1 (ut information) and self.load_tab_frame2 (memory information).
        """
        specified_host = self.load_tab_host_combo.currentText().strip()

        if not specified_host:
            warning_message = '*Warning*: No host is specified.'
            self.gui_warning(warning_message)
            return

        self.update_load_tab_frame1(specified_host, [], [])
        self.update_load_tab_frame2(specified_host, [], [])

        common.bprint('Loading ut/mem load information, please wait a moment ...', date_format='%Y-%m-%d %H:%M:%S')

        my_show_message = ShowMessage('Info', 'Loading ut/mem load information, please wait a moment ...')
        my_show_message.start()

        (sample_time_list, ut_list, mem_list) = self.get_load_info(specified_host)

        time.sleep(0.01)
        my_show_message.terminate()

        if sample_time_list:
            self.update_load_tab_frame1(specified_host, sample_time_list, ut_list)
            self.update_load_tab_frame2(specified_host, sample_time_list, mem_list)

    def get_load_info(self, specified_host):
        """
        Get sample_time/ut/mem list for specified host.
        """
        sample_time_list = []
        ut_list = []
        mem_list = []

        load_db_file = str(self.db_path) + '/load.db'

        if not os.path.exists(load_db_file):
            common.bprint('Load database "' + str(load_db_file) + '" is missing.', date_format='%Y-%m-%d %H:%M:%S', level='Warning')
        else:
            (load_db_file_connect_result, load_db_conn) = common_sqlite3.connect_db_file(load_db_file)

            if load_db_file_connect_result == 'failed':
                common.bprint('Failed on connecting load database file "' + str(load_db_file) + '".', date_format='%Y-%m-%d %H:%M:%S', level='Warning')
            else:
                if specified_host:
                    table_name = 'load_' + str(specified_host)
                    begin_date = self.load_tab_begin_date_edit.date().toString(Qt.ISODate)
                    begin_time = str(begin_date) + ' 00:00:00'
                    begin_second = time.mktime(time.strptime(begin_time, '%Y-%m-%d %H:%M:%S'))
                    end_date = self.load_tab_end_date_edit.date().toString(Qt.ISODate)
                    end_time = str(end_date) + ' 23:59:59'
                    end_second = time.mktime(time.strptime(end_time, '%Y-%m-%d %H:%M:%S'))
                    select_condition = "WHERE sample_second BETWEEN '" + str(begin_second) + "' AND '" + str(end_second) + "'"
                    data_dic = common_sqlite3.get_sql_table_data(load_db_file, load_db_conn, table_name, ['sample_time', 'ut', 'mem'], select_condition)

                    if not data_dic:
                        common.bprint('Load information is empty for "' + str(specified_host) + '".', date_format='%Y-%m-%d %H:%M:%S', level='Warning')
                    else:
                        for (i, sample_time) in enumerate(data_dic['sample_time']):
                            # For sample_time
                            sample_time = datetime.datetime.strptime(data_dic['sample_time'][i], '%Y%m%d_%H%M%S')
                            sample_time_list.append(sample_time)

                            # For ut
                            ut = data_dic['ut'][i]

                            if ut:
                                ut = int(re.sub(r'%', '', ut))
                            else:
                                ut = 0

                            ut_list.append(ut)

                            # For mem
                            mem = data_dic['mem'][i]

                            if mem:
                                if re.match(r'.*M', mem):
                                    mem = round(float(re.sub(r'M', '', mem))/1024, 1)
                                elif re.match(r'.*G', mem):
                                    mem = round(float(re.sub(r'G', '', mem)), 1)
                                elif re.match(r'.*T', mem):
                                    mem = round(float(re.sub(r'T', '', mem))*1024, 1)
                            else:
                                mem = 0

                            mem_list.append(mem)

                    load_db_conn.close()

        return sample_time_list, ut_list, mem_list

    def update_load_tab_frame1(self, specified_host, sample_time_list, ut_list):
        """
        Draw Ut curve for specified host on self.load_tab_frame1.
        """
        fig = self.load_tab_ut_canvas.figure
        fig.clear()
        self.load_tab_ut_canvas.draw()

        if sample_time_list and ut_list:
            self.draw_load_tab_ut_curve(fig, specified_host, sample_time_list, ut_list)

    def draw_load_tab_ut_curve(self, fig, specified_host, sample_time_list, ut_list):
        """
        Draw ut curve for specified host.
        """
        fig.subplots_adjust(bottom=0.25)
        axes = fig.add_subplot(111)
        axes.set_title('ut curve for host "' + str(specified_host) + '"')
        axes.set_xlabel('Sample Time')
        axes.set_ylabel('Cpu Utilization (%)')
        axes.plot(sample_time_list, ut_list, 'ro-', label='CPU', linewidth=0.1, markersize=0.1)
        axes.fill_between(sample_time_list, ut_list, color='red', alpha=0.5)
        axes.legend(loc='upper right')
        axes.tick_params(axis='x', rotation=15)
        axes.grid()
        self.load_tab_ut_canvas.draw()

    def update_load_tab_frame2(self, specified_host, sample_time_list, mem_list):
        """
        Draw mem curve for specified host on self.load_tab_frame2.
        """
        fig = self.load_tab_mem_canvas.figure
        fig.clear()
        self.load_tab_mem_canvas.draw()

        if sample_time_list and mem_list:
            self.draw_load_tab_mem_curve(fig, specified_host, sample_time_list, mem_list)

    def draw_load_tab_mem_curve(self, fig, specified_host, sample_time_list, mem_list):
        """
        Draw mem curve for specified host.
        """
        fig.subplots_adjust(bottom=0.25)
        axes = fig.add_subplot(111)
        axes.set_title('available mem curve for host "' + str(specified_host) + '"')
        axes.set_xlabel('Sample Time')
        axes.set_ylabel('Available Mem (G)')
        axes.plot(sample_time_list, mem_list, 'go-', label='MEM', linewidth=0.1, markersize=0.1)
        axes.fill_between(sample_time_list, mem_list, color='green', alpha=0.5)
        axes.legend(loc='upper right')
        axes.tick_params(axis='x', rotation=15)
        axes.grid()
        self.load_tab_mem_canvas.draw()
# For load TAB (end) #

# For utilization TAB (start) #
    def gen_utilization_tab(self):
        """
        Generate the utilization tab on lsfMonitor GUI, show host utilization (slot/cpu/mem) information.
        """
        self.utilization_tab_resource_list = ['slot', 'cpu', 'mem']

        # self.utilization_tab
        self.utilization_tab_frame0 = QFrame(self.utilization_tab)
        self.utilization_tab_frame0.setFrameShadow(QFrame.Raised)
        self.utilization_tab_frame0.setFrameShape(QFrame.Box)

        self.utilization_tab_table = QTableWidget(self.utilization_tab)

        self.utilization_tab_frame1 = QFrame(self.utilization_tab)
        self.utilization_tab_frame1.setFrameShadow(QFrame.Raised)
        self.utilization_tab_frame1.setFrameShape(QFrame.Box)

        # self.utilization_tab - Grid
        utilization_tab_grid = QGridLayout()

        utilization_tab_grid.addWidget(self.utilization_tab_frame0, 0, 0, 1, 2)
        utilization_tab_grid.addWidget(self.utilization_tab_table, 1, 0)
        utilization_tab_grid.addWidget(self.utilization_tab_frame1, 1, 1)

        utilization_tab_grid.setRowStretch(0, 1)
        utilization_tab_grid.setRowStretch(1, 10)

        utilization_tab_grid.setColumnStretch(0, 1)
        utilization_tab_grid.setColumnStretch(1, 2)

        self.utilization_tab.setLayout(utilization_tab_grid)

        # Generate sub-frame
        self.gen_utilization_tab_frame0()
        self.gen_utilization_tab_table()
        self.gen_utilization_tab_frame1()
        self.update_utilization_tab_info()

    def gen_utilization_tab_frame0(self):
        # self.utilization_tab_frame0
        # "Queue" item.
        utilization_tab_queue_label = QLabel('Queue', self.utilization_tab_frame0)
        utilization_tab_queue_label.setStyleSheet("font-weight: bold;")
        utilization_tab_queue_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.utilization_tab_queue_combo = common_pyqt5.QComboCheckBox(self.utilization_tab_frame0)
        self.set_utilization_tab_queue_combo()
        self.utilization_tab_queue_combo.currentTextChanged.connect(self.update_utilization_tab_host_combo)

        # "Host" item.
        utilization_tab_host_label = QLabel('Host', self.utilization_tab_frame0)
        utilization_tab_host_label.setStyleSheet("font-weight: bold;")
        utilization_tab_host_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.utilization_tab_host_combo = common_pyqt5.QComboCheckBox(self.utilization_tab_frame0)
        self.set_utilization_tab_host_combo(select_all=True)

        # "Resource" item.
        utilization_tab_resource_label = QLabel('Resource', self.utilization_tab_frame0)
        utilization_tab_resource_label.setStyleSheet("font-weight: bold;")
        utilization_tab_resource_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.utilization_tab_resource_combo = common_pyqt5.QComboCheckBox(self.utilization_tab_frame0)
        self.set_utilization_tab_resource_combo()

        # "Check" button.
        utilization_tab_check_button = QPushButton('Check', self.utilization_tab_frame0)
        utilization_tab_check_button.setStyleSheet('''QPushButton:hover{background:rgb(0, 85, 255);}''')
        utilization_tab_check_button.clicked.connect(self.update_utilization_tab_info)

        # "Begin_Date" item.
        utilization_tab_begin_date_label = QLabel('Begin_Date', self.utilization_tab_frame0)
        utilization_tab_begin_date_label.setStyleSheet("font-weight: bold;")
        utilization_tab_begin_date_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.utilization_tab_begin_date_edit = QDateEdit(self.utilization_tab_frame0)
        self.utilization_tab_begin_date_edit.setDisplayFormat('yyyy-MM-dd')
        self.utilization_tab_begin_date_edit.setMinimumDate(QDate.currentDate().addDays(-3652))
        self.utilization_tab_begin_date_edit.setCalendarPopup(True)
        self.utilization_tab_begin_date_edit.setDate(QDate.currentDate().addMonths(-1))

        # "End_Date" item.
        utilization_tab_end_date_label = QLabel('End_Date', self.utilization_tab_frame0)
        utilization_tab_end_date_label.setStyleSheet("font-weight: bold;")
        utilization_tab_end_date_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.utilization_tab_end_date_edit = QDateEdit(self.utilization_tab_frame0)
        self.utilization_tab_end_date_edit.setDisplayFormat('yyyy-MM-dd')
        self.utilization_tab_end_date_edit.setMinimumDate(QDate.currentDate().addDays(-3652))
        self.utilization_tab_end_date_edit.setCalendarPopup(True)
        self.utilization_tab_end_date_edit.setDate(QDate.currentDate())

        # empty item.
        utilization_tab_empty_label = QLabel('', self.utilization_tab_frame0)

        # Export button.
        utilization_tab_export_button = QPushButton('Export', self.utilization_tab_frame0)
        utilization_tab_export_button.setStyleSheet('''QPushButton:hover{background:rgb(170, 255, 127);}''')
        utilization_tab_export_button.clicked.connect(self.export_utilization_table)

        # self.utilization_tab_frame0 - Grid
        utilization_tab_frame0_grid = QGridLayout()

        utilization_tab_frame0_grid.addWidget(utilization_tab_queue_label, 0, 0)
        utilization_tab_frame0_grid.addWidget(self.utilization_tab_queue_combo, 0, 1)
        utilization_tab_frame0_grid.addWidget(utilization_tab_host_label, 0, 2)
        utilization_tab_frame0_grid.addWidget(self.utilization_tab_host_combo, 0, 3)
        utilization_tab_frame0_grid.addWidget(utilization_tab_resource_label, 0, 4)
        utilization_tab_frame0_grid.addWidget(self.utilization_tab_resource_combo, 0, 5)
        utilization_tab_frame0_grid.addWidget(utilization_tab_check_button, 0, 6)
        utilization_tab_frame0_grid.addWidget(utilization_tab_begin_date_label, 1, 0)
        utilization_tab_frame0_grid.addWidget(self.utilization_tab_begin_date_edit, 1, 1)
        utilization_tab_frame0_grid.addWidget(utilization_tab_end_date_label, 1, 2)
        utilization_tab_frame0_grid.addWidget(self.utilization_tab_end_date_edit, 1, 3)
        utilization_tab_frame0_grid.addWidget(utilization_tab_empty_label, 1, 4, 1, 2)
        utilization_tab_frame0_grid.addWidget(utilization_tab_export_button, 1, 6)

        utilization_tab_frame0_grid.setColumnStretch(1, 1)
        utilization_tab_frame0_grid.setColumnStretch(2, 1)
        utilization_tab_frame0_grid.setColumnStretch(3, 1)
        utilization_tab_frame0_grid.setColumnStretch(4, 1)
        utilization_tab_frame0_grid.setColumnStretch(5, 1)
        utilization_tab_frame0_grid.setColumnStretch(6, 1)

        self.utilization_tab_frame0.setLayout(utilization_tab_frame0_grid)

    def set_utilization_tab_queue_combo(self):
        """
        Set (initialize) self.utilization_tab_queue_combo.
        """
        self.utilization_tab_queue_combo.clear()
        self.fresh_lsf_info('bqueues')

        queue_list = copy.deepcopy(self.queues_dic['QUEUE_NAME'])
        queue_list.sort()
        queue_list.insert(0, 'ALL')

        for queue in queue_list:
            self.utilization_tab_queue_combo.addCheckBoxItem(queue)

        # Set "ALL" as checked status.
        for (i, qBox) in enumerate(self.utilization_tab_queue_combo.checkBoxList):
            if (qBox.text() == 'ALL') and (qBox.isChecked() is False):
                self.utilization_tab_queue_combo.checkBoxList[i].setChecked(True)
                break

    def set_utilization_tab_host_combo(self, host_list=[], select_all=False):
        """
        Set (initialize) self.utilization_tab_host_combo.
        """
        self.utilization_tab_host_combo.clear()

        if not host_list:
            self.fresh_lsf_info('bhosts')
            host_list = copy.deepcopy(self.bhosts_dic['HOST_NAME'])

        for host in host_list:
            self.utilization_tab_host_combo.addCheckBoxItem(host)

        if select_all:
            self.utilization_tab_host_combo.selectAllItems()

    def set_utilization_tab_resource_combo(self):
        """
        Set (initialize) self.utilization_tab_date_combo.
        """
        self.utilization_tab_resource_combo.clear()

        for resource in self.utilization_tab_resource_list:
            self.utilization_tab_resource_combo.addCheckBoxItem(resource)

        # Set all resources as checked status.
        self.utilization_tab_resource_combo.selectAllItems()

    def update_utilization_tab_host_combo(self):
        """
        Update self.utilization_tab_host_combo with self.utilization_tab_queue_combo value.
        """
        # Get host_list based on selected queue info.
        selected_host_list = []
        selected_queue_dic = self.utilization_tab_queue_combo.selectedItems()

        if 'ALL' in selected_queue_dic.values():
            self.fresh_lsf_info('bhosts')
            selected_host_list = copy.deepcopy(self.bhosts_dic['HOST_NAME'])
        else:
            self.fresh_lsf_info('queue_host')

            for selected_queue in selected_queue_dic.values():
                host_list = self.queue_host_dic[selected_queue]

                for host in host_list:
                    if host not in selected_host_list:
                        selected_host_list.append(host)

        # Update self.utilization_tab_host_combo with new host_list.
        if selected_host_list:
            self.set_utilization_tab_host_combo(host_list=selected_host_list, select_all=True)
        else:
            self.set_utilization_tab_host_combo()

    def update_utilization_tab_info(self):
        """
        Update self.utilization_tab_table and self.utilization_tab_frame1.
        """
        queue_utilization_dic = self.get_queue_utilization_info()

        if queue_utilization_dic:
            self.gen_utilization_tab_table(queue_utilization_dic)

        self.update_utilization_tab_frame1()

    def get_queue_utilization_info(self):
        """
        Get sample_time/ut/mem list for specified queues.
        """
        common.bprint('Loading queue utilization info, please wait a moment ...', date_format='%Y-%m-%d %H:%M:%S')

        my_show_message = ShowMessage('Info', 'Loading queue utilization info, please wait a moment ...')
        my_show_message.start()

        utilization_dic = {}
        utilization_db_file = str(self.db_path) + '/utilization_day.db'

        if not os.path.exists(utilization_db_file):
            common.bprint('Utilization database "' + str(utilization_db_file) + '" is missing.', date_format='%Y-%m-%d %H:%M:%S', level='Warning')
        else:
            (utilization_db_file_connect_result, utilization_db_conn) = common_sqlite3.connect_db_file(utilization_db_file)

            if utilization_db_file_connect_result == 'failed':
                common.bprint('Failed on connecting utilization database file "' + str(utilization_db_file) + '".', date_format='%Y-%m-%d %H:%M:%S', level='Warning')
            else:
                self.fresh_lsf_info('bhosts')
                host_list = copy.deepcopy(self.bhosts_dic['HOST_NAME'])

                if host_list:
                    for host_name in host_list:
                        table_name = 'utilization_' + str(host_name)
                        utilization_dic.setdefault(host_name, {})
                        key_list = copy.deepcopy(self.utilization_tab_resource_list)
                        key_list.insert(0, 'sample_date')
                        begin_date = self.utilization_tab_begin_date_edit.date().toString(Qt.ISODate)
                        begin_date = re.sub('-', '', begin_date)
                        end_date = self.utilization_tab_end_date_edit.date().toString(Qt.ISODate)
                        end_date = re.sub('-', '', end_date)
                        select_condition = 'WHERE sample_date>=' + str(begin_date) + ' AND sample_date<=' + str(end_date)
                        data_dic = common_sqlite3.get_sql_table_data(utilization_db_file, utilization_db_conn, table_name, key_list, select_condition)

                        if not data_dic:
                            continue
                        else:
                            for resource in self.utilization_tab_resource_list:
                                utilization_dic[host_name].setdefault(resource, 0.0)
                                utilization_list = []

                                for utilization in data_dic[resource]:
                                    utilization = float(utilization)

                                    if int(utilization) >= 100:
                                        utilization = 100.0

                                    utilization_list.append(utilization)

                                if utilization_list:
                                    avg_utilization = round((sum(utilization_list)/len(utilization_list)), 1)
                                    utilization_dic[host_name][resource] = avg_utilization

            utilization_db_conn.close()

        # Organize utilization info, get average utlization for every queue.
        queue_utilization_dic = {}
        self.fresh_lsf_info('bqueues')
        queue_list = copy.deepcopy(self.queues_dic['QUEUE_NAME'])
        queue_list.sort()
        queue_list.append('ALL')

        # Init queue_utilization_dic.
        for queue in queue_list:
            queue_utilization_dic.setdefault(queue, {})

            for resource in self.utilization_tab_resource_list:
                queue_utilization_dic[queue].setdefault(resource, [])

        # Fill queue_utilization_dic detailed data.
        self.fresh_lsf_info('host_queue')

        for host_name in utilization_dic.keys():
            if host_name in self.host_queue_dic:
                for resource in self.utilization_tab_resource_list:
                    if resource in utilization_dic[host_name]:
                        for queue in self.host_queue_dic[host_name]:
                            queue_utilization_dic[queue][resource].append(utilization_dic[host_name][resource])

                        queue_utilization_dic['ALL'][resource].append(utilization_dic[host_name][resource])

        # Get queue_utilization_dic average utilizaton data.
        for queue in queue_utilization_dic.keys():
            for resource in self.utilization_tab_resource_list:
                utilization_list = queue_utilization_dic[queue][resource]

                if utilization_list:
                    queue_utilization_dic[queue][resource] = round((sum(utilization_list)/len(utilization_list)), 1)

        time.sleep(0.01)
        my_show_message.terminate()

        return queue_utilization_dic

    def get_utilization_info(self, selected_host_list, selected_resource_list):
        """
        Get sample_time/ut/mem list for specified host.
        """
        common.bprint('Loading resource utilization information, please wait a moment ...', date_format='%Y-%m-%d %H:%M:%S')

        my_show_message = ShowMessage('Info', 'Loading resource utilization information, please wait a moment ...')
        my_show_message.start()

        utilization_dic = {}

        if self.enable_utilization_detail:
            utilization_db_file = str(self.db_path) + '/utilization.db'
        else:
            utilization_db_file = str(self.db_path) + '/utilization_day.db'

        if not os.path.exists(utilization_db_file):
            common.bprint('Utilization database "' + str(utilization_db_file) + '" is missing.', date_format='%Y-%m-%d %H:%M:%S', level='Warning')
        else:
            (utilization_db_file_connect_result, utilization_db_conn) = common_sqlite3.connect_db_file(utilization_db_file)

            if utilization_db_file_connect_result == 'failed':
                common.bprint('Failed on connecting utilization database file "' + str(utilization_db_file) + '".', date_format='%Y-%m-%d %H:%M:%S', level='Warning')
            else:
                if selected_host_list:
                    for selected_host in selected_host_list:
                        table_name = 'utilization_' + str(selected_host)
                        key_list = copy.deepcopy(selected_resource_list)

                        if self.enable_utilization_detail:
                            key_list.insert(0, 'sample_time')
                            begin_date = self.utilization_tab_begin_date_edit.date().toString(Qt.ISODate)
                            begin_time = str(begin_date) + ' 00:00:00'
                            begin_second = time.mktime(time.strptime(begin_time, '%Y-%m-%d %H:%M:%S'))
                            end_date = self.utilization_tab_end_date_edit.date().toString(Qt.ISODate)
                            end_time = str(end_date) + ' 23:59:59'
                            end_second = time.mktime(time.strptime(end_time, '%Y-%m-%d %H:%M:%S'))
                            select_condition = 'WHERE sample_second>=' + str(begin_second) + ' AND sample_second<=' + str(end_second)
                        else:
                            key_list.insert(0, 'sample_date')
                            begin_date = self.utilization_tab_begin_date_edit.date().toString(Qt.ISODate)
                            begin_date = re.sub('-', '', begin_date)
                            end_date = self.utilization_tab_end_date_edit.date().toString(Qt.ISODate)
                            end_date = re.sub('-', '', end_date)
                            select_condition = 'WHERE sample_date>=' + str(begin_date) + ' AND sample_date<=' + str(end_date)

                        data_dic = common_sqlite3.get_sql_table_data(utilization_db_file, utilization_db_conn, table_name, key_list, select_condition)

                        if not data_dic:
                            common.bprint('Utilization information is empty for "' + str(selected_host) + '".', date_format='%Y-%m-%d %H:%M:%S', level='Warning')
                        else:
                            if self.enable_utilization_detail:
                                key = 'sample_time'
                            else:
                                key = 'sample_date'

                            for (i, sample_date) in enumerate(data_dic[key]):
                                for selected_resource in selected_resource_list:
                                    if i == 0:
                                        utilization_dic.setdefault(selected_resource, {})

                                    utilization = float(data_dic[selected_resource][i])

                                    if int(utilization) >= 100:
                                        utilization = 100.0

                                    utilization_dic[selected_resource].setdefault(sample_date, {})
                                    utilization_dic[selected_resource][sample_date].setdefault(selected_host, utilization)

            utilization_db_conn.close()

        # Organize utilization info, get average utlization for sample_date.
        for selected_resource in utilization_dic.keys():
            for sample_date in utilization_dic[selected_resource].keys():
                utilization_list = list(utilization_dic[selected_resource][sample_date].values())
                utilization_dic[selected_resource][sample_date] = round((sum(utilization_list)/len(utilization_list)), 1)

        time.sleep(0.01)
        my_show_message.terminate()

        return utilization_dic

    def gen_utilization_tab_table(self, queue_utilization_dic={}):
        """
        Generte self.utilization_tab_table.
        """
        self.utilization_tab_table.setShowGrid(True)
        self.utilization_tab_table.setSortingEnabled(True)
        self.utilization_tab_table.setColumnCount(0)
        self.utilization_tab_table.setColumnCount(5)
        self.utilization_tab_table.setRowCount(0)
        self.utilization_tab_table.setRowCount(len(queue_utilization_dic))
        self.utilization_tab_table_title_list = ['Queue', 'slots', 'slot(%)', 'cpu(%)', 'mem(%)']
        self.utilization_tab_table.setHorizontalHeaderLabels(self.utilization_tab_table_title_list)
        self.utilization_tab_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.utilization_tab_table.setColumnWidth(1, 60)
        self.utilization_tab_table.setColumnWidth(2, 60)
        self.utilization_tab_table.setColumnWidth(3, 60)
        self.utilization_tab_table.setColumnWidth(4, 60)

        # Fresh LSF bhosts/queues/queue_host information.
        self.fresh_lsf_info('bhosts')
        self.fresh_lsf_info('queue_host')

        # Fill self.utilization_tab_table items.
        if queue_utilization_dic:
            row = -1

            for queue in queue_utilization_dic.keys():
                row += 1

                # Fill "Queue" item.
                item = QTableWidgetItem(queue)
                self.utilization_tab_table.setItem(row, 0, item)

                # Fill "slots" item.
                total = 0

                if queue == 'ALL':
                    for max in self.bhosts_dic['MAX']:
                        if re.match(r'^\d+$', max):
                            total += int(max)
                elif queue == 'lost_and_found':
                    total = 'N/A'
                else:
                    for queue_host in self.queue_host_dic[queue]:
                        host_index = self.bhosts_dic['HOST_NAME'].index(queue_host)
                        host_max = self.bhosts_dic['MAX'][host_index]

                        if re.match(r'^\d+$', host_max):
                            total += int(host_max)

                item = QTableWidgetItem(str(total))

                if queue == 'lost_and_found':
                    item.setForeground(QBrush(Qt.red))

                self.utilization_tab_table.setItem(row, 1, item)

                for (i, resource) in enumerate(self.utilization_tab_resource_list):
                    # Fill <resource> item.
                    item = QTableWidgetItem()
                    item.setData(Qt.DisplayRole, queue_utilization_dic[queue][resource])
                    self.utilization_tab_table.setItem(row, i+2, item)

    def gen_utilization_tab_frame1(self):
        """
        Generte self.utilization_tab_frame1.
        """
        # self.utilization_tab_frame1
        self.utilization_tab_utilization_canvas = common_pyqt5.FigureCanvasQTAgg()
        self.utilization_tab_utilization_toolbar = common_pyqt5.NavigationToolbar2QT(self.utilization_tab_utilization_canvas, self)

        # self.utilization_tab_frame1 - Grid
        utilization_tab_frame1_grid = QGridLayout()
        utilization_tab_frame1_grid.addWidget(self.utilization_tab_utilization_toolbar, 0, 0)
        utilization_tab_frame1_grid.addWidget(self.utilization_tab_utilization_canvas, 1, 0)
        self.utilization_tab_frame1.setLayout(utilization_tab_frame1_grid)

    def update_utilization_tab_frame1(self):
        """
        Draw Ut curve for specified host on self.utilization_tab_frame1.
        """
        # Generate figure.
        fig = self.utilization_tab_utilization_canvas.figure
        fig.clear()
        self.utilization_tab_utilization_canvas.draw()

        # Update figure.
        selected_host_dic = self.utilization_tab_host_combo.selectedItems()
        selected_host_list = list(selected_host_dic.values())

        if not selected_host_list:
            warning_message = '*Warning*: No queue/host is specified.'
            self.gui_warning(warning_message)
            return

        selected_resource_dic = self.utilization_tab_resource_combo.selectedItems()
        selected_resource_list = list(selected_resource_dic.values())

        if not selected_resource_list:
            warning_message = '*Warning*: No resource is specified.'
            self.gui_warning(warning_message)
            return

        if selected_host_list and selected_resource_list:
            utilization_dic = self.get_utilization_info(selected_host_list, selected_resource_list)

            if utilization_dic:
                self.draw_utilization_tab_utilization_curve(fig, utilization_dic)

    def draw_utilization_tab_utilization_curve(self, fig, utilization_dic):
        """
        Draw slot/cpu/mem utilization curve for specified host(s).
        """
        fig.subplots_adjust(bottom=0.25)
        axes = fig.add_subplot(111)

        # Set title.
        title = ''

        for selected_resource in utilization_dic.keys():
            utilization_list = list(utilization_dic[selected_resource].values())
            avg_utilization = round((sum(utilization_list)/len(utilization_list)), 1)
            title_line = str(selected_resource) + ' utilization : ' + str(avg_utilization) + '%'

            if title:
                title = str(title) + ';    ' + str(title_line)
            else:
                title = title_line

        axes.set_title(title)

        # set_xlabel/set_ylabel.
        if self.enable_utilization_detail:
            axes.set_xlabel('Sample Time')
        else:
            axes.set_xlabel('Sample Date')

        axes.set_ylabel('Utilization (%)')

        # axes.plot (sample_date_list / utilization_list)
        selected_resource_list = ['slot', 'mem', 'cpu']

        for selected_resource in selected_resource_list:
            if selected_resource not in utilization_dic:
                continue

            if self.enable_utilization_detail:
                common.bprint('Drawing ' + str(selected_resource) + ' curve, please wait a moment ...', date_format='%Y-%m-%d %H:%M:%S')

                my_show_message = ShowMessage('Info', 'Drawing ' + str(selected_resource) + ' curve, please wait a moment ...')
                my_show_message.start()

            sample_date_list = []
            utilization_list = []

            for (sample_date, utilization) in utilization_dic[selected_resource].items():
                if int(utilization) >= 100:
                    utilization = 100.0

                if not sample_date_list:
                    sample_date_list.append(sample_date)
                    utilization_list.append(utilization)
                else:
                    if self.enable_utilization_detail:
                        for j in range(len(sample_date_list)):
                            sample_date_1 = re.sub(r'_', '', sample_date)
                            sample_date_2 = re.sub(r'_', '', sample_date_list[j])

                            if int(sample_date_1) > int(sample_date_2):
                                if j == len(sample_date_list)-1:
                                    sample_date_list.append(sample_date)
                                    utilization_list.append(utilization)
                                    break
                            else:
                                sample_date_list.insert(j, sample_date)
                                utilization_list.insert(j, utilization)
                                break
                    else:
                        for j in range(len(sample_date_list)):
                            if int(sample_date) > int(sample_date_list[j]):
                                if j == len(sample_date_list)-1:
                                    sample_date_list.append(sample_date)
                                    utilization_list.append(utilization)
                                    break
                            else:
                                sample_date_list.insert(j, sample_date)
                                utilization_list.insert(j, utilization)
                                break

            for (k, sample_date) in enumerate(sample_date_list):
                if self.enable_utilization_detail:
                    sample_date = datetime.datetime.strptime(sample_date, '%Y%m%d_%H%M%S')
                    expected_linewidth = 0.1
                    expected_markersize = 0.1
                else:
                    sample_date = datetime.datetime.strptime(sample_date, '%Y%m%d')
                    expected_linewidth = 1
                    expected_markersize = 1

                sample_date_list[k] = sample_date

            if selected_resource == 'slot':
                color = 'bo-'
                fill_color = 'lightblue'
                fill_alpha = 0.3
            elif selected_resource == 'cpu':
                color = 'ro-'
                fill_color = 'red'
                fill_alpha = 0.5
            elif selected_resource == 'mem':
                color = 'go-'
                fill_color = 'green'
                fill_alpha = 0.3

            axes.plot(sample_date_list, utilization_list, color, label=selected_resource.upper(), linewidth=expected_linewidth, markersize=expected_markersize)
            axes.fill_between(sample_date_list, utilization_list, color=fill_color, alpha=fill_alpha)

            if self.enable_utilization_detail:
                time.sleep(0.01)
                my_show_message.terminate()

        axes.legend(loc='upper right')
        axes.tick_params(axis='x', rotation=15)
        axes.grid()
        self.utilization_tab_utilization_canvas.draw()
# For utilization TAB (end) #

# For license TAB (start) #
    def gen_license_tab(self):
        """
        Generate the license tab on lsfMonitor GUI, show host license usage information.
        """
        # self.license_tab
        self.license_tab_frame0 = QFrame(self.license_tab)
        self.license_tab_frame0.setFrameShadow(QFrame.Raised)
        self.license_tab_frame0.setFrameShape(QFrame.Box)

        self.license_tab_feature_label = QLabel('Feature Information', self.license_tab)
        self.license_tab_feature_label.setStyleSheet("font-weight: bold;")
        self.license_tab_feature_label.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)

        self.license_tab_expires_label = QLabel('Expires Information', self.license_tab)
        self.license_tab_expires_label.setStyleSheet("font-weight: bold;")
        self.license_tab_expires_label.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)

        self.license_tab_feature_table = QTableWidget(self.license_tab)
        self.license_tab_feature_table.itemClicked.connect(self.license_tab_check_click)
        self.license_tab_expires_table = QTableWidget(self.license_tab)

        # self.license_tab - Grid
        license_tab_grid = QGridLayout()

        license_tab_grid.addWidget(self.license_tab_frame0, 0, 0, 1, 2)
        license_tab_grid.addWidget(self.license_tab_feature_label, 1, 0)
        license_tab_grid.addWidget(self.license_tab_expires_label, 1, 1)
        license_tab_grid.addWidget(self.license_tab_feature_table, 2, 0)
        license_tab_grid.addWidget(self.license_tab_expires_table, 2, 1)

        license_tab_grid.setRowStretch(0, 2)
        license_tab_grid.setRowStretch(1, 1)
        license_tab_grid.setRowStretch(2, 20)

        self.license_tab.setLayout(license_tab_grid)

        # Generate sub-frame
        self.gen_license_tab_frame0()
        self.gen_license_tab_feature_table(self.license_dic)
        self.gen_license_tab_expires_table(self.license_dic)

        if self.specified_feature:
            self.license_tab_feature_line.setText(str(self.specified_feature))
            self.license_tab_user_line.setText(str(self.specified_user))
            self.update_license_info()

    def gen_license_tab_frame0(self):
        # self.license_tab_frame0
        # "Show" item.
        license_tab_show_label = QLabel('Show', self.license_tab_frame0)
        license_tab_show_label.setStyleSheet("font-weight: bold;")
        license_tab_show_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.license_tab_show_combo = common_pyqt5.QComboCheckBox(self.license_tab_frame0)
        self.set_license_tab_show_combo()

        # "Server" item.
        license_tab_server_label = QLabel('Server', self.license_tab_frame0)
        license_tab_server_label.setStyleSheet("font-weight: bold;")
        license_tab_server_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.license_tab_server_combo = common_pyqt5.QComboCheckBox(self.license_tab_frame0)
        self.set_license_tab_server_combo()
        self.license_tab_server_combo.currentTextChanged.connect(self.update_license_tab_vendor_combo)

        # "Vendor" item.
        license_tab_vendor_label = QLabel('Vendor', self.license_tab_frame0)
        license_tab_vendor_label.setStyleSheet("font-weight: bold;")
        license_tab_vendor_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.license_tab_vendor_combo = common_pyqt5.QComboCheckBox(self.license_tab_frame0)
        self.set_license_tab_vendor_combo()

        # "Feature" item.
        license_tab_feature_label = QLabel('Feature', self.license_tab_frame0)
        license_tab_feature_label.setStyleSheet("font-weight: bold;")
        license_tab_feature_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.license_tab_feature_line = QLineEdit()
        self.license_tab_feature_line.returnPressed.connect(self.update_license_info)

        feature_list = self.get_license_feature_list()
        license_tab_feature_line_completer = common_pyqt5.get_completer(feature_list)
        self.license_tab_feature_line.setCompleter(license_tab_feature_line_completer)

        # "User" item.
        license_tab_user_label = QLabel('User', self.license_tab_frame0)
        license_tab_user_label.setStyleSheet("font-weight: bold;")
        license_tab_user_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.license_tab_user_line = QLineEdit()
        self.license_tab_user_line.returnPressed.connect(self.update_license_info)

        license_tab_user_line_completer = common_pyqt5.get_completer(self.users_dic['USER/GROUP'])
        self.license_tab_user_line.setCompleter(license_tab_user_line_completer)

        # "Filter" button.
        license_tab_check_button = QPushButton('Check', self.license_tab_frame0)
        license_tab_check_button.setStyleSheet('''QPushButton:hover{background:rgb(0, 85, 255);}''')
        license_tab_check_button.clicked.connect(self.update_license_info)

        # self.license_tab_frame0 - Grid
        license_tab_frame0_grid = QGridLayout()

        license_tab_frame0_grid.addWidget(license_tab_show_label, 0, 0)
        license_tab_frame0_grid.addWidget(self.license_tab_show_combo, 0, 1)
        license_tab_frame0_grid.addWidget(license_tab_server_label, 0, 2)
        license_tab_frame0_grid.addWidget(self.license_tab_server_combo, 0, 3)
        license_tab_frame0_grid.addWidget(license_tab_vendor_label, 0, 4)
        license_tab_frame0_grid.addWidget(self.license_tab_vendor_combo, 0, 5)
        license_tab_frame0_grid.addWidget(license_tab_feature_label, 0, 6)
        license_tab_frame0_grid.addWidget(self.license_tab_feature_line, 0, 7)
        license_tab_frame0_grid.addWidget(license_tab_user_label, 0, 8)
        license_tab_frame0_grid.addWidget(self.license_tab_user_line, 0, 9)
        license_tab_frame0_grid.addWidget(license_tab_check_button, 0, 10)

        license_tab_frame0_grid.setColumnStretch(1, 1)
        license_tab_frame0_grid.setColumnStretch(2, 1)
        license_tab_frame0_grid.setColumnStretch(3, 1)
        license_tab_frame0_grid.setColumnStretch(4, 1)
        license_tab_frame0_grid.setColumnStretch(5, 1)
        license_tab_frame0_grid.setColumnStretch(6, 1)
        license_tab_frame0_grid.setColumnStretch(7, 1)
        license_tab_frame0_grid.setColumnStretch(8, 1)
        license_tab_frame0_grid.setColumnStretch(9, 1)
        license_tab_frame0_grid.setColumnStretch(10, 1)

        self.license_tab_frame0.setLayout(license_tab_frame0_grid)

    def get_license_feature_list(self):
        """
        Get all features from self.license_dic.
        """
        feature_list = []

        for license_server in self.license_dic.keys():
            for vendor_daemon in self.license_dic[license_server]['vendor_daemon'].keys():
                for feature in self.license_dic[license_server]['vendor_daemon'][vendor_daemon]['feature'].keys():
                    feature_list.append(feature)

        feature_list = list(set(feature_list))

        return feature_list

    def set_license_tab_show_combo(self):
        self.license_tab_show_combo.clear()

        license_status_list = ['ALL', 'IN_USE', 'NOT_USED']

        for license_status in license_status_list:
            self.license_tab_show_combo.addCheckBoxItem(license_status)

        # Set "ALL" as checked status.
        for (i, qBox) in enumerate(self.license_tab_show_combo.checkBoxList):
            if (qBox.text() == 'ALL') and (qBox.isChecked() is False):
                self.license_tab_show_combo.checkBoxList[i].setChecked(True)
                break

    def set_license_tab_server_combo(self):
        self.license_tab_server_combo.clear()

        license_server_list = list(self.license_dic.keys())
        license_server_list.insert(0, 'ALL')

        for license_server in license_server_list:
            self.license_tab_server_combo.addCheckBoxItem(license_server)

        # Set "ALL" as checked status.
        for (i, qBox) in enumerate(self.license_tab_server_combo.checkBoxList):
            if (qBox.text() == 'ALL') and (qBox.isChecked() is False):
                self.license_tab_server_combo.checkBoxList[i].setChecked(True)
                break

    def set_license_tab_vendor_combo(self):
        self.license_tab_vendor_combo.clear()

        # Get vendor_daemon list.
        vendor_daemon_list = ['ALL', ]
        selected_license_server_list = self.license_tab_server_combo.currentText().strip().split()

        for license_server in self.license_dic.keys():
            for selected_license_server in selected_license_server_list:
                if (selected_license_server == license_server) or (selected_license_server == 'ALL'):
                    for vendor_daemon in self.license_dic[license_server]['vendor_daemon'].keys():
                        if vendor_daemon not in vendor_daemon_list:
                            vendor_daemon_list.append(vendor_daemon)

        # Fill self.license_tab_vendor_combo.
        for vendor_daemon in vendor_daemon_list:
            self.license_tab_vendor_combo.addCheckBoxItem(vendor_daemon)

        # Set "ALL" as checked status.
        for (i, qBox) in enumerate(self.license_tab_vendor_combo.checkBoxList):
            if (qBox.text() == 'ALL') and (qBox.isChecked() is False):
                self.license_tab_vendor_combo.checkBoxList[i].setChecked(True)
                break

    def update_license_tab_vendor_combo(self):
        self.set_license_tab_vendor_combo()

    def update_license_info(self):
        # Get license information.
        self.get_license_dic()

        if not self.license_dic:
            warning_message = '*Warning*: Not find any license information.'
            self.gui_warning(warning_message)
            return

        selected_license_server_list = self.license_tab_server_combo.currentText().strip().split()
        selected_vendor_daemon_list = self.license_tab_vendor_combo.currentText().strip().split()
        specified_license_feature_list = self.license_tab_feature_line.text().strip().split()
        specified_license_user_list = self.license_tab_user_line.text().strip().split()
        show_mode_list = self.license_tab_show_combo.currentText().strip().split()

        if show_mode_list:
            if ('ALL' in show_mode_list) or (('IN_USE' in show_mode_list) and ('NOT_USED' in show_mode_list)):
                show_mode = 'ALL'
            else:
                show_mode = show_mode_list[0]
        else:
            show_mode = 'ALL'

        filter_license_dic_item = common_license.FilterLicenseDic()
        filtered_license_dic = filter_license_dic_item.run(license_dic=self.license_dic, server_list=selected_license_server_list, vendor_list=selected_vendor_daemon_list, feature_list=specified_license_feature_list, user_list=specified_license_user_list, show_mode=show_mode)

        # Update self.license_tab_feature_table and self.license_tab_expires_table.
        self.gen_license_tab_feature_table(filtered_license_dic)
        self.gen_license_tab_expires_table(filtered_license_dic)

    def gen_license_tab_feature_table(self, license_dic):
        self.license_tab_feature_table.setShowGrid(True)
        self.license_tab_feature_table.setSortingEnabled(True)
        self.license_tab_feature_table.setColumnCount(0)
        self.license_tab_feature_table.setColumnCount(5)
        self.license_tab_feature_table_title_list = ['Server', 'Vendor', 'Feature', 'Issued', 'In_Use']
        self.license_tab_feature_table.setHorizontalHeaderLabels(self.license_tab_feature_table_title_list)

        self.license_tab_feature_table.setColumnWidth(0, 160)
        self.license_tab_feature_table.setColumnWidth(1, 80)
        self.license_tab_feature_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.license_tab_feature_table.setColumnWidth(3, 50)
        self.license_tab_feature_table.setColumnWidth(4, 50)

        # Get license feature information length.
        license_feature_info_length = 0

        for license_server in license_dic.keys():
            for vendor_daemon in license_dic[license_server]['vendor_daemon'].keys():
                for feature in license_dic[license_server]['vendor_daemon'][vendor_daemon]['feature'].keys():
                    license_feature_info_length += 1

        # Fill self.license_tab_feature_table items.
        self.license_tab_feature_table.setRowCount(0)
        self.license_tab_feature_table.setRowCount(license_feature_info_length)

        row = -1

        for license_server in license_dic.keys():
            for vendor_daemon in license_dic[license_server]['vendor_daemon'].keys():
                for feature in license_dic[license_server]['vendor_daemon'][vendor_daemon]['feature'].keys():
                    row += 1

                    # Fill "Server" item.
                    self.license_tab_feature_table.setItem(row, 0, QTableWidgetItem(license_server))

                    # Fill "Vendor" item.
                    self.license_tab_feature_table.setItem(row, 1, QTableWidgetItem(vendor_daemon))

                    # Fill "Feature" item.
                    item = QTableWidgetItem(feature)
                    item.setForeground(QBrush(Qt.blue))
                    self.license_tab_feature_table.setItem(row, 2, item)

                    # Fill "Issued" item.
                    issued = license_dic[license_server]['vendor_daemon'][vendor_daemon]['feature'][feature]['issued']
                    item = QTableWidgetItem()

                    if re.match(r'^\d+$', issued):
                        item.setData(Qt.DisplayRole, int(issued))
                    else:
                        item.setText(issued)

                    self.license_tab_feature_table.setItem(row, 3, item)

                    # Fill "In_Use" item.
                    in_use = license_dic[license_server]['vendor_daemon'][vendor_daemon]['feature'][feature]['in_use']
                    item = QTableWidgetItem()
                    item.setData(Qt.DisplayRole, int(in_use))

                    if in_use == '0':
                        item.setFont(QFont('song', 9))
                    else:
                        item.setFont(QFont('song', 9, QFont.Bold))

                    self.license_tab_feature_table.setItem(row, 4, item)

    def license_tab_check_click(self, item=None):
        """
        If click the Job id, jump to the JOB tab and show the job information.
        If click the "PEND" Status, show the job pend reasons on a QMessageBox.information().
        """
        if item is not None:
            if item.column() == 4:
                current_row = self.license_tab_feature_table.currentRow()
                in_use_num = int(self.license_tab_feature_table.item(current_row, 4).text().strip())

                if in_use_num > 0:
                    license_server = self.license_tab_feature_table.item(current_row, 0).text().strip()
                    vendor_daemon = self.license_tab_feature_table.item(current_row, 1).text().strip()
                    license_feature = self.license_tab_feature_table.item(current_row, 2).text().strip()

                    common.bprint('Getting license feature "' + str(license_feature) + '" usage on license server ' + str(license_server) + ' ...', date_format='%Y-%m-%d %H:%M:%S')

                    self.my_show_license_feature_usage = ShowLicenseFeatureUsage(server=license_server, vendor=vendor_daemon, feature=license_feature)
                    self.my_show_license_feature_usage.start()

    def gen_license_tab_expires_table(self, license_dic):
        self.license_tab_expires_table.setShowGrid(True)
        self.license_tab_expires_table.setSortingEnabled(True)
        self.license_tab_expires_table.setColumnCount(0)
        self.license_tab_expires_table.setColumnCount(4)
        self.license_tab_expires_table_title_list = ['License Server', 'Feature', 'Num', 'Expires']
        self.license_tab_expires_table.setHorizontalHeaderLabels(self.license_tab_expires_table_title_list)

        self.license_tab_expires_table.setColumnWidth(0, 160)
        self.license_tab_expires_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.license_tab_expires_table.setColumnWidth(2, 50)
        self.license_tab_expires_table.setColumnWidth(3, 100)

        # Get license feature information length.
        license_expires_info_length = 0

        for license_server in license_dic.keys():
            for vendor_daemon in license_dic[license_server]['vendor_daemon'].keys():
                for feature in license_dic[license_server]['vendor_daemon'][vendor_daemon]['expires'].keys():
                    license_expires_info_length += len(license_dic[license_server]['vendor_daemon'][vendor_daemon]['expires'][feature])

        # Fill self.license_tab_expires_table items.
        self.license_tab_expires_table.setRowCount(0)
        self.license_tab_expires_table.setRowCount(license_expires_info_length)

        row = -1

        for license_server in license_dic.keys():
            for vendor_daemon in license_dic[license_server]['vendor_daemon'].keys():
                for feature in license_dic[license_server]['vendor_daemon'][vendor_daemon]['expires'].keys():
                    for expires_dic in license_dic[license_server]['vendor_daemon'][vendor_daemon]['expires'][feature]:
                        row += 1

                        # Fill "Server" item.
                        self.license_tab_expires_table.setItem(row, 0, QTableWidgetItem(license_server))

                        # Fill "Feature" item.
                        item = QTableWidgetItem(feature)
                        item.setForeground(QBrush(Qt.blue))
                        self.license_tab_expires_table.setItem(row, 1, item)

                        # Fill "Num" item.
                        item = QTableWidgetItem()
                        item.setData(Qt.DisplayRole, int(expires_dic['license']))
                        self.license_tab_expires_table.setItem(row, 2, item)

                        # Fill "Expires" item.
                        expires = expires_dic['expires']
                        item = QTableWidgetItem(expires)
                        expires_mark = common_license.check_expire_date(expires)

                        if expires_mark == 0:
                            pass
                        elif expires_mark == -1:
                            item.setForeground(QBrush(Qt.gray))
                        else:
                            item.setForeground(QBrush(Qt.red))
                        self.license_tab_expires_table.setItem(row, 3, item)
# For license TAB (end) #

# Export table (start) #
    def export_jobs_table(self):
        self.export_table('jobs', self.jobs_tab_table, self.jobs_tab_table_title_list)

    def export_hosts_table(self):
        self.export_table('hosts', self.hosts_tab_table, self.hosts_tab_table_title_list)

    def export_queues_table(self):
        self.export_table('queues', self.queues_tab_table, self.queues_tab_table_title_list)

    def export_utilization_table(self):
        self.export_table('utilization', self.utilization_tab_table, self.utilization_tab_table_title_list)

    def export_license_feature_table(self):
        self.export_table('license_feature', self.license_tab_feature_table, self.license_tab_feature_table_title_list)

    def export_license_expires_table(self):
        self.export_table('license_expires', self.license_tab_expires_table, self.license_tab_expires_table_title_list)

    def export_table(self, table_type, table_item, title_list):
        """
        Export specified table info into an csv file.
        """
        current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        current_time_string = re.sub('-', '', current_time)
        current_time_string = re.sub(':', '', current_time_string)
        current_time_string = re.sub(' ', '_', current_time_string)
        default_output_file = './lsfMonitor_' + str(table_type) + '_' + str(current_time_string) + '.csv'
        (output_file, output_file_type) = QFileDialog.getSaveFileName(self, 'Export ' + str(table_type) + ' table', default_output_file, 'CSV Files (*.csv)')

        if output_file:
            # Get table content.
            content_dic = {}
            row_num = table_item.rowCount()
            column_num = table_item.columnCount()

            for column in range(column_num):
                column_list = []

                for row in range(row_num):
                    if table_item.item(row, column):
                        column_list.append(table_item.item(row, column).text())
                    else:
                        column_list.append('')

                content_dic.setdefault(title_list[column], column_list)

            # Write csv
            common.bprint('Writing ' + str(table_type) + ' table into "' + str(output_file) + '" ...', date_format='%Y-%m-%d %H:%M:%S')

            common.write_csv(csv_file=output_file, content_dic=content_dic)
# Export table (end) #

    def closeEvent(self, QCloseEvent):
        """
        When window close, post-process.
        """
        common.bprint('Bye', date_format='%Y-%m-%d %H:%M:%S')


class CheckIssueReason(QThread):
    """
    Start tool check_issue_reason to debug issue job.
    """
    def __init__(self, job='', issue='PEND'):
        super(CheckIssueReason, self).__init__()
        self.job = job
        self.issue = issue

    def run(self):
        command = str(os.environ['LSFMONITOR_INSTALL_PATH']) + '/monitor/tools/check_issue_reason -i ' + str(self.issue)

        if self.job:
            command = str(command) + ' -j ' + str(self.job)

        os.system(command)


class ProcessTracer(QThread):
    """
    Start tool process_tracer to trace job process.
    """
    def __init__(self, job):
        super(ProcessTracer, self).__init__()
        self.job = job

    def run(self):
        command = str(os.environ['LSFMONITOR_INSTALL_PATH']) + '/monitor/tools/process_tracer -j ' + str(self.job)
        os.system(command)


class ShowLicenseFeatureUsage(QThread):
    """
    Start tool show_license_feature_usage to show license feature usage information.
    """
    def __init__(self, server, vendor, feature):
        super(ShowLicenseFeatureUsage, self).__init__()
        self.server = server
        self.vendor = vendor
        self.feature = feature

    def run(self):
        command = str(os.environ['LSFMONITOR_INSTALL_PATH']) + '/monitor/tools/show_license_feature_usage -s ' + str(self.server) + ' -v ' + str(self.vendor) + ' -f ' + str(self.feature)
        os.system(command)


class ShowMessage(QThread):
    """
    Show message with tool message.
    """
    def __init__(self, title, message):
        super(ShowMessage, self).__init__()
        self.title = title
        self.message = message

    def run(self):
        command = 'python3 ' + str(os.environ['LSFMONITOR_INSTALL_PATH']) + '/monitor/tools/message.py --title "' + str(self.title) + '" --message "' + str(self.message) + '"'
        os.system(command)


#################
# Main Function #
#################
def main():
    (specified_job, specified_user, specified_feature, specified_tab, disable_license) = read_args()
    app = QApplication(sys.argv)
    mw = MainWindow(specified_job, specified_user, specified_feature, specified_tab, disable_license)
    mw.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
