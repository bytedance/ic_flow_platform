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

from PyQt5.QtWidgets import QWidget, QMainWindow, QAction, QPushButton, QLabel, QHeaderView, QVBoxLayout, QHBoxLayout, QLineEdit, QTableView, QAbstractItemView, QMenu, QToolTip, QDesktopWidget, QMessageBox, QComboBox, QFileDialog
from PyQt5.QtGui import QBrush, QFont, QColor, QStandardItem, QStandardItemModel, QCursor
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
    blank_setting = {'BUILD': {'PATH': 'Example : $DEFAULT_PATH',
                               'COMMAND': 'Example : ./gen_block_run_dir.pl -c ${BLOCK}.block_flow.configure'},
                     'RUN': {'PATH': 'Example : $DEFAULT_PATH',
                             'COMMAND': 'Example : make presta',
                             'RUN_METHOD': 'Example : bsub -q comet -n 8 -R "rusage[mem=80000]" -Is'},
                     'CHECK': {'PATH': 'Example : $DEFAULT_PATH/syn_dc',
                               'COMMAND': 'Example : ${IFP_INSTALL_PATH}/function/check/syn/synopsys/syn_synopsys.syn_dc.py -b ${BLOCK}',
                               'VIEWER': 'Example : ${IFP_INSTALL_PATH}/function/check/tools/view_checklist_report.py -i',
                               'REPORT_FILE': 'Example : file_check/file_check.rpt'},
                     'SUMMARY': {'PATH': 'Example : ${DEFAULT_PATH}/syn_dc',
                                 'COMMAND': 'Example : ${IFP_INSTALL_PATH}/function/summary/collect_syn_qor.py',
                                 'VIEWER': 'Example : /bin/soffice',
                                 'REPORT_FILE': 'Example : fv_qor.xlsx'},
                     'POST RUN': {'PATH': 'Example : tbd',
                                  'COMMAND': 'Example : tbd',
                                  'RUN_METHOD': 'Example : tbd'},
                     'RELEASE': {'PATH': 'Example : tbd',
                                 'COMMAND': 'Example : tbd'}}
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

        self.setup_table = QTableView()
        self.setup_model = QStandardItemModel(1, 6)
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

        self.save_button = QPushButton('Save')
        self.save_button.clicked.connect(self.save)

        self.user_input = AutoVivification()
        self.detailed_setting = AutoVivification()
        self.blank_setting = parsing_blank_setting()
        self.state = AutoVivification()
        self.priority = AutoVivification()
        self.run_type = AutoVivification()
        self.final_setting = {}
        self.raw_setting = {}
        self.table_info = AutoVivification()
        self.span_info = AutoVivification()

        self.cwd = os.getcwd()

    def init_ui(self):
        self.config_path_layout.addWidget(self.config_path_label)
        self.config_path_layout.addWidget(self.config_path_edit)
        self.config_path_layout.addWidget(self.save_button)

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

        header = ['Block', 'Version', 'Flow', 'Vendor', 'Branch', 'Task']

        self.setup_model.setHorizontalHeaderLabels(header)
        self.setup_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.setup_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.setup_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.setup_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.setup_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.setup_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)

        self.setup_table.setStyleSheet('font-family : calibri; font-size : 15px')
        self.setup_table.setShowGrid(True)
        self.setup_table.setEditTriggers(QAbstractItemView.DoubleClicked)

        self.setup_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.setup_table.customContextMenuRequested.connect(self.generate_menu)

        self.top_layout.addWidget(self.config_path_widget)
        self.top_layout.addWidget(self.project_var_widget)
        self.top_layout.addWidget(self.setup_table)

        self.thread = QThread()
        self.worker = self.Worker(self)
        self.worker.moveToThread(self.thread)
        self.worker.message.connect(self.update_state)
        self.thread.started.connect(self.worker.run)
        self.thread.start()
        return self.top_widget

    def update_state(self, state):
        self.state = state
        row = self.setup_table.currentIndex().row()

        for i in range(self.setup_model.rowCount()):
            if row == i:
                continue

            block = self.setup_model.index(i, 0).data()
            version = self.setup_model.index(i, 1).data()
            flow = self.setup_model.index(i, 2).data()
            vendor = self.setup_model.index(i, 3).data()
            branch = self.setup_model.index(i, 4).data()
            task = self.setup_model.index(i, 5).data()

            item = QStandardItem(task)
            item.setTextAlignment(Qt.AlignLeft)
            item.setTextAlignment(Qt.AlignVCenter)
            item.setEditable(True)

            if None in [block, version, flow, vendor, branch, task]:
                item.setBackground(QBrush(QColor(255, 255, 255)))
            elif state[block][version][flow][vendor][branch][task] == 'user':
                item.setBackground(QBrush(QColor(100, 149, 237)))
            elif state[block][version][flow][vendor][branch][task] == 'default':
                item.setBackground(QBrush(QColor(211, 211, 211)))
            elif state[block][version][flow][vendor][branch][task] == 'blank':
                item.setBackground(QBrush(QColor(255, 0, 0)))

            self.setup_model.setItem(i, 5, item)

        self.setup_table.setEditTriggers(QAbstractItemView.DoubleClicked)
        self.setup_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.setup_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.setup_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.setup_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.setup_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.setup_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)

    class Worker(QObject):
        message = pyqtSignal(dict)

        def __init__(self, mainwindow):
            super(QObject, self).__init__()
            self.mainwindow = mainwindow
            self.user_input = AutoVivification()
            self.detailed_setting = AutoVivification()
            self.default_setting = AutoVivification()
            self.state = AutoVivification()

        def run(self):
            while True:
                self.mainwindow.parsing_user_setting()
                self.user_input = self.mainwindow.user_input
                self.detailed_setting = self.mainwindow.detailed_setting
                self.default_setting = self.mainwindow.default_setting

                for block in self.user_input['BLOCK'].keys():
                    for version in self.user_input['BLOCK'][block].keys():
                        if not self.mainwindow.priority[block][version] == {}:
                            if not sorted(list(self.user_input['BLOCK'][block][version].keys())) == sorted(self.mainwindow.priority[block][version].keys()):
                                self.mainwindow.priority[block][version] = {}

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

                ordered_flow = []

                if self.priority[block][version] == {}:
                    ordered_flow = setting['BLOCK'][block][version].keys()
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
                    flow_start_line = row

                    for vendor in setting['BLOCK'][block][version][flow].keys():
                        vendor_start_line = row

                        for branch in setting['BLOCK'][block][version][flow][vendor].keys():
                            branch_start_line = row

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
                                self.setup_model.setItem(row, 1, QStandardItem(block_version))
                                self.setup_model.setItem(row, 2, QStandardItem(flow))
                                self.setup_model.setItem(row, 3, QStandardItem(vendor))
                                self.setup_model.setItem(row, 4, QStandardItem(task_branch))
                                self.setup_model.setItem(row, 5, QStandardItem(task))
                                self.table_info[row] = [block, block_version, flow, vendor, task_branch, task]
                                row += 1

                                if stage == 'load':
                                    if setting['BLOCK'][block][version][flow][vendor][branch][task] is not None:
                                        check_flag = 0

                                        for category in setting['BLOCK'][block][version][flow][vendor][branch][task].keys():
                                            for item in setting['BLOCK'][block][version][flow][vendor][branch][task][category].keys():
                                                if not setting['BLOCK'][block][version][flow][vendor][branch][task][category][item] == self.default_setting[flow][vendor][task][category][item]:
                                                    check_flag = 1

                                        if check_flag == 1:
                                            self.detailed_setting[block][block_version][flow][vendor][task_branch][task] = \
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

        self.update_state(self.state)

    def parsing_user_setting(self):
        self.user_input = AutoVivification()

        for i in range(self.setup_model.rowCount()):
            block = self.setup_model.index(i, 0).data()
            version = self.setup_model.index(i, 1).data()
            flow = self.setup_model.index(i, 2).data()
            vendor = self.setup_model.index(i, 3).data()
            branch = self.setup_model.index(i, 4).data()
            task = self.setup_model.index(i, 5).data()

            if not block == self.table_info[i][0] and not self.span_info[i][0] == {}:
                self.table_info[i][0] = block

                for j in range(i+1, self.span_info[i][0]+1):
                    self.setup_model.setItem(j, 0, QStandardItem(block))
                    self.table_info[j][0] = block

            if not version == self.table_info[i][1] and not self.span_info[i][1] == {}:
                self.table_info[i][1] = version

                for j in range(i+1, self.span_info[i][1]+1):
                    self.setup_model.setItem(j, 1, QStandardItem(version))
                    self.table_info[j][1] = version

            if not flow == self.table_info[i][2] and not self.span_info[i][2] == {}:
                self.table_info[i][2] = flow

                for j in range(i+1, self.span_info[i][2]+1):
                    self.setup_model.setItem(j, 2, QStandardItem(flow))
                    self.table_info[j][2] = flow

            if not vendor == self.table_info[i][3] and not self.span_info[i][3] == {}:
                self.table_info[i][3] = vendor

                for j in range(i+1, self.span_info[i][3]+1):
                    self.setup_model.setItem(j, 3, QStandardItem(vendor))
                    self.table_info[j][3] = vendor

            if not branch == self.table_info[i][4] and not self.span_info[i][4] == {}:
                self.table_info[i][4] = branch

                for j in range(i+1, self.span_info[i][4]+1):
                    self.setup_model.setItem(j, 4, QStandardItem(branch))
                    self.table_info[j][4] = branch

            self.user_input['BLOCK'][block][version][flow][vendor][branch][task] = ''

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
            self.var_edit.setText(';'.join(['%s : %s' % (key, self.raw_setting['VAR'][key]) for key in self.raw_setting['VAR'].keys()]))

        self.draw_table(self.raw_setting, stage='load')

    def save(self):
        self.parsing_user_setting()

        if self.project_edit.text() == '':
            self.show_info('warning', 'Can not save your setting to config file due to empty Project!')
        else:
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
                    self.show_info('warning', 'Can not save your setting to config file due to empty version!')
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
                        self.show_info('warning', 'Can not save your setting to config file due to empty flow!')
                        return

                    self.final_setting['BLOCK'][block][version_wi_order].setdefault(flow, {})

                    for vendor in self.user_input['BLOCK'][block][version][flow].keys():
                        if vendor == '':
                            self.show_info('warning', 'Can not save your setting to config file due to empty vendor!')
                            return

                        self.final_setting['BLOCK'][block][version_wi_order][flow].setdefault(vendor, {})

                        for branch in self.user_input['BLOCK'][block][version][flow][vendor].keys():
                            if branch == '':
                                self.show_info('warning', 'Can not save your setting to config file due to empty branch!')
                                return

                            if self.run_type[block][version][flow][vendor][branch] == {}:
                                self.run_type[block][version][flow][vendor][branch] = 'serial'

                            branch_wi_type = '%s(RUN_TYPE=%s)' % (branch, self.run_type[block][version][flow][vendor][branch])

                            self.final_setting['BLOCK'][block][version_wi_order][flow][vendor].setdefault(branch_wi_type, {})

                            for task in self.user_input['BLOCK'][block][version][flow][vendor][branch].keys():
                                if task == '':
                                    self.show_info('warning', 'Can not save your setting to config file due to empty task!')
                                    return

                                self.final_setting['BLOCK'][block][version_wi_order][flow][vendor][branch_wi_type].setdefault(task, {})

                                if not self.detailed_setting[block][version][flow][vendor][branch][task] == {}:
                                    for category in self.detailed_setting[block][version][flow][vendor][branch][task].keys():
                                        self.final_setting['BLOCK'][block][version_wi_order][flow][vendor][branch_wi_type][task].setdefault(category, {})

                                        for item in self.detailed_setting[block][version][flow][vendor][branch][task][category].keys():
                                            if category in self.default_setting[flow][vendor][task].keys():
                                                if item in self.default_setting[flow][vendor][task][category].keys():
                                                    if self.default_setting[flow][vendor][task][category][item] == self.detailed_setting[block][version][flow][vendor][branch][task][category][item]:
                                                        continue

                                            self.final_setting['BLOCK'][block][version_wi_order][flow][vendor][branch_wi_type][task][category][item] = self.detailed_setting[block][version][flow][vendor][branch][task][category][item]

        self.save_flag.emit([dict(self.final_setting), self.config_path_edit.text()])

    def generate_menu(self, pos):
        menu = QMenu()
        row = self.setup_table.currentIndex().row()
        column = self.setup_table.currentIndex().column()

        if len(self.setup_table.selectedIndexes()) == 0:
            action1 = QAction('Add more block')
            action1.triggered.connect(self.add_block)
            menu.addAction(action1)
        else:
            if column == 0:
                action1 = QAction('Add more block')
                action1.triggered.connect(self.add_block)
                menu.addAction(action1)
                action4 = QAction('Copy current block')
                action4.triggered.connect(lambda: self.copy_current_item(row, column, 'block'))
                menu.addAction(action4)
                action2 = QAction('Remove current block')
                action2.triggered.connect(lambda: self.remove_current_item(row, column, 'block'))
                menu.addAction(action2)
            elif column == 1:
                action1 = QAction('Add more version')
                action1.triggered.connect(lambda: self.add_more_version(row, column))
                menu.addAction(action1)
                action4 = QAction('Copy current version')
                action4.triggered.connect(lambda: self.copy_current_item(row, column, 'version'))
                menu.addAction(action4)
                action2 = QAction('Remove current version')
                action2.triggered.connect(lambda: self.remove_current_item(row, column, 'version'))
                menu.addAction(action2)
                action3 = QAction('Set RUN_ORDER')
                action3.triggered.connect(lambda: self.set_priority(row, column))
                menu.addAction(action3)
            elif column == 2:
                action1 = QAction('Add more flow')
                action1.triggered.connect(lambda: self.add_more_flow(row, column))
                menu.addAction(action1)
                action4 = QAction('Copy current flow')
                action4.triggered.connect(lambda: self.copy_current_item(row, column, 'flow'))
                menu.addAction(action4)
                action2 = QAction('Remove current flow')
                action2.triggered.connect(lambda: self.remove_current_item(row, column, 'flow'))
                menu.addAction(action2)
            elif column == 3:
                action1 = QAction('Add more vendor')
                action1.triggered.connect(lambda: self.add_more_vendor(row, column))
                menu.addAction(action1)
                action4 = QAction('Copy current vendor')
                action4.triggered.connect(lambda: self.copy_current_item(row, column, 'vendor'))
                menu.addAction(action4)
                action2 = QAction('Remove current vendor')
                action2.triggered.connect(lambda: self.remove_current_item(row, column, 'vendor'))
                menu.addAction(action2)
            elif column == 4:
                action1 = QAction('Add more branch')
                action1.triggered.connect(lambda: self.add_more_branch(row, column))
                menu.addAction(action1)
                action4 = QAction('Copy current branch')
                action4.triggered.connect(lambda: self.copy_current_item(row, column, 'branch'))
                menu.addAction(action4)
                action2 = QAction('Remove current branch')
                action2.triggered.connect(lambda: self.remove_current_item(row, column, 'branch'))
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

                block = self.setup_model.index(row, 0).data()
                version = self.setup_model.index(row, 1).data()
                flow = self.setup_model.index(row, 2).data()
                vendor = self.setup_model.index(row, 3).data()
                branch = self.setup_model.index(row, 4).data()

                if self.run_type[block][version][flow][vendor][branch] == {}:
                    self.run_type[block][version][flow][vendor][branch] = 'serial'
                    action3.setChecked(False)
                    action5.setChecked(True)
                elif self.run_type[block][version][flow][vendor][branch] == 'serial':
                    action3.setChecked(False)
                    action5.setChecked(True)
                elif self.run_type[block][version][flow][vendor][branch] == 'parallel':
                    action3.setChecked(True)
                    action5.setChecked(False)
            elif column == 5:
                action1 = QAction('Edit task')
                action1.triggered.connect(lambda: self.edit_detailed_config(row, column))
                menu.addAction(action1)
                action3 = QAction('Add more task')
                action3.triggered.connect(lambda: self.add_more_task(row, column))
                menu.addAction(action3)
                action4 = QAction('Copy current task')
                action4.triggered.connect(lambda: self.copy_current_item(row, column, 'task'))
                menu.addAction(action4)
                action2 = QAction('Remove current task')
                action2.triggered.connect(lambda: self.remove_current_item(row, column, 'task'))
                menu.addAction(action2)

        menu.exec_(self.setup_table.mapToGlobal(pos))

    def set_run_type(self, run_type):
        row = self.setup_table.currentIndex().row()
        block = self.setup_model.index(row, 0).data()
        version = self.setup_model.index(row, 1).data()
        flow = self.setup_model.index(row, 2).data()
        vendor = self.setup_model.index(row, 3).data()
        branch = self.setup_model.index(row, 4).data()
        self.run_type[block][version][flow][vendor][branch] = run_type

    def set_priority(self, row, column):
        block = self.setup_model.index(row, 0).data()
        version = self.setup_model.index(row, 1).data()
        self.parsing_user_setting()
        self.child = MainWindow3(block, version, self.user_input['BLOCK'][block][version].keys(), self.priority[block][version])
        self.child.setWindowModality(Qt.ApplicationModal)
        self.child.message.connect(self.update_priority)
        self.child.show()

    def add_block(self):
        total_rows = self.setup_model.rowCount()
        self.setup_model.insertRow(total_rows)

    def add_more_version(self, row, column):
        block = self.setup_model.index(row, 0).data()

        if block is None:
            print('Empty block, cant add new version!')
            return
        else:
            self.parsing_user_setting()
            self.user_input['BLOCK'][block][''][''][''][''][''] = ''
            self.draw_table(self.user_input)

    def add_more_flow(self, row, column):
        block = self.setup_model.index(row, 0).data()
        version = self.setup_model.index(row, 1).data()
        self.priority[block][version] = {}

        if block is None or version is None:
            print('Empty block/version, cant add new flow!')
            return
        else:
            self.parsing_user_setting()
            self.user_input['BLOCK'][block][version][''][''][''][''] = ''
            self.draw_table(self.user_input)

    def add_more_vendor(self, row, column):
        block = self.setup_model.index(row, 0).data()
        version = self.setup_model.index(row, 1).data()
        flow = self.setup_model.index(row, 2).data()

        if block is None or version is None or flow is None:
            print('Empty block/version/flow, cant add new vendor!')
            return
        else:
            self.parsing_user_setting()
            self.user_input['BLOCK'][block][version][flow][''][''][''] = ''
            self.draw_table(self.user_input)

    def add_more_branch(self, row, column):
        block = self.setup_model.index(row, 0).data()
        version = self.setup_model.index(row, 1).data()
        flow = self.setup_model.index(row, 2).data()
        vendor = self.setup_model.index(row, 3).data()

        if block is None or version is None or flow is None or vendor is None:
            print('Empty block/version/flow/vendor, cant add new branch!')
            return
        else:
            self.parsing_user_setting()
            self.user_input['BLOCK'][block][version][flow][vendor][''][''] = ''
            self.draw_table(self.user_input)

    def add_more_task(self, row, column):
        block = self.setup_model.index(row, 0).data()
        version = self.setup_model.index(row, 1).data()
        flow = self.setup_model.index(row, 2).data()
        vendor = self.setup_model.index(row, 3).data()
        branch = self.setup_model.index(row, 4).data()

        if block is None or version is None or flow is None or vendor is None or branch is None:
            print('Empty block/version/flow/vendor/branch, cant add new task!')
            return
        else:
            self.parsing_user_setting()
            self.user_input['BLOCK'][block][version][flow][vendor][branch][''] = ''
            self.draw_table(self.user_input)

    def remove_current_item(self, row, column, item):
        self.parsing_user_setting()

        block = self.setup_model.index(row, 0).data()

        if item == 'block':
            del self.user_input['BLOCK'][block]

        version = self.setup_model.index(row, 1).data()

        if item == 'version':
            del self.user_input['BLOCK'][block][version]

        flow = self.setup_model.index(row, 2).data()

        if item == 'flow':
            del self.user_input['BLOCK'][block][version][flow]

        vendor = self.setup_model.index(row, 3).data()

        if item == 'vendor':
            del self.user_input['BLOCK'][block][version][flow][vendor]

        branch = self.setup_model.index(row, 4).data()

        if item == 'branch':
            del self.user_input['BLOCK'][block][version][flow][vendor][branch]

        task = self.setup_model.index(row, 5).data()

        if item == 'task':
            del self.user_input['BLOCK'][block][version][flow][vendor][branch][task]

        self.draw_table(self.user_input)

    def copy_current_item(self, row, column, item):
        self.parsing_user_setting()

        block = self.setup_model.index(row, 0).data()

        if item == 'block':
            self.user_input['BLOCK']['%s(2)' % block] = copy.deepcopy(self.user_input['BLOCK'][block])

        version = self.setup_model.index(row, 1).data()

        if item == 'version':
            self.user_input['BLOCK'][block]['%s(2)' % version] = copy.deepcopy(self.user_input['BLOCK'][block][version])

        flow = self.setup_model.index(row, 2).data()

        if item == 'flow':
            self.user_input['BLOCK'][block][version]['%s(2)' % flow] = copy.deepcopy(self.user_input['BLOCK'][block][version][flow])

        vendor = self.setup_model.index(row, 3).data()

        if item == 'vendor':
            self.user_input['BLOCK'][block][version][flow]['%s(2)' % vendor] = copy.deepcopy(self.user_input['BLOCK'][block][version][flow][vendor])

        branch = self.setup_model.index(row, 4).data()

        if item == 'branch':
            self.user_input['BLOCK'][block][version][flow][vendor]['%s(2)' % branch] = copy.deepcopy(self.user_input['BLOCK'][block][version][flow][vendor][branch])

        task = self.setup_model.index(row, 5).data()

        if item == 'task':
            self.user_input['BLOCK'][block][version][flow][vendor][branch]['%s(2)' % task] = copy.deepcopy(self.user_input['BLOCK'][block][version][flow][vendor][branch][task])

        self.draw_table(self.user_input)

    def edit_detailed_config(self, row, column):
        block = self.setup_model.index(row, 0).data()
        version = self.setup_model.index(row, 1).data()
        flow = self.setup_model.index(row, 2).data()
        vendor = self.setup_model.index(row, 3).data()
        branch = self.setup_model.index(row, 4).data()
        task = self.setup_model.index(row, 5).data()

        if flow in self.default_setting.keys():
            if vendor in self.default_setting[flow].keys():
                if task in self.default_setting[flow][vendor].keys():
                    self.child = MainWindow2(row, column,
                                             self.default_setting[flow][vendor][task],
                                             self.detailed_setting[block][version][flow][vendor][branch][task],
                                             self.blank_setting,
                                             self.default_var,
                                             self.cwd,
                                             block,
                                             version,
                                             flow,
                                             vendor,
                                             branch,
                                             task)
                    self.child.setWindowModality(Qt.ApplicationModal)
                    self.child.message.connect(self.update)
                    self.child.show()
                    return

        self.child = MainWindow2(row, column,
                                 {},
                                 self.detailed_setting[block][version][flow][vendor][branch][task],
                                 self.blank_setting,
                                 self.default_var,
                                 self.cwd,
                                 block,
                                 version,
                                 flow,
                                 vendor,
                                 branch,
                                 task)
        self.child.setWindowModality(Qt.ApplicationModal)
        self.child.message.connect(self.update)
        self.child.show()

    def update(self, value):
        row = value[0]
        setting = value[2]
        new_setting = copy.deepcopy(setting)
        block = self.setup_model.index(row, 0).data()
        version = self.setup_model.index(row, 1).data()
        flow = self.setup_model.index(row, 2).data()
        vendor = self.setup_model.index(row, 3).data()
        branch = self.setup_model.index(row, 4).data()
        task = self.setup_model.index(row, 5).data()

        for category in setting.keys():
            if flow in self.default_setting.keys():
                if vendor in self.default_setting[flow].keys():
                    if task in self.default_setting[flow][vendor].keys():
                        if category in self.default_setting[flow][vendor][task].keys():
                            for item in setting[category].keys():
                                if item in self.default_setting[flow][vendor][task][category].keys():
                                    if self.default_setting[flow][vendor][task][category][item] == setting[category][item]:
                                        del new_setting[category][item]

            for item in setting[category].keys():
                if setting[category][item] == '':
                    del new_setting[category][item]

            if len(new_setting[category].keys()) == 0:
                del new_setting[category]

        self.detailed_setting[block][version][flow][vendor][branch][task] = new_setting

    def update_priority(self, value):
        block = value[0]
        version = value[1]
        priority = value[2]
        self.priority[block][version] = priority
        self.draw_table(self.user_input)

    def show_info(self, info_type, info):
        messagebox = QMessageBox()

        if info_type == 'warning':
            messagebox.setWindowTitle('WARNING')
            messagebox.setText(info)
        elif info_type == 'done':
            messagebox.setWindowTitle('DONE')
            messagebox.setText(info)

        messagebox.setStyleSheet("QLabel{"
                                 "min-width: 400px;"
                                 "min-height : 100px;"
                                 "}")

        screen = QDesktopWidget().screenGeometry()
        messagebox.move(int(screen.width() / 2), int(screen.height() / 2))
        messagebox.exec_()


