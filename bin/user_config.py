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

from PyQt5 import QtGui
from PyQt5.QtWidgets import QWidget, QMainWindow, QAction, QPushButton, QLabel, QHeaderView, QVBoxLayout, QHBoxLayout, QLineEdit, QTableView, QAbstractItemView, QMenu, QToolTip, QDesktopWidget, QMessageBox, QComboBox, QFileDialog, QApplication, QGridLayout
from PyQt5.QtGui import QBrush, QFont, QColor, QStandardItem, QStandardItemModel, QCursor, QPalette
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QThread

os.environ['PYTHONUNBUFFERED'] = '1'

sys.path.append(str(os.environ['IFP_INSTALL_PATH']) + '/config')
from config import default_yaml_administrators


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
    blank_setting = {'BUILD': {'PATH': {'example': '$DEFAULT_PATH'},
                               'COMMAND': {'example': './gen_block_run_dir.pl -c ${BLOCK}.block_flow.configure'},
                               'RUN_METHOD': {'example': run_method_example}
                               },
                     'RUN': {'PATH': {'example': '$DEFAULT_PATH'},
                             'COMMAND': {'example': 'make presta'},
                             'RUN_METHOD': {'example': run_method_example}
                             },
                     'CHECK': {'PATH': {'example': '$DEFAULT_PATH/syn_dc'},
                               'COMMAND': {'example': '${IFP_INSTALL_PATH}/function/check/syn/synopsys/syn_synopsys.syn_dc.py -b ${BLOCK}'},
                               'RUN_METHOD': {'example': run_method_example},
                               'VIEWER': {'example': '${IFP_INSTALL_PATH}/function/check/tools/view_checklist_report.py -i'},
                               'REPORT_FILE': {'example': 'file_check/file_check.rpt'}
                               },
                     'SUMMARY': {'PATH': {'example': '${DEFAULT_PATH}/syn_dc'},
                                 'COMMAND': {'example': '${IFP_INSTALL_PATH}/function/summary/collect_syn_qor.py'},
                                 'RUN_METHOD': {'example': run_method_example},
                                 'VIEWER': {'example': '/bin/soffice'},
                                 'REPORT_FILE': {'example': 'fv_qor.xlsx'}
                                 },
                     'POST_RUN': {'PATH': {'example': '${DEFAULT_PATH}/dc'},
                                  'COMMAND': {'example': 'make post_run'},
                                  'RUN_METHOD': {'example': run_method_example}
                                  },
                     'RELEASE': {'PATH': {'example': '${DEFAULT_PATH}/dc'},
                                 'COMMAND': {'example': 'make release'},
                                 'RUN_METHOD': {'example': run_method_example}
                                 },
                     }

    return blank_setting


