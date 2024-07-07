# -*- coding: utf-8 -*-
################################
# File Name   : user_config.py
# Author      : jingfuyi
# Created On  : 2022-09-20 17:46:15
# Description :
################################
import copy
import os
import re
import time
import yaml
import sys
import functools
import graphviz
import shutil
import datetime
import getpass
from screeninfo import get_monitors

from PyQt5.QtWidgets import QWidget, QMainWindow, QAction, QPushButton, QLabel, QHeaderView, QVBoxLayout, QHBoxLayout, QLineEdit, QTableView, QAbstractItemView, QMenu, QToolTip, QDesktopWidget, QMessageBox, QComboBox, QFileDialog, QApplication, QGridLayout, QTreeWidget, QTreeWidgetItem, \
    QTableWidget, QTableWidgetItem, QCompleter, QCheckBox, QStyledItemDelegate
from PyQt5.QtGui import QBrush, QFont, QColor, QStandardItem, QStandardItemModel, QCursor, QPalette, QPixmap
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QThread

import common
import common_pyqt5

os.environ['PYTHONUNBUFFERED'] = '1'

sys.path.append(str(os.environ['IFP_INSTALL_PATH']) + '/config')
sys.path.append(str(os.environ['IFP_INSTALL_PATH']) + '/common')
from config import default_yaml_administrators
from common import parse_user_api, add_api_menu
from common_pyqt5 import Dialog, CustomDelegate, center_window, QComboCheckBox


class AutoVivification(dict):
    def __getitem__(self, item):
        try:
            return dict.__getitem__(self, item)
        except KeyError:
            value = self[item] = type(self)()
            return value


def center(self):
    screen = QDesktopWidget().screenGeometry()
    size = self.geometry()
    self.move(int((screen.width() - size.width()) / 2), int((screen.height() - size.height()) / 2))


def parsing_blank_setting():
    run_method_example = '\n1. *Empty for local*\n2. bsub -q normal -n 8 -R "rusage[mem=80000]" -Is\n3. xterm -e bsub -q normal -n 8 -R "rusage[mem=80000]" -Is'
    blank_setting = {'COMMON': {'XTERM_COMMAND': {'example': ''}
                                },
                     'BUILD': {'PATH': {'example': '${DEFAULT_PATH}'},
                               'COMMAND': {'example': './gen_block_run_dir.pl -c ${BLOCK}.block_flow.configure'},
                               'RUN_METHOD': {'example': run_method_example}
                               },
                     'RUN': {'PATH': {'example': '${DEFAULT_PATH}'},
                             'COMMAND': {'example': 'make presta'},
                             'RUN_METHOD': {'example': run_method_example},
                             'REQUIRED_LICENSE': {'example': '',
                                                  'widget_type': 'button'}
                             },
                     'CHECK': {'PATH': {'example': '${DEFAULT_PATH}/syn_dc'},
                               'COMMAND': {'example': '${IFP_INSTALL_PATH}/function/check/syn/synopsys/syn_synopsys.syn_dc.py -b ${BLOCK}'},
                               'RUN_METHOD': {'example': run_method_example},
                               'VIEWER': {'example': '${IFP_INSTALL_PATH}/function/check/tools/view_checklist_report.py -i'},
                               'REPORT_FILE': {'example': 'file_check/file_check.rpt'}
                               },
                     'SUMMARIZE': {'PATH': {'example': '${DEFAULT_PATH}/syn_dc'},
                                   'COMMAND': {'example': '${IFP_INSTALL_PATH}/function/summary/collect_syn_qor.py'},
                                   'RUN_METHOD': {'example': run_method_example},
                                   'VIEWER': {'example': '/bin/soffice'},
                                   'REPORT_FILE': {'example': 'fv_qor.xlsx'}
                                   },
                     'RELEASE': {'PATH': {'example': '${DEFAULT_PATH}/dc'},
                                 'COMMAND': {'example': 'make release'},
                                 'RUN_METHOD': {'example': run_method_example}
                                 },
                     }

    return blank_setting


def check_task_items(task):
    invalid_dic = {}

    for action in task:
        for item in task[action]:
            if item == 'PATH':
                # PATH must exist
                if not os.path.isdir(task[action][item]):
                    invalid_dic.setdefault(action, []).append(item)

            elif item == 'RUN_METHOD':
                # xterm must be used with -e
                if re.search(r"xterm(?!\s+-e)", task[action][item]):
                    invalid_dic.setdefault(action, []).append(item)

                # Do not allow '/" marks around bsub command
                if re.search(r"(\'\s*bsub.+\')|(\"\s*bsub.+\")", task[action][item]):
                    invalid_dic.setdefault(action, []).append(item)

    return invalid_dic


