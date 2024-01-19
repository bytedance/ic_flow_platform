# -*- coding: utf-8 -*-

import os
import re
import sys
import stat
import shutil
import argparse
import datetime
import getpass
import importlib
from matplotlib import colors
import functools

# Import PyQt5 libraries.
import yaml
from PyQt5.QtCore import pyqtSignal, QTimer, Qt
from PyQt5.QtWidgets import QMainWindow, QApplication, QAction, QMessageBox, QTabWidget, QWidget, QFrame, QGridLayout, QTextEdit, QTableWidget, QHeaderView, QTableWidgetItem, QFileDialog, QTreeWidget, QTreeWidgetItem, QDialog, QCheckBox, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QMenu, QTableView, QProgressDialog, QSplitter
from PyQt5.QtGui import QIcon, QBrush, QColor, QFont, QStandardItem, QStandardItemModel

# Import local python files.
import parse_config
from user_config import UserConfig, DefaultConfig
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
IFP_VERSION = 'V1.2'

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

    # Contral arguments.
    parser.add_argument('-build', '--build',
                        default=False,
                        action='store_true',
                        help='Enable build function, create run directories/files.')
    parser.add_argument('-run', '--run',
                        default=False,
                        action='store_true',
                        help='Enable run function, run tasks/corners.')
    parser.add_argument('-check', '--check',
                        default=False,
                        action='store_true',
                        help='Enable check function, check results of tasks/corners with specified checklist.')
    parser.add_argument('-summarize', '--summarize',
                        default=False,
                        action='store_true',
                        help='Enable summarize function, get summary report with specified information requirement.')
    parser.add_argument('-release', '--release',
                        default=False,
                        action='store_true',
                        help='Enable release function, release current result to release directory.')
    parser.add_argument('-d', '--debug',
                        default=False,
                        action='store_true',
                        help='Enable debug mode, will print more useful messages.')

    args = parser.parse_args()

    # get config_file.
    args.config_file = os.path.abspath(args.config_file)

    if not os.path.exists(args.config_file):
        gen_config_file(args.config_file)

    # Argument '--run' and '--check', must do checklist after running tasks/corners.
    if args.run and (not args.check):
        args.check = True

    return (args.config_file, args.build, args.run, args.check, args.summarize, args.release, args.debug)


def gen_config_file(config_file):
    """
    Generate configure file.
    """
    print('>>> Generating empty configure file "' + str(config_file) + '" ...')

    try:
        with open(config_file, 'w') as CF:
            CF.write('')
    except Exception as error:
        print('*Error*: Failed on creating config file "' + str(config_file) + '".')
        print('         ' + str(error))
        sys.exit(1)