class UserConfig(QMainWindow):
    save_flag = pyqtSignal(object)

    def __init__(self, config_file, default_yaml):
        super().__init__()
        self.config_file = config_file
        self.default_yaml = default_yaml
        self.default_var = AutoVivification()
        self.default_setting = {}
        self.update_default_setting()
        self.top_widget = QWidget()
        self.top_layout = QVBoxLayout()
        self.top_widget.setLayout(self.top_layout)
        self.setCentralWidget(self.top_widget)

        self.setup_table = DraggableTableView()
        # self.setup_table = QTableView()
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

        self.project_var_widget = QWidget()
        self.project_var_layout = QHBoxLayout()
        self.project_var_widget.setLayout(self.project_var_layout)
        self.project_label = QLabel('Project     ')
        self.project_edit = QLineEdit()
        self.project_edit.setFixedWidth(250)
        self.var_label = QLabel('Var     ')
        self.var_edit = QLineEdit()
        self.var_edit.setPlaceholderText('DEFAULT_PATH = ${CWD}/${BLOCK}/${BLOCK}_${VERSION}_${BRANCH};')

        self.user_input = AutoVivification()
        self.detailed_setting = AutoVivification()
        self.blank_setting = parsing_blank_setting()
        self.state = AutoVivification()
        self.version_state = AutoVivification()
        self.priority = AutoVivification()
        self.run_type = AutoVivification()
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

        self.cwd = os.getcwd()
        center(self)

    def init_ui(self):
        self.config_path_layout.addWidget(self.config_path_label)
        self.config_path_layout.addWidget(self.config_path_edit)

        self.project_var_layout.addWidget(self.project_label)
        self.project_var_layout.addWidget(self.project_edit)
        self.project_var_layout.addStretch(1)
        self.project_var_layout.addWidget(self.var_label)
        self.project_var_layout.addWidget(self.var_edit)

        self.project_var_layout.setStretch(0, 1)
        self.project_var_layout.setStretch(1, 5)
        self.project_var_layout.setStretch(2, 1)
        self.project_var_layout.setStretch(3, 1)
        self.project_var_layout.setStretch(4, 20)

        header = ['Block', 'Version', '', 'Flow', 'Vendor', 'Branch', '', 'Task']

        self.setup_model.setHorizontalHeaderLabels(header)
        self.setup_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.setup_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.setup_table.setColumnWidth(2, 1)
        self.setup_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.setup_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.setup_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.setup_table.setColumnWidth(6, 1)
        self.setup_table.horizontalHeader().setSectionResizeMode(7, QHeaderView.Stretch)

        self.setup_table.setStyleSheet('font-family : calibri; font-size : 15px')
        self.setup_table.setShowGrid(True)
        self.setup_table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        self.setup_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.setup_table.customContextMenuRequested.connect(self.generate_menu)

        self.top_layout.addWidget(self.config_path_widget)
        self.top_layout.addWidget(self.project_var_widget)
        self.top_layout.addWidget(self.setup_table)

        self.thread = QThread()
        self.worker = Worker(self)
        self.worker.moveToThread(self.thread)
        self.worker.message.connect(self.update_state)
        self.thread.started.connect(self.worker.run)
        self.thread.start()
        return self.top_widget

    def update_state(self, state):
        self.state = state

        for i in range(self.setup_model.rowCount()):

            block = self.setup_model.index(i, 0).data()
            version = self.setup_model.index(i, 1).data()
            flow = self.setup_model.index(i, 3).data()
            vendor = self.setup_model.index(i, 4).data()
            branch = self.setup_model.index(i, 5).data()
            task = self.setup_model.index(i, 7).data()

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

            self.setup_model.setItem(i, 7, item)

        self.setup_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setup_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.setup_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.setup_table.setColumnWidth(2, 2)
        self.setup_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.setup_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.setup_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.setup_table.setColumnWidth(6, 1)
        self.setup_table.horizontalHeader().setSectionResizeMode(7, QHeaderView.Stretch)

    def parsing_default_setting(self, yaml_file):
        task_dic = AutoVivification()

        if os.path.exists(yaml_file):
            default_dic = yaml.safe_load(open(yaml_file, 'r'))

            if default_dic:
                if 'VAR' in default_dic:
                    self.default_var = default_dic['VAR']

                if 'TASK' in default_dic:
                    for key in default_dic['TASK'].keys():
                        flow = key.split(':')[0]
                        vendor = key.split(':')[1]
                        task = key.split(':')[2]

                        if default_dic['TASK'][key]:
                            for category in default_dic['TASK'][key].keys():
                                if default_dic['TASK'][key][category]:
                                    for item in default_dic['TASK'][key][category].keys():
                                        task_dic[flow][vendor][task][category][item] = default_dic['TASK'][key][category][item]

        return task_dic

    def update_default_setting(self):
        self.default_setting = self.parsing_default_setting(self.default_yaml)

    """
    1. Draw table by following dict
       a. self.user_input (GUI setting) or self.raw_setting (load ifp.cfg.yaml)
       b. self.priority[block][block_version][flow]
       c. self.run_type[block][block_version][flow][vendor][task_branch]
    2. Parsing self.detailed_setting[block][block_version][flow][vendor][task_branch][task] when load ifp.cfg.yaml
    """

    def draw_table(self, setting, stage=''):
        self.setup_model.setRowCount(0)
        self.span_info = AutoVivification()
        self.table_info = AutoVivification()
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
                if version is not None:
                    match = re.match(r'(\S+)\(RUN_ORDER=(.*)\)', version)

                    if match:
                        block_version = match.group(1)
                        run_order = match.group(2)
                        priority = 1

                        for i in run_order.split(','):
                            for j in i.split('|'):
                                self.priority[block][block_version][j.strip()] = priority

                            priority += 1
                    else:
                        block_version = version
                else:
                    block_version = version

                version_start_line = row

                run_order_set_flag = False
                ordered_flow = []
                order_rows = AutoVivification()
                final_priority = {}

                if self.priority[block][block_version] == {}:
                    ordered_flow = setting['BLOCK'][block][version].keys()
                    for i, flow in enumerate(ordered_flow):
                        self.priority[block][block_version][flow] = i + 1
                    final_priority[1] = list(ordered_flow)
                else:

                    if not sorted(list(self.priority[block][block_version].keys())) == sorted(list(setting['BLOCK'][block][version].keys())):
                        ordered_flow = setting['BLOCK'][block][version].keys()
                        final_priority[1] = list(ordered_flow)
                    else:
                        run_order_set_flag = True

                        for flow in self.priority[block][block_version].keys():
                            if not self.priority[block][block_version][flow] in final_priority.keys():
                                final_priority[self.priority[block][block_version][flow]] = [flow]
                            else:
                                final_priority[self.priority[block][block_version][flow]].append(flow)

                        for num in sorted(final_priority.keys()):
                            ordered_flow.extend(final_priority[num])

                for flow in ordered_flow:

                    if not self.priority[block][block_version][flow] in order_rows.keys():
                        order_rows[self.priority[block][block_version][flow]]['start'] = row

                    flow_start_line = row

                    for vendor in setting['BLOCK'][block][version][flow].keys():
                        vendor_start_line = row

                        for branch in setting['BLOCK'][block][version][flow][vendor].keys():
                            branch_start_line = row
                            run_type_rows = AutoVivification()
                            run_type_rows['start'] = row

                            if branch is not None:
                                branch = re.sub(r'\'', '', branch)
                                match = re.match(r'(\S+)\(RUN_TYPE=(\S+)\)', branch)

                                if match:
                                    task_branch = match.group(1)

                                    if match.group(2) in ['serial', 'parallel']:
                                        self.run_type[block][block_version][flow][vendor][task_branch] = match.group(2)
                                    else:
                                        self.run_type[block][block_version][flow][vendor][task_branch] = 'serial'
                                else:
                                    task_branch = branch
                            else:
                                task_branch = branch

                            for task in setting['BLOCK'][block][version][flow][vendor][branch].keys():
                                self.setup_model.setItem(row, 0, QStandardItem(block))

                                version_item = QStandardItem(block_version)

                                if not run_order_set_flag:
                                    version_item.setBackground(QBrush(QColor(255, 0, 0)))
                                self.setup_model.setItem(row, 1, version_item)

                                order_item = QStandardItem('')

                                if len(final_priority[self.priority[block][block_version][flow]]) > 1:
                                    if self.priority[block][block_version][flow] % 2 == 0:
                                        order_item.setBackground(QBrush(QColor(135, 206, 250)))
                                    else:
                                        order_item.setBackground(QBrush(QColor(70, 130, 180)))

                                self.setup_model.setItem(row, 2, order_item)
                                self.setup_model.setItem(row, 3, QStandardItem(flow))
                                self.setup_model.setItem(row, 4, QStandardItem(vendor))
                                self.setup_model.setItem(row, 5, QStandardItem(task_branch))

                                run_type_item = QStandardItem('')

                                if self.run_type[block][block_version][flow][vendor][task_branch] == 'parallel' and len(list(setting['BLOCK'][block][version][flow][vendor][branch].keys())) > 1:
                                    run_type_item.setBackground(QBrush(QColor(70, 130, 180)))

                                self.setup_model.setItem(row, 6, run_type_item)
                                self.setup_model.setItem(row, 7, QStandardItem(task))

                                self.table_info[row] = [block, block_version, flow, vendor, task_branch, task]
                                row += 1

                                if stage == 'load':
                                    if setting['BLOCK'][block][version][flow][vendor][branch][task] is not None:
                                        check_flag = 0
                                        for category in setting['BLOCK'][block][version][flow][vendor][branch][task].keys():
                                            if category in self.default_setting[flow][vendor][task].keys():
                                                for item in setting['BLOCK'][block][version][flow][vendor][branch][task][category].keys():
                                                    if item in self.default_setting[flow][vendor][task][category].keys():
                                                        if not setting['BLOCK'][block][version][flow][vendor][branch][task][category][item] == self.default_setting[flow][vendor][task][category][item]:
                                                            check_flag = 1
                                                    else:
                                                        check_flag = 1
                                            else:
                                                check_flag = 1

                                        if check_flag == 1:
                                            self.detailed_setting[block][block_version][flow][vendor][task_branch][task] = \
                                                setting['BLOCK'][block][version][flow][vendor][branch][task]

                            order_rows[self.priority[block][block_version][flow]]['end'] = row

                            run_type_rows['end'] = row

                            if run_type_rows['end'] - run_type_rows['start'] > 1 and self.run_type[block][block_version][flow][vendor][task_branch] == 'parallel':
                                self.setup_table.setSpan(run_type_rows['start'], 6, run_type_rows['end'] - run_type_rows['start'], 1)

                            if row - branch_start_line > 1:
                                self.setup_table.setSpan(branch_start_line, 5, row - branch_start_line, 1)
                                self.span_info[branch_start_line][4] = row - 1

                        if row - vendor_start_line > 1:
                            self.setup_table.setSpan(vendor_start_line, 4, row - vendor_start_line, 1)
                            self.span_info[vendor_start_line][3] = row - 1

                    if row - flow_start_line > 1:
                        self.setup_table.setSpan(flow_start_line, 3, row - flow_start_line, 1)
                        self.span_info[flow_start_line][2] = row - 1

                for num in order_rows.keys():
                    if order_rows[num]['end'] - order_rows[num]['start'] > 1:
                        self.setup_table.setSpan(order_rows[num]['start'], 2, order_rows[num]['end'] - order_rows[num]['start'], 1)

                if row - version_start_line > 1:
                    self.setup_table.setSpan(version_start_line, 1, row - version_start_line, 1)
                    self.span_info[version_start_line][1] = row - 1

            if row - block_start_line > 1:
                self.setup_table.setSpan(block_start_line, 0, row - block_start_line, 1)
                self.span_info[block_start_line][0] = row - 1
        self.update_state(self.state)

    """
    1. Parsing GUI user setting
    2. Update self.user_input['BLOCK'][block][version][flow][vendor][branch][task]
    """

    def parsing_user_setting(self):
        self.user_input = AutoVivification()

        for i in range(self.setup_model.rowCount()):
            block = self.setup_model.index(i, 0).data()
            version = self.setup_model.index(i, 1).data()
            flow = self.setup_model.index(i, 3).data()
            vendor = self.setup_model.index(i, 4).data()
            branch = self.setup_model.index(i, 5).data()
            task = self.setup_model.index(i, 7).data()

            if not block == self.table_info[i][0] and not self.span_info[i][0] == {}:
                self.table_info[i][0] = block

                for j in range(i + 1, self.span_info[i][0] + 1):
                    self.setup_model.setItem(j, 0, QStandardItem(block))
                    self.table_info[j][0] = block

            if not version == self.table_info[i][1] and not self.span_info[i][1] == {}:
                self.table_info[i][1] = version

                for j in range(i + 1, self.span_info[i][1] + 1):
                    self.setup_model.setItem(j, 1, QStandardItem(version))
                    self.table_info[j][1] = version

            if not flow == self.table_info[i][3] and not self.span_info[i][3] == {}:
                self.table_info[i][3] = flow

                for j in range(i + 1, self.span_info[i][3] + 1):
                    self.setup_model.setItem(j, 3, QStandardItem(flow))
                    self.table_info[j][3] = flow

            if not vendor == self.table_info[i][4] and not self.span_info[i][4] == {}:
                self.table_info[i][4] = vendor

                for j in range(i + 1, self.span_info[i][4] + 1):
                    self.setup_model.setItem(j, 4, QStandardItem(vendor))
                    self.table_info[j][4] = vendor

            if not branch == self.table_info[i][5] and not self.span_info[i][5] == {}:
                self.table_info[i][5] = branch

                for j in range(i + 1, self.span_info[i][5] + 1):
                    self.setup_model.setItem(j, 5, QStandardItem(branch))
                    self.table_info[j][5] = branch

            self.user_input['BLOCK'][block][version][flow][vendor][branch][task] = ''

    '''
    1. Parsing GUI info by def parsing_user_setting
    2. Parsing priority of flows and change version to version(RUN_ORDER=)
    3. Parsing run_type of branches and change branch to branch(RUN_TYPE=)
    4. Delete repeated task setting between default.yaml and ifp.cfg.yaml
    5. Save final setting to self.final_setting['BLOCK'][block][version_wi_order][flow][vendor][branch_wi_type][task][category][item]
    '''

    def parsing_final_setting(self):
        self.parsing_user_setting()

        self.final_setting['PROJECT'] = self.project_edit.text()
        self.final_setting['VAR'] = {}

        for item in self.var_edit.text().split(';'):
            if len(item.split('=')) == 2:
                self.final_setting['VAR'][item.split('=')[0].strip()] = item.split('=')[1].strip()

        self.final_setting['BLOCK'] = {}

        for block in self.user_input['BLOCK'].keys():
            if block == '' or block is None:
                continue

            self.final_setting['BLOCK'].setdefault(block, {})

            for version in self.user_input['BLOCK'][block].keys():
                if version == '':
                    Dialog('WARNING', 'Can not save your setting to config file due to empty version!', QMessageBox.Warning)
                    return

                ordered_flow = []

                if self.priority[block][version] == {}:
                    version_wi_order = '%s(RUN_ORDER=%s)' % (version, ','.join(self.user_input['BLOCK'][block][version].keys()))
                    ordered_flow = self.user_input['BLOCK'][block][version].keys()
                else:
                    final_priority = {}

                    for flow in self.priority[block][version].keys():
                        if not self.priority[block][version][flow] in final_priority.keys():
                            final_priority[self.priority[block][version][flow]] = [flow]
                        else:
                            final_priority[self.priority[block][version][flow]].append(flow)

                    priority = []

                    for key in sorted(final_priority.keys()):
                        priority.append('|'.join(final_priority[key]))
                        ordered_flow.extend(final_priority[key])

                    version_wi_order = '%s(RUN_ORDER=%s)' % (version, ','.join(priority))

                self.final_setting['BLOCK'][block].setdefault(version_wi_order, {})

                for flow in ordered_flow:
                    if flow == '':
                        Dialog('WARNING', 'Can not save your setting to config file due to empty flow!', QMessageBox.Warning)
                        return

                    self.final_setting['BLOCK'][block][version_wi_order].setdefault(flow, {})

                    for vendor in self.user_input['BLOCK'][block][version][flow].keys():
                        if vendor == '':
                            Dialog('WARNING', 'Can not save your setting to config file due to empty vendor!', QMessageBox.Warning)
                            return

                        self.final_setting['BLOCK'][block][version_wi_order][flow].setdefault(vendor, {})

                        for branch in self.user_input['BLOCK'][block][version][flow][vendor].keys():
                            if branch == '':
                                Dialog('WARNING', 'Can not save your setting to config file due to empty branch!', QMessageBox.Warning)
                                return

                            if self.run_type[block][version][flow][vendor][branch] == {}:
                                self.run_type[block][version][flow][vendor][branch] = 'serial'

                            branch_wi_type = '%s(RUN_TYPE=%s)' % (branch, self.run_type[block][version][flow][vendor][branch])

                            self.final_setting['BLOCK'][block][version_wi_order][flow][vendor].setdefault(branch_wi_type, {})

                            for task in self.user_input['BLOCK'][block][version][flow][vendor][branch].keys():
                                if task == '':
                                    Dialog('WARNING', 'Can not save your setting to config file due to empty task!', QMessageBox.Warning)
                                    return

                                self.final_setting['BLOCK'][block][version_wi_order][flow][vendor][branch_wi_type].setdefault(task, {})

                                if not self.detailed_setting[block][version][flow][vendor][branch][task] == {}:
                                    for category in self.detailed_setting[block][version][flow][vendor][branch][task].keys():
                                        if self.detailed_setting[block][version][flow][vendor][branch][task][category] == {}:
                                            continue

                                        for item in self.detailed_setting[block][version][flow][vendor][branch][task][category].keys():
                                            if category in self.default_setting[flow][vendor][task].keys():
                                                if item in self.default_setting[flow][vendor][task][category].keys():
                                                    if self.default_setting[flow][vendor][task][category][item] == self.detailed_setting[block][version][flow][vendor][branch][task][category][item]:
                                                        continue

                                            self.final_setting['BLOCK'][block][version_wi_order][flow][vendor][branch_wi_type][task].setdefault(category, {})
                                            self.final_setting['BLOCK'][block][version_wi_order][flow][vendor][branch_wi_type][task][category][item] = self.detailed_setting[block][version][flow][vendor][branch][task][category][item]

    """
    1. Load ifp.cfg.yaml
    2. Draw table by raw setting
    3. Parsing GUI setting and check if any default task setting that not defined in default.yaml and ifp.cfg.yaml
    4. Update ifp.cfg.yaml and reload
    """

    def load(self):
        self.user_input = AutoVivification()
        self.detailed_setting = AutoVivification()
        self.priority = AutoVivification()
        file = open(self.config_path_edit.text(), 'r')
        self.raw_setting = yaml.safe_load(file)

        if self.raw_setting is None:
            return

        if 'PROJECT' in self.raw_setting.keys():
            self.project_edit.setText(self.raw_setting['PROJECT'])

        if ('VAR' in self.raw_setting.keys()) and self.raw_setting['VAR']:
            self.var_edit.setText(';'.join(['%s=%s' % (key, self.raw_setting['VAR'][key]) for key in self.raw_setting['VAR'].keys()]))
        else:
            self.raw_setting['VAR'] = {}

        self.draw_table(self.raw_setting, stage='load')
        self.parsing_user_setting()

    def save(self):
        self.parsing_final_setting()
        self.save_flag.emit(True)

    def generate_menu(self, pos):
        if self.project_edit.text() == '':
            Dialog('WARNING', 'Please enter project name firstly', QMessageBox.Warning)
            return

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
            self.current_selected_flow = self.setup_model.index(self.current_selected_row, 3).data()
            self.current_selected_vendor = self.setup_model.index(self.current_selected_row, 4).data()
            self.current_selected_branch = self.setup_model.index(self.current_selected_row, 5).data()
            self.current_selected_task = self.setup_model.index(self.current_selected_row, 7).data()

        if len(self.setup_table.selectedIndexes()) == 0:
            action1 = QAction('Create block')
            action1.triggered.connect(lambda: self.add_more_item('block'))
            menu.addAction(action1)
        else:
            if self.current_selected_column == 0:
                action1 = QAction('Add block')
                action1.triggered.connect(lambda: self.add_more_item('block'))
                menu.addAction(action1)
                action4 = QAction('Copy block')
                action4.triggered.connect(lambda: self.copy_current_item('block'))
                menu.addAction(action4)

                if len(selected_rows[0]) > 1:
                    action2 = QAction('Remove blocks')
                else:
                    action2 = QAction('Remove block')

                action2.triggered.connect(lambda: self.remove_current_item('block'))
                menu.addAction(action2)
            elif self.current_selected_column == 1:
                action1 = QAction('Add version')
                action1.triggered.connect(lambda: self.add_more_item('version'))
                menu.addAction(action1)
                action4 = QAction('Copy version')
                action4.triggered.connect(lambda: self.copy_current_item('version'))
                menu.addAction(action4)

                if len(selected_rows[1]) > 1:
                    action2 = QAction('Remove versions')
                else:
                    action2 = QAction('Remove version')

                action2.triggered.connect(lambda: self.remove_current_item('version'))
                menu.addAction(action2)
                action3 = QAction('Set RUN_ORDER')
                action3.triggered.connect(lambda: self.set_priority(self.current_selected_block, self.current_selected_version))
                menu.addAction(action3)
            elif self.current_selected_column == 3:
                action1 = QAction('Add flow')
                action1.triggered.connect(lambda: self.add_more_item('flow'))
                menu.addAction(action1)
                action4 = QAction('Copy flow')
                action4.triggered.connect(lambda: self.copy_current_item('flow'))
                menu.addAction(action4)

                if len(selected_rows[3]) > 1:
                    action2 = QAction('Remove flows')
                else:
                    action2 = QAction('Remove flow')

                action2.triggered.connect(lambda: self.remove_current_item('flow'))
                menu.addAction(action2)
            elif self.current_selected_column == 4:
                action1 = QAction('Add vendor')
                action1.triggered.connect(lambda: self.add_more_item('vendor'))
                menu.addAction(action1)
                action4 = QAction('Copy vendor')
                action4.triggered.connect(lambda: self.copy_current_item('vendor'))
                menu.addAction(action4)

                if len(selected_rows[4]) > 1:
                    action2 = QAction('Remove vendors')
                else:
                    action2 = QAction('Remove vendor')

                action2.triggered.connect(lambda: self.remove_current_item('vendor'))
                menu.addAction(action2)
            elif self.current_selected_column == 5:
                action1 = QAction('Add branch')
                action1.triggered.connect(lambda: self.add_more_item('branch'))
                menu.addAction(action1)

                if len(selected_rows[5]) > 1:
                    action2 = QAction('Remove branches')
                    action4 = QAction('Copy branches')

                else:
                    action2 = QAction('Remove branch')
                    action4 = QAction('Copy branch')

                action4.triggered.connect(lambda: self.copy_current_item('branch'))
                menu.addAction(action4)
                action2.triggered.connect(lambda: self.remove_current_item('branch'))
                menu.addAction(action2)

                menu2 = menu.addMenu('Set RUN_TYPE')

                action3 = QAction('parallel')
                action3.setCheckable(True)

                action5 = QAction('serial')
                action5.setCheckable(True)
                action3.triggered.connect(lambda: self.set_run_type('parallel'))
                action5.triggered.connect(lambda: self.set_run_type('serial'))

                menu2.addAction(action3)
                menu2.addAction(action5)

                if self.run_type[self.current_selected_block][self.current_selected_version][self.current_selected_flow][self.current_selected_vendor][self.current_selected_branch] == {}:
                    self.run_type[self.current_selected_block][self.current_selected_version][self.current_selected_flow][self.current_selected_vendor][self.current_selected_branch] = 'serial'
                    action3.setChecked(False)
                    action5.setChecked(True)
                elif self.run_type[self.current_selected_block][self.current_selected_version][self.current_selected_flow][self.current_selected_vendor][self.current_selected_branch] == 'serial':
                    action3.setChecked(False)
                    action5.setChecked(True)
                elif self.run_type[self.current_selected_block][self.current_selected_version][self.current_selected_flow][self.current_selected_vendor][self.current_selected_branch] == 'parallel':
                    action3.setChecked(True)
                    action5.setChecked(False)
            elif self.current_selected_column == 7:
                action1 = QAction('Edit task')
                action1.triggered.connect(lambda: self.edit_detailed_config())
                menu.addAction(action1)
                action3 = QAction('Add task')
                action3.triggered.connect(lambda: self.add_more_item('task'))
                menu.addAction(action3)
                action4 = QAction('Copy task')
                action4.triggered.connect(lambda: self.copy_current_item('task'))
                menu.addAction(action4)

                if len(selected_rows[7]) > 1:
                    action2 = QAction('Remove tasks')
                else:
                    action2 = QAction('Remove task')

                action2.triggered.connect(lambda: self.remove_current_item('task'))
                menu.addAction(action2)

        menu.exec_(self.setup_table.mapToGlobal(pos))

    def set_run_type(self, run_type):
        self.run_type[self.current_selected_block][self.current_selected_version][self.current_selected_flow][self.current_selected_vendor][self.current_selected_branch] = run_type
        self.save()

    def set_priority(self, block, version):
        self.parsing_user_setting()
        self.child = WindowForRunOrder(block, version, self.user_input['BLOCK'][block][version].keys(), self.priority[block][version])
        self.child.setWindowModality(Qt.ApplicationModal)
        self.child.message.connect(self.update_priority)
        self.child.save_signal.connect(self.save)
        self.child.show()

    def clean_dict_for_empty_key(self):
        raw_setting = copy.deepcopy(self.user_input)

        for block in raw_setting['BLOCK'].keys():
            if raw_setting['BLOCK'][block] == {}:
                del self.user_input['BLOCK'][block]
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
                                    del self.priority[block][version]
                                    if self.user_input['BLOCK'][block] == {}:
                                        del self.user_input['BLOCK'][block]
                            else:
                                for vendor in raw_setting['BLOCK'][block][version][flow].keys():
                                    if raw_setting['BLOCK'][block][version][flow][vendor] == {}:
                                        del self.user_input['BLOCK'][block][version][flow][vendor]
                                        if self.user_input['BLOCK'][block][version][flow] == {}:
                                            del self.user_input['BLOCK'][block][version][flow]
                                            del self.priority[block][version][flow]
                                            if self.user_input['BLOCK'][block][version] == {}:
                                                del self.user_input['BLOCK'][block][version]
                                                del self.priority[block][version]
                                                if self.user_input['BLOCK'][block] == {}:
                                                    del self.user_input['BLOCK'][block]
                                    else:
                                        for branch in raw_setting['BLOCK'][block][version][flow][vendor].keys():
                                            if raw_setting['BLOCK'][block][version][flow][vendor][branch] == {}:
                                                del self.user_input['BLOCK'][block][version][flow][vendor][branch]
                                                if self.user_input['BLOCK'][block][version][flow][vendor] == {}:
                                                    del self.user_input['BLOCK'][block][version][flow][vendor]
                                                    if self.user_input['BLOCK'][block][version][flow] == {}:
                                                        del self.user_input['BLOCK'][block][version][flow]
                                                        del self.priority[block][version][flow]
                                                        if self.user_input['BLOCK'][block][version] == {}:
                                                            del self.user_input['BLOCK'][block][version]
                                                            del self.priority[block][version]
                                                            if self.user_input['BLOCK'][block] == {}:
                                                                del self.user_input['BLOCK'][block]

    def add_more_item(self, item):
        self.parsing_user_setting()
        self.child = WindowForAddItems(item, self.user_input, self.detailed_setting, self.priority, self.run_type, self.current_selected_block, self.current_selected_version, self.current_selected_flow, self.current_selected_vendor, self.current_selected_branch, self.current_selected_task)
        self.child.setWindowModality(Qt.ApplicationModal)
        self.child.message.connect(self.update_table_after_add)
        self.child.save_signal.connect(self.save)
        self.child.show()

    def remove_current_item(self, item):

        self.parsing_user_setting()
        selected_rows = AutoVivification()

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
            for row in selected_rows[0]:
                block = self.setup_model.index(row, 0).data()
                del self.user_input['BLOCK'][block]

                if block in self.priority.keys():
                    del self.priority[block]

        if item == 'version':
            for row in selected_rows[1]:
                block = self.setup_model.index(row, 0).data()
                version = self.setup_model.index(row, 1).data()
                del self.user_input['BLOCK'][block][version]

                if block in self.priority.keys():
                    if version in self.priority[block].keys():
                        del self.priority[block][version]

        if item == 'flow':
            for row in selected_rows[3]:
                block = self.setup_model.index(row, 0).data()
                version = self.setup_model.index(row, 1).data()
                flow = self.setup_model.index(row, 3).data()
                del self.user_input['BLOCK'][block][version][flow]

                if block in self.priority.keys():
                    if version in self.priority[block].keys():
                        if flow in self.priority[block][version].keys():
                            del self.priority[block][version][flow]

        if item == 'vendor':
            for row in selected_rows[4]:
                block = self.setup_model.index(row, 0).data()
                version = self.setup_model.index(row, 1).data()
                flow = self.setup_model.index(row, 3).data()
                vendor = self.setup_model.index(row, 4).data()
                del self.user_input['BLOCK'][block][version][flow][vendor]

                if self.user_input['BLOCK'][block][version][flow] == {}:
                    del self.priority[block][version][flow]

        if item == 'branch':
            for row in selected_rows[5]:
                block = self.setup_model.index(row, 0).data()
                version = self.setup_model.index(row, 1).data()
                flow = self.setup_model.index(row, 3).data()
                vendor = self.setup_model.index(row, 4).data()
                branch = self.setup_model.index(row, 5).data()
                del self.user_input['BLOCK'][block][version][flow][vendor][branch]

        if item == 'task':
            for row in selected_rows[7]:
                block = self.setup_model.index(row, 0).data()
                version = self.setup_model.index(row, 1).data()
                flow = self.setup_model.index(row, 3).data()
                vendor = self.setup_model.index(row, 4).data()
                branch = self.setup_model.index(row, 5).data()
                task = self.setup_model.index(row, 7).data()
                del self.user_input['BLOCK'][block][version][flow][vendor][branch][task]

        self.clean_dict_for_empty_key()
        self.draw_table(self.user_input)
        self.save()

    def copy_current_item(self, item):
        selected_rows = AutoVivification()
        for index in self.setup_table.selectedIndexes():
            if index.column() not in selected_rows.keys():
                selected_rows.setdefault(index.column(), [])

            selected_rows[index.column()].append(index.row())

        selected_branches = AutoVivification()

        if item == 'branch' and len(selected_rows[5]) > 1:
            for block in self.user_input['BLOCK'].keys():
                block_flag = False
                for version in self.user_input['BLOCK'][block].keys():
                    for flow in self.user_input['BLOCK'][block][version].keys():
                        for vendor in self.user_input['BLOCK'][block][version][flow].keys():
                            for branch in self.user_input['BLOCK'][block][version][flow][vendor].keys():
                                for row in selected_rows[5]:
                                    selected_block = self.setup_model.index(row, 0).data()
                                    selected_version = self.setup_model.index(row, 1).data()
                                    selected_flow = self.setup_model.index(row, 3).data()
                                    selected_vendor = self.setup_model.index(row, 4).data()
                                    selected_branch = self.setup_model.index(row, 5).data()

                                    if selected_block == block and selected_version == version and selected_flow == flow and selected_vendor == vendor and selected_branch == branch:
                                        selected_branches['BLOCK'][block][version][flow][vendor][branch] = True
                                        block_flag = True
                                        break
                                    else:
                                        selected_branches['BLOCK'][block][version][flow][vendor][branch] = False

                if block_flag is False:
                    del selected_branches['BLOCK'][block]

            self.child = WindowForCopyItems('branches', self.user_input, self.detailed_setting, self.priority, self.run_type, selected_branches=selected_branches)
        else:
            self.child = WindowForCopyItems(item, self.user_input, self.detailed_setting, self.priority, self.run_type, block=self.current_selected_block, version=self.current_selected_version, flow=self.current_selected_flow, vendor=self.current_selected_vendor, branch=self.current_selected_branch,
                                            task=self.current_selected_task,
                                            )
        self.child.setWindowModality(Qt.ApplicationModal)
        self.child.message.connect(self.update_table_after_copy)
        self.child.save_signal.connect(self.save)
        self.child.show()

    def update_table_after_copy(self, info):
        copy_item = info[0]

        self.draw_table(self.user_input)

        if copy_item == 'update flow':
            self.set_priority(self.current_selected_block, self.current_selected_version)
            Dialog('Warning', 'Please set priority for new flow!', QMessageBox.Warning)
        elif copy_item == 'task':

            # Copy all default setting of raw task to new task as user defined setting if new task is not a default task
            new_task = info[1]

            if new_task not in self.default_setting[self.current_selected_flow][self.current_selected_vendor].keys():
                for category in self.default_setting[self.current_selected_flow][self.current_selected_vendor][self.current_selected_task].keys():
                    if category not in self.detailed_setting[self.current_selected_block][self.current_selected_version][self.current_selected_flow][self.current_selected_vendor][self.current_selected_branch][new_task].keys():
                        self.detailed_setting[self.current_selected_block][self.current_selected_version][self.current_selected_flow][self.current_selected_vendor][self.current_selected_branch][new_task].setdefault(category, {})
                    for item in self.default_setting[self.current_selected_flow][self.current_selected_vendor][self.current_selected_task][category].keys():
                        if item not in self.detailed_setting[self.current_selected_block][self.current_selected_version][self.current_selected_flow][self.current_selected_vendor][self.current_selected_branch][new_task][category].keys():
                            self.detailed_setting[self.current_selected_block][self.current_selected_version][self.current_selected_flow][self.current_selected_vendor][self.current_selected_branch][new_task][category][item] = \
                                self.default_setting[self.current_selected_flow][self.current_selected_vendor][self.current_selected_task][category][item]

    def update_table_after_add(self, info):
        self.user_input = copy.deepcopy(info[0])
        self.priority = copy.deepcopy(info[1])
        self.draw_table(self.user_input)

        if info[2] == 'update flow':
            self.set_priority(info[3], info[4])
            Dialog('Warning', 'Please set priority for new flow!', QMessageBox.Warning)

    def edit_detailed_config(self):

        if self.current_selected_flow in self.default_setting.keys():
            if self.current_selected_vendor in self.default_setting[self.current_selected_flow].keys():
                self.child = WindowForDetailedTaskInfo(self.user_input,
                                                       self.default_setting,
                                                       self.detailed_setting[self.current_selected_block][self.current_selected_version][self.current_selected_flow][self.current_selected_vendor][self.current_selected_branch][self.current_selected_task],
                                                       self.blank_setting,
                                                       self.default_var,
                                                       self.cwd,
                                                       self.current_selected_block,
                                                       self.current_selected_version,
                                                       self.current_selected_flow,
                                                       self.current_selected_vendor,
                                                       self.current_selected_branch,
                                                       self.current_selected_task,
                                                       self.raw_setting['VAR'] if 'VAR' in self.raw_setting.keys() else {})
                self.child.setWindowModality(Qt.ApplicationModal)
                self.child.message.connect(self.update_detailed_setting)
                self.child.show()
                return

        self.child = WindowForDetailedTaskInfo(self.user_input,
                                               {},
                                               self.detailed_setting[self.current_selected_block][self.current_selected_version][self.current_selected_flow][self.current_selected_vendor][self.current_selected_branch][self.current_selected_task],
                                               self.blank_setting,
                                               self.default_var,
                                               self.cwd,
                                               self.current_selected_block,
                                               self.current_selected_version,
                                               self.current_selected_flow,
                                               self.current_selected_vendor,
                                               self.current_selected_branch,
                                               self.current_selected_task,
                                               self.raw_setting['VAR'] if 'VAR' in self.raw_setting.keys() else {})
        self.child.setWindowModality(Qt.ApplicationModal)
        self.child.message.connect(self.update_detailed_setting)
        self.child.show()

    def update_detailed_setting(self, value):
        setting = value[0]
        new_task = value[1]
        new_setting = copy.deepcopy(setting)

        if not self.current_selected_task == new_task:
            if self.current_selected_task in self.detailed_setting[self.current_selected_block][self.current_selected_version][self.current_selected_flow][self.current_selected_vendor][self.current_selected_branch].keys():
                del self.detailed_setting[self.current_selected_block][self.current_selected_version][self.current_selected_flow][self.current_selected_vendor][self.current_selected_branch][self.current_selected_task]
                del self.user_input['BLOCK'][self.current_selected_block][self.current_selected_version][self.current_selected_flow][self.current_selected_vendor][self.current_selected_branch][self.current_selected_task]

                self.user_input['BLOCK'][self.current_selected_block][self.current_selected_version][self.current_selected_flow][self.current_selected_vendor][self.current_selected_branch][new_task] = ''
                self.setup_model.setItem(self.current_selected_row, 7, QStandardItem(new_task))

        for category in setting.keys():
            if self.current_selected_flow in self.default_setting.keys():
                if self.current_selected_vendor in self.default_setting[self.current_selected_flow].keys():
                    if new_task in self.default_setting[self.current_selected_flow][self.current_selected_vendor].keys():
                        if category in self.default_setting[self.current_selected_flow][self.current_selected_vendor][new_task].keys():
                            for item in setting[category].keys():
                                if item in self.default_setting[self.current_selected_flow][self.current_selected_vendor][new_task][category].keys():
                                    if self.default_setting[self.current_selected_flow][self.current_selected_vendor][new_task][category][item] == setting[category][item]:
                                        del new_setting[category][item]

            for item in setting[category].keys():
                if setting[category][item] == '':
                    del new_setting[category][item]

            if len(new_setting[category].keys()) == 0:
                del new_setting[category]

        self.detailed_setting[self.current_selected_block][self.current_selected_version][self.current_selected_flow][self.current_selected_vendor][self.current_selected_branch][new_task] = copy.deepcopy(new_setting)
        self.current_selected_task = new_task
        self.save()

    def update_priority(self, value):
        block = value[0]
        version = value[1]
        priority = value[2]
        self.priority[block][version] = priority
        self.draw_table(self.user_input)

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