class MainWindow2(QMainWindow):
    message = pyqtSignal(list)

    def __init__(self, row, column, default_setting, detailed_setting, blank_setting, default_var, cwd, block, version, flow, vendor, branch, task):
        super().__init__()
        self.top_widget = QWidget()
        self.top_layout = QVBoxLayout()
        self.top_widget.setLayout(self.top_layout)
        self.setCentralWidget(self.top_widget)
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
        self.task = task
        self.raw_setting = AutoVivification()
        self.setting = AutoVivification()
        self.row = row
        self.column = column
        self.tips = AutoVivification()

        if not self.detailed_setting == {}:
            self.setting = self.detailed_setting
        elif not self.default_setting == {}:
            self.setting = self.default_setting
        elif not self.blank_setting == {}:
            self.setting = self.blank_setting

        self.title = '%s/%s/%s' % (self.flow, self.vendor, self.task)
        header = ['Item', 'Value']
        self.label_env = QLabel('Env setting :')
        self.label_env.setStyleSheet('font-weight : bold')
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

        row = 0

        self.env_mapping = {'$CWD': self.cwd,
                            '$IFP_INSTALL_PATH': os.getenv('IFP_INSTALL_PATH'),
                            '$BLOCK': self.block,
                            '$VERSION': self.version,
                            '$FLOW': self.flow,
                            '$VENDOR': self.vendor,
                            '$BRANCH': self.branch,
                            '$TASK': self.task,
                            }

        for key in self.default_var.keys():
            self.env_mapping.setdefault('$%s' % key, self.default_var[key])

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

        row = 0

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
                        value = self.detailed_setting[category][key]
                        item = QStandardItem(value)
                        item.setBackground(QBrush(QColor(100, 149, 237)))

                if value == '':
                    if category in self.default_setting.keys():
                        if key in self.default_setting[category].keys():
                            value = self.default_setting[category][key]
                            item = QStandardItem(value)
                            item.setBackground(QBrush(QColor(255, 255, 255)))

                if value == '':
                    item = QStandardItem(value)
                    item.setBackground(QBrush(QColor(255, 255, 255)))

                self.raw_setting[category][key] = value
                self.tips[row] = self.blank_setting[category][key]
                item.setTextAlignment(Qt.AlignLeft)
                item.setTextAlignment(Qt.AlignVCenter)
                self.setup_model.setItem(row, 1, item)
                row += 1

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

        self.top_layout.addWidget(self.label_env)
        self.top_layout.addWidget(self.env_table)
        self.top_layout.addStretch(1)
        self.top_layout.addWidget(self.label_setup)
        self.top_layout.addWidget(self.setup_table)
        self.top_layout.addWidget(self.button_widget)
        self.top_layout.setStretch(0, 1)
        self.top_layout.setStretch(1, 6)
        self.top_layout.setStretch(3, 1)
        self.top_layout.setStretch(4, 8)
        self.resize(800, 600)
        self.setWindowTitle('Detailed setting for %s' % self.title)
        center(self)

    def show_tips(self, index):
        if index.data() == '' and index.column() == 1:
            QToolTip.showText(QCursor.pos(), self.tips[index.row()])

    def save(self):
        setting = AutoVivification()
        category = ''
        update_flag = 0

        for i in range(self.setup_model.rowCount()):
            item = self.setup_model.index(i, 0).data()
            value = self.setup_model.index(i, 1).data()

            if re.search(r'\*\s+(.*)', item):
                category = re.search(r'\*\s+(.*)', item).group(1)
            else:
                if category in self.detailed_setting.keys():
                    if item in self.detailed_setting[category].keys():
                        update_flag = 1
                        setting[category][item] = value
                        continue

                if not self.raw_setting[category][item] == value:
                    update_flag = 1
                    setting[category][item] = self.setup_model.index(i, 1).data()
                    continue

        if update_flag == 1:
            self.message.emit([self.row, self.column, setting])

        self.close()