class UserConfig(QMainWindow):
    save_flag = pyqtSignal(object)

    def __init__(self, ifp_obj, config_file, default_yaml, api_yaml):
        super().__init__()

        self.ifp_obj = ifp_obj
        self.config_file = config_file
        self.default_yaml = default_yaml
        self.api_yaml = api_yaml
        self.default_var = AutoVivification()
        self.default_setting = {}
        self.default_dependency_dic = {}
        self.update_default_setting()
        self.top_widget = QWidget()
        self.top_layout = QVBoxLayout()
        self.top_widget.setLayout(self.top_layout)
        self.setCentralWidget(self.top_widget)

        self.header_menu = QMenu()
        self.hide_column_menu = QMenu()
        self.hide_branches_menu = QMenu()
        self.header_column_mapping = {'Block': 0,
                                      'Version': 1,
                                      'Flow': 2,
                                      'Vendor': 3,
                                      'Branch': 4,
                                      'Task': 5
                                      }

        self.branch_row_mapping = AutoVivification()
        self.block_row_mapping = AutoVivification()
        self.task_row_mapping = AutoVivification()
        self.branch_show_flag = AutoVivification()
        self.view_status_dic = {}

        self.view_status_dic.setdefault('column', {})

        for header in self.header_column_mapping.keys():
            self.view_status_dic['column'][header] = True

        self.setup_table = DraggableTableView()
        self.setup_table.clicked.connect(self.update_status_bar)
        self.setup_table.setMouseTracking(True)
        self.setup_table.entered.connect(self.show_tips)
        self.setup_table.exchange_flag.connect(self.exchange_task)
        self.setup_model = QStandardItemModel(0, 6)
        self.setup_table.setModel(self.setup_model)
        self.setup_table.verticalHeader().setVisible(False)

        self.config_path_widget = QWidget()
        self.config_path_layout = QHBoxLayout()
        self.config_path_widget.setLayout(self.config_path_layout)
        self.config_path_label = QLabel('Config file')
        self.config_path_edit = QLineEdit()
        self.config_path_edit.setText(self.config_file)
        self.config_path_edit.setEnabled(False)

        self.ifp_env_setting = AutoVivification()
        self.user_input = AutoVivification()
        self.user_var = AutoVivification()
        self.detailed_setting = AutoVivification()
        self.blank_setting = parsing_blank_setting()
        self.state = AutoVivification()
        self.version_state = AutoVivification()
        self.dependency_priority = AutoVivification()
        self.dependency_chart = AutoVivification()
        self.item_chart_dic = {}
        self.final_setting = {}
        self.raw_setting = {}
        self.table_info = AutoVivification()
        self.span_info = AutoVivification()

        self.current_selected_row = None
        self.current_selected_column = None
        self.current_selected_block = None
        self.current_selected_version = None
        self.current_selected_flow = None
        self.current_selected_vendor = None
        self.current_selected_branch = None
        self.current_selected_task = None

        self.child = None
        self.compatible_flag = False
        self.disable_gui_flag = False

        self.cwd = os.getcwd()
        center(self)

        self.thread = QThread()
        self.ifp_monitor = IFPMonitor(self)
        self.ifp_monitor.moveToThread(self.thread)
        self.ifp_monitor.message.connect(self.update_state)
        self.thread.started.connect(self.ifp_monitor.run)
        self.thread.start()

    def init_ui(self):
        self.config_path_layout.addWidget(self.config_path_label)
        self.config_path_layout.addWidget(self.config_path_edit)

        header = ['Block', 'Version', 'Flow', 'Vendor', 'Branch', 'Task']

        self.setup_model.setHorizontalHeaderLabels(header)
        self.setup_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.setup_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.setup_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.setup_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.setup_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.setup_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)

        self.setup_table.setShowGrid(True)
        self.setup_table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        self.setup_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.setup_table.customContextMenuRequested.connect(self.generate_menu)
        self.setup_table.setItemDelegate(CustomDelegate(wrap_columns=[0, 1, 3]))

        self.top_layout.addWidget(self.config_path_widget)
        self.top_layout.addWidget(self.setup_table)

        return self.top_widget

    def disable_gui(self):
        self.disable_gui_flag = True

    def enable_gui(self):
        self.disable_gui_flag = False

    def update_status_bar(self, index):
        self.current_selected_row = index.row()
        self.current_selected_column = index.column()

        self.current_selected_block = self.setup_model.index(self.current_selected_row, 0).data()
        self.current_selected_version = self.setup_model.index(self.current_selected_row, 1).data()
        self.current_selected_flow = self.setup_model.index(self.current_selected_row, 2).data()
        self.current_selected_vendor = self.setup_model.index(self.current_selected_row, 3).data()
        self.current_selected_branch = self.setup_model.index(self.current_selected_row, 4).data()
        self.current_selected_task = self.setup_model.index(self.current_selected_row, 5).data()

        all_items = [self.current_selected_block, self.current_selected_version, self.current_selected_flow, self.current_selected_vendor, self.current_selected_branch, self.current_selected_task]
        message_items = []

        for i in range(self.current_selected_column + 1):
            message_items.append(all_items[i])

        self.ifp_obj.update_status_bar(' -> '.join(message_items))

    def show_tips(self, index):

        desktop = QApplication.desktop()
        screen_num = desktop.screenNumber(QCursor.pos())
        screen_rect = desktop.screenGeometry(screen_num)

        if not index.column() == 5:
            QToolTip.showText(QCursor.pos(), self.setup_model.index(index.row(), index.column()).data(), self.setup_table, screen_rect, 10000)

    def update_config_view(self, view_name, item_text, item_select_status):
        if view_name == 'column':
            if item_text not in self.header_column_mapping.keys():
                return

            if item_select_status:
                self.setup_table.showColumn(self.header_column_mapping[item_text])

            else:
                self.setup_table.hideColumn(self.header_column_mapping[item_text])

        elif view_name == 'branch':
            if item_select_status:
                exclude_visible_row_list = []

                for block in self.block_row_mapping.keys():
                    if (block in self.view_status_dic['block']) and (not self.view_status_dic['block'][block]):
                        exclude_visible_row_list += self.block_row_mapping[block]

                for row in self.branch_row_mapping[item_text]:
                    if row not in exclude_visible_row_list:
                        self.setup_table.showRow(row)
            else:
                for row in self.branch_row_mapping[item_text]:
                    self.setup_table.hideRow(row)

            self.ifp_obj.top_tab.setCurrentIndex(0)

        elif view_name == 'block':
            if item_select_status:
                exclude_visible_row_list = []

                for branch in self.branch_row_mapping.keys():
                    if (branch in self.view_status_dic['branch']) and (not self.view_status_dic['branch'][branch]):
                        exclude_visible_row_list += self.branch_row_mapping[branch]

                for row in self.block_row_mapping[item_text]:
                    if row not in exclude_visible_row_list:
                        self.setup_table.showRow(row)
            else:
                for row in self.block_row_mapping[item_text]:
                    self.setup_table.hideRow(row)

            self.ifp_obj.top_tab.setCurrentIndex(0)

        self.view_status_dic[view_name][item_text] = item_select_status
        self.view_status_dic[view_name][item_text] = item_select_status
        self.ifp_obj.top_tab.setCurrentIndex(0)

    def update_state(self, state):
        self.state = state

        for i in range(self.setup_model.rowCount()):

            block = self.setup_model.index(i, 0).data()
            version = self.setup_model.index(i, 1).data()
            flow = self.setup_model.index(i, 2).data()
            vendor = self.setup_model.index(i, 3).data()
            branch = self.setup_model.index(i, 4).data()
            task = self.setup_model.index(i, 5).data()

            item = QStandardItem(task)
            item.setTextAlignment(Qt.AlignLeft)
            item.setTextAlignment(Qt.AlignVCenter)

            if None in [block, version, flow, vendor, branch, task]:
                item.setBackground(QBrush(QColor(255, 255, 255)))
            elif self.state[block][version][flow][vendor][branch][task] == 'user':
                item.setForeground(QBrush(QColor(100, 149, 237)))
                item.setFont(QFont('Calibri', 10, 500))
            elif self.state[block][version][flow][vendor][branch][task] == 'default':
                item.setBackground(QBrush(QColor(255, 255, 255)))
            elif self.state[block][version][flow][vendor][branch][task] == 'blank':
                item.setForeground(QBrush(QColor(255, 0, 0)))
                item.setFont(QFont('Calibri', 10, 500))

            self.setup_model.setItem(i, 5, item)

        self.setup_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setup_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)

    def parsing_default_setting(self, yaml_file):
        task_dic = AutoVivification()

        if os.path.exists(yaml_file):
            default_dic = yaml.safe_load(open(yaml_file, 'r'))

            if default_dic:
                if 'VAR' in default_dic:
                    self.default_var = default_dic['VAR']

                if 'TASK' in default_dic:
                    for key in default_dic['TASK'].keys():
                        flow_tmp = key.split(':')[0]
                        vendor = key.split(':')[1]
                        task_tmp = key.split(':')[2]

                        flow, flow_dependency = self.get_item_dependency(item=flow_tmp)
                        task, task_dependency = self.get_item_dependency(item=task_tmp)

                        self.default_dependency_dic.setdefault('flow_dependency', {})
                        self.default_dependency_dic.setdefault('task_dependency', {})

                        self.default_dependency_dic['flow_dependency'][flow] = flow_dependency

                        if flow not in self.default_dependency_dic['task_dependency']:
                            self.default_dependency_dic['task_dependency'][flow] = {}

                        if vendor not in self.default_dependency_dic['task_dependency'][flow]:
                            self.default_dependency_dic['task_dependency'][flow][vendor] = {}

                        self.default_dependency_dic['task_dependency'][flow][vendor][task] = task_dependency

                        if default_dic['TASK'][key]:
                            for category in default_dic['TASK'][key].keys():
                                if default_dic['TASK'][key][category]:
                                    for item in default_dic['TASK'][key][category].keys():
                                        task_dic[flow][vendor][task][category][item] = default_dic['TASK'][key][category][item]

        return task_dic

    def update_default_setting(self):
        self.default_setting = self.parsing_default_setting(self.default_yaml)

    @staticmethod
    def get_item_dependency(item=''):
        if my_match := re.match(r'(.*)\(RUN_AFTER=(.*)\)', item):
            item_name = my_match.group(1)
            item_dependency = my_match.group(2)
        else:
            item_name = item
            item_dependency = ''

        return item_name, item_dependency

    """
    1. Draw table by following dict
       a. self.user_input (GUI setting) or self.raw_setting (load ifp.cfg.yaml)
    2. Parsing self.detailed_setting[block][block_version][flow][vendor][task_branch][task] when load ifp.cfg.yaml
    """

    def preprocess_setting(self):
        setting = self.raw_setting
        modified_setting = copy.deepcopy(setting)

        if setting is None:
            return

        if 'BLOCK' not in setting.keys():
            return

        for block in setting['BLOCK'].keys():
            self.dependency_priority.setdefault(block, {})

            for version in setting['BLOCK'][block].keys():
                if version is not None:
                    match = re.match(r'(\S+)\(RUN_ORDER=(.*)\)', version)

                    if match:
                        self.update_config_yaml()
                        return
                    else:
                        block_version = version
                else:
                    block_version = version

                self.dependency_priority[block].setdefault(block_version, {})
                self.dependency_priority[block][block_version].setdefault('flow_dependency', {})
                self.dependency_priority[block][block_version].setdefault('task_dependency', {})

                for flow in setting['BLOCK'][block][version].keys():
                    flow_name, flow_dependency = self.get_item_dependency(flow)

                    if flow_name != flow:
                        modified_setting['BLOCK'][block][version][flow_name] = copy.deepcopy(modified_setting['BLOCK'][block][version][flow])
                        del modified_setting['BLOCK'][block][version][flow]

                    self.dependency_priority[block][block_version]['flow_dependency'][flow_name] = flow_dependency
                    self.dependency_priority[block][block_version]['task_dependency'].setdefault(flow_name, {})

                    for vendor in setting['BLOCK'][block][version][flow].keys():
                        self.dependency_priority[block][block_version]['task_dependency'][flow_name].setdefault(vendor, {})

                        for branch in setting['BLOCK'][block][version][flow][vendor].keys():
                            if branch is not None:
                                branch = re.sub(r'\'', '', branch)
                                match = re.match(r'(\S+)\(RUN_TYPE=(\S+)\)', branch)

                                if match:
                                    self.update_config_yaml()
                                    return
                                else:
                                    task_branch = branch
                            else:
                                task_branch = branch

                            self.dependency_priority[block][block_version]['task_dependency'][flow_name][vendor].setdefault(task_branch, {})

                            for task in setting['BLOCK'][block][version][flow][vendor][branch].keys():
                                task_name, task_dependency = self.get_item_dependency(task)

                                if task_name != task:
                                    modified_setting['BLOCK'][block][version][flow_name][vendor][branch][task_name] = copy.deepcopy(modified_setting['BLOCK'][block][version][flow_name][vendor][branch][task])
                                    del modified_setting['BLOCK'][block][version][flow_name][vendor][branch][task]

                                self.dependency_priority[block][block_version]['task_dependency'][flow_name][vendor][task_branch][task_name] = task_dependency

        self.raw_setting = modified_setting

    def update_config_yaml(self):
        info = '''<br>IFP upgrades to v1.2 or newer version </br>
                  <br> Please reset the dependencies in setup menu <b>Set dependency. </b> </br>
                  <br><b>ifp.cfg.yaml</b> will be updated after you click <b>‘SAVE’</b> button!</br>'''

        title = 'Warning!'
        self.compatible_flag = True

        Dialog(title, info)

        self.compatible_setting()
        self.preprocess_setting()

    def compatible_setting(self):
        compatible_setting = copy.deepcopy(self.raw_setting)

        if 'BLOCK' not in self.raw_setting.keys():
            return

        for block in self.raw_setting['BLOCK'].keys():
            for version in self.raw_setting['BLOCK'][block].keys():
                if version is not None:
                    match = re.match(r'(\S+)\(RUN_ORDER=(.*)\)', version)

                    if match:
                        block_version = match.group(1)
                    else:
                        block_version = version
                else:
                    block_version = version

                if block_version != version:
                    compatible_setting['BLOCK'][block][block_version] = copy.deepcopy(compatible_setting['BLOCK'][block][version])
                    del compatible_setting['BLOCK'][block][version]

                for flow in self.raw_setting['BLOCK'][block][version].keys():
                    if flow.find('RUN_AFTER') == -1:
                        flow_name = r'%s(RUN_AFTER=)' % flow
                        compatible_setting['BLOCK'][block][block_version][flow_name] = copy.deepcopy(compatible_setting['BLOCK'][block][block_version][flow])
                        del compatible_setting['BLOCK'][block][block_version][flow]
                    else:
                        flow_name = flow

                    for vendor in self.raw_setting['BLOCK'][block][version][flow].keys():
                        for branch in self.raw_setting['BLOCK'][block][version][flow][vendor].keys():
                            if branch is not None:
                                branch = re.sub(r'\'', '', branch)
                                match = re.match(r'(\S+)\(RUN_TYPE=(\S+)\)', branch)

                                if match:
                                    task_branch = match.group(1)
                                else:
                                    task_branch = branch
                            else:
                                task_branch = branch

                            if block_version != branch:
                                compatible_setting['BLOCK'][block][block_version][flow_name][vendor][task_branch] = copy.deepcopy(compatible_setting['BLOCK'][block][block_version][flow_name][vendor][branch])
                                del compatible_setting['BLOCK'][block][block_version][flow_name][vendor][branch]

                            for task in self.raw_setting['BLOCK'][block][version][flow][vendor][branch].keys():
                                if task.find('RUN_AFTER') == -1:
                                    task_name = r'%s(RUN_AFTER=)' % task
                                    compatible_setting['BLOCK'][block][block_version][flow_name][vendor][task_branch][task_name] = copy.deepcopy(compatible_setting['BLOCK'][block][block_version][flow_name][vendor][task_branch][task])
                                    del compatible_setting['BLOCK'][block][block_version][flow_name][vendor][task_branch][task]
                                else:
                                    task_name = task

                                if 'SUMMARY' in self.raw_setting['BLOCK'][block][version][flow][vendor][branch][task].keys():
                                    compatible_setting['BLOCK'][block][block_version][flow_name][vendor][task_branch][task_name]['SUMMARIZE'] = copy.deepcopy(compatible_setting['BLOCK'][block][block_version][flow_name][vendor][task_branch][task_name]['SUMMARY'])
                                    del compatible_setting['BLOCK'][block][block_version][flow_name][vendor][task_branch][task_name]['SUMMARY']

        self.raw_setting = compatible_setting

    def add_setting_dependency(self):
        modified_setting = copy.deepcopy(self.final_setting)

        for block in self.final_setting['BLOCK'].keys():
            if block == '' or block is None:
                continue

            for version in self.final_setting['BLOCK'][block].keys():
                for flow in self.final_setting['BLOCK'][block][version].keys():

                    if self.dependency_priority[block][version]['flow_dependency'][flow] == {}:
                        flow_run_after = r'%s(RUN_AFTER=)' % flow
                    else:
                        flow_run_after = r'%s(RUN_AFTER=%s)' % (flow, self.dependency_priority[block][version]['flow_dependency'][flow])

                    modified_setting['BLOCK'][block][version][flow_run_after] = copy.deepcopy(self.final_setting['BLOCK'][block][version][flow])
                    del modified_setting['BLOCK'][block][version][flow]

                    for vendor in self.final_setting['BLOCK'][block][version][flow].keys():
                        for branch in self.final_setting['BLOCK'][block][version][flow][vendor].keys():
                            for task in self.final_setting['BLOCK'][block][version][flow][vendor][branch].keys():
                                if self.dependency_priority[block][version]['task_dependency'][flow][vendor][branch][task] == {}:
                                    task_run_after = r'%s(RUN_AFTER=)' % task
                                else:
                                    task_run_after = r'%s(RUN_AFTER=%s)' % (task, self.dependency_priority[block][version]['task_dependency'][flow][vendor][branch][task])

                                modified_setting['BLOCK'][block][version][flow_run_after][vendor][branch][task_run_after] = copy.deepcopy(self.final_setting['BLOCK'][block][version][flow][vendor][branch][task])
                                del modified_setting['BLOCK'][block][version][flow_run_after][vendor][branch][task]

        self.final_setting = modified_setting

    def update_setting_dependency(self, setting):
        if setting is None:
            return

        if 'BLOCK' not in setting.keys():
            return

        for block in setting['BLOCK'].keys():
            self.dependency_priority.setdefault(block, {})

            for version in setting['BLOCK'][block].keys():
                self.dependency_priority[block].setdefault(version, {})
                self.dependency_priority[block][version].setdefault('flow_dependency', {})
                self.dependency_priority[block][version].setdefault('task_dependency', {})

                for flow in setting['BLOCK'][block][version].keys():
                    if flow not in self.dependency_priority[block][version]['flow_dependency'].keys():
                        self.dependency_priority[block][version]['flow_dependency'][flow] = ''

                    self.dependency_priority[block][version]['task_dependency'].setdefault(flow, {})

                    for vendor in setting['BLOCK'][block][version][flow].keys():
                        self.dependency_priority[block][version]['task_dependency'][flow].setdefault(vendor, {})

                        for branch in setting['BLOCK'][block][version][flow][vendor].keys():
                            self.dependency_priority[block][version]['task_dependency'][flow][vendor].setdefault(branch, {})

                            for task in setting['BLOCK'][block][version][flow][vendor][branch].keys():
                                if task not in self.dependency_priority[block][version]['task_dependency'][flow][vendor][branch].keys():
                                    self.dependency_priority[block][version]['task_dependency'][flow][vendor][branch][task] = {}

    def draw_table(self, setting, stage=''):
        self.update_setting_dependency(setting)
        self.setup_model.setRowCount(0)
        self.span_info = AutoVivification()
        self.table_info = AutoVivification()
        default_setting_tmp = copy.deepcopy(self.default_setting)
        row = 0

        if setting is None:
            return

        if 'BLOCK' not in setting.keys():
            return

        for block in setting['BLOCK'].keys():
            block_start_line = row

            for version in setting['BLOCK'][block].keys():

                # First time load ifp.cfg.yaml, the version may be IFP_v1.0(RUN_ORDER=gen_dir,syn,fv|sta), draw table by IFP_v1.0
                # Other scenario, the version is IFP_v1.0 without RUN_ORDER information
                # So setting['BLOCK'][block] must keep [version], others use [block_version] which do not have RUN_ORDER information

                version_start_line = row

                for flow in setting['BLOCK'][block][version].keys():

                    flow_start_line = row

                    for vendor in setting['BLOCK'][block][version][flow].keys():
                        vendor_start_line = row

                        for branch in setting['BLOCK'][block][version][flow][vendor].keys():
                            branch_start_line = row

                            for task in setting['BLOCK'][block][version][flow][vendor][branch].keys():
                                self.setup_model.setItem(row, 0, QStandardItem(block))
                                self.setup_model.setItem(row, 1, QStandardItem(version))
                                self.setup_model.setItem(row, 2, QStandardItem(flow))
                                self.setup_model.setItem(row, 3, QStandardItem(vendor))
                                self.setup_model.setItem(row, 4, QStandardItem(branch))
                                self.setup_model.setItem(row, 5, QStandardItem(task))

                                self.table_info[row] = [block, version, flow, vendor, branch, task]
                                row += 1

                                if stage == 'load':
                                    if setting['BLOCK'][block][version][flow][vendor][branch][task] is not None:
                                        check_flag = 0
                                        for category in setting['BLOCK'][block][version][flow][vendor][branch][task].keys():
                                            if category in default_setting_tmp[flow][vendor][task].keys():
                                                for item in setting['BLOCK'][block][version][flow][vendor][branch][task][category].keys():
                                                    if item in default_setting_tmp[flow][vendor][task][category].keys():
                                                        if not setting['BLOCK'][block][version][flow][vendor][branch][task][category][item] == default_setting_tmp[flow][vendor][task][category][item]:
                                                            check_flag = 1
                                                    else:
                                                        check_flag = 1
                                            else:
                                                check_flag = 1

                                        if check_flag == 1:
                                            self.detailed_setting[block][version][flow][vendor][branch][task] = \
                                                setting['BLOCK'][block][version][flow][vendor][branch][task]

                            if row - branch_start_line > 1:
                                self.setup_table.setSpan(branch_start_line, 4, row - branch_start_line, 1)
                                self.span_info[branch_start_line][4] = row - 1

                        if row - vendor_start_line > 1:
                            self.setup_table.setSpan(vendor_start_line, 3, row - vendor_start_line, 1)
                            self.span_info[vendor_start_line][3] = row - 1

                    if row - flow_start_line > 1:
                        self.setup_table.setSpan(flow_start_line, 2, row - flow_start_line, 1)
                        self.span_info[flow_start_line][2] = row - 1

                if row - version_start_line > 1:
                    self.setup_table.setSpan(version_start_line, 1, row - version_start_line, 1)
                    self.span_info[version_start_line][1] = row - 1

            if row - block_start_line > 1:
                self.setup_table.setSpan(block_start_line, 0, row - block_start_line, 1)
                self.span_info[block_start_line][0] = row - 1

    """
    1. Parsing GUI user setting
    2. Update self.user_input['BLOCK'][block][version][flow][vendor][branch][task]
    """

    def parsing_user_setting(self):
        self.branch_row_mapping = AutoVivification()
        self.view_status_dic.setdefault('branch', {})
        self.view_status_dic.setdefault('block', {})
        self.view_status_dic.setdefault('task', {})

        for i in range(self.setup_model.rowCount()):
            block = self.setup_model.index(i, 0).data()
            version = self.setup_model.index(i, 1).data()
            flow = self.setup_model.index(i, 2).data()
            vendor = self.setup_model.index(i, 3).data()
            branch = self.setup_model.index(i, 4).data()
            task = self.setup_model.index(i, 5).data()

            self.view_status_dic['branch'][branch] = True
            self.view_status_dic['block'][block] = True
            self.view_status_dic['task'][task] = True

            if branch not in self.branch_row_mapping.keys():
                self.branch_row_mapping[branch] = [i]
            else:
                self.branch_row_mapping[branch].append(i)

            if not block == self.table_info[i][0] and not self.span_info[i][0] == {}:
                self.table_info[i][0] = block

                for j in range(i + 1, self.span_info[i][0] + 1):
                    self.setup_model.setItem(j, 0, QStandardItem(block))
                    self.table_info[j][0] = block

            if block not in self.block_row_mapping.keys():
                self.block_row_mapping[block] = [i]
            else:
                self.block_row_mapping[block].append(i)

            if task not in self.task_row_mapping.keys():
                self.task_row_mapping[block] = [i]
            else:
                self.task_row_mapping[block].append(i)

            if not version == self.table_info[i][1] and not self.span_info[i][1] == {}:
                self.table_info[i][1] = version

                for j in range(i + 1, self.span_info[i][1] + 1):
                    self.setup_model.setItem(j, 1, QStandardItem(version))
                    self.table_info[j][1] = version

            if not flow == self.table_info[i][2] and not self.span_info[i][2] == {}:
                self.table_info[i][2] = flow

                for j in range(i + 1, self.span_info[i][2] + 1):
                    self.setup_model.setItem(j, 2, QStandardItem(flow))
                    self.table_info[j][2] = flow

            if not vendor == self.table_info[i][3] and not self.span_info[i][3] == {}:
                self.table_info[i][3] = vendor

                for j in range(i + 1, self.span_info[i][3] + 1):
                    self.setup_model.setItem(j, 3, QStandardItem(vendor))
                    self.table_info[j][3] = vendor

            if not branch == self.table_info[i][4] and not self.span_info[i][4] == {}:
                self.table_info[i][4] = branch

                for j in range(i + 1, self.span_info[i][4] + 1):
                    self.setup_model.setItem(j, 4, QStandardItem(branch))
                    self.table_info[j][4] = branch

            self.user_input['BLOCK'][block][version][flow][vendor][branch][task] = ''

    '''
    1. Parsing GUI info by def parsing_user_setting
    2. Delete repeated task setting between default.yaml and ifp.cfg.yaml
    3. Save final setting to self.final_setting['BLOCK'][block][version][flow][vendor][branch][task][category][item]
    '''

    def parsing_final_setting(self):
        self.parsing_user_setting()
        self.final_setting['VAR'] = {}
        default_setting_tmp = copy.deepcopy(self.default_setting)

        for key in self.user_var.keys():
            self.final_setting['VAR'][key] = self.user_var[key]

        self.final_setting['BLOCK'] = {}

        for block in self.user_input['BLOCK'].keys():
            if block == '' or block is None:
                continue

            self.final_setting['BLOCK'].setdefault(block, {})

            for version in self.user_input['BLOCK'][block].keys():
                if version == '':
                    Dialog('WARNING', 'Can not save your setting to config file due to empty version!', QMessageBox.Warning)
                    return

                self.final_setting['BLOCK'][block].setdefault(version, {})

                for flow in self.user_input['BLOCK'][block][version].keys():
                    if flow == '':
                        Dialog('WARNING', 'Can not save your setting to config file due to empty flow!', QMessageBox.Warning)
                        return

                    self.final_setting['BLOCK'][block][version].setdefault(flow, {})

                    for vendor in self.user_input['BLOCK'][block][version][flow].keys():
                        if vendor == '':
                            Dialog('WARNING', 'Can not save your setting to config file due to empty vendor!', QMessageBox.Warning)
                            return

                        self.final_setting['BLOCK'][block][version][flow].setdefault(vendor, {})

                        for branch in self.user_input['BLOCK'][block][version][flow][vendor].keys():
                            if branch == '':
                                Dialog('WARNING', 'Can not save your setting to config file due to empty branch!', QMessageBox.Warning)
                                return

                            self.final_setting['BLOCK'][block][version][flow][vendor].setdefault(branch, {})

                            for task in self.user_input['BLOCK'][block][version][flow][vendor][branch].keys():
                                if task == '':
                                    Dialog('WARNING', 'Can not save your setting to config file due to empty task!', QMessageBox.Warning)
                                    return

                                self.final_setting['BLOCK'][block][version][flow][vendor][branch].setdefault(task, {})

                                if not self.detailed_setting[block][version][flow][vendor][branch][task] == {}:
                                    for category in self.detailed_setting[block][version][flow][vendor][branch][task].keys():
                                        if self.detailed_setting[block][version][flow][vendor][branch][task][category] == {}:
                                            continue

                                        for item in self.detailed_setting[block][version][flow][vendor][branch][task][category].keys():

                                            if category in default_setting_tmp[flow][vendor][task].keys():
                                                if item in default_setting_tmp[flow][vendor][task][category].keys():
                                                    if default_setting_tmp[flow][vendor][task][category][item] == self.detailed_setting[block][version][flow][vendor][branch][task][category][item]:
                                                        continue

                                            self.final_setting['BLOCK'][block][version][flow][vendor][branch][task].setdefault(category, {})
                                            self.final_setting['BLOCK'][block][version][flow][vendor][branch][task][category][item] = self.detailed_setting[block][version][flow][vendor][branch][task][category][item]

    """
    1. Load ifp.cfg.yaml
    2. Draw table by raw setting
    3. Parsing GUI setting and check if any default task setting that not defined in default.yaml and ifp.cfg.yaml
    4. Update ifp.cfg.yaml and reload
    """

    def load(self):
        self.user_input = AutoVivification()
        self.detailed_setting = AutoVivification()
        file = open(self.config_path_edit.text(), 'r')
        self.raw_setting = yaml.safe_load(file)

        if self.raw_setting is None:
            return

        if 'VAR' in self.raw_setting.keys():
            self.user_var = self.raw_setting['VAR']

        if 'PROJECT' in self.raw_setting.keys():
            self.user_input['PROJECT'] = self.raw_setting['PROJECT']
        else:
            self.user_input['PROJECT'] = ''

        if 'GROUP' in self.raw_setting.keys():
            self.user_input['GROUP'] = self.raw_setting['GROUP']
        else:
            self.user_input['GROUP'] = ''

        self.preprocess_setting()
        self.draw_table(self.raw_setting, stage='load')
        self.parsing_user_setting()
        self.ifp_monitor.wake_up = True

    def save(self, *args):
        self.parsing_final_setting()
        self.add_setting_dependency()

        if len(args) == 2:
            tag = args[0]
            api_yaml = args[1]

            if tag == 'api' and api_yaml:
                self.ifp_obj.api_yaml = api_yaml

        if self.compatible_flag:
            os.rename(self.config_path_edit.text(), r'%s.%s' % (self.config_path_edit.text(), 'old_version_%s' % (datetime.datetime.now().strftime('%Y_%m_%d'))))
            self.compatible_flag = False

        self.save_flag.emit(True)

    def generate_menu(self, pos):
        self.user_api = parse_user_api(self.api_yaml)
        menu = QMenu()
        self.current_selected_row = self.setup_table.currentIndex().row()
        self.current_selected_column = self.setup_table.currentIndex().column()

        selected_rows = AutoVivification()
        for index in self.setup_table.selectedIndexes():
            if index.column() not in selected_rows.keys():
                selected_rows.setdefault(index.column(), [])

            selected_rows[index.column()].append(index.row())

        if self.current_selected_row is None:
            self.current_selected_block = None
            self.current_selected_version = None
            self.current_selected_flow = None
            self.current_selected_vendor = None
            self.current_selected_branch = None
            self.current_selected_task = None
        else:
            self.current_selected_block = self.setup_model.index(self.current_selected_row, 0).data()
            self.current_selected_version = self.setup_model.index(self.current_selected_row, 1).data()
            self.current_selected_flow = self.setup_model.index(self.current_selected_row, 2).data()
            self.current_selected_vendor = self.setup_model.index(self.current_selected_row, 3).data()
            self.current_selected_branch = self.setup_model.index(self.current_selected_row, 4).data()
            self.current_selected_task = self.setup_model.index(self.current_selected_row, 5).data()

        if len(self.setup_table.selectedIndexes()) == 0 or self.setup_table.indexAt(pos).column() < 0 or self.setup_table.indexAt(pos).row() < 0:
            action1 = QAction('Create block')
            action1.triggered.connect(lambda: self.add_more_item('block'))
            action1.setDisabled(self.disable_gui_flag)
            menu.addAction(action1)
        else:
            if self.current_selected_column == 0:
                action1 = QAction('Add block')
                action1.triggered.connect(lambda: self.add_more_item('block'))
                action1.setDisabled(self.disable_gui_flag)
                menu.addAction(action1)
                action4 = QAction('Copy block')
                action4.triggered.connect(lambda: self.copy_current_item('block'))
                action4.setDisabled(self.disable_gui_flag)
                menu.addAction(action4)

                if len(selected_rows[0]) > 1:
                    action2 = QAction('Remove blocks')
                else:
                    action2 = QAction('Remove block')

                action2.triggered.connect(lambda: self.remove_current_item('block'))
                action2.setDisabled(self.disable_gui_flag)
                menu.addAction(action2)
                add_api_menu(self.ifp_obj, self.user_api, menu, project=self.user_input['PROJECT'], group=self.user_input['GROUP'], tab='CONFIG', column='BLOCK', var_dic={'BLOCK': self.current_selected_block})

            elif self.current_selected_column == 1:
                action1 = QAction('Add version')
                action1.triggered.connect(lambda: self.add_more_item('version'))
                action1.setDisabled(self.disable_gui_flag)
                menu.addAction(action1)
                action4 = QAction('Copy version')
                action4.triggered.connect(lambda: self.copy_current_item('version'))
                action4.setDisabled(self.disable_gui_flag)
                menu.addAction(action4)

                if len(selected_rows[1]) > 1:
                    action2 = QAction('Remove versions')
                else:
                    action2 = QAction('Remove version')

                action2.triggered.connect(lambda: self.remove_current_item('version'))
                action2.setDisabled(self.disable_gui_flag)
                menu.addAction(action2)
                add_api_menu(self.ifp_obj, self.user_api, menu, project=self.user_input['PROJECT'], group=self.user_input['GROUP'], tab='CONFIG', column='VERSION', var_dic={'BLOCK': self.current_selected_block, 'VERSION': self.current_selected_version})

            elif self.current_selected_column == 2:
                action1 = QAction('Add flow')
                action1.triggered.connect(lambda: self.add_more_item('flow'))
                action1.setDisabled(self.disable_gui_flag)
                menu.addAction(action1)
                action4 = QAction('Copy flow')
                action4.triggered.connect(lambda: self.copy_current_item('flow'))
                action4.setDisabled(self.disable_gui_flag)
                menu.addAction(action4)

                if len(selected_rows[2]) > 1:
                    action2 = QAction('Remove flows')
                else:
                    action2 = QAction('Remove flow')

                action2.triggered.connect(lambda: self.remove_current_item('flow'))
                action2.setDisabled(self.disable_gui_flag)
                menu.addAction(action2)
                add_api_menu(self.ifp_obj, self.user_api, menu, project=self.user_input['PROJECT'], group=self.user_input['GROUP'], tab='CONFIG', column='FLOW', var_dic={'BLOCK': self.current_selected_block, 'VERSION': self.current_selected_version,
                                                                                                                                                                          'FLOW': self.current_selected_flow})
            elif self.current_selected_column == 3:
                action1 = QAction('Add vendor')
                action1.triggered.connect(lambda: self.add_more_item('vendor'))
                action1.setDisabled(self.disable_gui_flag)
                menu.addAction(action1)
                action4 = QAction('Copy vendor')
                action4.triggered.connect(lambda: self.copy_current_item('vendor'))
                action4.setDisabled(self.disable_gui_flag)
                menu.addAction(action4)

                if len(selected_rows[3]) > 1:
                    action2 = QAction('Remove vendors')
                else:
                    action2 = QAction('Remove vendor')

                action2.triggered.connect(lambda: self.remove_current_item('vendor'))
                action2.setDisabled(self.disable_gui_flag)
                menu.addAction(action2)
                add_api_menu(self.ifp_obj, self.user_api, menu, project=self.user_input['PROJECT'], group=self.user_input['GROUP'], tab='CONFIG', column='VENDOR', var_dic={'BLOCK': self.current_selected_block, 'VERSION': self.current_selected_version,
                                                                                                                                                                            'FLOW': self.current_selected_flow, 'VENDOR': self.current_selected_vendor})
            elif self.current_selected_column == 4:
                action1 = QAction('Add branch')
                action1.triggered.connect(lambda: self.add_more_item('branch'))
                action1.setDisabled(self.disable_gui_flag)
                menu.addAction(action1)

                if len(selected_rows[4]) > 1:
                    action2 = QAction('Remove branches')
                    action4 = QAction('Copy branches')

                else:
                    action2 = QAction('Remove branch')
                    action4 = QAction('Copy branch')

                action4.triggered.connect(lambda: self.copy_current_item('branch'))
                action4.setDisabled(self.disable_gui_flag)
                menu.addAction(action4)
                action2.triggered.connect(lambda: self.remove_current_item('branch'))
                action2.setDisabled(self.disable_gui_flag)
                menu.addAction(action2)
                add_api_menu(self.ifp_obj, self.user_api, menu, project=self.user_input['PROJECT'], group=self.user_input['GROUP'], tab='CONFIG', column='BRANCH', var_dic={'BLOCK': self.current_selected_block, 'VERSION': self.current_selected_version,
                                                                                                                                                                            'FLOW': self.current_selected_flow, 'VENDOR': self.current_selected_vendor,
                                                                                                                                                                            'BRANCH': self.current_selected_branch})

            elif self.current_selected_column == 5:
                action1 = QAction('Edit task')
                if self.disable_gui_flag:
                    action1.triggered.connect(lambda: self.edit_detailed_config(read_only=True, block=self.current_selected_block, version=self.current_selected_version,
                                                                                flow=self.current_selected_flow, vendor=self.current_selected_vendor,
                                                                                branch=self.current_selected_branch, task=self.current_selected_task))
                else:
                    action1.triggered.connect(lambda: self.edit_detailed_config(read_only=False, block=self.current_selected_block, version=self.current_selected_version,
                                                                                flow=self.current_selected_flow, vendor=self.current_selected_vendor,
                                                                                branch=self.current_selected_branch, task=self.current_selected_task))

                menu.addAction(action1)
                action3 = QAction('Add task')
                action3.triggered.connect(lambda: self.add_more_item('task'))
                action3.setDisabled(self.disable_gui_flag)
                menu.addAction(action3)
                action4 = QAction('Copy task')
                action4.triggered.connect(lambda: self.copy_current_item('task'))
                action4.setDisabled(self.disable_gui_flag)
                menu.addAction(action4)

                if len(selected_rows[5]) > 1:
                    action2 = QAction('Remove tasks')
                else:
                    action2 = QAction('Remove task')

                action2.triggered.connect(lambda: self.remove_current_item('task'))
                action2.setDisabled(self.disable_gui_flag)
                menu.addAction(action2)
                add_api_menu(self.ifp_obj, self.user_api, menu, project=self.user_input['PROJECT'], group=self.user_input['GROUP'], tab='CONFIG', column='TASK', var_dic={'BLOCK': self.current_selected_block, 'VERSION': self.current_selected_version,
                                                                                                                                                                          'FLOW': self.current_selected_flow, 'VENDOR': self.current_selected_vendor,
                                                                                                                                                                          'BRANCH': self.current_selected_branch, 'TASK': self.current_selected_task})

        menu.exec_(self.setup_table.mapToGlobal(pos))

    def set_dependency_priority(self):
        if not self.dependency_priority:
            title = 'Warning'
            info = 'Please add block first!'
            Dialog(title, info, icon=QMessageBox.Warning)
            return

        self.dependency_setting_windows = WindowForDependency(
            dependency_priority_dic=self.dependency_priority,
            default_dependency_dic=self.default_dependency_dic
        )
        self.dependency_setting_windows.setWindowModality(Qt.ApplicationModal)
        self.dependency_setting_windows.message.connect(self.update_extension_config_setting)
        self.dependency_setting_windows.show()

    def clean_dict_for_empty_key(self, deleted_branch_list=None):
        raw_setting = copy.deepcopy(self.user_input)

        for block in raw_setting['BLOCK'].keys():
            if raw_setting['BLOCK'][block] == {}:
                del self.user_input['BLOCK'][block]
                del self.view_status_dic['block'][block]
            else:
                for version in raw_setting['BLOCK'][block].keys():
                    if raw_setting['BLOCK'][block][version] == {}:
                        del self.user_input['BLOCK'][block][version]

                        if self.user_input['BLOCK'][block] == {}:
                            del self.user_input['BLOCK'][block]
                    else:
                        for flow in raw_setting['BLOCK'][block][version].keys():
                            if raw_setting['BLOCK'][block][version][flow] == {}:
                                del self.user_input['BLOCK'][block][version][flow]

                                if self.user_input['BLOCK'][block][version] == {}:
                                    del self.user_input['BLOCK'][block][version]

                                    if self.user_input['BLOCK'][block] == {}:
                                        del self.user_input['BLOCK'][block]
                            else:
                                for vendor in raw_setting['BLOCK'][block][version][flow].keys():
                                    if raw_setting['BLOCK'][block][version][flow][vendor] == {}:
                                        del self.user_input['BLOCK'][block][version][flow][vendor]

                                        if self.user_input['BLOCK'][block][version][flow] == {}:
                                            del self.user_input['BLOCK'][block][version][flow]

                                            if self.user_input['BLOCK'][block][version] == {}:
                                                del self.user_input['BLOCK'][block][version]

                                                if self.user_input['BLOCK'][block] == {}:
                                                    del self.user_input['BLOCK'][block]
                                    else:
                                        for branch in raw_setting['BLOCK'][block][version][flow][vendor].keys():
                                            if deleted_branch_list and branch in deleted_branch_list:
                                                deleted_branch_list.remove(branch)

                                            if raw_setting['BLOCK'][block][version][flow][vendor][branch] == {}:
                                                del self.user_input['BLOCK'][block][version][flow][vendor][branch]

                                                if self.user_input['BLOCK'][block][version][flow][vendor] == {}:
                                                    del self.user_input['BLOCK'][block][version][flow][vendor]

                                                    if self.user_input['BLOCK'][block][version][flow] == {}:
                                                        del self.user_input['BLOCK'][block][version][flow]

                                                        if self.user_input['BLOCK'][block][version] == {}:
                                                            del self.user_input['BLOCK'][block][version]

                                                            if self.user_input['BLOCK'][block] == {}:
                                                                del self.user_input['BLOCK'][block]

        for branch in deleted_branch_list:
            del self.view_status_dic['branch'][branch]

    def clean_dependency_dict_for_empty_key(self):
        raw_dependency = copy.deepcopy(self.dependency_priority)

        for block in raw_dependency.keys():
            if not raw_dependency[block]:
                del self.dependency_priority[block]
            else:
                for version in raw_dependency[block].keys():
                    if not raw_dependency[block][version]:
                        del self.dependency_priority[block][version]
                    else:
                        if 'flow_dependency' not in raw_dependency[block][version]:
                            continue

                        if 'task_dependency' not in raw_dependency[block][version]:
                            continue

                        if not raw_dependency[block][version]['flow_dependency']:
                            del self.dependency_priority[block][version]['flow_dependency']

                        if not raw_dependency[block][version]['task_dependency']:
                            del self.dependency_priority[block][version]['task_dependency']
                        else:
                            for flow in raw_dependency[block][version]['task_dependency'].keys():
                                if not raw_dependency[block][version]['task_dependency'][flow]:
                                    del self.dependency_priority[block][version]['task_dependency'][flow]
                                else:
                                    for vendor in raw_dependency[block][version]['task_dependency'][flow].keys():
                                        if not raw_dependency[block][version]['task_dependency'][flow][vendor]:
                                            del self.dependency_priority[block][version]['task_dependency'][flow][vendor]
                                        else:
                                            for branch in raw_dependency[block][version]['task_dependency'][flow][vendor].keys():
                                                if not raw_dependency[block][version]['task_dependency'][flow][vendor][branch]:
                                                    del self.dependency_priority[block][version]['task_dependency'][flow][vendor][branch]

    def add_more_item(self, item):
        self.parsing_user_setting()
        self.child = WindowForAddItems(item,
                                       self.user_input,
                                       self.detailed_setting,
                                       self.default_setting,
                                       self.current_selected_block,
                                       self.current_selected_version,
                                       self.current_selected_flow,
                                       self.current_selected_vendor,
                                       self.current_selected_branch,
                                       self.current_selected_task,
                                       self.ifp_obj.auto_import_tasks,
                                       self.dependency_priority,
                                       self.default_dependency_dic)
        self.child.setWindowModality(Qt.ApplicationModal)
        self.child.message.connect(self.update_table_after_add)
        self.child.save_signal.connect(self.save)
        self.child.show()

    def remove_current_item(self, item):
        self.parsing_user_setting()
        selected_rows = AutoVivification()
        selected_branch_list = []

        for index in self.setup_table.selectedIndexes():
            if index.column() not in selected_rows.keys():
                selected_rows.setdefault(index.column(), [])

            selected_rows[index.column()].append(index.row())

        reply = QMessageBox.question(self, "Warning", "Are you sure to remove selected %s?" % item, QMessageBox.Yes | QMessageBox.No)

        if reply == QMessageBox.Yes:
            pass
        elif reply == QMessageBox.No:
            return

        if item == 'block':
            selected_block_list = []

            for row in selected_rows[0]:
                block = self.setup_model.index(row, 0).data()

                if block not in selected_block_list:
                    selected_block_list.append(block)

                del self.user_input['BLOCK'][block]
                del self.dependency_priority[block]

            for block in selected_block_list:
                del self.view_status_dic['block'][block]

        if item == 'version':
            for row in selected_rows[1]:
                block = self.setup_model.index(row, 0).data()
                version = self.setup_model.index(row, 1).data()
                del self.user_input['BLOCK'][block][version]
                del self.dependency_priority[block][version]

        if item == 'flow':
            for row in selected_rows[2]:
                block = self.setup_model.index(row, 0).data()
                version = self.setup_model.index(row, 1).data()
                flow = self.setup_model.index(row, 2).data()
                del self.user_input['BLOCK'][block][version][flow]
                del self.dependency_priority[block][version]['flow_dependency'][flow]
                del self.dependency_priority[block][version]['task_dependency'][flow]

                for flow_item in self.dependency_priority[block][version]['flow_dependency'].keys():
                    dependency = self.dependency_priority[block][version]['flow_dependency'][flow_item]

                    new_dependency = self.remove_dependency_specific_item(dependency, flow)
                    self.dependency_priority[block][version]['flow_dependency'][flow_item] = new_dependency

        if item == 'vendor':
            for row in selected_rows[3]:
                block = self.setup_model.index(row, 0).data()
                version = self.setup_model.index(row, 1).data()
                flow = self.setup_model.index(row, 2).data()
                vendor = self.setup_model.index(row, 3).data()
                del self.user_input['BLOCK'][block][version][flow][vendor]
                del self.dependency_priority[block][version]['task_dependency'][flow][vendor]

        if item == 'branch':
            selected_branch_list = []

            for row in selected_rows[4]:
                block = self.setup_model.index(row, 0).data()
                version = self.setup_model.index(row, 1).data()
                flow = self.setup_model.index(row, 2).data()
                vendor = self.setup_model.index(row, 3).data()
                branch = self.setup_model.index(row, 4).data()

                if branch not in selected_branch_list:
                    selected_branch_list.append(branch)

                del self.user_input['BLOCK'][block][version][flow][vendor][branch]
                del self.dependency_priority[block][version]['task_dependency'][flow][vendor][branch]

        if item == 'task':
            for row in selected_rows[5]:
                block = self.setup_model.index(row, 0).data()
                version = self.setup_model.index(row, 1).data()
                flow = self.setup_model.index(row, 2).data()
                vendor = self.setup_model.index(row, 3).data()
                branch = self.setup_model.index(row, 4).data()
                task = self.setup_model.index(row, 5).data()
                del self.user_input['BLOCK'][block][version][flow][vendor][branch][task]
                del self.dependency_priority[block][version]['task_dependency'][flow][vendor][branch][task]

                for task_item in self.dependency_priority[block][version]['task_dependency'][flow][vendor][branch].keys():
                    dependency = self.dependency_priority[block][version]['task_dependency'][flow][vendor][branch][task_item]

                    new_dependency = self.remove_dependency_specific_item(dependency, task)
                    self.dependency_priority[block][version]['task_dependency'][flow][vendor][branch][task_item] = new_dependency

        self.clean_dict_for_empty_key(deleted_branch_list=selected_branch_list)
        self.clean_dependency_dict_for_empty_key()
        self.draw_table(self.user_input)
        self.save()

    @staticmethod
    def remove_dependency_specific_item(dependency, remove_item):
        if dependency.find(remove_item) == -1:
            new_dependency = dependency
            print("dependecy item:", dependency, "remove:", remove_item)
        else:
            first_dependency_list = dependency.split(',')
            new_first_dependency_list = []

            for first_dependency in first_dependency_list:
                second_dependency_list = first_dependency.split('|')
                new_second_dependency_list = []

                for second_dependency in second_dependency_list:
                    third_dependency_list = second_dependency.split('&')
                    new_third_dependency_list = []

                    for third_dependency in third_dependency_list:
                        if remove_item != third_dependency:
                            new_third_dependency_list.append(third_dependency)
                        else:
                            continue

                    new_second_dependency_list.append('&'.join(new_third_dependency_list))

                new_first_dependency_list.append('|'.join(new_second_dependency_list))

            new_dependency = ','.join(new_first_dependency_list)

        return new_dependency

    def copy_current_item(self, item):
        selected_rows = AutoVivification()

        for index in self.setup_table.selectedIndexes():
            if index.column() not in selected_rows.keys():
                selected_rows.setdefault(index.column(), [])

            selected_rows[index.column()].append(index.row())

        selected_branches = AutoVivification()

        if item == 'branch' and len(selected_rows[4]) > 1:
            for block in self.user_input['BLOCK'].keys():
                block_flag = False

                for version in self.user_input['BLOCK'][block].keys():
                    for flow in self.user_input['BLOCK'][block][version].keys():
                        for vendor in self.user_input['BLOCK'][block][version][flow].keys():
                            for branch in self.user_input['BLOCK'][block][version][flow][vendor].keys():
                                for row in selected_rows[4]:
                                    selected_block = self.setup_model.index(row, 0).data()
                                    selected_version = self.setup_model.index(row, 1).data()
                                    selected_flow = self.setup_model.index(row, 2).data()
                                    selected_vendor = self.setup_model.index(row, 3).data()
                                    selected_branch = self.setup_model.index(row, 4).data()

                                    if selected_block == block and selected_version == version and selected_flow == flow and selected_vendor == vendor and selected_branch == branch:
                                        selected_branches['BLOCK'][block][version][flow][vendor][branch] = True
                                        block_flag = True
                                        break
                                    else:
                                        selected_branches['BLOCK'][block][version][flow][vendor][branch] = False

                if block_flag is False:
                    del selected_branches['BLOCK'][block]

            self.child = WindowForCopyItems('branches',
                                            self.user_input,
                                            self.detailed_setting,
                                            selected_branches=selected_branches,
                                            dependency_dic=self.dependency_priority)
        else:
            self.child = WindowForCopyItems(item,
                                            self.user_input,
                                            self.detailed_setting,
                                            block=self.current_selected_block,
                                            version=self.current_selected_version,
                                            flow=self.current_selected_flow,
                                            vendor=self.current_selected_vendor,
                                            branch=self.current_selected_branch,
                                            task=self.current_selected_task,
                                            dependency_dic=self.dependency_priority)

        self.child.setWindowModality(Qt.ApplicationModal)
        self.child.message.connect(self.update_table_after_copy)
        self.child.save_signal.connect(self.save)
        self.child.show()

    def update_table_after_copy(self, info):
        copy_item = info[0]
        default_setting_tmp = copy.deepcopy(self.default_setting)

        self.draw_table(self.user_input)

        if copy_item == 'update flow':
            # Update dependency
            Dialog('Warning', 'Please check dependency for new flow!', QMessageBox.Warning)
        elif copy_item == 'task':

            # Copy all default setting of raw task to new task as user defined setting if new task is not a default task
            new_task = info[1]

            if new_task not in default_setting_tmp[self.current_selected_flow][self.current_selected_vendor].keys():
                for category in default_setting_tmp[self.current_selected_flow][self.current_selected_vendor][self.current_selected_task].keys():
                    if category not in self.detailed_setting[self.current_selected_block][self.current_selected_version][self.current_selected_flow][self.current_selected_vendor][self.current_selected_branch][new_task].keys():
                        self.detailed_setting[self.current_selected_block][self.current_selected_version][self.current_selected_flow][self.current_selected_vendor][self.current_selected_branch][new_task].setdefault(category, {})
                    for item in default_setting_tmp[self.current_selected_flow][self.current_selected_vendor][self.current_selected_task][category].keys():
                        if item not in self.detailed_setting[self.current_selected_block][self.current_selected_version][self.current_selected_flow][self.current_selected_vendor][self.current_selected_branch][new_task][category].keys():
                            self.detailed_setting[self.current_selected_block][self.current_selected_version][self.current_selected_flow][self.current_selected_vendor][self.current_selected_branch][new_task][category][item] = \
                                default_setting_tmp[self.current_selected_flow][self.current_selected_vendor][self.current_selected_task][category][item]

    def update_table_after_add(self, info):
        self.user_input = copy.deepcopy(info[0])
        self.draw_table(self.user_input)

    def edit_detailed_config(self, read_only=False, block=None, version=None, flow=None, vendor=None, branch=None, task=None):
        if flow in self.default_setting.keys():
            if vendor in self.default_setting[flow].keys():
                self.child = WindowForDetailedTaskInfo(self.user_input,
                                                       self.default_setting,
                                                       self.detailed_setting[block][version][flow][vendor][branch][task],
                                                       self.blank_setting,
                                                       self.default_var,
                                                       self.cwd,
                                                       block,
                                                       version,
                                                       flow,
                                                       vendor,
                                                       branch,
                                                       task,
                                                       self.user_var,
                                                       read_only)
                self.child.setWindowModality(Qt.ApplicationModal)
                self.child.message.connect(self.update_detailed_setting)
                self.child.show()
                return

        self.child = WindowForDetailedTaskInfo(self.user_input,
                                               AutoVivification(),
                                               self.detailed_setting[block][version][flow][vendor][branch][task],
                                               self.blank_setting,
                                               self.default_var,
                                               self.cwd,
                                               block,
                                               version,
                                               flow,
                                               vendor,
                                               branch,
                                               task,
                                               self.raw_setting['VAR'] if 'VAR' in self.raw_setting.keys() else {},
                                               read_only)
        self.child.setWindowModality(Qt.ApplicationModal)
        self.child.message.connect(self.update_detailed_setting)
        self.child.show()

    def update_detailed_setting(self, value):
        setting = value[0]
        new_task = value[1]
        new_setting = copy.deepcopy(setting)
        default_setting_tmp = copy.deepcopy(self.default_setting)

        if not self.current_selected_task == new_task:
            if self.current_selected_task in self.detailed_setting[self.current_selected_block][self.current_selected_version][self.current_selected_flow][self.current_selected_vendor][self.current_selected_branch].keys():
                del self.detailed_setting[self.current_selected_block][self.current_selected_version][self.current_selected_flow][self.current_selected_vendor][self.current_selected_branch][self.current_selected_task]
                del self.user_input['BLOCK'][self.current_selected_block][self.current_selected_version][self.current_selected_flow][self.current_selected_vendor][self.current_selected_branch][self.current_selected_task]

                self.user_input['BLOCK'][self.current_selected_block][self.current_selected_version][self.current_selected_flow][self.current_selected_vendor][self.current_selected_branch][new_task] = ''
                self.setup_model.setItem(self.current_selected_row, 5, QStandardItem(new_task))

                self.dependency_priority[self.current_selected_block][self.current_selected_version]['task_dependency'][self.current_selected_flow][self.current_selected_vendor][self.current_selected_branch][new_task] = ''
                del self.dependency_priority[self.current_selected_block][self.current_selected_version]['task_dependency'][self.current_selected_flow][self.current_selected_vendor][self.current_selected_branch][self.current_selected_task]
                Dialog(title='Warning', info='Task %s dependency have been reset to " "!' % new_task, icon=QMessageBox.Warning)

        for category in setting.keys():
            for item in setting[category].keys():
                if item in default_setting_tmp[self.current_selected_flow][self.current_selected_vendor][new_task][category].keys():
                    if default_setting_tmp[self.current_selected_flow][self.current_selected_vendor][new_task][category][item] == setting[category][item]:
                        del new_setting[category][item]

            for item in setting[category].keys():
                if setting[category][item] == '':
                    del new_setting[category][item]

            if len(new_setting[category].keys()) == 0:
                del new_setting[category]

        self.detailed_setting[self.current_selected_block][self.current_selected_version][self.current_selected_flow][self.current_selected_vendor][self.current_selected_branch][new_task] = copy.deepcopy(new_setting)
        self.current_selected_task = new_task
        self.save()

    def update_extension_config_setting(self, tag=None, *args, **kwargs):
        # For dependency setting
        if tag == 'dependency':
            dependency_dic = args[0]

            if not dependency_dic:
                return

            self.dependency_priority = dependency_dic
            self.save()
        # For Variable setting
        elif tag == 'env':
            var_dic = args[0]
            mode = args[1]

            if not mode:
                return

            if mode == 'user':
                self.user_var = {}

                for key, value in var_dic.items():
                    if key in self.default_var and value == self.default_var[key]:
                        continue

                    self.user_var[key] = value
                self.save()
            elif mode == 'advance':
                self.default_var = var_dic

                with open(self.default_yaml, 'r') as DF:
                    default_dic = yaml.load(DF, Loader=yaml.CLoader)

                if not default_dic:
                    default_dic = {}

                default_dic['VAR'] = self.default_var

                with open(self.default_yaml, 'w') as DF:
                    DF.write(yaml.dump(default_dic, allow_unicode=True))
        elif tag == 'API':
            api_dic = args[0]
            api_yaml = args[1]

            if not api_yaml:
                return

            with open(api_yaml, 'w') as af:
                af.write(yaml.dump(api_dic, allow_unicode=True))

            self.save('api', api_yaml)

    def exchange_task(self, info):
        block = info[0]
        version = info[1]
        flow = info[2]
        vendor = info[3]
        branch = info[4]
        raw_task = info[5]
        new_task = info[6]

        tasks = list(self.user_input['BLOCK'][block][version][flow][vendor][branch].keys())
        new_tasks = []
        for task in tasks:
            del self.user_input['BLOCK'][block][version][flow][vendor][branch][task]

            if task == raw_task:
                new_tasks.append(new_task)
            elif task == new_task:
                new_tasks.append(raw_task)
            else:
                new_tasks.append(task)

        for task in new_tasks:
            self.user_input['BLOCK'][block][version][flow][vendor][branch][task] = ''

        self.draw_table(self.user_input)
        self.save()