class Worker(QObject):
    message = pyqtSignal(dict)

    def __init__(self, mainwindow):
        super(QObject, self).__init__()
        self.mainwindow = mainwindow
        self.user_input = AutoVivification()
        self.detailed_setting = AutoVivification()
        self.default_setting = AutoVivification()
        self.priority = AutoVivification()
        self.state = AutoVivification()

    def run(self):
        while True:
            self.user_input = copy.deepcopy(self.mainwindow.user_input)
            self.detailed_setting = copy.deepcopy(self.mainwindow.detailed_setting)
            self.default_setting = copy.deepcopy(self.mainwindow.default_setting)
            self.priority = copy.deepcopy(self.mainwindow.priority)

            for block in self.user_input['BLOCK'].keys():
                for version in self.user_input['BLOCK'][block].keys():

                    # if not self.mainwindow.priority[block][version] == {}:
                    #     if not sorted(list(self.user_input['BLOCK'][block][version].keys())) == sorted(self.mainwindow.priority[block][version].keys()):
                    #         self.mainwindow.priority[block][version] = {}

                    for flow in self.user_input['BLOCK'][block][version].keys():
                        for vendor in self.user_input['BLOCK'][block][version][flow].keys():
                            for branch in self.user_input['BLOCK'][block][version][flow][vendor].keys():
                                for task in self.user_input['BLOCK'][block][version][flow][vendor][branch].keys():
                                    if not self.detailed_setting[block][version][flow][vendor][branch][task] == {}:
                                        self.state[block][version][flow][vendor][branch][task] = 'user'
                                        continue

                                    if flow in self.default_setting.keys():
                                        if vendor in self.default_setting[flow].keys():
                                            if task in self.default_setting[flow][vendor].keys():
                                                self.state[block][version][flow][vendor][branch][task] = 'default'
                                                continue

                                    self.state[block][version][flow][vendor][branch][task] = 'blank'

            self.message.emit(self.state)
            time.sleep(3)


