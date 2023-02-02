# -*- coding: utf-8 -*-

import os
import re
import sys
import shutil
import argparse
import datetime
import copy
import getpass

# Import PyQt5 libraries.
import yaml
from PyQt5.QtCore import pyqtSignal, QTimer, Qt
from PyQt5.QtWidgets import QMainWindow, QApplication, QAction, qApp, QMessageBox, QTabWidget, QWidget, QFrame, QGridLayout, QTextEdit, QTableWidget, QHeaderView, QTableWidgetItem, QFileDialog, QTreeWidget, QTreeWidgetItem, QDialog, QCheckBox, QVBoxLayout
from PyQt5.QtGui import QIcon, QBrush, QColor

# Import local python files.
import parse_config
import function
from user_config import UserConfig, DefaultConfig

# Import common python files.
sys.path.append(str(os.environ['IFP_INSTALL_PATH']) + '/common')
import common
import common_pyqt5

# Import config settings.
sys.path.append(str(os.environ['IFP_INSTALL_PATH']) + '/config')
import config

os.environ['PYTHONUNBUFFERED'] = '1'
CWD = os.getcwd()
USER = getpass.getuser()
IFP_VERSION = 'V1.0 (2023.2.1)'


#### Process input arguments (start) ####
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
    parser.add_argument('-summary', '--summary',
                        default=False,
                        action='store_true',
                        help='Enable summary function, get summary report with specified information requirement.')
    parser.add_argument('-post_run', '--post_run',
                        default=False,
                        action='store_true',
                        help='Enable post run function, execute user specified command.')
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

    return(args.config_file, args.build, args.run, args.check, args.summary, args.post_run, args.release, args.debug)


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


