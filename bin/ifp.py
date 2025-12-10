# -*- coding: utf-8 -*-
import copy
import inspect
import json
import os
import pwd
import re
import signal
import subprocess
import sys
import stat
import threading
import time
import traceback
from pathlib import Path

import jinja2
import shutil
import socket
import argparse
import datetime
import getpass
import importlib
from typing import Dict, Tuple, List

from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtWebEngineWidgets import QWebEngineView
from matplotlib import colors
import functools

# Import PyQt5 libraries.
import yaml
from PyQt5.QtCore import pyqtSignal, QTimer, Qt, QProcess, QRect, QPoint, QUrl, QThread, pyqtSlot, QObject, QEvent
from PyQt5.QtWidgets import QMainWindow, QApplication, QAction, QMessageBox, QTabWidget, QWidget, QFrame, QGridLayout, QTextEdit, QTableWidget, QHeaderView, QTableWidgetItem, QFileDialog, QTreeWidget, QTreeWidgetItem, QDialog, QCheckBox, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, \
    QMenu, QTableView, QProgressDialog, QSplitter, QTabBar, QStylePainter, QStyleOptionTab, QStyle, QStatusBar, QButtonGroup, QRadioButton, QActionGroup, QToolBar
from PyQt5.QtGui import QIcon, QBrush, QColor, QFont, QStandardItem, QStandardItemModel, QPixmap

# Import local python files.
import parse_config
from user_config import UserConfig, WindowForDependency, WindowForToolGlobalEnvEditor, WindowForAPI, WindowForTaskInformation, TaskJobCheckWorker
from job_manager import JobManager

# Import common python files.
sys.path.append(str(os.environ['IFP_INSTALL_PATH']) + '/common')
import common
import common_db
import common_pyqt5

# Import install config settings.
sys.path.append(str(os.environ['IFP_INSTALL_PATH']) + '/config')
import config as install_config

QT_DEVICE_PIXEL_RATIO = 1
os.environ['PYTHONUNBUFFERED'] = '1'
CWD = os.getcwd()
USER = getpass.getuser()
IFP_VERSION = 'V1.4.3 (2025.12.10)'

# Solve some unexpected warning message.
if 'XDG_RUNTIME_DIR' not in os.environ:
    os.environ['XDG_RUNTIME_DIR'] = '/tmp/runtime-' + str(USER)

    if not os.path.exists(os.environ['XDG_RUNTIME_DIR']):
        os.makedirs(os.environ['XDG_RUNTIME_DIR'])

    os.chmod(os.environ['XDG_RUNTIME_DIR'], stat.S_IRWXU + stat.S_IRWXG + stat.S_IRWXO)


# Process input arguments (start) #
def readArgs():
    """
    Read in arguments.
    """
    parser = argparse.ArgumentParser()

    # Basic arguments.
    parser.add_argument('-config_file', '--config_file',
                        default=str(CWD) + '/ifp.cfg.yaml',
                        help='Specify the configure file, default is "<CWD>/ifp.cfg.yaml".')
    parser.add_argument('-d', '--debug',
                        default=False,
                        action='store_true',
                        help='Enable debug mode, will print more useful messages.')
    parser.add_argument('-r', '--read',
                        default=False,
                        action='store_true',
                        help='Read-Only Mode.')
    parser.add_argument('-a', '--action',
                        default='',
                        choices=['build', 'run', 'check', 'summarize'],
                        help='Execute action after launch IFP')
    parser.add_argument('-t', '--title',
                        default='IC Flow Platform %s' % IFP_VERSION,
                        help='Specify GUI title')

    args = parser.parse_args()

    # get config_file.
    config_file_path = os.path.abspath(args.config_file)
    status_file_name, cache_dir_name = common.gen_cache_file_name(config_file=os.path.basename(args.config_file))

    if not args.read:
        if os.path.exists(config_file_path):
            if not os.access(os.getcwd(), os.W_OK) or not os.access(config_file_path, os.W_OK):
                print('*Error*: You do not have write permission in this path or ifp.cfg.yaml')
                print('*Error*: add \'-r\', and IFP will launch in Read-Only Mode.')
                sys.exit(1)

        # Normal Mode: Generating status & cache from current directory
        status_file_path = os.path.join(os.getcwd(), status_file_name)
        cache_dir_path = os.path.join(os.getcwd(), cache_dir_name)

        if not os.path.exists(config_file_path):
            gen_config_file(config_file_path)

        if not os.path.exists(status_file_path):
            gen_config_file(status_file_path)

        try:
            os.makedirs(os.path.join(os.path.dirname(args.config_file), cache_dir_path), exist_ok=True)
        except Exception as error:
            print('*Error*: Failed on creating .ifp.')
            print('*Error*: add \'-r\', and IFP will launch in Read-Only Mode.')
            print('         ' + str(error))
            sys.exit(1)

    if os.environ.get('IFP_DEMO_MODE', 'FALSE') == 'TRUE':
        print('>>> IFP Demo mode, you can set $IFP_DEMO_MODE=FALSE to exit')

    return config_file_path, args.read, args.debug, args.action, args.title


def gen_config_file(config_file):
    """
    Generate configure file.
    """

    try:
        with open(config_file, 'w') as CF:
            CF.write('')

    except Exception as error:
        print('*Error*: Failed on creating config file "' + str(config_file) + '".')
        print('*Error*: add \'-r\', and IFP will launch in Read-Only Mode.')
        print('         ' + str(error))
        sys.exit(1)


def gen_lock_file():
    """
    Generate lock file.
    """
    try:
        ifp_path = "%s/.ifp" % os.getcwd()
        os.makedirs(ifp_path, exist_ok=True)

        lock_file = "%s/ifp.lock" % ifp_path

        if os.path.exists(lock_file):
            lock_info = {}

            with open(lock_file, 'r') as f:
                for line in f:
                    key, value = line.split(': ')
                    lock_info[key] = value.strip()

                msg_str = """
  • User      : %s
  • Start time: %s
  • Host name : %s
  • PID       : %s""" % (lock_info.get('user'), lock_info.get('start_time'), lock_info.get('host_name'), lock_info.get('pid'))

                if not lock_info.get("jobid") == 'None':
                    msg_str += """
  • JobID     : %s""" % lock_info.get("jobid")

                message = """IFP is already running in this directory, locked by:
%s

Please make sure the above process has been properly terminated,
or manully delete the lock file at:
%s""" % (msg_str, lock_file)

                msgbox = QMessageBox()
                msgbox.setWindowTitle("IFP locked")
                msgbox.setText(f"<pre style='white-space: pre-wrap; word-wrap: break-word;'>{message}</pre>")

                msgbox.addButton(QPushButton("Ok"), QMessageBox.AcceptRole)

                msgbox.exec_()

                return False

        else:
            user = getpass.getuser()
            host = socket.gethostname()
            pid = os.getpid()
            time = datetime.datetime.now().replace(microsecond=0)
            job_id = os.environ.get('LSB_JOBID')

            with open("%s/ifp.lock" % ifp_path, 'w') as f:
                f.write("user: %s\nhost_name: %s \npid: %s\njobid: %s\nstart_time: %s" % (user, host, pid, job_id, time))

            return True

    except Exception as error:
        print('*Error*: Failed on creating lock file.')
        print('     ' + str(error))

        return False