class IFPMonitor(QObject):
    message = pyqtSignal(dict)

    def __init__(self, mainwindow):
        super(QObject, self).__init__()
        self.mainwindow = mainwindow
        self.user_input = AutoVivification()
        self.detailed_setting = AutoVivification()
        self.default_setting = AutoVivification()
        self.state = AutoVivification()
        self.wake_up = False

    def run(self):
        while True:
            if self.wake_up:
                self.user_input = copy.deepcopy(self.mainwindow.user_input)
                self.detailed_setting = copy.deepcopy(self.mainwindow.detailed_setting)
                self.default_setting = copy.deepcopy(self.mainwindow.default_setting)

                for block in self.user_input['BLOCK'].keys():
                    for version in self.user_input['BLOCK'][block].keys():
                        for flow in self.user_input['BLOCK'][block][version].keys():
                            for vendor in self.user_input['BLOCK'][block][version][flow].keys():
                                for branch in self.user_input['BLOCK'][block][version][flow][vendor].keys():
                                    for task in self.user_input['BLOCK'][block][version][flow][vendor][branch].keys():
                                        if not self.detailed_setting[block][version][flow][vendor][branch][task] == {}:
                                            self.state[block][version][flow][vendor][branch][task] = 'user'

                                            if len(check_task_items(self.detailed_setting[block][version][flow][vendor][branch][task])):
                                                self.state[block][version][flow][vendor][branch][task] = 'blank'

                                            continue

                                        if flow in self.default_setting.keys():
                                            if vendor in self.default_setting[flow].keys():
                                                if task in self.default_setting[flow][vendor].keys():
                                                    self.state[block][version][flow][vendor][branch][task] = 'default'
                                                    continue

                                        self.state[block][version][flow][vendor][branch][task] = 'blank'

                self.message.emit(self.state)
                self.wake_up = False
            time.sleep(3)


class WindowForAddItems(QMainWindow):
    message = pyqtSignal(list)
    save_signal = pyqtSignal()

    def __init__(self,
                 item,
                 user_input,
                 detailed_setting,
                 default_setting,
                 block=None,
                 version=None,
                 flow=None,
                 vendor=None,
                 branch=None,
                 task=None,
                 auto_import_tasks=True,
                 dependency_dic=None,
                 default_dependency_dic=None):
        super().__init__()
        self.item = item
        self.user_input = user_input
        self.detailed_setting = detailed_setting
        self.default_setting = default_setting
        self.block = block
        self.version = version
        self.flow = flow
        self.vendor = vendor
        self.branch = branch
        self.task = task
        self.dependency_dic = dependency_dic
        self.default_dependency_dic = default_dependency_dic
        self.auto_import_tasks = auto_import_tasks

        if len(list(self.default_setting.keys())) == 0:
            self.auto_import_tasks = False

        self.top_widget = QWidget()
        self.top_layout = QVBoxLayout()
        self.top_widget.setLayout(self.top_layout)
        self.setCentralWidget(self.top_widget)

        self.new_branch_widget = QWidget()
        self.new_branch_layout = QHBoxLayout()
        self.new_branch_widget.setLayout(self.new_branch_layout)
        self.new_branch_label = QLabel('New branch : ')
        self.new_branch_edit = QLineEdit()
        self.new_branch_edit.setFixedWidth(200)
        self.new_branch_edit.textChanged.connect(self.create_new_branch)
        self.new_branch_layout.addWidget(self.new_branch_label)
        self.new_branch_layout.addWidget(self.new_branch_edit)
        self.new_branch_layout.addStretch(1)

        self.table = QTableView()
        self.table_model = QStandardItemModel(1, 6)
        self.table.setModel(self.table_model)
        header = ['Block', 'Version', 'Flow', 'Vendor', 'Branch', 'Task']
        self.table_model.setHorizontalHeaderLabels(header)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.table.setStyleSheet('font-family : calibri; font-size : 15px')
        self.table.setShowGrid(True)
        self.table.horizontalHeader().sectionClicked.connect(self.title_click_behavior)

        self.save_button = QPushButton('save')
        self.save_button.clicked.connect(self.save)
        self.cancel_button = QPushButton('cancel')
        self.cancel_button.clicked.connect(self.close)

        self.button_widget = QWidget()
        self.button_layout = QHBoxLayout()
        self.button_widget.setLayout(self.button_layout)

        self.button_layout.addStretch(1)
        self.button_layout.addWidget(self.save_button)
        self.button_layout.addWidget(self.cancel_button)

        if self.auto_import_tasks and self.item in ['block', 'version']:
            self.resize(1200, 500)
            self.new_branch_edit.setEnabled(True)
            self.top_layout.addWidget(self.new_branch_widget)
        else:
            self.resize(1200, 100)

        self.top_layout.addWidget(self.table)
        self.top_layout.addWidget(self.button_widget)

        self.draw_table(self.table, self.table_model, editable=True)

        self.setWindowTitle('Add new %s' % self.item)
        center(self)

    def title_click_behavior(self, index):
        if not self.auto_import_tasks:
            return

        unselected_flag = False

        if index == 5:
            for i in range(self.table_model.rowCount()):
                if not self.table_model.item(i, 5).checkState() == Qt.Checked:
                    unselected_flag = True
                    break
        else:
            return

        for i in range(self.table_model.rowCount()):
            if unselected_flag:
                self.table_model.item(i, 5).setCheckState(Qt.Checked)
            else:
                self.table_model.item(i, 5).setCheckState(Qt.Unchecked)

    def draw_table(self, table, model, editable=False):
        model.setRowCount(0)
        if self.item == 'block':
            model.setRowCount(1)

        if self.item in ['version', 'flow', 'vendor', 'branch', 'task']:
            block_item = QStandardItem(self.block)
            block_item.setFlags(Qt.ItemIsEditable)
            model.setItem(0, 0, block_item)

        if self.item in ['flow', 'vendor', 'branch', 'task']:
            version_item = QStandardItem(self.version)
            version_item.setFlags(Qt.ItemIsEditable)
            model.setItem(0, 1, version_item)

        if self.item in ['vendor', 'branch', 'task']:
            flow_item = QStandardItem(self.flow)
            flow_item.setFlags(Qt.ItemIsEditable)
            model.setItem(0, 2, flow_item)

        if self.item in ['branch', 'task']:
            vendor_item = QStandardItem(self.vendor)
            vendor_item.setFlags(Qt.ItemIsEditable)
            model.setItem(0, 3, vendor_item)

        if self.item in ['task']:
            branch_item = QStandardItem(self.branch)
            branch_item.setFlags(Qt.ItemIsEditable)
            model.setItem(0, 4, branch_item)

        row = 0
        if self.item in ['block', 'version'] and self.auto_import_tasks:
            for flow in self.default_setting.keys():
                flow_start_line = row
                flow_item = QStandardItem(flow)
                flow_item.setFlags(Qt.ItemIsEditable)
                model.setItem(row, 2, flow_item)

                for vendor in self.default_setting[flow].keys():
                    vendor_start_line = row
                    vendor_item = QStandardItem(vendor)
                    vendor_item.setFlags(Qt.ItemIsEditable)
                    model.setItem(row, 3, vendor_item)

                    for task in self.default_setting[flow][vendor].keys():
                        task_item = QStandardItem(task)
                        task_item.setCheckable(True)
                        task_item.setCheckState(Qt.Checked)
                        # task_item.setFlags(Qt.ItemIsEditable)
                        model.setItem(row, 5, task_item)
                        row += 1

                    vendor_end_line = row

                    if vendor_end_line - vendor_start_line > 1:
                        table.setSpan(vendor_start_line, 3, vendor_end_line - vendor_start_line, 1)

                flow_end_line = row

                if flow_end_line - flow_start_line > 1:
                    table.setSpan(flow_start_line, 2, flow_end_line - flow_start_line, 1)

            if row > 1:
                table.setSpan(0, 0, row, 1)
                table.setSpan(0, 1, row, 1)

        if self.item == 'task' and self.auto_import_tasks:
            qitem = QStandardItem('')
            model.setItem(0, 5, qitem)
            index = model.indexFromItem(qitem)
            lineedit = QLineEdit2(values=self.default_setting[self.flow][self.vendor].keys())
            table.setIndexWidget(index, lineedit)

    def create_new_branch(self):
        if self.item in ['block', 'version']:
            for i in range(self.table_model.rowCount()):
                self.table_model.setItem(i, 4, QStandardItem(self.new_branch_edit.text()))

    @staticmethod
    def clean_dependency(item_list=None, item=None, dependency=None):
        if not item_list or not item or not dependency:
            return ''

        independent_condition_list = dependency.split(',')
        valid_independent_condition_list = []

        if not independent_condition_list:
            return ''

        for independent_condition in independent_condition_list:
            parallel_condition_list = independent_condition.split('|')
            valid_parallel_condition_list = []

            if not parallel_condition_list:
                continue

            for parallel_condition in parallel_condition_list:
                and_condition_list = parallel_condition.split('&')
                valid_add_condition_list = []

                if not and_condition_list:
                    continue

                for and_condition in and_condition_list:
                    if and_condition.strip() not in item_list:
                        continue
                    else:
                        valid_add_condition_list.append(and_condition.strip())

                valid_parallel_condition = '&'.join(valid_add_condition_list)

                if valid_parallel_condition:
                    valid_parallel_condition_list.append(valid_parallel_condition)

            valid_independent_condition = '|'.join(valid_parallel_condition_list)

            if valid_independent_condition:
                valid_independent_condition_list.append(valid_independent_condition)

        valid_dependency = ','.join(valid_independent_condition_list)

        return valid_dependency

    def save(self):
        block = None
        version = None
        flow = None
        vendor = None
        raw_user_input = copy.deepcopy(self.user_input)

        for i in range(self.table_model.rowCount()):
            if self.table_model.index(i, 0).data():
                block = self.table_model.index(i, 0).data()

            if self.table_model.index(i, 1).data():
                version = self.table_model.index(i, 1).data()

            if self.table_model.index(i, 2).data():
                flow = self.table_model.index(i, 2).data()

            if self.table_model.index(i, 3).data():
                vendor = self.table_model.index(i, 3).data()

            branch = self.table_model.index(i, 4).data()

            if self.item == 'task' and self.auto_import_tasks:
                task = self.table.indexWidget(self.table_model.index(i, 5)).text()
            else:
                task = self.table_model.index(i, 5).data()

            if '' or None in [block, version, flow, vendor, branch, task]:
                Dialog('Error', "Please fill in any empty item", QMessageBox.Critical)
                return

            if self.item == 'block' and block in raw_user_input['BLOCK'].keys():
                Dialog('Error', "You add one repeated block %s" % block, QMessageBox.Critical)
                return
            elif self.item == 'version' and version in raw_user_input['BLOCK'][block].keys():
                Dialog('Error', "You add one repeated version %s" % version, QMessageBox.Critical)
                return
            elif self.item == 'flow' and flow in raw_user_input['BLOCK'][block][version].keys():
                Dialog('Error', "You add one repeated flow %s" % flow, QMessageBox.Critical)
                return
            elif self.item == 'vendor' and vendor in raw_user_input['BLOCK'][block][version][flow].keys():
                Dialog('Error', "You add one repeated vendor %s" % vendor, QMessageBox.Critical)
                return
            elif self.item == 'branch' and branch in raw_user_input['BLOCK'][block][version][flow][vendor].keys():
                Dialog('Error', "You add one repeated branch %s" % branch, QMessageBox.Critical)
                return
            elif self.item == 'task' and task in raw_user_input['BLOCK'][block][version][flow][vendor][branch].keys():
                Dialog('Error', "You add one repeated task %s" % task, QMessageBox.Critical)
                return

            if self.auto_import_tasks:
                if block not in self.dependency_dic:
                    self.dependency_dic.setdefault(block, {})

                if version not in self.dependency_dic[block]:
                    self.dependency_dic[block].setdefault(version, {})
                    self.dependency_dic[block][version].setdefault('flow_dependency', {})
                    self.dependency_dic[block][version].setdefault('task_dependency', {})

                if flow not in self.dependency_dic[block][version]['flow_dependency']:
                    self.dependency_dic[block][version]['task_dependency'].setdefault(flow, {})

                if vendor not in self.dependency_dic[block][version]['task_dependency'][flow]:
                    self.dependency_dic[block][version]['task_dependency'][flow].setdefault(vendor, {})

                if branch not in self.dependency_dic[block][version]['task_dependency'][flow][vendor]:
                    self.dependency_dic[block][version]['task_dependency'][flow][vendor].setdefault(branch, {})

            if self.item == 'task':
                all_tasks = list(self.user_input['BLOCK'][block][version][flow][vendor][branch].keys())
                index = all_tasks.index(self.task)
                all_tasks.insert(index + 1, task)
                self.user_input['BLOCK'][block][version][flow][vendor][branch] = {}

                for k in all_tasks:
                    self.user_input['BLOCK'][block][version][flow][vendor][branch][k] = ''

                # Update dependency
                if self.auto_import_tasks:
                    if task not in self.dependency_dic[block][version]['task_dependency'][flow][vendor][branch]:
                        try:
                            dependency = self.default_dependency_dic['task_dependency'][flow][vendor][task]
                        except Exception:
                            dependency = ''

                        task_list = list(self.user_input['BLOCK'][block][version][flow][vendor][branch].keys())
                        valid_dependency = self.clean_dependency(item_list=task_list, item=task, dependency=dependency)
                        self.dependency_dic[block][version]['task_dependency'][flow][vendor][branch][task] = valid_dependency

            else:
                if self.item in ['block', 'version'] and self.auto_import_tasks:
                    if not self.table_model.item(i, 5).checkState() == Qt.Checked:
                        continue

                    # Update dependency
                    if flow not in self.dependency_dic[block][version]['flow_dependency'] and flow in self.default_dependency_dic['flow_dependency']:
                        flow_list = list(self.user_input['BLOCK'][block][version].keys())

                        valid_dependency = self.clean_dependency(item_list=flow_list, item=flow, dependency=self.default_dependency_dic['flow_dependency'][flow])
                        self.dependency_dic[block][version]['flow_dependency'][flow] = valid_dependency
                        self.dependency_dic[block][version]['task_dependency'].setdefault(flow, {})

                    if task not in self.dependency_dic[block][version]['task_dependency'][flow][vendor][branch]:
                        try:
                            dependency = self.default_dependency_dic['task_dependency'][flow][vendor][task]
                        except Exception:
                            dependency = ''

                        task_list = list(self.user_input['BLOCK'][block][version][flow][vendor][branch].keys())
                        valid_dependency = self.clean_dependency(item_list=task_list, item=task, dependency=dependency)
                        self.dependency_dic[block][version]['task_dependency'][flow][vendor][branch][task] = valid_dependency

                self.user_input['BLOCK'][block][version][flow][vendor][branch][task] = ''

        self.message.emit([self.user_input, self.item, block, version])
        self.save_signal.emit()
        self.close()


