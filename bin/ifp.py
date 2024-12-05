# -*- coding: utf-8 -*-
import copy
import json
import os
import re
import sys
import stat
import shutil
import argparse
import datetime
import getpass
import importlib
from typing import Dict

from matplotlib import colors
import functools

# Import PyQt5 libraries.
import yaml
from PyQt5.QtCore import pyqtSignal, QTimer, Qt, QProcess, QRect, QPoint
from PyQt5.QtWidgets import QMainWindow, QApplication, QAction, QMessageBox, QTabWidget, QWidget, QFrame, QGridLayout, QTextEdit, QTableWidget, QHeaderView, QTableWidgetItem, QFileDialog, QTreeWidget, QTreeWidgetItem, QDialog, QCheckBox, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, \
    QMenu, QTableView, QProgressDialog, QSplitter, QTabBar, QStylePainter, QStyleOptionTab, QStyle, QStatusBar
from PyQt5.QtGui import QIcon, QBrush, QColor, QFont, QStandardItem, QStandardItemModel, QPixmap

# Import local python files.
import parse_config
from user_config import UserConfig, DefaultConfig, WindowForDependency, WindowForToolGlobalEnvEditor, WindowForAPI, WindowForGlobalTaskInfo, TaskJobCheckWorker
from job_manager import JobManager

# Import common python files.
sys.path.append(str(os.environ['IFP_INSTALL_PATH']) + '/common')
import common
import common_pyqt5

# Import install config settings.
sys.path.append(str(os.environ['IFP_INSTALL_PATH']) + '/config')
import config as install_config

QT_DEVICE_PIXEL_RATIO = 1
os.environ['PYTHONUNBUFFERED'] = '1'
CWD = os.getcwd()
USER = getpass.getuser()
IFP_VERSION = 'V1.4 (2024.11.30)'

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
    parser.add_argument('-a', '--action',
                        default='',
                        choices=['build', 'run', 'check', 'summarize'],
                        help='Execute action after launch IFP')
    args = parser.parse_args()

    # get config_file.
    args.config_file = os.path.abspath(args.config_file)

    if not os.path.exists(args.config_file):
        gen_config_file(args.config_file)

    if not os.path.exists('%s/.ifp.status.yaml' % os.path.dirname(args.config_file)):
        gen_config_file('%s/.ifp.status.yaml' % os.path.dirname(args.config_file))

    if os.environ.get('IFP_DEMO_MODE', 'FALSE') == 'TRUE':
        print('>>> IFP Demo mode, you can set $IFP_DEMO_MODE=FALSE to exit')

    return args.config_file, args.debug, args.action