# GUI (start) #
class MainWindow(QMainWindow):
    """
    >>> block = version = flow = task = None
    1. Total task settings ---------------------------------------------------------
    >>> config_obj = parse_config.Config('ifp.cfg.yaml')
    >>> config_dic = config_obj.config_dic
    >>> config_dic['PROJECT'] = 'demo'
    >>> config_dic['GROUP'] = 'syn'
    >>> config_dic['VAR']['IFP_INSTALL_PATH'] = ''
    >>> config_dic['BLOCK'][block][version][flow][task]['NAME'] = ''
    >>> config_dic['BLOCK'][block][version][flow][task]['ACTION']['RUN']['PATH'] = ''
    >>> config_dic['BLOCK'][block][version][flow][task]['RUN_AFTER']['TASK'] = 'setup&lpe'
    >>> config_dic['BLOCK'][block][version][flow][task]['DEPENDENCY']['FILE'] = ['${DEFAULT_PATH}/kitgen_setup.txt']
    >>> config_dic['BLOCK'][block][version][flow][task]['DEPENDENCY']['LICENSE'] = ['Liberate_Unified_Cell:5000']
    2. IFP Table info with tasks ---------------------------------------------------------
    >>> main_table_info_list = config_obj.main_table_info_list
    >>> main_table_info_list[0] = {'Block': '', 'Version': '', 'Flow': '', 'Task': '', 'Visible': True, 'Selected': False,
    >>>                            'PATH': '${DEFAULT_PATH}', 'Status': None, 'Check': None, 'Summary': None, 'Job': None,
    >>>                            'Runtime': None, 'Xterm': None, 'BuildStatus': None, 'RunStatus': None, 'CheckStatus': None,
    >>>                            'SummarizeStatus': None, 'ReleaseStatus': None, 'Task_obj': None}
    3. Task job manager for all progress data---------------------------------------------------------
    >>> job_manager = JobManager()
    >>> task_obj = main_table_info_list[0]['Task_obj'] = job_manager.all_tasks[block][version][flow][task]
    >>> action = task_obj.action
    >>> job_id = task_obj.job_id
    """

    def __init__(self, config_file, read, debug, auto_execute_action, title):
        super().__init__()
        self.record_count = 0

        with common_pyqt5.WaitingWindow('Loading IFP ...'):
            # IFP input parameters
            self.read_mode = read
            self.debug = debug
            self.auto_execute_action = auto_execute_action
            self.title = title if not self.read_mode else f'{title} (Read Only)'

            self.ifp_config_file = config_file
            status_file_name, cache_dir_name = common.gen_cache_file_name(config_file=os.path.basename(self.ifp_config_file))

            if not self.read_mode:
                dir_path = os.getcwd()
                self.ifp_status_file = os.path.join(dir_path, status_file_name)
                self.ifp_cache_dir = os.path.join(dir_path, cache_dir_name)
            else:
                dir_path = os.path.dirname(self.ifp_config_file)

                if os.path.exists(os.path.join(dir_path, status_file_name)):
                    self.ifp_status_file = os.path.join(os.path.join(dir_path, status_file_name))
                else:
                    self.ifp_status_file = os.path.join(os.getcwd(), f'{status_file_name}.read_mode_temp_file')
                    gen_config_file(self.ifp_status_file)

                self.ifp_cache_dir = os.path.join(dir_path, cache_dir_name)

            self.ifp_pnum = -1
            self.memos_logger = common.MemosLogger(log_path=os.path.join(self.ifp_cache_dir, 'memos.log'))

            self.ignore_fail_icon = QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/ignore_fail.png')
            self.run_mode_unchange_icon = QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/unchanged.png')
            self.check_undefined_icon = QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/check_undefined.png')
            self.check_pass_icon = QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/check_pass.png')
            self.check_fail_icon = QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/check_fail.png')
            self.check_init_icon = QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/check_init.png')
            self.summary_undefined_icon = QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/summary_undefined.png')
            self.summary_pass_icon = QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/summary_pass.png')
            self.summary_fail_icon = QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/summary_fail.png')
            self.summary_init_icon = QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/summary_init.png')
            self.terminal_icon = QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/other/terminal.png')

            # Parsing IFP System settings from user home directory and create parameters
            self.setting_parameters_obj = SystemSetting()
            self.setting_parameters_dic = self.setting_parameters_obj.config_dic

            for key, value in self.setting_parameters_dic.items():
                setattr(self, key, value)

            # Initial IFP parameters
            self.config_obj = None
            self.config_dic = None
            self.main_table_info_list = None
            self.status_filt_flag = 'Total'
            self.ifp_env_setting = None
            self.first_time_for_ifp = False
            self.disable_gui_flag = False
            top_tab_index = 0

            if os.path.getsize(self.ifp_config_file) == 0:
                self.first_time_for_ifp = True
            else:
                top_tab_index = 1

            # Show or hide column flags
            self.view_status_dic = {}
            self.view_detail_column_dic = {}
            self.header_column_mapping = {}
            self.block_row_mapping = {}

            # LSF Monitor list
            self.monitor_list = []

            self.api_menu_list = []
            self.api_toolbar_list = []

            # Initial ifp.py/job_manager.py/user_config.py parameters
            self.default_config_file = None
            self.api_yaml = None
            # Initial job_manager.py dict
            self.job_manager = JobManager(self, debug=self.debug)
            self.job_manager.disable_gui_signal.connect(self.disable_gui)
            self.job_manager.close_signal.connect(self.final_close)
            # Initial ifp.py dict
            self.update_dict_by_load_config_file(self.ifp_config_file)
            execute_action_for_pre_ifp(self)

            # Initial user_config.py dict and GUI
            self.task_window = None
            self.task_window = UserConfig(self, self.config_obj, self.ifp_config_file, self.default_config_file, self.api_yaml)
            self.task_window.load()
            self.task_window.save_flag.connect(lambda: self.save(save_mode='keep'))

            # IFP sub windows
            self.config_tab_index = {}
            self.guide_window = GuideWindow()
            self.setting_window = None
            self.dependency_window = WindowForDependency(mode='widget')
            self.var_window = None
            self.api_window = None
            self.config_view_window = None
            self.flow_multiple_select_window = None
            self.default_config_window = None
            self.task_multiple_select_window = None
            self.status_icon_widget = None

            # User Setting
            self.setting_widget = None
            self.task_widget = None
            self.dependency_widget = self.dependency_window.init_ui()
            self.var_widget = None
            self.api_widget = None

            # Main
            self.toolbar_list = []
            self.control_menu = None
            self.file_menu = None

            # Generate the GUI.
            self.main_table_title_list = ['Block', 'Version', 'Flow', 'Task', 'Status', 'Check', 'Summary', 'Job', 'Runtime', 'Xterm', 'Build Status', 'Run Status', 'Check Status', 'Summarize Status', 'Release Status']
            self.status_title_list = ['Build Status', 'Run Status', 'Check Status', 'Summarize Status', 'Release Status']
            self.operation_title_list = ['Status', 'Check', 'Summary', 'Job', 'Runtime', 'Xterm']
            # Initial ifp.py GUI
            self.pnum = 100

            self.gen_gui()
            self.load_status_file(self.ifp_status_file, api_reload=False)

            # System log
            self.ifp_start_time = datetime.datetime.now()
            self.write_system_log('start ifp')

            # Define QTimer
            self.timer = QTimer(self)
            self.timer.start(1000)
            self.timer.timeout.connect(self.update_runtime)

            # Init close dialog
            self.close_dialog = QProgressDialog()
            self.init_close_dialog()

            self.resize_filter = ResizeEventFilter(self)
            self.installEventFilter(self.resize_filter)

            if self.ifp_env_setting['System settings']['Appearance']['Fullscreen mode']['value']:
                self.showMaximized()
            else:
                self.show()

            if self.first_time_for_ifp or self.config_dic['PROJECT'] == 'demo':
                self.guide_window.show()

            if top_tab_index == 0:
                self.top_tab.setCurrentIndex(0)
            elif top_tab_index == 1:
                self.top_tab.setCurrentIndex(1)

            # Init temporary parameters
            self.current_selected_row = None
            self.current_selected_column = None
            self.current_selected_task_dic = None
            self.current_selected_task_obj = None

            self.progress_dialog = None

            if not self.read_mode:
                self.export_complete_ifp_cfg_yaml()

            self.execute_action_after_launch_ifp()
            self.flow_chart_window = FlowChartWindow(config_obj=self.config_obj, width=925, height=750)
            self.flow_chart_window.block_version_task.connect(self.open_task_information)

            self.full_flowchart_window = FlowChartWindow(config_obj=self.config_obj,
                                                         width=int(self.width() * 0.78) if not self.isMaximized() else int(common_pyqt5.get_monitors()[0].width * 0.76),
                                                         height=int(self.height() * 0.52) if not self.isMaximized() else int(common_pyqt5.get_monitors()[0].height * 0.52))
            self.full_flowchart_window.block_version_task.connect(self.open_task_information)
            self.gen_full_flowchart()

            self.cache_view_path = os.path.join(os.getcwd(), f'{os.path.basename(self.ifp_cache_dir)}/VIEW/{{TAB}}/view_status.json')
            self.tab_name = 'MAIN'

            self.load_cache()
            self.sidebar_tree.update()

            if self.read_mode:
                self.set_read_mode()

            self.task_information_show = False
            self.set_ignore_fail_for_all_tasks()

    def set_read_mode(self):
        # Disable User Config
        self.disable_gui_flag = True
        self.disable_gui(True)

        # Disable Main Window
        # Toolbar
        for toolbar in self.toolbar_list:
            toolbar.setEnabled(False)

        # Window Menu
        for control_action in self.control_menu.actions():
            control_action.setEnabled(False)

        for file_action in self.file_menu.actions():
            file_action.setEnabled(False)

    def update_pnum(self, pnum: int):
        self.pnum = pnum

    def load_cache(self):
        self.load_view_status_cache()

    def load_view_status_cache(self):
        # load main window cache
        main_cache_path = self.cache_view_path.format_map({'TAB': self.tab_name})

        if not os.path.exists(main_cache_path):
            return

        try:
            with open(main_cache_path, 'r') as mf:
                update_dic = json.load(mf)

            self.view_status_dic['block'].update({key: update_dic['block'][key] for key in self.view_status_dic['block'] if key in update_dic['block']})
            self.view_status_dic['task'].update({key: update_dic['task'][key] for key in self.view_status_dic['task'] if key in update_dic['task']})
            self.view_status_dic['column'].update({key: update_dic['column'][key] for key in self.view_status_dic['column'] if key in update_dic['column']})
        except Exception:
            return

        for column in self.view_status_dic['column']:
            if not self.view_status_dic['column'][column]:
                self.update_main_table_row_visible('column', column, self.view_status_dic['column'][column])

        # self.update_main_table_status()
        # self.apply_main_table_status(status=self.view_status_dic)

    def gen_full_flowchart(self):
        layout = QVBoxLayout()
        self.flow_chart_widget.setLayout(layout)
        layout.addWidget(self.full_flowchart_window)
        self.full_flowchart_window.gen_full_flow_graph(dependency_dic=self.task_window.dependency_priority)

    # GUI (start)
    def gen_gui(self):
        # Gen meanbar and toolbar.
        self.gen_menubar()
        self.gen_toolbar()
        self.gen_status_bar()

        # Gen tab widgets.
        self.top_tab = QTabWidget(self)
        self.env_tab = QWidget()

        self.config_tab = TabWidget()
        self.top_tab.addTab(self.config_tab, 'CONFIG')

        self.main_tab = QWidget()
        self.top_tab.addTab(self.main_tab, 'MAIN')

        self.flow_chart_widget = QWidget()

        self.gen_main_tab()
        self.gen_config_tab()

        # Gen message frame
        self.message_frame = QFrame(self.main_tab)
        self.message_frame.setFrameShadow(QFrame.Raised)
        self.message_frame.setFrameShape(QFrame.Box)
        self.gen_message_frame()

        # Gen main splitter
        self.main_splitter = QSplitter()
        self.main_splitter.setOrientation(0)
        self.main_splitter.addWidget(self.top_tab)
        self.main_splitter.addWidget(self.message_frame)
        self.main_splitter.setStretchFactor(0, 2)
        self.main_splitter.setStretchFactor(1, 1)

        self.setCentralWidget(self.main_splitter)

        # Set GUI size, title and icon.
        self.gui_width = 1200
        self.gui_height = 800
        common_pyqt5.auto_resize(self, self.gui_width, self.gui_height)
        self.setWindowTitle(self.title)
        self.setWindowIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/logo/ifp.png'))
        common_pyqt5.center_window(self)
        self.resize_table_column()

    def gen_menubar(self):
        menubar = self.menuBar()

        # File
        self.save_status_file_action = QAction('Save Status File', self)
        self.save_status_file_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/red/save_file.png'))
        self.save_status_file_action.triggered.connect(self.save_status_file)

        self.load_status_file_action = QAction('Load Status File', self)
        self.load_status_file_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/add_file.png'))
        self.load_status_file_action.triggered.connect(self.load_status_file)

        save_config_file_action = QAction('Save Config File', self)
        save_config_file_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/red/save_file.png'))
        save_config_file_action.triggered.connect(lambda: self.save(save_mode='save_as_other_file'))

        load_config_file_action = QAction('Load Config File', self)
        load_config_file_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/add_file.png'))
        load_config_file_action.triggered.connect(self.load)

        save_default_yaml_action = QAction('Save Default Yaml', self)
        save_default_yaml_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/red/save_file.png'))
        save_default_yaml_action.triggered.connect(self.save_default_yaml)

        save_api_yaml_action = QAction('Save API Yaml', self)
        save_api_yaml_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/red/save_file.png'))
        save_api_yaml_action.triggered.connect(self.save_api_yaml)

        self.clear_status_action = QAction('Clear Task Status', self)
        self.clear_status_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/gray/clear.png'))
        self.clear_status_action.triggered.connect(self.clear_task_status)

        exit_action = QAction('&Exit', self)
        exit_action.setShortcut('Ctrl+E')
        exit_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/exit.png'))
        exit_action.triggered.connect(self.close)

        self.file_menu = menubar.addMenu('File')
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.save_status_file_action)
        self.file_menu.addAction(self.load_status_file_action)
        self.file_menu.addSeparator()
        self.file_menu.addAction(save_config_file_action)
        self.file_menu.addAction(load_config_file_action)
        self.file_menu.addSeparator()
        self.file_menu.addAction(save_default_yaml_action)
        self.file_menu.addAction(save_api_yaml_action)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.clear_status_action)
        self.file_menu.addAction(exit_action)

        # View
        config_view_action = QAction('Config View', self)
        config_view_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/settings.png'))
        config_view_action.triggered.connect(self.gen_config_view_gui)

        main_view_action = QAction('Main View', self)
        main_view_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/settings.png'))
        main_view_action.triggered.connect(self.gen_main_view_gui)

        self.view_status_dic.setdefault('column', {})

        for i, item in enumerate(self.main_table_title_list):
            self.header_column_mapping[item] = i

            if item not in self.status_title_list:
                self.view_status_dic['column'][item] = True

        self.view_detail_column_dic = {title: True for title in self.operation_title_list}

        detail_status_action = QAction('Detail Status Info', self)
        detail_status_action.setShortcut('Ctrl+H')
        detail_status_action.setCheckable(True)
        detail_status_action.setChecked(False)
        detail_status_action.triggered.connect(self.show_or_hide_detail_status)

        zoom_in_action = QAction('Zoom &In', self)
        zoom_in_action.setShortcut('Ctrl+I')
        zoom_in_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/zoom_in.png'))
        zoom_in_action.triggered.connect(self.zoom_in)

        zoom_out_action = QAction('Zoom &Out', self)
        zoom_out_action.setShortcut('Ctrl+O')
        zoom_out_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/zoom_out.png'))
        zoom_out_action.triggered.connect(self.zoom_out)

        view_menu = menubar.addMenu('View')
        view_menu.addAction(config_view_action)
        view_menu.addAction(main_view_action)
        view_menu.addSeparator()
        view_menu.addAction(zoom_in_action)
        view_menu.addAction(zoom_out_action)
        view_menu.addSeparator()
        view_menu.addAction(detail_status_action)

        # Control
        control_all_action = QAction('&All_Steps', self)
        control_all_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/other/all.png'))
        control_all_action.triggered.connect(lambda: self.execute_action(common.action.run, run_all_steps=True))

        control_build_action = QAction('&' + common.action.build, self)
        control_build_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/other/build.png'))
        control_build_action.triggered.connect(lambda: self.execute_action(common.action.build))

        control_run_action = QAction('&' + common.action.run, self)
        control_run_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/run.png'))
        control_run_action.triggered.connect(lambda: self.execute_action(common.action.run))

        control_kill_action = QAction('&' + common.action.kill, self)
        control_kill_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/kill.png'))
        control_kill_action.triggered.connect(lambda: self.execute_action(common.action.kill))

        control_check_action = QAction('&' + common.action.check, self)
        control_check_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/checklist.png'))
        control_check_action.triggered.connect(lambda: self.execute_action(common.action.check))

        control_summary_action = QAction('&' + common.action.summarize, self)
        control_summary_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/summary.png'))
        control_summary_action.triggered.connect(lambda: self.execute_action(common.action.summarize))

        control_release_action = QAction('&' + common.action.release, self)
        control_release_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/release.png'))
        control_release_action.triggered.connect(lambda: self.execute_action(common.action.release))

        self.control_menu = menubar.addMenu('Control')
        self.control_menu.addAction(control_all_action)
        self.control_menu.addAction(control_build_action)
        self.control_menu.addAction(control_run_action)
        self.control_menu.addAction(control_kill_action)
        self.control_menu.addAction(control_check_action)
        self.control_menu.addAction(control_summary_action)
        self.control_menu.addAction(control_release_action)

        # Tool
        lsf_monitor_action = QAction('LSF monitor', self)
        lsf_monitor_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/chart.png'))
        lsf_monitor_action.triggered.connect(self.show_lsf_monitor)

        tool_menu = menubar.addMenu('Tool')
        tool_menu.addAction(lsf_monitor_action)

        # Help
        about_action = QAction('&About', self)
        about_action.setShortcut('Ctrl+A')
        about_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/copyright.png'))
        about_action.triggered.connect(self.show_about)

        guide_action = QAction('&Guidance', self)
        guide_action.triggered.connect(lambda: GuideWindow().show())

        help_menu = menubar.addMenu('Help')
        help_menu.addAction(about_action)
        help_menu.addAction(guide_action)

        self.memos_logger.setup_menu_bar_memos(menubar)
        self.api_menu_list = common.add_api_menu_bar(self, self.user_api, menubar)

    def gen_status_bar(self):
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)

    def resizeEvent(self, a0):
        # This method is called when the window state changes

        if hasattr(self, 'full_flowchart_window'):
            self.full_flowchart_window.resize_graph(width=int(self.width() * 0.76), height=int(self.height() * 0.52))

        super().changeEvent(a0)

    def update_status_bar(self, message):
        self.statusBar.showMessage(message)

    def add_status_icon(self, icon_path, icon_text):
        if self.status_icon_widget is None:
            self.status_icon_widget = QWidget()
            layout = QHBoxLayout(self.status_icon_widget)
            layout.setContentsMargins(0, 0, 0, 0)

            label_icon = QLabel()
            pixmap = QPixmap(icon_path)
            pixmap = pixmap.scaled(16, 16, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            label_icon.setPixmap(pixmap)
            layout.addWidget(label_icon)
            label_text = QLabel(icon_text)
            layout.addWidget(label_text)
            self.statusBar.addPermanentWidget(self.status_icon_widget)

    def remove_status_icon(self):
        try:
            if self.status_icon_widget is not None:
                self.statusBar.removeWidget(self.status_icon_widget)
                self.status_icon_widget = None
        except Exception:
            pass

    def update_status_bar_tip(self):
        try:
            self.add_status_icon(icon_path=(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/other/warning.png'),
                                 icon_text='default.yaml/api.yaml updated. Review changes to reload config.')
        except Exception:
            pass

    def gen_toolbar(self):
        # Run all steps
        run_all_steps_action = QAction('Run All Steps', self)
        run_all_steps_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/other/all.png'))
        run_all_steps_action.triggered.connect(lambda: self.execute_action(common.action.run, run_all_steps=True))

        toolbar = self.addToolBar('Run All Steps')
        toolbar.addAction(run_all_steps_action)
        self.toolbar_list.append(toolbar)

        # Build
        build_action = QAction(common.action.build, self)
        build_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/other/build.png'))
        build_action.triggered.connect(lambda: self.execute_action(common.action.build))

        toolbar = self.addToolBar(common.action.build)
        toolbar.addAction(build_action)
        self.toolbar_list.append(toolbar)

        # Run
        run_action = QAction(common.action.run, self)
        run_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/run.png'))
        run_action.triggered.connect(lambda: self.execute_action(common.action.run))

        toolbar = self.addToolBar(common.action.run)
        toolbar.addAction(run_action)
        self.toolbar_list.append(toolbar)

        # Kill
        kill_action = QAction(common.action.kill, self)
        kill_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/kill.png'))
        kill_action.triggered.connect(lambda: self.execute_action(common.action.kill))

        toolbar = self.addToolBar(common.action.kill)
        toolbar.addAction(kill_action)
        self.toolbar_list.append(toolbar)

        # Check
        check_action = QAction(common.action.check, self)
        check_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/checklist.png'))
        check_action.triggered.connect(lambda: self.execute_action(common.action.check))

        toolbar = self.addToolBar(common.action.check)
        toolbar.addAction(check_action)
        self.toolbar_list.append(toolbar)

        # Summary
        summary_action = QAction(common.action.summarize, self)
        summary_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/summary.png'))
        summary_action.triggered.connect(lambda: self.execute_action(common.action.summarize))

        toolbar = self.addToolBar(common.action.summarize)
        toolbar.addAction(summary_action)
        self.toolbar_list.append(toolbar)

        # Release
        release_action = QAction(common.action.release, self)
        release_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/release.png'))
        release_action.triggered.connect(lambda: self.execute_action(common.action.release))

        toolbar = self.addToolBar('Release')
        toolbar.addAction(release_action)
        self.toolbar_list.append(toolbar)

        self.memos_logger.setup_tool_bar_memos(self.toolbar_list)

        # self.toolbar = self.addToolBar('API')
        self.api_toolbar_list = common.add_api_tool_bar(self, self.user_api)
        self.toolbar_list += self.api_toolbar_list

    def show_about(self):
        QMessageBox.about(self, 'IC flow Platform', """                                                       Version """ + str(IFP_VERSION) + """

Copyright © 2021 ByteDance. All Rights Reserved worldwide.""")

    def cache_view_window_status(self, save: bool, tab_name: str, view_status_dic: Dict[str, Dict[str, bool]]):
        if not save:
            return

        if self.read_mode:
            return

        cache_path = self.cache_view_path.format_map({'TAB': tab_name})

        if not os.path.exists(cache_path):
            os.makedirs(os.path.dirname(cache_path))

        with open(cache_path, 'w') as mf:
            mf.write(json.dumps(view_status_dic))

    # CloseDialog (start)
    def init_close_dialog(self):
        self.close_dialog.setCancelButton(None)
        self.close_dialog.setWindowFlags(Qt.CustomizeWindowHint | Qt.WindowTitleHint | Qt.WindowStaysOnTopHint)
        self.close_dialog.setWindowTitle('Please Wait')
        self.close_dialog.setLabelText('Killing Tasks. . .')
        self.close_dialog.setRange(0, 0)
        self.close_dialog.close()

    def closeEvent(self, event):
        """
        When user close GUI MainWindow, This function will execute
        """
        # Click exit button when close_dialog is displayed is an invalid action
        if self.close_dialog.isVisible():
            event.ignore()
            return

        if self.read_mode:
            event.accept()
            return

        running_tasks = []

        self.qapp.removeEventFilter(self.event_filter)
        warning_text = "Below jobs are working:\n"

        # read main_table_info_list and get running tasks
        for main_table_info in self.main_table_info_list:
            block = main_table_info['Block']
            version = main_table_info['Version']
            task = main_table_info['Task']
            status = main_table_info['Status']

            if status in common.CLOSE_REMIND_STATUS:
                running_tasks.append(main_table_info)
                items = "Block:" + block + "  Version:" + version + " Task:" + task + " Status:" + status

                if len(running_tasks) <= 3:
                    warning_text = warning_text + items + "\n"

        if len(running_tasks) > 3:
            warning_text = warning_text + "......\n"

        warning_text = warning_text + "\nSure to quit and close all of them?"

        if len(running_tasks) > 0:
            # Build QMessageBox
            reply = QMessageBox.question(self, "Warning", warning_text, QMessageBox.Yes | QMessageBox.No)

            if reply == QMessageBox.Yes:
                # Execute killing action to all tasks
                kill_tasks = self.job_manager.kill_all_jobs_before_close_window()

                if kill_tasks:
                    self.setEnabled(False)
                    self.close_dialog.show()

            event.ignore()
            return

        self.memos_logger.log('Exit IFP')
        self.job_manager.launch_timer.stop()
        self.job_manager.flush_timer.stop()

        ifp_close_time = datetime.datetime.now()
        run_time = (ifp_close_time - self.ifp_start_time).seconds
        hours = run_time // 3600
        minutes = (run_time % 3600) // 60
        seconds = run_time % 60
        self.write_system_log("close ifp, total runtime %02d:%02d:%02d" % (hours, minutes, seconds))

        self.task_window.thread.quit()
        self.save_status_file(self.ifp_status_file)
        self.cache_view_window_status(save=True, tab_name=self.tab_name, view_status_dic=self.view_status_dic)
        self.task_window.ifp_monitor.stop_event.set()
        self.timer.stop()

        event.accept()

    # CloseDialog (end)

    # SettingWindow (start) to show IFP system settings

    def parse_ifp_env_setting(self):
        self.ifp_env_setting = {'Project settings': {'Project': {'Project name': {'widget_type': 'edit',
                                                                                  'value': self.config_dic['PROJECT'],
                                                                                  'description': 'Collocate with \'User group\' to define which default.yaml and api.yaml to use'},
                                                                 'User group': {'widget_type': 'edit',
                                                                                'value': self.config_dic['GROUP'] if 'GROUP' in self.config_dic.keys() else None,
                                                                                'description': 'Collocate with \'Project name\' to define which default.yaml and api.yaml to use'},
                                                                 'Default setting': {'widget_type': 'edit',
                                                                                     'value': self.default_config_file,
                                                                                     'description': 'Define default flow/tasks and task attribute to run'},
                                                                 'API setting': {'widget_type': 'edit',
                                                                                 'value': self.api_yaml,
                                                                                 'split_line': True,
                                                                                 'description': 'Define default IFP API settings to use'},
                                                                 'Auto import tasks': {'widget_type': 'select',
                                                                                       'value': self.auto_import_tasks,
                                                                                       'description': 'Import all tasks setting and dependency when add new block/version'}}
                                                     },
                                'System settings': {'Appearance': {'Fullscreen mode': {'widget_type': 'select',
                                                                                       'value': self.fullscreen_flag,
                                                                                       'description': 'Launch IFP in fullscreen mode'}},
                                                    'Cluster management': {'$BSUB_QUEUE': {'widget_type': 'edit',
                                                                                           'value': self.config_dic['VAR']['BSUB_QUEUE'] if 'BSUB_QUEUE' in self.config_dic['VAR'].keys() else None},
                                                                           '$MAX_RUNNING_JOBS': {'widget_type': 'edit',
                                                                                                 'value': self.config_obj.var_dic.get('MAX_RUNNING_JOBS')}
                                                                           },
                                                    'Process management': {'Ignore fail tasks': {'widget_type': 'select',
                                                                                                 'value': self.ignore_fail,
                                                                                                 'description': 'Even if dependent tasks failed, selected task can start on schedule'},
                                                                           'Rerun before view': {'widget_type': 'select',
                                                                                                 'value': self.rerun_check_or_summarize_before_view,
                                                                                                 'description': 'Auto re-check/re-summarize before view report'},
                                                                           'Send results': {'widget_type': 'select',
                                                                                            'value': self.send_result,
                                                                                            'description': 'Send result to users after action done'},
                                                                           'Confirm rerun tasks': {'widget_type': 'select',
                                                                                                   'value': self.rerun_flag,
                                                                                                   'description': 'Remind user to confirm if rerun PASSED tasks'},
                                                                           'Auto check': {'widget_type': 'select',
                                                                                          'value': self.auto_check,
                                                                                          'description': 'Auto execute check action after run finish'},
                                                                           'Makefile Mode': {'widget_type': 'select',
                                                                                             'value': self.makefile_mode,
                                                                                             'description': 'Automatically select the prerequisite tasks for a Task.'},
                                                                           },

                                                    },
                                'Advanced settings': {'Variable': {'Enable user variable interface': {'widget_type': 'select',
                                                                                                      'value': self.enable_variable_interface,
                                                                                                      'description': 'Show variable interface and can edit variables with effect only in IFP'}},
                                                      'Order': {'Enable user run order interface': {'widget_type': 'select',
                                                                                                    'value': self.enable_order_interface,
                                                                                                    'description': 'Show order interface and can adjust run order between tasks'}},
                                                      'API': {'Enable user API interface': {'widget_type': 'select',
                                                                                            'value': self.enable_api_interface,
                                                                                            'description': 'Show API interface and can enable/disable API'}}

                                                      }}

    def update_ifp_setting(self, settings, need_reload_flag, ignore_fail_flag=True):
        self.ifp_env_setting = settings

        if not settings['Project settings']['Project']['Default setting']['value'] == self.default_config_file:
            self.default_config_file = settings['Project settings']['Project']['Default setting']['value']
            self.task_window.default_yaml = settings['Project settings']['Project']['Default setting']['value']

        if not settings['Project settings']['Project']['API setting']['value'] == self.api_yaml:
            self.api_yaml = settings['Project settings']['Project']['API setting']['value']
            self.task_window.api_yaml = settings['Project settings']['Project']['API setting']['value']

        if not settings['Project settings']['Project']['Auto import tasks']['value'] == self.auto_import_tasks:
            self.setting_parameters_obj.update_local_config('auto_import_tasks', settings['Project settings']['Project']['Auto import tasks']['value'])
            self.auto_import_tasks = settings['Project settings']['Project']['Auto import tasks']['value']

        if not settings['System settings']['Process management']['Confirm rerun tasks']['value'] == self.rerun_flag:
            self.setting_parameters_obj.update_local_config('rerun_flag', settings['System settings']['Process management']['Confirm rerun tasks']['value'])
            self.rerun_flag = settings['System settings']['Process management']['Confirm rerun tasks']['value']

        if not settings['System settings']['Process management']['Rerun before view']['value'] == self.rerun_check_or_summarize_before_view:
            self.setting_parameters_obj.update_local_config('rerun_check_or_summarize_before_view', settings['System settings']['Process management']['Rerun before view']['value'])
            self.rerun_check_or_summarize_before_view = settings['System settings']['Process management']['Rerun before view']['value']

        if not settings['System settings']['Process management']['Ignore fail tasks']['value'] == self.ignore_fail:
            self.setting_parameters_obj.update_local_config('ignore_fail', settings['System settings']['Process management']['Ignore fail tasks']['value'])
            self.ignore_fail = settings['System settings']['Process management']['Ignore fail tasks']['value']

            if ignore_fail_flag:
                self.set_ignore_fail_for_all_tasks()

        if not settings['System settings']['Process management']['Send results']['value'] == self.send_result:
            self.setting_parameters_obj.update_local_config('send_result', settings['System settings']['Process management']['Send results']['value'])
            self.send_result = settings['System settings']['Process management']['Send results']['value']

        if not settings['System settings']['Process management']['Auto check']['value'] == self.auto_check:
            self.setting_parameters_obj.update_local_config('auto_check', settings['System settings']['Process management']['Auto check']['value'])
            self.auto_check = settings['System settings']['Process management']['Auto check']['value']

        if not settings['System settings']['Process management']['Makefile Mode']['value'] == self.makefile_mode:
            self.setting_parameters_obj.update_local_config('makefile_mode', settings['System settings']['Process management']['Makefile Mode']['value'])
            self.makefile_mode = settings['System settings']['Process management']['Makefile Mode']['value']

        if not settings['System settings']['Appearance']['Fullscreen mode']['value'] == self.fullscreen_flag:
            self.setting_parameters_obj.update_local_config('fullscreen_flag', settings['System settings']['Appearance']['Fullscreen mode']['value'])
            self.fullscreen_flag = settings['System settings']['Appearance']['Fullscreen mode']['value']

        if not settings['Advanced settings']['Variable']['Enable user variable interface']['value'] == self.enable_variable_interface:
            self.setting_parameters_obj.update_local_config('enable_variable_interface', settings['Advanced settings']['Variable']['Enable user variable interface']['value'])
            self.enable_variable_interface = settings['Advanced settings']['Variable']['Enable user variable interface']['value']
            self.hide_config_tab(self.var_widget)

        if not settings['Advanced settings']['Order']['Enable user run order interface']['value'] == self.enable_order_interface:
            self.setting_parameters_obj.update_local_config('enable_order_interface', settings['Advanced settings']['Order']['Enable user run order interface']['value'])
            self.enable_order_interface = settings['Advanced settings']['Order']['Enable user run order interface']['value']
            self.hide_config_tab(self.dependency_widget)

        if not settings['Advanced settings']['API']['Enable user API interface']['value'] == self.enable_api_interface:
            self.setting_parameters_obj.update_local_config('enable_api_interface', settings['Advanced settings']['API']['Enable user API interface']['value'])
            self.enable_api_interface = settings['Advanced settings']['API']['Enable user API interface']['value']
            self.hide_config_tab(self.api_widget)

        self.setting_parameters_obj.save_local_config()

        if self.fullscreen_flag:
            self.showMaximized()

        if need_reload_flag:
            self.task_window.save()

    def set_ignore_fail_for_all_tasks(self):
        for (i, main_table_info) in enumerate(self.main_table_info_list):
            task_obj = self.main_table_info_list[i]['Task_obj']
            # main_table_item = self.main_table_model.item(i, 4)
            index = self.main_table_model.index(i, 4)

            if self.ignore_fail:
                task_obj.ignore_fail = True

                if index is not None:
                    icon = QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/ignore_fail.png')
                    self.main_table_model.setData(index, icon, Qt.DecorationRole)

                # if isinstance(main_table_item, QTableWidgetItem):
                #     main_table_item.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/ignore_fail.png'))
            else:
                task_obj.ignore_fail = False

                if index is not None:
                    self.main_table_model.setData(index, QIcon(), Qt.DecorationRole)

                # if isinstance(main_table_item, QTableWidgetItem):
                #     main_table_item.setIcon(QIcon())

    # SettingWindow (end)

    # ViewWindow (start) to show or hide columns/rows
    def gen_main_view_gui(self):
        self.config_view_window = ViewWindow(status_dic=self.view_status_dic, disable_list=self.view_disable_item_list, title=f'{self.tab_name} View')
        self.config_view_window.setWindowModality(Qt.ApplicationModal)
        # self.config_view_window.item_select_status_signal.connect(self.update_main_view)
        self.config_view_window.status.connect(self.apply_main_table_status)
        self.config_view_window.save_cache.connect(functools.partial(self.cache_view_window_status, tab_name=self.tab_name, view_status_dic=self.view_status_dic))
        self.config_view_window.init_ui()
        self.config_view_window.show()

    def apply_main_table_status(self, status: dict):
        for view_name, view_status in status.items():
            for item_name, item_status in view_status.items():
                self.update_main_table_row_visible(view_name=view_name, item_text=item_name, item_select_status=item_status)

        self.view_status_dic = status
        self.config_obj.update_batch_visible(view_status=self.view_status_dic)
        self.update_main_table_status()

    def update_main_table_row_visible(self, view_name, item_text, item_select_status):
        if view_name == 'column':
            pass

        elif view_name == 'block':
            # Update self.main_table_info_list (Visible or not).
            if item_select_status:
                # branch hidden remain hidden
                exclude_visible_row_list = []

                for task in self.task_row_mapping.keys():
                    if (task in self.view_status_dic['task'].keys()) and (not self.view_status_dic['task'][task]):
                        exclude_visible_row_list += self.task_row_mapping[task]

                for row in self.block_row_mapping[item_text]:
                    if row not in exclude_visible_row_list:
                        self.main_table_info_list[row]['Visible'] = True
            else:
                for row in self.block_row_mapping[item_text]:
                    self.main_table_info_list[row]['Visible'] = False
        elif view_name == 'task':
            # Update self.main_table_info_list (Visible or not).
            if item_select_status:
                # branch hidden remain hidden
                exclude_visible_row_list = []

                for block in self.block_row_mapping.keys():
                    if (block in self.view_status_dic['block'].keys()) and (not self.view_status_dic['block'][block]):
                        exclude_visible_row_list += self.block_row_mapping[block]

                for row in self.task_row_mapping[item_text]:
                    if row not in exclude_visible_row_list:
                        self.main_table_info_list[row]['Visible'] = True
            else:
                for row in self.task_row_mapping[item_text]:
                    self.main_table_info_list[row]['Visible'] = False

    def update_main_table_status(self):
        self.update_main_table()
        self.update_status_table()
        self.sidebar_tree.update()

    def _show_hide_table_row(self, row: int, column: int, enable: bool):
        if column == 3:
            self.main_table_info_list[row]['Visible'] = enable
        elif column == 0:
            block = self.main_table_info_list[row]['Block']
            self.update_main_table_row_visible('block', self.main_table_info_list[row]['Block'], enable)
            self.view_status_dic['block'][block] = enable
            self.config_obj.update_batch_visible(view_status=self.view_status_dic)
        else:
            return

        self.update_main_table_status()
        self.top_tab.setCurrentIndex(1)

    def gen_config_view_gui(self):
        self.config_view_window = ViewWindow(status_dic=self.task_window.view_status_dic, title=f'{self.task_window.tab_name} View')
        self.config_view_window.setWindowModality(Qt.ApplicationModal)
        self.config_view_window.status.connect(self.task_window.apply_config_view_status)
        self.config_view_window.init_ui()
        self.config_view_window.show()

    # ViewWindow (end)

    # MultipleSelectWindow (start)
    def select_flows(self):
        flow_list = self.get_all_flows()
        self.flow_multiple_select_window = MultipleSelectWindow('Select Flows', flow_list)
        self.flow_multiple_select_window.item_select_status_signal.connect(self.update_flow_select_status)
        self.flow_multiple_select_window.show()

    def get_all_flows(self):
        flow_list = []

        for main_table_info in self.main_table_info_list:
            if main_table_info['Flow'] not in flow_list:
                flow_list.append(main_table_info['Flow'])

        return flow_list

    def update_flow_select_status(self, flow, flow_select_status):
        if flow_select_status:
            status = Qt.Checked
            self.update_message_text({'message': 'Flow "' + str(flow) + '" is selected.', 'color': 'black'})
        else:
            status = Qt.Unchecked
            self.update_message_text({'message': 'Flow "' + str(flow) + '" is un-selected.', 'color': 'black'})

        for main_table_info in self.main_table_info_list:
            if flow == main_table_info['Flow']:
                self.update_main_table_item(main_table_info['Block'], main_table_info['Version'], main_table_info['Flow'], main_table_info['Task'], 'Task', main_table_info['Task'], selected=status)

    def select_tasks(self):
        task_list = self.get_all_tasks()
        self.task_multiple_select_window = MultipleSelectWindow('Select Tasks', task_list)
        self.task_multiple_select_window.item_select_status_signal.connect(self.update_task_select_status)
        self.task_multiple_select_window.show()

    def get_all_tasks(self):
        task_list = []

        for main_table_info in self.main_table_info_list:
            if main_table_info['Task'] not in task_list:
                task_list.append(main_table_info['Task'])

        return task_list

    def update_task_select_status(self, task, task_select_status):
        if task_select_status:
            status = Qt.Checked
            self.update_message_text({'message': 'Task "' + str(task) + '" is selected.', 'color': 'black'})
        else:
            status = Qt.Unchecked
            self.update_message_text({'message': 'Task "' + str(task) + '" is un-selected.', 'color': 'black'})

        for main_table_info in self.main_table_info_list:
            if task == main_table_info['Task']:
                self.update_main_table_item(main_table_info['Block'], main_table_info['Version'], main_table_info['Flow'], main_table_info['Task'], 'Task', main_table_info['Task'], selected=status)

    # MultipleSelectWindow (end)

    # Process status/config files (start) #
    def save_status_file(self, status_file=''):
        if self.read_mode:
            return

        if not status_file:
            (status_file, file_type) = QFileDialog.getSaveFileName(self, 'Save status file', '.', 'YAML (*.yaml)')

        if status_file:
            frame = inspect.currentframe()
            caller_frame = frame.f_back
            caller_info = inspect.getframeinfo(caller_frame)

            if not caller_info.function == 'generate_main_tab_api_menu':
                self.update_message_text({'message': 'Save status into file "' + str(status_file) + '".', 'color': 'black'})

            # Seitch self.main_table_info_list into a dict.
            main_table_info_dic = {i: {'Block': main_table_info['Block'],
                                       'Version': main_table_info['Version'],
                                       'Flow': main_table_info['Flow'],
                                       'Task': main_table_info['Task'],
                                       'Status': main_table_info['Status'],
                                       'BuildStatus': main_table_info['BuildStatus'],
                                       'RunStatus': main_table_info['RunStatus'],
                                       'CheckStatus': main_table_info['CheckStatus'],
                                       'SummarizeStatus': main_table_info['SummarizeStatus'],
                                       'ReleaseStatus': main_table_info['ReleaseStatus'],
                                       'Job': main_table_info['Job'],
                                       'Runtime': main_table_info['Runtime'],
                                       'Visible': main_table_info['Visible'],
                                       'Selected': main_table_info['Selected']}
                                   for i, main_table_info in enumerate(self.main_table_info_list)}

            with open(status_file, 'w', encoding='utf-8') as SF:
                yaml.dump(main_table_info_dic, SF, indent=4, sort_keys=False, Dumper=yaml.CDumper)

        self.save_api_for_read_mode()

    def load_status_file(self, status_file='', api_reload: bool = True):
        if not status_file:
            (status_file, file_type) = QFileDialog.getOpenFileName(self, 'Load status file', '.', '*')

        if status_file and os.path.exists(status_file):
            self.update_message_text({'message': 'Load status with file "' + str(status_file) + '".', 'color': 'black'})

            # Get status from status file.
            with open(status_file, 'r', encoding='utf-8') as SF:
                saved_status_dic = yaml.load(SF, Loader=yaml.CLoader)

            if not saved_status_dic:
                saved_status_dic = {}

            for (j, status_dic) in saved_status_dic.items():
                if not type(j) is int or not {'Status', 'BuildStatus', 'RunStatus', 'CheckStatus', 'SummarizeStatus', 'ReleaseStatus', 'Job', 'Runtime', 'Visible', 'Selected'} < set(status_dic.keys()):
                    self.update_message_text({'message': 'Failed load status with file "' + str(status_file) + '" due to format is wrong.', 'color': 'red'})
                    return

            # Update self.main_table_info_list with new status_file.
            for (i, main_table_info) in enumerate(self.main_table_info_list):
                for (j, status_dic) in saved_status_dic.items():
                    if (main_table_info['Block'] == status_dic['Block']) and (main_table_info['Version'] == status_dic['Version']) and (main_table_info['Flow'] == status_dic['Flow']) and (main_table_info['Task'] == status_dic['Task']):
                        status = status_dic['Status']
                        # runtime = status_dic['Runtime']
                        job = status_dic['Job']

                        if status == common.status.running:
                            status = self._update_main_tab_job_status(status=status, job=job, api_reload=api_reload)

                        self.main_table_info_list[i]['Status'] = status
                        self.main_table_info_list[i]['BuildStatus'] = status_dic['BuildStatus']
                        self.main_table_info_list[i]['RunStatus'] = status_dic['RunStatus']
                        self.main_table_info_list[i]['CheckStatus'] = status_dic['CheckStatus']
                        self.main_table_info_list[i]['SummarizeStatus'] = status_dic['SummarizeStatus']
                        self.main_table_info_list[i]['ReleaseStatus'] = status_dic['ReleaseStatus']
                        self.main_table_info_list[i]['Job'] = status_dic['Job']
                        self.main_table_info_list[i]['Runtime'] = status_dic['Runtime']
                        self.main_table_info_list[i]['Visible'] = status_dic['Visible']
                        self.main_table_info_list[i]['Selected'] = status_dic['Selected']

            # Update related GUI parts.
            self.update_main_table()
            self.update_status_table()

    def clear_task_status(self):
        reply = QMessageBox.question(self, 'Clear task status', 'Sure to clear all task status (including Job ID and Runtime info)?', QMessageBox.Yes | QMessageBox.Cancel)

        if not reply == QMessageBox.Yes:
            return

        status_file = './.ifp.status.yaml'
        clear_dic = {}

        for (i, main_table_info) in enumerate(self.main_table_info_list):
            block = main_table_info['Block']
            version = main_table_info['Version']
            flow = main_table_info['Flow']
            task = main_table_info['Task']
            visible = main_table_info['Visible']
            selected = main_table_info['Selected']

            clear_dic[i] = {
                'Block': block,
                'Version': version,
                'Flow': flow,
                'Task': task,
                'Status': '',
                'BuildStatus': '',
                'RunStatus': '',
                'CheckStatus': '',
                'SummarizeStatus': '',
                'ReleaseStatus': '',
                'Job': '',
                'Runtime': '',
                'Visible': visible,
                'Selected': selected,
            }

        with open(status_file, 'w') as f:
            yaml.dump(clear_dic, f, indent=4, sort_keys=False)

        self.load_status_file(status_file)

    def _update_main_tab_job_status(self, status: str, job: str, api_reload: bool = False) -> str:
        check, job_dic = TaskJobCheckWorker.check_job_id(job_id=job)
        new_status = ''

        if check:
            if job_dic.get('job_type') == 'LSF':
                new_status = TaskJobCheckWorker.get_lsf_job_status(job_id=str(job_dic['job_id']), api_reload=api_reload)
            elif job_dic.get('job_type') == 'LOCAL':
                new_status = TaskJobCheckWorker.get_local_job_status(job_id=str(job_dic['job_id']))

        return new_status if new_status else status

    def save(self, save_mode='keep'):
        """
        save_mode=keep : user can not define new ifp.cfg.yaml
        save_mode=<others> : filedialog for user to define new ifp.cfg.yaml
        """
        config_file = self.task_window.config_file

        if not save_mode == 'keep':
            (config_file, file_type) = QFileDialog.getSaveFileName(self, 'Save config file', config_file, 'Config Files (*.yaml)')
            self.task_window.parsing_final_setting()

        if config_file:
            self.task_window.final_setting['PROJECT'] = self.ifp_env_setting['Project settings']['Project']['Project name']['value']
            self.task_window.final_setting['GROUP'] = self.ifp_env_setting['Project settings']['Project']['User group']['value']
            self.task_window.final_setting['DEFAULT_YAML'] = self.default_config_file
            self.task_window.final_setting['API_YAML'] = self.api_yaml
            self.task_window.final_setting['VAR']['BSUB_QUEUE'] = self.ifp_env_setting['System settings']['Cluster management']['$BSUB_QUEUE']['value']
            self.task_window.final_setting['VAR']['MAX_RUNNING_JOBS'] = self.ifp_env_setting['System settings']['Cluster management']['$MAX_RUNNING_JOBS']['value']

            with open(config_file, 'w', encoding='utf-8') as SF:
                yaml.dump(dict(self.task_window.final_setting), SF, indent=4, sort_keys=False)

            self.load(config_file)

        if os.path.getsize(self.ifp_config_file) == 0:
            self.config_tab.setCurrentIndex(0)
            self.guide_window.show()

    def load(self, config_file='', api_reload: bool = True):
        if not config_file:
            (config_file, file_type) = QFileDialog.getOpenFileName(self, 'Load config file', '.', '*')

        with common_pyqt5.WaitingWindow('Loading IFP ...'):
            if config_file:
                try:
                    with open(config_file, 'r') as fh:
                        yaml.load(fh, Loader=yaml.FullLoader)
                except Exception:
                    self.update_message_text({'message': 'Failed load config file "' + str(config_file) + '".', 'color': 'red'})
                    self.progress_dialog.close()
                    return

                self.save_status_file(self.ifp_status_file)
                self.update_message_text({'message': 'Load config file "' + str(config_file) + '".', 'color': 'black'})
                # Update self.config_dic and self.main_table_info_list with new config_file.
                self.update_dict_by_load_config_file(config_file)
                self.config_obj.save_ifp_records()
                # Update related GUI parts.
                self.load_cache()
                self.config_obj.update_batch_visible(view_status=self.view_status_dic)
                self.update_sidebar_tree()
                # self.update_status_table()
                self.update_tab_index_dic()
                # self.update_main_table()
                self.set_ignore_fail_for_all_tasks()
                self.full_flowchart_window.gen_full_flow_graph(dependency_dic=self.task_window.dependency_priority)
                self.load_status_file(self.ifp_status_file, api_reload=api_reload)
                self.task_window.config_file = config_file
                self.task_window.config_path_edit.setText(config_file)
                self.task_window.load()
                self.update_config_tab()
                self.remove_status_icon()

                try:
                    self.update_api_menubar()
                    self.update_api_toolbar()
                except Exception:
                    pass

            self.export_complete_ifp_cfg_yaml()

    def update_api_menubar(self):
        for menu in self.api_menu_list:
            if not isinstance(menu, QMenu):
                continue

            self.menuBar().removeAction(menu.menuAction())

        self.api_menu_list = common.add_api_menu_bar(self, self.user_api, self.menuBar())

    def update_api_toolbar(self):
        for toolbar in self.api_toolbar_list:
            if not isinstance(toolbar, QToolBar):
                continue

            self.removeToolBar(toolbar)

        self.api_toolbar_list = common.add_api_tool_bar(self, self.user_api)

    def reload_config_after_finished_api(self):
        while True:
            if self.progress_dialog is None:
                break

            time.sleep(1)

        self.load(self.task_window.config_file, api_reload=True)
        self.progress_dialog = None

    def blocking_gui(self, action_name: str):
        self.progress_dialog = QProgressDialog(f"Executing {action_name} and blocking main GUI", "Cancel", 0, 0, self)
        self.progress_dialog.setWindowTitle('Executing API')
        self.progress_dialog.setCancelButton(None)
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setWindowFlags(Qt.Window | Qt.WindowTitleHint | Qt.CustomizeWindowHint | Qt.WindowStaysOnTopHint)
        self.progress_dialog.setRange(0, 0)
        self.progress_dialog.show()
        self.progress_dialog.raise_()
        self.progress_dialog.activateWindow()
        QApplication.processEvents()

    def unblocking_gui(self):
        if self.progress_dialog is not None:
            self.progress_dialog.close()

        self.progress_dialog = None

    def export_complete_ifp_cfg_yaml(self):
        complete_ifp_cfg_yaml_path = f'{self.ifp_cache_dir}/ifp.cfg.complete.yaml'
        complete_dict = {'PROJECT': self.ifp_env_setting['Project settings']['Project']['Project name']['value'], 'GROUP': self.ifp_env_setting['Project settings']['Project']['User group']['value'], 'DEFAULT_YAML': self.default_config_file, 'API_YAML': self.api_yaml, 'BLOCK': {}, 'VAR': {}}

        for block in self.config_dic['BLOCK'].keys():
            complete_dict['BLOCK'].setdefault(block, {})
            for version in self.config_dic['BLOCK'][block].keys():
                complete_dict['BLOCK'][block].setdefault(version, {})
                for flow in self.config_dic['BLOCK'][block][version].keys():
                    complete_dict['BLOCK'][block][version].setdefault(flow, {})
                    for task in self.config_dic['BLOCK'][block][version][flow].keys():
                        complete_dict['BLOCK'][block][version].setdefault(flow, {})
                        complete_dict['BLOCK'][block][version][flow][task] = copy.deepcopy(self.config_dic['BLOCK'][block][version][flow][task]['ACTION'])
                        complete_dict['BLOCK'][block][version][flow][task]['RUN_AFTER'] = copy.deepcopy(self.config_dic['BLOCK'][block][version][flow][task]['RUN_AFTER'])

        for (key, value) in self.config_obj.var_dic.items():
            complete_dict['VAR'][key] = value

        with open(complete_ifp_cfg_yaml_path, 'w', encoding='utf-8') as SF:
            yaml.dump(dict(complete_dict), SF, indent=4, sort_keys=False, default_flow_style=False, Dumper=yaml.SafeDumper)

    def update_dict_by_load_config_file(self, config_file):
        self.ifp_config_file = config_file

        if self.read_mode:
            common.update_for_read_mode(cwd=os.path.dirname(self.ifp_config_file), user=pwd.getpwuid(os.stat(self.ifp_config_file).st_uid).pw_name)

        self.config_obj = parse_config.Config(config_file)
        self.config_obj.update_for_read_mode(cwd=os.path.dirname(self.ifp_config_file), user=pwd.getpwuid(os.stat(self.ifp_config_file).st_uid).pw_name)
        self.default_config_file = self.config_obj.default_config_file
        self.api_yaml = self.config_obj.api_yaml
        self.user_api = common.parse_user_api(self.api_yaml)
        self.save_api_for_read_mode()
        self.config_dic = self.config_obj.config_dic
        self.main_table_info_list = self.config_obj.main_table_info_list
        self.job_manager.update(self.config_dic)
        self.block_row_mapping = {}
        self.task_row_mapping = {}
        self.parse_ifp_env_setting()

        self.view_status_dic['block'] = {}
        self.view_status_dic['task'] = {}

        for (i, main_table_info) in enumerate(self.main_table_info_list):

            block = main_table_info['Block']
            self.view_status_dic['block'][block] = True

            if block not in self.block_row_mapping.keys():
                self.block_row_mapping[block] = [i]
            else:
                self.block_row_mapping[block].append(i)

            version = main_table_info['Version']
            flow = main_table_info['Flow']
            task = main_table_info['Task']
            self.view_status_dic['task'][task] = True

            if task not in self.task_row_mapping.keys():
                self.task_row_mapping[task] = [i]
            else:
                self.task_row_mapping[task].append(i)

            self.main_table_info_list[i]['Task_obj'] = self.job_manager.all_tasks[block][version][flow][task]

    def save_api_for_read_mode(self):
        if self.read_mode:
            return

        if self.api_yaml:
            try:
                dir_path = os.path.join(os.getcwd(), '.ifp/config')
                os.makedirs(dir_path, exist_ok=True)

                with open(os.path.join(dir_path, os.path.basename(self.api_yaml)), 'w') as ap:
                    ap.write(yaml.dump(self.user_api, allow_unicode=True))
            except Exception as error:
                print(f'*Error*: {str(error)}')

    # Process status/config files (end) #

    # Toolbar functions (start)
    def zoom_in(self):
        self.update_message_text({'message': 'Zoom in', 'color': 'black'})

        self.gui_width = self.width()
        self.gui_height = self.height()
        self.showNormal()
        self.gui_height += 30
        self.resize(self.gui_width, self.gui_height)

    def zoom_out(self):
        self.update_message_text({'message': 'Zoom out', 'color': 'black'})

        self.gui_width = self.width()
        self.gui_height = self.height()
        self.showNormal()
        self.gui_height -= 30
        self.resize(self.gui_width, self.gui_height)

    def show_lsf_monitor(self):
        self.update_message_text({'message': 'Show LSF/Openlava information with tool "bmonitor".', 'color': 'black'})

        bmonitor = shutil.which('bmonitor')

        if not bmonitor:
            bmonitor = str(os.environ['IFP_INSTALL_PATH']) + '/tools/lsfMonitor/monitor/bin/bmonitor'

        if os.path.exists(bmonitor):
            self.run_monitor(bmonitor, 'default')
        else:
            QMessageBox.warning(self, 'LSF Monitor Warning', 'Not find "bmonitor" on system.')

    # Toolbar function (end)

    # config_tab (start) #
    def gen_config_tab(self):
        # config tab -> task setting
        self.task_widget = self.task_window.init_ui()
        self.task_widget.setWhatsThis('saved')

        # setting tab -> ifp setting
        self.setting_window = SettingWindow(self, self.ifp_env_setting, mode='widget')
        self.setting_widget = self.setting_window.init_ui()
        self.setting_widget.update_setting_flag.connect(self.update_ifp_setting)
        self.setting_widget.update.connect(self.update_config_tab_name)
        self.setting_widget.setWhatsThis('saved')

        # env tab -> ifp variable setting
        self.var_window = WindowForToolGlobalEnvEditor(default_var=self.task_window.default_var, user_var=self.task_window.user_var)
        self.var_widget = self.var_window.init_ui()
        self.var_widget.message.connect(self.task_window.update_extension_config_setting)
        self.var_widget.update.connect(self.update_config_tab_name)
        self.var_widget.setWhatsThis('saved')

        # dependency tab -> task/flow dependency setting
        self.dependency_window.update_setting(dependency_priority_dic=self.task_window.dependency_priority,
                                              default_dependency_dic=self.task_window.default_dependency_dic)
        self.dependency_window.message.connect(self.task_window.update_extension_config_setting)
        self.dependency_window.update.connect(self.update_config_tab_name)
        self.dependency_widget.setWhatsThis('saved')

        # API -> ifp api setting
        self.api_window = WindowForAPI(api_yaml=self.api_yaml)
        self.api_widget = self.api_window.init_ui()
        self.api_widget.update.connect(self.update_config_tab_name)
        self.api_widget.message.connect(self.task_window.update_extension_config_setting)
        self.api_widget.setWhatsThis('saved')

        self.config_tab_index = {self.setting_widget: 'Setting',
                                 self.task_widget: 'Task',
                                 self.dependency_widget: 'Order',
                                 self.var_widget: 'Variable',
                                 self.api_widget: 'API'}

        self.update_tab_label_dic()

        for widget in self.config_tab_index.keys():
            if widget == self.var_widget and not self.enable_variable_interface:
                continue
            elif widget == self.dependency_widget and not self.enable_order_interface:
                continue
            elif widget == self.api_widget and not self.enable_api_interface:
                continue

            self.config_tab.addTab(widget, self.config_tab_index[widget])

        self.config_tab.setTabPosition(QTabWidget.West)

        if os.path.getsize(self.ifp_config_file) == 0:
            self.config_tab.setCurrentIndex(0)
            self.guide_window.show()
        else:
            self.config_tab.setCurrentIndex(1)

        self.config_tab.currentChanged.connect(self.check_config_unsaved_tab)

    def update_config_tab(self):
        self.config_tab.currentChanged.disconnect()
        current_index = self.config_tab.currentIndex()

        # setting tab -> ifp setting
        self.setting_window = SettingWindow(self, self.ifp_env_setting, mode='widget')
        self.setting_widget = self.setting_window.init_ui()
        self.setting_widget.update_setting_flag.connect(self.update_ifp_setting)
        self.setting_widget.update.connect(self.update_config_tab_name)
        self.setting_widget.setWhatsThis('saved')

        # env tab -> ifp variable setting
        self.var_window = WindowForToolGlobalEnvEditor(default_var=self.task_window.default_var, user_var=self.task_window.user_var)
        self.var_widget = self.var_window.init_ui()
        self.var_widget.message.connect(self.task_window.update_extension_config_setting)
        self.var_widget.update.connect(self.update_config_tab_name)
        self.var_widget.setWhatsThis('saved')

        # dependency tab -> task/flow dependency setting
        self.dependency_window.update_setting(dependency_priority_dic=self.task_window.dependency_priority,
                                              default_dependency_dic=self.task_window.default_dependency_dic)

        self.dependency_widget.setWhatsThis('saved')

        # API -> ifp api setting
        self.api_window = WindowForAPI(api_yaml=self.api_yaml)
        self.api_widget = self.api_window.init_ui()
        self.api_widget.update.connect(self.update_config_tab_name)
        self.api_widget.message.connect(self.task_window.update_extension_config_setting)
        self.api_widget.setWhatsThis('saved')

        self.config_tab_index = {self.setting_widget: 'Setting',
                                 self.task_widget: 'Task',
                                 self.dependency_widget: 'Order',
                                 self.var_widget: 'Variable',
                                 self.api_widget: 'API'}

        self.update_tab_label_dic()
        self.config_tab.removeTab(0)
        self.config_tab.insertTab(0, self.setting_widget, 'Setting')

        if self.enable_order_interface:
            self.config_tab.removeTab(self.tab_label_dic['Order'])
            self.config_tab.insertTab(self.tab_label_dic['Order'], self.dependency_widget, 'Order')

        if self.enable_variable_interface:
            self.config_tab.removeTab(self.tab_label_dic['Variable'])
            self.config_tab.insertTab(self.tab_label_dic['Variable'], self.var_widget, 'Variable')

        if self.enable_api_interface:
            self.config_tab.removeTab(self.tab_label_dic['API'])
            self.config_tab.insertTab(self.tab_label_dic['API'], self.api_widget, 'API')

        self.config_tab.setCurrentIndex(current_index)
        self.config_tab.currentChanged.connect(self.check_config_unsaved_tab)

    def hide_config_tab(self, widget):
        self.update_tab_label_dic()

        if self.config_tab.indexOf(widget) == -1:
            self.config_tab.insertTab(list(self.config_tab_index.keys()).index(widget), widget, self.config_tab_index[widget])
        else:
            self.config_tab.removeTab(self.config_tab.indexOf(widget))

    def check_config_unsaved_tab(self):
        unsaved_flag = False
        unsaved_index = 0

        for i in range(self.config_tab.count()):
            tab_status = self.config_tab.widget(i).whatsThis()

            if tab_status and tab_status == 'unsaved':
                unsaved_flag = True
                unsaved_index = i
                break

        if unsaved_flag:
            self.config_tab.currentChanged.disconnect()
            self.config_tab.setCurrentIndex(unsaved_index)
            self.config_tab.currentChanged.connect(self.check_config_unsaved_tab)

            common_pyqt5.Dialog(
                title='Save Changes?',
                info='Save your changes or reset before leaving current tab',
                icon=QMessageBox.Warning
            )

    def update_tab_label_dic(self):
        self.tab_label_dic = {'Setting': 0,
                              'Task': 1,
                              'Order': 2,
                              'Variable': 3,
                              'API': 4}

        for tab in self.tab_label_dic:
            if tab == 'Order' and not self.enable_order_interface:
                self.tab_label_dic['Variable'] -= 1
                self.tab_label_dic['API'] -= 1
            elif tab == 'Variable' and not self.enable_variable_interface:
                self.tab_label_dic['API'] -= 1

    def update_tab_index_dic(self):
        self.config_tab_index = {self.setting_widget: 'Setting',
                                 self.task_widget: 'Task',
                                 self.dependency_widget: 'Order',
                                 self.var_widget: 'Variable',
                                 self.api_widget: 'API'}

    def update_config_tab_name(self, state=None, update_name=None):
        if state is None or not update_name:
            return

        if state:
            if update_name == 'Setting':
                self.config_tab.setTabText(0, "* Setting")
                self.config_tab.tabBar().setTabTextColor(0, QColor('red'))
                self.setting_widget.setWhatsThis('unsaved')
            elif update_name == 'Order':
                self.config_tab.setTabText(self.tab_label_dic['Order'], "* Order")
                self.config_tab.tabBar().setTabTextColor(self.tab_label_dic['Order'], QColor('red'))
                self.dependency_widget.setWhatsThis('unsaved')
            elif update_name == 'env':
                self.config_tab.setTabText(self.tab_label_dic['Variable'], "* Variable")
                self.config_tab.tabBar().setTabTextColor(self.tab_label_dic['Variable'], QColor('red'))
                self.var_widget.setWhatsThis('unsaved')
            elif update_name == 'API':
                self.config_tab.setTabText(self.tab_label_dic['API'], "* API")
                self.config_tab.tabBar().setTabTextColor(self.tab_label_dic['API'], QColor('red'))
                self.api_widget.setWhatsThis('unsaved')
        else:
            if update_name == 'Setting':
                self.config_tab.setTabText(0, "Setting")
                self.config_tab.tabBar().setTabTextColor(0, QColor('black'))
                self.setting_widget.setWhatsThis('saved')
            elif update_name == 'env':
                self.config_tab.setTabText(self.tab_label_dic['Variable'], 'Variable')
                self.config_tab.tabBar().setTabTextColor(self.tab_label_dic['Variable'], QColor('black'))
                self.var_widget.setWhatsThis('saved')
            elif update_name == 'Order':
                self.config_tab.setTabText(self.tab_label_dic['Order'], "Order")
                self.config_tab.tabBar().setTabTextColor(self.tab_label_dic['Order'], QColor('black'))
                self.dependency_widget.setWhatsThis('saved')
            elif update_name == 'API':
                self.config_tab.setTabText(self.tab_label_dic['API'], "API")
                self.config_tab.tabBar().setTabTextColor(self.tab_label_dic['API'], QColor('black'))
                self.api_widget.setWhatsThis('saved')

    # config_tab (end) #

    # main_tab (start) #
    def gen_main_tab(self):
        # self.sidebar_tree
        # self.sidebar_tree = QTreeWidget(self.main_tab)
        self.tree_frame = QFrame(self.main_tab)
        self.tree_frame.setFrameShadow(QFrame.Raised)
        self.tree_frame.setFrameShape(QFrame.Box)

        self.sidebar_tree = SidebarTree()
        self.sidebar_tree.go_to_msg.connect(self._go_to_table_row)
        self.sidebar_tree.show_hide_item.connect(self._show_hide_table_row)

        # self.status_table
        self.status_table = QTableWidget(self.main_tab)

        self.main_frame = QFrame(self.main_tab)
        self.main_frame.setFrameShadow(QFrame.Raised)
        self.main_frame.setFrameShape(QFrame.Box)

        splitter = QSplitter()
        splitter.setOrientation(Qt.Horizontal)
        splitter.addWidget(self.tree_frame)
        splitter.addWidget(self.main_frame)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 5)

        main_tab_grid = QVBoxLayout()
        main_tab_grid.addWidget(splitter)
        self.main_tab.setLayout(main_tab_grid)

        # Gen sub-frames.
        self.gen_sidebar_tree()
        self.gen_main_frame()
        self.gen_status_table()

    def disable_gui(self, signal):
        if signal:
            self.setting_window.disable_gui()
            self.task_window.disable_gui()

            if self.dependency_widget is not None:
                self.dependency_window.disable_gui()

            self.var_window.disable_gui()
            self.api_window.disable_gui()
            self.save_status_file_action.setDisabled(True)
            self.load_status_file_action.setDisabled(True)
            self.clear_status_action.setDisabled(True)
            self.disable_gui_flag = True
        else:
            self.setting_window.enable_gui()
            self.task_window.enable_gui()

            if self.dependency_widget is not None:
                self.dependency_window.enable_gui()

            self.var_window.enable_gui()
            self.api_window.enable_gui()
            self.save_status_file_action.setDisabled(False)
            self.load_status_file_action.setDisabled(False)
            self.clear_status_action.setDisabled(False)
            self.disable_gui_flag = False

    # sidebar_tree (start) #
    def gen_sidebar_tree(self):
        layout = QVBoxLayout()
        self.tree_frame.setLayout(layout)

        layout.addWidget(self.sidebar_tree)

    def update_main_table_block_visible_status(self, block, status):
        # Update self.main_table_info_list (Visible or not).
        for (row, main_table_info) in enumerate(self.main_table_info_list):
            if main_table_info['Block'] == block:
                if status == Qt.Checked:
                    self.main_table_info_list[row]['Selected'] = True
                    self.main_table_info_list[row]['Visible'] = True
                elif status == Qt.Unchecked:
                    self.main_table_info_list[row]['Selected'] = False
                    self.main_table_info_list[row]['Visible'] = False

        # Update self.main_table.
        self.update_main_table()

    def update_sidebar_tree(self):
        self.sidebar_tree.update()

    # sidebar_tree (end) #

    # status_table (start) #
    def gen_status_table(self):
        self.status_table.setShowGrid(True)

        # Gen self.status_table title.
        self.status_table.setRowCount(5)
        self.status_table.setVerticalHeaderLabels(['Total', 'Run', 'Passed', 'Failed', 'Others'])

        self.status_table.verticalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.status_table.verticalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.status_table.verticalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.status_table.verticalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.status_table.verticalHeader().setSectionResizeMode(4, QHeaderView.Stretch)

        self.status_table.setColumnCount(1)
        self.status_table.setHorizontalHeaderLabels(['Task Run Status', ])
        self.status_table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft)
        self.status_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)

        # Set status table to read-only
        self.status_table.setEditTriggers(QTableWidget.NoEditTriggers)

        # Trigger a slot function when a cell is double clicked
        self.status_table.cellClicked.connect(self.click_status_table)

        self.status_table.setFixedHeight(150)

        # Update self.status_table.
        self.update_status_table()

    def click_status_table(self, row, column):
        """
        Trigger this function when double clicked status table
        """
        item = self.status_table.verticalHeaderItem(row)
        self.status_filt_flag = item.text()

        self.update_main_table()

    def update_status_table(self):
        status_dic = self.get_status_dic()
        hided_status_dic = self.get_hided_status_dic()

        for (row, status) in enumerate(['Total', 'Run', 'Passed', 'Failed', 'Others']):
            if hided_status_dic[status] > 0:
                item = QTableWidgetItem(str(status_dic[status]) + "  (" + str(hided_status_dic[status]) + " hided)")
            else:
                item = QTableWidgetItem(str(status_dic[status]))

            if status == 'Passed':
                item.setForeground(QBrush(Qt.green))
            elif status == 'Failed':
                item.setForeground(QBrush(Qt.red))

            self.status_table.setItem(row, 0, item)

        if not self.status_filt_flag == 'Total':
            self.update_main_table()

    def get_status_dic(self):
        status_dic = {'Total': 0, 'Run': 0, 'Passed': 0, 'Failed': 0, 'Others': 0}

        for main_table_info in self.main_table_info_list:
            status_dic['Total'] += 1
            status = main_table_info['RunStatus']
            check_status = main_table_info['CheckStatus']

            if not status == common.status.running and check_status in [common.status.checking, common.status.passed, common.status.failed]:
                status = check_status

            if status:
                if status == common.status.running:
                    status_dic['Run'] += 1
                elif status == common.status.passed:
                    status_dic['Passed'] += 1
                elif status == common.status.failed:
                    status_dic['Failed'] += 1
                else:
                    status_dic['Others'] += 1
            else:
                status_dic['Others'] += 1

        return status_dic

    def get_hided_status_dic(self):
        hided_status_dic = {'Total': 0, 'Run': 0, 'Passed': 0, 'Failed': 0, 'Others': 0}

        for main_table_info in self.main_table_info_list:
            if not main_table_info['Visible']:
                hided_status_dic['Total'] += 1
                status = main_table_info['RunStatus']
                check_status = main_table_info['CheckStatus']

                if check_status in [common.status.checking, common.status.passed, common.status.failed]:
                    status = check_status

                if status:
                    if status == common.status.running:
                        hided_status_dic['Run'] += 1
                    elif status == common.status.passed:
                        hided_status_dic['Passed'] += 1
                    elif status == common.status.failed:
                        hided_status_dic['Failed'] += 1
                    else:
                        hided_status_dic['Others'] += 1
                else:
                    hided_status_dic['Others'] += 1

        return hided_status_dic

    # status_table (end) #

    # main_frame (start) #
    def gen_main_frame(self):
        # self.main_table = QTableWidget(self.main_frame)
        # self.main_table.horizontalHeader().sectionClicked.connect(self.main_table_title_click_behavior)
        # Gen self.main_table title.
        # self.main_table.setColumnCount(len(self.main_table_title_list))
        # self.main_table.setHorizontalHeaderLabels(self.main_table_title_list)
        self.main_table = QTableView(self.main_frame)
        self.main_table_model = QStandardItemModel(self.main_table)
        self.main_table.setModel(self.main_table_model)
        self.main_table.horizontalHeader().sectionClicked.connect(self.main_table_title_click_behavior)

        self.main_table_model.setColumnCount(len(self.main_table_title_list))
        self.main_table_model.setHorizontalHeaderLabels(self.main_table_title_list)

        # Clear main table Selections.
        self.event_filter = GlobalEventFilter(self.main_table)
        self.qapp = QApplication.instance()
        self.qapp.installEventFilter(self.event_filter)

        """
        self.main_table.itemClicked.connect(self.main_table_item_click_behavior)
        self.main_table.doubleClicked.connect(self.main_table_item_double_click_behavior)
        """
        self.main_table.clicked.connect(self.main_table_item_click_behavior)
        self.main_table.doubleClicked.connect(self.main_table_item_double_click_behavior)

        self.filter_row = common_pyqt5.TableFilterRow(self.main_table, model=self.main_table_model, parent=self, filter_columns=[0, 1, 2, 3, 4])

        main_table_widget = QWidget(self)
        main_table_layout = QVBoxLayout()
        main_table_widget.setLayout(main_table_layout)
        main_table_layout.addWidget(self.filter_row)
        main_table_layout.addWidget(self.main_table)

        # Grid
        main_frame_tab = QTabWidget()
        main_frame_tab.addTab(main_table_widget, 'TableView')
        main_frame_tab.addTab(self.flow_chart_widget, 'FlowChart')
        main_frame_tab.currentChanged.connect(self.on_main_frame_tab_changed)

        main_frame_grid = QGridLayout()
        main_frame_grid.addWidget(main_frame_tab, 0, 0)
        self.main_frame.setLayout(main_frame_grid)

        # self.main_frame.setLayout(main_frame_layout)

        # Gen self.main_table.
        self.gen_main_table()

    def on_main_frame_tab_changed(self, index: int = 0):
        try:
            if index == 0:
                self.full_flowchart_window.timer.stop()
            elif index == 1:
                if self.full_flowchart_window.refresh_interval is not None:
                    self.full_flowchart_window.timer.start(self.full_flowchart_window.refresh_interval * 1000)
        except Exception:
            pass

    def main_table_title_click_behavior(self, index):
        self.memos_logger.log(f'Click Main Table Title -> Index <{str(index)}>')

        if index == 3:
            handle_row_list = []
            status = Qt.Unchecked
            main_table_row = 0

            for row, main_table_info in enumerate(self.main_table_info_list):
                if main_table_info['Visible'] and self.filt_task_status(main_table_info):
                    main_table_row += 1

                    if self.main_table.isRowHidden(main_table_row - 1):
                        continue

                    if not main_table_info['Selected']:
                        status = Qt.Checked

                    handle_row_list.append(row)

            if status == Qt.Checked:
                self.update_message_text({'message': 'All tasks are selected.', 'color': 'black'})
            else:
                self.update_message_text({'message': 'All tasks are un-selected.', 'color': 'black'})

            for row in handle_row_list:
                main_table_info = self.main_table_info_list[row]

                if main_table_info['Visible'] and self.filt_task_status(main_table_info):
                    if status == Qt.Checked:
                        main_table_info['Selected'] = True
                    else:
                        main_table_info['Selected'] = False

                self.update_main_table_item(main_table_info['Block'], main_table_info['Version'], main_table_info['Flow'], main_table_info['Task'], 'Task', main_table_info['Task'], selected=status)

    def main_table_item_click_behavior(self, index):
        if index is None:
            return
        else:
            row = index.row()
            col = index.column()
            # item = self.main_table_model.item(row, col)
            data = self.main_table_model.data(index)
            self.memos_logger.log(f'Click Main Table Item -> ({str(row)}, {str(col)}), Data <{str(data)}>')

        if data is not None:
            self.current_selected_row = row
            self.current_selected_column = col

            visible_row = -1

            for (row, main_table_info) in enumerate(self.main_table_info_list):
                if main_table_info['Visible'] and self.filt_task_status(main_table_info):
                    visible_row += 1

                    if visible_row == self.current_selected_row:
                        self.current_selected_task_dic = main_table_info
                        self.current_selected_task_obj = self.current_selected_task_dic['Task_obj']

                        if self.current_selected_column == 3:
                            if self.main_table_model.data(index, Qt.CheckStateRole) == 0:
                                status = Qt.Unchecked
                                if self.main_table_info_list[row]['Selected']:
                                    self.update_message_text({'message': 'Row ' + str(visible_row + 1) + ', task "' + str(main_table_info['Task']) + '" is un-selected.', 'color': 'black'})
                                self.main_table_info_list[row]['Selected'] = False
                            else:
                                status = Qt.Checked
                                if not self.main_table_info_list[row]['Selected']:
                                    self.update_message_text({'message': 'Row ' + str(visible_row + 1) + ', task "' + str(main_table_info['Task']) + '" is selected.', 'color': 'black'})
                                self.main_table_info_list[row]['Selected'] = True

                            self.update_main_table_item(main_table_info['Block'], main_table_info['Version'], main_table_info['Flow'], main_table_info['Task'], 'Task', main_table_info['Task'], selected=status)
                        elif self.current_selected_column == 5:
                            self.pop_check(main_table_info)
                        elif self.current_selected_column == 6:
                            self.pop_summary(main_table_info)
                        elif self.current_selected_column == 7:
                            job = main_table_info['Job']

                            if job and str(job).startswith('b'):
                                jobid = str(job)[2:]
                                self.update_message_text({'message': 'View job information for "' + str(jobid) + '".', 'color': 'black'})
                                self.view_job_info(jobid)
                            elif job and str(job).startswith('l'):
                                pid = str(job)[2:]
                                (return_code, stdout, stderr) = common.run_command('ps -p {}'.format(pid))

                                if not return_code:
                                    pid = stdout.decode('utf-8').split()[4]
                                    process_info = 'local process running, PID: {}'.format(pid)
                                    self.update_message_text({'message': process_info, 'color': 'black'})
                                else:
                                    self.update_message_text({'message': 'Cannot fetch local process {} info (not supported)'.format(pid), 'color': 'red'})
                        elif self.current_selected_column == 9:
                            self.pop_xterm(main_table_info)

                        all_items = [main_table_info['Block'], main_table_info['Version'], main_table_info['Flow'], main_table_info['Task']]
                        message_items = []

                        for i in range(self.current_selected_column + 1):
                            if self.current_selected_column <= 3:
                                message_items.append(all_items[i])
                            else:
                                continue

                        self.update_status_bar(' -> '.join(message_items))

    def update_select_count(self):
        try:
            select_count = 0
            executed_task_count = 0

            for row, info_dic in enumerate(self.main_table_info_list):
                if info_dic['Selected']:
                    select_count += 1

                    if not self.main_table.isRowHidden(row):
                        executed_task_count += 1

            if select_count:
                if select_count == executed_task_count:
                    self.main_table_model.setHeaderData(3, Qt.Horizontal, "Task (%d selected)" % select_count)
                else:
                    self.main_table_model.setHeaderData(3, Qt.Horizontal, "Task (%d -> %d selected)" % (select_count, executed_task_count))
            else:
                self.main_table_model.setHeaderData(3, Qt.Horizontal, "Task")

        except Exception:
            pass

    def main_table_item_double_click_behavior(self, index):
        if index is None:
            return
        else:
            row = index.row()
            col = index.column()
            data = self.main_table_model.data(index)
            self.memos_logger.log(f'DoubleClick Main Table Item -> ({str(row)}, {str(col)}), Data <{str(data)}>')
            # item = self.main_table_model.item(row, col)

        if self.current_selected_column == 3:
            # status = self.main_table_model.item(row, 4).text().strip()
            status = self.main_table_model.data(index).strip()
            read_only = True if self.disable_gui_flag and status == common.status.running else False
            self.edit_detailed_config(read_only=read_only, block=self.current_selected_task_dic['Block'], version=self.current_selected_task_dic['Version'], flow=self.current_selected_task_dic['Flow'], task=self.current_selected_task_dic['Task'])
        else:
            pass

    def open_file(self, item):
        task = self.config_dic['BLOCK'][item.Block][item.Version][item.Flow][item.Task]

        (log_file, file_type) = QFileDialog.getOpenFileName(self, 'Open file', str(task.PATH), 'LOG (*.log *.log[0-9]*)')

        if log_file:
            command = 'gvim ' + str(os.path.realpath(log_file))

            thread_run = common.ThreadRun()
            thread_run.run([command, ])

    def view_job_info(self, jobid):
        """
        View job information with tool 'lsfMonitor'.
        """
        self.update_message_text({'message': 'Show job information for jobid "' + str(jobid) + '".', 'color': 'black'})

        bmonitor_location = shutil.which('bmonitor')
        bmonitor = bmonitor_location

        if not bmonitor_location:
            bmonitor = str(os.environ['IFP_INSTALL_PATH']) + '/tools/lsfMonitor/monitor/bin/bmonitor'

        if os.path.exists(bmonitor):
            command = str(bmonitor) + ' --disable_license -j ' + str(jobid)
            self.run_monitor(command, str(jobid))
        else:
            QMessageBox.warning(self, 'LSF Monitor Warning', 'Not find "bmonitor" on system.')

    def pop_check(self, item):
        self.execute_action(common.action.check_view, task_dic_list=[item, ])

    def pop_summary(self, item):
        self.execute_action(common.action.summarize_view, task_dic_list=[item, ])

    def pop_xterm(self, item):
        task = self.config_dic['BLOCK'][item.Block][item.Version][item.Flow][item.Task]

        path = common.expand_var(str(task.PATH), ifp_var_dic=self.config_obj.var_dic, **{'BLOCK': item.Block, 'VERSION': item.Version, 'FLOW': item.Flow, 'TASK': item.Task})

        if 'COMMON' in task.ACTION:
            xterm_command = common.expand_var(str(task.ACTION['COMMON']['XTERM_COMMAND']), ifp_var_dic=self.config_obj.var_dic, **{'BLOCK': item.Block, 'VERSION': item.Version, 'FLOW': item.Flow, 'TASK': item.Task})
            command = str(self.xterm_command) + ' "cd ' + path + '; ' + xterm_command + '; exec ' + str(os.environ['SHELL']) + '"'
        else:
            command = str(self.xterm_command) + ' "cd ' + path + '; exec ' + str(os.environ['SHELL']) + '"'

        thread_run = common.ThreadRun(xterm=True)
        thread_run.run([command, ])

    def gen_main_table(self):
        self.main_table.setShowGrid(True)
        self.main_table.verticalHeader().setVisible(True)
        self.main_table.setEditTriggers(QTableView.NoEditTriggers)

        self.main_table.setItemDelegate(common_pyqt5.CustomDelegate(wrap_columns=[0, 1, 2], check_available=True, icon_columns=[3, 4], table_view=self.main_table))
        self.main_table_header = self.main_table.horizontalHeader()
        self.main_table_header.setContextMenuPolicy(Qt.CustomContextMenu)
        self.main_table_header.customContextMenuRequested.connect(self.generate_select_menu)

        # gen open file menu
        self.main_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.main_table.customContextMenuRequested.connect(self.generate_menu)

        # Update self.main_table.
        self.hide_detail_status()

    def _go_to_table_row(self, row: int, column: int):
        count = 0

        for i, main_table_info in enumerate(self.main_table_info_list):
            if not main_table_info['Visible']:
                continue

            if i == row:
                break

            count += 1

        # self.main_table.setCurrentCell(count, column)
        index = self.main_table_model.index(count, column)
        self.main_table.setCurrentIndex(index)

    def generate_select_menu(self, pos):
        menu = QMenu()
        column = self.main_table_header.logicalIndexAt(pos)
        self.memos_logger.log(f'Right Click Main Table Header <{str(column)}>')

        if column in [2, 3]:
            select_flows_action = QAction('Select Flows', self)
            select_flows_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/red/F.png'))
            select_flows_action.triggered.connect(self.select_flows)
            menu.addAction(select_flows_action)

            select_steps_action = QAction('Select Tasks', self)
            select_steps_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/red/T.png'))
            select_steps_action.triggered.connect(self.select_tasks)
            menu.addAction(select_steps_action)

            task_run_modes = {}

            for ifp_item in self.main_table_info_list:
                if len(ifp_item.RunModes) <= 1:
                    continue

                task_run_modes[ifp_item.Task] = ifp_item.RunModes

            if task_run_modes:
                select_mode_action = QMenu('Select Run Mode', self)
                select_mode_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/red/T.png'))

                for task, run_modes in task_run_modes.items():
                    task_menu = QMenu(task, self)
                    action_group = QActionGroup(task_menu)
                    action_group.setExclusive(True)

                    for run_mode in run_modes:
                        run_mode_action = QAction(run_mode, task_menu)
                        action_group.addAction(run_mode_action)
                        task_menu.addAction(run_mode_action)
                        run_mode_action.triggered.connect(functools.partial(self.select_task_run_mode, task, run_mode))

                    select_mode_action.addMenu(task_menu)

                menu.addMenu(select_mode_action)

        menu.exec_(self.main_table.mapToGlobal(pos))

    def select_task_run_mode(self, task, run_mode):
        t_list = []

        for i, ifp_item in enumerate(self.main_table_info_list):
            if ifp_item.Task != task:
                continue

            read_only = True if self.disable_gui_flag and ifp_item.Status == common.status.running else False

            if read_only:
                QMessageBox.warning(self, 'IFP Warning', 'Could not change Run Mode when task(s) is running!')
                return

            t_list.append(i)

        for i in t_list:
            self.main_table_info_list[i].RunMode = run_mode

        self.update_main_table()

    def show_version_flowchart(self, block: str, version: str):
        dependency_dic = self.task_window.dependency_priority[block][version]
        task_list = list(dependency_dic.keys())

        for task in dependency_dic.keys():
            dependency_dic[task] = WindowForDependency.clean_dependency(item_list=task_list, item=task, dependency=dependency_dic[task])

        self.flow_chart_window.gen_flow_graph(dependency_dic=dependency_dic, version=version, block=block)
        self.flow_chart_window.show()

    def show_flow_flowchart(self, block: str, version: str, flow: str):
        task_list = [task for task in self.config_dic['BLOCK'][block][version][flow]]
        dependency_dic = {task: self.task_window.dependency_priority[block][version][task] for task in self.task_window.dependency_priority[block][version] if task in task_list}

        for task in dependency_dic.keys():
            dependency_dic[task] = WindowForDependency.clean_dependency(item_list=task_list, item=task, dependency=dependency_dic[task])

        self.flow_chart_window.gen_flow_graph(dependency_dic=dependency_dic, version=version, block=block)
        self.flow_chart_window.show()

    def generate_menu(self, pos):
        select_items = []

        try:
            selection_model = self.main_table.selectionModel()
            selected_indexes = selection_model.selectedIndexes()
            processed_positions = set()

            for index in selected_indexes:
                row, col = index.row(), index.column()

                # Skip if already processed (for merged cells)
                if (row, col) in processed_positions:
                    continue

                item = self.main_table_model.item(row, col)
                if item:
                    select_items.append(item)

                    # Mark span area as processed
                    row_span = self.main_table.rowSpan(row, col)
                    col_span = self.main_table.columnSpan(row, col)

                    for r in range(row, row + row_span):
                        for c in range(col, col + col_span):
                            processed_positions.add((r, c))
        except Exception as error:
            print(error)
            print(traceback.format_exc())
            pass

        if len(select_items) == 0:
            return

        index_at_pos = self.main_table.indexAt(pos)

        if not index_at_pos.isValid():
            return

        # if len(select_items) == 0:
        #     return

        # if not self.main_table.itemAt(pos):
        #     return

        self.current_selected_column = selected_indexes[-1].column()
        self.current_selected_row = selected_indexes[-1].row()

        # cross-column selection is meaningless
        visible_row_list = []
        row_list = []
        """
        for item in select_items:
            if not item.column() == self.current_selected_column:
                return

            row_list.append(item.row())
        """

        for index in selected_indexes:
            if not index.column() == self.current_selected_column:
                return

            visible_row_list.append(index.row())

        menu = IgnoreRightButtonMenu()
        visible_row = -1
        self.memos_logger.log(f'Right Click Main Table -> Row List <{str(min(visible_row_list))} ~ {str(max(visible_row_list))}>, Column <{str(self.current_selected_column)}>')
        current_selected_row = -1

        visible_row_list = set(visible_row_list)

        for (row, main_table_info) in enumerate(self.main_table_info_list):
            if main_table_info['Visible'] and self.filt_task_status(main_table_info):
                visible_row += 1

                if visible_row in visible_row_list:
                    row_list.append(row)

                if visible_row == self.current_selected_row:
                    self.current_selected_task_dic = main_table_info
                    self.current_selected_task_obj = self.current_selected_task_dic['Task_obj']
                    current_selected_row = row

        # If only select one task
        if len(selected_indexes) == 1 and self.current_selected_column == 3:
            selected_task_obj = self.main_table_info_list[current_selected_row]['Task_obj']

            skip_action = QAction('Skip task', self)
            skip_action.setCheckable(True)
            skip_action.setChecked(self.current_selected_task_obj.skipped)
            skip_action.triggered.connect(lambda: self.set_task_as_skipped(selected_task_obj, self.current_selected_row, self.current_selected_column))
            menu.addAction(skip_action)

            if self.read_mode:
                skip_action.setEnabled(False)

            ignore_fail_action = QAction('Ignore fail', self)
            ignore_fail_action.setCheckable(True)
            ignore_fail_action.setChecked(self.current_selected_task_obj.ignore_fail)
            ignore_fail_action.triggered.connect(lambda: self.set_task_as_ignore_fail(selected_task_obj, self.current_selected_row, self.current_selected_column))
            menu.addAction(ignore_fail_action)

            if self.read_mode:
                ignore_fail_action.setEnabled(False)

            # Run Mode
            run_mode_list = self.current_selected_task_dic.RunModes

            if len(run_mode_list) > 1:
                choice_mode_menu = QMenu('Switch run mode (temporary)')
                action_group = QActionGroup(self)
                action_group.setExclusive(True)

                for run_mode in run_mode_list:
                    run_mode_action = QAction(run_mode, self)
                    run_mode_action.setCheckable(True)
                    run_mode_action.triggered.connect(functools.partial(self.switch_task_run_mode, ifp_item=self.current_selected_task_dic, run_mode=run_mode))

                    if self.read_mode:
                        run_mode_action.setEnabled(False)

                    action_group.addAction(run_mode_action)
                    choice_mode_menu.addAction(run_mode_action)
                    run_mode_name = 'RUN' if run_mode == 'default' else f'RUN.{run_mode}'

                    if run_mode_name == self.current_selected_task_dic.RunMode:
                        run_mode_action.setChecked(True)

                menu.addMenu(choice_mode_menu)

            action_menu = QMenu('Execute action alone')
            build_action = QAction(common.action.build)
            build_action.triggered.connect(lambda: self.execute_action(common.action.build, task_dic_list=[self.current_selected_task_dic, ], select_task=True))
            build_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/other/build.png'))
            action_menu.addAction(build_action)

            run_action = QAction(common.action.run)
            run_action.triggered.connect(lambda: self.execute_action(common.action.run, task_dic_list=[self.current_selected_task_dic, ], select_task=True))
            run_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/run.png'))
            action_menu.addAction(run_action)

            kill_action = QAction(common.action.kill)
            kill_action.triggered.connect(lambda: self.execute_action(common.action.kill, task_dic_list=[self.current_selected_task_dic, ], select_task=True))
            kill_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/kill.png'))
            action_menu.addAction(kill_action)

            check_action = QAction(common.action.check)
            check_action.triggered.connect(lambda: self.execute_action(common.action.check, task_dic_list=[self.current_selected_task_dic, ], select_task=True))
            check_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/checklist.png'))
            action_menu.addAction(check_action)

            summarize_action = QAction(common.action.summarize)
            summarize_action.triggered.connect(lambda: self.execute_action(common.action.summarize, task_dic_list=[self.current_selected_task_dic, ], select_task=True))
            summarize_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/summary.png'))
            action_menu.addAction(summarize_action)

            release_action = QAction(common.action.release)
            release_action.triggered.connect(lambda: self.execute_action(common.action.release, task_dic_list=[self.current_selected_task_dic, ], select_task=True))
            release_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/release.png'))
            action_menu.addAction(release_action)

            if self.read_mode:
                for action in action_menu.actions():
                    action.setEnabled(False)

            menu.addMenu(action_menu)

            menu.addSeparator()

            view_setting_action = QAction('Task information', self)

            status = self.main_table_model.item(self.current_selected_row, 4).text().strip()
            read_only = True if self.disable_gui_flag and status == common.status.running else False

            view_setting_action.triggered.connect(lambda: self.edit_detailed_config(read_only=read_only, block=self.current_selected_task_dic['Block'], version=self.current_selected_task_dic['Version'], flow=self.current_selected_task_dic['Flow'], task=self.current_selected_task_dic['Task']))
            menu.addAction(view_setting_action)

            open_file_action = QAction('Open file', self)
            open_file_action.triggered.connect(lambda: self.open_file(self.current_selected_task_dic))
            menu.addAction(open_file_action)

            self.generate_main_tab_api_menu(self.current_selected_column, self.current_selected_task_dic, menu)
        # If select one block/version
        elif len(selected_indexes) == 1 and self.current_selected_column < 3:
            self.generate_multiple_select_task_menu(self.current_selected_column, row_list, menu)
            self.generate_main_tab_api_menu(self.current_selected_column, self.current_selected_task_dic, menu)
        # If multiple select block/version/task
        elif len(selected_indexes) > 1 and self.current_selected_column <= 3:
            self.generate_multiple_select_task_menu(self.current_selected_column, row_list, menu)
            self.generate_main_tab_api_menu(self.current_selected_column, self.current_selected_task_dic, menu)

        self.memos_logger.setup_menu_memos(menu, 'Main Table Menu')
        menu.exec_(self.main_table.viewport().mapToGlobal(pos))

    def switch_task_run_mode(self, ifp_item: parse_config.IfpItem, run_mode: str):
        read_only = True if self.disable_gui_flag and ifp_item.Status == common.status.running else False

        if read_only:
            QMessageBox.warning(self, 'IFP Warning', 'Could not change Run Mode when task(s) is running!')
            return

        ifp_item.RunMode = run_mode
        self.update_main_table_item(ifp_item.Block, ifp_item.Version, ifp_item.Flow, ifp_item.Task, 'Task', ifp_item.Task, selected=ifp_item.Selected)

    def open_task_information(self, block: str, version: str, task: str):
        for flow in self.config_dic['BLOCK'].get(block, {}).get(version, {}):
            for c_task in self.config_dic['BLOCK'][block][version][flow]:
                if c_task == task:
                    self.edit_detailed_config(read_only=self.task_window.disable_gui_flag, block=block, version=version, flow=flow, task=task)
                    return

    def edit_detailed_config(self,
                             read_only=False,
                             block=None,
                             version=None,
                             flow=None,
                             task=None):
        self.task_window.current_selected_task = task
        self.task_window.current_selected_flow = flow
        self.task_window.current_selected_block = block
        self.task_window.current_selected_version = version
        self.task_information_show = True
        self.child = WindowForTaskInformation(task_obj=self.job_manager.all_tasks[block][version][flow][task], user_config_obj=self.task_window, read_only=read_only)
        self.child.detailed_task_window.message.connect(self.task_window.update_detailed_setting)
        self.child.show_sig.connect(self.change_task_information_show_status)
        self.setDisabled(True)
        self.child.show()

    def change_task_information_show_status(self, show_sig: bool):
        self.task_information_show = show_sig
        self.setDisabled(show_sig)

    def generate_multiple_select_task_menu(self, select_column, row_list, menu):
        select_task_action = QAction('Select All Task', self)
        select_task_action.triggered.connect(lambda: self.trigger_all_selected_task(select_column, row_list, True))
        menu.addAction(select_task_action)

        unselect_task_action = QAction('Unselect All Task', self)
        unselect_task_action.triggered.connect(lambda: self.trigger_all_selected_task(select_column, row_list, False))
        menu.addAction(unselect_task_action)

        # block = self.main_table.item(row_list[0], 0).text()
        # version = self.main_table.item(row_list[0], 1).text()
        # flow = self.main_table.item(row_list[0], 2).text()
        # block = self.main_table_model.item(row_list[0], 0).text()
        # version = self.main_table_model.item(row_list[0], 1).text()
        # flow = self.main_table_model.item(row_list[0], 2).text()
        block_index = self.main_table_model.index(row_list[0], 0)
        version_index = self.main_table_model.index(row_list[0], 1)
        flow_index = self.main_table_model.index(row_list[0], 2)
        block = self.main_table_model.data(block_index).strip()
        version = self.main_table_model.data(version_index).strip()
        flow = self.main_table_model.data(flow_index).strip()

        if select_column == 1:
            show_flow_chart_action = QAction('Show Flow Chart', self)
            show_flow_chart_action.triggered.connect(functools.partial(self.show_version_flowchart, block, version))
            menu.addAction(show_flow_chart_action)
        elif select_column == 2:
            show_flow_chart_action = QAction('Show Flow Chart', self)
            show_flow_chart_action.triggered.connect(functools.partial(self.show_flow_flowchart, block, version, flow))
            menu.addAction(show_flow_chart_action)

    def generate_main_tab_api_menu(self, selected_column, task_dic, menu):
        user_api = self.user_api
        project = self.ifp_env_setting['Project settings']['Project']['Project name']['value']
        group = self.ifp_env_setting['Project settings']['Project']['User group']['value']

        if selected_column == 0:
            common.add_api_menu(self, user_api, menu, project=project, group=group, tab='MAIN', column='BLOCK', var_dic={'BLOCK': task_dic['Block']})
        elif selected_column == 1:
            common.add_api_menu(self, user_api, menu, project=project, group=group, tab='MAIN', column='VERSION', var_dic={'BLOCK': task_dic['Block'], 'VERSION': task_dic['Version']})
        elif selected_column == 2:
            common.add_api_menu(self, user_api, menu, project=project, group=group, tab='MAIN', column='FLOW', var_dic={'BLOCK': task_dic['Block'], 'VERSION': task_dic['Version'], 'FLOW': task_dic['Flow']})
        elif selected_column == 3:
            common.add_api_menu(self, user_api, menu, project=project, group=group, tab='MAIN', column='TASK', var_dic={'BLOCK': task_dic['Block'], 'VERSION': task_dic['Version'], 'FLOW': task_dic['Flow'], 'TASK': task_dic['Task']})

    def set_task_as_skipped(self, task_obj, row, column):
        if task_obj.skipped:
            task_obj.skipped = False
            # self.main_table.itemFromIndex(self.main_table.model().index(row, column)).setForeground(QBrush(QColor(0, 0, 0)))
            self.main_table_model.itemFromIndex(self.main_table_model.index(row, column)).setForeground(QBrush(QColor(0, 0, 0)))

        else:
            task_obj.skipped = True
            # self.main_table.itemFromIndex(self.main_table.model().index(row, column)).setForeground(QBrush(QColor(211, 211, 211)))
            self.main_table_model.itemFromIndex(self.main_table_model.index(row, column)).setForeground(QBrush(QColor(211, 211, 211)))

    def set_task_as_ignore_fail(self, task_obj, row, column):
        if task_obj.ignore_fail:
            task_obj.ignore_fail = False
            # self.main_table.itemFromIndex(self.main_table.model().index(row, column + 1)).setIcon(QIcon())
            self.main_table_model.itemFromIndex(self.main_table_model.index(row, column + 1)).setIcon(QIcon())

            if self.ignore_fail:
                self.setting_window.ifp_env_setting['System settings']['Process management']['Ignore fail tasks']['widget'].setChecked(False)
                self.setting_window.ifp_env_setting['System settings']['Process management']['Ignore fail tasks']['value'] = False
                self.update_ifp_setting(self.setting_window.ifp_env_setting, need_reload_flag=False, ignore_fail_flag=False)
                self.update_config_tab_name(False, 'Setting')
        else:
            task_obj.ignore_fail = True
            self.main_table_model.itemFromIndex(self.main_table_model.index(row, column + 1)).setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/ignore_fail.png'))
            # self.main_table.itemFromIndex(self.main_table.model().index(row, column + 1)).setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/ignore_fail.png'))

    def trigger_all_selected_task(self, column, row_list, status):
        for row in row_list:
            self.update_select_item_status(row, status)

    def update_select_item_status(self, row, select_status):
        if select_status:
            status = Qt.Checked
            # self.update_message_text({'message': 'Row: %d task is selected.' % (row + 1), 'color': 'black'})
        else:
            status = Qt.Unchecked
            # self.update_message_text({'message': 'Row: %d task is unselected.' % (row + 1), 'color': 'black'})

        try:
            main_table_info = self.main_table_info_list[row]

            if not self.main_table.isRowHidden(row):
                self.update_main_table_item(main_table_info.Block, main_table_info.Version, main_table_info.Flow, main_table_info.Task, 'Task', main_table_info.Task, selected=status)
        except Exception:
            pass

    def update_main_table(self, mode='create'):
        """
        Draw Main TAB table.

        Args:
             mode: Default 'create', option 'update'|'create', for setting func update_main_table_item args - mode
        """
        # Initial, clean up self.main_table.
        # self.main_table.setModel(None)
        self.main_table.clearSpans()
        self.main_table_model.clear()
        # self.main_table_model.setColumnCount(len(self.main_table_title_list))
        self.main_table_model.setHorizontalHeaderLabels(self.main_table_title_list)

        # Set row count.
        row_count = 0

        for i, main_table_info in enumerate(self.main_table_info_list):
            if main_table_info['Visible'] and self.filt_task_status(main_table_info):
                row_count += 1

            if not main_table_info['Visible']:
                self.main_table_info_list[i]['Selected'] = False

        self.main_table_model.setRowCount(0)

        # Update content.
        row_dic = {'Block': {'current': '', 'last': '', 'start_row': 0, 'end_row': 0, 'column': 0},
                   'Version': {'current': '', 'last': '', 'start_row': 0, 'end_row': 0, 'column': 1},
                   'Flow': {'current': '', 'last': '', 'start_row': 0, 'end_row': 0, 'column': 2}}

        visible_row = -1
        # self.main_table_model.beginResetModel()
        self.main_table_info_list = self.config_obj.main_table_info_list

        for (row, main_table_info) in enumerate(self.main_table_info_list):
            if not main_table_info['Visible'] or not self.filt_task_status(main_table_info):
                continue

            visible_row += 1

            # Set main_table items.
            block = main_table_info['Block']
            version = main_table_info['Version']
            flow = main_table_info['Flow']
            task = main_table_info['Task']
            status = main_table_info['Status']
            buildstatus = main_table_info['BuildStatus']
            runstatus = main_table_info['RunStatus']
            checkstatus = main_table_info['CheckStatus']
            summarizestatus = main_table_info['SummarizeStatus']
            releasestatus = main_table_info['ReleaseStatus']
            check = True if not main_table_info['Check'] else main_table_info['Check']
            summary = True if not main_table_info['Summary'] else main_table_info['Check']
            job = main_table_info['Job']
            runtime = main_table_info['Runtime']
            xterm = main_table_info['Xterm']

            row_dic['Block']['current'] = block
            row_dic['Version']['current'] = version
            row_dic['Flow']['current'] = flow

            items = []

            items.append(self.update_main_table_item(block, version, flow, task, 'Block', block, flags=Qt.ItemIsSelectable | Qt.ItemIsEnabled, mode=mode, row=row, vrow=visible_row))
            items.append(self.update_main_table_item(block, version, flow, task, 'Version', version, flags=Qt.ItemIsSelectable | Qt.ItemIsEnabled, mode=mode, row=row, vrow=visible_row))
            items.append(self.update_main_table_item(block, version, flow, task, 'Flow', flow, flags=Qt.ItemIsSelectable | Qt.ItemIsEnabled, mode=mode, row=row, vrow=visible_row))

            if main_table_info['Selected']:
                items.append(self.update_main_table_item(block, version, flow, task, 'Task', task, selected=Qt.Checked, mode=mode, row=row, vrow=visible_row))
            else:
                items.append(self.update_main_table_item(block, version, flow, task, 'Task', task, selected=Qt.Unchecked, mode=mode, row=row, vrow=visible_row))

            items.append(self.update_main_table_item(block, version, flow, task, 'Status', status, flags=Qt.ItemIsSelectable | Qt.ItemIsEnabled, mode=mode, row=row, vrow=visible_row))

            if self.config_dic['BLOCK'][block][version][flow][task]['ACTION'].get(common.action.check.upper(), None) is None:
                items.append(self.update_main_table_item(block, version, flow, task, 'Check', None, mode=mode, row=row, vrow=visible_row))
            else:
                items.append(self.update_main_table_item(block, version, flow, task, 'Check', check, mode=mode, row=row, vrow=visible_row))

            if self.config_dic['BLOCK'][block][version][flow][task]['ACTION'].get(common.action.summarize.upper(), None) is None:
                items.append(self.update_main_table_item(block, version, flow, task, 'Summary', None, mode=mode, row=row, vrow=visible_row))
            else:
                items.append(self.update_main_table_item(block, version, flow, task, 'Summary', summary, mode=mode, row=row, vrow=visible_row))

            items.append(self.update_main_table_item(block, version, flow, task, 'Job', job, flags=Qt.ItemIsSelectable | Qt.ItemIsEnabled, mode=mode, row=row, vrow=visible_row))
            items.append(self.update_main_table_item(block, version, flow, task, 'Runtime', runtime, flags=Qt.ItemIsSelectable | Qt.ItemIsEnabled, mode=mode, row=row, vrow=visible_row))
            items.append(self.update_main_table_item(block, version, flow, task, 'Xterm', xterm, mode=mode, row=row, vrow=visible_row))

            items.append(self.update_main_table_item(block, version, flow, task, 'BuildStatus', buildstatus, flags=Qt.ItemIsSelectable | Qt.ItemIsEnabled, mode=mode, row=row, vrow=visible_row))
            items.append(self.update_main_table_item(block, version, flow, task, 'RunStatus', runstatus, flags=Qt.ItemIsSelectable | Qt.ItemIsEnabled, mode=mode, row=row, vrow=visible_row))
            items.append(self.update_main_table_item(block, version, flow, task, 'CheckStatus', checkstatus, flags=Qt.ItemIsSelectable | Qt.ItemIsEnabled, mode=mode, row=row, vrow=visible_row))
            items.append(self.update_main_table_item(block, version, flow, task, 'SummarizeStatus', summarizestatus, flags=Qt.ItemIsSelectable | Qt.ItemIsEnabled, mode=mode, row=row, vrow=visible_row))
            items.append(self.update_main_table_item(block, version, flow, task, 'ReleaseStatus', releasestatus, flags=Qt.ItemIsSelectable | Qt.ItemIsEnabled, mode=mode, row=row, vrow=visible_row))
            self.main_table_model.appendRow(items)

            # Merge Block/Version/Flow/ items.
            key_list = list(row_dic.keys())
            merge_mark = False

            for (index, key) in enumerate(key_list):
                if index == 0:
                    merge_mark = False

                if row_dic[key]['current'] == row_dic[key]['last']:
                    row_dic[key]['end_row'] = visible_row
                else:
                    for sub_index in range(index, len(key_list)):
                        sub_key = key_list[sub_index]
                        row_dic[sub_key]['start_row'] = row_dic[sub_key]['end_row'] = visible_row

                if merge_mark or (row_dic[key]['end_row'] > row_dic[key]['start_row']) or (visible_row == row_count - 1):
                    if row_dic[key]['end_row'] > row_dic[key]['start_row']:
                        self.main_table.setSpan(row_dic[key]['start_row'], row_dic[key]['column'], row_dic[key]['end_row'] - row_dic[key]['start_row'] + 1, 1)
                        merge_mark = True
                else:
                    merge_mark = False

                row_dic[key]['last'] = row_dic[key]['current']

            # remark = self.main_table.item(row, 15).text() if self.main_table.item(row, 15) is not None else ''
            # remark_item = QTableWidgetItem(remark)
            # remark_item.setFlags(remark_item.flags() | Qt.ItemIsEditable)
            # self.main_table.setItem(row, 15, remark_item)
        # self.main_table_model.insertRows(0, row_count, items_list)
        # self.main_table.setModel(self.main_table_model)

        self.hide_detail_status()
        self.resize_table_column()
        self.filter_row.apply_filter()

        try:
            for column in self.view_status_dic['column']:
                if column not in self.header_column_mapping:
                    continue

                if not self.view_status_dic['column'][column]:
                    self.main_table.hideColumn(self.header_column_mapping[column])
        except Exception:
            pass

    def filt_task_status(self, main_table_info):
        status = self.status_filt_flag
        row_status = main_table_info["RunStatus"]

        check_status = main_table_info['CheckStatus']

        if check_status in [common.status.checking, common.status.passed, common.status.failed] and row_status != common.status.running:
            row_status = check_status

        if status == "" or status == "Total" or (status == "Run" and row_status == common.status.running) or (status == "Passed" and row_status == common.status.passed) or (status == "Failed" and row_status == common.status.failed) or (
                status == "Others" and row_status != common.status.running and row_status != common.status.passed and row_status != common.status.failed):
            return 1
        else:
            return 0

    def resize_table_column(self):
        self.main_table.resizeColumnsToContents()

        for i in range(self.main_table_model.columnCount()):
            self.main_table.horizontalHeader().setSectionResizeMode(i, QHeaderView.Interactive)

        self.main_table.setColumnWidth(4, 140)
        self.main_table.setColumnWidth(5, 50)
        self.main_table.setColumnWidth(6, 70)
        self.main_table.setColumnWidth(7, 70)
        self.main_table.setColumnWidth(8, 70)
        self.main_table.setColumnWidth(9, 50)
        self.main_table.resizeColumnToContents(0)
        self.main_table.resizeColumnToContents(1)
        self.main_table.resizeColumnToContents(2)
        self.main_table.resizeColumnToContents(3)
        # self.main_table.horizontalHeader().setSectionResizeMode(15, QHeaderView.Stretch)

        # self.main_table.model().layoutChanged.emit()

        current_width = self.main_table.columnWidth(3)
        self.main_table.setColumnWidth(3, current_width + 15)

        total_column_width = sum([self.main_table.columnWidth(i) for i in range(self.main_table_model.columnCount())])

        if self.main_table.verticalScrollBar().isVisible():
            table_width = self.main_table.width() - self.main_table.verticalHeader().width() - self.main_table.verticalScrollBar().width() - 2
        else:
            table_width = self.main_table.width() - self.main_table.verticalHeader().width() - 2
        resize_column = abs(total_column_width - table_width)
        resize_total_column_width = sum([self.main_table.columnWidth(i) for i in [0, 1, 2, 3]])

        if resize_total_column_width == 0:
            return

        if total_column_width > table_width:
            for i in [0, 1, 2, 3]:
                self.main_table.setColumnWidth(i, self.main_table.columnWidth(i) - int((self.main_table.columnWidth(i) / resize_total_column_width) * resize_column))
        elif total_column_width < table_width:
            for i in [0, 1, 2, 3]:
                self.main_table.setColumnWidth(i, self.main_table.columnWidth(i) + int((self.main_table.columnWidth(i) / resize_total_column_width) * resize_column))

    def update_main_table_item(self, block, version, flow, task, key, value, color=None, selected=None, flags=None, mode='update', row=None, vrow=None):
        """
        mode 'create' for draw Main TAB table totally, create only.
        mode 'update' for update Main TAB table, modify Main table item.
        """
        task_obj = self.job_manager.all_tasks[block][version][flow][task]
        row_info_list = ['Block', 'Version', 'Flow', 'Task', 'Status', 'Check', 'Summary', 'Job', 'Runtime', 'Xterm', 'BuildStatus', 'RunStatus', 'CheckStatus', 'SummarizeStatus', 'ReleaseStatus']
        # visible_row = -1

        if 'Status' in key and value:
            filtered_value = value.split('(')[0]
        else:
            filtered_value = value

        if mode == 'create' and row is not None and vrow is not None:
            self.main_table_info_list[row][key] = filtered_value

            if selected:
                self.main_table_info_list[row]['Selected'] = True
            else:
                if selected is not None:
                    self.main_table_info_list[row]['Selected'] = False

            item = self.generate_main_table_item(vrow, row, task_obj, row_info_list, key, value, color, selected, flags, mode)
            return item
        """
        for (row, main_table_info) in enumerate(self.main_table_info_list):
            if main_table_info['Visible'] and self.filt_task_status(main_table_info):
                visible_row += 1

            if (block == main_table_info['Block']) and (version == main_table_info['Version']) and (flow == main_table_info['Flow']) and (task == main_table_info['Task']):
                # Update self.main_table_info_list.
                self.main_table_info_list[row][key] = filtered_value

                if selected:
                    self.main_table_info_list[row]['Selected'] = True
                else:
                    if selected is not None:
                        self.main_table_info_list[row]['Selected'] = False

                # Update self.main_table.
                if main_table_info['Visible'] and self.filt_task_status(main_table_info):
                    self.generate_main_table_item(visible_row, row, task_obj, row_info_list, key, value, color, selected, flags)
        """
        uuid = common.generate_uuid_from_components(item_list=[block, version, flow, task])
        main_table_info = self.config_obj.main_table_item_dic[uuid]
        visible_row = main_table_info.visible_index
        row = main_table_info.index

        self.main_table_info_list[row][key] = filtered_value

        if selected:
            self.main_table_info_list[row]['Selected'] = True
        else:
            if selected is not None:
                self.main_table_info_list[row]['Selected'] = False

        if main_table_info['Visible'] and self.filt_task_status(main_table_info):
            self.generate_main_table_item(visible_row, row, task_obj, row_info_list, key, value, color, selected, flags)

    def generate_main_table_item(self, visible_row, row, task_obj, row_info_list, key, value, color=None, selected=None, flags=None, mode: str = 'update'):
        if (key != 'Check') and (key != 'Summary') and (key != 'Xterm'):
            # index = self.main_table_model.index(visible_row, row_info_list.index(key))
            # self.main_table_model.setData(index, value, Qt.DisplayRole)

            # item = QTableWidgetItem(value)
            item = QStandardItem()
            item.setData(value, Qt.DisplayRole)

            if 'Status' in key and not color:
                color = self.mapping_status_color(str(value))

            if 'Status' in key and color:
                # self.main_table_model.setData(index, QBrush(color), Qt.ForegroundRole)
                item.setForeground(QBrush(color))

            if selected:
                item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Checked)
            else:
                if selected is not None:
                    item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
                    item.setCheckState(Qt.Unchecked)
            # if selected is not None:
            #     self.main_table_model.setData(index, Qt.Checked if selected else Qt.Unchecked, Qt.CheckStateRole)

            if flags:
                item.setFlags(flags)

            if key == 'Status':
                if task_obj.ignore_fail:
                    icon = self.ignore_fail_icon
                    item.setIcon(icon)
                    # self.main_table_model.setData(index, icon, Qt.DecorationRole)

            if key == 'Task' and task_obj.skipped:
                # self.main_table_model.setData(index, QBrush(QColor(211, 211, 211)), Qt.ForegroundRole)
                item.setForeground(QBrush(QColor(211, 211, 211)))

            if key == 'Task':
                task_config_obj = self.config_obj.get_task(task_obj.block, task_obj.version, task_obj.flow, task_obj.task)
                run_mode_list = task_config_obj.RunInfo.keys()

                if len(run_mode_list) > 1:
                    item.setToolTip(f'Current Run Mode: {task_config_obj.RunMode}')
                    # tooltip = f'Current Run Mode: {task_config_obj.RunMode}'
                    # self.main_table_model.setData(index, tooltip, Qt.ToolTipRole)

                    if task_config_obj.OriRunMode != task_config_obj.RunMode:
                        icon_index = self.get_run_mode_index(lst=run_mode_list, remove_value=task_config_obj.OriRunMode, find_value=task_config_obj.RunMode)
                        # icon = QIcon(str(os.environ['IFP_INSTALL_PATH']) + f'/data/pictures/office/changed_{str(icon_index)}.png')
                        item.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + f'/data/pictures/office/changed_{str(icon_index)}.png'))
                    else:
                        # icon = QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/unchanged.png')
                        item.setIcon(self.run_mode_unchange_icon)

                    # self.main_table_model.setData(index, icon, Qt.DecorationRole)
                    # item.setIcon(icon)

            if mode == 'update':
                self.main_table_model.setItem(visible_row, row_info_list.index(key), item)

        if (key == 'Check') or (key == 'Summary') or (key == 'Xterm'):
            # item = QTableWidgetItem(None)
            item = QStandardItem(None)
            # icon = None

            if key == 'Check':
                if value is None:
                    # icon = QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/check_undefined.png')
                    item.setIcon(self.check_undefined_icon)
                elif value == common.status.passed:
                    # icon = QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/check_pass.png')
                    item.setIcon(self.check_pass_icon)
                elif value == common.status.failed:
                    # icon = QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/check_fail.png')
                    item.setIcon(self.check_fail_icon)
                else:
                    # icon = QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/check_init.png')
                    item.setIcon(self.check_init_icon)

            if key == 'Summary':
                if value is None:
                    # icon = QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/summary_undefined.png')
                    item.setIcon(self.summary_undefined_icon)
                elif value == common.status.passed:
                    # icon = QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/summary_pass.png')
                    item.setIcon(self.summary_pass_icon)
                elif value == common.status.failed:
                    # icon = QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/summary_fail.png')
                    item.setIcon(self.summary_fail_icon)
                else:
                    # icon = QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/summary_init.png')
                    item.setIcon(self.summary_init_icon)

            if key == 'Xterm':
                # icon = QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/other/terminal.png')
                item.setIcon(self.terminal_icon)

            item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            item.setTextAlignment(Qt.AlignCenter)
            # self.main_table_model.setItem(visible_row, row_info_list.index(key), item)
            # index = self.main_table_model.index(visible_row, row_info_list.index(key))

            # if icon is not None:
            #     item.setIcon(icon)
            #     # self.main_table_model.setData(index, icon, Qt.DecorationRole)

            # self.main_table_model.setData(index, Qt.AlignCenter, Qt.TextAlignmentRole)

            if mode == 'update':
                self.main_table_model.setItem(visible_row, row_info_list.index(key), item)

        if (key == 'Job') and value:
            # item = QTableWidgetItem(None)
            item = QStandardItem(None)
            text = None

            if value.startswith('b'):
                text = value[2:]
                item.setData(value[2:], Qt.DisplayRole)
                # item = QStandardItem(value[2:])
                # item = QTableWidgetItem(value[2:])

            if value.startswith('l'):
                text = None
                item = QStandardItem(None)
                # item = QTableWidgetItem(None)

            if text is not None:
                pass
                # index = self.main_table_model.index(visible_row, row_info_list.index(key))
                # self.main_table_model.setData(index, text)

            if mode == 'update':
                self.main_table_model.setItem(visible_row, row_info_list.index(key), item)

        return item

    @staticmethod
    def get_run_mode_index(lst: List[str], remove_value: str, find_value: str) -> int:
        filtered_list = [item for item in lst if item != remove_value]

        try:
            position = filtered_list.index(find_value)
            return position % 4
        except ValueError:
            return 0

    @staticmethod
    def mapping_status_color(status):
        color = None

        if re.search(r'pass', str(status), flags=re.I):
            color = QColor(0, 204, 68)
        elif re.search(r'fail', str(status), flags=re.I):
            color = QColor(255, 0, 0)
        elif re.search(r'undefined', str(status), flags=re.I):
            color = QColor(133, 51, 255)
        elif re.search(r'ing', str(status), flags=re.I):
            color = QColor(255, 153, 0)
        elif re.search(r'queue', str(status), flags=re.I):
            color = QColor(51, 153, 255)
        elif re.search(r'kill', str(status), flags=re.I):
            color = QColor(255, 0, 0)
        elif re.search(r'skip', str(status), flags=re.I):
            color = QColor(211, 211, 211)

        return color

    # main_frame (end) #

    # message_frame (start) #
    def gen_message_frame(self):
        # self.message_text = QTextEdit(self.message_frame)
        self.message_text = common_pyqt5.BatchMessageBox(self.message_frame)
        self.message_text.setReadOnly(True)
        self.message_text.setAcceptRichText(True)

        # Grid
        message_frame_grid = QGridLayout()
        message_frame_grid.addWidget(self.status_table, 0, 0, 1, 1)
        message_frame_grid.addWidget(self.message_text, 0, 1, 1, 2)

        message_frame_grid.setColumnStretch(0, 1)
        message_frame_grid.setColumnStretch(1, 6)

        self.message_frame.setLayout(message_frame_grid)
        self.update_message_text({'message': 'Welcome to IC Flow Platform', 'color': 'black'})

    def update_message_text(self, info_dic):
        """
        color support string like blue, Blue, BLUE ...
        if could not identify color string , will print a warning message on terminal and using default color: block
        for example, color could be yellow, green, blue, orange, brown, and etc ...
        """
        if 'message' not in info_dic:
            return

        common_pyqt5.text_edit_visible_position(self.message_text, 'End')
        message = info_dic['message']
        color = info_dic['color'] if 'color' in info_dic else 'black'
        html = info_dic['html'] if 'html' in info_dic else False
        current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        if html:
            self.message_text.insertHtml('[' + str(current_time) + ']&nbsp;&nbsp;&nbsp;&nbsp;' + str(message) + '<br>')
        else:
            # default color: black
            (red, green, blue) = (0, 0, 0)

            if color:
                color = color.lower()

                try:
                    (red, green, blue) = (int(c * 255) for c in colors.to_rgb(color))
                except ValueError:
                    common.print_warning('*Warning*: ValueError ' + color)

            color = QColor(red, green, blue)
            color_format = self.message_text.currentCharFormat()
            color_format.setForeground(color)
            self.message_text.setCurrentCharFormat(color_format)

            self.message_text.insertPlainText('[' + str(current_time) + ']    ' + str(message) + '\n')

        common_pyqt5.text_edit_visible_position(self.message_text, 'End')

    # message_frame (end) #
    # main_tab (end) #
    # GUI (end) #
    @staticmethod
    def write_system_log(message):
        if not install_config.system_log_path == '':
            if not os.path.exists(install_config.system_log_path):
                common.run_command('touch %s' % install_config.system_log_path)
                os.chmod(install_config.system_log_path, 0o0777)

            time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            user = USER
            host = os.popen('hostname').read().strip()

            with open(install_config.system_log_path, 'a') as f:
                f.write('[%s][%s@%s]: %s\n' % (time, user, host, message))

    # execute_action (start)
    def execute_action(self, action_name, task_dic_list=None, run_all_steps=False, select_task=False):
        if action_name == common.TaskAction().run or run_all_steps:
            self.makefile_func()

        if task_dic_list is None:
            task_dic_list = []

        if not task_dic_list:
            table_row = 0

            for row, task_info_dic in enumerate(self.main_table_info_list):
                if task_info_dic['Visible']:
                    table_row += 1

                    if not self.main_table.isRowHidden(table_row - 1) and task_info_dic['Selected']:
                        task_dic_list.append(task_info_dic)

            if not self.auto_execute_action:
                task_dic_list = self.filter_task_before_execute_action(action_name, task_dic_list)

        if not task_dic_list:
            return

        if select_task:
            self.current_selected_task_dic['Selected'] = True
            self.update_main_table_item(self.current_selected_task_dic['Block'], self.current_selected_task_dic['Version'], self.current_selected_task_dic['Flow'], self.current_selected_task_dic['Task'], 'Task', self.current_selected_task_dic['Task'], selected=Qt.Checked)

        self.job_manager.receive_action(action_name, task_dic_list, run_all_steps=run_all_steps)

    def makefile_func(self):
        # Check Makefile Mode
        if not self.makefile_mode:
            return

        paths_dic = {}
        message_dic = {}

        # Discover Paths
        if self.config_obj.block_dic:
            # Discover Path
            for block in self.config_obj.block_dic.values():
                paths_dic.setdefault(block.NAME, {})
                message_dic.setdefault(block.NAME, {})

                if block.VERSION:
                    for version in block.VERSION.values():
                        paths_dic[block.NAME].setdefault(version.NAME, [])
                        message_dic[block.NAME].setdefault(version.NAME, [])
                        task_objs = []

                        # Get Selected Tasks
                        if version.FLOW:
                            for flow in version.FLOW.values():
                                if flow.TASK:
                                    for task in flow.TASK.values():
                                        task_objs.append(task)

                        path = WindowForDependency.discover_path(block=block.NAME,
                                                                 version=version.NAME,
                                                                 dependency=self.config_obj.real_task_dependency,
                                                                 task_list=[task.NAME for task in task_objs if task.Selected])

                        for task in task_objs:
                            if task.NAME in path and not task.Selected:
                                message_dic[block.NAME][version.NAME].append(task.NAME)

        unselected_tasks = []

        for block_name in message_dic:
            for version_name in message_dic[block_name]:
                unselected_tasks += message_dic[block_name][version_name]

        if len(unselected_tasks) == 0:
            return

        # MessageBox
        message_box = QMessageBox(self)
        message_box.setWindowTitle("Makefile Mode")
        message_box.setIcon(QMessageBox.Question)
        message_box.setText("""
<p>Automatically select following task:</p>
{}
""".format(''.join('<p><b>Block</b>: {} <b>Version</b>: {}</p><p><b>Task</b>: {}</p>'.format(block, version, ' '.join(message_dic[block][version])) for block in message_dic for version in message_dic[block] if message_dic[block][version])))
        message_box.setTextFormat(Qt.RichText)
        select_button = message_box.addButton('Confirm Selection', QMessageBox.YesRole)
        message_box.addButton('Skip Selection', QMessageBox.NoRole)
        message_box.exec_()

        if message_box.clickedButton() == select_button:
            for i, main_table_info_item in enumerate(self.main_table_info_list):
                block = main_table_info_item['Block']
                version = main_table_info_item['Version']
                task = main_table_info_item['Task']

                if task in message_dic[block][version]:
                    self.main_table_info_list[i].Selected = True

            self.update_main_table()
        else:
            return

    def filter_task_before_execute_action(self, action_name, task_dic_list):
        filtered_task_dic_list = []

        if action_name in [common.action.run, common.action.build]:
            if self.rerun_flag:
                filtered_task_dic_list = self.check_rerun_item(task_dic_list, action_name)
            else:
                filtered_task_dic_list = task_dic_list

            # Write system log
            flow_list = []
            for task_dic in filtered_task_dic_list:
                flow_info = "%s-%s-%s" % (task_dic['Block'], task_dic['Version'], task_dic['Flow'])
                if flow_info not in flow_list:
                    flow_list.append(flow_info)
                    self.write_system_log("run flow %s" % flow_info)
        elif action_name in [common.action.build, common.action.release, common.action.check, common.action.check_view, common.action.summarize, common.action.summarize_view]:
            for task in task_dic_list:
                if task['Status']:
                    if not re.match('.+ing$', task['Status'], re.I) and task['Status'] != common.status.queued:
                        filtered_task_dic_list.append(task)
                    else:
                        self.update_message_text({'message': '*Warning*: Can\'t execute {} action to {} {} {} {} because it\'s {}.'.format(action_name, task['Block'], task['Version'], task['Flow'], task['Task'], task['Status']), 'color': 'orange'})
                else:
                    filtered_task_dic_list.append(task)
        elif action_name == "Kill":
            for task in task_dic_list:
                filtered_task_dic_list.append(task)

        return filtered_task_dic_list

    def execute_action_after_launch_ifp(self):
        if self.auto_execute_action:
            for main_table_info in self.main_table_info_list:
                self.update_main_table_item(main_table_info['Block'], main_table_info['Version'], main_table_info['Flow'], main_table_info['Task'], 'Task', main_table_info['Task'], selected=Qt.Checked)

            if self.auto_execute_action == 'run':
                self.execute_action(common.action.run)

    def check_rerun_item(self, task_dic_list, action_name):
        # Checks whether any tasks has RUN PASS
        rerun_task_dic_list = []
        normal_task_dic_list = []
        warning_text = "Below tasks have run/check pass before: \n"

        for task in task_dic_list:
            if (task["CheckStatus"] == common.status.passed) or (task['CheckStatus'] != common.status.failed and task['RunStatus'] == common.status.passed):
                rerun_task_dic_list.append(task)
                if len(rerun_task_dic_list) <= 3:
                    warning_text = warning_text + "Block: " + task["Block"] + " Version: " + task["Version"] + " Task: " + task["Task"] + "\n"
            else:
                normal_task_dic_list.append(task)

        if len(rerun_task_dic_list) > 3:
            warning_text = warning_text + "...\n"

        warning_text = warning_text + "\nSure to " + action_name + " these tasks?"

        if len(rerun_task_dic_list) > 0:
            message_box = QMessageBox(self)
            message_box.setWindowTitle("Rerun Tasks?")
            message_box.setIcon(QMessageBox.Question)
            message_box.setText(warning_text)
            checkbox = QCheckBox("Don't show this message again. (Run all selected tasks)")
            checkbox.setChecked(False)
            message_box.setCheckBox(checkbox)
            message_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
            choice = message_box.exec_()
            check = message_box.checkBox()

            if check.isChecked():
                self.setting_window.ifp_env_setting['System settings']['Process management']['Confirm rerun tasks']['widget'].setChecked(False)
                self.setting_window.save()

            if choice == QMessageBox.Cancel:
                task_dic_list = []
            elif choice == QMessageBox.No:
                task_dic_list = normal_task_dic_list

        return task_dic_list

    def update_task_status(self, task_obj, action, status):
        if status == common.status.cancelled:
            action = common.action.run

        block, version, flow, task = task_obj.block, task_obj.version, task_obj.flow, task_obj.task
        self.config_dic['BLOCK'][block][version][flow][task].Status = status
        self.update_main_table_item(block, version, flow, task, 'Status', status)

        if re.match(r'(\S+)\s+(\S+)', status, flags=re.I):
            status_value = re.match(r'(\S+)\s+(\S+)', status, flags=re.I).group(2)
        else:
            status_value = status

        if action == common.action.build:
            self.update_main_table_item(block, version, flow, task, 'BuildStatus', status_value)
        elif action == common.action.run:
            self.update_main_table_item(block, version, flow, task, 'RunStatus', status_value)
        elif action == common.action.check:
            self.update_main_table_item(block, version, flow, task, 'CheckStatus', status_value)
            self.update_main_table_item(block, version, flow, task, 'Check', status_value)
        elif action == common.action.summarize:
            self.update_main_table_item(block, version, flow, task, 'SummarizeStatus', status_value)
            self.update_main_table_item(block, version, flow, task, 'Summary', status_value)
        elif action == common.action.release:
            self.update_main_table_item(block, version, flow, task, 'ReleaseStatus', status_value)

        self.update_status_table()

    def send_result_to_user(self, block, version, flow, task, action):
        if self.send_result and self.send_result_command:
            result_report = self.gen_result_report(block=block, version=version, flow=flow, task=task, action=action)

            send_result_command = re.sub('USER', USER, self.send_result_command)
            send_result_command = re.sub('RESULT', result_report, send_result_command)
            send_result_command = re.sub('TITLE', '"[FAIL] IC Flow Platform"', send_result_command)
            send_result_command = re.sub('HEADER_COLOR', 'red', send_result_command)
            os.system(send_result_command)
            os.system(f'rm {result_report}')

    @staticmethod
    def gen_result_report(**kwargs):
        current_time = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        result_report = str(CWD) + '/.result.' + str(current_time) + '.report'

        with open(result_report, 'w') as RR:
            RR.write(f"{kwargs['block']} -> {kwargs['version']} -> {kwargs['flow']} -> {kwargs['task']} {kwargs['action']} failed!\n")
            RR.write('Directory : ' + str(CWD) + '\n')

        return result_report

    def final_close(self):
        self.close_dialog.close()
        self.full_flowchart_window.close()
        self.close()

    def update_runtime(self):
        """
        Update runtime in main table per second
        """
        self.timer.stop()

        for main_table_info in self.main_table_info_list:
            block = main_table_info['Block']
            version = main_table_info['Version']
            flow = main_table_info['Flow']
            task = main_table_info['Task']
            status = main_table_info['Status']
            runtime = main_table_info['Runtime']

            if status == common.status.running and runtime and runtime != "pending":
                hour, minute, second = map(int, runtime.split(':'))
                second += 1

                if second == 60:
                    second = 0
                    minute += 1

                    if minute == 60:
                        minute = 0
                        hour += 1

                self.update_main_table_item(block, version, flow, task, 'Runtime', '%02d:%02d:%02d' % (hour, minute, second))
            elif (status == common.status.killing or status == common.status.killed) and runtime == "pending":
                self.update_main_table_item(block, version, flow, task, 'Runtime', "00:00:00")

        self.timer.start(1000)
        self.update_select_count()
        # self.record_count = 0
        # print(self.update_main_table_item.get_count() - self.record_count)

    def show_or_hide_detail_status(self):
        action = self.sender()

        if action.isChecked():
            self.show_detail_status()
        else:
            self.hide_detail_status()

        self.resize_table_column()

    def show_detail_status(self):
        self.view_disable_item_list = self.operation_title_list

        for column in self.main_table_title_list:
            if column in self.operation_title_list:
                self.main_table.hideColumn(self.header_column_mapping[column])
                self.view_detail_column_dic[column] = self.view_status_dic['column'][column]

        for title in self.status_title_list:
            self.main_table.showColumn(self.header_column_mapping[title])

    def hide_detail_status(self):
        self.view_disable_item_list = []

        for column in self.main_table_title_list:
            if column in self.operation_title_list:

                if self.view_detail_column_dic[column]:
                    self.main_table.showColumn(self.header_column_mapping[column])
                    self.view_status_dic['column'][column] = self.view_detail_column_dic[column]

        for title in self.status_title_list:
            self.main_table.hideColumn(self.header_column_mapping[title])

    def run_monitor(self, command, jobid):
        message = 'Monitor for ' + jobid + ' is already running.'

        if jobid in self.monitor_list:
            QMessageBox.warning(self, 'LSF Monitor Warning', message)
            return

        self.monitor_list.append(jobid)

        process = QProcess(self)
        process.setProperty("jobid", jobid)
        process.finished.connect(self.monitor_finished)
        process.errorOccurred.connect(self.monitor_error)
        process.start(command)

    def monitor_finished(self, exitCode, exitStatus):
        if exitCode != 0:
            QMessageBox.warning(self, 'LSF Monitor Warning', 'LSFMonitor start unsuccessfully.')

        jobid = self.sender().property('jobid')
        self.monitor_list.remove(jobid)

    def monitor_error(self, error):
        QMessageBox.warning(self, 'LSF Monitor Warning', 'LSFMonitor start unsuccessfully.')
        jobid = self.sender().property('jobid')
        self.monitor_list.remove(jobid)

    # execute_action (end)

    def save_default_yaml(self, default_yaml=''):
        """
        Save the current Task, Var and Dependency configurations as default yaml
        """
        # Check if have exactly one block/version
        if not self.save_default_yaml_validity():
            QMessageBox.warning(self, 'Can\'t save.', 'Please ensure there is exactly one block/version.')
            return

        # Check if var_window and dependency window have been saved
        if self.var_window.save_button.isEnabled() or self.dependency_window.save_button.isEnabled():
            QMessageBox.warning(self, 'Can\'t save.', 'Please save changes in Variable/Dependency config tab.')
            return

        # User select files to dump
        if not default_yaml:
            (default_yaml, file_type) = QFileDialog.getSaveFileName(self, 'Save default yaml', './default.yaml', 'YAML (*.yaml)')

        if default_yaml:
            self.update_message_text({'message': 'Save default yaml into file "' + str(default_yaml) + '".', 'color': 'black'})
            # convert current configuration to a dic
            yaml_dic = self.gen_default_yaml_dic()

            # dump to local file
            with open(default_yaml, 'w') as f:
                f.write(yaml.dump(yaml_dic, allow_unicode=True, sort_keys=False))

            QMessageBox.information(self, 'Done', 'Successfully save default yaml to %s.' % default_yaml)

    def save_default_yaml_validity(self):
        '''
        Check if have exactly one block/version
        Block/Version of each row must be the same with first row
        '''
        model = self.task_window.setup_model
        row_count = model.rowCount()

        if row_count == 0:
            return False

        block = model.item(0, 0).text()
        version = model.item(0, 1).text()

        for row in range(row_count):
            block_row = model.item(row, 0).text()
            version_row = model.item(row, 1).text()

            if block_row != block or version_row != version:
                return False

        return True

    def gen_default_yaml_dic(self):
        """
        Get data from config tabs and generate a dic for default yaml
        """
        var_dic = self.var_window.return_table_dic()
        task_dic = {}
        flow_dic = {}

        for block in self.config_dic['BLOCK']:
            for version in self.config_dic['BLOCK'][block]:
                for flow in self.config_dic['BLOCK'][block][version]:
                    flow_dic.setdefault(flow, [])
                    for task in self.config_dic['BLOCK'][block][version][flow]:
                        flow_dic[flow].append(task)
                        task_dic[task] = self.config_dic['BLOCK'][block][version][flow][task].get('ACTION', {})
                        task_dic[task]['RUN_AFTER'] = self.config_dic['BLOCK'][block][version][flow][task].get('RUN_AFTER', {})
                        task_dic[task]['DEPENDENCY'] = self.config_dic['BLOCK'][block][version][flow][task].get('DEPENDENCY', {})

        task_list = list(task_dic.keys())

        for task in task_dic.keys():
            task_dic[task]['RUN_AFTER']['TASK'] = WindowForDependency.clean_dependency(item_list=task_list, item=task, dependency=task_dic[task].get('RUN_AFTER', {}).get('TASK', ''))

        yaml_dic = {'VAR': var_dic,
                    'TASK': task_dic,
                    'FLOW': flow_dic}

        return yaml_dic

    def save_api_yaml(self, api_yaml=''):
        """
        Save the current API configurations as api yaml
        """
        # API tab must be saved before dump
        if self.api_window.save_button.isEnabled():
            QMessageBox.Warning(self, 'Can\'t save.', 'You have unsaved changes in API configuration tab.')
            return

        # User select file to dump
        if not api_yaml:
            (api_yaml, file_type) = QFileDialog.getSaveFileName(self, 'Save api yaml', './api.yaml', 'YAML (*.yaml)')

        if api_yaml:
            self.update_message_text({'message': 'Save api yaml into file "' + str(api_yaml) + '".', 'color': 'black'})
            # call save interface in self.api_window
            self.api_window.save(api_yaml)

            QMessageBox.information(self, 'Done', 'Successfully save api yaml to %s.' % api_yaml)