class WindowForAddItems(QMainWindow):
    message = pyqtSignal(list)
    save_signal = pyqtSignal(bool)

    def __init__(self, item, user_input, detailed_setting, priority, run_type, block=None, version=None, flow=None, vendor=None, branch=None, task=None):
        super().__init__()
        self.item = item
        self.user_input = user_input
        self.detailed_setting = detailed_setting
        self.priority = priority
        self.run_type = run_type
        self.block = block
        self.version = version
        self.flow = flow
        self.vendor = vendor
        self.branch = branch
        self.task = task

        self.top_widget = QWidget()
        self.top_layout = QVBoxLayout()
        self.top_widget.setLayout(self.top_layout)
        self.setCentralWidget(self.top_widget)

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

        self.top_layout.addWidget(self.table)
        self.top_layout.addWidget(self.button_widget)

        self.draw_table(self.table, self.table_model, editable=True)

        self.resize(1200, 100)
        self.setWindowTitle('Add new %s' % self.item)
        center(self)

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

    def save(self):
        block = None
        version = None
        for i in range(self.table_model.rowCount()):

            block = self.table_model.index(i, 0).data()
            version = self.table_model.index(i, 1).data()
            flow = self.table_model.index(i, 2).data()
            vendor = self.table_model.index(i, 3).data()
            branch = self.table_model.index(i, 4).data()
            task = self.table_model.index(i, 5).data()

            if '' or None in [block, version, flow, vendor, branch, task]:
                Dialog('Error', "Please fill in any empty item", QMessageBox.Critical)
                return

            if self.item == 'block' and block in self.user_input['BLOCK'].keys():
                Dialog('Error', "You add one repeated block %s" % block, QMessageBox.Critical)
                return
            elif self.item == 'version' and version in self.user_input['BLOCK'][block].keys():
                Dialog('Error', "You add one repeated version %s" % version, QMessageBox.Critical)
                return
            elif self.item == 'flow' and flow in self.user_input['BLOCK'][block][version].keys():
                Dialog('Error', "You add one repeated flow %s" % flow, QMessageBox.Critical)
                return
            elif self.item == 'vendor' and vendor in self.user_input['BLOCK'][block][version][flow].keys():
                Dialog('Error', "You add one repeated vendor %s" % vendor, QMessageBox.Critical)
                return
            elif self.item == 'branch' and branch in self.user_input['BLOCK'][block][version][flow][vendor].keys():
                Dialog('Error', "You add one repeated branch %s" % branch, QMessageBox.Critical)
                return
            elif self.item == 'task' and task in self.user_input['BLOCK'][block][version][flow][vendor][branch].keys():
                Dialog('Error', "You add one repeated task %s" % task, QMessageBox.Critical)
                return

            if self.item == 'flow':
                self.priority[block][version][flow] = 9999
            elif self.item in ['block', 'version']:
                self.priority[block][version][flow] = 1

            if self.item == 'task':
                all_tasks = list(self.user_input['BLOCK'][block][version][flow][vendor][branch].keys())
                index = all_tasks.index(self.task)
                all_tasks.insert(index + 1, task)
                self.user_input['BLOCK'][block][version][flow][vendor][branch] = {}
                for k in all_tasks:
                    self.user_input['BLOCK'][block][version][flow][vendor][branch][k] = ''

            else:
                self.user_input['BLOCK'][block][version][flow][vendor][branch][task] = ''

        if self.item == 'flow':
            self.message.emit([self.user_input, self.priority, 'update flow', block, version])
        else:
            self.message.emit([self.user_input, self.priority, self.item, block, version])

        self.close()
        self.save_signal.emit(True)