class WindowForCopyItems(QMainWindow):
    message = pyqtSignal(list)
    save_signal = pyqtSignal()

    def __init__(self, item, user_input, detailed_setting, block=None, version=None, flow=None, vendor=None, branch=None, task=None, selected_branches=None, dependency_dic=None):
        super().__init__()
        self.item = item
        self.user_input = user_input
        self.detailed_setting = detailed_setting
        self.dependency_dic = dependency_dic
        self.block = block
        self.version = version
        self.flow = flow
        self.vendor = vendor
        self.branch = branch
        self.task = task
        self.selected_branches = selected_branches
        self.copy_branches_row_mapping = AutoVivification()
        self.span_info = AutoVivification()
        self.table_info = AutoVivification()

        self.top_widget = QWidget()
        self.top_layout = QVBoxLayout()
        self.top_widget.setLayout(self.top_layout)
        self.setCentralWidget(self.top_widget)

        self.raw_table_label = QLabel('Copied Setting (Non editable)')
        self.raw_table_label.setStyleSheet('font-weight : bold; font-size : 20px')

        self.raw_table = QTableView()
        self.raw_table_model = QStandardItemModel(1, 6)
        self.raw_table.setModel(self.raw_table_model)
        header = ['Block', 'Version', 'Flow', 'Vendor', 'Branch', 'Task']
        self.raw_table_model.setHorizontalHeaderLabels(header)
        self.raw_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.raw_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.raw_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.raw_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.raw_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.raw_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.raw_table.setStyleSheet('font-family : calibri; font-size : 15px')
        self.raw_table.setShowGrid(True)
        self.raw_table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        self.new_table_label = QLabel('New Setting')
        self.new_table_label.setStyleSheet('font-weight : bold; font-size : 20px')

        self.new_branch_widget = QWidget()
        self.new_branch_layout = QHBoxLayout()
        self.new_branch_widget.setLayout(self.new_branch_layout)
        self.new_branch_label = QLabel('New branch : ')
        self.new_branch_edit = QLineEdit()
        self.new_branch_edit.setFixedWidth(200)
        self.new_branch_edit.textChanged.connect(self.create_new_branch)

        if self.item == 'task':
            self.new_branch_edit.setEnabled(False)

        self.new_branch_layout.addWidget(self.new_branch_label)
        self.new_branch_layout.addWidget(self.new_branch_edit)
        self.new_branch_layout.addStretch(1)

        self.new_table = QTableView()
        self.new_table_model = QStandardItemModel(1, 6)
        self.new_table.setModel(self.new_table_model)
        header = ['Block', 'Version', 'Flow', 'Vendor', 'Branch', 'Task']
        self.new_table_model.setHorizontalHeaderLabels(header)
        self.new_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.new_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.new_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.new_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.new_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.new_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.new_table.setStyleSheet('font-family : calibri; font-size : 15px')
        self.new_table.setShowGrid(True)

        self.save_button = QPushButton('save')
        self.save_button.clicked.connect(self.save)
        self.cancel_button = QPushButton('cancel')
        self.cancel_button.clicked.connect(self.close)

        self.button_widget = QWidget()
        self.button_layout = QHBoxLayout()
        self.button_widget.setLayout(self.button_layout)

        self.button_layout.addStretch(1)
        self.button_layout.addWidget(self.save_button)
        self.button_layout.addWidget(self.cancel_button)

        if not self.item == 'branches':
            self.top_layout.addWidget(self.raw_table_label)
            self.top_layout.addWidget(self.raw_table)
            self.top_layout.addStretch(2)

        self.top_layout.addWidget(self.new_table_label)
        self.top_layout.addWidget(self.new_branch_widget)
        self.top_layout.addWidget(self.new_table)
        self.top_layout.addWidget(self.button_widget)

        if not self.item == 'branches':
            self.top_layout.setStretch(0, 1)
            self.top_layout.setStretch(1, 12)
            self.top_layout.setStretch(3, 1)
            self.top_layout.setStretch(4, 1)
            self.top_layout.setStretch(5, 12)
            self.top_layout.setStretch(6, 1)

            self.draw_table(self.raw_table, self.raw_table_model, editable=False)
        self.draw_table(self.new_table, self.new_table_model, editable=True)

        self.resize(1200, 600)
        self.setWindowTitle('Copy %s' % self.item)
        center(self)

    def draw_table(self, table, model, editable=False):
        model.setRowCount(0)
        row = 0
        versions = []

        if self.item == 'branches':
            blocks = list(self.selected_branches['BLOCK'].keys())
        else:
            blocks = [self.block]

        for block in blocks:
            block_start_line = row

            if self.item in ['block', 'branches']:
                versions = list(self.user_input['BLOCK'][block].keys())
            elif self.item in ['version', 'flow', 'vendor', 'branch', 'task']:
                versions = [self.version]

            for version in versions:
                version_start_line = row

                for flow in self.user_input['BLOCK'][block][version].keys():
                    if self.item in ['flow', 'vendor', 'branch', 'task'] and not flow == self.flow:
                        continue

                    flow_start_line = row

                    for vendor in self.user_input['BLOCK'][block][version][flow].keys():
                        if self.item in ['vendor', 'branch', 'task'] and not vendor == self.vendor:
                            continue

                        vendor_start_line = row

                        for branch in self.user_input['BLOCK'][block][version][flow][vendor].keys():
                            if self.item in ['branch', 'task'] and not branch == self.branch:
                                continue

                            if self.item == 'branches' and self.selected_branches['BLOCK'][block][version][flow][vendor][branch] is True and editable:
                                count = 2
                            else:
                                count = 1

                            for i in range(count):
                                branch_start_line = row

                                for task in self.user_input['BLOCK'][block][version][flow][vendor][branch].keys():
                                    if self.item in ['task'] and not task == self.task:
                                        continue

                                    block_item = QStandardItem(block)

                                    if editable and self.item in ['version', 'flow', 'vendor', 'branch', 'task', 'branches']:
                                        block_item.setFlags(Qt.ItemIsEditable)
                                    model.setItem(row, 0, block_item)

                                    version_item = QStandardItem(version)

                                    if editable and self.item in ['flow', 'vendor', 'branch', 'task', 'branches']:
                                        version_item.setFlags(Qt.ItemIsEditable)
                                    model.setItem(row, 1, QStandardItem(version_item))

                                    flow_item = QStandardItem(flow)

                                    if editable and self.item in ['block', 'version', 'vendor', 'branch', 'task', 'branches']:
                                        flow_item.setFlags(Qt.ItemIsEditable)
                                    model.setItem(row, 2, flow_item)

                                    vendor_item = QStandardItem(vendor)

                                    if editable and self.item in ['task', 'branches']:
                                        vendor_item.setFlags(Qt.ItemIsEditable)
                                    model.setItem(row, 3, vendor_item)

                                    if i == 1:
                                        self.copy_branches_row_mapping[row] = branch
                                        branch_item = QStandardItem('')
                                        self.table_info[row] = [block, version, flow, vendor, '', task]
                                        branch_item.setBackground(QBrush(QColor(255, 248, 220)))
                                    else:
                                        self.copy_branches_row_mapping[row] = False
                                        branch_item = QStandardItem(branch)
                                        self.table_info[row] = [block, version, flow, vendor, branch, task]

                                    if editable and self.item in ['task', 'branches'] and i == 0:
                                        branch_item.setFlags(Qt.ItemIsEditable)

                                    model.setItem(row, 4, branch_item)

                                    task_item = QStandardItem(task)

                                    if editable and self.item in ['block', 'version', 'flow', 'vendor', 'branch', 'branches']:
                                        task_item.setFlags(Qt.ItemIsEditable)

                                    model.setItem(row, 5, task_item)
                                    row += 1

                                if row - branch_start_line > 1:
                                    table.setSpan(branch_start_line, 4, row - branch_start_line, 1)
                                    self.span_info[branch_start_line][4] = row - 1

                        if row - vendor_start_line > 1:
                            table.setSpan(vendor_start_line, 3, row - vendor_start_line, 1)
                            self.span_info[vendor_start_line][3] = row - 1

                    if row - flow_start_line > 1:
                        table.setSpan(flow_start_line, 2, row - flow_start_line, 1)
                        self.span_info[flow_start_line][2] = row - 1

                if row - version_start_line > 1:
                    table.setSpan(version_start_line, 1, row - version_start_line, 1)
                    self.span_info[version_start_line][1] = row - 1

            if row - block_start_line > 1:
                table.setSpan(block_start_line, 0, row - block_start_line, 1)
                self.span_info[block_start_line][0] = row - 1

        self.new_branch_edit.setPlaceholderText('<Enter for all new branch>')

    def create_new_branch(self):
        if self.item in ['block', 'version', 'flow', 'vendor', 'branch']:
            for i in range(self.new_table_model.rowCount()):
                self.new_table_model.setItem(i, 4, QStandardItem(self.new_branch_edit.text()))
        elif self.item == 'branches':
            for i in range(self.new_table_model.rowCount()):
                if self.copy_branches_row_mapping[i] is not False:
                    item = QStandardItem(self.new_branch_edit.text())
                    item.setBackground(QBrush(QColor(255, 248, 220)))
                    self.new_table_model.setItem(i, 4, item)

    def save(self):
        update_flow_flag = False
        task_new = ''
        block, version, flow, vendor, branch, task = None, None, None, None, None, None

        for i in range(self.new_table_model.rowCount()):
            block_new = self.new_table_model.index(i, 0).data()
            version_new = self.new_table_model.index(i, 1).data()
            flow_new = self.new_table_model.index(i, 2).data()
            vendor_new = self.new_table_model.index(i, 3).data()
            branch_new = self.new_table_model.index(i, 4).data()
            task_new = self.new_table_model.index(i, 5).data()

            for cell in [block_new, version_new, flow_new, vendor_new, branch_new, task_new]:
                if re.search(r'^\s*$', cell):
                    Dialog('Error', "Empty %s name!" % list(locals().keys())[list(locals().values()).index(cell)].replace('_new', ''), QMessageBox.Critical)
                    return

            if not self.item == 'branches':
                block = self.raw_table_model.index(i, 0).data()
                version = self.raw_table_model.index(i, 1).data()
                flow = self.raw_table_model.index(i, 2).data()
                vendor = self.raw_table_model.index(i, 3).data()
                branch = self.raw_table_model.index(i, 4).data()
                task = self.raw_table_model.index(i, 5).data()

                if (self.item == 'block' and (block == block_new or block_new == '')) or (self.item == 'version' and (version == version_new or version_new == '')) or \
                        (self.item == 'flow' and (flow == flow_new or flow_new == '')) or (self.item == 'vendor' and (vendor == vendor_new or vendor_new == '')) or \
                        (self.item == 'branch' and (branch == branch_new or branch_new == '')) or (self.item == 'task' and (task == task_new or task_new == '')):
                    Dialog('Error', "Please give a new %s name!" % self.item, QMessageBox.Critical)
                    return
            else:
                if branch_new == '' or (self.copy_branches_row_mapping[i] is not False and self.copy_branches_row_mapping[i] == branch_new):
                    Dialog('Error', "Please give a new branch name!", QMessageBox.Critical)
                    return

            # Update dependency dic
            raw_block = self.raw_table_model.index(i, 0).data()
            raw_version = self.raw_table_model.index(i, 1).data()
            raw_flow = self.raw_table_model.index(i, 2).data()
            raw_vendor = self.raw_table_model.index(i, 3).data()
            raw_branch = self.raw_table_model.index(i, 4).data()
            raw_task = self.raw_table_model.index(i, 5).data()

            block_flag = False if raw_block == block_new else True
            version_flag = False if raw_version == version_new else True
            flow_flag = False if raw_flow == flow_new else True
            vendor_flag = False if raw_vendor == vendor_new else True
            branch_flag = False if raw_branch == branch_new else True
            task_flag = False if raw_task == task_new else True

            block_tmp = block_new if block_flag else raw_block
            version_tmp = version_new if version_flag else raw_version
            flow_tmp = flow_new if flow_flag else raw_flow
            vendor_tmp = vendor_new if vendor_flag else raw_vendor
            branch_tmp = branch_new if branch_flag else raw_branch

            if block_new not in self.dependency_dic:
                if version_flag or flow_flag or vendor_flag or branch_flag or task_flag:
                    self.dependency_dic.setdefault(block_new, {})
                else:
                    self.dependency_dic[block_new] = copy.deepcopy(self.dependency_dic[raw_block])

            if version_new not in self.dependency_dic[block_tmp]:
                if flow_flag or vendor_flag or branch_flag or task_flag:
                    self.dependency_dic[block_tmp].setdefault(version_new, {})
                    self.dependency_dic[block_tmp][version_new].setdefault('flow_dependency', {})
                    self.dependency_dic[block_tmp][version_new].setdefault('task_dependency', {})
                else:
                    self.dependency_dic[block_tmp][version_new] = copy.deepcopy(self.dependency_dic[raw_block][raw_version])

            if flow_new not in self.dependency_dic[block_tmp][version_tmp]['flow_dependency']:
                self.dependency_dic[block_tmp][version_tmp]['flow_dependency'][flow_new] = copy.deepcopy(self.dependency_dic[raw_block][raw_version]['flow_dependency'][raw_flow])

                if vendor_flag or branch_flag or task_flag:
                    self.dependency_dic[block_tmp][version_tmp]['task_dependency'].setdefault(flow_new, {})
                else:
                    self.dependency_dic[block_tmp][version_tmp]['task_dependency'][flow_new] = copy.deepcopy(self.dependency_dic[raw_block][raw_version]['task_dependency'][raw_flow])

            if vendor_new not in self.dependency_dic[block_tmp][version_tmp]['task_dependency'][flow_tmp]:
                if branch_flag or task_flag:
                    self.dependency_dic[block_tmp][version_tmp]['task_dependency'][flow_tmp].setdefault(vendor_new, {})
                else:
                    self.dependency_dic[block_tmp][version_tmp]['task_dependency'][flow_tmp][vendor_new] = copy.deepcopy(self.dependency_dic[raw_block][raw_version]['task_dependency'][raw_flow][raw_vendor])

            if branch_new not in self.dependency_dic[block_tmp][version_tmp]['task_dependency'][flow_tmp][vendor_tmp]:
                if task_flag:
                    self.dependency_dic[block_tmp][version_tmp]['task_dependency'][flow_tmp][vendor_tmp].setdefault(branch_new, {})
                else:
                    self.dependency_dic[block_tmp][version_tmp]['task_dependency'][flow_tmp][vendor_tmp][branch_new] = copy.deepcopy(self.dependency_dic[raw_block][raw_version]['task_dependency'][raw_flow][raw_vendor][raw_branch])

            if task_new not in self.dependency_dic[block_tmp][version_tmp]['task_dependency'][flow_tmp][vendor_tmp][branch_tmp]:
                self.dependency_dic[block_tmp][version_tmp]['task_dependency'][flow_tmp][vendor_tmp][branch_tmp][task_new] = copy.deepcopy(self.dependency_dic[raw_block][raw_version]['task_dependency'][raw_flow][raw_vendor][raw_branch][raw_task])

            if not block_new == self.table_info[i][0] and not self.span_info[i][0] == {}:
                self.table_info[i][0] = block_new

                for j in range(i + 1, self.span_info[i][0] + 1):
                    self.new_table_model.setItem(j, 0, QStandardItem(block_new))
                    self.table_info[j][0] = block_new

            if not version_new == self.table_info[i][1] and not self.span_info[i][1] == {}:
                self.table_info[i][1] = version_new

                for j in range(i + 1, self.span_info[i][1] + 1):
                    self.new_table_model.setItem(j, 1, QStandardItem(version_new))
                    self.table_info[j][1] = version_new

            if not flow_new == self.table_info[i][2] and not self.span_info[i][2] == {}:
                self.table_info[i][2] = flow_new

                for j in range(i + 1, self.span_info[i][2] + 1):
                    self.new_table_model.setItem(j, 2, QStandardItem(flow_new))
                    self.table_info[j][2] = flow_new

            if not vendor_new == self.table_info[i][3] and not self.span_info[i][3] == {}:
                self.table_info[i][3] = vendor_new

                for j in range(i + 1, self.span_info[i][3] + 1):
                    self.new_table_model.setItem(j, 3, QStandardItem(vendor_new))
                    self.table_info[j][3] = vendor_new

            if not branch_new == self.table_info[i][4] and not self.span_info[i][4] == {}:
                self.table_info[i][4] = branch_new

                for j in range(i + 1, self.span_info[i][4] + 1):
                    self.new_table_model.setItem(j, 4, QStandardItem(branch_new))
                    self.table_info[j][4] = branch_new

            if not self.user_input['BLOCK'][block_new][version_new][flow_new][vendor_new][branch_new][task_new]:
                if self.item == 'task':
                    all_tasks = list(self.user_input['BLOCK'][block_new][version_new][flow_new][vendor_new][branch_new].keys())
                    index = all_tasks.index(self.task)
                    all_tasks.insert(index + 1, task_new)
                    self.user_input['BLOCK'][block_new][version_new][flow_new][vendor_new][branch_new] = {}

                    for k in all_tasks:
                        self.user_input['BLOCK'][block_new][version_new][flow_new][vendor_new][branch_new][k] = ''
                else:
                    self.user_input['BLOCK'][block_new][version_new][flow_new][vendor_new][branch_new][task_new] = ''

            if not self.item == 'branches':
                if not self.detailed_setting[block_new][version_new][flow_new][vendor_new][branch_new][task_new]:
                    self.detailed_setting[block_new][version_new][flow_new][vendor_new][branch_new][task_new] = copy.deepcopy(self.detailed_setting[block][version][flow][vendor][branch][task])
            else:
                if self.copy_branches_row_mapping[i] is not False:
                    self.detailed_setting[block_new][version_new][flow_new][vendor_new][branch_new][task_new] = copy.deepcopy(self.detailed_setting[block_new][version_new][flow_new][vendor_new][self.copy_branches_row_mapping[i]][task_new])

            if not self.item == 'branches':
                if not flow_new == flow:
                    update_flow_flag = True

        if update_flow_flag:
            self.message.emit(['update flow'])
        elif self.item == 'task':
            self.message.emit([self.item, task_new])
        else:
            self.message.emit([self.item])

        self.save_signal.emit()
        self.close()