class MainWindow3(QMainWindow):
    message = pyqtSignal(list)

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
        self.widgets = {}

        if not self.priority == {}:
            self.flows = []
            self.nums = []

            for i in range(len(list(self.priority.keys()))):
                self.nums.append(str(i + 1))

            for flow in self.priority.keys():
                layout = QHBoxLayout()
                widget = QWidget()
                widget.setLayout(layout)
                edit = QLineEdit()
                edit.setText(flow)
                edit.setEnabled(False)
                edit.setFixedWidth(200)
                box = QComboBox()
                box.addItems(self.nums)
                box.setCurrentText(str(priority[flow]))
                box.setFixedWidth(50)
                layout.addWidget(edit)
                layout.addWidget(box)
                layout.addStretch(1)
                self.top_layout.addWidget(widget)
                self.widgets[flow] = box
        else:
            self.nums = []

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
                self.widgets[self.flows[i]] = box

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

        self.top_layout.addWidget(self.button_widget)

        self.resize(300, 100 * len(self.nums))
        self.setWindowTitle('Set priority for %s/%s' % (self.block, self.version))
        center(self)

    def save(self):
        priority = {}

        for flow in self.widgets.keys():
            priority[flow] = self.widgets[flow].currentText()

        self.message.emit([self.block, self.version, priority])
        self.close()


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
            except:
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