class WindowForCopyItems(QMainWindow):
    message = pyqtSignal(list)
    save_signal = pyqtSignal(bool)

    def __init__(self, item, user_input, detailed_setting, priority, run_type, block=None, version=None, flow=None, vendor=None, branch=None, task=None, selected_branches=None):
        super().__init__()
        self.item = item
        self.user_input = user_input
        self.detailed_setting = detailed_setting
        self.priority = priority
        self.run_type = run_type
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
                block_version = version
                version_start_line = row

                ordered_flow = []

                if self.priority[block][version] == {}:
                    ordered_flow = self.user_input['BLOCK'][block][version].keys()
                else:
                    final_priority = {}

                    for flow in self.priority[block][version].keys():
                        if not self.priority[block][version][flow] in final_priority.keys():
                            final_priority[self.priority[block][version][flow]] = [flow]
                        else:
                            final_priority[self.priority[block][version][flow]].append(flow)

                    for key in sorted(final_priority.keys()):
                        ordered_flow.extend(final_priority[key])

                for flow in ordered_flow:
                    if self.item in ['flow', 'vendor', 'branch', 'task'] and not flow == self.flow:
                        continue

                    flow_start_line = row

                    for vendor in self.user_input['BLOCK'][block][version][flow].keys():
                        if self.item in ['vendor', 'branch', 'task'] and not vendor == self.vendor:
                            continue

                        vendor_start_line = row

                        for branch in self.user_input['BLOCK'][block][version][flow][vendor].keys():
                            if self.item in ['task'] and not branch == self.branch:
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

                                    version_item = QStandardItem(block_version)
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
                                        self.table_info[row] = [block, block_version, flow, vendor, '', task]
                                        branch_item.setBackground(QBrush(QColor(255, 248, 220)))
                                    else:
                                        self.copy_branches_row_mapping[row] = False
                                        branch_item = QStandardItem(branch)
                                        self.table_info[row] = [block, block_version, flow, vendor, branch, task]

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

            if not self.run_type[block_new][version_new][flow_new][vendor_new][branch_new]:
                self.run_type[block_new][version_new][flow_new][vendor_new][branch_new] = self.run_type[block][version][flow][vendor][branch]

            if not self.priority[block_new][version_new]:
                self.priority[block_new][version_new] = copy.deepcopy(self.priority[block][version])

            if not self.item == 'branches':
                if not flow_new == flow:
                    update_flow_flag = True
                    self.priority[block_new][version_new][flow_new] = 9999

        if update_flow_flag:
            self.message.emit(['update flow'])
        elif self.item == 'task':

            self.message.emit([self.item, task_new])
        else:
            self.message.emit([self.item])

        self.close()
        self.save_signal.emit(True)