# GUI (start) #
class MainWindow(QMainWindow):
    def __init__(self, config_file, build, run, check, summarize, release, debug):
        super().__init__()

        # IFP input parameters
        self.config_file = config_file
        self.build = build
        self.run = run
        self.check = check
        self.summarize = summarize
        self.release = release
        self.debug = debug

        # IFP global ENV flag (USER), detailed description in def parse_ifp_env_setting
        self.config_setting = ConfigSetting()
        self.config_dic = self.config_setting.config_dic

        for key, value in self.config_dic.items():
            setattr(self, key, value)

        # IFP global ENV flag (SYSTEM)
        self.config_obj = None
        self.main_table_info_list = None
        self.status_filt_flag = ''
        self.ifp_env_setting = None

        # Show or hide column flags
        self.view_status_dic = {}
        self.view_detail_column_dic = {}
        self.header_column_mapping = {}
        self.branch_row_mapping = {}
        self.block_row_mapping = {}

        # Update ifp.py and user_config.py parameters when start ifp
        self.job_manager = JobManager(self, debug=self.debug)
        self.job_manager.disable_gui_signal.connect(self.disable_gui)
        self.job_manager.finish_signal.connect(self.send_result_to_user)
        self.job_manager.close_signal.connect(self.final_close)
        self.update_dict_by_load_config_file(self.config_file)
        self.default_config_file = self.config_obj.default_config_file
        self.env_dic = self.config_obj.env_dic
        self.user_config = UserConfig(self, self.config_file, self.default_config_file)
        self.user_config.save_flag.connect(lambda: self.save_config_file(save_mode='keep'))
        self.parse_ifp_env_setting()

        # IFP sub windows
        self.setting_window = None
        self.config_view_window = None
        self.flow_multiple_select_window = None
        self.default_config_window = None
        self.task_multiple_select_window = None

        # Generate the GUI.
        self.main_table_title_list = ['Block', 'Version', 'Flow', 'Vendor', 'Branch', 'Task', 'Status', 'Check', 'Summary', 'Job', 'Runtime', 'Xterm', 'Build Status', 'Run Status', 'Check Status', 'Summarize Status', 'Release Status']
        self.status_title_list = ['Build Status', 'Run Status', 'Check Status', 'Summarize Status', 'Release Status']
        self.operation_title_list = ['Status', 'Check', 'Summary', 'Job', 'Runtime', 'Xterm']
        self.gen_gui()

        # Switch to "CONFIG" tab if not BLOCK information on uer config file.
        if not self.config_dic['BLOCK']:
            self.top_tab.setCurrentWidget(self.config_tab)

        # Execute specified functions after GUI started.
        QTimer.singleShot(1000, self.execute_func)

        # System log
        self.ifp_start_time = datetime.datetime.now()
        self.write_system_log('start ifp')

        # Define QTimer
        timer = QTimer(self)
        timer.start(1000)
        timer.timeout.connect(self.update_runtime)

        # Init close dialog
        self.close_dialog = QProgressDialog()
        self.init_close_dialog()

    def init_close_dialog(self):
        self.close_dialog.setCancelButton(None)
        self.close_dialog.setWindowFlags(Qt.CustomizeWindowHint | Qt.WindowTitleHint | Qt.WindowStaysOnTopHint)
        self.close_dialog.setWindowTitle('Please Wait')
        self.close_dialog.setLabelText('Killing Tasks. . .')
        self.close_dialog.setRange(0, 0)
        self.close_dialog.close()

    def disable_gui(self, signal):
        if signal:
            self.top_tab.setTabEnabled(1, False)
            self.setting_action.setEnabled(False)
            self.dependency_action.setEnabled(False)
        else:
            self.top_tab.setTabEnabled(1, True)
            self.setting_action.setEnabled(True)
            self.dependency_action.setEnabled(True)

    def tab_changed(self, index):
        if index == 1:
            self.user_config.update_stage_flag = True
        elif index == 2:
            self.user_config.update_stage_flag = False

    # GUI (start) #
    def gen_gui(self):
        # Gen meanbar and toolbar.
        self.gen_menubar()
        self.gen_toolbar()

        # Gen widgets.
        self.top_tab = QTabWidget(self)
        self.setCentralWidget(self.top_tab)
        self.top_tab.currentChanged.connect(self.tab_changed)

        self.env_tab = QWidget()
        self.top_tab.addTab(self.env_tab, 'ENV')

        self.config_tab = QWidget()
        self.top_tab.addTab(self.config_tab, 'CONFIG')

        self.main_tab = QWidget()
        self.top_tab.addTab(self.main_tab, 'MAIN')
        self.top_tab.setCurrentWidget(self.main_tab)

        self.gen_env_tab()
        self.gen_main_tab()
        self.gen_config_tab()

        # Set GUI size, title and icon.
        self.gui_width = 1200
        self.gui_height = 607
        self.resize(self.gui_width, self.gui_height)
        self.setWindowTitle('IC FLow Platform')
        self.setWindowIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/logo/ifp.png'))
        common_pyqt5.center_window(self)

        if self.fullscreen_flag:
            self.showMaximized()

    # menubar (start) #
    def gen_menubar(self):
        menubar = self.menuBar()

        # File
        self.setting_action = QAction('Setting', self)
        self.setting_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/settings.png'))
        self.setting_action.triggered.connect(self.gen_setting_gui)

        self.dependency_action = QAction('Set Dependency', self)
        self.dependency_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/settings.png'))
        self.dependency_action.triggered.connect(self.user_config.set_dependency_priority)

        save_status_file_action = QAction('Save Status File', self)
        save_status_file_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/red/save_file.png'))
        save_status_file_action.triggered.connect(self.save_status_file)

        load_status_file_action = QAction('Load Status File', self)
        load_status_file_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/add_file.png'))
        load_status_file_action.triggered.connect(self.load_status_file)

        save_config_file_action = QAction('Save Config File', self)
        save_config_file_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/red/save_file.png'))
        save_config_file_action.triggered.connect(lambda: self.save_config_file(save_mode='save_as_other_file'))

        load_config_file_action = QAction('Load Config File', self)
        load_config_file_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/add_file.png'))
        load_config_file_action.triggered.connect(self.load_config_file)

        exit_action = QAction('&Exit', self)
        exit_action.setShortcut('Ctrl+E')
        exit_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/exit.png'))
        exit_action.triggered.connect(self.close)

        file_menu = menubar.addMenu('File')
        file_menu.addSeparator()
        file_menu.addAction(save_status_file_action)
        file_menu.addAction(load_status_file_action)
        file_menu.addAction(save_config_file_action)
        file_menu.addAction(load_config_file_action)
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

        setup_menu = menubar.addMenu('Setup')
        setup_menu.addAction(self.setting_action)
        setup_menu.addAction(self.dependency_action)

        # Contral
        contral_all_action = QAction('&All_Steps', self)
        contral_all_action.setShortcut('Ctrl+A')
        contral_all_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/other/all.png'))
        contral_all_action.triggered.connect(lambda: self.execute_action(common.action.run, run_all_steps=True))

        contral_build_action = QAction('&' + common.action.build, self)
        contral_build_action.setShortcut('Ctrl+B')
        contral_build_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/other/build.png'))
        contral_build_action.triggered.connect(lambda: self.execute_action(common.action.build))

        contral_run_action = QAction('&' + common.action.run, self)
        contral_run_action.setShortcut('Ctrl+R')
        contral_run_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/run.png'))
        contral_run_action.triggered.connect(lambda: self.execute_action(common.action.run))

        contral_kill_action = QAction('&' + common.action.kill, self)
        contral_kill_action.setShortcut('Ctrl+K')
        contral_kill_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/kill.png'))
        contral_kill_action.triggered.connect(lambda: self.execute_action(common.action.kill))

        contral_check_action = QAction('&' + common.action.check, self)
        contral_check_action.setShortcut('Ctrl+C')
        contral_check_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/checklist.png'))
        contral_check_action.triggered.connect(lambda: self.execute_action(common.action.check))

        contral_summary_action = QAction('&' + common.action.summarize, self)
        contral_summary_action.setShortcut('Ctrl+S')
        contral_summary_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/summary.png'))
        contral_summary_action.triggered.connect(lambda: self.execute_action(common.action.summarize))

        contral_release_action = QAction('&' + common.action.release, self)
        contral_release_action.setShortcut('Ctrl+Shift+R')
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
        tool_menu.addAction(config_default_action)

        # Help
        about_action = QAction('&About', self)
        about_action.setShortcut('Ctrl+A')
        about_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/copyright.png'))
        about_action.triggered.connect(self.show_about)

        help_menu = menubar.addMenu('Help')
        help_menu.addAction(about_action)

    def show_about(self):
        QMessageBox.about(self, 'IC flow Platform', """                                                       Version """ + str(IFP_VERSION) + """

Copyright © 2021 ByteDance. All Rights Reserved worldwide.""")

    def gen_setting_gui(self):
        self.parse_ifp_env_setting()
        self.setting_window = SettingWindow(self.ifp_env_setting)
        self.setting_window.setWindowModality(Qt.ApplicationModal)
        self.setting_window.update_setting_flag.connect(self.update_ifp_setting)
        self.setting_window.init_ui()
        self.setting_window.show()

    def gen_main_view_gui(self):
        self.config_view_window = ViewWindow(status_dic=self.view_status_dic, disable_list=self.view_disable_item_list, title='Main View')
        self.config_view_window.setWindowModality(Qt.ApplicationModal)
        self.config_view_window.item_select_status_signal.connect(self.update_main_view)
        self.config_view_window.init_ui()
        self.config_view_window.show()

    def update_main_view(self, view_name, item_text, item_select_status):
        if view_name == 'column':
            if item_text not in self.header_column_mapping.keys():
                return

            if item_select_status:
                self.main_table.showColumn(self.header_column_mapping[item_text])
            else:
                self.main_table.hideColumn(self.header_column_mapping[item_text])

        elif view_name == 'branch':
            if item_select_status:
                # block hidden remain hidden
                exclude_visible_row_list = []

                for block in self.block_row_mapping.keys():
                    if (block in self.view_status_dic['block'].keys()) and (not self.view_status_dic['block'][block]):
                        exclude_visible_row_list += self.block_row_mapping[block]

                for row in self.branch_row_mapping[item_text]:
                    if row not in exclude_visible_row_list:
                        self.main_table_info_list[row]['Visible'] = True
            else:
                for row in self.branch_row_mapping[item_text]:
                    self.main_table_info_list[row]['Visible'] = False

        elif view_name == 'block':
            # Update self.main_table_info_list (Visible or not).
            if item_select_status:
                # branch hidden remain hidden
                exclude_visible_row_list = []

                for branch in self.branch_row_mapping.keys():
                    if (branch in self.view_status_dic['branch'].keys()) and (not self.view_status_dic['branch'][branch]):
                        exclude_visible_row_list += self.branch_row_mapping[branch]

                for row in self.block_row_mapping[item_text]:
                    if row not in exclude_visible_row_list:
                        self.main_table_info_list[row]['Visible'] = True
            else:
                for row in self.block_row_mapping[item_text]:
                    self.main_table_info_list[row]['Visible'] = False

        self.view_status_dic[view_name][item_text] = item_select_status
        self.update_main_table()
        self.top_tab.setCurrentIndex(2)
        self.update_status_table()

    def gen_config_view_gui(self):
        self.config_view_window = ViewWindow(status_dic=self.user_config.view_status_dic, title='Config View')
        self.config_view_window.setWindowModality(Qt.ApplicationModal)
        self.config_view_window.item_select_status_signal.connect(self.user_config.update_config_view)
        self.config_view_window.init_ui()
        self.config_view_window.show()

    def parse_ifp_env_setting(self):
        self.ifp_env_setting = {'Project settings': {'Project': {'Project name': {'widget_type': 'edit',
                                                                                  'value': self.config_dic['PROJECT']},
                                                                 'User group': {'widget_type': 'edit',
                                                                                'value': self.config_dic['GROUP'] if 'GROUP' in self.config_dic.keys() else None},
                                                                 'Default setting': {'widget_type': 'edit',
                                                                                     'value': self.default_config_file,
                                                                                     'split_line': True},
                                                                 'Auto import tasks': {'widget_type': 'select',
                                                                                       'value': self.auto_import_tasks,
                                                                                       'description': 'Import all tasks when add new block/version'}}
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
                                                                                                   'description': 'Remind user to confirm if rerun PASSED tasks'}
                                                                           },

                                                    }
                                }

    def update_ifp_setting(self, settings, need_reload_flag):
        self.ifp_env_setting = settings

        if not settings['Project settings']['Project']['Default setting']['value'] == self.default_config_file:
            self.default_config_file = settings['Project settings']['Project']['Default setting']['value']
            self.user_config.default_yaml = settings['Project settings']['Project']['Default setting']['value']
            self.user_config.update_default_setting()

        if not settings['Project settings']['Project']['Auto import tasks']['value'] == self.auto_import_tasks:
            self.config_setting.update_local_config('auto_import_tasks', settings['Project settings']['Project']['Auto import tasks']['value'])
            self.auto_import_tasks = settings['Project settings']['Project']['Auto import tasks']['value']

        if not settings['System settings']['Process management']['Confirm rerun tasks']['value'] == self.rerun_flag:
            self.config_setting.update_local_config('rerun_flag', settings['System settings']['Process management']['Confirm rerun tasks']['value'])
            self.rerun_flag = settings['System settings']['Process management']['Confirm rerun tasks']['value']

        if not settings['System settings']['Process management']['Rerun before view']['value'] == self.rerun_check_or_summarize_before_view:
            self.config_setting.update_local_config('rerun_check_or_summarize_before_view', settings['System settings']['Process management']['Rerun before view']['value'])
            self.rerun_check_or_summarize_before_view = settings['System settings']['Process management']['Rerun before view']['value']

        if not settings['System settings']['Process management']['Ignore fail tasks']['value'] == self.ignore_fail:
            self.config_setting.update_local_config('ignore_fail', settings['System settings']['Process management']['Ignore fail tasks']['value'])
            self.ignore_fail = settings['System settings']['Process management']['Ignore fail tasks']['value']

        if not settings['System settings']['Process management']['Send results']['value'] == self.send_result:
            self.config_setting.update_local_config('send_result', settings['System settings']['Process management']['Send results']['value'])
            self.send_result = settings['System settings']['Process management']['Send results']['value']

        if not settings['System settings']['Appearance']['Fullscreen mode']['value'] == self.fullscreen_flag:
            self.config_setting.update_local_config('fullscreen_flag', settings['System settings']['Appearance']['Fullscreen mode']['value'])
            self.fullscreen_flag = settings['System settings']['Appearance']['Fullscreen mode']['value']

        self.config_setting.save_local_config()

        if need_reload_flag:
            self.user_config.save()

    # menubar (end) #

    # toolbar (start) #
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
                                          'Vendor': main_table_info['Vendor'],
                                          'Branch': main_table_info['Branch'],
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

        if status_file:
            self.update_message_text({'message': 'Load status with file "' + str(status_file) + '".', 'color': 'black'})

            # Get status from status file.
            with open(status_file, 'rb') as SF:
                saved_status_dic = yaml.load(SF, Loader=yaml.FullLoader)

            # Update self.main_table_info_list with new status_file.
            for (i, main_table_info) in enumerate(self.main_table_info_list):
                for (j, status_dic) in saved_status_dic.items():
                    if (main_table_info['Block'] == status_dic['Block']) and (main_table_info['Version'] == status_dic['Version']) and (main_table_info['Flow'] == status_dic['Flow']) and (main_table_info['Vendor'] == status_dic['Vendor']) and (main_table_info['Branch'] == status_dic['Branch']) and (
                            main_table_info['Task'] == status_dic['Task']):
                        self.main_table_info_list[i]['Status'] = status_dic['Status']
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

    def load_config_file(self, config_file=''):
        if not config_file:
            (config_file, file_type) = QFileDialog.getOpenFileName(self, 'Load config file', '.', '*')

        if config_file:
            self.save_status_file('./.ifp.status.yaml')
            self.update_message_text({'message': 'Load config file "' + str(config_file) + '".', 'color': 'black'})

            # Update self.config_dic and self.main_table_info_list with new config_file.
            self.update_dict_by_load_config_file(config_file)
            # Update related GUI parts.
            self.update_env_table()
            self.update_sidebar_tree()
            self.update_main_table()
            self.update_status_table()

            self.user_config.config_path_edit.setText(self.config_file)
            self.user_config.load()
            self.update_filter_branches_menu()
            self.load_status_file('./.ifp.status.yaml')

    def update_dict_by_load_config_file(self, config_file):
        self.config_file = config_file
        self.config_obj = parse_config.Config(config_file)
        self.config_dic = self.config_obj.config_dic
        self.main_table_info_list = self.config_obj.main_table_info_list
        self.job_manager.update(self.config_dic)

        self.branch_row_mapping = {}
        self.block_row_mapping = {}

        self.view_status_dic['block'] = {}
        self.view_status_dic['branch'] = {}

        for (i, main_table_info) in enumerate(self.main_table_info_list):
            branch = main_table_info['Branch']
            self.view_status_dic['branch'][branch] = True

            if branch not in self.branch_row_mapping.keys():
                self.branch_row_mapping[branch] = [i]
            else:
                self.branch_row_mapping[branch].append(i)

            block = main_table_info['Block']
            self.view_status_dic['block'][block] = True

            if block not in self.block_row_mapping.keys():
                self.block_row_mapping[block] = [i]
            else:
                self.block_row_mapping[block].append(i)

    def save_config_file(self, save_mode='keep'):
        """
        save_mode=keep : user can not define new ifp.cfg.yaml
        save_mode=<others> : filedialog for user to define new ifp.cfg.yaml
        """
        config_file = self.user_config.config_path_edit.text()

        if not save_mode == 'keep':
            (config_file, file_type) = QFileDialog.getSaveFileName(self, 'Save config file', config_file, 'Config Files (*.yaml)')
            self.user_config.parsing_final_setting()

        if config_file:
            self.user_config.final_setting['PROJECT'] = self.ifp_env_setting['Project settings']['Project']['Project name']['value']
            self.user_config.final_setting['GROUP'] = self.ifp_env_setting['Project settings']['Project']['User group']['value']
            self.user_config.final_setting['VAR']['BSUB_QUEUE'] = self.ifp_env_setting['System settings']['Cluster management']['$BSUB_QUEUE']['value']

            with open(config_file, 'w', encoding='utf-8') as SF:
                yaml.dump(dict(self.user_config.final_setting), SF, indent=4, sort_keys=False)

            self.load_config_file(config_file)
            self.user_config.config_path_edit.setText(config_file)

    # Process status/config files (end) #

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

        bmonitor_location = shutil.which('bmonitor')

        if bmonitor_location:
            os.system('bmonitor')
        else:
            bmonitor = str(os.environ['IFP_INSTALL_PATH']) + '/tools/lsfMonitor/monitor/bin/bmonitor'

            if os.path.exists(bmonitor):
                (return_code, stdout, stderr) = common.run_command(bmonitor)

                if return_code != 0:
                    QMessageBox.warning(self, 'LSF Monitor Warning', 'Failed on starting "bmonitor".')
            else:
                QMessageBox.warning(self, 'LSF Monitor Warning', 'Not find "bmonitor" on system.')

    def edit_config_default(self):
        self.default_config_window = DefaultConfig(self.default_config_file)
        self.default_config_window.save_signal.connect(self.user_config.update_default_setting)
        self.default_config_window.show()

    # Select flows (start) #
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
                self.update_main_table_item(main_table_info['Block'], main_table_info['Version'], main_table_info['Flow'], main_table_info['Vendor'], main_table_info['Branch'], main_table_info['Task'], 'Task', main_table_info['Task'], selected=status)

    # Select flows (end) #

    # Select tasks (start) #
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
                self.update_main_table_item(main_table_info['Block'], main_table_info['Version'], main_table_info['Flow'], main_table_info['Vendor'], main_table_info['Branch'], main_table_info['Task'], 'Task', main_table_info['Task'], selected=status)

    # Select tasks (end) #

    # def run_all_steps(self):
    #     build_obj = self.execute_action('Build', run=False)
    #     run_obj = self.execute_action('Run', run=False)
    #     check_obj = self.execute_action('Check', run=False)
    #     sum_obj = self.execute_action('Summary', run=False)
    #
    #     build_obj.start()
    #     build_obj.finish_signal.connect(lambda: run_obj.start())
    #     run_obj.finish_signal.connect(lambda: check_obj.start())
    #     check_obj.finish_signal.connect(lambda: sum_obj.start())

    # toolbar (end) #

    # env_tab (start) #
    def gen_env_tab(self):
        # self.env_frame
        self.env_frame = QFrame(self.env_tab)
        self.env_frame.setFrameShadow(QFrame.Raised)
        self.env_frame.setFrameShape(QFrame.Box)

        # Grid
        env_tab_grid = QGridLayout()
        env_tab_grid.addWidget(self.env_frame, 0, 0)
        self.env_tab.setLayout(env_tab_grid)

        # Gen self.env_frame.
        self.gen_env_frame()

    def gen_env_frame(self):
        # self.env_table
        self.env_table = QTableWidget(self.env_frame)

        # Grid
        env_frame_grid = QGridLayout()
        env_frame_grid.addWidget(self.env_table, 0, 0)
        self.env_frame.setLayout(env_frame_grid)

        # Gen self.env_table.
        self.gen_env_table()

    def gen_env_table(self):
        self.env_table.setShowGrid(True)
        self.env_table.verticalHeader().setVisible(False)

        # Gen env_table title.
        self.env_table.setColumnCount(2)
        self.env_table.setHorizontalHeaderLabels(['Env_Variable', 'Value'])
        self.env_table.setColumnWidth(0, 250)
        self.env_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)

        self.update_env_table()

    def update_env_table(self):
        # Initial, clean up self.env_table.
        self.env_table.setRowCount(0)

        # Update env_table content.
        row_num = 0

        self.env_table.setRowCount(len(self.env_dic.keys()))

        for (key, value) in self.env_dic.items():
            key_item = QTableWidgetItem(key)
            key_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            value_item = QTableWidgetItem(value)
            value_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)

            self.env_table.setItem(row_num, 0, key_item)
            self.env_table.setItem(row_num, 1, value_item)

            # Transfer environment settings into python.
            os.environ[key] = value

            row_num += 1

    # env_tab (end) #

    # config_tab (start) #
    def gen_config_tab(self):
        config_widget = self.user_config.init_ui()

        # Grid
        config_tab_grid = QGridLayout()
        config_tab_grid.addWidget(config_widget, 0, 0)

        self.config_tab.setLayout(config_tab_grid)
        self.user_config.load()

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

        # self.message_frame
        self.message_frame = QFrame(self.main_tab)
        self.message_frame.setFrameShadow(QFrame.Raised)
        self.message_frame.setFrameShape(QFrame.Box)

        # self.main_splitter
        self.main_splitter = QSplitter(self)
        self.main_splitter.setOrientation(0)
        self.main_splitter.addWidget(self.main_frame)
        self.main_splitter.addWidget(self.message_frame)

        self.main_splitter.setStretchFactor(0, 3)
        self.main_splitter.setStretchFactor(1, 1)

        # Grid
        main_tab_grid = QGridLayout()

        main_tab_grid.addWidget(self.sidebar_tree, 0, 0, 1, 1)
        main_tab_grid.addWidget(self.status_table, 1, 0, 2, 1)
        main_tab_grid.addWidget(self.main_splitter, 0, 1, 3, 2)

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
        self.gen_message_frame()

    # sidebar_tree (start) #
    def gen_sidebar_tree(self):
        self.sidebar_tree.setColumnCount(1)
        self.sidebar_tree.setHeaderLabels(['     Project - Block', ])
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
        root_item = QTreeWidgetItem(self.sidebar_tree)
        root_item.setText(0, self.config_dic['PROJECT'])
        root_item.setIcon(0, QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/blue/project.png'))

        block_list = self.get_all_blocks()

        for block in block_list:
            child_item = self.get_sidebar_tree_block_item(block, Qt.Checked)
            root_item.addChild(child_item)

        self.sidebar_tree.expandAll()

    def get_sidebar_tree_block_item(self, block, status=Qt.Checked):
        item = QTreeWidgetItem()
        item.setText(0, block)
        item.setIcon(0, QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/blue/block.png'))

        return item

    def get_all_blocks(self):
        block_list = []

        for main_table_info in self.main_table_info_list:
            if main_table_info['Block'] not in block_list:
                block_list.append(main_table_info['Block'])

        return block_list

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

        # Grid
        main_frame_grid = QGridLayout()
        main_frame_grid.addWidget(self.main_table, 0, 0)
        self.main_frame.setLayout(main_frame_grid)

        # Gen self.main_table.
        self.gen_main_table()

    def main_table_title_click_behavior(self, index):
        if index == 5:
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

                    self.update_main_table_item(main_table_info['Block'], main_table_info['Version'], main_table_info['Flow'], main_table_info['Vendor'], main_table_info['Branch'], main_table_info['Task'], 'Task', main_table_info['Task'], selected=status)

    def main_table_item_click_behavior(self, item):
        if item is not None:
            item_row = item.row()
            item_column = item.column()
            visible_row = -1

            for (row, main_table_info) in enumerate(self.main_table_info_list):
                if main_table_info['Visible'] and self.filt_task_status(main_table_info):
                    visible_row += 1

                    if visible_row == item_row:
                        if item_column == 5:
                            if item.checkState() == 0:
                                status = Qt.Unchecked
                                self.main_table_info_list[row]['Selected'] = False
                                self.update_message_text({'message': 'Row ' + str(visible_row+1) + ', task "' + str(main_table_info['Task']) + '" is un-selected.', 'color': 'black'})
                            else:
                                status = Qt.Checked
                                self.main_table_info_list[row]['Selected'] = True
                                self.update_message_text({'message': 'Row ' + str(visible_row+1) + ', task "' + str(main_table_info['Task']) + '" is selected.', 'color': 'black'})

                            self.update_main_table_item(main_table_info['Block'], main_table_info['Version'], main_table_info['Flow'], main_table_info['Vendor'], main_table_info['Branch'], main_table_info['Task'], 'Task', main_table_info['Task'], selected=status)
                        elif item_column == 7:
                            self.pop_check(main_table_info)
                        elif item_column == 8:
                            self.pop_summary(main_table_info)
                        elif item_column == 9:
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
                        elif item_column == 11:
                            self.pop_xterm(main_table_info)

    def open_file(self, item):
        task = self.config_dic['BLOCK'][item.Block][item.Version][item.Flow][item.Vendor][item.Branch][item.Task]

        (log_file, file_type) = QFileDialog.getOpenFileName(self, 'Open file', str(task.PATH), 'LOG (*.log)')

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
            command = str(bmonitor) + ' -t JOB -dl -j ' + str(jobid)
            (return_code, stdout, stderr) = common.run_command(command)

            if return_code != 0:
                QMessageBox.warning(self, 'LSF Monitor Warning', 'Failed on getting job information for jobid "' + str(jobid) + '".')
        else:
            QMessageBox.warning(self, 'LSF Monitor Warning', 'Not find "bmonitor" on system.')

    def pop_check(self, item):
        self.execute_action(common.action.check_view, task_dic_list=[item, ])

    def pop_summary(self, item):
        self.execute_action(common.action.summarize_view, task_dic_list=[item, ])

    def pop_xterm(self, item):
        task = self.config_dic['BLOCK'][item.Block][item.Version][item.Flow][item.Vendor][item.Branch][item.Task]
        if 'COMMON' in task.ACTION:
            command = str(self.xterm_command) + ' "cd ' + str(task.PATH) + '; ' + str(task.ACTION['COMMON']['XTERM_COMMAND']) + '; exec ' + str(os.environ['SHELL']) + '"'
        else:
            command = str(self.xterm_command) + ' "cd ' + str(task.PATH) + '; exec ' + str(os.environ['SHELL']) + '"'

        thread_run = common.ThreadRun()
        thread_run.run([command, ])

    def gen_main_table(self):
        self.main_table.setShowGrid(True)
        self.main_table.verticalHeader().setVisible(True)
        self.main_table.setEditTriggers(QTableWidget.NoEditTriggers)

        # Gen self.main_table title.
        self.main_table.setColumnCount(len(self.main_table_title_list))
        self.main_table.setHorizontalHeaderLabels(self.main_table_title_list)

        self.main_table.setItemDelegate(common_pyqt5.CustomDelegate(wrap_columns=[0, 1, 4]))

        self.main_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.main_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.main_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)

        self.main_table_header = self.main_table.horizontalHeader()
        self.main_table_header.setContextMenuPolicy(Qt.CustomContextMenu)
        self.main_table_header.customContextMenuRequested.connect(self.generate_select_menu)

        self.main_table.setColumnWidth(2, 60)
        self.main_table.setColumnWidth(3, 80)
        self.main_table.setColumnWidth(5, 140)
        self.main_table.setColumnWidth(6, 140)
        self.main_table.setColumnWidth(7, 50)
        self.main_table.setColumnWidth(8, 70)
        self.main_table.setColumnWidth(9, 70)
        self.main_table.setColumnWidth(10, 70)
        self.main_table.setColumnWidth(11, 50)

        # gen open file menu
        self.main_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.main_table.customContextMenuRequested.connect(self.generate_openfile_menu)

        # Update self.main_table.
        self.update_main_table()
        self.hide_detail_status()

    def generate_select_menu(self, pos):
        menu = QMenu()
        column = self.main_table_header.logicalIndexAt(pos)

        if column == 5:
            select_flows_action = QAction('Select Flows', self)
            select_flows_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/red/F.png'))
            select_flows_action.triggered.connect(self.select_flows)
            menu.addAction(select_flows_action)

            select_steps_action = QAction('Select Tasks', self)
            select_steps_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/red/T.png'))
            select_steps_action.triggered.connect(self.select_tasks)
            menu.addAction(select_steps_action)

        menu.exec_(self.main_table.mapToGlobal(pos))

    def generate_openfile_menu(self, pos):
        menu = QMenu()
        column = self.main_table_header.logicalIndexAt(pos)
        current_selected_row = self.main_table.indexAt(pos).row()
        filter_main_table_info_list = []

        for (row, main_table_info) in enumerate(self.main_table_info_list):
            if main_table_info['Visible']:
                filter_main_table_info_list.append(main_table_info)

        task_dic = filter_main_table_info_list[current_selected_row]

        if column == 5:
            open_file_action = QAction('Open File', self)
            open_file_action.triggered.connect(lambda: self.open_file(task_dic))
            menu.addAction(open_file_action)

        menu.exec_(self.main_table.mapToGlobal(pos))

    def update_main_table(self):
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
                   'Flow': {'current': '', 'last': '', 'start_row': 0, 'end_row': 0, 'column': 2},
                   'Vendor': {'current': '', 'last': '', 'start_row': 0, 'end_row': 0, 'column': 3},
                   'Branch': {'current': '', 'last': '', 'start_row': 0, 'end_row': 0, 'column': 4}}

        visible_row = -1

        for main_table_info in self.main_table_info_list:
            if not main_table_info['Visible'] or not self.filt_task_status(main_table_info):
                continue

            visible_row += 1

            # Set main_table items.
            block = main_table_info['Block']
            version = main_table_info['Version']
            flow = main_table_info['Flow']
            vendor = main_table_info['Vendor']
            branch = main_table_info['Branch']
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
            row_dic['Vendor']['current'] = vendor
            row_dic['Branch']['current'] = branch

            self.update_main_table_item(block, version, flow, vendor, branch, task, 'Block', block, flags=Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self.update_main_table_item(block, version, flow, vendor, branch, task, 'Version', version, flags=Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self.update_main_table_item(block, version, flow, vendor, branch, task, 'Flow', flow, flags=Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self.update_main_table_item(block, version, flow, vendor, branch, task, 'Vendor', vendor, flags=Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self.update_main_table_item(block, version, flow, vendor, branch, task, 'Branch', branch, flags=Qt.ItemIsSelectable | Qt.ItemIsEnabled)

            if main_table_info['Selected']:
                self.update_main_table_item(block, version, flow, vendor, branch, task, 'Task', task, selected=Qt.Checked)
            else:
                self.update_main_table_item(block, version, flow, vendor, branch, task, 'Task', task, selected=Qt.Unchecked)

            self.update_main_table_item(block, version, flow, vendor, branch, task, 'Status', status)
            self.update_main_table_item(block, version, flow, vendor, branch, task, 'BuildStatus', buildstatus)
            self.update_main_table_item(block, version, flow, vendor, branch, task, 'RunStatus', runstatus)
            self.update_main_table_item(block, version, flow, vendor, branch, task, 'CheckStatus', checkstatus)
            self.update_main_table_item(block, version, flow, vendor, branch, task, 'SummarizeStatus', summarizestatus)
            self.update_main_table_item(block, version, flow, vendor, branch, task, 'ReleaseStatus', releasestatus)
            self.update_main_table_item(block, version, flow, vendor, branch, task, 'Check', check)
            self.update_main_table_item(block, version, flow, vendor, branch, task, 'Summary', summary)
            self.update_main_table_item(block, version, flow, vendor, branch, task, 'Job', job)
            self.update_main_table_item(block, version, flow, vendor, branch, task, 'Runtime', runtime)
            self.update_main_table_item(block, version, flow, vendor, branch, task, 'Xterm', xterm)

            # Merge Block/Version/Flow/Vendor/Branch items.
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

        if check_status in [common.status.checking, "{} {}".format(common.action.check, common.status.passed), "{} {}".format(common.action.check, common.status.failed)]:
            row_status = check_status

        if status == "" or status == "Total" or (status == "Run" and row_status == common.status.running) or (status == "Passed" and row_status == common.status.passed) or (status == "Failed" and row_status == common.status.failed) or (status == "Others" and row_status != common.status.running and row_status != common.status.passed and row_status != common.status.failed):
            return 1
        else:
            return 0

    def update_main_table_item(self, block, version, flow, vendor, branch, task, key, value, color=None, selected=None, flags=None):
        row_info_list = ['Block', 'Version', 'Flow', 'Vendor', 'Branch', 'Task', 'Status', 'Check', 'Summary', 'Job', 'Runtime', 'Xterm', 'BuildStatus', 'RunStatus', 'CheckStatus', 'SummarizeStatus', 'ReleaseStatus']
        visible_row = -1

        for (row, main_table_info) in enumerate(self.main_table_info_list):
            if main_table_info['Visible'] and self.filt_task_status(main_table_info):
                visible_row += 1

            if (block == main_table_info['Block']) and (version == main_table_info['Version']) and (flow == main_table_info['Flow']) and (vendor == main_table_info['Vendor']) and (branch == main_table_info['Branch']) and (task == main_table_info['Task']):
                # Update self.main_table_info_list.
                self.main_table_info_list[row][key] = value

                if selected:
                    self.main_table_info_list[row]['Selected'] = True
                else:
                    if selected is not None:
                        self.main_table_info_list[row]['Selected'] = False

                # Update self.main_table.
                if main_table_info['Visible'] and self.filt_task_status(main_table_info):
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

                        if color:
                            item.setForeground(QBrush(color))

                        if selected:
                            item.setCheckState(Qt.Checked)
                        else:
                            if selected is not None:
                                item.setCheckState(Qt.Unchecked)

                        if flags:
                            item.setFlags(flags)

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
        message_frame_grid.addWidget(self.message_text, 0, 0)
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

    def write_system_log(self, message):
        if not install_config.system_log_path == '':
            if not os.path.exists(install_config.system_log_path):
                common.run_command('touch %s' % install_config.system_log_path)
                os.chmod(install_config.system_log_path, 0o0777)

            time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            user = USER
            host = os.popen('hostname').read().strip()

            with open(install_config.system_log_path, 'a') as f:
                f.write('[%s][%s@%s]: %s\n' % (time, user, host, message))

    # GUI function (start) #
    def execute_func(self):
        """
        Execute specified functions after GUI started.
        """
        if self.build:
            self.execute_action(common.action.build)

        if self.run:
            self.execute_action(common.action.run)

        if self.check:
            self.execute_action(common.action.check)

        if self.summarize:
            self.execute_action(common.action.summarize)

        if self.release:
            self.execute_action(common.action.release)

    def execute_action(self, action_name, task_dic_list=None, run_all_steps=False):
        if task_dic_list is None:
            task_dic_list = []

        if not task_dic_list:
            task_dic_list = list(filter(lambda x: x.get('Selected'), self.main_table_info_list))
            task_dic_list = self.filt_task_dic_list(action_name, task_dic_list)

        if not task_dic_list:
            return

        self.job_manager.receive_action(action_name, task_dic_list, run_all_steps=run_all_steps)

    def filt_task_dic_list(self, action_name, task_dic_list):
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
                        self.update_message_text({'message': '*Warning*: Can\'t execute {} action to {} {} {} {} {} {} because it\'s {}.'.format(action_name, task['Block'], task['Version'], task['Flow'], task['Vendor'], task['Branch'], task['Task'], task['Status']), 'color': 'orange'})
                else:
                    filtered_task_dic_list.append(task)
        elif action_name == "Kill":
            for task in task_dic_list:
                filtered_task_dic_list.append(task)

        return filtered_task_dic_list

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
                self.rerun_flag = False

            if choice == QMessageBox.Cancel:
                task_dic_list = []
            elif choice == QMessageBox.No:
                task_dic_list = normal_task_dic_list

        return task_dic_list

    def update_task_status(self, task_obj, action, status):
        block, version, flow, vendor, branch, task = task_obj.block, task_obj.version, task_obj.flow, task_obj.vendor, task_obj.branch, task_obj.task
        self.config_dic['BLOCK'][block][version][flow][vendor][branch][task].Status = status
        self.update_main_table_item(block, version, flow, vendor, branch, task, 'Status', status)

        if re.match(r'(\S+)\s+(\S+)', status, flags=re.I):
            status_value = re.match(r'(\S+)\s+(\S+)', status, flags=re.I).group(2)
        else:
            status_value = status

        if action == common.action.build:
            self.update_main_table_item(block, version, flow, vendor, branch, task, 'BuildStatus', status_value)
        elif action == common.action.run:
            self.update_main_table_item(block, version, flow, vendor, branch, task, 'RunStatus', status_value)
        elif action == common.action.check:
            self.update_main_table_item(block, version, flow, vendor, branch, task, 'CheckStatus', status_value)
            self.update_main_table_item(block, version, flow, vendor, branch, task, 'Check', status_value)
        elif action == common.action.summarize:
            self.update_main_table_item(block, version, flow, vendor, branch, task, 'SummarizeStatus', status_value)
            self.update_main_table_item(block, version, flow, vendor, branch, task, 'Summary', status_value)
        elif action == common.action.release:
            self.update_main_table_item(block, version, flow, vendor, branch, task, 'ReleaseStatus', status_value)

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
            RR.write('Config : ' + str(self.config_file) + '\n')

            status_dic = self.get_status_dic()

            RR.write('Total ' + str(status_dic['Total']) + ' tasks, ' + str(status_dic['Passed']) + ' pass.\n')

        return (result_report)

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

        self.user_config.thread.quit()
        event.accept()

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
            vendor = main_table_info['Vendor']
            branch = main_table_info['Branch']
            task = main_table_info['Task']
            status = main_table_info['Status']
            runtime = main_table_info['Runtime']

            if status == common.status.running and runtime and runtime != "pending":
                runtime = datetime.datetime.strptime(runtime, "%H:%M:%S")
                runtime += datetime.timedelta(seconds=1)
                self.update_main_table_item(block, version, flow, vendor, branch, task, 'Runtime', runtime.strftime("%H:%M:%S"))

            elif status == common.status.killing and runtime == "pending":
                self.update_main_table_item(block, version, flow, vendor, branch, task, 'Runtime', "00:00:00")

    def update_filter_branches_menu(self):
        for branch in self.branch_row_mapping.keys():
            self.update_main_view(view_name='branch', item_text=branch, item_select_status=True)
            self.user_config.update_config_view(view_name='branch', item_text=branch, item_select_status=True)

    def update_filter_block_menu(self):
        for branch in self.branch_row_mapping.keys():
            self.update_main_view(view_name='block', item_text=branch, item_select_status=True)
            self.user_config.update_config_view(view_name='block', item_text=branch, item_select_status=True)

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


# GUI (end) #


class SettingWindow(QMainWindow):
    update_setting_flag = pyqtSignal(dict, bool)

    def __init__(self, ifp_env_setting):
        super().__init__()

        self.ifp_env_setting = ifp_env_setting

        self.top_widget = QWidget()
        self.top_layout = QVBoxLayout()
        self.top_widget.setLayout(self.top_layout)
        self.setCentralWidget(self.top_widget)

        self.main_widget = QWidget()
        self.main_layout = QHBoxLayout()
        self.main_widget.setLayout(self.main_layout)

        self.button_widget = QWidget()
        self.button_layout = QHBoxLayout()
        self.button_widget.setLayout(self.button_layout)

        self.save_button = QPushButton('SAVE')
        self.cancel_button = QPushButton('CANCEL')
        self.save_button.clicked.connect(self.save)
        self.cancel_button.clicked.connect(self.close)
        self.save_button.setFont(QFont('Calibri', 10))
        self.cancel_button.setFont(QFont('Calibri', 10))

        self.frames = {}
        self.current_frame = None

        self.tree = QTreeWidget()
        self.tree.clicked.connect(self.generate_setting)
        self.frame0 = QFrame(self.main_widget)
        self.frame1 = QFrame(self.main_widget)
        self.frame0.setFixedWidth(250)
        self.frame1.setFixedWidth(700)

        self.need_reload_flag = False

    def init_ui(self):
        self.main_layout.addWidget(self.frame_items())
        self.main_layout.addWidget(self.frame_setting())

        self.button_layout.addStretch(1)
        self.button_layout.addWidget(self.save_button)
        self.button_layout.addWidget(self.cancel_button)

        self.top_layout.addWidget(self.main_widget)
        self.top_layout.addWidget(self.button_widget)

        self.top_layout.setStretch(0, 10)
        self.top_layout.setStretch(1, 1)

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

                    elif self.ifp_env_setting[main_category][child_category][item]['widget_type'] == 'select':
                        item_widget = QCheckBox(item)
                        line_layout.addWidget(item_widget)

                        if self.ifp_env_setting[main_category][child_category][item]['value'] is True:
                            item_widget.setChecked(True)
                        else:
                            item_widget.setChecked(False)

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

        self.resize(1000, 500)
        self.setWindowTitle('Settings')
        common_pyqt5.center_window(self)

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
        default_yaml_path = common.get_default_yaml_path(project, group)

        for main_category in self.ifp_env_setting.keys():
            for child_category in self.ifp_env_setting[main_category].keys():
                for item in self.ifp_env_setting[main_category][child_category].keys():
                    if self.ifp_env_setting[main_category][child_category][item]['widget_type'] == 'edit':
                        raw_setting = self.ifp_env_setting[main_category][child_category][item]['value']
                        new_setting = self.ifp_env_setting[main_category][child_category][item]['widget'].text()

                        if item == 'Default setting':
                            if not new_setting == default_yaml_path:
                                reply = QMessageBox.question(self, "Warning", "Flow will parse default setting from : \n %s \ndue to Project(%s) and Group(%s), press Yes to save setting or press No to keep raw setting." % (default_yaml_path, project, group))

                                if reply == QMessageBox.Yes:
                                    self.ifp_env_setting[main_category][child_category][item]['value'] = default_yaml_path
                                    self.need_reload_flag = True
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

                        if not raw_setting == new_setting:
                            self.ifp_env_setting[main_category][child_category][item]['value'] = new_setting

        self.update_setting_flag.emit(self.ifp_env_setting, self.need_reload_flag)
        self.close()


class ConfigSetting():
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

    def __init__(self, status_dic=None, disable_list=None, title='Main View'):
        super().__init__()

        if disable_list is None:
            disable_list = []

        if status_dic is None:
            status_dic = {}

        self.view_select_dic = status_dic
        self.disable_list = disable_list
        self.title = title

    def init_ui(self):
        self.top_widget = QWidget()
        self.top_layout = QVBoxLayout()
        self.top_widget.setLayout(self.top_layout)
        self.setCentralWidget(self.top_widget)

        self.main_widget = QWidget()
        self.main_layout = QGridLayout()
        self.main_layout.setColumnStretch(0, 1)
        self.main_layout.setColumnStretch(0, 6)
        self.main_widget.setLayout(self.main_layout)

        self.top_layout.addWidget(self.main_widget)
        self.top_layout.setStretch(0, 10)
        self.top_layout.setStretch(1, 1)

        self.tables = {}
        self.current_frame = None

        self.tree = QTreeWidget()
        self.tree.clicked.connect(self.generate_selection)
        self.frame0 = QFrame(self.main_widget)
        self.frame0.setFixedWidth(150)

        self.setFixedSize(500, 400)
        self.setWindowTitle(self.title)
        common_pyqt5.center_window(self)

        self.gen_tree()
        self.main_layout.addWidget(self.frame0, 0, 0)

        self.gen_table()

        self.current_frame = self.tables['column']
        self.current_frame.show()

    def gen_table(self):
        for view_name in self.view_select_dic:
            table = QTableView(self.main_widget)
            model = QStandardItemModel()
            table.setModel(model)
            table.setFixedWidth(300)
            table.setShowGrid(False)
            table.setSortingEnabled(True)
            table.verticalHeader().setVisible(False)
            table.horizontalHeader().setVisible(False)

            model.setColumnCount(2)
            table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
            table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)

            item_list = list(self.view_select_dic[view_name].keys())

            item_len = len(item_list)

            if item_len % 2 != 0:
                row_num = int(item_len / 2) + 1
            else:
                row_num = int(item_len / 2)

            model.setRowCount(row_num)

            row = 0
            column = 0

            for item in item_list:
                if row >= row_num:
                    column = 1
                    row = 0

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

                model.setItem(row, column, check_item)

                row += 1

            model.itemChanged.connect(functools.partial(self.update_view, view_name))
            self.tables[view_name] = table
            self.main_layout.addWidget(table, 0, 1)
            table.hide()

    def generate_selection(self):
        view_name = self.tree.currentItem().text(0)

        if view_name in self.view_select_dic.keys():
            self.current_frame.hide()
            table = self.tables[view_name]
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

        branch_child = QTreeWidgetItem(row_parent)
        branch_child.setText(0, 'branch')
        branch_child.setFont(0, QFont('Calibri', 10))
        branch_child.setExpanded(False)

        layout.addWidget(self.tree)

        return self.frame0

    def update_view(self, view_name, item=None):
        if view_name and item:
            item_status = True if item.checkState() else False
            self.item_select_status_signal.emit(view_name, item.text(), item_status)


# Main Process #
def main():
    (config_file, build, run, check, summarize, release, debug) = readArgs()
    QApplication.setFont(QFont("Calibri", 10))
    app = QApplication(sys.argv)
    mw = MainWindow(config_file, build, run, check, summarize, release, debug)
    mw.show()
    sys.exit(app.exec_())

    print('')
    print('Done')


if __name__ == '__main__':
    main()