#####################
#### GUI (start) ####
#####################
class MainWindow(QMainWindow):
    def __init__(self, config_file, build, run, check, summary, post_run, release, debug):
        super().__init__()

        self.config_file = config_file
        self.build = build
        self.run = run
        self.check = check
        self.summary = summary
        self.post_run = post_run
        self.release = release
        self.debug = debug

        self.ignore_fail = False
        self.xterm_mode = False
        self.send_result = False

        self.config_obj = parse_config.Config(self.config_file)
        self.config_dic = self.config_obj.config_dic
        self.main_table_info_list = self.config_obj.main_table_info_list

        self.default_config_file = str(os.environ['IFP_INSTALL_PATH']) + '/config/default.yaml'
        self.user_config = UserConfig(self.config_file, self.default_config_file)
        self.user_config.save_flag.connect(self.save_config_file)

        # Generate the GUI.
        self.gen_gui()

        # Switch to "CONFIG" tab if not BLOCK information on uer config file.
        if not self.config_dic['BLOCK']:
            self.top_tab.setCurrentWidget(self.config_tab)

        # Execute specified functions after GUI started.
        QTimer.singleShot(1000, self.execute_func)

    #### GUI (start) ####
    def gen_gui(self):
        # Gen meanbar and toolbar.
        self.gen_menubar()
        self.gen_toolbar()

        # Gen widgets.
        self.top_tab = QTabWidget(self)
        self.setCentralWidget(self.top_tab)

        self.env_tab = QWidget()
        self.top_tab.addTab(self.env_tab, 'ENV')

        self.config_tab = QWidget()
        self.top_tab.addTab(self.config_tab, 'CONFIG')

        self.main_tab = QWidget()
        self.top_tab.addTab(self.main_tab, 'MAIN')
        self.top_tab.setCurrentWidget(self.main_tab)

        self.gen_env_tab()
        self.gen_config_tab()
        self.gen_main_tab()

        # Set GUI size, title and icon.
        self.gui_width = 1200
        self.gui_height = 607
        self.resize(self.gui_width, self.gui_height)
        self.setWindowTitle('IC FLow Platform')
        self.setWindowIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/logo/ifp.png'))
        common_pyqt5.move_gui_to_window_center(self)

    ## menubar (start) ##
    def gen_menubar(self):
        menubar = self.menuBar()

        # File
        save_status_file_action = QAction('Save Status File', self)
        save_status_file_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/red/save_file.png'))
        save_status_file_action.triggered.connect(self.save_status_file)

        load_status_file_action = QAction('Load Status File', self)
        load_status_file_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/add_file.png'))
        load_status_file_action.triggered.connect(self.load_status_file)

        load_config_file_action = QAction('Load Config File', self)
        load_config_file_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/add_file.png'))
        load_config_file_action.triggered.connect(self.load_config_file)

        exit_action = QAction('&Exit', self)
        exit_action.setShortcut('Ctrl+E')
        exit_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/exit.png'))
        exit_action.triggered.connect(qApp.quit)

        file_menu = menubar.addMenu('File')
        file_menu.addAction(save_status_file_action)
        file_menu.addAction(load_status_file_action)
        file_menu.addAction(load_config_file_action)
        file_menu.addAction(exit_action)

        # View
        zoom_in_action = QAction('Zoom &In', self)
        zoom_in_action.setShortcut('Ctrl+I')
        zoom_in_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/zoom_in.png'))
        zoom_in_action.triggered.connect(self.zoom_in)

        zoom_out_action = QAction('Zoom &Out', self)
        zoom_out_action.setShortcut('Ctrl+O')
        zoom_out_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/zoom_out.png'))
        zoom_out_action.triggered.connect(self.zoom_out)

        view_menu = menubar.addMenu('View')
        view_menu.addAction(zoom_in_action)
        view_menu.addAction(zoom_out_action)

        # Setup
        select_flows_action = QAction('Select Flows', self)
        select_flows_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/red/F.png'))
        select_flows_action.triggered.connect(self.select_flows)

        select_steps_action = QAction('Select Tasks', self)
        select_steps_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/red/T.png'))
        select_steps_action.triggered.connect(self.select_tasks)

        ignore_fail_action = QAction('Ignore Fail', self, checkable=True)
        ignore_fail_action.triggered.connect(self.setup_ignore_fail)

        xterm_mode_action = QAction('Xterm Mode', self, checkable=True)
        xterm_mode_action.triggered.connect(self.start_xterm_mode)

        send_result_action = QAction('Send Result', self, checkable=True)
        send_result_action.triggered.connect(self.setup_send_result)

        setup_menu = menubar.addMenu('Setup')
        setup_menu.addAction(select_flows_action)
        setup_menu.addAction(select_steps_action)
        setup_menu.addAction(ignore_fail_action)
        setup_menu.addAction(xterm_mode_action)
        setup_menu.addAction(send_result_action)

        # Contral
        contral_all_action = QAction('&All_Steps', self)
        contral_all_action.setShortcut('Ctrl+A')
        contral_all_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/other/all.png'))
        contral_all_action.triggered.connect(self.run_all_steps)

        contral_build_action = QAction('&Build', self)
        contral_build_action.setShortcut('Ctrl+B')
        contral_build_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/other/build.png'))
        contral_build_action.triggered.connect(lambda: self.execute_action('Build'))

        contral_run_action = QAction('&Run', self)
        contral_run_action.setShortcut('Ctrl+R')
        contral_run_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/run.png'))
        contral_run_action.triggered.connect(lambda: self.execute_action('Run'))

        contral_kill_action = QAction('&Kill', self)
        contral_kill_action.setShortcut('Ctrl+K')
        contral_kill_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/kill.png'))
        contral_kill_action.triggered.connect(lambda: self.execute_action('Kill'))

        contral_check_action = QAction('&Check', self)
        contral_check_action.setShortcut('Ctrl+C')
        contral_check_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/checklist.png'))
        contral_check_action.triggered.connect(lambda: self.execute_action('Check'))

        contral_summary_action = QAction('&Summary', self)
        contral_summary_action.setShortcut('Ctrl+S')
        contral_summary_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/summary.png'))
        contral_summary_action.triggered.connect(lambda: self.execute_action('Summary'))

        contral_post_run_action = QAction('&Post Run', self)
        contral_post_run_action.setShortcut('Ctrl+P')
        contral_post_run_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/post_run.png'))
        contral_post_run_action.triggered.connect(lambda: self.execute_action('Post Run'))

        contral_release_action = QAction('&Release', self)
        contral_release_action.setShortcut('Ctrl+Shift+R')
        contral_release_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/release.png'))
        contral_release_action.triggered.connect(lambda: self.execute_action('Release'))

        contral_menu = menubar.addMenu('Control')
        contral_menu.addAction(contral_all_action)
        contral_menu.addAction(contral_build_action)
        contral_menu.addAction(contral_run_action)
        contral_menu.addAction(contral_kill_action)
        contral_menu.addAction(contral_check_action)
        contral_menu.addAction(contral_summary_action)
        contral_menu.addAction(contral_post_run_action)
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
    ## menubar (end) ##

    ## toolbar (start) ##
    def gen_toolbar(self):
        # Run all steps
        run_all_steps_action = QAction('Run All Steps', self)
        run_all_steps_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/other/all.png'))
        run_all_steps_action.triggered.connect(self.run_all_steps)

        self.toolbar = self.addToolBar('Run All Steps')
        self.toolbar.addAction(run_all_steps_action)

        # Build
        build_action = QAction('Build', self)
        build_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/other/build.png'))
        build_action.triggered.connect(lambda: self.execute_action('Build'))

        self.toolbar = self.addToolBar('Build')
        self.toolbar.addAction(build_action)

        # Run
        run_action = QAction('Run', self)
        run_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/run.png'))
        run_action.triggered.connect(lambda: self.execute_action('Run'))

        self.toolbar = self.addToolBar('Run')
        self.toolbar.addAction(run_action)

        # Kill
        kill_action = QAction('Kill', self)
        kill_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/kill.png'))
        kill_action.triggered.connect(lambda: self.execute_action('Kill'))

        self.toolbar = self.addToolBar('Kill')
        self.toolbar.addAction(kill_action)

        # Check
        check_action = QAction('Check', self)
        check_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/checklist.png'))
        check_action.triggered.connect(lambda: self.execute_action('Check'))

        self.toolbar = self.addToolBar('Check')
        self.toolbar.addAction(check_action)

        # Summary
        summary_action = QAction('Summary', self)
        summary_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/summary.png'))
        summary_action.triggered.connect(lambda: self.execute_action('Summary'))

        self.toolbar = self.addToolBar('Summary')
        self.toolbar.addAction(summary_action)

        # Post Run
        post_run_action = QAction('Post Run', self)
        post_run_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/post_run.png'))
        post_run_action.triggered.connect(lambda: self.execute_action('Post Run'))

        self.toolbar = self.addToolBar('Post Run')
        self.toolbar.addAction(post_run_action)

        # Release
        release_action = QAction('Release', self)
        release_action.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/release.png'))
        release_action.triggered.connect(lambda: self.execute_action('Release'))

        self.toolbar = self.addToolBar('Release')
        self.toolbar.addAction(release_action)

    # Process status/config files (start) #
    def save_status_file(self, status_file=''):
        if not status_file:
            (status_file, file_type) = QFileDialog.getSaveFileName(self, 'Save status file', '.', 'YAML (*.yaml)')

        if status_file:
            self.update_message_text('Save status into file "' + str(status_file) + '".')

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
                                          'Job': main_table_info['Job'],
                                          'Runtime': main_table_info['Runtime']}

            with open(status_file, 'w', encoding='utf-8') as SF:
                yaml.dump(main_table_info_dic, SF, indent=4, sort_keys=False)

    def load_status_file(self, status_file=''):
        if not status_file:
            (status_file, file_type) = QFileDialog.getOpenFileName(self, 'Load status file', '.', 'YAML (*.yaml)')

        if status_file:
            self.update_message_text('Load status with file "' + str(status_file) + '".')

            # Get status from status file.
            with open(status_file, 'rb') as SF:
                saved_status_dic = yaml.load(SF, Loader=yaml.FullLoader)

            # Update self.main_table_info_list with new status_file.
            for (i, main_table_info) in enumerate(self.main_table_info_list):
                for (j, status_dic) in saved_status_dic.items():
                    if (main_table_info['Block'] == status_dic['Block']) and (main_table_info['Version'] == status_dic['Version']) and (main_table_info['Flow'] == status_dic['Flow']) and (main_table_info['Vendor'] == status_dic['Vendor']) and (main_table_info['Branch'] == status_dic['Branch']) and (main_table_info['Task'] == status_dic['Task']):
                        self.main_table_info_list[i]['Status'] = status_dic['Status']
                        self.main_table_info_list[i]['Job'] = status_dic['Job']
                        self.main_table_info_list[i]['Runtime'] = status_dic['Runtime']

            # Update related GUI parts.
            self.update_main_table()
            self.update_status_table()

    def load_config_file(self, config_file=''):
        if not config_file:
            (config_file, file_type) = QFileDialog.getOpenFileName(self, 'Load config file', '.', 'YAML (*.yaml)')

        if config_file:
            self.update_message_text('Load config file "' + str(config_file) + '".')

            # Update self.config_dic and self.main_table_info_list with new config_file.
            self.config_file = config_file
            self.config_obj = parse_config.Config(self.config_file)
            self.config_dic = self.config_obj.config_dic
            self.main_table_info_list = self.config_obj.main_table_info_list

            # Update related GUI parts.
            self.update_env_table()
            self.update_sidebar_tree()
            self.update_main_table()
            self.update_status_table()

            self.user_config.config_path_edit.setText(self.config_file)
            self.user_config.load()

    def save_config_file(self, config_setting):
        (config_file, file_type) = QFileDialog.getSaveFileName(self, 'Save config file', config_setting[1], 'Config Files (*.yaml)')

        if config_file:
            with open(config_file, 'w', encoding='utf-8') as SF:
                yaml.dump(config_setting[0], SF, indent=4, sort_keys=False)

            self.load_config_file(config_file)
            self.user_config.config_path_edit.setText(config_file)
    # Process status/config files (end) #

    def zoom_in(self):
        self.update_message_text('Zoom in')

        self.gui_height += 30
        self.resize(self.gui_width, self.gui_height)

    def zoom_out(self):
        self.update_message_text('Zoom out')

        self.gui_height -= 30
        self.resize(self.gui_width, self.gui_height)

    def show_lsf_monitor(self):
        self.update_message_text('Show LSF/Openlava information with tool "bmonitor".')

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
        self.class_default_config = DefaultConfig(self.default_config_file)
        self.class_default_config.save_signal.connect(self.user_config.update_default_setting)
        self.class_default_config.show()

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

        return(flow_list)

    def update_flow_select_status(self, flow, flow_select_status):
        if flow_select_status:
            status = True
            self.update_message_text('Flow "' + str(flow) + '" is selected.')
        else:
            status = False
            self.update_message_text('Flow "' + str(flow) + '" is un-selected.')

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

        return(task_list)

    def update_task_select_status(self, task, task_select_status):
        if task_select_status:
            status = True
            self.update_message_text('Task "' + str(task) + '" is selected.')
        else:
            status = False
            self.update_message_text('Task "' + str(task) + '" is un-selected.')

        for main_table_info in self.main_table_info_list:
            if task == main_table_info['Task']:
                self.update_main_table_item(main_table_info['Block'], main_table_info['Version'], main_table_info['Flow'], main_table_info['Vendor'], main_table_info['Branch'], main_table_info['Task'], 'Task', main_table_info['Task'], selected=status)
    # Select tasks (end) #

    def setup_ignore_fail(self, state):
        if state:
            self.ignore_fail = True
        else:
            self.ignore_fail = False

    def start_xterm_mode(self, state):
        if state:
            self.xterm_mode = True
        else:
            self.xterm_mode = False

    def setup_send_result(self, state):
        if state:
            self.send_result = True
        else:
            self.send_result = False

    def run_all_steps(self):
        build_obj = self.execute_action('Build', run=False)
        run_obj = self.execute_action('Run', run=False)
        check_obj = self.execute_action('Check', run=False)
        sum_obj = self.execute_action('Summary', run=False)

        build_obj.start()
        build_obj.finish_signal.connect(lambda: run_obj.start())
        run_obj.finish_signal.connect(lambda: check_obj.start())
        check_obj.finish_signal.connect(lambda: sum_obj.start())
    ## toolbar (end) ##

    ## env_tab (start) ##
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
        env_dic = self.get_env_dic()
        row_num = 0

        self.env_table.setRowCount(len(env_dic.keys()))

        for (key, value) in env_dic.items():
            key_item = QTableWidgetItem(key)
            key_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            value_item = QTableWidgetItem(value)
            value_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)

            self.env_table.setItem(row_num, 0, key_item)
            self.env_table.setItem(row_num, 1, value_item)

            # Transfer environment settings into python.
            os.environ[key] = value

            row_num += 1

    def get_env_dic(self):
        env_dic = {}
        env_file = ''

        if re.match('^.*/csh$', os.environ['SHELL']) or re.match('^.*/tcsh$', os.environ['SHELL']):
            env_file = str(os.environ['IFP_INSTALL_PATH']) + '/config/env.' + str(self.config_dic['PROJECT']) + '.csh'

            if not os.path.exists(env_file):
                env_file = str(os.environ['IFP_INSTALL_PATH']) + '/config/env.csh'
        else:
            env_file = str(os.environ['IFP_INSTALL_PATH']) + '/config/env.' + str(self.config_dic['PROJECT']) + '.sh'

            if not os.path.exists(env_file):
                env_file = str(os.environ['IFP_INSTALL_PATH']) + '/config/env.sh'

        if os.path.exists(env_file):
            command = 'source ' + str(env_file) + '; env'
            (return_code, stdout, stderr) = common.run_command(command)
            env_compile = re.compile('^(\S+?)=(.+)$')

            for line in stdout.decode('utf-8').split('\n'):
                if env_compile.match(line):
                    my_match = env_compile.match(line)

                    if my_match.group(1).startswith('BASH_FUNC_'):
                        continue

                    env_dic.setdefault(my_match.group(1), my_match.group(2))
        else:
            QMessageBox.warning(self, 'Env configuration warning', 'Not find any environment configuration file "' + str(env_file) + '".')

        return(env_dic)
    ## env_tab (end) ##

    ## config_tab (start) ##
    def gen_config_tab(self):
        config_widget = self.user_config.init_ui()

        # Grid
        config_tab_grid = QGridLayout()
        config_tab_grid.addWidget(config_widget, 0, 0)

        self.config_tab.setLayout(config_tab_grid)
        self.user_config.load()
    ## config_tab (end) ##

    ## main_tab (start) ##
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

        # Grid
        main_tab_grid = QGridLayout()

        main_tab_grid.addWidget(self.sidebar_tree, 0, 0, 1, 1)
        main_tab_grid.addWidget(self.status_table, 1, 0, 2, 1)
        main_tab_grid.addWidget(self.main_frame, 0, 1, 2, 2)
        main_tab_grid.addWidget(self.message_frame, 2, 1, 1, 1)

        main_tab_grid.setRowStretch(0, 5)
        main_tab_grid.setRowStretch(1, 1)
        main_tab_grid.setRowStretch(2, 1)

        main_tab_grid.setColumnStretch(0, 1)
        main_tab_grid.setColumnStretch(1, 6)

        self.main_tab.setLayout(main_tab_grid)

        # Gen sub-frames.
        self.gen_sidebar_tree()
        self.gen_status_table()
        self.gen_main_frame()
        self.gen_message_frame()

    # sidebar_tree (start) #
    def gen_sidebar_tree(self):
        self.sidebar_tree.setColumnCount(1)
        self.sidebar_tree.setHeaderLabels(['     Project - Block', ])
        self.sidebar_tree.header().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.sidebar_tree.header().setStretchLastSection(False)

        self.sidebar_tree.itemClicked.connect(self.sidebar_tree_item_click_behavior)

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
                    self.update_message_text('All blocks are selected.')
                else:
                    self.update_message_text('All blocks are un-selected.')
            else:
                if item.checkState(column):
                    self.update_message_text('Block ' + str(item.text(column)) + ' is selected.')
                else:
                    self.update_message_text('Block ' + str(item.text(column)) + ' is un-selected.')

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
        root_item.setCheckState(0, Qt.Checked)
        root_item.setIcon(0, QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/blue/project.png'))

        block_list = self.get_all_blocks()

        for block in block_list:
            child_item = self.get_sidebar_tree_block_item(block, Qt.Checked)
            root_item.addChild(child_item)

        self.sidebar_tree.expandAll()

    def get_sidebar_tree_block_item(self, block, status=Qt.Checked):
        item = QTreeWidgetItem()
        item.setText(0, block)
        item.setCheckState(0, status)
        item.setIcon(0, QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/blue/block.png'))

        return(item)

    def get_all_blocks(self):
        block_list = []

        for main_table_info in self.main_table_info_list:
            if main_table_info['Block'] not in block_list:
                block_list.append(main_table_info['Block'])

        return(block_list)
    # sidebar_tree (end) #

    # status_table (start) #
    def gen_status_table(self):
        self.status_table.setShowGrid(True)

        # Gen self.status_table title.
        self.status_table.setRowCount(5)
        self.status_table.setVerticalHeaderLabels(['Total', 'Pend', 'Run', 'Passed', 'Failed'])

        self.status_table.verticalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.status_table.verticalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.status_table.verticalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.status_table.verticalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.status_table.verticalHeader().setSectionResizeMode(4, QHeaderView.Stretch)

        self.status_table.setColumnCount(1)
        self.status_table.setHorizontalHeaderLabels(['Task Status', ])
        self.status_table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft)
        self.status_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)

        # Update self.status_table.
        self.update_status_table()

    def update_status_table(self):
        status_dic = self.get_status_dic()

        item = QTableWidgetItem(str(status_dic['Total']))
        self.status_table.setItem(0, 0, item)

        item = QTableWidgetItem(str(status_dic['Pend']))
        self.status_table.setItem(1, 0, item)

        item = QTableWidgetItem(str(status_dic['Run']))
        self.status_table.setItem(2, 0, item)

        item = QTableWidgetItem(str(status_dic['Passed']))
        item.setForeground(QBrush(Qt.green))
        self.status_table.setItem(3, 0, item)

        item = QTableWidgetItem(str(status_dic['Failed']))
        item.setForeground(QBrush(Qt.red))
        self.status_table.setItem(4, 0, item)

    def get_status_dic(self):
        status_dic = {'Total': 0, 'Pend': 0, 'Run': 0, 'Passed': 0, 'Failed': 0}

        for main_table_info in self.main_table_info_list:
            status_dic['Total'] += 1
            status = main_table_info['Status']

            if status:
                if (status.find('Queued') >= 0) or (status.find('undefined') >= 0):
                    status_dic['Pend'] += 1
                elif (status == 'Building') or (status == 'Running'):
                    status_dic['Run'] += 1
                elif status.find('PASS') >= 0:
                    status_dic['Passed'] += 1
                elif status.find('FAIL') >= 0:
                    status_dic['Failed'] += 1
            else:
                status_dic['Pend'] += 1

        return(status_dic)
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
            if self.main_table.item(0, 5).checkState() == 0:
                status = Qt.Checked
                self.update_message_text('All tasks are selected.')
            else:
                status = Qt.Unchecked
                self.update_message_text('All tasks are un-selected.')

            for main_table_info in self.main_table_info_list:
                if main_table_info['Visible']:
                    self.update_main_table_item(main_table_info['Block'], main_table_info['Version'], main_table_info['Flow'], main_table_info['Vendor'], main_table_info['Branch'], main_table_info['Task'], 'Task', main_table_info['Task'], selected=status)

    def main_table_item_click_behavior(self, item):
        if item is not None:
            item_row = item.row()
            item_column = item.column()
            visible_row = -1

            for (row, main_table_info) in enumerate(self.main_table_info_list):
                if main_table_info['Visible']:
                    visible_row += 1

                    if visible_row == item_row:
                        if item_column == 5:
                            if item.checkState() == 0:
                                status = Qt.Unchecked
                                self.update_message_text('Row ' + str(visible_row+1) + ', task "' + str(main_table_info['Task']) + '" is un-selected.')
                            else:
                                status = Qt.Checked
                                self.update_message_text('Row ' + str(visible_row+1) + ', task "' + str(main_table_info['Task']) + '" is selected.')

                            self.update_main_table_item(main_table_info['Block'], main_table_info['Version'], main_table_info['Flow'], main_table_info['Vendor'], main_table_info['Branch'], main_table_info['Task'], 'Task', main_table_info['Task'], selected=status)
                        elif item_column == 7:
                            self.pop_check(main_table_info)
                        elif item_column == 8:
                            self.pop_summary(main_table_info)
                        elif item_column == 9:
                            job = main_table_info['Job']

                            if job and str(job).startswith('b'):
                                jobid = str(job)[2:]
                                self.update_message_text('View job information for "' + str(jobid) + '".')
                                self.view_job_info(jobid)
                            elif job and str(job).startswith('l'):
                                pid = str(job)[2:]
                                (return_code, stdout, stderr) = common.run_command('ps -p {}'.format(pid))

                                if not return_code:
                                    process_info = 'local process info:\n{}'.format(stdout.decode('utf-9'))
                                    self.update_message_text(process_info)
                                else:
                                    self.update_message_text('Failed to get local process {} info'.format(pid))
                        elif item_column == 11:
                            self.pop_xterm(main_table_info)

    def view_job_info(self, jobid):
        """
        View job information with tool 'lsfMonitor'.
        """
        self.update_message_text('Show job information for jobid "' + str(jobid) + '".')

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
        task = self.config_dic['BLOCK'][item.Block][item.Version][item.Flow][item.Vendor][item.Branch][item.Task]

        if 'CHECK' in task.ACTION.keys():
            check_path = task.ACTION['CHECK']['PATH'] or task.PATH
            rpt = task.ACTION['CHECK']['REPORT_FILE']

            if not re.match('^/.*$', rpt):
                rpt = str(check_path) + '/' + str(rpt)

            if (not os.path.exists(rpt)) or (not os.path.exists(check_path)):
                self.execute_action('Check', task_dic_list=[item, ])

            if os.path.exists(rpt) and os.path.exists(check_path):
                self.execute_action('Check View', task_dic_list=[item, ])

    def pop_summary(self, item):
        task = self.config_dic['BLOCK'][item.Block][item.Version][item.Flow][item.Vendor][item.Branch][item.Task]

        if 'SUMMARY' in task.ACTION.keys():
            sum_path = task.ACTION['SUMMARY']['PATH'] or task.PATH
            rpt = task.ACTION['SUMMARY']['REPORT_FILE']

            if not re.match('^/.*$', rpt):
                rpt = str(sum_path) + '/' + str(rpt)

            if (not os.path.exists(rpt)) or (not os.path.exists(sum_path)):
                self.execute_action('Summary', task_dic_list=[item, ])

            if os.path.exists(rpt) and os.path.exists(sum_path):
                self.execute_action('Summary View', task_dic_list=[item, ])

    def pop_xterm(self, item):
        task = self.config_dic['BLOCK'][item.Block][item.Version][item.Flow][item.Vendor][item.Branch][item.Task]
        command = 'xterm -e "cd ' + str(task.PATH) + '; ' + str(os.environ['SHELL']) + '"'
        thread_run = common.ThreadRun()
        thread_run.run([command, ])

    def gen_main_table(self):
        self.main_table.setShowGrid(True)
        self.main_table.verticalHeader().setVisible(True)

        # Gen self.main_table title.
        main_table_title_list = ['Block', 'Version', 'Flow', 'Vendor', 'Branch', 'Task', 'Status', 'Check', 'Summary', 'Job', 'Runtime', 'Xterm']
        self.main_table.setColumnCount(len(main_table_title_list))
        self.main_table.setHorizontalHeaderLabels(main_table_title_list)

        self.main_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.main_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.main_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)

        self.main_table.setColumnWidth(2, 60)
        self.main_table.setColumnWidth(3, 80)
        self.main_table.setColumnWidth(5, 140)
        self.main_table.setColumnWidth(6, 140)
        self.main_table.setColumnWidth(7, 50)
        self.main_table.setColumnWidth(8, 70)
        self.main_table.setColumnWidth(9, 60)
        self.main_table.setColumnWidth(10, 70)
        self.main_table.setColumnWidth(11, 50)

        # Update self.main_table.
        self.update_main_table()

    def update_main_table(self):
        # Initial, clean up self.main_table.
        self.main_table.setRowCount(0)

        # Set row count.
        row_count = 0

        for main_table_info in self.main_table_info_list:
            if main_table_info['Visible']:
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
            if not main_table_info['Visible']:
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
            self.update_main_table_item(block, version, flow, vendor, branch, task, 'Task', task, selected=True)
            self.update_main_table_item(block, version, flow, vendor, branch, task, 'Status', status)
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

                if merge_mark or (row_dic[key]['end_row'] > row_dic[key]['start_row']) or (visible_row == row_count-1):
                    if row_dic[key]['end_row'] > row_dic[key]['start_row']:
                        self.main_table.setSpan(row_dic[key]['start_row'], row_dic[key]['column'], row_dic[key]['end_row']-row_dic[key]['start_row']+1, 1)
                        merge_mark = True
                else:
                    merge_mark = False

                row_dic[key]['last'] = row_dic[key]['current']

    def update_main_table_item(self, block, version, flow, vendor, branch, task, key, value, color=None, selected=None, flags=None):
        row_info_list = ['Block', 'Version', 'Flow', 'Vendor', 'Branch', 'Task', 'Status', 'Check', 'Summary', 'Job', 'Runtime', 'Xterm']
        visible_row = -1

        for (row, main_table_info) in enumerate(self.main_table_info_list):
            if main_table_info['Visible']:
                visible_row += 1

            if (block == main_table_info['Block']) and (version == main_table_info['Version']) and (flow == main_table_info['Flow']) and (vendor == main_table_info['Vendor']) and (branch == main_table_info['Branch']) and (task == main_table_info['Task']):
                # Update self.main_table_info_list.
                if (key != 'Check') and (key != 'Summary') and (key != 'Xterm'):
                    self.main_table_info_list[row][key] = value

                if selected:
                    self.main_table_info_list[row]['Selected'] = True
                else:
                    if selected is not None:
                        self.main_table_info_list[row]['Selected'] = False

                # Update self.main_table.
                if main_table_info['Visible']:
                    if (key != 'Check') and (key != 'Summary') and (key != 'Xterm'):
                        item = QTableWidgetItem(value)

                        if key == 'Status' and not color:
                            if re.search(r'pass',  str(value), flags=re.I):
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
                        item = QTableWidgetItem(value)

                        if key == 'Check':
                            item.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/checklist.png'))

                        if key == 'Summary':
                            item.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/office/summary.png'))

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

        # Grid
        message_frame_grid = QGridLayout()
        message_frame_grid.addWidget(self.message_text, 0, 0)
        self.message_frame.setLayout(message_frame_grid)

        self.update_message_text('Welcome to IC Flow Platform')

    def update_message_text(self, message):
        current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.message_text.insertPlainText('[' + str(current_time) + ']    ' + str(message) + '\n')
        common_pyqt5.set_text_cursor_position(self.message_text, 'end')
    # message_frame (end) #
    ## main_tab (end) ##
    #### GUI (end) ####

    #### GUI function (start) ####
    def execute_func(self):
        """
        Execute specified functions after GUI started.
        """
        if self.build:
            self.execute_action('Build')

        if self.run:
            self.execute_action('Run')

        if self.check:
            self.execute_action('Check')

        if self.summary:
            self.execute_action('Summary')

        if self.post_run:
            self.execute_action('Post Run')

        if self.release:
            self.execute_action('Release')

    def filter_task(self, main_table_info_list, query):
        """
        return item complying the query schema
        query should be staff like 'Block=="blockname" and Flow=="flowname"'
        """
        result = []

        for main_table_info in main_table_info_list:
            context = copy.deepcopy(main_table_info.as_dict())

            if eval(query, context):
                result.append(main_table_info)

        return result

    def prep_tasks(self, main_table_info_list, kind):
        """
        kinds refers to Action names
        """
        selected_tasks = list(filter(lambda x: x.get('Selected'), main_table_info_list))

        if len(selected_tasks) == 0:
            QMessageBox.warning(self, 'Nothing to {}'.format(kind), '*Info*: No task is selected, nothing to be {}'.format(kind))
            return []

        if kind in ['Run', 'Build']:
            tasks_to_build_or_run = self.filter_task(selected_tasks, 'Status!="Running" and Status!="Killing"')

            if not tasks_to_build_or_run:
                QMessageBox.warning(self, 'Nothing to {}'.format(kind), '*Info*: Selected tasks are either running or killing, nothing to be {}'.format(kind))

            return tasks_to_build_or_run
        elif kind == 'Kill':
            running_tasks = self.filter_task(selected_tasks, 'Status=="Running"')

            if not running_tasks:
                QMessageBox.warning(self, 'Nothing to {}'.format(kind), '*Info*: No running tasks are found, nothing to be {}'.format(kind))

            return running_tasks
        elif kind in ['Check', 'Summary', 'Post Run', 'Release']:
            return selected_tasks

        return []

    def execute_action(self, action_name, task_dic_list=[], run=True):
        if not task_dic_list:
            task_dic_list = self.prep_tasks(self.main_table_info_list, action_name)

        if not task_dic_list:
            return

        if action_name == 'Build':
            ifp_obj = function.IfpBuild(task_dic_list, self.config_dic, debug=self.debug)
            self.ic_build = ifp_obj
        elif action_name == 'Run':
            ifp_obj = function.IfpRun(task_dic_list, self.config_dic, debug=self.debug, ignore_fail=self.ignore_fail, xterm_mode=self.xterm_mode)
            self.ic_run = ifp_obj
        elif action_name == 'Kill':
            ifp_obj = function.IfpKill(task_dic_list, self.config_dic, debug=self.debug)
            self.ic_kill = ifp_obj
        elif action_name == 'Check':
            ifp_obj = function.IfpCheck(task_dic_list, self.config_dic, debug=self.debug)
            self.ic_check = ifp_obj
        elif action_name == 'Summary':
            ifp_obj = function.IfpSummary(task_dic_list, self.config_dic, debug=self.debug)
            self.ic_sum = ifp_obj
        elif action_name == 'Post Run':
            ifp_obj = function.IfpPostRun(task_dic_list, self.config_dic, debug=self.debug)
            self.ic_postrun = ifp_obj
        elif action_name == 'Release':
            ifp_obj = function.IfpRelease(task_dic_list, self.config_dic, debug=self.debug)
            self.ic_release = ifp_obj
        elif action_name == 'Check View':
            ifp_obj = function.IfpCheckView(task_dic_list, self.config_dic, debug=self.debug)
            self.ic_check_view = ifp_obj
        elif action_name == 'Summary View':
            ifp_obj = function.IfpSummaryView(task_dic_list, self.config_dic, debug=self.debug)
            self.ic_sum_view = ifp_obj

        # Update main table content.
        if (action_name != 'Check View') and (action_name != 'Summary View'):
            ifp_obj.start_one_signal.connect(self.update_task_status)
            ifp_obj.msg_signal.connect(self.update_message_text)

            if action_name == 'Run':
                ifp_obj.set_one_jobid_signal.connect(self.update_main_table_item)
                ifp_obj.set_run_time_signal.connect(self.update_main_table_item)
                ifp_obj.finish_signal.connect(self.send_result_to_user)

            ifp_obj.finish_one_signal.connect(self.update_task_status)

        if run:
            ifp_obj.start()

        return ifp_obj

    def update_task_status(self, block, version, flow, vendor, branch, task, status):
        self.config_dic['BLOCK'][block][version][flow][vendor][branch][task].Status = status
        self.update_main_table_item(block, version, flow, vendor, branch, task, 'Status', status)
        self.update_status_table()

    def send_result_to_user(self):
        if self.send_result and config.send_result_command:
            result_report = self.gen_result_report()

            send_result_command = re.sub('USER', USER, config.send_result_command)
            send_result_command = re.sub('RESULT', result_report, send_result_command)

            self.update_message_text('Send result.')
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

        return(result_report)


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
        self.resize(180, 40*len(item_list))
        self.setWindowTitle(title)
        common_pyqt5.move_gui_to_window_center(self)

    def update_main_gui(self):
        for (item, item_checkbox) in self.checkbox_dic.items():
            item_status = item_checkbox.isChecked()
            self.item_select_status_signal.emit(item, item_status)
###################
#### GUI (end) ####
###################


################
# Main Process #
################
def main():
    (config_file, build, run, check, summary, post_run, release, debug) = readArgs()

    app = QApplication(sys.argv)
    mw = MainWindow(config_file, build, run, check, summary, post_run, release, debug)
    mw.show()
    sys.exit(app.exec_())

    print('')
    print('Done')


if __name__ == '__main__':
    main()