class WindowForDetailedTaskInfo(QMainWindow):
    message = pyqtSignal(list)

    def __init__(self, user_input, default_setting, detailed_setting, blank_setting, default_var, cwd, block, version, flow, vendor, branch, task, var):
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
        self.setup_table.setColumnWidth(0, 120)

        self.setup_model.setHorizontalHeaderLabels(header)
        self.setup_table.setStyleSheet('font-family : calibri; font-size : 15px')
        self.setup_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.setup_table.setShowGrid(True)

        # Defined by system
        self.env_mapping = {'$CWD': self.cwd,
                            '$IFP_INSTALL_PATH': os.getenv('IFP_INSTALL_PATH'),
                            '$BLOCK': self.block,
                            '$VERSION': self.version,
                            '$FLOW': self.flow,
                            '$VENDOR': self.vendor,
                            '$BRANCH': self.branch,
                            '$TASK': self.raw_task,
                            }

        # Defined by default yaml
        for key in self.default_var.keys():
            self.env_mapping.setdefault('$%s' % key, self.default_var[key])

        # Defined by user VAR and will replace system and default env setting
        for key in self.var.keys():
            self.env_mapping['$' + key] = self.var[key]

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

        self.top_layout.addWidget(self.widget_task_name)
        self.top_layout.addStretch(1)
        self.top_layout.addWidget(self.label_env)
        self.top_layout.addWidget(self.env_table)
        self.top_layout.addStretch(1)
        self.top_layout.addWidget(self.label_setup)
        self.top_layout.addWidget(self.setup_table)
        self.top_layout.addWidget(self.button_widget)
        self.top_layout.setStretch(0, 1)
        self.top_layout.setStretch(2, 1)
        self.top_layout.setStretch(3, 6)
        self.top_layout.setStretch(5, 1)
        self.top_layout.setStretch(6, 8)
        self.resize(900, 600)
        center(self)

    def draw_table(self, new_task, draw_type='new'):
        self.new_task = new_task
        self.env_model.setItem(7, 1, QStandardItem(new_task))
        self.title = '%s/%s/%s' % (self.flow, self.vendor, self.new_task)
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

    def show_tips(self, index):
        desktop = QApplication.desktop()
        screen_num = desktop.screenNumber(QCursor.pos())
        screen_rect = desktop.screenGeometry(screen_num)

        if index.data() == '' and index.column() == 1 and index.row() in self.tips.keys():
            QToolTip.showText(QCursor.pos(), 'Example : ' + self.tips[index.row()], self.setup_table, screen_rect, 50000)

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

        self.message.emit([setting, self.new_task])

        self.close()