class WindowForDetailedTaskInfo(QMainWindow):
    message = pyqtSignal(list)

    def __init__(self, user_input, default_setting, detailed_setting, blank_setting, default_var, cwd, block, version, flow, vendor, branch, task, var, read_only):
        super().__init__()
        self.top_widget = QWidget()
        self.top_layout = QVBoxLayout()
        self.top_widget.setLayout(self.top_layout)
        self.setCentralWidget(self.top_widget)
        self.user_input = user_input
        self.default_setting = default_setting
        self.detailed_setting = detailed_setting
        self.blank_setting = blank_setting
        self.default_var = default_var
        self.cwd = cwd
        self.block = block
        self.version = version
        self.flow = flow
        self.vendor = vendor
        self.branch = branch
        self.raw_task = task
        self.new_task = task
        self.var = var
        self.raw_setting = AutoVivification()
        self.tips = AutoVivification()
        self.invalid_dic = check_task_items(self.detailed_setting)
        self.read_only = read_only

        self.all_tasks = self.user_input['BLOCK'][self.block][self.version][self.flow][self.vendor][self.branch].keys()

        self.widget_task_name = QWidget()
        self.layout_task_name = QHBoxLayout()
        self.widget_task_name.setLayout(self.layout_task_name)

        self.label_task_name = QLabel('Task name :')
        self.label_task_name.setStyleSheet('font-weight : bold;font-size : 15px')
        self.line_edit_task_name = QLineEdit(task)
        self.line_edit_task_name.setFixedWidth(100)
        self.line_edit_task_name.textChanged.connect(self.draw_table)
        self.label_info = QLabel()
        self.label_info.setStyleSheet('font-size : 12px')

        self.layout_task_name.addWidget(self.label_task_name)
        self.layout_task_name.addWidget(self.line_edit_task_name)
        self.layout_task_name.addWidget(self.label_info)

        self.layout_task_name.setStretch(0, 1)
        self.layout_task_name.setStretch(1, 5)
        self.layout_task_name.setStretch(2, 20)

        header = ['Item', 'Value']
        self.label_env = QLabel('Env setting (Non editable):')
        self.label_env.setStyleSheet('font-weight : bold;')
        self.env_table = QTableView()
        self.env_model = QStandardItemModel(1, 2)
        self.env_table.setModel(self.env_model)
        self.env_table.setColumnWidth(0, 180)
        self.env_model.setHorizontalHeaderLabels(header)
        self.env_table.setStyleSheet('font-family : calibri; font-size : 15px')
        self.env_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.env_table.setShowGrid(True)
        self.env_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.env_table.setSelectionMode(QAbstractItemView.NoSelection)

        self.label_setup = QLabel('Flow setting :')
        self.label_setup.setStyleSheet('font-weight : bold')
        self.setup_table = QTableView()
        self.setup_table.setMouseTracking(True)
        self.setup_table.entered.connect(self.show_tips)
        self.setup_model = QStandardItemModel(1, 2)
        self.setup_table.setModel(self.setup_model)
        self.setup_table.setColumnWidth(0, 140)

        self.setup_model.setHorizontalHeaderLabels(header)
        self.setup_table.setStyleSheet('font-family : calibri; font-size : 15px')
        self.setup_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.setup_table.setShowGrid(True)

        # Defined by system
        self.env_mapping = {'${PROJECT}': self.user_input['PROJECT'],
                            '${GROUP}': self.user_input['GROUP'],
                            '${CWD}': self.cwd,
                            '${IFP_INSTALL_PATH}': os.getenv('IFP_INSTALL_PATH'),
                            '${BLOCK}': self.block,
                            '${VERSION}': self.version,
                            '${FLOW}': self.flow,
                            '${VENDOR}': self.vendor,
                            '${BRANCH}': self.branch,
                            '${TASK}': self.raw_task,
                            }

        # Defined by default yaml
        for key in self.default_var.keys():
            self.env_mapping.setdefault('${%s}' % key, self.default_var[key])

        # Defined by user VAR and will replace system and default env setting
        for key in self.var.keys():
            self.env_mapping['${' + key + '}'] = self.var[key]

        row = 0
        for category in self.env_mapping.keys():
            item = QStandardItem('%s' % category)
            item.setTextAlignment(Qt.AlignLeft)
            item.setTextAlignment(Qt.AlignVCenter)
            self.env_model.setItem(row, 0, item)

            item = QStandardItem('%s' % self.env_mapping[category])
            item.setTextAlignment(Qt.AlignLeft)
            item.setTextAlignment(Qt.AlignVCenter)
            self.env_model.setItem(row, 1, item)
            row += 1

        self.draw_table(self.raw_task, 'raw')
        self.float_env_button = QPushButton('Show Variable ->')
        self.float_env_button.clicked.connect(self.float_env_setting)
        self.save_button = QPushButton('save')
        self.save_button.clicked.connect(self.save)
        self.cancel_button = QPushButton('cancel')
        self.cancel_button.clicked.connect(self.close)

        env_dic = {}

        for key, value in self.env_mapping.items():
            if my_match := re.match(r'\$\{(\S+)\}', key):
                env_dic[my_match.group(1)] = value

        var_setting_window = WindowForToolGlobalEnvEditor(default_var=env_dic, user_var={}, window='edit_task')
        self.var_setting_table = var_setting_window.init_ui()

        self.env_floating_flag = False

        self.button_widget = QWidget()
        self.button_layout = QHBoxLayout()
        self.button_widget.setLayout(self.button_layout)

        self.button_layout.addStretch(1)
        self.button_layout.addWidget(self.save_button)
        self.button_layout.addWidget(self.cancel_button)

        self.main_layout = QHBoxLayout()
        self.setup_layout = QVBoxLayout()

        setting_layout = QHBoxLayout()
        setting_layout.addWidget(self.widget_task_name)
        setting_layout.addStretch(1)
        setting_layout.addWidget(self.float_env_button)
        self.setup_layout.addWidget(self.label_env, 1)
        self.setup_layout.addWidget(self.env_table, 5)
        self.setup_layout.addWidget(self.setup_table, 14)

        self.main_layout.addLayout(self.setup_layout, 10)
        self.main_layout.addWidget(self.var_setting_table, 7)
        self.var_setting_table.hide()

        self.top_layout.addLayout(setting_layout)
        self.top_layout.addLayout(self.main_layout, 20)
        self.top_layout.addWidget(self.button_widget, 1)
        self.hide_env()
        common_pyqt5.auto_resize(self, 800, 800)
        center(self)

        self.child = None

        if self.read_only:
            self.setup_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
            self.save_button.setEnabled(False)
            self.line_edit_task_name.setEnabled(False)

    def draw_table(self, new_task, draw_type='new'):
        self.new_task = new_task
        self.env_model.setItem(7, 1, QStandardItem(new_task))
        self.title = '%s/%s/%s (Read Only)' % (self.flow, self.vendor, self.new_task) if self.read_only else '%s/%s/%s' % (self.flow, self.vendor, self.new_task)
        self.setWindowTitle('Detailed setting for %s' % self.title)

        self.setup_model.setRowCount(0)
        row = 0

        task_for_default_setting = ''
        if self.flow in self.default_setting.keys():
            if self.vendor in self.default_setting[self.flow].keys():
                if self.new_task in self.default_setting[self.flow][self.vendor].keys():
                    task_for_default_setting = self.new_task
                    self.label_info.setText('1. Default setting from %s as white line\n2. Highlighted blue line is user defined setting' % self.new_task)
                elif not self.raw_task == self.new_task and self.raw_task in self.default_setting[self.flow][self.vendor].keys():
                    task_for_default_setting = self.raw_task
                    self.label_info.setText('1. Keep default setting from %s as white line due to %s not define in default.yaml\n2. Highlighted blue line is user defined setting' % (self.raw_task, self.new_task))
                else:
                    self.label_info.setText('1. Missing default setting for %s-%s-%s\n2. Highlighted blue line is user defined setting' % (self.flow, self.vendor, self.new_task))
            else:
                self.label_info.setText('1. Missing default setting for %s-%s-%s\n2. Highlighted blue line is user defined setting' % (self.flow, self.vendor, self.new_task))
        else:
            self.label_info.setText('1. Missing default setting for %s-%s-%s\n2. Highlighted blue line is user defined setting' % (self.flow, self.vendor, self.new_task))

        for category in self.blank_setting.keys():
            item = QStandardItem('* %s' % category)
            item.setTextAlignment(Qt.AlignLeft)
            item.setTextAlignment(Qt.AlignVCenter)
            item.setEditable(False)
            f = QFont('Calibri', 15)
            f.setBold(True)
            item.setFont(f)
            item.setBackground(QBrush(QColor(245, 255, 250)))
            item.setForeground(QBrush(QColor(0, 0, 0)))
            self.setup_model.setItem(row, 0, item)
            self.setup_table.setSpan(row, 0, 1, 2)
            row += 1

            for key in self.blank_setting[category].keys():

                item = QStandardItem(key)
                item.setTextAlignment(Qt.AlignLeft)
                item.setTextAlignment(Qt.AlignVCenter)
                item.setEditable(False)
                self.setup_model.setItem(row, 0, item)

                if category in self.invalid_dic.keys():
                    if key in self.invalid_dic[category]:
                        item.setForeground(QBrush(QColor(255, 0, 0)))
                        item.setFont(QFont('Calibri', 11, 1000))

                value = ''

                if category in self.detailed_setting.keys():
                    if key in self.detailed_setting[category].keys():
                        if not self.detailed_setting[category][key] == {}:
                            value = self.detailed_setting[category][key]
                            item = QStandardItem(value)
                            item.setBackground(QBrush(QColor(100, 149, 237)))

                if value == '':
                    # Current flow/vendor not in default setting
                    if self.default_setting == {}:
                        pass
                    else:
                        if not task_for_default_setting == '':
                            if category in self.default_setting[self.flow][self.vendor][task_for_default_setting].keys():
                                if key in self.default_setting[self.flow][self.vendor][task_for_default_setting][category].keys():
                                    if not self.default_setting[self.flow][self.vendor][task_for_default_setting][category][key] == {}:
                                        value = self.default_setting[self.flow][self.vendor][task_for_default_setting][category][key]
                                        item = QStandardItem(value)
                                        item.setBackground(QBrush(QColor(255, 255, 255)))

                if value == '':
                    item = QStandardItem(value)
                    item.setBackground(QBrush(QColor(255, 255, 255)))

                if key == 'REQUIRED_LICENSE':
                    item = QStandardItem(value)
                    item.setTextAlignment(Qt.AlignCenter)
                    button = QPushButton(value)
                    button.setStyleSheet('text-align:left')
                    button.clicked.connect(self.edit_required_license)

                    if self.read_only:
                        button.setEnabled(False)

                    self.setup_model.setItem(row, 1, item)
                    index = self.setup_model.indexFromItem(item)
                    self.setup_table.setIndexWidget(index, button)

                # Record raw task setting
                if draw_type == 'raw':
                    self.raw_setting[category][key] = value

                if 'gui_type' in self.blank_setting[category][key].keys():
                    if self.blank_setting[category][key]['gui_type'] == 'option':
                        item = QStandardItem('')
                        combobox = QComboBox2()
                        combobox.setEditable(True)
                        combobox.lineEdit().setAlignment(Qt.AlignCenter)
                        combobox.addItems(self.blank_setting[category][key]['options'])
                        self.setup_model.setItem(row, 1, item)
                        index = self.setup_model.indexFromItem(item)
                        self.setup_table.setIndexWidget(index, combobox)

                        if value == '':
                            combobox.setCurrentText(self.blank_setting[category][key]['options'][0])
                        else:
                            combobox.setCurrentText(value)

                else:
                    self.tips[row] = self.blank_setting[category][key]['example']
                    item.setTextAlignment(Qt.AlignLeft)
                    item.setTextAlignment(Qt.AlignVCenter)
                    self.setup_model.setItem(row, 1, item)

                row += 1

    def edit_required_license(self):
        row = self.setup_table.indexAt(self.sender().pos()).row()
        text = self.setup_model.index(row, 1).data()
        self.child = WindowForEditRequiredLicense(row, text)
        self.child.setWindowModality(Qt.ApplicationModal)
        self.child.message.connect(self.update_required_license)
        self.child.show()

    def update_required_license(self, row, text):
        self.setup_model.setItem(row, 1, QStandardItem(text))
        button = self.setup_table.indexWidget(self.setup_model.index(row, 1))
        button.setText(text)

    def show_tips(self, index):
        desktop = QApplication.desktop()
        screen_num = desktop.screenNumber(QCursor.pos())
        screen_rect = desktop.screenGeometry(screen_num)

        if index.data() == '' and index.column() == 1 and index.row() in self.tips.keys():
            QToolTip.showText(QCursor.pos(), 'Example : ' + self.tips[index.row()], self.setup_table, screen_rect, 10000)

    def save(self):
        if not self.raw_task == self.new_task:
            if self.new_task in self.all_tasks:
                QMessageBox.critical(self, "Error", "%s already exist, please update task name" % self.new_task, QMessageBox.Ok)
                return

            reply = QMessageBox.question(self, "Warning", "Are you sure to change task name from %s to %s? \n Flow will copy all setting, please confirm if any special setting for %s!" % (self.raw_task, self.new_task, self.new_task), QMessageBox.Yes | QMessageBox.No)

            if reply == QMessageBox.Yes:
                pass
            elif reply == QMessageBox.No:
                return

        setting = AutoVivification()
        category = ''
        warning_info = ''
        warning_num = 0

        for i in range(self.setup_model.rowCount()):
            item = self.setup_model.index(i, 0).data()
            value = self.setup_model.index(i, 1).data()

            if re.search(r'\*\s+(.*)', item):
                category = re.search(r'\*\s+(.*)', item).group(1)
            else:
                if 'gui_type' in self.blank_setting[category][item].keys():
                    if self.blank_setting[category][item]['gui_type'] == 'option':
                        value = self.setup_table.indexWidget(self.setup_model.index(i, 1)).currentText()

                setting[category][item] = value

            if value == '':
                if category in self.detailed_setting.keys() and category in self.default_setting[self.flow][self.vendor][self.new_task].keys():
                    if item in self.detailed_setting[category].keys() and item in self.default_setting[self.flow][self.vendor][self.new_task][category].keys():
                        if not self.detailed_setting[category][item] == {} and not self.default_setting[self.flow][self.vendor][self.new_task][category][item] == {}:
                            warning_num += 1
                            warning_info += '%s. Remove user_defined_setting <b>[%s]</b> for %s/%s, flow will replace it with default_setting <b>[%s]</b><br/>\n' % (
                                warning_num, self.detailed_setting[category][item], category, item, self.default_setting[self.flow][self.vendor][self.new_task][category][item])

        if warning_info:
            warning_info += '<br/>If you want to keep your setting, please return and press cancel button'
            reply = QMessageBox.question(self, "Confirm Your Changes", warning_info, QMessageBox.Yes | QMessageBox.No)

            if reply == QMessageBox.Yes:
                pass
            elif reply == QMessageBox.No:
                return

        self.message.emit([setting, self.new_task])

        self.close()

    def float_env_setting(self):
        if self.env_floating_flag:
            self.float_env_button.setText('Show Variable ->')
            self.var_setting_table.hide()
            self.env_floating_flag = False
            common_pyqt5.auto_resize(self, 800, 800)
        else:
            self.hide_env()
            self.float_env_button.setText('<- Hide Variable')
            self.env_floating_flag = True
            self.var_setting_table.show()
            common_pyqt5.auto_resize(self, 1350, 800)

    def hide_env(self):
        self.label_env.hide()
        self.env_table.hide()

    def show_env(self):
        self.label_env.show()
        self.env_table.show()


class WindowForEditRequiredLicense(QMainWindow):
    message = pyqtSignal(int, str)

    def __init__(self, row, required_license):
        super().__init__()
        self.required_license = required_license
        self.row = row
        self.init_ui()

    def init_ui(self):
        title = 'Edit Required License'
        self.setFixedWidth(600)
        self.setFixedHeight(300)
        self.setWindowTitle(title)

        self.top_widget = QWidget()
        self.top_layout = QVBoxLayout()
        self.top_widget.setLayout(self.top_layout)
        self.setCentralWidget(self.top_widget)
        self.setup_table = QTableView()
        self.setup_model = QStandardItemModel(10, 2)
        self.setup_table.setModel(self.setup_model)
        self.setup_table.setColumnWidth(0, 140)

        self.setup_model.setHorizontalHeaderLabels(['Feature', 'Required quantity'])
        self.setup_table.setStyleSheet('font-family : calibri; font-size : 15px')
        self.setup_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.setup_table.setShowGrid(True)
        self.setup_table.setColumnWidth(0, 400)

        self.save_button = QPushButton('save')
        self.save_button.clicked.connect(self.save)
        self.cancel_button = QPushButton('cancel')
        self.cancel_button.clicked.connect(self.close)

        self.button_widget = QWidget()
        self.button_layout = QHBoxLayout()
        self.button_widget.setLayout(self.button_layout)

        self.button_layout.addStretch(1)
        self.button_layout.addWidget(self.save_button)
        self.button_layout.addWidget(self.cancel_button)

        self.top_layout.addWidget(self.setup_table)
        self.top_layout.addWidget(self.button_widget)

        row = 0
        for i in self.required_license.split(','):
            if len(i.split(':')) == 2:
                feature = i.split(':')[0].strip()
                quantity = i.split(':')[1].strip()

                item = QStandardItem(feature)
                item.setTextAlignment(Qt.AlignLeft)
                item.setTextAlignment(Qt.AlignVCenter)
                item.setEditable(True)
                self.setup_model.setItem(row, 0, item)

                item = QStandardItem(quantity)
                item.setTextAlignment(Qt.AlignLeft)
                item.setTextAlignment(Qt.AlignVCenter)
                item.setEditable(True)
                self.setup_model.setItem(row, 1, item)
                row += 1

    def save(self):
        text = []

        for i in range(self.setup_model.rowCount()):
            feature = self.setup_model.index(i, 0).data()

            if not feature:
                continue

            quantity = self.setup_model.index(i, 1).data()

            text.append('%s : %s' % (feature, quantity))

        self.message.emit(self.row, ',  '.join(text))

        self.close()