class MultipleSelectWindow(QDialog):
    """
    Select multiple choices.
    """
    item_select_status_signal = pyqtSignal(str, bool)

    def __init__(self, title, item_list):
        super(MultipleSelectWindow, self).__init__()
        self.gen_gui(title, item_list)

    def gen_gui(self, title, item_list):
        # Generate QCheckBox.
        self.checkbox_dic = {}

        for item in item_list:
            self.checkbox_dic[item] = QCheckBox(item)
            self.checkbox_dic[item].stateChanged.connect(self.update_main_gui)

        # Grid
        main_tab_layout = QVBoxLayout()

        for checkbox in self.checkbox_dic.values():
            main_tab_layout.addWidget(checkbox)

        self.setLayout(main_tab_layout)

        # Set GUI size and title.
        self.resize(180, 40 * len(item_list))
        self.setWindowTitle(title)
        common_pyqt5.center_window(self)

    def update_main_gui(self):
        for (item, item_checkbox) in self.checkbox_dic.items():
            item_status = item_checkbox.isChecked()
            self.item_select_status_signal.emit(item, item_status)


class SettingWindow(QMainWindow):
    update_setting_flag = pyqtSignal(dict, bool)
    update = pyqtSignal(bool, str)

    def __init__(self, mw, ifp_env_setting, mode='setting'):
        super().__init__()

        self.mw = mw
        self.ifp_env_setting = ifp_env_setting
        self.origin_ifp_env_setting = copy.deepcopy(self.ifp_env_setting)
        self.mode = mode

        self.top_widget = QWidget()
        self.top_layout = QVBoxLayout()
        self.top_widget.setLayout(self.top_layout)
        self.setCentralWidget(self.top_widget)

        self.main_widget = QWidget()
        self.main_layout = QHBoxLayout()
        self.main_layout.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self.main_widget.setLayout(self.main_layout)

        self.button_widget = QWidget()
        self.button_layout = QHBoxLayout()
        self.button_widget.setLayout(self.button_layout)

        if self.mode == 'login':
            self.save_button = QPushButton('START')
        else:
            self.save_button = QPushButton('SAVE')

        self.cancel_button = QPushButton('CANCEL')
        self.cancel_button.clicked.connect(self.close)
        self.cancel_button.setFont(QFont('Calibri', 10))

        if self.mode == 'widget':
            self.save_button.setEnabled(False)
            self.reset_button = QPushButton('RESET')
            self.reset_button.setFont(QFont('Calibri', 10))
            self.reset_button.clicked.connect(self.reset)
            self.cancel_button.hide()

        self.save_button.clicked.connect(self.save)
        self.save_button.setFont(QFont('Calibri', 10))

        self.frames = {}
        self.current_frame = None
        self.reset = False

        self.tree = QTreeWidget()
        self.tree.clicked.connect(self.generate_setting)
        self.frame0 = QFrame(self.main_widget)
        self.frame1 = QFrame(self.main_widget)
        self.frame0.setFixedWidth(250)
        self.frame1.setFixedWidth(700)

        self.need_reload_flag = False
        self.project_item = None
        self.disable_gui_flag = False

    def init_ui(self):
        self.main_layout.addWidget(self.frame_items())
        self.main_layout.addWidget(self.frame_setting())

        self.button_layout.addStretch(1)
        self.button_layout.addWidget(self.save_button)
        self.button_layout.addWidget(self.cancel_button)

        if self.mode == 'widget':
            self.button_layout.addWidget(self.reset_button)

        self.top_layout.addWidget(self.main_widget)
        self.top_layout.addWidget(self.button_widget)

        self.top_layout.setStretch(0, 10)
        self.top_layout.setStretch(1, 1)

        self.resize(1000, 500)

        if self.mode == 'login':
            self.setWindowTitle('Login - IC Flow Platform %s' % IFP_VERSION)
        else:
            self.setWindowTitle('Settings')

        common_pyqt5.center_window(self)
        self.tree.setCurrentItem(self.project_item)

        self.gen_main_tab()
        self.generate_setting()

        return self

    def disable_gui(self):
        for main_category in self.ifp_env_setting.keys():
            for child_category in self.ifp_env_setting[main_category].keys():
                for item in self.ifp_env_setting[main_category][child_category].keys():
                    widget = self.ifp_env_setting[main_category][child_category][item]['widget']
                    if isinstance(widget, QLineEdit):
                        widget.setReadOnly(True)
                    elif isinstance(widget, QTextEdit):
                        widget.setReadOnly(True)
                    elif isinstance(widget, QPushButton):
                        widget.setEnabled(False)
                    elif isinstance(widget, QCheckBox):
                        widget.setEnabled(False)

        self.cancel_button.setEnabled(False)
        self.reset_button.setEnabled(False)

    def enable_gui(self):
        for main_category in self.ifp_env_setting.keys():
            for child_category in self.ifp_env_setting[main_category].keys():
                for item in self.ifp_env_setting[main_category][child_category].keys():
                    widget = self.ifp_env_setting[main_category][child_category][item]['widget']
                    if isinstance(widget, QLineEdit):
                        widget.setReadOnly(False)
                    elif isinstance(widget, QTextEdit):
                        widget.setReadOnly(False)
                    elif isinstance(widget, QPushButton):
                        widget.setEnabled(True)
                    elif isinstance(widget, QCheckBox):
                        widget.setEnabled(True)

        self.cancel_button.setEnabled(True)
        self.reset_button.setEnabled(True)

    def gen_main_tab(self):
        for main_category in self.ifp_env_setting.keys():
            self.frames.setdefault(main_category, {})

            for child_category in self.ifp_env_setting[main_category].keys():
                frame = QFrame(self.main_widget)
                frame.setFixedWidth(700)
                layout = QVBoxLayout()
                frame.setLayout(layout)
                self.frames[main_category][child_category] = frame
                label = QLabel('%s -> %s' % (main_category, child_category))
                label.setFont(QFont('Calibri', 10, QFont.Bold))
                layout.addWidget(label)

                row = 0

                for item in self.ifp_env_setting[main_category][child_category].keys():
                    line_widget = QWidget()
                    line_layout = QHBoxLayout()
                    line_widget.setLayout(line_layout)
                    item_widget = None

                    if self.ifp_env_setting[main_category][child_category][item]['widget_type'] == 'edit':
                        item_label = QLabel(item)
                        if item == '$MAX_RUNNING_JOBS':
                            item_label.setFixedWidth(150)
                        else:
                            item_label.setFixedWidth(100)
                        item_widget = QLineEdit()
                        item_label.setFont(QFont('Calibri', 10))
                        line_layout.addWidget(item_label)
                        line_layout.addWidget(item_widget)

                        if self.ifp_env_setting[main_category][child_category][item]['value'] is not None:
                            item_widget.setText(str(self.ifp_env_setting[main_category][child_category][item]['value']))

                        if self.mode == 'widget':
                            item_widget.textChanged.connect(self.modify_setting_signal)

                    elif self.ifp_env_setting[main_category][child_category][item]['widget_type'] == 'select':
                        item_widget = QCheckBox(item)
                        line_layout.addWidget(item_widget)

                        if self.ifp_env_setting[main_category][child_category][item]['value'] is True:
                            item_widget.setChecked(True)
                        else:
                            item_widget.setChecked(False)

                        if self.mode == 'widget':
                            item_widget.stateChanged.connect(self.modify_setting_signal)

                    self.ifp_env_setting[main_category][child_category][item]['widget'] = item_widget
                    layout.addWidget(line_widget)

                    row += 1

                    if 'description' in self.ifp_env_setting[main_category][child_category][item].keys():
                        label = QLabel('             ' + self.ifp_env_setting[main_category][child_category][item]['description'])
                        label.setStyleSheet('font-family : calibri; font-size : 13px; font-style:oblique; color:#9c9c9c')
                        layout.addWidget(label)
                        label.setFixedHeight(10)
                        row += 1

                    if 'split_line' in self.ifp_env_setting[main_category][child_category][item].keys():
                        hline = QFrame(self)
                        hline.setFrameShape(QFrame.HLine)
                        hline.setFrameShadow(QFrame.Plain)
                        hline.setStyleSheet("color : grey")
                        hline.setLineWidth(0)
                        hline.setMidLineWidth(0)
                        layout.addWidget(hline)

                layout.addStretch(1)
                layout.setStretch(row + 1, 50)
                self.main_layout.addWidget(frame)
                frame.hide()

    def frame_items(self):
        layout = QVBoxLayout()
        self.frame0.setLayout(layout)

        self.tree.clear()
        self.tree.setColumnCount(1)
        self.tree.setColumnWidth(0, 240)
        self.tree.setHeaderHidden(True)
        self.tree.horizontalScrollBar().hide()

        for main_category in self.ifp_env_setting.keys():
            parent = QTreeWidgetItem(self.tree)
            parent.setText(0, main_category)
            parent.setForeground(0, QBrush(QColor(0, 0, 0)))
            parent.setFont(0, QFont('Calibri', 10, QFont.Bold))
            parent.setSelected(False)
            parent.setExpanded(True)

            for child_category in self.ifp_env_setting[main_category].keys():
                child = QTreeWidgetItem(parent)
                child.setText(0, child_category)
                child.setFont(0, QFont('Calibri', 10))
                child.setExpanded(False)

                if child_category == 'Project':
                    self.project_item = child

        layout.addWidget(self.tree)

        return self.frame0

    def frame_setting(self):
        layout = QVBoxLayout()
        self.frame1.setLayout(layout)
        self.current_frame = self.frame1

        return self.frame1

    def generate_setting(self):
        child_category = self.tree.currentItem()

        if child_category.parent() is None:
            return
        else:
            main_category = child_category.parent()
            self.current_frame.hide()
            frame = self.frames[main_category.text(0)][child_category.text(0)]
            frame.show()
            self.current_frame = frame

    def save(self):
        project = self.ifp_env_setting['Project settings']['Project']['Project name']['widget'].text()
        group = self.ifp_env_setting['Project settings']['Project']['User group']['widget'].text()
        raw_project = self.ifp_env_setting['Project settings']['Project']['Project name']['value']
        raw_group = self.ifp_env_setting['Project settings']['Project']['User group']['value']

        need_auto_update_default_yaml_flag = False

        if not project == raw_project or not group == raw_group:
            need_auto_update_default_yaml_flag = True

        default_yaml_path = common.get_default_yaml_path(project, group)
        api_yaml = common.get_default_yaml_path(project, group, key_word='api')

        for main_category in self.ifp_env_setting.keys():
            for child_category in self.ifp_env_setting[main_category].keys():
                for item in self.ifp_env_setting[main_category][child_category].keys():
                    if self.ifp_env_setting[main_category][child_category][item]['widget_type'] == 'edit':
                        raw_setting = self.ifp_env_setting[main_category][child_category][item]['value']
                        new_setting = self.ifp_env_setting[main_category][child_category][item]['widget'].text()
                        self.origin_ifp_env_setting[main_category][child_category][item]['value'] = new_setting
                        auto_parse_setting = ''

                        if item == 'Default setting':
                            auto_parse_setting = default_yaml_path
                        elif item == 'API setting':
                            auto_parse_setting = api_yaml

                        if item in ['Default setting', 'API setting']:

                            if not raw_setting == new_setting:
                                if new_setting == '':
                                    new_setting = auto_parse_setting
                                self.ifp_env_setting[main_category][child_category][item]['value'] = new_setting
                                self.need_reload_flag = True
                                continue

                            elif not new_setting == auto_parse_setting and need_auto_update_default_yaml_flag:
                                reply = QMessageBox.question(self, "Warning", "Flow will parse %s from : \n %s \ndue to Project(%s) and Group(%s), press Yes to save setting or press No to keep raw setting." % (item, auto_parse_setting, project, group))

                                if reply == QMessageBox.Yes:
                                    self.ifp_env_setting[main_category][child_category][item]['value'] = auto_parse_setting
                                    self.need_reload_flag = True
                                    self.ifp_env_setting[main_category][child_category][item]['widget'].setText(auto_parse_setting)
                                    continue
                                elif reply == QMessageBox.No:
                                    pass

                        if not str(raw_setting) == str(new_setting):
                            self.ifp_env_setting[main_category][child_category][item]['value'] = new_setting

                            if child_category not in ['Process management']:
                                self.need_reload_flag = True

                    elif self.ifp_env_setting[main_category][child_category][item]['widget_type'] == 'select':
                        raw_setting = self.ifp_env_setting[main_category][child_category][item]['value']
                        new_setting = self.ifp_env_setting[main_category][child_category][item]['widget'].isChecked()
                        self.origin_ifp_env_setting[main_category][child_category][item]['value'] = new_setting

                        if not raw_setting == new_setting:
                            self.ifp_env_setting[main_category][child_category][item]['value'] = new_setting

        self.update_setting_flag.emit(self.ifp_env_setting, self.need_reload_flag)

        if self.mode == 'login':
            if self.ifp_env_setting['System settings']['Appearance']['Fullscreen mode']['value']:
                self.mw.showMaximized()
            else:
                self.mw.show()
        else:
            pass

        if self.mode != 'widget':
            self.close()
        else:
            self.save_button.setEnabled(False)
            self.update.emit(False, 'Setting')

    def modify_setting_signal(self):
        if self.mode != 'widget':
            return

        self.save_button.setEnabled(True)
        self.update.emit(True, 'Setting')

    def reset(self):
        if self.mode != 'widget':
            return

        self.ifp_env_setting = copy.deepcopy(self.origin_ifp_env_setting)
        self.gen_main_tab()
        self.generate_setting()
        self.save_button.setEnabled(False)
        self.update.emit(False, 'Setting')