class WindowForRunOrder(QMainWindow):
    message = pyqtSignal(list)
    save_signal = pyqtSignal(bool)

    def __init__(self, block, version, flows, priority):
        super().__init__()
        self.top_widget = QWidget()
        self.top_layout = QVBoxLayout()
        self.block = block
        self.version = version
        self.top_widget.setLayout(self.top_layout)
        self.setCentralWidget(self.top_widget)

        self.flows = list(flows)
        self.priority = priority
        self.widgets = AutoVivification()

        self.save_button = QPushButton('save')
        self.save_button.clicked.connect(self.save)
        self.cancel_button = QPushButton('cancel')
        self.cancel_button.clicked.connect(self.close)
        self.user_choise = False
        self.init_ui()

    def init_ui(self):

        self.order = AutoVivification()
        self.nums = []

        if not self.priority == {}:
            for i in range(len(list(self.priority.keys()))):
                self.nums.append(str(i + 1))

            for flow in self.priority.keys():
                if not self.priority[flow] in self.order.keys():
                    self.order[self.priority[flow]] = [flow]
                else:
                    self.order[self.priority[flow]].append(flow)

            for i in self.order.keys():
                for flow in self.order[i]:
                    layout = QHBoxLayout()
                    widget = QWidget()
                    widget.setLayout(layout)
                    edit = QLineEdit()
                    edit.setText(flow)
                    edit.setEnabled(False)
                    edit.setFixedWidth(200)
                    box = QComboBox()
                    box.addItems(self.nums)

                    if str(i) not in self.nums:
                        box.setCurrentText(str(self.nums[-1]))
                    else:
                        box.setCurrentText(str(i))

                    box.setFixedWidth(50)
                    layout.addWidget(edit)
                    layout.addWidget(box)
                    layout.addStretch(1)
                    self.top_layout.addWidget(widget)
                    self.widgets[flow]['box'] = box
                    self.widgets[flow]['edit'] = edit
        else:
            for i in range(len(self.flows)):
                self.nums.append(str(i + 1))

            for i in range(len(self.flows)):
                layout = QHBoxLayout()
                widget = QWidget()
                widget.setLayout(layout)
                edit = QLineEdit()
                edit.setText(self.flows[i])
                edit.setEnabled(False)
                edit.setFixedWidth(200)
                box = QComboBox()
                box.addItems(self.nums)
                box.setCurrentText(str(i + 1))
                box.setFixedWidth(50)
                layout.addWidget(edit)
                layout.addWidget(box)
                layout.addStretch(1)
                self.top_layout.addWidget(widget)
                self.widgets[self.flows[i]]['box'] = box
                self.widgets[self.flows[i]]['edit'] = edit

        self.button_widget = QWidget()
        self.button_layout = QHBoxLayout()
        self.button_widget.setLayout(self.button_layout)

        self.button_layout.addStretch(1)
        self.button_layout.addWidget(self.save_button)
        self.button_layout.addWidget(self.cancel_button)

        self.top_layout.addWidget(self.button_widget)
        self.resize(300, 100 * len(self.nums))
        self.setWindowTitle('Set priority for %s/%s' % (self.block, self.version))
        center(self)

    def save(self):
        priority = {}

        for flow in self.widgets.keys():
            priority[flow] = int(self.widgets[flow]['box'].currentText())

        self.message.emit([self.block, self.version, priority])
        self.close()
        self.save_signal.emit(True)


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
        self.cancel_button.clicked.connect(self.cancel)

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
        self.setWindowFlag(Qt.WindowCloseButtonHint, False)
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

    def cancel(self, event):
        if self.update_flag == 1:
            reply = QMessageBox.question(
                self, "Message",
                "Are you sure to quit? Any unsaved setting will be lost.",
                QMessageBox.Save | QMessageBox.Close | QMessageBox.Cancel,
                QMessageBox.Save)

            if reply == QMessageBox.Save:
                self.save_to_yaml()
            elif reply == QMessageBox.Close:
                self.close()
            elif reply == QMessageBox.Cancel:
                pass

        else:
            self.close()

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