class WindowForDependency(QMainWindow):
    message = pyqtSignal(str, dict)
    update = pyqtSignal(bool, str)

    def __init__(self, dependency_priority_dic=None, default_dependency_dic=None, mode='window'):
        super().__init__()

        self.dependency_priority_dic = dependency_priority_dic
        self.origin_dependency_priority_dic = copy.deepcopy(self.dependency_priority_dic)
        self.default_dependency_dic = default_dependency_dic
        self.current_block = list(self.dependency_priority_dic.keys())[0]
        self.current_version = list(self.dependency_priority_dic[self.current_block].keys())[0]
        self.current_dependency_priority_dic = dependency_priority_dic[self.current_block][self.current_version]

        self.dependency_clipboard = {}
        self.table_item_condition_dic = {}

        self.gen_current_picture_dir()
        self.mode = mode
        self.modify_item_set = set()
        self.gui_enable_flag = True
        self.init_ui()

        self.update_flag = 'dependency'

    def gen_current_picture_dir(self):
        """
        mkdir CWD/.picture directory in order to save flow chart
        """
        self.picture_dir = os.path.join(os.getcwd(), '.pictures/%s/%s/' % (self.current_block, self.current_version))

        if not os.path.exists(self.picture_dir):
            os.makedirs(self.picture_dir)

    def init_ui(self):
        title = 'Dependency Setting'

        screen_resolutions = self.get_screen_resolutions()

        for width, height in screen_resolutions:
            width_rate = int((width / 1100) * 10) / 10 if width < 1100 else 1
            self.width_scale_rate = width_rate if width_rate < 1 else 1

            height_rate = int((height / 650) * 10) / 10 if height < 650 else 1
            self.height_scale_rate = height_rate if height_rate < 1 else 1

        self.setWindowTitle(title)

        self.top_widget = QWidget()
        self.top_layout = QVBoxLayout()
        self.top_widget.setLayout(self.top_layout)
        self.setCentralWidget(self.top_widget)

        self.selection_widget = QWidget()

        self.main_widget = QWidget()
        self.main_layout = QHBoxLayout()
        self.main_widget.setLayout(self.main_layout)

        self.top_layout.addWidget(self.selection_widget, 0)
        self.top_layout.addWidget(self.main_widget, 1)
        self.top_layout.setStretch(0, 1)
        self.top_layout.setStretch(1, 10)

        self.tables = {}
        self.current_table = None
        self.current_chart = None

        self.tree = QTreeWidget()
        self.before_tree_item = None
        self.tree.clicked.connect(self.generate_selection)
        self.main_layout.addWidget(self.tree, 1)

        self.gen_main_tab()

        self.gen_dependency_chart(chart_name='flow_chart', dependency_dic=self.current_dependency_priority_dic['flow_dependency'])

        self.current_table = self.tables['flow_dependency']

        self.save_button = QPushButton('SAVE')
        self.save_button.clicked.connect(self.save)

        if self.mode == 'window':
            self.cancel_button = QPushButton('CANCEL')
            self.cancel_button.clicked.connect(self.close)
        elif self.mode == 'widget':
            self.reset_button = QPushButton('RESET')
            self.reset_button.clicked.connect(self.reset)
            self.save_button.setEnabled(False)

        self.button_widget = QWidget()
        self.button_layout = QHBoxLayout()
        self.button_widget.setFixedHeight(50 * self.height_scale_rate)

        self.button_widget.setLayout(self.button_layout)
        self.button_layout.addStretch(1)
        self.button_layout.addWidget(self.save_button)

        if self.mode == 'window':
            self.button_layout.addWidget(self.cancel_button)
        elif self.mode == 'widget':
            self.button_layout.addWidget(self.reset_button)

        self.top_layout.addWidget(self.button_widget, 2)

        center_window(self)
        self.current_table.show()

        return self

    def gen_main_tab(self):
        self.gen_selection_button()
        self.gen_tree()
        self.gen_tables()

    def gen_selection_button(self):
        """
        select current block/version
        """
        block_label = QLabel('Block', self.selection_widget)
        block_label.setStyleSheet("font-weight: bold;")
        block_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.block_combo = QComboBox(self.selection_widget)
        self.block_combo.addItems(list(self.dependency_priority_dic.keys()))
        self.block_combo.activated.connect(self.set_version_combo)

        version_label = QLabel('Version', self.selection_widget)
        version_label.setStyleSheet("font-weight: bold;")
        version_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.version_combo = QComboBox(self.selection_widget)
        self.version_combo.addItems(list(self.dependency_priority_dic[self.current_block].keys()))
        self.version_combo.activated.connect(self.update_tree_table_frame)

        button_layout = QGridLayout()
        button_layout.addWidget(block_label, 0, 0)
        button_layout.addWidget(self.block_combo, 0, 1)
        button_layout.addWidget(version_label, 0, 2)
        button_layout.addWidget(self.version_combo, 0, 3)
        button_layout.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)

        self.selection_widget.setLayout(button_layout)

    def gen_tree(self):
        """
        current block - version dependency tree
        """
        self.tree.clear()
        self.tree.setHeaderHidden(True)
        self.tree.horizontalScrollBar().hide()

        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.generate_tree_menu)

        self.tree.setStyleSheet("QTreeView::item:hover{color:#CDB5CD;}"
                                "QTreeView::item:selected{color:#4F94CD;}")

        tree_parent = QTreeWidgetItem(self.tree)
        tree_parent.setText(0, r'%s -> %s' % (self.current_block, self.current_version))
        tree_parent.setForeground(0, QBrush(QColor(0, 0, 0)))
        tree_parent.setFont(0, QFont('Calibri', 10, QFont.Bold))
        tree_parent.setSelected(True)
        tree_parent.setExpanded(True)

        for flow in list(self.current_dependency_priority_dic['flow_dependency'].keys()):
            flow_parent = QTreeWidgetItem(tree_parent)
            flow_parent.setText(0, flow)
            flow_parent.setFont(0, QFont('Calibri', 10))
            flow_parent.setSelected(False)
            flow_parent.setExpanded(True)

            for vendor in list(self.current_dependency_priority_dic['task_dependency'][flow].keys()):
                for branch in list(self.current_dependency_priority_dic['task_dependency'][flow][vendor].keys()):
                    task_child = QTreeWidgetItem(flow_parent)
                    task_child.setText(0, r'%s -> %s' % (vendor, branch))
                    task_child.setFont(0, QFont('Calibri', 10))
                    task_child.setSelected(False)
                    task_child.setExpanded(False)

        self.tree.setCurrentItem(tree_parent)
        return self.tree

    def set_version_combo(self):
        block = self.block_combo.currentText().strip()

        if block and (block in self.dependency_priority_dic.keys()):
            self.version_combo.clear()

            for version in self.dependency_priority_dic[block].keys():
                self.version_combo.addItem(version)

        self.update_tree_table_frame()

    def update_tree_table_frame(self):
        self.current_block = self.block_combo.currentText().strip()
        self.current_version = self.version_combo.currentText().strip()

        self.gen_current_picture_dir()

        self.current_dependency_priority_dic = self.dependency_priority_dic[self.current_block][self.current_version]
        self.gen_tree()
        self.gen_tables()

        self.current_table.hide()
        self.current_table = self.tables['flow_dependency']
        self.current_table.show()

        self.gen_dependency_chart(chart_name='flow_chart', dependency_dic=self.current_dependency_priority_dic['flow_dependency'])

    def generate_selection(self):
        tree_item = self.tree.currentItem()
        view_name = tree_item.text(0)

        if self.before_tree_item:
            self.post_dependency_check()

        self.before_tree_item = tree_item

        if tree_item.child(0):
            if not tree_item.parent():
                self.update_dependency_show_info(view_name='flow_dependency')
            else:
                self.current_table.hide()
                self.current_chart.hide()
                return
        else:
            flow = tree_item.parent().text(0)

            if my_match := re.match(r'(.*)->(.*)', view_name):
                vendor = my_match.group(1).strip()
                branch = my_match.group(2).strip()

                self.update_dependency_show_info(view_name='task_dependency', flow=flow, vendor=vendor, branch=branch)

    def post_dependency_check(self):
        if not self.before_tree_item:
            return

        try:
            if not self.before_tree_item.child(0):
                pass
        except Exception:
            return

        if self.before_tree_item.child(0):
            if not self.before_tree_item.parent():
                for flow in self.current_dependency_priority_dic['flow_dependency'].keys():
                    repeat_condition_list = self.current_dependency_priority_dic['flow_dependency'][flow].split(',')
                    new_repeat_condition_list = []

                    for repeat_condition in repeat_condition_list:
                        parallel_condition_list = []

                        if not repeat_condition.split('|'):
                            new_repeat_condition_list.append(repeat_condition)
                            continue

                        for parallel_condition in repeat_condition.split('|'):
                            if parallel_condition.strip():
                                parallel_condition_list.append(parallel_condition)

                        new_repeat_condition_list.append('|'.join(parallel_condition_list))

                    self.current_dependency_priority_dic['flow_dependency'][flow] = '|'.join(new_repeat_condition_list)
        else:
            flow = self.before_tree_item.parent().text(0)

            if my_match := re.match(r'(.*)->(.*)', self.before_tree_item.text(0)):
                vendor = my_match.group(1).strip()
                branch = my_match.group(2).strip()

                for task in self.current_dependency_priority_dic['task_dependency'][flow][vendor][branch].keys():
                    repeat_condition_list = self.current_dependency_priority_dic['task_dependency'][flow][vendor][branch][task].split(',')
                    new_repeat_condition_list = []

                    for repeat_condition in repeat_condition_list:
                        parallel_condition_list = []

                        if not repeat_condition.split('|'):
                            new_repeat_condition_list.append(repeat_condition)
                            continue

                        for parallel_condition in repeat_condition.split('|'):
                            if parallel_condition.strip():
                                parallel_condition_list.append(parallel_condition)

                        new_repeat_condition_list.append('|'.join(parallel_condition_list))

                    self.current_dependency_priority_dic['task_dependency'][flow][vendor][branch][task] = '|'.join(new_repeat_condition_list)

        self.dependency_priority_dic[self.current_block][self.current_version] = self.current_dependency_priority_dic

    def gen_chart_frame(self, image_path, full_image_path):
        layout = QVBoxLayout()
        image_label = QLabel()
        layout.addWidget(image_label)

        pixmap = QPixmap(image_path)
        image_label.setPixmap(pixmap)
        image_label.setToolTip('<img src="%s.png">' % str(full_image_path))

        image_label.setAlignment(Qt.AlignCenter | Qt.AlignLeft)
        image_label.setStyleSheet("background-color: white ;border: 1px solid lightgray ;")
        image_label.setFixedWidth(360 * self.width_scale_rate)

        self.main_layout.addWidget(image_label)

        if self.current_chart:
            self.current_chart.hide()

        self.current_chart = image_label
        self.current_chart.show()

    def gen_dependency_chart(self, chart_name='', dependency_dic={}, graph_size=[3.2, 3.6]):
        node_list = list(dependency_dic.keys())
        flow_chart_dic = {}
        dot = graphviz.Digraph('round-table', comment='The Round Table')

        width = graph_size[0] * self.width_scale_rate
        height = graph_size[1] * self.height_scale_rate

        # basic element
        for node in node_list:
            if not re.match(r'^\s+$', node):
                dot.node(node, node, shape='box')
                flow_chart_dic.setdefault(node, [])

        # num
        link_node = 0

        # dependencies
        for node in dependency_dic:
            condition = dependency_dic[node]

            if not condition:
                continue

            # ^ the third priority
            third_condition_list = condition.split(',')

            if '' in third_condition_list:
                third_condition_list.remove('')

            second_link_list = []

            for third_condition in third_condition_list:
                # | the second priority
                second_condition_list = third_condition.split('|')

                if '' in second_condition_list:
                    second_condition_list.remove('')

                first_link_list = []

                for second_condition in second_condition_list:
                    # & the first priority
                    first_condition_list = second_condition.split('&')

                    if '' in first_condition_list:
                        first_condition_list.remove('')

                    if len(first_condition_list) == 1:
                        first_link_node = first_condition_list[0]
                    elif len(first_condition_list) > 1:
                        dot.node(str(link_node), '&', **{'width': '0.15', 'height': '0.15'})
                        flow_chart_dic.setdefault(str(link_node), [])
                        first_link_node = str(link_node)

                        for first_item in first_condition_list:
                            dot.edge(first_item, str(link_node))
                            flow_chart_dic[first_item].append(str(link_node))
                    else:
                        continue

                    link_node += 1
                    first_link_list.append(first_link_node)

                if len(first_link_list) == 1:
                    second_link_node = first_link_list[0]
                elif len(first_link_list) > 1:
                    dot.node(str(link_node), '|', **{'width': '0.15', 'height': '0.15'})
                    flow_chart_dic.setdefault(str(link_node), [])
                    second_link_node = str(link_node)

                    for second_item in first_link_list:
                        dot.edge(second_item, str(link_node))
                        flow_chart_dic[second_item].append(str(link_node))
                else:
                    continue

                link_node += 1
                second_link_list.append(second_link_node)

            for third_link_node in second_link_list:
                dot.edge(third_link_node, node)
                flow_chart_dic[third_link_node].append(node)

        dot.render(os.path.join(self.picture_dir, 'full_%s' % chart_name), format='png')
        dot.graph_attr['size'] = '%s, %s' % (str(width), str(height))
        dot.render(os.path.join(self.picture_dir, chart_name), format='png')

        self.gen_chart_frame(image_path=os.path.join(self.picture_dir, r'%s.png' % chart_name), full_image_path=os.path.join(self.picture_dir, 'full_%s' % chart_name))

    def check_dependency_setting(self, dependency_dic={}):
        """
        check dependency setting correctness
        including:
        1. loop -> dfs chart check
        2. the same condition (,, &, |)
        """
        check_status = True
        node_list = list(dependency_dic.keys())
        flow_chart_dic = {}

        # basic element
        for node in node_list:
            if not re.match(r'^\s+$', node):
                flow_chart_dic.setdefault(node, [])

        # num
        link_node = 0

        # dependencies
        for node in dependency_dic:
            condition = dependency_dic[node]

            if not condition:
                continue

            # ^ the third priority
            third_condition_list = condition.split(',')
            check_status = self.check_same_condition(third_condition_list)

            if not check_status:
                return check_status

            if '' in third_condition_list:
                third_condition_list.remove('')

            second_link_list = []

            for third_condition in third_condition_list:
                # | the second priority
                second_condition_list = third_condition.split('|')
                check_status = self.check_same_condition(third_condition_list)

                if not check_status:
                    return check_status

                if '' in second_condition_list:
                    second_condition_list.remove('')

                first_link_list = []

                for second_condition in second_condition_list:
                    # & the first priority
                    first_condition_list = second_condition.split('&')
                    check_status = self.check_same_condition(third_condition_list)

                    if not check_status:
                        return check_status

                    if '' in first_condition_list:
                        first_condition_list.remove('')

                    if len(first_condition_list) == 1:
                        first_link_node = first_condition_list[0]
                    elif len(first_condition_list) > 1:
                        flow_chart_dic.setdefault(str(link_node), [])
                        first_link_node = str(link_node)

                        for first_item in first_condition_list:
                            flow_chart_dic[first_item].append(str(link_node))
                    else:
                        continue

                    link_node += 1
                    first_link_list.append(first_link_node)

                if len(first_link_list) == 1:
                    second_link_node = first_link_list[0]
                elif len(first_link_list) > 1:
                    flow_chart_dic.setdefault(str(link_node), [])
                    second_link_node = str(link_node)

                    for second_item in first_link_list:
                        flow_chart_dic[second_item].append(str(link_node))
                else:
                    continue

                link_node += 1
                second_link_list.append(second_link_node)

            for third_link_node in second_link_list:
                flow_chart_dic[third_link_node].append(node)

        self.vis = []
        self.trace = []

        for node in flow_chart_dic.keys():
            check_status = self.dfs_check_loop(node, flow_chart_dic)

            if not check_status:
                return check_status

        return check_status

    @staticmethod
    def check_same_condition(check_list):
        check_status = True

        if len(check_list) != len(set(check_list)):
            check_status = False
            check_dic = {}

            for condition in check_list:
                if condition not in check_dic:
                    check_dic[condition] = 1
                else:
                    title = 'Warning'
                    info = 'Dependencies contains the same condition!'
                    Dialog(title, info)
                    return check_status

        return check_status

    def gen_table(self, flow='', vendor='', branch='', view_name='', item_list=[]):
        table = QTableWidget()
        table.setMouseTracking(True)

        # table format
        table.setSortingEnabled(True)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setVisible(True)

        # table row & column setting
        table.setColumnCount(4)

        if view_name == 'flow_dependency':
            table.setHorizontalHeaderLabels(['flow', 'add', 'del', 'dependency'])
        elif view_name == 'task_dependency':
            table.setHorizontalHeaderLabels(['task', 'add', 'del', 'dependency'])

        # table.setColumnWidth(0, 80)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        table.setColumnWidth(1, 25)
        table.setColumnWidth(2, 25)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)

        # table menu for add repeat setting
        if view_name == 'task_dependency':
            table.setContextMenuPolicy(Qt.CustomContextMenu)
            table.customContextMenuRequested.connect(functools.partial(self.generate_table_menu, table, flow, vendor, branch, view_name))

        # table context
        row_len = 0
        item_condition_dic = {}
        dependency_item_list = []
        item_condition_mapping = {}

        for item in item_list:
            item_condition_dic.setdefault(item, {})

            if flow and vendor and branch:
                dependency_item_list = [task for task in self.current_dependency_priority_dic['task_dependency'][flow][vendor][branch].keys()]
                condition = self.current_dependency_priority_dic['task_dependency'][flow][vendor][branch][item]
            else:
                dependency_item_list = [flow for flow in self.current_dependency_priority_dic['flow_dependency'].keys()]
                condition = self.current_dependency_priority_dic['flow_dependency'][item]

            repeat_condition_list = condition.split(',')

            if len(repeat_condition_list) == 1:
                item_condition_dic[item] = self.parse_dependency_condition(condition=condition)
                item_condition_mapping[item] = condition

                row_len += len(item_condition_dic[item].keys())
            else:
                item_num = 1

                for repeat_condition in repeat_condition_list:
                    new_item = r'%s - %s' % (item, str(item_num))
                    item_condition_dic[new_item] = self.parse_dependency_condition(condition=repeat_condition)
                    item_condition_mapping[new_item] = repeat_condition
                    item_num += 1

                    row_len += len(item_condition_dic[new_item].keys())

        table.setRowCount(row_len)
        row = 0

        for item in item_condition_dic.keys():
            item_name, _ = self.get_item_name(item)

            same_item_line = 0

            selectable_item_list = []

            for selectable_item in dependency_item_list:
                if selectable_item == item_name:
                    continue
                else:
                    selectable_item_list.append(selectable_item)

            for parallel_condition in item_condition_dic[item].keys():
                if same_item_line != 0:
                    name_item = QTableWidgetItem('')
                    name_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                    add_item = QTableWidgetItem('')
                    table.setItem(row, 1, add_item)
                else:
                    name_item = QTableWidgetItem(item_name)

                    if self.mode == 'widget':
                        if flow and vendor and branch:
                            modify_tuple = ('%s-%s-task-%s-%s-%s' % (self.current_block, self.current_version, flow, vendor, branch), item_name)
                        else:
                            modify_tuple = ('%s-%s-flow' % (self.current_block, self.current_version), item_name)

                        if modify_tuple in self.modify_item_set:
                            name_item.setForeground(QBrush(QColor(100, 149, 237)))
                            name_item.setFont(QFont('Calibri', 10, 500))

                    name_item.setWhatsThis(item)
                    name_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                    add_item = QPushButton('+')
                    add_item.setDown(False)

                    if not self.gui_enable_flag:
                        add_item.setEnabled(False)

                    table.setCellWidget(row, 1, add_item)
                    add_item.clicked.connect(functools.partial(self.add_condition, flow, vendor, branch, item))

                delete_item = QPushButton('-')
                delete_item.setDown(False)

                dependency_item = QComboCheckBox(table)
                dependency_item.setEditLineSeparator(separator='&')

                dependency_item.addCheckBoxItems(selectable_item_list)
                dependency_item.setItemsCheckStatus(item_condition_dic[item][parallel_condition])
                dependency_item.stateChangedconnect(functools.partial(self.change_condition_dependency_list, dependency_item, flow, vendor, branch, item, same_item_line))

                name_item.setToolTip(r'%s' % item_condition_mapping[item])
                table.setItem(row, 0, name_item)

                if not self.gui_enable_flag:
                    delete_item.setEnabled(False)
                    dependency_item.setItemsCheckEnable(False)

                table.setCellWidget(row, 2, delete_item)
                table.setCellWidget(row, 3, dependency_item)
                row += 1
                same_item_line += 1

                # table signal
                delete_item.clicked.connect(functools.partial(self.delete_condition, flow, vendor, branch, item, parallel_condition))

        if view_name == 'task_dependency':
            self.tables.setdefault(flow, {})
            self.tables[flow].setdefault(vendor, {})
            self.tables[flow][vendor].setdefault(branch, {})
            self.tables[flow][vendor][branch]['task_dependency'] = table
        else:
            self.tables['flow_dependency'] = table
            self.table_item_condition_dic[view_name] = item_condition_dic

        self.main_layout.addWidget(table, 1)
        table.hide()

    @staticmethod
    def get_item_name(item):
        if my_match := re.match(r'(\S+)\s+-\s+(\d+)', item):
            item_name = my_match.group(1)
            item_num = int(my_match.group(2)) - 1
        else:
            item_name = item
            item_num = 0
        return item_name, item_num

    def gen_tables(self):
        # generate flow table
        flow_list = list(self.current_dependency_priority_dic['flow_dependency'].keys())
        view_name = 'flow_dependency'
        self.gen_table(view_name=view_name, item_list=flow_list)

        # generate task table
        for flow in self.current_dependency_priority_dic['task_dependency'].keys():
            for vendor in self.current_dependency_priority_dic['task_dependency'][flow]:
                for branch in self.current_dependency_priority_dic['task_dependency'][flow][vendor]:
                    view_name = 'task_dependency'
                    task_list = list(self.current_dependency_priority_dic['task_dependency'][flow][vendor][branch].keys())
                    self.gen_table(flow=flow, vendor=vendor, branch=branch, view_name=view_name, item_list=task_list)

    @staticmethod
    def parse_dependency_condition(condition=''):
        parallel_condition_dic = {}

        if condition:
            parallel_condition_list = condition.split('|')

            if parallel_condition_list:
                for parallel_condition in parallel_condition_list:
                    parallel_condition_dic[parallel_condition] = parallel_condition.split('&')

        if not parallel_condition_dic:
            parallel_condition_dic[''] = ['']

        return parallel_condition_dic

    def add_condition(self, flow='', vendor='', branch='', item_text=''):
        if not item_text:
            return

        item_name, item_num = self.get_item_name(item_text)

        if flow and vendor and branch:
            view_name = 'task_dependency'
            repeat_condition_list = self.current_dependency_priority_dic[view_name][flow][vendor][branch][item_name].split(',')
            new_repeat_condition = '|'.join([repeat_condition_list[item_num], ''])
            new_repeat_condition_list = [repeat_condition_list[i] if i != item_num else new_repeat_condition for i in range(len(repeat_condition_list))]

            self.current_dependency_priority_dic[view_name][flow][vendor][branch][item_name] = ','.join(new_repeat_condition_list)
            self.update_dependency_show_info(view_name=view_name, flow=flow, vendor=vendor, branch=branch, modify_item=item_name)
        else:
            view_name = 'flow_dependency'
            repeat_condition_list = self.current_dependency_priority_dic[view_name][item_name].split(',')
            new_repeat_condition = '|'.join([repeat_condition_list[item_num], ''])
            new_repeat_condition_list = [repeat_condition_list[i] if i != item_num else new_repeat_condition for i in range(len(repeat_condition_list))]

            self.current_dependency_priority_dic[view_name][item_name] = ','.join(new_repeat_condition_list)
            self.update_dependency_show_info(view_name=view_name, modify_item=item_name)

        self.dependency_priority_dic[self.current_block][self.current_version] = self.current_dependency_priority_dic

    def delete_condition(self, flow='', vendor='', branch='', item='', delete_condition=''):
        if not item:
            return

        item_name, item_num = self.get_item_name(item)

        if flow and vendor and branch:
            view_name = 'task_dependency'

            repeat_condition_list = self.current_dependency_priority_dic[view_name][flow][vendor][branch][item_name].split(',')
            parallel_condition_list = repeat_condition_list[item_num].split('|')
            condition_list = []

            for condition in parallel_condition_list:
                if condition != delete_condition:
                    condition_list.append(condition)

            new_repeat_condition = '|'.join(condition_list)
            new_repeat_condition_list = [repeat_condition_list[i] if i != item_num else new_repeat_condition for i in range(len(repeat_condition_list))]

            self.current_dependency_priority_dic[view_name][flow][vendor][branch][item_name] = ','.join(new_repeat_condition_list)
            self.update_dependency_show_info(view_name=view_name, flow=flow, vendor=vendor, branch=branch, modify_item=item_name)
        else:
            view_name = 'flow_dependency'

            repeat_condition_list = self.current_dependency_priority_dic[view_name][item_name].split(',')
            parallel_condition_list = repeat_condition_list[item_num].split('|')
            condition_list = []

            for condition in parallel_condition_list:
                if condition != delete_condition:
                    condition_list.append(condition)

            new_repeat_condition = '|'.join(condition_list)
            new_repeat_condition_list = [repeat_condition_list[i] if i != item_num else new_repeat_condition for i in range(len(repeat_condition_list))]

            self.current_dependency_priority_dic[view_name][item_name] = ','.join(new_repeat_condition_list)
            self.update_dependency_show_info(view_name=view_name, modify_item=item_name)

        self.dependency_priority_dic[self.current_block][self.current_version] = self.current_dependency_priority_dic

    def change_condition_dependency_list(self, dependency_item, flow='', vendor='', branch='', item='', condition_num=0):
        dependency_item_list = [item for index, item in dependency_item.selectedItems().items()]
        dependency_condition = '&'.join(dependency_item_list)
        condition_dic = {}

        item_name, item_num = self.get_item_name(item)

        if flow and vendor and branch:
            view_name = 'task_dependency'

            repeat_condition_list = self.current_dependency_priority_dic[view_name][flow][vendor][branch][item_name].split(',')
            repeat_condition = repeat_condition_list[item_num]

            for i in range(len(repeat_condition.split('|'))):
                parallel_condition = repeat_condition.split('|')[i]
                if condition_num == i:
                    condition_dic[dependency_condition] = ''
                else:
                    condition_dic[parallel_condition] = ''

            new_repeat_condition = '|'.join(list(condition_dic.keys()))
            new_repeat_condition_list = [repeat_condition_list[i] if i != item_num else new_repeat_condition for i in range(len(repeat_condition_list))]

            new_dependency_dic = copy.deepcopy(self.current_dependency_priority_dic[view_name][flow][vendor][branch])
            new_dependency_dic[item_name] = ','.join(new_repeat_condition_list)
            check_status = self.check_dependency_setting(new_dependency_dic)

            if check_status:
                self.current_dependency_priority_dic[view_name][flow][vendor][branch][item_name] = ','.join(new_repeat_condition_list)

            self.update_dependency_show_info(view_name=view_name, flow=flow, vendor=vendor, branch=branch, modify_item=item_name)
        else:
            view_name = 'flow_dependency'

            repeat_condition_list = self.current_dependency_priority_dic[view_name][item_name].split(',')
            repeat_condition = repeat_condition_list[item_num]

            for i in range(len(repeat_condition.split('|'))):
                parallel_condition = repeat_condition.split('|')[i]
                if condition_num == i:
                    condition_dic[dependency_condition] = ''
                else:
                    condition_dic[parallel_condition] = ''

            new_repeat_condition = '|'.join(list(condition_dic.keys()))
            new_repeat_condition_list = [repeat_condition_list[i] if i != item_num else new_repeat_condition for i in range(len(repeat_condition_list))]

            new_dependency_dic = copy.deepcopy(self.current_dependency_priority_dic[view_name])
            new_dependency_dic[item_name] = ','.join(new_repeat_condition_list)
            check_status = self.check_dependency_setting(new_dependency_dic)

            if check_status:
                self.current_dependency_priority_dic[view_name][item_name] = ','.join(new_repeat_condition_list)

            self.update_dependency_show_info(view_name=view_name, modify_item=item_name)

        self.dependency_priority_dic[self.current_block][self.current_version] = self.current_dependency_priority_dic

    def generate_tree_menu(self, pos):
        if not self.gui_enable_flag:
            return

        tree_item = self.tree.itemAt(pos)

        if not tree_item:
            return

        tree_branch = tree_item.text(0)
        flow, vendor, branch = None, None, None

        if tree_item:
            if tree_item.child(0) and tree_item.parent():
                return
            else:
                if re.match(r'%s\s*->\s*%s' % (self.current_block, self.current_version), tree_branch):
                    dependency_dic = self.current_dependency_priority_dic['flow_dependency']
                    view_name = 'flow_dependency'
                else:
                    flow = tree_item.parent().text(0)

                    if my_match := re.match(r'(\S+)\s*->\s*(\S+)', tree_branch):
                        vendor = my_match.group(1)
                        branch = my_match.group(2)

                    dependency_dic = self.current_dependency_priority_dic['task_dependency'][flow][vendor][branch]
                    view_name = 'task_dependency'

                menu = QMenu()

                copy_current_action = menu.addAction('Copy Current Dependency')
                copy_current_action.triggered.connect(functools.partial(self.copy_dependency, dependency_dic))

                paste_current_action = menu.addAction('Paste Clipboard Dependency')
                apply_default_dependency_action = menu.addAction('Apply Default Dependency')

                if (not self.dependency_clipboard) or (set(self.dependency_clipboard.keys()) != set(dependency_dic.keys())):
                    paste_current_action.setDisabled(True)

                if flow and vendor and branch:
                    paste_current_action.triggered.connect(functools.partial(self.paste_dependency, flow, vendor, branch))
                    apply_default_dependency_action.triggered.connect(functools.partial(self.apply_default_dependency, flow, vendor, branch))
                else:
                    paste_current_action.triggered.connect(functools.partial(self.paste_dependency))
                    apply_default_dependency_action.triggered.connect(functools.partial(self.apply_default_dependency))

                apply_all_dependency_action = menu.addAction('Apply Dependency To All')
                apply_all_dependency_action.triggered.connect(functools.partial(self.apply_all_dependency, dependency_dic, view_name))

                if view_name == 'task_dependency':
                    apply_current_version_dependency_action = menu.addAction('Apply Dependency To Current Version ')
                    apply_current_version_dependency_action.triggered.connect(functools.partial(self.apply_current_version_dependency, dependency_dic))

        menu.exec_(self.tree.mapToGlobal(pos))

    def generate_table_menu(self, table, flow, vendor, branch, view_name, pos):
        if not self.gui_enable_flag:
            return

        current_selected_row = table.currentIndex().row()
        current_selected_column = table.currentIndex().column()

        if current_selected_column != 0:
            return
        else:
            current_selected_item = table.item(current_selected_row, current_selected_column).whatsThis().strip()

            menu = QMenu()
            add_action = menu.addAction('Add Another Condition')
            add_action.triggered.connect(functools.partial(self.add_repeat_dependency, flow, vendor, branch, view_name, current_selected_item))

            delete_action = menu.addAction('Delete Current Condition')
            item_name, _ = self.get_item_name(current_selected_item)

            if item_name == current_selected_item:
                delete_action.setDisabled(True)

            delete_action.triggered.connect(functools.partial(self.delete_repeat_dependency, flow, vendor, branch, view_name, current_selected_item))

        menu.exec_(table.mapToGlobal(pos))

    def add_repeat_dependency(self, flow='', vendor='', branch='', view_name='', item=''):
        if not item:
            return

        item_name, item_num = self.get_item_name(item)

        if flow and vendor and branch:
            new_repeat_condition_list = self.current_dependency_priority_dic[view_name][flow][vendor][branch][item_name].split(',')
            new_repeat_condition_list.append('')

            self.current_dependency_priority_dic[view_name][flow][vendor][branch][item_name] = ','.join(new_repeat_condition_list)
            self.update_dependency_show_info(view_name=view_name, flow=flow, vendor=vendor, branch=branch, modify_item=item_name)
        else:
            new_repeat_condition_list = self.current_dependency_priority_dic[view_name][item_name].split(',')
            new_repeat_condition_list.append('')

            self.current_dependency_priority_dic[view_name][item_name] = ','.join(new_repeat_condition_list)
            self.update_dependency_show_info(view_name=view_name, modify_item=item_name)

        self.dependency_priority_dic[self.current_block][self.current_version] = self.current_dependency_priority_dic

    def delete_repeat_dependency(self, flow='', vendor='', branch='', view_name='', item=''):
        if not item:
            return

        item_name, item_num = self.get_item_name(item)
        new_repeat_condition_list = []

        if flow and vendor and branch:
            for condition in self.current_dependency_priority_dic[view_name][flow][vendor][branch][item_name].split(','):
                if condition != self.current_dependency_priority_dic[view_name][flow][vendor][branch][item_name].split(',')[item_num]:
                    new_repeat_condition_list.append(condition)

            self.current_dependency_priority_dic[view_name][flow][vendor][branch][item_name] = ','.join(new_repeat_condition_list)
            self.update_dependency_show_info(view_name=view_name, flow=flow, vendor=vendor, branch=branch, modify_item=item_name)
        else:
            for condition in self.current_dependency_priority_dic[view_name][item_name].split(','):
                if condition != self.current_dependency_priority_dic[view_name][item_name].split(',')[item_num]:
                    new_repeat_condition_list.append(condition)

            self.current_dependency_priority_dic[view_name][item_name] = ','.join(new_repeat_condition_list)
            self.update_dependency_show_info(view_name=view_name, modify_item=item_name)

        self.dependency_priority_dic[self.current_block][self.current_version] = self.current_dependency_priority_dic

    def copy_dependency(self, dependency_dic):
        self.dependency_clipboard = copy.deepcopy(dependency_dic)

    def paste_dependency(self, flow='', vendor='', branch=''):
        dependency_dic = copy.deepcopy(self.dependency_clipboard)

        if flow and vendor and branch:
            self.current_dependency_priority_dic['task_dependency'][flow][vendor][branch] = dependency_dic

            self.update_dependency_show_info(view_name='task_dependency', flow=flow, vendor=vendor, branch=branch)
        else:
            self.current_dependency_priority_dic['flow_dependency'] = dependency_dic

            self.update_dependency_show_info(view_name='flow_dependency')

        self.dependency_priority_dic[self.current_block][self.current_version] = self.current_dependency_priority_dic

        if self.mode == 'widget':
            self.save_button.setEnabled(True)
            self.update.emit(True, 'Dependency')

    def apply_all_dependency(self, dependency_dic=None, view_name=''):
        if (not view_name) or (not dependency_dic):
            return

        item_list = list(dependency_dic.keys())

        if view_name == 'flow_dependency':
            for block in self.dependency_priority_dic.keys():
                for version in self.dependency_priority_dic[block].keys():
                    if view_name not in self.dependency_priority_dic[block][version]:
                        continue

                    flow_list = self.dependency_priority_dic[block][version][view_name]

                    if set(flow_list) == set(item_list):
                        self.dependency_priority_dic[block][version][view_name] = dependency_dic

        elif view_name == 'task_dependency':
            for block in self.dependency_priority_dic.keys():
                for version in self.dependency_priority_dic[block].keys():
                    if view_name not in self.dependency_priority_dic[block][version]:
                        continue

                    for flow in self.dependency_priority_dic[block][version][view_name].keys():
                        for vendor in self.dependency_priority_dic[block][version][view_name][flow].keys():
                            for branch in self.dependency_priority_dic[block][version][view_name][flow][vendor].keys():
                                task_list = list(self.dependency_priority_dic[block][version][view_name][flow][vendor][branch].keys())

                                if set(task_list) == set(item_list):
                                    self.dependency_priority_dic[block][version][view_name][flow][vendor][branch] = dependency_dic

        if self.mode == 'widget':
            self.save_button.setEnabled(True)
            self.update.emit(True, 'Dependency')

    def apply_default_dependency(self, flow=None, vendor=None, branch=None):
        if flow and vendor and branch:
            if flow in self.default_dependency_dic['task_dependency'] and vendor in self.default_dependency_dic['task_dependency'][flow]:
                task_list = list(self.current_dependency_priority_dic['task_dependency'][flow][vendor][branch].keys())

                for task in task_list:
                    if task not in self.default_dependency_dic['task_dependency'][flow][vendor]:
                        continue
                    else:
                        dependency = self.default_dependency_dic['task_dependency'][flow][vendor][task]
                        clean_dependency = self.clean_dependency(item_list=task_list, item=task, dependency=dependency)
                        self.current_dependency_priority_dic['task_dependency'][flow][vendor][branch][task] = clean_dependency

                self.update_dependency_show_info(view_name='task_dependency', flow=flow, vendor=vendor, branch=branch)
        else:
            flow_list = list(self.current_dependency_priority_dic['flow_dependency'].keys())

            for flow in flow_list:
                if flow not in self.default_dependency_dic['flow_dependency']:
                    continue
                else:
                    dependency = self.default_dependency_dic['flow_dependency'][flow]
                    clean_dependency = self.clean_dependency(item_list=flow_list, item=flow, dependency=dependency)
                    self.current_dependency_priority_dic['flow_dependency'][flow] = clean_dependency

                self.update_dependency_show_info(view_name='flow_dependency')

        self.dependency_priority_dic[self.current_block][self.current_version] = self.current_dependency_priority_dic

        if self.mode == 'widget':
            self.save_button.setEnabled(True)
            self.update.emit(True, 'Dependency')

    def apply_current_version_dependency(self, dependency_dic={}):
        for flow in self.current_dependency_priority_dic['task_dependency'].keys():
            for vendor in self.current_dependency_priority_dic['task_dependency'][flow].keys():
                for branch in self.current_dependency_priority_dic['task_dependency'][flow][vendor].keys():
                    item_list = list(self.current_dependency_priority_dic['task_dependency'][flow][vendor][branch].keys())

                    if set(item_list) == set(dependency_dic.keys()):
                        self.current_dependency_priority_dic['task_dependency'][flow][vendor][branch] = dependency_dic

        self.dependency_priority_dic[self.current_block][self.current_version] = dependency_dic

        if self.mode == 'widget':
            self.save_button.setEnabled(True)
            self.update.emit(True, 'Dependency')

    def update_dependency_show_info(self, view_name='', flow='', vendor='', branch='', modify_item=None):
        if view_name == 'flow_dependency':
            flow_list = list(self.current_dependency_priority_dic['flow_dependency'].keys())

            if modify_item:
                self.modify_item_set.add((r'%s-%s-flow' % (self.current_block, self.current_version), modify_item))

            self.gen_table(view_name=view_name, item_list=flow_list)
            current_table = self.tables[view_name]
            self.gen_dependency_chart(chart_name='flow_dependency', dependency_dic=self.current_dependency_priority_dic[view_name])
        elif view_name == 'task_dependency':
            if (not flow) or (not vendor) or (not branch):
                return

            task_list = list(self.current_dependency_priority_dic['task_dependency'][flow][vendor][branch].keys())

            if modify_item:
                self.modify_item_set.add((r'%s-%s-task-%s-%s-%s' % (self.current_block, self.current_version, flow, vendor, branch), modify_item))

            self.gen_table(flow=flow, vendor=vendor, branch=branch, view_name=view_name, item_list=task_list)
            current_table = self.tables[flow][vendor][branch][view_name]
            self.gen_dependency_chart(chart_name=r'%s_%s_%s_task_dependency' % (flow, vendor, branch), dependency_dic=self.current_dependency_priority_dic[view_name][flow][vendor][branch])
        else:
            return

        self.current_table.hide()
        current_table.show()
        self.current_table = current_table

        if self.mode == 'widget':
            if self.modify_item_set:
                self.save_button.setEnabled(True)
                self.update.emit(True, 'Dependency')

    def dfs_check_loop(self, node, flow_chart_dic):
        check_status = True

        if node in self.vis:
            if node in self.trace:
                title = 'Warning'
                info = 'Dependencies contains a loop!'
                Dialog(title, info)
                return False

        self.vis.append(node)
        self.trace.append(node)

        for vs in flow_chart_dic[node]:
            check_status = self.dfs_check_loop(vs, flow_chart_dic)

            if not check_status:
                return check_status

        self.trace.pop()

        return check_status

    def save(self):
        self.before_tree_item = self.tree.currentItem()
        self.post_dependency_check()
        self.message.emit(self.update_flag, self.dependency_priority_dic)
        self.origin_dependency_priority_dic = copy.deepcopy(self.dependency_priority_dic)

        if self.mode == 'window':
            self.close()
        elif self.mode == 'widget':
            self.modify_item_set = set()
            self.init_ui()
            self.save_button.setEnabled(False)
            self.update.emit(False, 'Dependency')

    def closeEvent(self, event):
        if not hasattr(self, 'picture_dir'):
            return

        if os.path.exists(self.picture_dir):
            shutil.rmtree(self.picture_dir)

    @staticmethod
    def get_screen_resolutions():
        resolutions = set()
        for monitor in get_monitors():
            resolutions.add((monitor.width, monitor.height))
        return resolutions

    @staticmethod
    def clean_dependency(item_list=None, item=None, dependency=None):
        if not item_list or not item or not dependency:
            return ''

        independent_condition_list = dependency.split(',')
        valid_independent_condition_list = []

        if not independent_condition_list:
            return ''

        for independent_condition in independent_condition_list:
            parallel_condition_list = independent_condition.split('|')
            valid_parallel_condition_list = []

            if not parallel_condition_list:
                continue

            for parallel_condition in parallel_condition_list:
                and_condition_list = parallel_condition.split('&')
                valid_add_condition_list = []

                if not and_condition_list:
                    continue

                for and_condition in and_condition_list:
                    if and_condition.strip() not in item_list:
                        continue
                    else:
                        valid_add_condition_list.append(and_condition.strip())

                valid_parallel_condition = '&'.join(valid_add_condition_list)

                if valid_parallel_condition:
                    valid_parallel_condition_list.append(valid_parallel_condition)

            valid_independent_condition = '|'.join(valid_parallel_condition_list)

            if valid_independent_condition:
                valid_independent_condition_list.append(valid_independent_condition)

        valid_dependency = ','.join(valid_independent_condition_list)

        return valid_dependency

    def reset(self):
        self.dependency_priority_dic = copy.deepcopy(self.origin_dependency_priority_dic)
        self.current_dependency_priority_dic = self.dependency_priority_dic[self.current_block][self.current_version]
        self.modify_item_set = set()
        self.init_ui()
        self.update.emit(False, 'Dependency')

    def disable_gui(self):
        self.gui_enable_flag = False
        self.update_tree_table_frame()

    def enable_gui(self):
        self.gui_enable_flag = True
        self.update_tree_table_frame()