class SystemSetting:
    def __init__(self):
        self.local_config_dir = '/home/' + USER + '/.ifp/config'
        self.local_config_file = self.local_config_dir + '/config.py'
        self.config_dic = common.CONFIG_DIC
        self.local_config_dic = {}

        # Get install config settings as default setting
        for key in self.config_dic:
            if key in dir(install_config):
                value = getattr(install_config, key)
            else:
                value = self.config_dic[key]['value']

            self.config_dic.update({key: value})

        # If user has local config file
        if os.path.isfile(self.local_config_file):
            # Import local config.py
            spec = importlib.util.spec_from_file_location('config', self.local_config_file)
            local_config = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(local_config)

            # If user has define personal setting in ~/.ifp/config/config.py, use user's setting
            for key in dir(local_config):
                if not re.match('^__.+__$', key):
                    value = getattr(local_config, key)
                    self.local_config_dic.setdefault(key, value)
                    if key in self.config_dic and key not in common.config.admin_setting_dic:
                        self.config_dic.update({key: value})

    def update_local_config(self, config_item, config_value):
        # If user defined item in local config.py, update it
        # If user didn't define item in local config.py, create it
        self.local_config_dic.update({config_item: config_value})

    def save_local_config(self):
        if self.local_config_dic:
            # Create .ifp/config dir
            if not os.path.isdir(self.local_config_dir):
                os.makedirs(self.local_config_dir)

            with open(self.local_config_file, 'w') as f:
                for item, value in self.local_config_dic.items():
                    f.write(str(item) + ' = ' + str(value) + '\n')