class Dialog:
    def __init__(self, title, info, icon=QMessageBox.Critical):
        msgbox = QMessageBox()
        msgbox.setText(info)
        msgbox.setWindowTitle(title)
        msgbox.setIcon(icon)
        msgbox.setStandardButtons(QMessageBox.Ok)
        reply = msgbox.exec()

        if reply == QMessageBox.Ok:
            return


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
        task = self.model().index(row, 7).data()

        if col == 7 and event.buttons() == Qt.MidButton:
            self.drag_row = row
            self.label.setText(task)
            self.drag_widget.show()
            self.drag_flag = True
        super(DraggableTableView, self).mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        row, col = self.indexAt(event.pos()).row(), self.indexAt(event.pos()).column()
        if col == 7 and self.drag_flag:
            self.drag_widget.move(event.pos())
            self.set_row_bg_color(row, QColor(254, 163, 86))
            self.set_row_bg_color(row + 1, QColor(255, 255, 255))
            self.set_row_bg_color(row - 1, QColor(255, 255, 255))
        super(DraggableTableView, self).mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        row, col = self.indexAt(event.pos()).row(), self.indexAt(event.pos()).column()
        if col == 7 and self.drag_flag:
            self.set_row_bg_color(row, QColor(255, 255, 255))
            self.drop_row = row
            raw_block = self.model().index(self.drag_row, 0).data()
            raw_version = self.model().index(self.drag_row, 1).data()
            raw_flow = self.model().index(self.drag_row, 3).data()
            raw_vendor = self.model().index(self.drag_row, 4).data()
            raw_branch = self.model().index(self.drag_row, 5).data()
            raw_task = self.model().index(self.drag_row, 7).data()

            new_block = self.model().index(self.drop_row, 0).data()
            new_version = self.model().index(self.drop_row, 1).data()
            new_flow = self.model().index(self.drop_row, 3).data()
            new_vendor = self.model().index(self.drop_row, 4).data()
            new_branch = self.model().index(self.drop_row, 5).data()
            new_task = self.model().index(self.drop_row, 7).data()

            if raw_block == new_block and raw_version == new_version and raw_flow == new_flow and raw_vendor == new_vendor and raw_branch == new_branch and not raw_task == new_task:
                self.exchange_flag.emit([raw_block, raw_version, raw_flow, raw_vendor, raw_branch, raw_task, new_task])

        self.drag_widget.hide()
        self.drag_flag = False
        super(DraggableTableView, self).mouseReleaseEvent(event)

    def set_row_bg_color(self, row, color):
        if row < 0:
            return

        item = self.model().itemFromIndex(self.model().index(row, 7))
        item.setBackground(QBrush(color))