class WindowForToolGlobalEnvEditor(QMainWindow):
    message = pyqtSignal(str, dict, str)
    update = pyqtSignal(bool, str)

    def __init__(self, default_var=None, user_var=None, window='config'):
        super().__init__()

        self.default_var = default_var
        self.user_var = user_var
        self.title = 'IFP Env Editor'
        self.common_var_set = set()
        self.row_count = 0
        self.table_dic = {}
        self.mode = 'user'
        self.update_flag = 'env'
        self.window = window
        self.gui_enable_signal = True

        user = getpass.getuser()

        if user in default_yaml_administrators:
            self.advance = True
        else:
            self.advance = False

        self.view_env_mode = False

        if self.window == 'edit_task':
            self.advance = False

        self.init_parameter()

    def init_parameter(self):
        if self.mode == 'user':
            self.common_var_set = set(self.user_var.keys()).intersection(set(self.default_var.keys()))
            self.row_count = len(self.default_var.keys()) + len(self.user_var.keys()) - len(self.common_var_set)
        elif self.mode == 'advance':
            self.row_count = len(self.default_var.keys())

    def init_ui(self):
        self.setWindowTitle(self.title)

        self.top_widget = QWidget()
        self.top_layout = QVBoxLayout()
        self.top_widget.setLayout(self.top_layout)
        self.setCentralWidget(self.top_widget)

        self.main_widget = QWidget()
        self.main_layout = QVBoxLayout()
        self.main_widget.setLayout(self.main_layout)
        self.main_layout.setAlignment(Qt.AlignLeft)

        self.table = QTableWidget()
        self.main_label = QLabel()
        self.env_table = QTableWidget()
        self.env_label = QLabel()

        self.gen_main_tab()

        self.save_button = QPushButton('SAVE')
        self.save_button.clicked.connect(self.save)
        self.save_button.setEnabled(False)
        self.reset_button = QPushButton('RESET')
        self.reset_button.clicked.connect(self.reset)

        if self.advance:
            if self.mode == 'advance':
                self.advance_button = QPushButton('User')
            elif self.mode == 'user':
                self.advance_button = QPushButton('Default')

            self.advance_button.clicked.connect(self.advance_mode)

        self.view_env_button = QPushButton('Show System Variable')
        self.view_env_button.clicked.connect(self.view_env_parameter)

        self.button_widget = QWidget()
        self.button_layout = QHBoxLayout()

        if self.window == 'config':
            self.button_widget.setLayout(self.button_layout)
            self.button_layout.addWidget(self.view_env_button)

            self.button_layout.addStretch(1)
            self.button_layout.addWidget(self.save_button)
            self.button_layout.addWidget(self.reset_button)

            self.top_layout.addWidget(self.main_widget, 10)
            self.top_layout.addWidget(self.button_widget, 1)
        elif self.window == 'edit_task':
            self.button_widget.setLayout(self.button_layout)
            self.button_layout.addWidget(self.view_env_button)
            self.button_layout.addStretch(1)

            self.top_layout.addWidget(self.main_widget, 20)
            self.top_layout.addWidget(self.button_widget, 1)

        center_window(self)

        return self

    def gen_main_tab(self):
        font = QFont('Calibri', 10, QFont.Bold)
        self.main_label.clear()

        if self.window == 'config':
            if self.mode == 'user':
                self.main_label.setText('Admin or user defined variables with effect only for IFP and is editable.')
            elif self.mode == 'advance':
                self.main_label.setText('Admin defined variables with effect only for IFP and is editable.')
        elif self.window == 'edit_task':
            self.main_label.setText('IFP Variables read-only, you can modify them in <CONFIG -> Variable Tab>')

        self.main_label.setFont(font)
        self.main_layout.addWidget(self.main_label)

        self.table.clear()
        self.table.setMouseTracking(True)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setVisible(True)

        if self.window == 'config':
            self.table.setColumnCount(3)
            self.table.setHorizontalHeaderLabels(['Variable Name', 'Variable Value', 'Comment'])
            self.table.setColumnWidth(0, 150)
            self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
            self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        elif self.window == 'edit_task':
            self.table.setColumnCount(2)
            self.table.setHorizontalHeaderLabels(['Variable Name', 'Variable Value'])
            self.table.setColumnWidth(0, 150)
            self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)

        row = 0
        self.table.setRowCount(self.row_count)

        if self.mode == 'user':
            for key, value in self.default_var.items():
                if key in self.common_var_set:
                    continue

                key_item = QTableWidgetItem(key)
                key_item.setFlags(key_item.flags() & ~Qt.ItemIsEditable)
                key_item.setForeground(QBrush(QColor(125, 125, 125)))
                value_item = QTableWidgetItem(value)

                if self.window == 'config':
                    comment_item = QTableWidgetItem('Default variables set by admin,  can be edited for yourself but cannot be deleted')
                    comment_item.setFlags(key_item.flags() & ~Qt.ItemIsEditable)
                    comment_item.setForeground(QBrush(QColor(192, 192, 192)))

                    if key.strip() == 'BSUB_QUEUE':
                        key_item.setFlags(key_item.flags() & ~Qt.ItemIsEditable)
                        value_item.setFlags(value_item.flags() & ~Qt.ItemIsEditable)
                        key_item.setForeground(QBrush(QColor(125, 125, 125)))
                        value_item.setForeground(QBrush(QColor(125, 125, 125)))
                        comment_item = QTableWidgetItem('Modify BSUB_QUEUE in Setting -> Cluster Managerment')

                    self.table.setItem(row, 2, comment_item)
                elif self.window == 'edit_task':
                    value_item.setFlags(value_item.flags() & ~Qt.ItemIsEditable)

                self.table.setItem(row, 0, key_item)
                self.table.setItem(row, 1, value_item)
                row += 1

            for key, value in self.user_var.items():
                key_item = QTableWidgetItem(key)
                value_item = QTableWidgetItem(value)

                if key.strip() == 'BSUB_QUEUE':
                    key_item.setFlags(key_item.flags() & ~Qt.ItemIsEditable)
                    value_item.setFlags(value_item.flags() & ~Qt.ItemIsEditable)
                    key_item.setForeground(QBrush(QColor(125, 125, 125)))
                    value_item.setForeground(QBrush(QColor(125, 125, 125)))
                    comment_item = QTableWidgetItem('Modify BSUB_QUEUE in Setting -> Cluster Managerment')
                else:
                    comment_item = QTableWidgetItem('User customized variables, you can editable/added/deleted')

                comment_item.setFlags(key_item.flags() & ~Qt.ItemIsEditable)
                comment_item.setForeground(QBrush(QColor(192, 192, 192)))

                if key in self.common_var_set:
                    key_item.setFlags(key_item.flags() & ~Qt.ItemIsEditable)
                    key_item.setForeground(QBrush(QColor(125, 125, 125)))

                self.table.setItem(row, 0, key_item)
                self.table.setItem(row, 1, value_item)
                self.table.setItem(row, 2, comment_item)
                row += 1
        elif self.mode == 'advance':
            for key, value in self.default_var.items():
                key_item = QTableWidgetItem(key)
                value_item = QTableWidgetItem(value)
                comment_item = QTableWidgetItem('IFP Default Variables, editable/added/deleted for administrators')
                comment_item.setFlags(comment_item.flags() & ~Qt.ItemIsEditable)
                comment_item.setForeground(QBrush(QColor(192, 192, 192)))

                self.table.setItem(row, 0, key_item)
                self.table.setItem(row, 1, value_item)
                self.table.setItem(row, 2, comment_item)
                row += 1

        if self.window == 'config':
            self.table.setContextMenuPolicy(Qt.CustomContextMenu)
            self.table.customContextMenuRequested.connect(self.generate_table_menu)
            self.table.itemChanged.connect(self.on_item_changes)

        self.main_layout.addWidget(self.table)

        env_dic = common.get_env_dic()
        self.env_table.clear()
        self.env_table.setMouseTracking(True)
        self.env_table.setSortingEnabled(True)
        self.env_table.verticalHeader().setVisible(False)
        self.env_table.horizontalHeader().setVisible(True)

        if self.window == 'config':
            self.env_table.setColumnCount(3)
            self.env_table.setHorizontalHeaderLabels(['Variable Name', 'Variable Value', 'COMMENT'])
            self.env_table.setColumnWidth(0, 150)
            self.env_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
            self.env_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        else:
            self.env_table.setColumnCount(2)
            self.env_table.setHorizontalHeaderLabels(['Variable Name', 'Variable Value'])
            self.env_table.setColumnWidth(0, 150)
            self.env_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)

        row = 0
        self.env_table.setRowCount(len(env_dic.keys()))

        for key, value in env_dic.items():
            key_item = QTableWidgetItem(key)
            key_item.setFlags(key_item.flags() & ~Qt.ItemIsEditable)
            key_item.setForeground(QBrush(QColor(125, 125, 125)))

            value_item = QTableWidgetItem(value)
            value_item.setFlags(value_item.flags() & ~Qt.ItemIsEditable)
            value_item.setForeground(QBrush(QColor(125, 125, 125)))

            if self.window == 'config':
                comment_item = QTableWidgetItem('System variables which can be invoked only')
                comment_item.setFlags(comment_item.flags() & ~Qt.ItemIsEditable)
                comment_item.setForeground(QBrush(QColor(192, 192, 192)))
                self.env_table.setItem(row, 2, comment_item)

            self.env_table.setItem(row, 0, key_item)
            self.env_table.setItem(row, 1, value_item)
            row += 1

        if self.window == 'config':
            self.env_label.setText('System variables and is read only.')
        elif self.window == 'edit_task':
            self.env_label.setText('System variables read-only')

        self.env_label.setFont(font)

        self.main_layout.addWidget(self.env_label)
        self.main_layout.addWidget(self.env_table)

        if self.view_env_mode:
            self.env_label.show()
            self.env_table.show()
        else:
            self.env_label.hide()
            self.env_table.hide()

    def on_item_changes(self, item):
        if not item:
            return

        item.setForeground(QBrush(QColor(100, 149, 237)))
        item.setFont(QFont('Calibri', 10, 500))
        self.save_button.setEnabled(True)
        self.update.emit(True, self.update_flag)

    def read_table(self):
        rows = self.row_count
        self.table_dic = {}

        for i in range(rows):
            if not self.table.item(i, 0) or not self.table.item(i, 1):
                continue

            var_name = self.table.item(i, 0).text().strip()
            var_content = self.table.item(i, 1).text().strip()
            self.table_dic[var_name] = var_content

    def generate_table_menu(self, pos):
        if not self.gui_enable_signal:
            return

        current_selected_row = self.table.currentIndex().row()
        current_selected_column = self.table.currentIndex().column()

        if current_selected_column != 0:
            if current_selected_row == -1 and current_selected_column == -1:
                menu = QMenu()
                add_action = menu.addAction('Add Variable')
                add_action.triggered.connect(self.add_var)

                menu.exec_(self.table.mapToGlobal(pos))
            return
        else:
            if not self.table.item(current_selected_row, current_selected_column):
                return

            current_selected_item_row = self.table.item(current_selected_row, current_selected_column).row()
            current_selected_item = self.table.item(current_selected_row, current_selected_column).text()

            menu = QMenu()
            add_action = menu.addAction('Add Variable')
            add_action.triggered.connect(self.add_var)

            delete_action = menu.addAction('Delete Variable')

            if self.mode == 'user' and current_selected_item in self.default_var:
                delete_action.setDisabled(True)

            delete_action.triggered.connect(functools.partial(self.delete_var, current_selected_item_row, current_selected_item))

        menu.exec_(self.table.mapToGlobal(pos))

    def add_var(self):
        self.row_count += 1
        self.table.setRowCount(self.row_count)
        self.update.emit(True, self.update_flag)

    def delete_var(self, delete_row=None, item=None):
        if delete_row is None or not item:
            return

        self.table.removeRow(delete_row)
        self.row_count -= 1
        self.table.setRowCount(self.row_count)
        self.table.update()
        self.save_button.setEnabled(True)
        self.update.emit(True, self.update_flag)

    def save(self):
        self.read_table()
        self.update.emit(False, self.update_flag)
        self.message.emit(self.update_flag, self.table_dic, self.mode)

        if self.mode == 'user':
            self.user_var = {}

            for key, value in self.table_dic.items():
                if key in self.default_var and value == self.default_var[key]:
                    continue

                if key == '' or value == '':
                    continue

                self.user_var[key] = value
        elif self.mode == 'advance':
            self.default_var = {}

            for key, value in self.table_dic.items():
                if key == '' or value == '':
                    continue

                self.default_var[key] = value

        self.init_parameter()
        self.init_ui()

        self.save_button.setStyleSheet("")
        self.save_button.setEnabled(False)

    def reset(self):
        try:
            self.table.itemChanged.disconnect()
        except Exception:
            pass

        self.init_parameter()
        self.gen_main_tab()
        self.table.itemChanged.connect(self.on_item_changes)
        self.save_button.setStyleSheet("")
        self.update.emit(False, self.update_flag)

    def advance_mode(self):
        try:
            self.table.itemChanged.disconnect()
        except Exception:
            pass

        if self.mode == 'user':
            self.mode = 'advance'
            self.advance_button.setText('User')
        elif self.mode == 'advance':
            self.mode = 'user'
            self.advance_button.setText('Default')

        self.init_parameter()
        self.gen_main_tab()
        self.table.itemChanged.connect(self.on_item_changes)
        self.save_button.setStyleSheet("")

    def view_env_parameter(self):
        if self.view_env_mode:
            self.view_env_mode = False
            self.env_label.hide()
            self.env_table.hide()
            self.view_env_button.setText('Show System Variable')
        else:
            self.view_env_mode = True
            self.env_label.show()
            self.env_table.show()
            self.view_env_button.setText('Hide System Variable')

    def disable_gui(self):
        self.gui_enable_signal = False
        row_count = self.table.rowCount()
        column_count = self.table.columnCount()

        self.table.itemChanged.disconnect()

        for row in range(row_count):
            for column in range(column_count):
                item = self.table.item(row, column)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)

        self.table.itemChanged.connect(self.on_item_changes)

    def enable_gui(self):
        self.gui_enable_signal = True

        row_count = self.table.rowCount()
        column_count = self.table.columnCount()

        self.table.itemChanged.disconnect()

        for row in range(row_count):
            for column in range(column_count):
                item = self.table.item(row, column)
                item.setFlags(item.flags() | Qt.ItemIsEditable)

        self.table.itemChanged.connect(self.on_item_changes)


class WindowForAPI(QMainWindow):
    message = pyqtSignal(str, dict, str)
    update = pyqtSignal(bool, str)

    def __init__(self, api_yaml=None):
        super().__init__()

        self.api_dic = common.parse_user_api(api_yaml)

        self.title = 'API Setting'
        self.update_flag = 'API'
        self.user_api_yaml = os.path.join(common.get_user_ifp_config_path(), os.path.basename(api_yaml))
        self.table_column_list = ['Enable', 'Tab', 'Project', 'Group', 'Label', 'Comment', 'Command']

    def init_ui(self):
        self.setWindowTitle(self.title)

        self.top_widget = QWidget()
        self.top_layout = QVBoxLayout()
        self.top_widget.setLayout(self.top_layout)
        self.setCentralWidget(self.top_widget)

        self.main_widget = QWidget()
        self.main_layout = QVBoxLayout()
        self.main_widget.setLayout(self.main_layout)
        self.main_layout.setAlignment(Qt.AlignLeft)

        self.table = QTableWidget()
        self.main_label = QLabel()
        self.api_table = QTableWidget()
        self.api_label = QLabel()

        self.gen_main_tab()

        self.save_button = QPushButton('SAVE')
        self.save_button.clicked.connect(self.save)
        self.save_button.setEnabled(False)
        self.reset_button = QPushButton('RESET')
        self.reset_button.clicked.connect(self.reset)

        self.button_widget = QWidget()
        self.button_layout = QHBoxLayout()

        self.button_widget.setLayout(self.button_layout)

        self.button_layout.addStretch(1)
        self.button_layout.addWidget(self.save_button)
        self.button_layout.addWidget(self.reset_button)

        self.top_layout.addWidget(self.main_widget)
        self.top_layout.addWidget(self.button_widget)
        self.top_layout.setStretch(0, 10)
        self.top_layout.setStretch(1, 1)

        center_window(self)

        return self

    def gen_main_tab(self):
        self.table.clear()
        self.table.setMouseTracking(True)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setVisible(True)
        self.table.horizontalHeader().setVisible(True)

        self.table.setColumnCount(len(self.table_column_list))
        self.table.setHorizontalHeaderLabels(self.table_column_list)

        row = 0
        api_list = self.analysis_api(total_api_dic=self.api_dic)
        self.table.setRowCount(len(api_list))

        for api_dic in api_list:
            api_content = self.gen_api_content(api_dic)
            label_item = QTableWidgetItem(api_dic['LABEL'])
            project_item = QTableWidgetItem(api_dic['PROJECT'])
            group_item = QTableWidgetItem(api_dic['GROUP'])
            tab_item = QTableWidgetItem(api_dic['TAB'])
            label_item.setToolTip(api_content)
            comment_item = QTableWidgetItem(api_dic['COMMENT'])
            command_item = QTableWidgetItem(api_dic['COMMAND'])

            if api_dic['ENABLE']:
                status_item = QCheckBox()
                status_item.setCheckState(Qt.Checked)
            else:
                status_item = QCheckBox()
                status_item.setCheckState(Qt.Unchecked)

            status_item.setStyleSheet("margin-left:25%;")

            self.table.setCellWidget(row, 0, status_item)
            status_item.stateChanged.connect(lambda state, row=row: self.table_status_changed(state, row))
            column = 1

            for item in [tab_item, project_item, group_item, label_item, comment_item, command_item]:
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)

                if not api_dic['ENABLE']:
                    item.setForeground(QBrush(QColor('grey')))

                self.table.setItem(row, column, item)
                column += 1
            row += 1

        self.table.resizeColumnsToContents()
        self.main_layout.addWidget(self.table)

    @staticmethod
    def gen_api_content(api_dic=None):
        if not api_dic or not isinstance(api_dic, dict):
            return ''

        content = '<table>'

        for key, value in api_dic.items():
            content += '<tr><td><b>%s</b></td><td>%s</td></tr>' % (str(key), str(value))

        content += '</table>'

        return content

    def save(self):
        self.update_api_dic()
        self.message.emit(self.update_flag, self.api_dic, self.user_api_yaml)
        self.update.emit(False, self.update_flag)
        self.init_ui()

        self.save_button.setEnabled(False)

    def reset(self):
        self.gen_main_tab()
        self.save_button.setStyleSheet("")
        self.update.emit(False, self.update_flag)

    @staticmethod
    def analysis_api(total_api_dic=None):
        if not total_api_dic:
            return []

        api_list = []

        if 'TABLE_RIGHT_KEY_MENU' in total_api_dic['API']:
            for api_dic in total_api_dic['API']['TABLE_RIGHT_KEY_MENU']:
                if 'API-2' not in api_dic:
                    api_list.append(api_dic)
                else:
                    api_2_item_dic = copy.deepcopy(api_dic)
                    del api_2_item_dic['API-2']

                    for api_2_dic in api_dic['API-2']:
                        final_dic = copy.deepcopy(api_2_item_dic)
                        final_dic.update(api_2_dic)
                        api_list.append(final_dic)

        if 'PRE_API' in total_api_dic['API']:
            for api_dic in total_api_dic['API']['PRE_API']:
                api_list.append(api_dic)

        return api_list

    def update_api_dic(self):
        row_count = self.table.rowCount()
        api_status_dic = {}

        for i in range(row_count):
            if self.table.cellWidget(i, 0).checkState() == Qt.Checked:
                status = True
            else:
                status = False

            name_list = []

            for j in range(self.table.columnCount()):
                if j == 0:
                    continue

                name_list.append(self.table.item(i, j).text().strip())

            label = '_'.join(name_list)
            api_status_dic[label] = status

        if 'TABLE_RIGHT_KEY_MENU' in self.api_dic['API']:
            for i in range(len(self.api_dic['API']['TABLE_RIGHT_KEY_MENU'])):
                if 'API-2' not in self.api_dic['API']['TABLE_RIGHT_KEY_MENU'][i]:
                    name_list = []

                    for name in self.table_column_list:
                        name = name.upper()

                        if name == 'ENABLE':
                            continue

                        if self.api_dic['API']['TABLE_RIGHT_KEY_MENU'][i][name]:
                            name_list.append(str(self.api_dic['API']['TABLE_RIGHT_KEY_MENU'][i][name]).strip())
                        else:
                            name_list.append('')

                    label = '_'.join(name_list)

                    if label in api_status_dic:
                        self.api_dic['API']['TABLE_RIGHT_KEY_MENU'][i]['ENABLE'] = api_status_dic[label]
                else:
                    for j in range(len(self.api_dic['API']['TABLE_RIGHT_KEY_MENU'][i]['API-2'])):
                        name_list = []

                        for name in self.table_column_list:
                            name = name.upper()

                            if name == 'ENABLE':
                                continue

                            if name in self.api_dic['API']['TABLE_RIGHT_KEY_MENU'][i]['API-2'][j]:
                                if self.api_dic['API']['TABLE_RIGHT_KEY_MENU'][i]['API-2'][j][name]:
                                    name_list.append(str(self.api_dic['API']['TABLE_RIGHT_KEY_MENU'][i]['API-2'][j][name]).strip())
                                else:
                                    name_list.append('')
                            else:
                                if self.api_dic['API']['TABLE_RIGHT_KEY_MENU'][i][name]:
                                    name_list.append(str(self.api_dic['API']['TABLE_RIGHT_KEY_MENU'][i][name]).strip())
                                else:
                                    name_list.append('')

                        label = '_'.join(name_list)

                        if label in api_status_dic:
                            self.api_dic['API']['TABLE_RIGHT_KEY_MENU'][i]['API-2'][j]['ENABLE'] = api_status_dic[label]

        if 'PRE_API' in self.api_dic['API']:
            for i in range(len(self.api_dic['API']['PRE_API'])):
                name_list = []

                for name in self.table_column_list:
                    name = name.upper()

                    if name == 'ENABLE':
                        continue

                    if self.api_dic['API']['PRE_API'][i][name]:
                        name_list.append(str(self.api_dic['API']['PRE_API'][i][name]).strip())
                    else:
                        name_list.append('')

                label = '_'.join(name_list)

                if label in api_status_dic:
                    self.api_dic['API']['PRE_API'][i]['ENABLE'] = api_status_dic[label]

    def table_status_changed(self, state, item_row):
        if not self.save_button.isEnabled():
            self.save_button.setEnabled(True)

        if state == Qt.Checked:
            status = True
        else:
            status = False

        for column in range(1, self.table.columnCount()):
            table_item = self.table.item(item_row, column)

            if status:
                table_item.setForeground(QBrush(QColor('black')))
            else:
                table_item.setForeground(QBrush(QColor('grey')))

        self.update.emit(True, self.update_flag)

    def disable_gui(self):
        """
        Disable status_item in table
        """
        row_count = self.table.rowCount()

        for row in range(row_count):
            status_item = self.table.cellWidget(row, 0)
            status_item.setEnabled(False)

    def enable_gui(self):
        """
        Enable status_item in table
        """
        row_count = self.table.rowCount()

        for row in range(row_count):
            status_item = self.table.cellWidget(row, 0)
            status_item.setEnabled(True)