class ViewWindow(QMainWindow):
    status = pyqtSignal(dict)
    save_cache = pyqtSignal(bool)

    def __init__(self, status_dic=None, disable_list=None, title='Main View'):
        super().__init__()

        if disable_list is None:
            disable_list = []

        if status_dic is None:
            status_dic = {}

        self.view_select_dic = status_dic
        self.disable_list = disable_list
        self.title = title

        self.top_widget = QWidget()
        self.top_layout = QVBoxLayout()
        self.main_widget = QWidget()
        self.main_layout = QHBoxLayout()
        self.button_widget = QWidget()
        self.button_layout = QHBoxLayout()

        self.apply_button = QPushButton('Apply')
        self.cancel_button = QPushButton('Cancel')
        self.apply_button.clicked.connect(self.apply)
        self.cancel_button.clicked.connect(self.cancel)

        self.tables = {}
        self.tree = QTreeWidget()
        self.frame0 = QFrame(self.main_widget)
        self.current_frame = None

    def init_ui(self):
        self.setFixedSize(600, 400)
        self.setWindowTitle(self.title)

        self.top_widget.setLayout(self.top_layout)
        self.setCentralWidget(self.top_widget)
        self.top_layout.addWidget(self.main_widget)
        self.top_layout.addWidget(self.button_widget)
        self.top_layout.setStretch(0, 10)
        self.top_layout.setStretch(1, 1)

        self.main_widget.setLayout(self.main_layout)
        self.tree.clicked.connect(self.generate_selection)
        self.frame0.setFixedWidth(150)

        self.gen_tree()
        self.main_layout.addWidget(self.frame0)

        self.button_widget.setLayout(self.button_layout)
        self.button_layout.addStretch(1)
        self.button_layout.addWidget(self.apply_button)
        self.button_layout.addWidget(self.cancel_button)

        self.gen_table()
        self.current_frame = self.tables['column']
        self.current_frame.show()

        common_pyqt5.center_window(self)

    def gen_table(self):
        for view_name in self.view_select_dic:
            table = QTableView()
            model = QStandardItemModel()
            table.setModel(model)
            table.setShowGrid(False)
            table.setSortingEnabled(True)
            table.verticalHeader().setVisible(False)
            table.horizontalHeader().setVisible(False)

            model.setColumnCount(1)

            item_list = list(self.view_select_dic[view_name].keys())
            item_len = len(item_list)
            model.setRowCount(item_len)

            row = 0

            for item in item_list:
                check_item = QStandardItem(item)

                if item in self.disable_list:
                    check_item.setForeground(QBrush(QColor(*(int(c * 255) for c in colors.to_rgb('grey')))))
                    check_item.setCheckable(False)
                else:
                    check_item.setCheckable(True)

                if self.view_select_dic[view_name][item]:
                    check_item.setCheckState(Qt.Checked)
                else:
                    check_item.setCheckState(Qt.Unchecked)

                model.setItem(row, 0, check_item)

                row += 1

            # model.itemChanged.connect(functools.partial(self.update_view, view_name))
            self.tables[view_name] = table
            self.main_layout.addWidget(table)
            table.hide()

    def generate_selection(self):
        view_name = self.tree.currentItem().text(0)

        if view_name in self.view_select_dic.keys():
            self.current_frame.hide()
            table = self.tables[view_name]
            table.resizeColumnsToContents()
            table.show()
            self.current_frame = table

    def gen_tree(self):
        layout = QVBoxLayout()
        self.frame0.setLayout(layout)

        self.tree.clear()
        self.tree.setColumnCount(1)
        self.tree.setColumnWidth(0, 240)
        self.tree.setHeaderHidden(True)
        self.tree.horizontalScrollBar().hide()

        column_parent = QTreeWidgetItem(self.tree)
        column_parent.setText(0, 'column')
        column_parent.setForeground(0, QBrush(QColor(0, 0, 0)))
        column_parent.setFont(0, QFont('Calibri', 10, QFont.Bold))
        column_parent.setSelected(True)
        column_parent.setExpanded(False)

        row_parent = QTreeWidgetItem(self.tree)
        row_parent.setText(0, 'row')
        row_parent.setForeground(0, QBrush(QColor(0, 0, 0)))
        row_parent.setFont(0, QFont('Calibri', 10, QFont.Bold))
        row_parent.setSelected(False)
        row_parent.setExpanded(True)

        block_child = QTreeWidgetItem(row_parent)
        block_child.setText(0, 'block')
        block_child.setFont(0, QFont('Calibri', 10))
        block_child.setExpanded(False)

        task_child = QTreeWidgetItem(row_parent)
        task_child.setText(0, 'task')
        task_child.setFont(0, QFont('Calibri', 10))
        task_child.setExpanded(False)

        layout.addWidget(self.tree)

        return self.frame0

    def read_status(self) -> Dict[str, Dict[str, bool]]:
        status = {}

        for view_name, table in self.tables.items():
            status.setdefault(view_name, {})

            for row in range(table.model().rowCount()):
                item = table.model().item(row, 0)
                item_name = item.text()
                item_status = True if item.checkState() else False
                status[view_name].update({item_name: item_status})

        return status

    def apply(self):
        progress_dialog = QProgressDialog("Updating Window ...", "Cancel", 0, 0, self)
        progress_dialog.setWindowTitle('Please Wait')
        progress_dialog.setCancelButton(None)
        progress_dialog.setWindowModality(Qt.WindowModal)
        progress_dialog.setWindowFlags(Qt.Window | Qt.WindowTitleHint | Qt.CustomizeWindowHint)
        progress_dialog.setRange(0, 0)
        progress_dialog.show()

        progress_dialog.raise_()
        progress_dialog.activateWindow()
        QApplication.processEvents()

        status_dic = self.read_status()
        self.status.emit(status_dic)

        progress_dialog.close()

    def cancel(self):
        self.close()

    def closeEvent(self, a0):
        self.save_cache.emit(True)
        super().closeEvent(a0)