def gen_config_file(config_file):
    """
    Generate configure file.
    """

    try:
        with open(config_file, 'w') as CF:
            CF.write('')

    except Exception as error:
        print('*Error*: Failed on creating config file "' + str(config_file) + '".')
        print('         ' + str(error))
        sys.exit(1)


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
    def __init__(self, config_file, debug, auto_execute_action):
        super().__init__()

        # IFP input parameters
        self.ifp_config_file = config_file
        self.debug = debug
        self.auto_execute_action = auto_execute_action

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

        # Initial ifp.py/job_manager.py/user_config.py parameters
        self.default_config_file = None
        self.api_yaml = None
        # Initial job_manager.py dict
        self.job_manager = JobManager(self, debug=self.debug)
        self.job_manager.disable_gui_signal.connect(self.disable_gui)
        self.job_manager.finish_signal.connect(self.send_result_to_user)
        self.job_manager.close_signal.connect(self.final_close)
        # Initial ifp.py dict
        self.update_dict_by_load_config_file(self.ifp_config_file)
        execute_action_for_pre_ifp(self)

        # Initial user_config.py dict and GUI
        self.task_window = None
        self.task_window = UserConfig(self, self.ifp_config_file, self.default_config_file, self.api_yaml)
        self.task_window.load()
        self.task_window.save_flag.connect(lambda: self.save(save_mode='keep'))

        # IFP sub windows
        self.config_tab_index = {}
        self.guide_window = GuideWindow()
        self.setting_window = None
        self.dependency_window = None
        self.var_window = None
        self.api_window = None
        self.config_view_window = None
        self.flow_multiple_select_window = None
        self.default_config_window = None
        self.task_multiple_select_window = None

        self.setting_widget = None
        self.task_widget = None
        self.dependency_widget = None
        self.var_widget = None
        self.api_widget = None

        # Generate the GUI.
        self.main_table_title_list = ['Block', 'Version', 'Flow', 'Task', 'Status', 'Check', 'Summary', 'Job', 'Runtime', 'Xterm', 'Build Status', 'Run Status', 'Check Status', 'Summarize Status', 'Release Status']
        self.status_title_list = ['Build Status', 'Run Status', 'Check Status', 'Summarize Status', 'Release Status']
        self.operation_title_list = ['Status', 'Check', 'Summary', 'Job', 'Runtime', 'Xterm']
        # Initial ifp.py GUI

        self.gen_gui()
        self.load_status_file('./.ifp.status.yaml')

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

        self.export_complete_ifp_cfg_yaml()
        self.execute_action_after_launch_ifp()

        self.cache_view_path = os.path.join(common.get_user_cache_path(), 'VIEW/{TAB}/view_status.json')
        self.tab_name = 'MAIN'

        self._load_cache()

    def _load_cache(self):
        self._load_view_status_cache()

    def _load_view_status_cache(self):
        # load main window cache
        main_cache_path = self.cache_view_path.format_map({'TAB': self.tab_name})

        if not os.path.exists(main_cache_path):
            return

        try:
            with open(main_cache_path, 'r') as mf:
                update_dic = json.load(mf)

            self.view_status_dic['block'].update({key: update_dic['block'][key] for key in self.view_status_dic['block'] if key in update_dic['block']})
            self.view_status_dic['task'].update({key: update_dic['task'][key] for key in self.view_status_dic['task'] if key in update_dic['task']})
        except Exception:
            return

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

        self.gen_main_tab()
        self.gen_config_tab()

        # Gen message frame
        self.message_frame = QFrame()
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
        self.gui_height = 650
        self.resize(self.gui_width, self.gui_height)
        self.setWindowTitle('IC Flow Platform %s' % IFP_VERSION)
        self.setWindowIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/logo/ifp.png'))
        common_pyqt5.center_window(self)

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

        exit_action = QAction('&Exit', self)
        exit_action.setShortcut('Ctrl+E')
        exit_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/exit.png'))
        exit_action.triggered.connect(self.close)

        file_menu = menubar.addMenu('File')
        file_menu.addSeparator()
        file_menu.addAction(self.save_status_file_action)
        file_menu.addAction(self.load_status_file_action)
        file_menu.addSeparator()
        file_menu.addAction(save_config_file_action)
        file_menu.addAction(load_config_file_action)
        file_menu.addSeparator()
        file_menu.addAction(save_default_yaml_action)
        file_menu.addAction(save_api_yaml_action)
        file_menu.addSeparator()
        file_menu.addAction(exit_action)

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

        # Contral
        contral_all_action = QAction('&All_Steps', self)
        contral_all_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/other/all.png'))
        contral_all_action.triggered.connect(lambda: self.execute_action(common.action.run, run_all_steps=True))

        contral_build_action = QAction('&' + common.action.build, self)
        contral_build_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/other/build.png'))
        contral_build_action.triggered.connect(lambda: self.execute_action(common.action.build))

        contral_run_action = QAction('&' + common.action.run, self)
        contral_run_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/run.png'))
        contral_run_action.triggered.connect(lambda: self.execute_action(common.action.run))

        contral_kill_action = QAction('&' + common.action.kill, self)
        contral_kill_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/kill.png'))
        contral_kill_action.triggered.connect(lambda: self.execute_action(common.action.kill))

        contral_check_action = QAction('&' + common.action.check, self)
        contral_check_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/checklist.png'))
        contral_check_action.triggered.connect(lambda: self.execute_action(common.action.check))

        contral_summary_action = QAction('&' + common.action.summarize, self)
        contral_summary_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/summary.png'))
        contral_summary_action.triggered.connect(lambda: self.execute_action(common.action.summarize))

        contral_release_action = QAction('&' + common.action.release, self)
        contral_release_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/release.png'))
        contral_release_action.triggered.connect(lambda: self.execute_action(common.action.release))

        contral_menu = menubar.addMenu('Control')
        contral_menu.addAction(contral_all_action)
        contral_menu.addAction(contral_build_action)
        contral_menu.addAction(contral_run_action)
        contral_menu.addAction(contral_kill_action)
        contral_menu.addAction(contral_check_action)
        contral_menu.addAction(contral_summary_action)
        contral_menu.addAction(contral_release_action)

        # Tool
        lsf_monitor_action = QAction('LSF monitor', self)
        lsf_monitor_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/chart.png'))
        lsf_monitor_action.triggered.connect(self.show_lsf_monitor)

        config_default_action = QAction('Config Default Yaml', self)
        config_default_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/edit_file.png'))
        config_default_action.triggered.connect(self.edit_config_default)

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

    def gen_status_bar(self):
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)

    def update_status_bar(self, message):
        self.statusBar.showMessage(message)

    def gen_toolbar(self):
        # Run all steps
        run_all_steps_action = QAction('Run All Steps', self)
        run_all_steps_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/other/all.png'))
        run_all_steps_action.triggered.connect(lambda: self.execute_action(common.action.run, run_all_steps=True))

        self.toolbar = self.addToolBar('Run All Steps')
        self.toolbar.addAction(run_all_steps_action)

        # Build
        build_action = QAction(common.action.build, self)
        build_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/other/build.png'))
        build_action.triggered.connect(lambda: self.execute_action(common.action.build))

        self.toolbar = self.addToolBar(common.action.build)
        self.toolbar.addAction(build_action)

        # Run
        run_action = QAction(common.action.run, self)
        run_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/run.png'))
        run_action.triggered.connect(lambda: self.execute_action(common.action.run))

        self.toolbar = self.addToolBar(common.action.run)
        self.toolbar.addAction(run_action)

        # Kill
        kill_action = QAction(common.action.kill, self)
        kill_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/kill.png'))
        kill_action.triggered.connect(lambda: self.execute_action(common.action.kill))

        self.toolbar = self.addToolBar(common.action.kill)
        self.toolbar.addAction(kill_action)

        # Check
        check_action = QAction(common.action.check, self)
        check_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/checklist.png'))
        check_action.triggered.connect(lambda: self.execute_action(common.action.check))

        self.toolbar = self.addToolBar(common.action.check)
        self.toolbar.addAction(check_action)

        # Summary
        summary_action = QAction(common.action.summarize, self)
        summary_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/summary.png'))
        summary_action.triggered.connect(lambda: self.execute_action(common.action.summarize))

        self.toolbar = self.addToolBar(common.action.summarize)
        self.toolbar.addAction(summary_action)

        # Release
        release_action = QAction(common.action.release, self)
        release_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/release.png'))
        release_action.triggered.connect(lambda: self.execute_action(common.action.release))

        self.toolbar = self.addToolBar('Release')
        self.toolbar.addAction(release_action)

    def show_about(self):
        QMessageBox.about(self, 'IC flow Platform', """                                                       Version """ + str(IFP_VERSION) + """

Copyright © 2021 ByteDance. All Rights Reserved worldwide.""")

    def _cache_view_window_status(self, save: bool, tab_name: str, view_status_dic: Dict[str, Dict[str, bool]]):
        if not save:
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

        running_tasks = []
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

        ifp_close_time = datetime.datetime.now()
        run_time = (ifp_close_time - self.ifp_start_time).seconds
        hours = run_time // 3600
        minutes = (run_time % 3600) // 60
        seconds = run_time % 60
        self.write_system_log("close ifp, total runtime %02d:%02d:%02d" % (hours, minutes, seconds))

        self.task_window.thread.quit()
        self.save_status_file('./.ifp.status.yaml')
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
                                                                                           'value': self.config_dic['VAR']['BSUB_QUEUE'] if 'BSUB_QUEUE' in self.config_dic['VAR'].keys() else None}},
                                                    'Process management': {'Ignore fail tasks': {'widget_type': 'select',
                                                                                                 'value': self.ignore_fail,
                                                                                                 'description': 'Even if dependent tasks failed, selected task can start on schedule'},
                                                                           'Rerun before view': {'widget_type': 'select',
                                                                                                 'value': self.rerun_check_or_summarize_before_view,
                                                                                                 'description': 'Auto rerun CHECK(SUMMARIZE) command before view check(summarize) report'},
                                                                           'Send results': {'widget_type': 'select',
                                                                                            'value': self.send_result,
                                                                                            'description': 'Send result to users after action done'},
                                                                           'Confirm rerun tasks': {'widget_type': 'select',
                                                                                                   'value': self.rerun_flag,
                                                                                                   'description': 'Remind user to confirm if rerun PASSED tasks'},
                                                                           'Auto check': {'widget_type': 'select',
                                                                                          'value': self.auto_check,
                                                                                          'description': 'Auto execute check action after run finish'}
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

    def update_ifp_setting(self, settings, need_reload_flag):
        self.ifp_env_setting = settings

        if not settings['Project settings']['Project']['Default setting']['value'] == self.default_config_file:
            self.default_config_file = settings['Project settings']['Project']['Default setting']['value']
            self.task_window.default_yaml = settings['Project settings']['Project']['Default setting']['value']
            self.task_window.update_default_setting()

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
            self.set_ignore_fail_for_all_tasks()

        if not settings['System settings']['Process management']['Send results']['value'] == self.send_result:
            self.setting_parameters_obj.update_local_config('send_result', settings['System settings']['Process management']['Send results']['value'])
            self.send_result = settings['System settings']['Process management']['Send results']['value']

        if not settings['System settings']['Process management']['Auto check']['value'] == self.auto_check:
            self.setting_parameters_obj.update_local_config('auto_check', settings['System settings']['Process management']['Auto check']['value'])
            self.auto_check = settings['System settings']['Process management']['Auto check']['value']

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

            if self.ignore_fail:
                task_obj.ignore_fail = True
            else:
                task_obj.ignore_fail = False

    # SettingWindow (end)

    # ViewWindow (start) to show or hide columns/rows
    def gen_main_view_gui(self):
        self.config_view_window = ViewWindow(status_dic=self.view_status_dic, disable_list=self.view_disable_item_list, title=f'{self.tab_name} View')
        self.config_view_window.setWindowModality(Qt.ApplicationModal)
        self.config_view_window.item_select_status_signal.connect(self.update_main_view)
        self.config_view_window.save_cache.connect(functools.partial(self._cache_view_window_status, tab_name=self.tab_name, view_status_dic=self.view_status_dic))
        self.config_view_window.init_ui()
        self.config_view_window.show()

    def update_main_view(self, view_name, item_text, item_select_status, mode='update'):
        if view_name == 'column':
            if item_text not in self.header_column_mapping.keys():
                return

            if item_select_status:
                self.main_table.showColumn(self.header_column_mapping[item_text])
            else:
                self.main_table.hideColumn(self.header_column_mapping[item_text])
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

        self.view_status_dic[view_name][item_text] = item_select_status

        if mode == 'update':
            self.update_main_table()
            self.update_status_table()

        self.top_tab.setCurrentIndex(1)

    def gen_config_view_gui(self):
        self.config_view_window = ViewWindow(status_dic=self.task_window.view_status_dic, title=f'{self.task_window.tab_name} View')
        self.config_view_window.setWindowModality(Qt.ApplicationModal)
        self.config_view_window.item_select_status_signal.connect(self.task_window.update_config_view)
        self.config_view_window.init_ui()
        self.config_view_window.show()

    # ViewWindow (end)

    # DefaultConfigWindow (start) for admins to edit config
    def edit_config_default(self):
        self.default_config_window = DefaultConfig(self.default_config_file)
        self.default_config_window.save_signal.connect(self.task_window.update_default_setting)
        self.default_config_window.show()

    # DefaultConfigWindow (end)

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
        if not status_file:
            (status_file, file_type) = QFileDialog.getSaveFileName(self, 'Save status file', '.', 'YAML (*.yaml)')

        if status_file:
            self.update_message_text({'message': 'Save status into file "' + str(status_file) + '".', 'color': 'black'})

            # Seitch self.main_table_info_list into a dict.
            main_table_info_dic = {}

            for (i, main_table_info) in enumerate(self.main_table_info_list):
                main_table_info_dic[i] = {'Block': main_table_info['Block'],
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

            with open(status_file, 'w', encoding='utf-8') as SF:
                yaml.dump(main_table_info_dic, SF, indent=4, sort_keys=False)

    def load_status_file(self, status_file=''):
        if not status_file:
            (status_file, file_type) = QFileDialog.getOpenFileName(self, 'Load status file', '.', '*')

        if status_file and os.path.exists(status_file):
            self.update_message_text({'message': 'Load status with file "' + str(status_file) + '".', 'color': 'black'})

            # Get status from status file.
            with open(status_file, 'rb') as SF:
                saved_status_dic = yaml.load(SF, Loader=yaml.FullLoader)

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
                        runtime = status_dic['Runtime']
                        job = status_dic['Job']

                        if status == common.status.running and runtime and runtime != "pending":
                            status = self._update_main_tab_job_status(status=status, job=job)

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

    def _update_main_tab_job_status(self, status: str, job: str) -> str:
        check, job_dic = TaskJobCheckWorker.check_job_id(job_id=job)
        new_status = ''

        if check:
            if job_dic.get('job_type') == 'LSF':
                new_status = TaskJobCheckWorker.get_lsf_job_status(job_id=str(job_dic['job_id']))
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

            with open(config_file, 'w', encoding='utf-8') as SF:
                yaml.dump(dict(self.task_window.final_setting), SF, indent=4, sort_keys=False)

            self.load(config_file)

        if os.path.getsize(self.ifp_config_file) == 0:
            self.config_tab.setCurrentIndex(0)
            self.guide_window.show()

    def load(self, config_file=''):
        if not config_file:
            (config_file, file_type) = QFileDialog.getOpenFileName(self, 'Load config file', '.', '*')

        progress_dialog = QProgressDialog("Load ...", "Cancel", 0, 0, self)
        progress_dialog.setWindowTitle('Please Wait')
        progress_dialog.setCancelButton(None)
        progress_dialog.setWindowModality(Qt.WindowModal)
        progress_dialog.setWindowFlags(Qt.Window | Qt.WindowTitleHint | Qt.CustomizeWindowHint)
        progress_dialog.setRange(0, 0)
        progress_dialog.show()
        progress_dialog.raise_()
        progress_dialog.activateWindow()

        QApplication.processEvents()

        if config_file:
            try:
                with open(config_file, 'r') as fh:
                    yaml.load(fh, Loader=yaml.FullLoader)
            except Exception:
                self.update_message_text({'message': 'Failed load config file "' + str(config_file) + '".', 'color': 'red'})
                progress_dialog.close()
                return

            self.save_status_file('./.ifp.status.yaml')
            self.update_message_text({'message': 'Load config file "' + str(config_file) + '".', 'color': 'black'})
            # Update self.config_dic and self.main_table_info_list with new config_file.
            self.update_dict_by_load_config_file(config_file)
            # Update related GUI parts.
            self._load_cache()
            self.update_sidebar_tree()
            self.update_status_table()
            self.update_tab_index_dic()
            self.update_main_table()
            self.load_status_file('./.ifp.status.yaml')
            self.task_window.config_file = config_file
            self.task_window.config_path_edit.setText(config_file)
            self.task_window.load()
            self.update_config_tab()

        self.export_complete_ifp_cfg_yaml()
        progress_dialog.close()

    def export_complete_ifp_cfg_yaml(self):
        complete_ifp_cfg_yaml_path = '%s/.ifp/ifp.cfg.complete.yaml' % CWD
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
        self.config_obj = parse_config.Config(config_file)
        self.default_config_file = self.config_obj.default_config_file
        self.api_yaml = self.config_obj.api_yaml
        self.user_api = common.parse_user_api(self.api_yaml)
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

        self.set_ignore_fail_for_all_tasks()
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
        if not self.task_window.dependency_priority:
            self.dependency_widget = QWidget()
        else:
            self.dependency_window = WindowForDependency(
                dependency_priority_dic=self.task_window.dependency_priority,
                default_dependency_dic=self.task_window.default_dependency_dic,
                mode='widget'
            )
            self.dependency_widget = self.dependency_window.init_ui()
            self.dependency_widget.message.connect(self.task_window.update_extension_config_setting)
            self.dependency_widget.update.connect(self.update_config_tab_name)
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
        if not self.task_window.dependency_priority:
            self.dependency_widget = QWidget()
        else:
            self.dependency_window = WindowForDependency(
                dependency_priority_dic=self.task_window.dependency_priority,
                default_dependency_dic=self.task_window.default_dependency_dic,
                mode='widget'
            )
            self.dependency_widget = self.dependency_window.init_ui()
            self.dependency_widget.message.connect(self.task_window.update_extension_config_setting)
            self.dependency_widget.update.connect(self.update_config_tab_name)

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
        self.sidebar_tree = QTreeWidget(self.main_tab)

        # self.status_table
        self.status_table = QTableWidget(self.main_tab)

        # self.main_frame
        self.main_frame = QFrame(self.main_tab)
        self.main_frame.setFrameShadow(QFrame.Raised)
        self.main_frame.setFrameShape(QFrame.Box)

        # Grid
        main_tab_grid = QGridLayout()

        main_tab_grid.addWidget(self.sidebar_tree, 0, 0, 3, 1)
        # main_tab_grid.addWidget(self.status_table, 1, 0, 2, 1)
        main_tab_grid.addWidget(self.main_frame, 0, 1, 3, 2)

        main_tab_grid.setRowStretch(0, 5)
        main_tab_grid.setRowStretch(1, 1)
        main_tab_grid.setRowStretch(2, 1)

        main_tab_grid.setColumnStretch(0, 1)
        main_tab_grid.setColumnStretch(1, 6)

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
            self.disable_gui_flag = False

    # sidebar_tree (start) #
    def gen_sidebar_tree(self):
        self.sidebar_tree.setColumnCount(1)
        self.sidebar_tree.setHeaderLabels(['     %s' % self.config_dic['PROJECT'], ])
        self.sidebar_tree.header().setSectionResizeMode(QHeaderView.Stretch)
        self.sidebar_tree.header().setStretchLastSection(False)

        # Update self.sidebar_tree
        self.update_sidebar_tree()

    def sidebar_tree_item_click_behavior(self, item=None, column=0):
        if item is not None:
            if item.childCount():
                for child_item in item.takeChildren():
                    if item.checkState(column):
                        child_item = self.get_sidebar_tree_block_item(child_item.text(column), Qt.Checked)
                    else:
                        child_item = self.get_sidebar_tree_block_item(child_item.text(column), Qt.Unchecked)

                    item.addChild(child_item)
                    self.update_main_table_block_visible_status(child_item.text(column), child_item.checkState(column))

                if item.checkState(column):
                    self.update_message_text({'message': 'All blocks are selected.', 'color': 'black'})
                else:
                    self.update_message_text({'message': 'All blocks are un-selected.', 'color': 'black'})
            else:
                if item.checkState(column):
                    self.update_message_text({'message': 'Block ' + str(item.text(column)) + ' is selected.', 'color': 'black'})
                else:
                    self.update_message_text({'message': 'Block ' + str(item.text(column)) + ' is un-selected.', 'color': 'black'})

                self.update_main_table_block_visible_status(item.text(column), item.checkState(column))

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
        # Clear
        self.sidebar_tree.clear()

        for block in self.config_dic['BLOCK'].keys():

            block_item = self.get_sidebar_tree_block_item(block)
            self.sidebar_tree.addTopLevelItem(block_item)

            for version in self.config_dic['BLOCK'][block].keys():
                version_item = self.get_sidebar_tree_block_item(version)
                block_item.addChild(version_item)

                for flow in self.config_dic['BLOCK'][block][version].keys():
                    flow_item = self.get_sidebar_tree_block_item(flow)
                    version_item.addChild(flow_item)

                    for task in self.config_dic['BLOCK'][block][version][flow].keys():
                        task_item = self.get_sidebar_tree_block_item(task, icon_type='T')
                        flow_item.addChild(task_item)

        self.sidebar_tree.expandAll()

    def get_sidebar_tree_block_item(self, text, icon_type=''):
        item = QTreeWidgetItem()
        item.setText(0, text)
        # if icon_type == 'T':
        #     item.setIcon(0, QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/tree/icons8-t-67_副本.png'))
        # else:
        item.setIcon(0, QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/blue/block.png'))

        return item

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

            if check_status in [common.status.checking, common.status.passed, common.status.failed]:
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
        self.main_table = QTableWidget(self.main_frame)
        self.main_table.horizontalHeader().sectionClicked.connect(self.main_table_title_click_behavior)

        self.main_table.itemClicked.connect(self.main_table_item_click_behavior)
        self.main_table.doubleClicked.connect(self.main_table_item_double_click_behavior)

        # Grid
        main_frame_grid = QGridLayout()
        main_frame_grid.addWidget(self.main_table, 0, 0)
        self.main_frame.setLayout(main_frame_grid)

        # Gen self.main_table.
        self.gen_main_table()

    def main_table_title_click_behavior(self, index):
        if index == 3:
            status = Qt.Unchecked

            for main_table_info in self.main_table_info_list:
                if main_table_info['Visible'] and self.filt_task_status(main_table_info):
                    if not main_table_info['Selected']:
                        status = Qt.Checked

            if status == Qt.Checked:
                self.update_message_text({'message': 'All tasks are selected.', 'color': 'black'})
            else:
                self.update_message_text({'message': 'All tasks are un-selected.', 'color': 'black'})

            for main_table_info in self.main_table_info_list:
                if main_table_info['Visible'] and self.filt_task_status(main_table_info):
                    if status == Qt.Checked:
                        main_table_info['Selected'] = True
                    else:
                        main_table_info['Selected'] = False

                    self.update_main_table_item(main_table_info['Block'], main_table_info['Version'], main_table_info['Flow'], main_table_info['Task'], 'Task', main_table_info['Task'], selected=status)

    def main_table_item_click_behavior(self, item):
        if item is not None:
            self.current_selected_row = item.row()
            self.current_selected_column = item.column()

            visible_row = -1

            for (row, main_table_info) in enumerate(self.main_table_info_list):
                if main_table_info['Visible'] and self.filt_task_status(main_table_info):
                    visible_row += 1

                    if visible_row == self.current_selected_row:
                        self.current_selected_task_dic = main_table_info
                        self.current_selected_task_obj = self.current_selected_task_dic['Task_obj']

                        if self.current_selected_column == 3:
                            if item.checkState() == 0:
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
                                    self.update_message_text({'message': 'Failed to get local process {} info'.format(pid), 'color': 'red'})
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

    def main_table_item_double_click_behavior(self, item):
        if self.current_selected_column == 3:
            self.edit_detailed_config(read_only=self.disable_gui_flag, block=self.current_selected_task_dic['Block'], version=self.current_selected_task_dic['Version'], flow=self.current_selected_task_dic['Flow'], task=self.current_selected_task_dic['Task'])
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
            command = str(self.xterm_command) + ' "cd ' + path + '; ' + str(task.ACTION['COMMON']['XTERM_COMMAND']) + '; exec ' + str(os.environ['SHELL']) + '"'
        else:
            command = str(self.xterm_command) + ' "cd ' + path + '; exec ' + str(os.environ['SHELL']) + '"'

        thread_run = common.ThreadRun()
        thread_run.run([command, ])

    def gen_main_table(self):
        self.main_table.setShowGrid(True)
        self.main_table.verticalHeader().setVisible(True)
        self.main_table.setEditTriggers(QTableWidget.NoEditTriggers)

        # Gen self.main_table title.
        self.main_table.setColumnCount(len(self.main_table_title_list))
        self.main_table.setHorizontalHeaderLabels(self.main_table_title_list)

        self.main_table.setItemDelegate(common_pyqt5.CustomDelegate(wrap_columns=[0, 1]))

        self.main_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.main_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.main_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.main_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)

        self.main_table_header = self.main_table.horizontalHeader()
        self.main_table_header.setContextMenuPolicy(Qt.CustomContextMenu)
        self.main_table_header.customContextMenuRequested.connect(self.generate_select_menu)

        # self.main_table.setColumnWidth(2, 60)
        # self.main_table.setColumnWidth(3, 140)
        self.main_table.setColumnWidth(4, 140)
        self.main_table.setColumnWidth(5, 50)
        self.main_table.setColumnWidth(6, 70)
        self.main_table.setColumnWidth(7, 70)
        self.main_table.setColumnWidth(8, 70)
        self.main_table.setColumnWidth(9, 50)

        # gen open file menu
        self.main_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.main_table.customContextMenuRequested.connect(self.generate_menu)

        # Update self.main_table.
        self.hide_detail_status()

    def generate_select_menu(self, pos):
        menu = QMenu()
        column = self.main_table_header.logicalIndexAt(pos)

        if column in [2, 3]:
            select_flows_action = QAction('Select Flows', self)
            select_flows_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/red/F.png'))
            select_flows_action.triggered.connect(self.select_flows)
            menu.addAction(select_flows_action)

            select_steps_action = QAction('Select Tasks', self)
            select_steps_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/red/T.png'))
            select_steps_action.triggered.connect(self.select_tasks)
            menu.addAction(select_steps_action)

        menu.exec_(self.main_table.mapToGlobal(pos))

    def generate_menu(self, pos):
        select_items = self.main_table.selectedItems()

        if not select_items:
            return

        self.current_selected_column = select_items[-1].column()
        self.current_selected_row = select_items[-1].row()

        # cross-column selection is meaningless
        row_list = []

        for item in select_items:
            if not item.column() == self.current_selected_column:
                return

            row_list.append(item.row())

        menu = QMenu()

        visible_row = -1

        for (row, main_table_info) in enumerate(self.main_table_info_list):
            if main_table_info['Visible'] and self.filt_task_status(main_table_info):
                visible_row += 1

                if visible_row == self.current_selected_row:
                    self.current_selected_task_dic = main_table_info
                    self.current_selected_task_obj = self.current_selected_task_dic['Task_obj']

        # If only select one task
        if len(select_items) == 1 and self.current_selected_column == 3:
            skip_action = QAction('Skip task', self)
            skip_action.setCheckable(True)
            skip_action.setChecked(self.current_selected_task_obj.skipped)
            skip_action.triggered.connect(lambda: self.set_task_as_skipped(self.current_selected_task_obj, self.current_selected_row, self.current_selected_column))
            menu.addAction(skip_action)

            ignore_fail_action = QAction('Ignore fail', self)
            ignore_fail_action.setCheckable(True)
            ignore_fail_action.setChecked(self.current_selected_task_obj.ignore_fail)
            ignore_fail_action.triggered.connect(lambda: self.set_task_as_ignore_fail(self.current_selected_task_obj))
            menu.addAction(ignore_fail_action)

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

            menu.addMenu(action_menu)

            menu.addSeparator()

            view_setting_action = QAction('Task information', self)
            view_setting_action.triggered.connect(lambda: self.edit_detailed_config(read_only=self.disable_gui_flag, block=self.current_selected_task_dic['Block'], version=self.current_selected_task_dic['Version'], flow=self.current_selected_task_dic['Flow'], task=self.current_selected_task_dic['Task']))
            menu.addAction(view_setting_action)

            open_file_action = QAction('Open file', self)
            open_file_action.triggered.connect(lambda: self.open_file(self.current_selected_task_dic))
            menu.addAction(open_file_action)

            self.generate_main_tab_api_menu(self.current_selected_column, self.current_selected_task_dic, menu)
        # If select one block/version
        elif len(select_items) == 1 and self.current_selected_column < 3:
            self.generate_multiple_select_task_menu(self.current_selected_column, row_list, menu)
            self.generate_main_tab_api_menu(self.current_selected_column, self.current_selected_task_dic, menu)
        # If multiple select block/version/task
        elif len(select_items) > 1 and self.current_selected_column <= 3:
            self.generate_multiple_select_task_menu(self.current_selected_column, row_list, menu)

        menu.exec_(self.main_table.mapToGlobal(pos))

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
        self.child = WindowForGlobalTaskInfo(task_obj=self.job_manager.all_tasks[block][version][flow][task], user_config_obj=self.task_window, read_only=read_only)
        self.child.setWindowModality(Qt.ApplicationModal)
        self.child.detailed_task_window.message.connect(self.task_window.update_detailed_setting)
        self.child.show()

    def generate_multiple_select_task_menu(self, select_column, row_list, menu):
        select_task_action = QAction('Select All Task', self)
        select_task_action.triggered.connect(lambda: self.trigger_all_selected_task(select_column, row_list, True))
        menu.addAction(select_task_action)

        unselect_task_action = QAction('Unselect All Task', self)
        unselect_task_action.triggered.connect(lambda: self.trigger_all_selected_task(select_column, row_list, False))
        menu.addAction(unselect_task_action)

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
            self.main_table.itemFromIndex(self.main_table.model().index(row, column)).setForeground(QBrush(QColor(0, 0, 0)))

        else:
            task_obj.skipped = True
            self.main_table.itemFromIndex(self.main_table.model().index(row, column)).setForeground(QBrush(QColor(211, 211, 211)))

    def set_task_as_ignore_fail(self, task_obj):
        if task_obj.ignore_fail:
            task_obj.ignore_fail = False

            if self.ignore_fail:
                self.setting_window.ifp_env_setting['System settings']['Process management']['Ignore fail tasks']['widget'].setChecked(False)
                self.setting_window.save()
        else:
            task_obj.ignore_fail = True

    def trigger_all_selected_task(self, column, row_list, status):
        for row in row_list:
            row_span = self.main_table.rowSpan(row, column)

            for count in range(row, row + row_span):
                self.update_select_item_status(count, status)

    def update_select_item_status(self, row, select_status):
        if select_status:
            status = Qt.Checked
            # self.update_message_text({'message': 'Row: %d task is selected.' % (row + 1), 'color': 'black'})
        else:
            status = Qt.Unchecked
            # self.update_message_text({'message': 'Row: %d task is unselected.' % (row + 1), 'color': 'black'})

        self.update_main_table_item(self.main_table_info_list[row]['Block'], self.main_table_info_list[row]['Version'], self.main_table_info_list[row]['Flow'], self.main_table_info_list[row]['Task'], 'Task', self.main_table_info_list[row]['Task'], selected=status)

    def update_main_table(self, mode='create'):
        """
        Draw Main TAB table.

        Args:
             mode: Default 'create', option 'update'|'create', for setting func update_main_table_item args - mode
        """
        # Initial, clean up self.main_table.
        self.main_table.setRowCount(0)

        # Set row count.
        row_count = 0

        for main_table_info in self.main_table_info_list:
            if main_table_info['Visible'] and self.filt_task_status(main_table_info):
                row_count += 1
        self.main_table.setRowCount(row_count)

        # Update content.
        row_dic = {'Block': {'current': '', 'last': '', 'start_row': 0, 'end_row': 0, 'column': 0},
                   'Version': {'current': '', 'last': '', 'start_row': 0, 'end_row': 0, 'column': 1},
                   'Flow': {'current': '', 'last': '', 'start_row': 0, 'end_row': 0, 'column': 2}}

        visible_row = -1

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
            check = main_table_info['Check']
            summary = main_table_info['Summary']
            job = main_table_info['Job']
            runtime = main_table_info['Runtime']
            xterm = main_table_info['Xterm']

            row_dic['Block']['current'] = block
            row_dic['Version']['current'] = version
            row_dic['Flow']['current'] = flow

            self.update_main_table_item(block, version, flow, task, 'Block', block, flags=Qt.ItemIsSelectable | Qt.ItemIsEnabled, mode=mode, row=row, vrow=visible_row)
            self.update_main_table_item(block, version, flow, task, 'Version', version, flags=Qt.ItemIsSelectable | Qt.ItemIsEnabled, mode=mode, row=row, vrow=visible_row)
            self.update_main_table_item(block, version, flow, task, 'Flow', flow, flags=Qt.ItemIsSelectable | Qt.ItemIsEnabled, mode=mode, row=row, vrow=visible_row)

            if main_table_info['Selected']:
                self.update_main_table_item(block, version, flow, task, 'Task', task, selected=Qt.Checked, mode=mode, row=row, vrow=visible_row)
            else:
                self.update_main_table_item(block, version, flow, task, 'Task', task, selected=Qt.Unchecked, mode=mode, row=row, vrow=visible_row)

            self.update_main_table_item(block, version, flow, task, 'Status', status, mode=mode, row=row, vrow=visible_row)
            self.update_main_table_item(block, version, flow, task, 'BuildStatus', buildstatus, mode=mode, row=row, vrow=visible_row)
            self.update_main_table_item(block, version, flow, task, 'RunStatus', runstatus, mode=mode, row=row, vrow=visible_row)
            self.update_main_table_item(block, version, flow, task, 'CheckStatus', checkstatus, mode=mode, row=row, vrow=visible_row)
            self.update_main_table_item(block, version, flow, task, 'SummarizeStatus', summarizestatus, mode=mode, row=row, vrow=visible_row)
            self.update_main_table_item(block, version, flow, task, 'ReleaseStatus', releasestatus, mode=mode, row=row, vrow=visible_row)
            self.update_main_table_item(block, version, flow, task, 'Check', check, mode=mode, row=row, vrow=visible_row)
            self.update_main_table_item(block, version, flow, task, 'Summary', summary, mode=mode, row=row, vrow=visible_row)
            self.update_main_table_item(block, version, flow, task, 'Job', job, mode=mode, row=row, vrow=visible_row)
            self.update_main_table_item(block, version, flow, task, 'Runtime', runtime, mode=mode, row=row, vrow=visible_row)
            self.update_main_table_item(block, version, flow, task, 'Xterm', xterm, mode=mode, row=row, vrow=visible_row)

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

    def filt_task_status(self, main_table_info):
        status = self.status_filt_flag
        row_status = main_table_info["RunStatus"]

        check_status = main_table_info['CheckStatus']

        if check_status in [common.status.checking, common.status.passed, common.status.failed] and row_status != common.status.running:
            row_status = check_status

        if status == "" or status == "Total" or (status == "Run" and row_status == common.status.running) or (status == "Passed" and row_status == common.status.passed) or (status == "Failed" and row_status == common.status.failed) or (status == "Others" and row_status != common.status.running and row_status != common.status.passed and row_status != common.status.failed):
            return 1
        else:
            return 0

    def update_main_table_item(self, block, version, flow, task, key, value, color=None, selected=None, flags=None, mode='update', row=None, vrow=None):
        """
        mode 'create' for draw Main TAB table totally, create only.
        mode 'update' for update Main TAB table, modify Main table item.
        """
        task_obj = self.job_manager.all_tasks[block][version][flow][task]
        row_info_list = ['Block', 'Version', 'Flow', 'Task', 'Status', 'Check', 'Summary', 'Job', 'Runtime', 'Xterm', 'BuildStatus', 'RunStatus', 'CheckStatus', 'SummarizeStatus', 'ReleaseStatus']
        visible_row = -1

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

            self.generate_main_table_item(vrow, row, task_obj, row_info_list, key, value, color, selected, flags)
            return

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

    def generate_main_table_item(self, visible_row, row, task_obj, row_info_list, key, value, color=None, selected=None, flags=None):
        if (key != 'Check') and (key != 'Summary') and (key != 'Xterm'):

            item = QTableWidgetItem(value)

            if 'Status' in key and not color:
                if re.search(r'pass', str(value), flags=re.I):
                    color = QColor(0, 204, 68)
                elif re.search(r'fail', str(value), flags=re.I):
                    color = Qt.red
                elif re.search(r'undefined', str(value), flags=re.I):
                    color = QColor(133, 51, 255)
                elif re.search(r'ing', str(value), flags=re.I):
                    color = QColor(255, 153, 0)
                elif re.search(r'queue', str(value), flags=re.I):
                    color = QColor(51, 153, 255)
                elif re.search(r'kill', str(value), flags=re.I):
                    color = Qt.red
                elif re.search(r'skip', str(value), flags=re.I):
                    color = QColor(211, 211, 211)

            if color:
                item.setForeground(QBrush(color))

            if selected:
                item.setCheckState(Qt.Checked)
            else:
                if selected is not None:
                    item.setCheckState(Qt.Unchecked)

            if flags:
                item.setFlags(flags)

            if key == 'Task' and task_obj.skipped:
                item.setForeground(QBrush(QColor(211, 211, 211)))

            self.main_table.setItem(visible_row, row_info_list.index(key), item)

        if (key == 'Check') or (key == 'Summary') or (key == 'Xterm'):
            item = QTableWidgetItem(None)

            if key == 'Check':
                if value == common.status.passed:
                    item.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/check_pass.png'))
                elif value == common.status.failed:
                    item.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/check_fail.png'))
                else:
                    item.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/check_init.png'))

            if key == 'Summary':
                if value == common.status.passed:
                    item.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/summary_pass.png'))
                elif value == common.status.failed:
                    item.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/summary_fail.png'))
                else:
                    item.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/summary_init.png'))

            if key == 'Xterm':
                item.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/other/terminal.png'))

            item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            item.setTextAlignment(Qt.AlignCenter)
            self.main_table.setItem(visible_row, row_info_list.index(key), item)

        if (key == 'Job') and (value is not None):
            if value.startswith('b'):
                item = QTableWidgetItem(value[2:])

            if value.startswith('l'):
                item = QTableWidgetItem(None)

            self.main_table.setItem(visible_row, row_info_list.index(key), item)

    # main_frame (end) #

    # message_frame (start) #
    def gen_message_frame(self):
        self.message_text = QTextEdit(self.message_frame)
        self.message_text.setReadOnly(True)

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
        current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

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
        if task_dic_list is None:
            task_dic_list = []

        if not task_dic_list:
            task_dic_list = list(filter(lambda x: x.get('Selected'), self.main_table_info_list))
            task_dic_list = self.filter_task_before_execute_action(action_name, task_dic_list)

        if not task_dic_list:
            return

        if select_task:
            self.current_selected_task_dic['Selected'] = True
            self.update_main_table_item(self.current_selected_task_dic['Block'], self.current_selected_task_dic['Version'], self.current_selected_task_dic['Flow'], self.current_selected_task_dic['Task'], 'Task', self.current_selected_task_dic['Task'], selected=Qt.Checked)

        self.job_manager.receive_action(action_name, task_dic_list, run_all_steps=run_all_steps)

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
            for row in self.main_table_info_list.keys():
                self.update_main_table_item(self.main_table_info_list[row]['Block'], self.main_table_info_list[row]['Version'], self.main_table_info_list[row]['Flow'], self.main_table_info_list[row]['Task'], 'Task', self.main_table_info_list[row]['Task'], selected=Qt.Checked)
            pass

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

    def send_result_to_user(self):
        if self.send_result and self.send_result_command:
            result_report = self.gen_result_report()

            send_result_command = re.sub('USER', USER, self.send_result_command)
            send_result_command = re.sub('RESULT', result_report, send_result_command)

            self.update_message_text({'message': 'Send result.', 'color': 'black'})
            os.system(send_result_command)

    def gen_result_report(self):
        current_time = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        result_report = str(CWD) + '/.result.' + str(current_time) + '.report'

        with open(result_report, 'w') as RR:
            RR.write('IFP RESULT\n')
            RR.write('User : ' + str(USER) + '\n')
            RR.write('Directory : ' + str(CWD) + '\n')
            RR.write('Config : ' + str(self.ifp_config_file) + '\n')

            status_dic = self.get_status_dic()

            RR.write('Total ' + str(status_dic['Total']) + ' tasks, ' + str(status_dic['Passed']) + ' pass.\n')

        return (result_report)

    def final_close(self):
        self.close_dialog.close()
        self.close()

    def update_runtime(self):
        """
        Update runtime in main table per second
        """
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
            elif status == common.status.killing and runtime == "pending":
                self.update_main_table_item(block, version, flow, task, 'Runtime', "00:00:00")

    def update_filter_branches_menu(self):
        for branch in self.branch_row_mapping.keys():
            self.update_main_view(view_name='branch', item_text=branch, item_select_status=True, mode='no-update')
            self.task_window.update_config_view(view_name='branch', item_text=branch, item_select_status=True)

    def update_filter_block_menu(self):
        for branch in self.block_row_mapping.keys():
            self.update_main_view(view_name='block', item_text=branch, item_select_status=True, mode='no-update')
            self.task_window.update_config_view(view_name='block', item_text=branch, item_select_status=True)

    def show_or_hide_detail_status(self):
        action = self.sender()

        if action.isChecked():
            self.show_detail_status()
        else:
            self.hide_detail_status()

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
                        item_label.setFixedWidth(100)
                        item_widget = QLineEdit()
                        item_label.setFont(QFont('Calibri', 10))
                        line_layout.addWidget(item_label)
                        line_layout.addWidget(item_widget)

                        if self.ifp_env_setting[main_category][child_category][item]['value']:
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

                        if not raw_setting == new_setting:
                            self.ifp_env_setting[main_category][child_category][item]['value'] = new_setting

                            if not child_category == 'Process management':
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
    item_select_status_signal = pyqtSignal(str, str, bool)
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
        self.top_layout.setStretch(0, 10)
        self.top_layout.setStretch(1, 1)

        self.main_widget.setLayout(self.main_layout)
        self.tree.clicked.connect(self.generate_selection)
        self.frame0.setFixedWidth(150)

        self.gen_tree()
        self.main_layout.addWidget(self.frame0)

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

            model.itemChanged.connect(functools.partial(self.update_view, view_name))
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

    def update_view(self, view_name, item=None):
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

        if view_name and item:
            item_status = True if item.checkState() else False
            self.item_select_status_signal.emit(view_name, item.text(), item_status)

        progress_dialog.close()

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

            common.run_command_for_api(common.expand_var(item['COMMAND'], ifp_var_dic=var_dic), '', common.expand_var(item['PATH'], ifp_var_dic=var_dic), gating_flag=True)


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


# Main Process #
def main():
    (config_file, debug, auto_execute_action) = readArgs()
    QApplication.setFont(QFont("Calibri", 10))
    app = QApplication(sys.argv)
    execute_action_for_pre_cfg()
    MainWindow(config_file, debug, auto_execute_action)
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