class DefaultConfig(QMainWindow):
    save_signal = pyqtSignal(str)

    def __init__(self, default_yaml):
        super().__init__()

        self.admin_flag = 0

        if os.popen('whoami').read().strip() in default_yaml_administrators.split():
            self.admin_flag = 1

        self.default_yaml = default_yaml
        [self.default_setting, self.combs, self.flows, self.vendors, self.tasks] = self.parsing_default_setting(self.default_yaml)
        self.blank_setting = parsing_blank_setting()
        self.top_widget = QWidget()
        self.top_layout = QVBoxLayout()
        self.top_widget.setLayout(self.top_layout)
        self.setCentralWidget(self.top_widget)

        self.setting = AutoVivification()

        self.label_path = QLabel('Config path :')
        self.label_path.setStyleSheet('font-weight : bold')
        self.edit_path = QLineEdit()
        self.edit_path.setText(self.default_yaml)
        self.edit_path.setEnabled(False)
        self.save_yaml_button = QPushButton('Save')
        self.save_yaml_button.clicked.connect(self.save_to_yaml)
        self.yaml_widget = QWidget()
        self.yaml_layout = QHBoxLayout()
        self.yaml_widget.setLayout(self.yaml_layout)

        header = ['Item', 'Value']
        self.label_env = QLabel('Var setting :')
        self.label_env.setStyleSheet('font-weight : bold')
        self.env_table = QTableView()
        self.env_model = QStandardItemModel(5, 2)
        self.env_table.setModel(self.env_model)
        self.env_table.setColumnWidth(0, 120)
        self.env_model.setHorizontalHeaderLabels(header)
        self.env_table.setStyleSheet('font-family : calibri; font-size : 15px')
        self.env_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.env_table.setShowGrid(True)

        self.env_table.setSelectionMode(QAbstractItemView.NoSelection)

        self.label_setup = QLabel('Flow setting :')
        self.label_setup.setStyleSheet('font-weight : bold')
        self.setup_table = QTableView()
        self.setup_model = QStandardItemModel(1, 2)
        self.setup_table.setModel(self.setup_model)
        self.setup_table.setColumnWidth(0, 120)

        self.setup_model.setHorizontalHeaderLabels(header)
        self.setup_table.setStyleSheet('font-family : calibri; font-size : 15px')
        self.setup_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.setup_table.setShowGrid(True)

        self.save_button = QPushButton('update setting')
        self.save_button.clicked.connect(self.save)
        self.remove_button = QPushButton('delete')
        self.remove_button.clicked.connect(self.delete)
        self.cancel_button = QPushButton('cancel')
        self.cancel_button.clicked.connect(self.closeEvent)

        self.button_widget = QWidget()
        self.button_layout = QHBoxLayout()
        self.button_widget.setLayout(self.button_layout)

        self.comb_widget = QWidget()
        self.comb_layout = QHBoxLayout()
        self.comb_widget.setLayout(self.comb_layout)
        self.label_comb = QLabel('All')
        self.comb_all = QComboBox()
        self.comb_all.addItems(self.combs)
        self.comb_all.activated.connect(self.update_table)

        self.items_widget = QWidget()
        self.items_layout = QHBoxLayout()
        self.items_widget.setLayout(self.items_layout)
        self.label_flow = QLabel('FLow')
        self.label_vendor = QLabel('Vendor')
        self.label_task = QLabel('Task')

        self.edit_flow = QLineEdit()
        self.edit_flow.setFixedWidth(150)
        self.edit_flow.setEnabled(True)
        self.edit_flow.setAlignment(Qt.AlignCenter)
        self.edit_flow.textChanged.connect(self.update_add_button)
        self.edit_vendor = QLineEdit()
        self.edit_vendor.setFixedWidth(150)
        self.edit_vendor.setEnabled(True)
        self.edit_vendor.setAlignment(Qt.AlignCenter)
        self.edit_vendor.textChanged.connect(self.update_add_button)
        self.edit_task = QLineEdit()
        self.edit_task.setFixedWidth(150)
        self.edit_task.setEnabled(True)
        self.edit_task.setAlignment(Qt.AlignCenter)
        self.edit_task.textChanged.connect(self.update_add_button)

        self.current_flow = ''
        self.current_vendor = ''
        self.current_task = ''

        self.update_flag = 0

        if self.admin_flag == 0:
            self.env_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
            self.setup_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
            self.edit_flow.setEnabled(False)
            self.edit_vendor.setEnabled(False)
            self.edit_task.setEnabled(False)
            self.save_yaml_button.hide()
            self.save_button.hide()
            self.remove_button.hide()
        else:
            self.env_table.setEditTriggers(QAbstractItemView.AllEditTriggers)
            self.setup_table.setEditTriggers(QAbstractItemView.AllEditTriggers)
            self.edit_flow.setEnabled(True)
            self.edit_vendor.setEnabled(True)
            self.edit_task.setEnabled(True)
            self.save_yaml_button.show()
            self.save_button.show()
            self.remove_button.show()

        self.init_ui()

    def init_ui(self):
        row = 0

        for key in self.default_setting['VAR'].keys():
            item = QStandardItem('%s' % key)
            item.setTextAlignment(Qt.AlignLeft)
            item.setTextAlignment(Qt.AlignVCenter)
            self.env_model.setItem(row, 0, item)

            item = QStandardItem('%s' % self.default_setting['VAR'][key])
            item.setTextAlignment(Qt.AlignLeft)
            item.setTextAlignment(Qt.AlignVCenter)
            self.env_model.setItem(row, 1, item)
            row += 1

        self.draw_table({'TASK': {}})

        self.yaml_layout.addWidget(self.edit_path)
        self.yaml_layout.addWidget(self.save_yaml_button)
        self.items_layout.addWidget(self.label_flow)
        self.items_layout.addWidget(self.edit_flow)
        self.items_layout.addStretch(1)
        self.items_layout.addWidget(self.label_vendor)
        self.items_layout.addWidget(self.edit_vendor)
        self.items_layout.addStretch(1)
        self.items_layout.addWidget(self.label_task)
        self.items_layout.addWidget(self.edit_task)
        self.items_layout.setStretch(0, 1)
        self.items_layout.setStretch(1, 2)
        self.items_layout.setStretch(2, 3)
        self.items_layout.setStretch(3, 1)
        self.items_layout.setStretch(4, 2)
        self.items_layout.setStretch(5, 3)
        self.items_layout.setStretch(6, 1)
        self.items_layout.setStretch(7, 2)

        self.button_layout.addStretch(10)
        self.button_layout.addWidget(self.save_button)
        self.button_layout.addWidget(self.remove_button)
        self.button_layout.addWidget(self.cancel_button)

        self.comb_layout.addWidget(self.label_comb)
        self.comb_layout.addWidget(self.comb_all)
        self.comb_layout.addStretch(1)
        self.comb_layout.setStretch(0, 1)
        self.comb_layout.setStretch(1, 2)
        self.comb_layout.setStretch(2, 15)

        self.top_layout.addWidget(self.label_path)
        self.top_layout.addWidget(self.yaml_widget)
        self.top_layout.addStretch(1)
        self.top_layout.addWidget(self.label_env)
        self.top_layout.addWidget(self.env_table)
        self.top_layout.addStretch(1)
        self.top_layout.addWidget(self.label_setup)
        self.top_layout.addWidget(self.comb_widget)
        self.top_layout.addWidget(self.items_widget)
        self.top_layout.addWidget(self.setup_table)
        self.top_layout.addWidget(self.button_widget)
        self.top_layout.setStretch(3, 1)
        self.top_layout.setStretch(4, 4)
        self.top_layout.setStretch(6, 1)
        self.top_layout.setStretch(7, 1)
        self.top_layout.setStretch(8, 1)
        self.top_layout.setStretch(9, 8)
        self.resize(800, 600)
        self.setWindowTitle('Default Config')
        center(self)

        if not len(self.combs) == 0:
            self.update_table(0)

    def closeEvent(self, event):
        if self.update_flag == 1:
            reply = QMessageBox.question(
                self, "Message",
                "Are you sure to quit? Any unsaved setting will be lost.",
                QMessageBox.Save | QMessageBox.Close | QMessageBox.Cancel,
                QMessageBox.Save)

            if reply == QMessageBox.Save:
                self.save_to_yaml()
            elif reply == QMessageBox.Close:
                if type(event) is bool:
                    self.destroy()
                else:
                    event.accept()
            elif reply == QMessageBox.Cancel:
                if type(event) is bool:
                    return
                else:
                    event.ignore()
        else:
            self.destroy()

    def update_table(self, index):
        self.current_flow = self.comb_all.itemText(index).split(':')[0]
        self.current_vendor = self.comb_all.itemText(index).split(':')[1]
        self.current_task = self.comb_all.itemText(index).split(':')[2]

        self.edit_flow.setText(self.current_flow)
        self.edit_vendor.setText(self.current_vendor)
        self.edit_task.setText(self.current_task)

        if self.current_flow in self.default_setting['TASK'].keys():
            if self.current_vendor in self.default_setting['TASK'][self.current_flow].keys():
                if self.current_task in self.default_setting['TASK'][self.current_flow][self.current_vendor].keys():
                    self.draw_table(self.default_setting['TASK'][self.current_flow][self.current_vendor][self.current_task])

    def update_add_button(self):
        flow = self.edit_flow.text()
        vendor = self.edit_vendor.text()
        task = self.edit_task.text()

        if flow in self.default_setting['TASK'].keys():
            if vendor in self.default_setting['TASK'][self.current_flow].keys():
                if task in self.default_setting['TASK'][self.current_flow][self.current_vendor].keys():
                    self.save_button.setText('Update setting for %s/%s/%s' % (flow, vendor, task))
                    self.save_button.setEnabled(True)
                    self.remove_button.setEnabled(True)
                    return

        if not flow == '-' and not vendor == '-' and not task == '-':
            self.save_button.setText('Create setting for %s/%s/%s' % (flow, vendor, task))
            self.save_button.setEnabled(True)
            self.remove_button.setEnabled(False)

    def draw_table(self, setting):
        row = 0
        self.setup_model.setRowCount(0)

        for category in self.blank_setting.keys():
            item = QStandardItem('* %s' % category)
            item.setTextAlignment(Qt.AlignLeft)
            item.setTextAlignment(Qt.AlignVCenter)
            item.setEditable(False)
            f = QFont('Calibri', 10)
            f.setBold(True)
            item.setFont(f)
            item.setBackground(QBrush(QColor(245, 255, 250)))
            item.setForeground(QBrush(QColor(0, 0, 0)))
            self.setup_model.setItem(row, 0, item)
            self.setup_table.setSpan(row, 0, 1, 2)
            row += 1

            for key in self.blank_setting[category].keys():
                item = QStandardItem(key)
                item.setTextAlignment(Qt.AlignLeft)
                item.setTextAlignment(Qt.AlignVCenter)
                item.setEditable(False)
                self.setup_model.setItem(row, 0, item)

                value = ''

                if category in setting.keys():
                    if key in setting[category].keys():
                        value = setting[category][key]
                        item = QStandardItem(value)
                        item.setBackground(QBrush(QColor(255, 255, 255)))

                if value == '':
                    item = QStandardItem(value)
                    item.setBackground(QBrush(QColor(255, 255, 255)))

                item.setTextAlignment(Qt.AlignLeft)
                item.setTextAlignment(Qt.AlignVCenter)
                self.setup_model.setItem(row, 1, item)
                row += 1

    def parsing_default_setting(self, yaml_file):
        task_dic = {'VAR': {}, 'TASK': {}}
        combs = []
        flows = []
        vendors = []
        tasks = []

        if os.path.exists(yaml_file):
            default_dic = yaml.safe_load(open(yaml_file, 'r'))

            if default_dic:
                if 'VAR' in default_dic:
                    task_dic['VAR'] = copy.deepcopy(default_dic['VAR'])

                if 'TASK' in default_dic:
                    for key in default_dic['TASK'].keys():
                        combs.append(key)
                        flow = key.split(':')[0]
                        vendor = key.split(':')[1]
                        task = key.split(':')[2]
                        task_dic['TASK'].setdefault(flow, {})
                        task_dic['TASK'][flow].setdefault(vendor, {})
                        task_dic['TASK'][flow][vendor].setdefault(task, {})

                        if flow not in flows:
                            flows.append(flow)

                        if vendor not in vendors:
                            vendors.append(vendor)

                        if task not in tasks:
                            tasks.append(task)

                        for category in default_dic['TASK'][key].keys():
                            task_dic['TASK'][flow][vendor][task].setdefault(category, {})
                            for item in default_dic['TASK'][key][category].keys():
                                task_dic['TASK'][flow][vendor][task][category][item] = default_dic['TASK'][key][category][item]

        return [task_dic, combs, flows, vendors, tasks]

    def save(self):
        flow = self.edit_flow.text()
        vendor = self.edit_vendor.text()
        task = self.edit_task.text()
        setting = {}
        category = ''

        reply = QMessageBox.question(self, "Warning", "Are you sure to update default setting for %s/%s/%s" % (flow, vendor, task), QMessageBox.Yes | QMessageBox.No)

        if reply == QMessageBox.No:
            return

        for i in range(self.setup_model.rowCount()):
            item = self.setup_model.index(i, 0).data()
            value = self.setup_model.index(i, 1).data()

            if re.search(r'\*\s+(.*)', item):
                if not category == '' and setting[category] == {}:
                    del setting[category]

                category = re.search(r'\*\s+(.*)', item).group(1)
                setting.setdefault(category, {})
            else:
                if value == '':
                    continue

                setting[category].setdefault(item, value)

        if not category == '' and setting[category] == {}:
            del setting[category]

        if flow not in self.default_setting['TASK'].keys():
            self.default_setting['TASK'].setdefault(flow, {})

        if vendor not in self.default_setting['TASK'][flow].keys():
            self.default_setting['TASK'][flow].setdefault(vendor, {})

        self.default_setting['TASK'][flow][vendor][task] = copy.deepcopy(setting)
        self.update_flag = 1

        if '%s:%s:%s' % (flow, vendor, task) not in [self.comb_all.itemText(i) for i in range(self.comb_all.count())]:
            self.comb_all.addItem('%s:%s:%s' % (flow, vendor, task))
            self.comb_all.setCurrentIndex(self.comb_all.count() - 1)
            self.update_table(self.comb_all.count() - 1)
            self.remove_button.setEnabled(True)
        else:
            self.comb_all.setCurrentIndex([self.comb_all.itemText(i) for i in range(self.comb_all.count())].index('%s:%s:%s' % (flow, vendor, task)))
            self.update_table([self.comb_all.itemText(i) for i in range(self.comb_all.count())].index('%s:%s:%s' % (flow, vendor, task)))

    def save_to_yaml(self):
        (yaml_file, file_type) = QFileDialog.getSaveFileName(self, 'Save Default Config', self.edit_path.text(), 'Default Config Files (*)')

        if yaml_file:
            final_setting = {'VAR': {}}

            for i in range(self.env_model.rowCount()):
                item = self.env_model.index(i, 0).data()
                value = self.env_model.index(i, 1).data()

                if item:
                    if not item.strip() == '':
                        final_setting['VAR'].setdefault(item, value)

            final_setting.setdefault('TASK', {})

            for flow in self.default_setting['TASK'].keys():
                for vendor in self.default_setting['TASK'][flow].keys():
                    for task in self.default_setting['TASK'][flow][vendor].keys():
                        final_setting['TASK']['%s:%s:%s' % (flow, vendor, task)] = copy.deepcopy(self.default_setting['TASK'][flow][vendor][task])

            try:
                with open(yaml_file, 'w', encoding='utf-8') as f:
                    yaml.dump(dict(final_setting), f, indent=4, sort_keys=False)
            except Exception:
                QMessageBox.warning(self, "Warning", "Cant save setting to %s" % yaml_file, QMessageBox.Ok)
            else:
                QMessageBox.warning(self, "Done", "Successfully save setting to %s" % yaml_file, QMessageBox.Ok)

            self.save_signal.emit('update')

            self.edit_path.setText(yaml_file)
            self.update_flag = 0

    def delete(self):
        flow = self.edit_flow.text()
        vendor = self.edit_vendor.text()
        task = self.edit_task.text()
        reply = QMessageBox.question(self, "Warning", "Are you sure to delete default setting for %s/%s/%s" % (flow, vendor, task), QMessageBox.Yes | QMessageBox.No)

        if reply == QMessageBox.Yes:
            del self.default_setting['TASK'][flow][vendor][task]
            self.update_flag = 1
            self.comb_all.removeItem([self.comb_all.itemText(i) for i in range(self.comb_all.count())].index('%s:%s:%s' % (flow, vendor, task)))

            if self.comb_all.count() == 0:
                self.comb_all.setCurrentText('-')
                self.draw_table({'TASK': {}})
                self.edit_flow.setText('-')
                self.edit_vendor.setText('-')
                self.edit_task.setText('-')
                self.save_button.setText('-')
                self.save_button.setEnabled(False)
                self.remove_button.setEnabled(False)
            else:
                self.comb_all.setCurrentIndex(0)
                self.update_table(0)
        else:
            pass


class QComboBox2(QComboBox):
    def wheelEvent(self, QWheelEvent):
        pass


class DraggableTableView(QTableView):
    exchange_flag = pyqtSignal(list)

    def __init__(self, *args, **kwargs):
        super(DraggableTableView, self).__init__(*args, **kwargs)
        self.resize(400, 450)
        self.drag_row = -1
        self.drop_row = None
        self.drag_widget = None
        self.drag_flag = False
        self.drag_widget = QWidget(self)
        self.drag_layout = QHBoxLayout()
        self.drag_widget.setLayout(self.drag_layout)
        p = self.drag_widget.palette()
        p.setColor(QPalette.Background, QColor(70, 130, 180))
        self.drag_widget.setPalette(p)
        self.drag_widget.setAutoFillBackground(True)

        self.label = QLabel()
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setFont(QFont('Calibri', 12, 500))
        self.label.setStyleSheet("color:white")
        self.drag_layout.addWidget(self.label)
        self.drag_widget.resize(100, 40)
        self.drag_widget.hide()

    def mousePressEvent(self, event) -> None:
        row, col = self.indexAt(event.pos()).row(), self.indexAt(event.pos()).column()
        task = self.model().index(row, 5).data()

        if col == 5 and event.buttons() == Qt.MidButton:
            self.drag_row = row
            self.label.setText(task)
            self.drag_widget.show()
            self.drag_flag = True
        super(DraggableTableView, self).mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        row, col = self.indexAt(event.pos()).row(), self.indexAt(event.pos()).column()
        if col == 5 and self.drag_flag:
            self.drag_widget.move(event.pos())
            self.set_row_bg_color(row, QColor(254, 163, 86))
            self.set_row_bg_color(row + 1, QColor(255, 255, 255))
            self.set_row_bg_color(row - 1, QColor(255, 255, 255))
        super(DraggableTableView, self).mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        row, col = self.indexAt(event.pos()).row(), self.indexAt(event.pos()).column()
        if col == 5 and self.drag_flag:
            self.set_row_bg_color(row, QColor(255, 255, 255))
            self.drop_row = row
            raw_block = self.model().index(self.drag_row, 0).data()
            raw_version = self.model().index(self.drag_row, 1).data()
            raw_flow = self.model().index(self.drag_row, 2).data()
            raw_vendor = self.model().index(self.drag_row, 3).data()
            raw_branch = self.model().index(self.drag_row, 4).data()
            raw_task = self.model().index(self.drag_row, 5).data()

            new_block = self.model().index(self.drop_row, 0).data()
            new_version = self.model().index(self.drop_row, 1).data()
            new_flow = self.model().index(self.drop_row, 2).data()
            new_vendor = self.model().index(self.drop_row, 3).data()
            new_branch = self.model().index(self.drop_row, 4).data()
            new_task = self.model().index(self.drop_row, 5).data()

            if raw_block == new_block and raw_version == new_version and raw_flow == new_flow and raw_vendor == new_vendor and raw_branch == new_branch and not raw_task == new_task:
                self.exchange_flag.emit([raw_block, raw_version, raw_flow, raw_vendor, raw_branch, raw_task, new_task])

        self.drag_widget.hide()
        self.drag_flag = False
        super(DraggableTableView, self).mouseReleaseEvent(event)

    def set_row_bg_color(self, row, color):
        if row < 0:
            return

        item = self.model().itemFromIndex(self.model().index(row, 5))

        if not item:
            return

        item.setBackground(QBrush(color))


class QLineEdit2(QLineEdit):
    def __init__(self, parent=None, values=None):
        super().__init__(parent)
        self.values = values
        font = QFont('Calibri', 10)
        self.setFont(font)
        self.setStyleSheet("border: none")
        self.completer = QCompleter(values)
        self.completer.setFilterMode(Qt.MatchContains)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.setCompleter(self.completer)
        self.setToolTip('Default flows : \n' + '\n'.join(['    %s' % i for i in self.values]))
        self.textChanged.connect(self.update_tool_tip)

    def update_tool_tip(self, text):

        if len(self.values) == 0 or not text == '':
            self.setToolTip('')
        else:
            self.setToolTip('Default flows : \n' + '\n'.join(['    %s' % i for i in self.values]))


class AlignDelegate(QStyledItemDelegate):
    def initStyleOption(self, option, index):
        super(AlignDelegate, self).initStyleOption(option, index)
        option.displayAlignment = Qt.AlignCenter