class TabBar(QTabBar):
    def tabSizeHint(self, index):
        s = QTabBar.tabSizeHint(self, index)
        s.transpose()
        return s

    def paintEvent(self, event):
        painter = QStylePainter(self)
        opt = QStyleOptionTab()

        for i in range(self.count()):
            self.initStyleOption(opt, i)
            painter.drawControl(QStyle.CE_TabBarTabShape, opt)
            painter.save()

            s = opt.rect.size()
            s.transpose()
            r = QRect(QPoint(), s)
            r.moveCenter(opt.rect.center())
            opt.rect = r

            c = self.tabRect(i).center()
            painter.translate(c)
            painter.rotate(90)
            painter.translate(-c)
            painter.drawControl(QStyle.CE_TabBarTabLabel, opt)
            painter.restore()


class TabWidget(QTabWidget):
    def __init__(self, *args, **kwargs):
        QTabWidget.__init__(self, *args, **kwargs)
        self.setTabBar(TabBar(self))
        self.setTabPosition(QTabWidget.West)
        self.currentChanged.connect(self.onTabChanged)

    def onTabChanged(self, currentIndex):
        self.previousTabIndex = currentIndex


class SidebarTree(QMainWindow):
    go_to_msg = pyqtSignal(int, int)
    show_hide_item = pyqtSignal(int, int, bool)

    def __init__(self):
        super().__init__()

        self.tree = QTreeWidget()
        self.setCentralWidget(self.tree)
        self.config = parse_config.Config(None)
        self._init_ui()

    def _init_ui(self):
        self.tree.setColumnCount(1)
        self.tree.header().setSectionResizeMode(QHeaderView.Stretch)
        self.tree.header().setStretchLastSection(False)

        self._update_tree()
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._gen_tree_menu)

    def _gen_tree_menu(self, pos):
        item = self.tree.itemAt(pos)
        selected_item = self.tree.currentItem()

        if selected_item and selected_item == item:
            menu = QMenu()

            if selected_item.childCount():
                fold_menu = menu.addMenu('Folding')
                expand_all_action = fold_menu.addAction('Expand All')
                expand_siblings_action = fold_menu.addAction('Expand Siblings')
                expand_self_action = fold_menu.addAction('Expand')
                fold_menu.addSeparator()
                collapse_all_action = fold_menu.addAction('Collapse All')
                collapse_siblings_action = fold_menu.addAction('Collapse Siblings')
                collapse_self_action = fold_menu.addAction('Collapse')
                menu.addSeparator()

                expand_all_action.triggered.connect(functools.partial(self._fold_tree, expand=True, level='ALL'))
                expand_siblings_action.triggered.connect(functools.partial(self._fold_tree, expand=True, level='SIBLINGS'))
                expand_self_action.triggered.connect(functools.partial(self._fold_tree, expand=True, level='SELF'))
                collapse_all_action.triggered.connect(functools.partial(self._fold_tree, expand=False, level='ALL'))
                collapse_siblings_action.triggered.connect(functools.partial(self._fold_tree, expand=False, level='SIBLINGS'))
                collapse_self_action.triggered.connect(functools.partial(self._fold_tree, expand=False, level='SELF'))

            go_to_action = menu.addAction('Go To')
            go_to_action.triggered.connect(self._go_to_task)

            _, row, column = self.parse_tree_node(self.tree.currentItem().whatsThis(0))
            enable = self.config.table_visible_status[(row, column)]
            go_to_action.setEnabled(enable)

            if column in [0, 3]:
                show_hide_action = menu.addAction('Hide')

                if not enable:
                    show_hide_action.setText('Show')

                show_hide_action.triggered.connect(self._show_hide_item)

            menu.exec_(self.tree.viewport().mapToGlobal(pos))

    def _go_to_task(self):
        if not self.tree.currentItem():
            return

        check, row, column = self.parse_tree_node(self.tree.currentItem().whatsThis(0))

        if check:
            self.go_to_msg.emit(row, column)

    def _show_hide_item(self):
        if not self.tree.currentItem():
            return

        _, row, column = self.parse_tree_node(self.tree.currentItem().whatsThis(0))
        enable = not self.config.table_visible_status[(row, column)]

        self.show_hide_item.emit(row, column, enable)

    @staticmethod
    def parse_tree_node(what_is_this: str) -> Tuple[bool, int, int]:
        if my_match := re.match(r'(\d+):(\d+)', what_is_this):
            row = int(my_match.group(1))
            column = int(my_match.group(2))

            return True, row, column
        return False, 0, 0

    def _fold_tree(self, expand: bool, level: str = 'ALL'):
        if not self.tree.currentItem():
            return

        level = level.upper()

        if level == 'SELF':
            self.tree.currentItem().setExpanded(expand)
        elif level == 'SIBLINGS':
            parent = self.tree.currentItem().parent()

            if parent:
                for index in range(parent.childCount()):
                    parent.child(index).setExpanded(expand)
            else:
                for i in range(self.tree.topLevelItemCount()):
                    self.tree.topLevelItem(i).setExpanded(expand)
        elif level == 'ALL':
            if expand:
                self.tree.expandAll()
            else:
                self.tree.collapseAll()
        else:
            return

    def update(self):
        self._update_tree()

    def _update_tree(self):
        # Clear
        self.tree.clear()
        self.tree.setHeaderLabels(['     %s' % self.config.PROJECT, ])
        row = 0

        for block_obj in self.config.block_dic.values():
            block_item = self._generate_tree_item(block_obj.NAME, visible=block_obj.Visible)
            self.tree.addTopLevelItem(block_item)
            block_item.setWhatsThis(0, f'{str(row)}:{str(0)}')

            for version_obj in block_obj.VERSION.values():
                version_item = self._generate_tree_item(version_obj.NAME, visible=block_obj.Visible)
                block_item.addChild(version_item)
                version_item.setWhatsThis(0, f'{str(row)}:{str(1)}')

                for flow_obj in version_obj.FLOW.values():
                    flow_item = self._generate_tree_item(flow_obj.NAME, visible=block_obj.Visible)
                    version_item.addChild(flow_item)
                    flow_item.setWhatsThis(0, f'{str(row)}:{str(2)}')

                    for task_obj in flow_obj.TASK.values():
                        task_item = self._generate_tree_item(task_obj.NAME, visible=task_obj.Visible)
                        flow_item.addChild(task_item)
                        task_item.setWhatsThis(0, f'{str(row)}:{str(3)}')
                        row += 1

        self.tree.expandAll()

    @staticmethod
    def _generate_tree_item(text: str, visible: bool = True) -> QTreeWidgetItem:
        item = QTreeWidgetItem()
        item.setText(0, text)

        if visible:
            item.setForeground(0, QBrush(QColor('black')))
            item.setIcon(0, QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/blue/block.png'))
        else:
            item.setForeground(0, QBrush(QColor('gray')))
            item.setIcon(0, QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/gray/block.png'))

        return item


class FlowChartBackend(QObject):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window

    @pyqtSlot(str)
    def open_node_window(self, node_id):
        self.main_window.open_task_information_window(node_id)


class FlowChartWindow(QMainWindow):
    block_version_task = pyqtSignal(str, str, str)

    def __init__(self, config_obj: parse_config.Config, width: int, height: int):
        super().__init__()

        self.width = width
        self.height = height

        # Render
        env = jinja2.Environment(loader=jinja2.FileSystemLoader(os.path.join(str(os.environ['IFP_INSTALL_PATH']), 'data/js/templates')))
        template = env.get_template('flowchart.html')
        self.template_html = template.render(width=width - 40, height=height - 100, js=os.path.join(str(os.environ['IFP_INSTALL_PATH']), 'data/js'))

        if not os.access(os.getcwd(), os.W_OK):
            base_dir = Path.home()
        else:
            base_dir = os.getcwd()

        self.html_file = os.path.join(base_dir, f'.ifp/html/{datetime.datetime.now().timestamp()}flowchart.html')
        os.makedirs(os.path.dirname(self.html_file), exist_ok=True)

        with open(self.html_file, 'w') as ft:
            ft.write(self.template_html)

        self.config_obj = config_obj
        self.block = None
        self.version = None
        self.node_list = []
        self.edge_list = []

        # UI
        self.top_widget = QWidget()
        self.top_layout = QVBoxLayout()
        self.webview = QWebEngineView()
        self.button_widget = QWidget()
        self.button_layout = QHBoxLayout()
        self.refresh_button_group = QButtonGroup()
        self.refresh_list = [10, 20, 30, 60]
        self.refresh_interval = self.refresh_list[0]
        self.refresh_button_list = []
        self.job_refresh_button = QPushButton('Refresh')
        self.job_refresh_button.clicked.connect(self.refresh)
        self.job_refresh_button.setEnabled(False)

        # Refresh
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        # self.timer.start(self.refresh_interval * 1000)
        self.refresh_thread = FlowChartWorker(config_obj)
        self.refresh_thread.node_list.connect(self.update_task_status)

        # Web
        self.channel = QWebChannel()
        self.backend = FlowChartBackend(self)
        self.channel.registerObject("backend", self.backend)
        self.webview.page().setWebChannel(self.channel)

        self.graph_update_thread = None
        self.setMaximumSize(width, height)

        self._init_ui()

    def _init_ui(self):
        self.setCentralWidget(self.top_widget)

        self.webview.load(QUrl.fromLocalFile(self.html_file))
        self.top_layout.addWidget(self.webview, 20)
        self.top_layout.addWidget(self.button_widget, 1)
        self.top_widget.setLayout(self.top_layout)

        # Button
        flash_label = QLabel('Refresh(s)')
        flash_label.setStyleSheet("font-weight: bold;")
        flash_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.button_widget.setLayout(self.button_layout)
        self.button_layout.addStretch(2)
        self.button_layout.addWidget(flash_label, 2, Qt.AlignRight)

        for index, flash in enumerate(self.refresh_list):
            flash_button = QRadioButton(str(flash))
            flash_button.clicked.connect(self.restart_timer)
            self.refresh_button_list.append(flash_button)
            self.refresh_button_group.addButton(flash_button, index)

        flash_button = QRadioButton('Manual')
        flash_button.clicked.connect(self.restart_timer)
        self.refresh_button_list.append(flash_button)
        self.refresh_button_group.addButton(flash_button, len(self.refresh_button_list) + 1)

        self.refresh_button_group.button(0).setChecked(True)

        for i in range(len(self.refresh_button_list)):
            self.button_layout.addWidget(self.refresh_button_list[i], 1)

        self.button_layout.addStretch(20)
        self.button_layout.addWidget(self.job_refresh_button)

        common_pyqt5.center_window(self)

    def refresh(self):
        """
        Refresh node status.
        """
        # Stop Timer
        self.timer.stop()

        if not self.refresh_thread.isRunning():
            self.refresh_thread.start()

    def update_task_status(self, node_list):
        self.node_list = node_list
        self.update_graph()

        # Restart Timer
        self.restart_timer()

    def restart_timer(self):
        if my_match := re.match(r'^(\d+)$', self.new_refresh_interval):
            self.job_refresh_button.setEnabled(False)
            new_interval = int(my_match.group(1))
            self.refresh_interval = new_interval
            self.timer.stop()

            if not self.timer.isActive():
                self.timer.start(new_interval * 1000)
        else:
            self.job_refresh_button.setEnabled(True)
            self.timer.stop()
            self.refresh_interval = None

            if self.timer.isActive():
                self.timer.stop()

    def gen_flow_graph(self, dependency_dic: Dict[str, str], block: str, version: str):
        _, self.node_list, self.edge_list = WindowForDependency.gen_dependency_chart_info(block=block, version=version, dependency_dic=dependency_dic)
        self.block = block
        self.version = version
        self.setFixedSize(self.width, self.height)
        self.refresh_thread.load_block_version(block=block, version=version, node_list=self.node_list)
        self.setWindowTitle(f'Flow Chart for {block}/{version}')
        self.reset_graph()
        self.refresh()

    def gen_full_flow_graph(self, dependency_dic: Dict[str, Dict[str, Dict[str, str]]], update: bool = False):
        _, self.node_list, self.edge_list = WindowForDependency.gen_full_dependency_chart_info(dependency_dic=dependency_dic)
        self.refresh_thread.load_block_version(node_list=self.node_list)
        self.setWindowTitle('Flow Chart')

        if update:
            self.reset_graph()
            self.refresh()

    def reset_graph(self):
        js_command = "clearGraph();"
        self.webview.page().runJavaScript(js_command)

    def update_graph(self):
        """
        Update Flow Chart.
        """
        js_command = f"updateGraph({json.dumps(self.node_list)}, {json.dumps(self.edge_list)});"
        self.webview.page().runJavaScript(js_command)

    def resize_graph(self, width: int, height: int):
        """
        Update Flow Chart.
        """
        self.setMaximumSize(width, height)
        js_command = f"""
        try {{
            if (typeof resizeGraph !== 'undefined') {{
                resizeGraph({str(width - 40)}, {str(height - 100)});
            }}
        }} catch(error) {{
            console.log('resizeGraph not available yet');
        }}
        """

        def js_callback(__result):
            pass

        self.webview.page().runJavaScript(js_command, js_callback)

    @property
    def new_refresh_interval(self) -> str:
        for button in self.refresh_button_list:
            if not button.isChecked():
                continue

            return button.text()

    def closeEvent(self, a0):
        if isinstance(self.refresh_thread, FlowChartWorker) and self.refresh_thread.isRunning():
            self.refresh_thread.terminate()

        super().closeEvent(a0)

    def open_task_information_window(self, node_id: str):
        node_info = node_id.split('-')

        if len(node_info) < 3:
            return

        block, version, task = node_info[0], node_info[1], node_info[2]
        self.block_version_task.emit(block, version, task)


class FlowChartWorker(QThread):
    node_list = pyqtSignal(list)

    def __init__(self, config_obj: parse_config.Config):
        super().__init__()

        self.block = None
        self.version = None
        self.node_dic = {}
        self.config_obj = config_obj

    def load_block_version(self, node_list: List[Dict[str, str]], block: str = None, version: str = None):
        self.block = block
        self.version = version
        self.node_dic = {node_dic['id']: node_dic for node_dic in node_list}

    def run(self):
        if not self.node_dic:
            return

        for block in self.config_obj.block_dic.values():
            if self.block and block.NAME != self.block:
                continue

            for version in block.VERSION.values():
                if self.version and version.NAME != self.version:
                    continue

                for flow in version.FLOW.values():
                    if not flow.TASK:
                        continue

                    for task in flow.TASK.values():
                        node_id = f'{block.NAME}-{version.NAME}-{task.NAME}'

                        if node_id in self.node_dic:
                            color = MainWindow.mapping_status_color(status=task.RunStatus)

                            if color is None:
                                if 'color' in self.node_dic[node_id]:
                                    del self.node_dic[node_id]['color']

                                continue

                            if task.Status == 'Cancelled':
                                color = QColor(211, 211, 211)

                            self.node_dic[node_id]['color'] = {'background': color.name(),
                                                               'border': color.name(),
                                                               'highlight': color.name(),
                                                               'hover': color.name()}

        self.node_list.emit([node for node in self.node_dic.values()])


class IgnoreRightButtonMenu(QMenu):
    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            event.ignore()
        else:
            super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.RightButton:
            event.ignore()
        else:
            super().mouseDoubleClickEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.RightButton:
            event.ignore()
        else:
            super().mouseReleaseEvent(event)


def execute_action_for_pre_cfg():
    api_yaml = common.get_default_yaml_path(key_word='api')
    user_api = common.parse_user_api(api_yaml)
    env_dic = common.get_env_dic()
    tmp_ifp_folder = '%s/.ifp/' % os.getcwd()

    if not os.path.exists(tmp_ifp_folder):
        os.makedirs(tmp_ifp_folder)

    for (key, value) in env_dic.items():
        os.environ[key] = value

    if 'PRE_CFG' in user_api['API'].keys() and len(list(user_api['API']['PRE_CFG'])) > 0:
        var_dic = {'IFP_INSTALL_PATH': os.environ['IFP_INSTALL_PATH'],
                   'CWD': CWD}
        var_dic.update(env_dic)

        for item in user_api['API']['PRE_CFG']:
            if not item['ENABLE']:
                continue

            common.run_command_for_api(common.expand_var(item['COMMAND'], ifp_var_dic=var_dic), '', common.expand_var(item['PATH'], ifp_var_dic=var_dic))


def execute_action_for_pre_ifp(ifp_obj):
    user_api = common.parse_user_api(ifp_obj.api_yaml)

    if 'PRE_IFP' in user_api['API'].keys() and len(list(user_api['API']['PRE_IFP'])) > 0:
        for item in user_api['API']['PRE_IFP']:
            if not item['ENABLE']:
                continue

            if (not item['PROJECT'] or ifp_obj.config_dic['PROJECT'] == item['PROJECT']) and (not item['GROUP'] or ifp_obj.config_dic['GROUP'] == item['GROUP']):
                pass
            else:
                continue

            common.run_command_for_api(common.expand_var(item['COMMAND'], ifp_var_dic=ifp_obj.config_obj.var_dic), '', common.expand_var(item['PATH'], ifp_var_dic=ifp_obj.config_obj.var_dic))


class GuideWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.top_widget = QWidget()
        self.top_layout = QGridLayout()
        self.top_widget.setLayout(self.top_layout)
        self.setCentralWidget(self.top_widget)
        self.setWindowFlags(Qt.WindowStaysOnTopHint)
        self.resize(1000, 800)

        self.setWindowTitle('Guidance (1/7)')
        self.current_step = 1

        self.label = QLabel()
        self.label.setFont(QFont('Calibri', 12, QFont.Bold))
        self.comment_label = QLabel()
        self.comment_label.setStyleSheet('font-family : calibri; font-size : 17px; font-style:oblique; color:#9c9c9c')
        self.pic_label = QLabel()
        self.pic_label.setFrameShape(QFrame.Panel)
        self.pic_label.setMinimumSize(1, 1)

        self.button1 = QPushButton()
        self.button1.clicked.connect(lambda: self.update_gui(self.current_step - 1))
        self.button1.setFixedWidth(100)
        self.button2 = QPushButton()
        self.button2.clicked.connect(lambda: self.update_gui(self.current_step + 1))
        self.button2.setFixedWidth(100)

        self.guide_dic = {1: {'label': 'STEP 1.  We recommend user invoke administrators\' default settings by setting project name and user group here',
                              'comment': 'Tips : Uniformly manage and invoke same project/group settings for different users is a good way to run complicated IC tasks',
                              'pic': str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/readme/IFP_setting.png'},
                          2: {'label': 'STEP 2.  Create blocks by right key menu in <Task Tab> and directly import all tasks from default yaml if you choose auto_import_tasks',
                              'comment': 'Tips : Not suggest user to enter each task info here, please inform administrator to add new task in default.yaml/api.yaml',
                              'pic': str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/readme/IFP_set_task2.png'},
                          3: {'label': 'STEP 3.  Fine tuning task settings by <Task information> menu',
                              'comment': '',
                              'pic': str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/readme/IFP_set_task.png'},
                          4: {'label': 'STEP 4.  Modify run order between tasks in <Order Tab> so that you can manager your jobs more efficiently',
                              'comment': 'Tips : You can enable run order function in <Setting Tab> - advanced settings',
                              'pic': str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/readme/IFP_set_order.png'},
                          5: {'label': 'STEP 5.  Set variables in <Variable Tab> so that IFP can invoke them when parser default.yaml / api.yaml or task settings',
                              'comment': 'Tips : You can enable variable function in <Setting Tab> - advanced settings',
                              'pic': str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/readme/IFP_set_variable.png'},
                          6: {'label': 'STEP 6.  Enable or disable APIs in <API Tab>',
                              'comment': 'Tips : You can enable api function in <Setting Tab> - advanced settings',
                              'pic': str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/readme/IFP_set_API.png'},
                          7: {'label': 'STEP 7.  Select tasks and run action in <Main Tab>',
                              'comment': '',
                              'pic': str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/readme/IFP_main_tab.png'},
                          }

        self.init_ui()
        self.update_gui(1)
        common_pyqt5.center_window(self)

    def init_ui(self):
        self.top_layout.addWidget(QLabel(), 0, 0, 1, 10)
        self.top_layout.addWidget(self.label, 1, 0, 2, 12)
        self.top_layout.addWidget(self.comment_label, 3, 0, 1, 12)
        self.top_layout.addWidget(self.pic_label, 4, 0, 5, 12)
        self.top_layout.addWidget(QLabel(), 9, 0, 1, 10)
        self.top_layout.addWidget(self.button1, 10, 10, 2, 1)
        self.top_layout.addWidget(self.button2, 10, 11, 2, 1)

    def update_gui(self, step):
        self.current_step = step

        if step == 8:
            self.close()
            return

        self.setWindowTitle('Guidance (%s/7)' % self.current_step)
        self.label.setText(self.guide_dic[step]['label'])
        self.comment_label.setText(self.guide_dic[step]['comment'])
        pixmap = QPixmap(self.guide_dic[step]['pic'])
        self.pic_label.setPixmap(pixmap)
        self.pic_label.setScaledContents(True)

        if step == 1:
            self.button1.hide()
            self.button2.setText('Next')
        elif step == 7:
            self.button1.show()
            self.button1.setText('Back')
            self.button2.setText('OK')
        else:
            self.button1.show()
            self.button1.setText('Back')
            self.button2.setText('Next')


class ResizeEventFilter(QObject):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.window.resize_table_column)

    def eventFilter(self, obj, event):
        try:
            current_index = self.window.top_tab.currentIndex()

            if event.type() == QEvent.Resize:
                self.window.top_tab.setCurrentIndex(1)
                self.timer.start(200)
                self.window.top_tab.setCurrentIndex(current_index)
        except RuntimeError:
            pass

        return super().eventFilter(obj, event)


class GlobalEventFilter(QObject):
    def __init__(self, table):
        super().__init__()
        self.table = table

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonPress:
            if not self.table.underMouse():
                self.table.clearSelection()

        return super().eventFilter(obj, event)


def cleanup():
    global dispatcher_process, watcher_process
    print('Exiting, killing child processes...')

    # if dispatcher_process:
    #     dispatcher_process.kill()
    #     dispatcher_process.wait()

    # if watcher_process:
    #     watcher_process.kill()
    #     watcher_process.wait()

    for proc in [dispatcher_process, watcher_process]:
        terminate_popen(proc)


def terminate_popen(p: subprocess.Popen, timeout=5):
    if not p or p.poll() is not None:
        return
    try:
        pgid = os.getpgid(p.pid)
        os.killpg(pgid, signal.SIGTERM)
        p.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(pgid, signal.SIGKILL)
        p.wait()
    except ProcessLookupError:
        pass


def signal_handler(signum, frame):
    global ctrl_c_count

    if signum == signal.SIGINT:
        if not hasattr(signal_handler, 'count'):
            signal_handler.count = 0

        signal_handler.count += 1

        if signal_handler.count == 1:
            print("\nPress Ctrl+C again to exit")
            QTimer.singleShot(3000, lambda: setattr(signal_handler, 'count', 0))
        else:
            print("\nExiting...")
            QApplication.quit()
            threading.Timer(0.3, lambda: os._exit(130)).start()


# Main Process #
def main():
    signal.signal(signal.SIGINT, signal_handler)
    global dispatcher_process, watcher_process
    try:
        (config_file, read, debug, auto_execute_action, title) = common.readArgs()
        data_dir = os.path.join(os.path.dirname(config_file), common.gen_cache_file_name(config_file=os.path.basename(config_file))[-1])
        log_file = os.path.join(data_dir, 'ifp.log')
        env = os.environ.copy()
        env['IFP_LOG_FILE'] = log_file

        db_path = f'sqlite:///{os.path.join(data_dir, common_db.JobStoreTable)}'
        QApplication.setFont(QFont("Calibri", 10))

        # Follow user DPI for automatic scaling
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

        app = QApplication(sys.argv)
        launch_status = None

        if not read:
            launch_status = gen_lock_file()

            os.makedirs(data_dir, exist_ok=True)
            common_db.initialize_database(db_path)

            dispatcher_process = subprocess.Popen(
                ['python3', os.path.join(os.path.dirname(__file__), 'job_dispatcher.py'), *sys.argv[1:]],
                env=env,
                start_new_session=True
            )
            watcher_process = subprocess.Popen(
                ['python3', os.path.join(os.path.dirname(__file__), 'job_watcher.py'), *sys.argv[1:]],
                env=env,
                start_new_session=True
            )

            if not launch_status:
                sys.exit(1)

        execute_action_for_pre_cfg()
        MainWindow(config_file, read, debug, auto_execute_action, title)
        sys.exit(app.exec_())

    except Exception as error:
        print(traceback.format_exc())
        print(f'*Error*: {str(error)}.')
    finally:
        try:
            if not read and launch_status and os.path.exists('%s/.ifp/ifp.lock' % os.getcwd()):
                os.remove('%s/.ifp/ifp.lock' % os.getcwd())
        except Exception as error:
            print("*Error*: Remove lock file failed.")
            print('     ' + str(error))

        if not read:
            cleanup()


if __name__ == '__main__':
    main()
