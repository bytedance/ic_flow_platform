import datetime
import io
import json
import os
import re
import subprocess
import sys
import threading
import traceback
from collections import deque
from dataclasses import dataclass, asdict
from pathlib import Path

import pandas as pd
import psutil
import yaml
import time
import copy
import shutil
import getpass
import graphviz
import functools
from dateutil import parser
from typing import Tuple, Dict, List
from screeninfo import get_monitors

from PyQt5.QtWidgets import QWidget, QMainWindow, QAction, QPushButton, QLabel, QHeaderView, QVBoxLayout, QHBoxLayout, QLineEdit, QTableView, QAbstractItemView, QMenu, QToolTip, QDesktopWidget, QMessageBox, QComboBox, QFileDialog, QApplication, QGridLayout, \
    QTableWidget, QTableWidgetItem, QCompleter, QCheckBox, QStyledItemDelegate, QFormLayout, QScrollArea, QTabWidget, QTextEdit, QPlainTextEdit, QButtonGroup, QRadioButton, QFrame, QSizePolicy, QTextBrowser
from PyQt5.QtGui import QBrush, QFont, QColor, QStandardItem, QStandardItemModel, QCursor, QPalette, QPixmap, QPen, QPainter, QTextFormat, QTextDocument, QTextCursor, QTextCharFormat, QIcon
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QThread, QSize, QRegularExpression, QTimer, QProcess

os.environ['PYTHONUNBUFFERED'] = '1'
sys.path.append(str(os.environ['IFP_INSTALL_PATH']) + '/config')
sys.path.append(str(os.environ['IFP_INSTALL_PATH']) + '/common')
sys.path.append(str(os.environ['IFP_INSTALL_PATH']) + '/bin')
import job_manager
import config
import common
import common_db
import common_pyqt5
import common_lsf
import parse_config
from common import AutoVivification

EDIT_COLOR = QColor(100, 149, 237)


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
                             'LOG': {'example': 'run.log'},
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
                     'DEPENDENCY': {'LICENSE': {'example': '',
                                                'widget_type': 'button'},
                                    'FILE': {'example': '',
                                             'widget_type': 'button'},
                                    }
                     }

    return blank_setting


def custom_format_map(s, d):
    def replace(match):
        var_name = match.group(1)
        return str(d.get(var_name, match.group(0)))

    while True:
        new_s = re.sub(r'\$\{(\w+)\}', replace, s)

        if new_s == s:
            break

        s = new_s
    return s


get_monitors = common_pyqt5.custom_get_monitors  # noqa: F811


class SkipNullsDumper(yaml.SafeDumper):
    def represent_none(self, _):
        return self.represent_scalar('tag:yaml.org,2002:null', '')


SkipNullsDumper.add_representer(type(None), SkipNullsDumper.represent_none)


@dataclass
class TaskRunCache:
    job_id: str = ''
    status: str = ''
    cmd: str = ''
    exit_code: int = None
    cwd: str = ''
    submit_time: str = ''
    run_time: str = ''
    finish_time: str = ''
    message: str = ''
    refresh_interval: str = '3'
    timestamp: int = 0


@dataclass
class TaskLogCache:
    error: str = ''
    warning: str = ''
    search: str = ''
    log: str = ''
    timestamp: int = 0


@dataclass
class TaskCache:
    timestamp: int = 0
    task: str = ''
    flow: str = ''
    version: str = ''
    block: str = ''
    run: TaskRunCache = TaskRunCache()
    log: TaskLogCache = TaskLogCache()


class TaskJobInfo:
    def __init__(self, **kwargs):
        self.id = str(kwargs.get('job_id', ''))
        self.state = str(kwargs.get('status', ''))
        self.exit_code = str(kwargs.get('exit_code', ''))
        self.submit_time = self._time_format(str(kwargs.get('submitted_time', '')))
        self.finish_time = self._time_format(str(kwargs.get('finished_time', '')))
        self.run_time = self._delta_format(str(kwargs.get('submitted_time', '')))
        self.cmd = str(kwargs.get('command', ''))
        self.cwd = str(kwargs.get('cwd', ''))

    @staticmethod
    def _time_format(item: str):
        try:
            format_item = parser.parse(item).replace(year=datetime.datetime.now().year).strftime('%Y/%m/%d %H:%M:%S')
        except Exception:
            format_item = item

        return format_item

    def _delta_format(self, item: str):
        try:
            submit_item = parser.parse(item).replace(year=datetime.datetime.now().year)
        except Exception:
            return ''

        if self.finish_time == '':
            delta = datetime.datetime.now() - submit_item
        else:
            delta = parser.parse(item).replace(year=datetime.datetime.now().year) - submit_item

        return self.get_timedelta_format(delta)

    @staticmethod
    def get_timedelta_format(delta) -> str:
        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{days}days {hours}:{minutes}:{seconds}"


class TaskJobCheckWorker(QThread):
    job_dic = pyqtSignal(TaskJobInfo)

    def __init__(self, job_id: str, job_type: str = 'LSF'):
        super().__init__()
        self.job_id = job_id
        self.job_type = job_type.upper()

    def run(self):
        job_info = self._get_job_info()
        self.job_dic.emit(job_info)

    def _get_job_info(self) -> TaskJobInfo:
        if self.job_type == 'LSF':
            job_info = TaskJobInfo(**common_lsf.get_lsf_bjobs_uf_info('bjobs {} -UF'.format(self.job_id)).get(self.job_id, {}))
        elif self.job_type == 'LOCAL':
            job_info = TaskJobInfo(**self._get_local_job_info(pid=self.job_id))
        else:
            job_info = TaskJobInfo()

        return job_info

    @staticmethod
    def check_job_id(job_id: str) -> Tuple[bool, Dict[str, str]]:
        if my_match := re.match(r'^b:(\d+)$', job_id):
            job_id = my_match.group(1)
            job_type = 'LSF'
        elif my_match := re.match(r'^l:(\d+)$', job_id):
            job_id = my_match.group(1)
            job_type = 'LOCAL'
        else:
            return False, {'job_id': 0, 'job_type': 'NONE'}

        return True, {'job_id': job_id, 'job_type': job_type}

    @staticmethod
    def _get_local_job_info(pid: str) -> dict:
        try:
            process = psutil.Process(int(pid))
            proc_info = {
                'job_id': pid,
                "cwd": process.cwd(),
                "submitted_time": datetime.datetime.fromtimestamp(process.create_time()).strftime('%Y-%m-%d %H:%M:%S'),
                "command": " ".join(process.cmdline()),
                "status": process.status(),
                "exit_code": '',
                "finished_time": '',
            }

            if process.is_running() and process.status() == psutil.STATUS_ZOMBIE:
                proc_info["exit_code"] = process.wait(timeout=0)
                proc_info["end_time"] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            return proc_info

        except psutil.NoSuchProcess:
            try:
                session = common_db.setup_task_job()
                task_job = session.query(common_db.TaskJobs).filter_by(job_id=f'l:{pid}').first()

                if task_job:
                    task_job_dict = {column.name: getattr(task_job, column.name) for column in task_job.__table__.columns}
                    task_job_dict['job_id'] = task_job_dict['job_id'][2:]
                    return task_job_dict
            except Exception:
                pass

            return {"error": "No process found with PID {}".format(pid)}
        except psutil.AccessDenied:
            return {"error": "Permission denied to access process with PID {}".format(pid)}
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def get_lsf_job_status(job_id: str, api_reload: bool = False) -> str:
        try:
            status = os.popen(f'bjobs {job_id} | tail -n 1').read().split()[2]
        except Exception:
            status = ' '

        if status == 'RUN':
            return common.status.running if api_reload else ' '
        elif status == 'DONE':
            return '{} {}'.format(common.TaskAction().run, common.status.passed)
        elif status == 'EXIT':
            return '{} {}'.format(common.TaskAction().run, common.status.failed)
        elif status == 'QUEUE':
            return common.status.queued

        return status

    @staticmethod
    def get_local_job_status(job_id: str) -> str:
        try:
            os.kill(int(job_id), 0)
        except OSError:
            return common.status.passed
        else:
            try:
                pid, status = os.waitpid(int(job_id), os.WNOHANG)
                if pid == 0:
                    return common.status.running
                else:
                    if os.WIFEXITED(status):
                        exit_code = os.WEXITSTATUS(status)
                        return common.status.passed if exit_code == 0 else common.status.failed
                    elif os.WIFSIGNALED(status):
                        return common.status.failed
                    else:
                        return common.status.passed
            except OSError:
                return ''


class UserConfig(QMainWindow):
    save_flag = pyqtSignal(object)
    _instance = None

    def __new__(cls, *args, **kwargs):
        """
        Singleton mode.
        """
        if not cls._instance:
            cls._instance = super(UserConfig, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self, ifp_obj, config_obj: parse_config.Config, config_file, default_yaml, api_yaml):
        super().__init__()

        self.ifp_obj = ifp_obj
        self.config_obj = config_obj
        self.config_file = config_file
        self.default_yaml = default_yaml
        self.api_yaml = api_yaml

        self.default_var = self.config_obj.default_var_setting
        self.default_setting = self.config_obj.default_task_setting
        self.default_dependency_dic = self.config_obj.default_dependency_setting

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
                                      'Task': 3}

        self.block_row_mapping = AutoVivification()
        self.task_row_mapping = AutoVivification()
        self.view_status_dic = {}
        self.task_cache = AutoVivification()
        self.info_cache_path = os.path.join(self.ifp_obj.ifp_cache_dir, 'INFO/{BLOCK}/{VERSION}/{FLOW}/{TASK}/task.json')
        self.history_cache_path = os.path.join(self.ifp_obj.ifp_cache_dir, 'SUMMARY/summary.csv')
        self.history_cache_df = pd.DataFrame(columns=['block', 'version', 'flow', 'task', 'job_id', 'timestamp'])

        self.view_status_dic.setdefault('column', {})

        for header in self.header_column_mapping.keys():
            self.view_status_dic['column'][header] = True

        self.setup_table = DraggableTableView()
        self.setup_table.clicked.connect(self.update_status_bar)
        self.setup_table.setMouseTracking(True)
        self.setup_table.entered.connect(self.show_tips)
        self.setup_model = QStandardItemModel(1, 4)
        self.setup_table.setModel(self.setup_model)
        self.setup_table.verticalHeader().setVisible(False)
        # Show Floating
        # self.setup_table.horizontalHeader().hide()

        self.config_path_widget = QWidget()
        self.config_path_layout = QHBoxLayout()
        self.config_path_widget.setLayout(self.config_path_layout)
        self.config_path_label = QLabel('Config file')
        self.config_path_edit = QLineEdit()
        self.config_path_edit.setText(self.config_file)
        self.config_path_edit.setEnabled(False)

        self.ifp_env_setting = AutoVivification()
        self.blank_setting = parsing_blank_setting()
        self.state = AutoVivification()
        self.version_state = AutoVivification()

        self.dependency_priority = self.config_obj.real_task_dependency
        self.task_setting = self.config_obj.user_task_setting
        self.raw_setting = self.config_obj.user_config_dic
        self.user_var = self.config_obj.user_var_setting
        self.project = self.config_obj.PROJECT
        self.group = self.config_obj.GROUP

        self.dependency_chart = AutoVivification()
        self.item_chart_dic = {}
        self.final_setting = {}
        self.table_info = AutoVivification()
        self.span_info = AutoVivification()

        self.current_selected_row = None
        self.current_selected_column = None
        self.current_selected_block = None
        self.current_selected_version = None
        self.current_selected_flow = None
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
        self.ifp_monitor.pnum.connect(self.ifp_obj.update_pnum)
        self.ifp_monitor.config_update.connect(self.ifp_obj.update_status_bar_tip)
        self.thread.started.connect(self.ifp_monitor.run)
        self.thread.start()
        self.tab_name = 'CONFIG'

    def init_ui(self):
        self.config_path_layout.addWidget(self.config_path_label)
        self.config_path_layout.addWidget(self.config_path_edit)
        header = ['Block', 'Version', 'Flow', 'Task']

        self.setup_model.setHorizontalHeaderLabels(header)
        self.setup_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.setup_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.setup_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.setup_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)

        self.setup_table.setShowGrid(True)
        self.setup_table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        self.setup_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.setup_table.customContextMenuRequested.connect(self.generate_menu)
        self.setup_table.setItemDelegate(common_pyqt5.CustomDelegate(wrap_columns=[0, 1], table_view=self.setup_table))
        self.setup_table.doubleClicked.connect(self.generate_double_clicked)

        self.top_layout.addWidget(self.config_path_widget)

        container = QWidget()
        main_layout = QGridLayout()
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        main_layout.addWidget(self.setup_table, 1, 0)
        container.setLayout(main_layout)

        self.top_layout.addWidget(container)

        return self.top_widget

    def disable_gui(self):
        self.disable_gui_flag = True

    def enable_gui(self):
        self.disable_gui_flag = False

    def check_task_items(self, block: str, version: str, flow: str, task: str, task_dic: dict):
        invalid_dic = {}
        var_dic = {'BLOCK': block,
                   'VERSION': version,
                   'FLOW': flow,
                   'TASK': task}

        for action2 in task_dic:
            for item in task_dic[action2]:
                if item == 'PATH':
                    # PATH must exist
                    item_path = common.expand_var(str(task_dic[action2][item]), ifp_var_dic=self.config_obj.var_dic, **var_dic)
                    if not os.path.isdir(item_path):
                        invalid_dic.setdefault(action2, []).append(item)

                elif item == 'RUN_METHOD':
                    # xterm must be used with -e
                    run_method = common.expand_var(str(task_dic[action2][item]), ifp_var_dic=self.config_obj.var_dic, **var_dic)

                    if re.search(r"xterm(?!\s+-e)", run_method):
                        invalid_dic.setdefault(action2, []).append(item)

                    # Do not allow '/" marks around bsub command
                    if re.search(r"(\'\s*bsub.+\')|(\"\s*bsub.+\")", str(run_method)):
                        invalid_dic.setdefault(action2, []).append(item)

        return invalid_dic

    def update_status_bar(self, index):
        self.current_selected_row = index.row()
        self.current_selected_column = index.column()

        self.current_selected_block = self.setup_model.index(self.current_selected_row, 0).data()
        self.current_selected_version = self.setup_model.index(self.current_selected_row, 1).data()
        self.current_selected_flow = self.setup_model.index(self.current_selected_row, 2).data()
        self.current_selected_task = self.setup_model.index(self.current_selected_row, 3).data()

        self.ifp_obj.memos_logger.log(f'Select Config Table Item -> ({self.current_selected_block}, {self.current_selected_version}, {self.current_selected_flow}, {self.current_selected_task})')
        all_items = [self.current_selected_block, self.current_selected_version, self.current_selected_flow, self.current_selected_task]
        message_items = []

        for i in range(self.current_selected_column + 1):
            message_items.append(all_items[i])

        self.ifp_obj.update_status_bar(' -> '.join(message_items))

    def show_tips(self, index):
        desktop = QApplication.desktop()
        screen_num = desktop.screenNumber(QCursor.pos())
        screen_rect = desktop.screenGeometry(screen_num)

        # if not index.column() == 5:
        if not index.column() == 3:
            QToolTip.showText(QCursor.pos(), self.setup_model.index(index.row(), index.column()).data(), self.setup_table, screen_rect, 10000)

    def update_config_table_row_visible(self, view_name, item_text, item_select_status):
        if view_name == 'column':
            if item_text not in self.header_column_mapping.keys():
                return

            if item_select_status:
                self.setup_table.showColumn(self.header_column_mapping[item_text])

            else:
                self.setup_table.hideColumn(self.header_column_mapping[item_text])
        elif view_name == 'block':
            if item_select_status:
                exclude_visible_row_list = []

                for row in self.block_row_mapping[item_text]:
                    if row not in exclude_visible_row_list:
                        self.setup_table.showRow(row)
            else:
                for row in self.block_row_mapping[item_text]:
                    self.setup_table.hideRow(row)

            self.ifp_obj.top_tab.setCurrentIndex(0)
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
                        self.setup_table.showRow(row)
            else:
                for row in self.task_row_mapping[item_text]:
                    self.setup_table.hideRow(row)

    def apply_config_view_status(self, status):
        for view_name, view_status in status.items():
            for item_name, item_status in view_status.items():
                self.update_config_table_row_visible(view_name=view_name, item_text=item_name, item_select_status=item_status)

        self.view_status_dic = status
        self.ifp_obj.top_tab.setCurrentIndex(0)

    def update_state(self, state):
        self.state = state

        for i in range(self.setup_model.rowCount()):
            block = self.setup_model.index(i, 0).data()
            version = self.setup_model.index(i, 1).data()
            flow = self.setup_model.index(i, 2).data()
            task = self.setup_model.index(i, 3).data()

            item = self.setup_model.item(i, 3)
            item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

            if None in [block, version, flow, task]:
                item.setBackground(QBrush(QColor(255, 255, 255)))
            elif self.state[block][version][flow][task] == 'user':
                item.setForeground(QBrush(EDIT_COLOR))
                item.setFont(QFont('Calibri', 10, 500))
            elif self.state[block][version][flow][task] == 'default':
                item.setBackground(QBrush(QColor(255, 255, 255)))
            elif self.state[block][version][flow][task] == 'blank':
                item.setForeground(QBrush(QColor(255, 0, 0)))
                item.setFont(QFont('Calibri', 10, 500))

            self.setup_model.setItem(i, 3, item)

        self.setup_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setup_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)

    """
    1. Draw table by following dict
       a. self.task_setting (GUI setting) or self.raw_setting (load ifp.cfg.yaml)
    2. Parsing self.detailed_setting[block][block_version][flow][vendor][task_branch][task] when load ifp.cfg.yaml
    """

    def draw_table(self, setting):
        self.setup_model.setRowCount(0)
        self.span_info = AutoVivification()
        self.span_info_dic = {}
        self.table_info = AutoVivification()
        row = 0

        if setting is None:
            return

        for block in setting.keys():
            block_start_line = row

            for version in setting[block].keys():

                # First time load ifp.cfg.yaml, the version may be IFP_v1.0(RUN_ORDER=gen_dir,syn,fv|sta), draw table by IFP_v1.0
                # Other scenario, the version is IFP_v1.0 without RUN_ORDER information
                # So setting[block] must keep [version], others use [block_version] which do not have RUN_ORDER information

                version_start_line = row

                for flow in setting[block][version].keys():

                    flow_start_line = row

                    for task in setting[block][version][flow].keys():
                        self.setup_model.setItem(row, 0, QStandardItem(block))
                        self.setup_model.setItem(row, 1, QStandardItem(version))
                        self.setup_model.setItem(row, 2, QStandardItem(flow))
                        self.setup_model.setItem(row, 3, QStandardItem(task))

                        self.table_info[row] = [block, version, flow, task]
                        self.span_info_dic[(row, 2)] = flow_start_line
                        self.span_info_dic[(row, 1)] = version_start_line
                        self.span_info_dic[(row, 0)] = block_start_line
                        row += 1

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
    2. Update self.task_setting[block][version][flow][vendor][branch][task]
    """

    def parsing_user_setting(self):
        self.view_status_dic['block'] = {}
        self.view_status_dic['task'] = {}
        self.block_row_mapping = AutoVivification()
        self.task_row_mapping = AutoVivification()

        for i in range(self.setup_model.rowCount()):
            block = self.setup_model.index(i, 0).data()
            version = self.setup_model.index(i, 1).data()
            flow = self.setup_model.index(i, 2).data()
            task = self.setup_model.index(i, 3).data()

            self.view_status_dic['block'][block] = True
            self.view_status_dic['task'][task] = True

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
                self.task_row_mapping[task] = [i]
            else:
                self.task_row_mapping[task].append(i)

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

            # self.task_setting[block][version][flow][task] = {}

    '''
    1. Parsing GUI info by def parsing_user_setting
    2. Delete repeated task setting between default.yaml and ifp.cfg.yaml
    3. Save final setting to self.final_setting[block][version][flow][vendor][branch][task][category][item]
    '''

    def parsing_final_setting(self):
        self.parsing_user_setting()
        self.final_setting['VAR'] = {}
        default_setting_tmp = copy.deepcopy(self.config_obj.default_task_setting)

        for key in self.user_var.keys():
            self.final_setting['VAR'][key] = self.user_var[key]

        self.final_setting['BLOCK'] = {}

        for block in self.task_setting.keys():
            if block == '' or block is None:
                continue

            self.final_setting['BLOCK'].setdefault(block, {})

            for version in self.task_setting[block].keys():
                if version == '':
                    common_pyqt5.Dialog('WARNING', 'Can not save your setting to config file due to empty version!', QMessageBox.Warning)
                    return

                self.final_setting['BLOCK'][block].setdefault(version, {})

                for flow in self.task_setting[block][version].keys():
                    if flow == '':
                        common_pyqt5.Dialog('WARNING', 'Can not save your setting to config file due to empty flow!', QMessageBox.Warning)
                        return

                    self.final_setting['BLOCK'][block][version].setdefault(flow, {})
                    # task_list = list(set(self.config_obj.default_dependency_setting.keys()).union(self.dependency_priority[block][version].keys()))
                    task_list = list(self.dependency_priority[block][version].keys())

                    for task in self.task_setting[block][version][flow].keys():
                        if task == '':
                            common_pyqt5.Dialog('WARNING', 'Can not save your setting to config file due to empty task!', QMessageBox.Warning)
                            return

                        self.final_setting['BLOCK'][block][version][flow].setdefault(task, {})

                        task_dependency = self.dependency_priority.get(block, {}).get(version, {}).get(task, '')
                        default_dependency = self.default_dependency_dic.get(task, '')
                        task_dependency = WindowForDependency.clean_dependency(item_list=task_list, item=task, dependency=task_dependency)
                        default_dependency = WindowForDependency.clean_dependency(item_list=task_list, item=task, dependency=default_dependency)

                        if isinstance(task_dependency, str) and isinstance(default_dependency, str) and default_dependency.strip() != task_dependency.strip():
                            task_dependency = WindowForDependency.clean_dependency(item_list=task_list, item=task, dependency=task_dependency)
                            self.final_setting['BLOCK'][block][version][flow][task].update({'RUN_AFTER': {'TASK': task_dependency}})

                        if not self.task_setting[block][version][flow][task] == {}:
                            for category in self.task_setting[block][version][flow][task].keys():
                                if category == 'RUN_AFTER':
                                    continue

                                if category == 'RUN_MODE':
                                    self.final_setting['BLOCK'][block][version][flow][task][category] = self.task_setting[block][version][flow][task][category]

                                if not self.task_setting[block][version][flow][task][category]:
                                    continue

                                if not isinstance(self.task_setting[block][version][flow][task][category], dict):
                                    continue

                                for item in self.task_setting[block][version][flow][task][category].keys():
                                    if default_setting_tmp.get(task, {}).get(category, {}).get(item) is not None:
                                        if default_setting_tmp[task][category][item] == self.task_setting[block][version][flow][task][category][item]:
                                            continue
                                    else:
                                        if not self.task_setting.get(block, {}).get(version, {}).get(flow, {}).get(task, {}).get(category, {}).get(item):
                                            continue

                                    self.final_setting['BLOCK'][block][version][flow][task].setdefault(category, {})
                                    self.final_setting['BLOCK'][block][version][flow][task][category][item] = self.task_setting[block][version][flow][task][category][item]

    """
    1. Load ifp.cfg.yaml
    2. Draw table by raw setting
    3. Parsing GUI setting and check if any default task setting that not defined in default.yaml and ifp.cfg.yaml
    4. Update ifp.cfg.yaml and reload
    """

    def load(self):
        self.default_var = self.config_obj.default_var_setting
        self.default_setting = self.config_obj.default_task_setting
        self.default_dependency_dic = self.config_obj.default_dependency_setting
        self.dependency_priority = self.config_obj.real_task_dependency
        self.task_setting = self.config_obj.user_task_setting
        self.raw_setting = self.config_obj.user_config_dic
        self.user_var = self.config_obj.user_var_setting
        self.project = self.config_obj.PROJECT
        self.group = self.config_obj.GROUP

        self.draw_table(self.task_setting)
        self.parsing_user_setting()
        self.ifp_monitor.wake_up = True
        self._catch_task_status()

    def _catch_task_status(self):
        for block in self.ifp_obj.job_manager.all_tasks:
            for version in self.ifp_obj.job_manager.all_tasks[block]:
                for flow in self.ifp_obj.job_manager.all_tasks[block][version]:
                    for task in self.ifp_obj.job_manager.all_tasks[block][version][flow]:
                        task_obj = self.ifp_obj.job_manager.all_tasks[block][version][flow][task]
                        task_obj.set_one_jobid_signal.connect(self._update_task_cache)

    def save(self, *args):
        self.parsing_final_setting()

        if len(args) == 2:
            tag = args[0]
            api_yaml = args[1]

            if tag == 'api' and api_yaml:
                self.ifp_obj.api_yaml = api_yaml

        self.save_flag.emit(True)

    def generate_menu(self, pos):
        self.api_yaml = self.ifp_obj.config_obj.api_yaml
        self.user_api = common.parse_user_api(self.api_yaml)
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
            self.current_selected_task = None
        else:
            self.current_selected_block = self.setup_model.index(self.current_selected_row, 0).data()
            self.current_selected_version = self.setup_model.index(self.current_selected_row, 1).data()
            self.current_selected_flow = self.setup_model.index(self.current_selected_row, 2).data()
            self.current_selected_task = self.setup_model.index(self.current_selected_row, 3).data()

        self.ifp_obj.memos_logger.log(f'Right Click Config Table Item -> ({self.current_selected_block}, {self.current_selected_version}, {self.current_selected_flow}, {self.current_selected_task})')

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
                common.add_api_menu(self.ifp_obj, self.user_api, menu, project=self.project, group=self.group, tab='CONFIG', column='BLOCK', var_dic={'BLOCK': self.current_selected_block})

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
                common.add_api_menu(self.ifp_obj, self.user_api, menu, project=self.project, group=self.group, tab='CONFIG', column='VERSION', var_dic={'BLOCK': self.current_selected_block, 'VERSION': self.current_selected_version})

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
                common.add_api_menu(self.ifp_obj, self.user_api, menu, project=self.project, group=self.group, tab='CONFIG', column='FLOW', var_dic={'BLOCK': self.current_selected_block, 'VERSION': self.current_selected_version, 'FLOW': self.current_selected_flow})
            elif self.current_selected_column == 3:
                action1 = QAction('Task information')
                status = self.config_obj.get_task(self.current_selected_block, self.current_selected_version, self.current_selected_flow, self.current_selected_task).RunStatus
                read_only = True if self.disable_gui_flag and status == common.status.running else False

                if self.disable_gui_flag:
                    action1.triggered.connect(lambda: self.edit_detailed_config(read_only=read_only,
                                                                                block=self.current_selected_block,
                                                                                version=self.current_selected_version,
                                                                                flow=self.current_selected_flow,
                                                                                task=self.current_selected_task))
                else:
                    action1.triggered.connect(lambda: self.edit_detailed_config(read_only=read_only,
                                                                                block=self.current_selected_block,
                                                                                version=self.current_selected_version,
                                                                                flow=self.current_selected_flow,
                                                                                task=self.current_selected_task))

                task_obj_list = self.config_obj.get_block_task_list(block=self.current_selected_block)
                running_task = False

                for task_obj in task_obj_list:
                    if task_obj.RunStatus == common.status.running:
                        running_task = True
                        break

                menu.addAction(action1)
                menu.addSeparator()
                action3 = QAction('Add task')
                action3.triggered.connect(lambda: self.add_more_item('task'))
                action3.setDisabled(running_task)
                menu.addAction(action3)
                action4 = QAction('Copy task')
                action4.triggered.connect(lambda: self.copy_current_item('task'))
                action4.setDisabled(running_task)
                menu.addAction(action4)

                if len(selected_rows[5]) > 1:
                    action2 = QAction('Remove tasks')
                else:
                    action2 = QAction('Remove task')

                action2.triggered.connect(lambda: self.remove_current_item('task'))
                action2.setDisabled(running_task)
                menu.addAction(action2)
                common.add_api_menu(self.ifp_obj,
                                    self.user_api,
                                    menu,
                                    project=self.project,
                                    group=self.group,
                                    tab='CONFIG',
                                    column='TASK',
                                    var_dic={'BLOCK': self.current_selected_block,
                                             'VERSION': self.current_selected_version,
                                             'FLOW': self.current_selected_flow,
                                             'TASK': self.current_selected_task})
        self.ifp_obj.memos_logger.setup_menu_memos(menu, 'Config Table Menu')
        menu.exec_(self.setup_table.mapToGlobal(pos))

    def generate_double_clicked(self, item):
        row = item.row()
        column = item.column()

        if row is None or column is None:
            return
        elif column != 3:
            return
        else:
            block = self.setup_model.index(row, 0).data()
            version = self.setup_model.index(row, 1).data()
            flow = self.setup_model.index(row, 2).data()
            task = self.setup_model.index(row, 3).data()
            self.ifp_obj.memos_logger.log(f'DoubleClick Config Table Item -> ({block}, {version}, {flow}, {task})')

            self.edit_detailed_config(read_only=True if self.disable_gui_flag else False,
                                      block=block,
                                      version=version,
                                      flow=flow,
                                      task=task)

    def clean_dict_for_empty_key(self):
        raw_setting = copy.deepcopy(self.task_setting)

        for block in raw_setting.keys():
            if raw_setting[block] == {}:
                del self.task_setting[block]
                del self.view_status_dic['block'][block]
                del self.ifp_obj.view_status_dic['block'][block]
            else:
                for version in raw_setting[block].keys():
                    if raw_setting[block][version] == {}:
                        del self.task_setting[block][version]

                        if self.task_setting[block] == {}:
                            del self.task_setting[block]
                    else:
                        for flow in raw_setting[block][version].keys():
                            if raw_setting[block][version][flow] == {}:
                                del self.task_setting[block][version][flow]

                                if self.task_setting[block][version] == {}:
                                    del self.task_setting[block][version]

                                    if self.task_setting[block] == {}:
                                        del self.task_setting[block]

    def clean_dependency_dict_for_empty_key(self):
        raw_dependency = copy.deepcopy(self.dependency_priority)

        for block in raw_dependency.keys():
            if not raw_dependency[block]:
                del self.dependency_priority[block]
            else:
                for version in raw_dependency[block].keys():
                    if not raw_dependency[block][version]:
                        del self.dependency_priority[block][version]

    def add_more_item(self, item):
        self.parsing_user_setting()
        self.child = WindowForAddItems(item,
                                       self.task_setting,
                                       self.task_setting,
                                       self.config_obj.default_task_setting,
                                       default_flow_setting=self.config_obj.default_flow_setting,
                                       block=self.current_selected_block,
                                       version=self.current_selected_version,
                                       flow=self.current_selected_flow,
                                       task=self.current_selected_task,
                                       auto_import_tasks=self.ifp_obj.auto_import_tasks,
                                       dependency_dic=self.dependency_priority,
                                       default_dependency_dic=self.config_obj.default_dependency_setting)
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
            selected_block_list = []

            for row in selected_rows[0]:
                block = self.setup_model.index(row, 0).data()

                if block not in selected_block_list:
                    selected_block_list.append(block)

                del self.task_setting[block]
                del self.dependency_priority[block]

            for block in selected_block_list:
                del self.view_status_dic['block'][block]
                del self.ifp_obj.view_status_dic['block'][block]

        if item == 'version':
            for row in selected_rows[1]:
                block = self.setup_model.index(row, 0).data()
                version = self.setup_model.index(row, 1).data()
                del self.task_setting[block][version]
                del self.dependency_priority[block][version]

        if item == 'flow':
            for row in selected_rows[2]:
                block = self.setup_model.index(row, 0).data()
                version = self.setup_model.index(row, 1).data()
                flow = self.setup_model.index(row, 2).data()
                del self.task_setting[block][version][flow]
        if item == 'task':
            for row in selected_rows[3]:
                block = self.setup_model.index(row, 0).data()
                version = self.setup_model.index(row, 1).data()
                flow = self.setup_model.index(row, 2).data()
                task = self.setup_model.index(row, 3).data()
                del self.task_setting[block][version][flow][task]
                del self.dependency_priority[block][version][task]
                del self.view_status_dic['task'][task]
                del self.ifp_obj.view_status_dic['task'][task]

        self.clean_dict_for_empty_key()
        self.clean_dependency_dict_for_empty_key()
        self.draw_table(self.task_setting)
        self.save()

    @staticmethod
    def remove_dependency_specific_item(dependency, remove_item):
        if dependency.find(remove_item) == -1:
            new_dependency = dependency
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

        self.child = WindowForCopyItems(item,
                                        self.task_setting,
                                        self.task_setting,
                                        block=self.current_selected_block,
                                        version=self.current_selected_version,
                                        flow=self.current_selected_flow,
                                        task=self.current_selected_task,
                                        dependency_dic=self.dependency_priority)

        self.child.setWindowModality(Qt.ApplicationModal)
        self.child.message.connect(self.update_table_after_copy)
        self.child.save_signal.connect(self.save)
        self.child.show()

    def update_table_after_copy(self, info):
        copy_item = info[0]
        self.task_setting = info[-1]
        default_setting_tmp = copy.deepcopy(self.config_obj.default_task_setting)
        self.draw_table(self.task_setting)

        if copy_item == 'task':
            # Copy all default setting of raw task to new task as user defined setting if new task is not a default task
            new_task = info[1]
            self.task_setting[self.current_selected_block][self.current_selected_version][self.current_selected_flow][new_task] = copy.deepcopy(self.task_setting[self.current_selected_block][self.current_selected_version][self.current_selected_flow][self.current_selected_task])
            if new_task not in default_setting_tmp.keys():
                for category in default_setting_tmp[self.current_selected_task].keys():
                    if category not in self.task_setting[self.current_selected_block][self.current_selected_version][self.current_selected_flow][new_task].keys():
                        self.task_setting[self.current_selected_block][self.current_selected_version][self.current_selected_flow][new_task].setdefault(category, {})
                        for item in default_setting_tmp[self.current_selected_task][category].keys():
                            if item not in self.task_setting[self.current_selected_block][self.current_selected_version][self.current_selected_flow][new_task][category].keys():
                                self.task_setting[self.current_selected_block][self.current_selected_version][self.current_selected_flow][new_task][category][item] = default_setting_tmp[self.current_selected_task][category][item]

    def update_table_after_add(self, info):
        self.task_setting = copy.deepcopy(info[0])
        self.dependency_priority = info[-1]
        add_item = info[1]

        if add_item == 'task':
            for block in self.task_setting:
                for version in self.task_setting[block]:
                    for flow in self.task_setting[block][version]:
                        for task in self.task_setting[block][version][flow]:
                            if not self.task_setting.get(block, {}).get(version, {}).get(flow, {}).get(task):
                                self.task_setting[block][version][flow][task] = {}

        self.draw_table(self.task_setting)

    def edit_detailed_config(self,
                             read_only=False,
                             block=None,
                             version=None,
                             flow=None,
                             task=None):
        status = self.ifp_obj.job_manager.all_tasks[block][version][flow][task].status
        read_only = True if read_only and status == common.status.running else False
        self.ifp_obj.task_information_show = True
        self.child = WindowForTaskInformation(task_obj=self.ifp_obj.job_manager.all_tasks[block][version][flow][task], user_config_obj=self, read_only=read_only)
        self.child.setWindowModality(Qt.ApplicationModal)
        self.child.detailed_task_window.message.connect(self.update_detailed_setting)
        self.child.show_sig.connect(self.ifp_obj.change_task_information_show_status)
        self.child.show()

    def update_detailed_setting(self, value):
        setting = value[0]
        new_task = value[1]
        new_setting = copy.deepcopy(setting)
        default_setting_tmp = copy.deepcopy(self.config_obj.default_task_setting)

        if not self.current_selected_task == new_task:
            if self.current_selected_task in self.task_setting[self.current_selected_block][self.current_selected_version][self.current_selected_flow].keys():
                del self.task_setting[self.current_selected_block][self.current_selected_version][self.current_selected_flow][self.current_selected_task]

                self.task_setting[self.current_selected_block][self.current_selected_version][self.current_selected_flow][new_task] = {}

                self.dependency_priority[self.current_selected_block][self.current_selected_version][new_task] = ''
                del self.dependency_priority[self.current_selected_block][self.current_selected_version][self.current_selected_task]
                common_pyqt5.Dialog(title='Warning', info='Task %s dependency have been reset to " "!' % new_task, icon=QMessageBox.Warning)

        for category in setting.keys():
            if not isinstance(setting[category], dict):
                new_setting[category] = setting[category]
                continue

            for item in setting[category].keys():
                if default_setting_tmp.get(new_task, {}).get(category, {}).get(item) is not None:
                    if default_setting_tmp[new_task][category][item] == setting[category][item]:
                        del new_setting[category][item]

            for item in setting[category].keys():
                if setting.get(category, {}).get(item) is not None and setting[category][item] == self.config_obj.default_task_setting.get(category, {}).get(item):
                    del new_setting[category][item]

            if len(new_setting[category].keys()) == 0:
                del new_setting[category]

        self.task_setting[self.current_selected_block][self.current_selected_version][self.current_selected_flow][new_task] = copy.deepcopy(new_setting)

        if not self.current_selected_task == new_task:
            self.current_selected_task = new_task
            self.draw_table(self.task_setting)

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
                    if key in self.default_var and value == self.default_var:
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
                af.write(yaml.dump(api_dic, allow_unicode=True, Dumper=SkipNullsDumper, sort_keys=False))

            self.save('api', api_yaml)

    def exchange_task(self, info):
        block = info[0]
        version = info[1]
        flow = info[2]
        raw_task = info[3]
        new_task = info[4]

        tasks = list(self.task_setting[block][version][flow].keys())
        new_tasks = []
        for task in tasks:
            del self.task_setting[block][version][flow][task]

            if task == raw_task:
                new_tasks.append(new_task)
            elif task == new_task:
                new_tasks.append(raw_task)
            else:
                new_tasks.append(task)

        for task in new_tasks:
            self.task_setting[block][version][flow][task] = ''

        self.draw_table(self.task_setting)
        self.save()

    def _update_task_cache(self, block: str, version: str, flow: str, task: str, _: str, job_id: str):
        check, job_dic = TaskJobCheckWorker.check_job_id(job_id=job_id)

        if job_dic.get('job_type') == 'LSF':
            self.history_cache_df.loc[len(self.history_cache_df)] = [block, version, flow, task, job_dic.get('job_id', ''), int(datetime.datetime.now().timestamp())]

    def save_cache(self):
        if not os.path.exists(self.history_cache_path):
            os.makedirs(os.path.dirname(self.history_cache_path), exist_ok=True)
            self.history_cache_df.to_csv(self.history_cache_path, index=False)
        else:
            self.history_cache_df.to_csv(self.history_cache_path, index=False, header=False, mode='a+')


class IFPMonitor(QObject):
    message = pyqtSignal(dict)
    pnum = pyqtSignal(int)
    config_update = pyqtSignal()

    def __init__(self, mainwindow):
        super(QObject, self).__init__()
        self.mainwindow = mainwindow
        self.task_setting = AutoVivification()
        self.detailed_setting = AutoVivification()
        self.default_setting = AutoVivification()
        self.state = AutoVivification()
        self.stop_event = threading.Event()
        self.wake_up = False

    def run(self):
        while not self.stop_event.is_set():
            try:
                default_file_mtime = None
                api_file_mtime = None
                update_flag = False

                if os.path.exists(self.mainwindow.config_obj.default_config_file):
                    default_file_mtime = datetime.datetime.fromtimestamp(os.path.getmtime(self.mainwindow.config_obj.default_config_file))

                if os.path.exists(self.mainwindow.config_obj.api_yaml):
                    api_file_mtime = datetime.datetime.fromtimestamp(os.path.getmtime(self.mainwindow.config_obj.api_yaml))

                if default_file_mtime is not None and default_file_mtime > self.mainwindow.config_obj.default_config_file_mtime:
                    update_flag = True

                if api_file_mtime is not None and api_file_mtime > self.mainwindow.config_obj.api_file_mtime:
                    update_flag = True

                if update_flag:
                    self.config_update.emit()

            except Exception:
                pass

            try:
                result = subprocess.run(
                    "ps -U $(id -u) --no-headers | wc -l",
                    shell=True,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    timeout=2
                )
                current_pnum = int(result.stdout.strip())
                self.pnum.emit(current_pnum)
            except Exception:
                self.pnum.emit(-1)

            if self.wake_up:
                self.task_setting = copy.deepcopy(self.mainwindow.task_setting)
                self.detailed_setting = copy.deepcopy(self.mainwindow.task_setting)
                self.default_setting = copy.deepcopy(self.mainwindow.default_setting)

                for block in self.task_setting.keys():
                    for version in self.task_setting[block].keys():
                        for flow in self.task_setting[block][version].keys():
                            for task in self.task_setting[block][version][flow].keys():
                                if self.detailed_setting[block][version][flow][task]:
                                    self.state[block][version][flow][task] = 'user'

                                    if len(self.mainwindow.check_task_items(block, version, flow, task, self.detailed_setting[block][version][flow][task])):
                                        self.state[block][version][flow][task] = 'blank'

                                    continue

                                if task in self.default_setting.keys():
                                    self.state[block][version][flow][task] = 'default'

                                    continue

                                self.state[block][version][flow][task] = 'blank'

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
                 default_flow_setting=None,
                 block=None,
                 version=None,
                 flow=None,
                 task=None,
                 auto_import_tasks=True,
                 dependency_dic=None,
                 default_dependency_dic=None):
        super().__init__()
        self.item = item
        self.task_setting = user_input
        self.detailed_setting = detailed_setting
        self.default_setting = default_setting
        self.default_flow_setting = default_flow_setting
        self.block = block
        self.version = version
        self.flow = flow
        self.task = task
        self.dependency_dic = dependency_dic
        self.default_dependency_dic = default_dependency_dic
        self.auto_import_tasks = auto_import_tasks
        self.current_selected_row = None
        self.current_selected_column = None

        if len(list(self.default_setting.keys())) == 0:
            self.auto_import_tasks = False

        self.top_widget = QWidget()
        self.top_layout = QVBoxLayout()
        self.top_widget.setLayout(self.top_layout)
        self.setCentralWidget(self.top_widget)

        self.table = QTableView()
        self.table_model = QStandardItemModel(1, 4)
        self.span_info = {}
        self.table.setModel(self.table_model)
        header = ['Block', 'Version', 'Flow', 'Task']
        self.table_model.setHorizontalHeaderLabels(header)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.setStyleSheet('font-family : calibri; font-size : 15px')
        self.table.setShowGrid(True)
        self.table.horizontalHeader().sectionClicked.connect(self.title_click_behavior)
        self.table.clicked.connect(self.item_click_behavior)

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

        if self.auto_import_tasks and self.item in ['block', 'version', 'flow']:
            self.resize(1200, 500)
        else:
            self.resize(1200, 100)

        self.top_layout.addWidget(self.table)
        self.top_layout.addWidget(self.button_widget)

        self.draw_table(self.table, self.table_model, editable=True)

        self.setWindowTitle('Add new %s' % self.item)
        center(self)

    def item_click_behavior(self, index):
        if index is not None:

            self.current_selected_row = index.row()
            self.current_selected_column = index.column()
            item = self.table_model.itemFromIndex(index)

            if self.current_selected_column == 2 and self.auto_import_tasks and len(list(self.default_flow_setting.keys())) > 0:
                for count in range(self.current_selected_row, self.current_selected_row + self.table.rowSpan(self.current_selected_row, self.current_selected_column)):

                    task_item = self.table_model.item(count, 3)

                    if not task_item:
                        continue

                    if item.checkState():
                        task_item.setCheckState(Qt.Checked)
                    else:
                        task_item.setCheckState(Qt.Unchecked)

    def title_click_behavior(self, index):
        if not self.auto_import_tasks:
            return

        if index not in [2]:
            return

        unselected_flag = False

        for i in range(self.table_model.rowCount()):
            if self.table_model.item(i, index):
                if not self.table_model.item(i, index).checkState() == Qt.Checked:
                    unselected_flag = True
                    break

        for i in range(self.table_model.rowCount()):
            if self.table_model.item(i, index):
                if unselected_flag:
                    self.table_model.item(i, index).setCheckState(Qt.Checked)
                else:
                    self.table_model.item(i, index).setCheckState(Qt.Unchecked)

                if index == 2:
                    self.item_click_behavior(self.table_model.index(i, index))

    def draw_table(self, table, model, editable=False):
        model.setRowCount(0)
        if self.item == 'block':
            model.setRowCount(1)

        if self.item in ['version', 'flow', 'task']:
            block_item = QStandardItem(self.block)
            block_item.setFlags(Qt.ItemIsEditable)
            model.setItem(0, 0, block_item)

        if self.item in ['flow', 'task']:
            version_item = QStandardItem(self.version)
            version_item.setFlags(Qt.ItemIsEditable)
            model.setItem(0, 1, version_item)

        if self.item in ['task']:
            flow_item = QStandardItem(self.flow)
            flow_item.setFlags(Qt.ItemIsEditable)
            model.setItem(0, 2, flow_item)

        row = 0

        if self.item in ['block', 'version', 'flow'] and self.auto_import_tasks:
            if len(list(self.default_flow_setting.keys())) > 0:
                for flow in self.default_flow_setting.keys():
                    flow_start_line = row
                    flow_item = QStandardItem(flow)
                    flow_item.setCheckable(True)
                    flow_item.setCheckState(Qt.Checked)
                    model.setItem(row, 2, flow_item)

                    for task in self.default_flow_setting[flow]:
                        if task not in self.default_setting.keys():
                            continue
                        else:
                            task_item = QStandardItem(task)
                            task_item.setCheckable(True)
                            task_item.setCheckState(Qt.Checked)
                            task_item.setFlags(Qt.ItemIsEditable)
                            model.setItem(row, 3, task_item)
                            row += 1

                    flow_end_line = row

                    if flow_end_line - flow_start_line > 1:
                        table.setSpan(flow_start_line, 2, flow_end_line - flow_start_line, 1)
                        self.span_info[(flow_start_line, 2)] = (flow_end_line - flow_start_line, 1)
            else:
                flow_start_line = row
                flow_item = QStandardItem('')
                model.setItem(row, 2, flow_item)

                for task in self.default_setting.keys():
                    task_item = QStandardItem(task)
                    task_item.setCheckable(True)
                    task_item.setCheckState(Qt.Checked)
                    model.setItem(row, 3, task_item)
                    row += 1

                flow_end_line = row

                if flow_end_line - flow_start_line > 1:
                    table.setSpan(flow_start_line, 2, flow_end_line - flow_start_line, 1)
                    self.span_info[(flow_start_line, flow_end_line)] = (flow_end_line - flow_start_line, 1)

            if row > 1:
                table.setSpan(0, 0, row, 1)
                table.setSpan(0, 1, row, 1)
                self.span_info[(0, 0)] = (row, 1)
                self.span_info[(0, 1)] = (row, 1)

        if self.item == 'task' and self.auto_import_tasks:
            qitem = QStandardItem('')
            model.setItem(0, 3, qitem)
            index = model.indexFromItem(qitem)
            lineedit = QLineEdit2(values=self.default_setting.keys())
            table.setIndexWidget(index, lineedit)

    def save(self):
        self.save_button.setEnabled(False)
        block = None
        version = None
        flow = None
        raw_user_input = copy.deepcopy(self.task_setting)
        raw_tasks = []

        if self.item in ['flow', 'task']:
            for flow in self.task_setting[self.block][self.version].keys():
                for task in self.task_setting[self.block][self.version][flow].keys():
                    raw_tasks.append(task)

        all_tasks = []

        for i in range(self.table_model.rowCount()):

            if self.table_model.index(i, 0).data():
                block = self.table_model.index(i, 0).data().strip()

            if self.table_model.index(i, 1).data():
                version = self.table_model.index(i, 1).data().strip()

            if self.table_model.index(i, 2).data():
                flow = self.table_model.index(i, 2).data().strip()

            if self.item == 'task' and self.auto_import_tasks:
                task = self.table.indexWidget(self.table_model.index(i, 3)).text().strip()
            else:
                task = self.table_model.index(i, 3).data().strip()

            if not self.item == 'task' and self.auto_import_tasks:
                if self.table_model.item(i, 3) and not self.table_model.item(i, 3).checkState() == Qt.Checked:
                    continue

            if task in raw_tasks:
                common_pyqt5.Dialog('Error', "Task[%s] already exist in your config, please ensure task uniqueness!" % task, QMessageBox.Critical)
                self.save_button.setEnabled(True)
                return

            if task in all_tasks:
                common_pyqt5.Dialog('Error', "Cant import flows which include same task, please ensure task uniqueness!", QMessageBox.Critical)
                self.save_button.setEnabled(True)
                return
            else:
                all_tasks.append(task)

            if '' in [block, version, flow, task] or None in [block, version, flow, task]:
                common_pyqt5.Dialog('Error', "Please fill in any empty item", QMessageBox.Critical)
                self.save_button.setEnabled(True)
                return

            if self.item == 'block' and block in raw_user_input.keys():
                common_pyqt5.Dialog('Error', "You add one repeated block %s" % block, QMessageBox.Critical)
                self.save_button.setEnabled(True)
                return
            elif self.item == 'version' and version in raw_user_input[block].keys():
                common_pyqt5.Dialog('Error', "You add one repeated version %s" % version, QMessageBox.Critical)
                self.save_button.setEnabled(True)
                return
            elif self.item == 'flow' and flow in raw_user_input[block][version].keys():
                common_pyqt5.Dialog('Error', "You add one repeated flow %s" % flow, QMessageBox.Critical)
                self.save_button.setEnabled(True)
                return
            elif self.item == 'task' and task in raw_user_input[block][version][flow].keys():
                common_pyqt5.Dialog('Error', "You add one repeated task %s" % task, QMessageBox.Critical)
                self.save_button.setEnabled(True)
                return

        for i in range(self.table_model.rowCount()):
            if self.table_model.index(i, 0).data():
                block = self.table_model.index(i, 0).data()

            if self.table_model.index(i, 1).data():
                version = self.table_model.index(i, 1).data()

            if self.table_model.index(i, 2).data():
                flow = self.table_model.index(i, 2).data()

            if self.item == 'task' and self.auto_import_tasks:
                task = self.table.indexWidget(self.table_model.index(i, 3)).text()
            else:
                task = self.table_model.index(i, 3).data()

            if block not in self.dependency_dic:
                self.dependency_dic.setdefault(block, {})

            if version not in self.dependency_dic[block]:
                self.dependency_dic[block].setdefault(version, {})

            if task not in self.dependency_dic[block][version]:
                if self.auto_import_tasks:
                    tasks = list(set(all_tasks).union(set(raw_tasks)))
                    self.dependency_dic[block][version][task] = WindowForDependency.clean_dependency(item_list=tasks, item=task, dependency=self.default_dependency_dic.get(task, ''))

            if self.item == 'task':
                all_tasks = list(self.task_setting[block][version][flow].keys())
                index = all_tasks.index(self.task)
                all_tasks.insert(index + 1, task)
                self.task_setting[block][version][flow][task] = {}
                # self.task_setting[block][version][flow] = {}

                # for k in all_tasks:
                #     self.task_setting[block][version][flow][k] = {}
            else:
                if self.item in ['block', 'version', 'flow'] and self.auto_import_tasks:
                    if not self.table_model.item(i, 3).checkState() == Qt.Checked:
                        continue

                self.task_setting[block][version][flow][task] = {}

        self.message.emit([self.task_setting, self.item, block, version, self.dependency_dic])
        self.save_signal.emit()
        self.deleteLater()


class WindowForCopyItems(QMainWindow):
    message = pyqtSignal(list)
    save_signal = pyqtSignal()

    def __init__(self,
                 item,
                 user_input,
                 detailed_setting,
                 block=None,
                 version=None,
                 flow=None,
                 task=None,
                 dependency_dic=None):
        super().__init__()
        self.item = item
        self.task_setting = copy.deepcopy(user_input)
        self.detailed_setting = copy.deepcopy(detailed_setting)
        self.dependency_dic = dependency_dic
        self.block = block
        self.version = version
        self.flow = flow
        self.task = task
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
        self.raw_table_model = QStandardItemModel(1, 4)
        self.raw_table.setModel(self.raw_table_model)
        header = ['Block', 'Version', 'Flow', 'Task']
        self.raw_table_model.setHorizontalHeaderLabels(header)
        self.raw_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.raw_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.raw_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.raw_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.raw_table.setStyleSheet('font-family : calibri; font-size : 15px')
        self.raw_table.setShowGrid(True)
        self.raw_table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        self.new_table_label = QLabel('New Setting')
        self.new_table_label.setStyleSheet('font-weight : bold; font-size : 20px')

        self.new_table = QTableView()
        self.new_table_model = QStandardItemModel(1, 4)
        self.new_table.setModel(self.new_table_model)
        header = ['Block', 'Version', 'Flow', 'Task']
        self.new_table_model.setHorizontalHeaderLabels(header)
        self.new_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.new_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.new_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.new_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
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

        self.top_layout.addWidget(self.raw_table_label)
        self.top_layout.addWidget(self.raw_table)
        self.top_layout.addStretch(2)

        self.top_layout.addWidget(self.new_table_label)
        self.top_layout.addWidget(self.new_table)
        self.top_layout.addWidget(self.button_widget)

        self.top_layout.setStretch(0, 1)
        self.top_layout.setStretch(1, 12)
        self.top_layout.setStretch(3, 1)
        self.top_layout.setStretch(4, 12)
        self.top_layout.setStretch(5, 1)

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

            if self.item in ['block']:
                versions = list(self.task_setting[block].keys())
            elif self.item in ['version', 'flow', 'task']:
                versions = [self.version]

            for version in versions:
                version_start_line = row

                for flow in self.task_setting[block][version].keys():
                    if self.item in ['flow', 'task'] and not flow == self.flow:
                        continue

                    flow_start_line = row

                    for task in self.task_setting[block][version][flow].keys():
                        if self.item in ['task'] and not task == self.task:
                            continue

                        block_item = QStandardItem(block)

                        if editable and self.item in ['version', 'flow', 'task']:
                            block_item.setFlags(Qt.ItemIsEditable)
                        model.setItem(row, 0, block_item)

                        version_item = QStandardItem(version)

                        if editable and self.item in ['flow', 'task']:
                            version_item.setFlags(Qt.ItemIsEditable)

                        model.setItem(row, 1, QStandardItem(version_item))

                        flow_item = QStandardItem(flow)

                        if editable and self.item in ['block', 'version', 'task']:
                            flow_item.setFlags(Qt.ItemIsEditable)

                        model.setItem(row, 2, flow_item)

                        task_item = QStandardItem(task)

                        if editable and self.item in ['block', 'version']:
                            task_item.setFlags(Qt.ItemIsEditable)

                        model.setItem(row, 3, task_item)
                        row += 1

                    if row - flow_start_line > 1:
                        table.setSpan(flow_start_line, 2, row - flow_start_line, 1)
                        self.span_info[flow_start_line][2] = row - 1

                if row - version_start_line > 1:
                    table.setSpan(version_start_line, 1, row - version_start_line, 1)
                    self.span_info[version_start_line][1] = row - 1

            if row - block_start_line > 1:
                table.setSpan(block_start_line, 0, row - block_start_line, 1)
                self.span_info[block_start_line][0] = row - 1

    def save(self):
        self.save_button.setEnabled(False)
        update_flow_flag = False
        task_new = ''
        block, version, flow, task = None, None, None, None
        raw_tasks = []

        if self.item in ['flow', 'task']:
            for flow in self.task_setting[self.block][self.version].keys():
                for task in self.task_setting[self.block][self.version][flow].keys():
                    raw_tasks.append(task)

        for i in range(self.new_table_model.rowCount()):
            block_new = self.new_table_model.index(i, 0).data().strip()
            version_new = self.new_table_model.index(i, 1).data().strip()
            flow_new = self.new_table_model.index(i, 2).data().strip()
            task_new = self.new_table_model.index(i, 3).data().strip()

            if task_new in raw_tasks:
                common_pyqt5.Dialog('Error', "Task[%s] already exist in your config, please ensure task uniqueness!" % task_new, QMessageBox.Critical)
                self.save_button.setEnabled(True)
                return

            for cell in [block_new, version_new, flow_new, task_new]:
                if re.search(r'^\s*$', cell):
                    common_pyqt5.Dialog('Error', "Empty %s name!" % list(locals().keys())[list(locals().values()).index(cell)].replace('_new', ''), QMessageBox.Critical)
                    self.save_button.setEnabled(True)
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

            if self.item == 'block' and block_new in self.task_setting.keys():
                common_pyqt5.Dialog('Error', "You add one repeated block %s" % block_new, QMessageBox.Critical)
                self.save_button.setEnabled(True)
                return
            elif self.item == 'version' and version_new in self.task_setting[self.block].keys():
                common_pyqt5.Dialog('Error', "You add one repeated version %s" % version_new, QMessageBox.Critical)
                self.save_button.setEnabled(True)
                return
            elif self.item == 'flow' and flow_new in self.task_setting[self.block][self.version].keys():
                common_pyqt5.Dialog('Error', "You add one repeated flow %s" % flow_new, QMessageBox.Critical)
                self.save_button.setEnabled(True)
                return
            elif self.item == 'task' and task_new in self.task_setting[self.block][self.version][self.flow].keys():
                common_pyqt5.Dialog('Error', "You add one repeated task %s" % task_new, QMessageBox.Critical)
                self.save_button.setEnabled(True)
                return

        for i in range(self.new_table_model.rowCount()):
            block_new = self.new_table_model.index(i, 0).data()
            version_new = self.new_table_model.index(i, 1).data()
            flow_new = self.new_table_model.index(i, 2).data()
            task_new = self.new_table_model.index(i, 3).data()

            # Update dependency dic
            raw_block = self.raw_table_model.index(i, 0).data()
            raw_version = self.raw_table_model.index(i, 1).data()
            raw_flow = self.raw_table_model.index(i, 2).data()
            raw_task = self.raw_table_model.index(i, 3).data()

            block_flag = False if raw_block == block_new else True
            version_flag = False if raw_version == version_new else True
            flow_flag = False if raw_flow == flow_new else True
            task_flag = False if raw_task == task_new else True

            block_tmp = block_new if block_flag else raw_block
            version_tmp = version_new if version_flag else raw_version
            flow_tmp = flow_new if flow_flag else raw_flow

            if block_new not in self.dependency_dic:
                if version_flag or flow_flag or task_flag:
                    self.dependency_dic.setdefault(block_new, {})
                else:
                    self.dependency_dic[block_new] = copy.deepcopy(self.dependency_dic[raw_block])

            if version_new not in self.dependency_dic[block_tmp]:
                if flow_flag or task_flag:
                    self.dependency_dic[block_tmp].setdefault(version_new, {})
                else:
                    self.dependency_dic[block_tmp][version_new] = copy.deepcopy(self.dependency_dic[raw_block][raw_version])

            if task_new not in self.dependency_dic[block_tmp][version_tmp]:
                self.dependency_dic[block_tmp][version_tmp][task_new] = copy.deepcopy(self.dependency_dic[raw_block][raw_version][raw_task])

            if not self.task_setting[block_new][version_new][flow_new][task_new]:
                if self.item == 'task':
                    all_tasks = list(self.task_setting[block_new][version_new][flow_new].keys())
                    index = all_tasks.index(self.task)
                    all_tasks.insert(index + 1, task_new)
                    self.task_setting[block_new][version_new][flow_new] = {}

                    for k in all_tasks:
                        self.task_setting[block_new][version_new][flow_new][k] = {}
                else:
                    self.task_setting[block_new][version_new][flow_new][task_new] = {}

            if not self.detailed_setting[block_new][version_new][flow_new][task_new]:
                self.detailed_setting[block_new][version_new][flow_new][task_new] = copy.deepcopy(self.detailed_setting[raw_block][raw_version][raw_flow][raw_task])

            # if not self.item == 'branches':
            if not flow_new == flow:
                update_flow_flag = True

        for block in self.task_setting:
            for version in self.task_setting[block]:
                for flow in self.task_setting[block][version]:
                    for task in self.task_setting[block][version][flow]:
                        self.task_setting[block][version][flow][task] = self.detailed_setting[block][version][flow][task]

        if self.item == 'task':
            self.message.emit([self.item, task_new, self.task_setting])
        elif update_flow_flag:
            self.message.emit(['update flow', self.task_setting])
        else:
            self.message.emit([self.item, self.task_setting])

        self.save_signal.emit()
        self.deleteLater()


class WindowForTaskConfig(QMainWindow):
    message = pyqtSignal(list)
    resize_signal = pyqtSignal(int, int)
    close_signal = pyqtSignal(bool)

    def __init__(self,
                 blank_setting: dict,
                 task_obj: job_manager.TaskObject,
                 read_only: bool = False):
        super().__init__()

        # Information
        self.close_label = 'CONFIG'
        self.task_obj = task_obj
        self.block = self.task_obj.block
        self.version = self.task_obj.version
        self.flow = self.task_obj.flow
        self.raw_task = self.task_obj.task
        self.new_task = self.task_obj.task
        self.config_obj = parse_config.Config(None)
        self.user_task_setting = self.config_obj.user_task_setting
        self.default_task_setting = self.config_obj.default_task_setting
        self.detailed_setting = self.user_task_setting[self.block][self.version][self.flow][self.task_obj.task]
        self.blank_setting = blank_setting
        self.default_var = self.config_obj.default_var_setting
        self.project = self.config_obj.PROJECT
        self.group = self.config_obj.GROUP
        self.cwd = os.getcwd()
        self.var = self.config_obj.var_dic
        self.raw_setting = AutoVivification()
        self.tips = AutoVivification()
        self.read_only = read_only
        self.all_tasks = self.user_task_setting[self.block][self.version][self.flow].keys()

        # task config
        self.task_config_obj = self.config_obj.get_task(self.block, self.version, self.flow, self.task_obj.task)
        self.run_mode_list = list(self.task_config_obj.RunInfo.keys())
        self.show_run_mode = self.task_config_obj.RunMode

        # Defined by system
        self.var_mapping = {'PROJECT': self.project,
                            'GROUP': self.group,
                            'CWD': self.cwd,
                            'IFP_INSTALL_PATH': os.getenv('IFP_INSTALL_PATH'),
                            'BLOCK': self.block,
                            'VERSION': self.version,
                            'FLOW': self.flow,
                            'TASK': self.raw_task,
                            }
        self.replace_var_mapping = {**self.var, **copy.deepcopy(self.var_mapping)}
        self.var_mapping = {**self.default_var, **self.var, **self.var_mapping}

        # Top Layout
        self.top_widget = QWidget()
        self.top_layout = QVBoxLayout()
        self.main_layout = QHBoxLayout()
        self.setup_layout = QVBoxLayout()

        # Task Name
        self.widget_task_name = QWidget()
        self.layout_task_name = QHBoxLayout()
        self.label_task_name = QLabel('Task name :')
        self.line_edit_task_name = QLineEdit(self.task_obj.task)
        self.reset_to_default_button = QPushButton('Reset To Default')
        self.title = '%s/%s/%s/%s (Read Only)' % (self.block, self.version, self.flow, self.new_task) if self.read_only else '%s/%s' % (self.flow, self.new_task)
        self.show_env_button = QCheckBox('Parameter_mode')
        self.float_env_button = QPushButton('Show Variable ->')

        # Variable
        self.label_env = QLabel('Env setting (Non editable):')
        self.label_env.setStyleSheet('font-weight : bold;')
        self.env_table = QTableView()
        self.env_model = QStandardItemModel(1, 2)

        var_setting_window = WindowForToolGlobalEnvEditor(default_var=self.var_mapping, user_var={}, window='edit_task')
        self.show_var_values_flag = False
        self.var_setting_table = var_setting_window.init_ui()
        self.env_floating_flag = False

        # Task Setting
        self.setup_table = QTableView()
        self.setup_model = QStandardItemModel(1, 2)
        self.setup_model.itemChanged.connect(self.check_path_validity)
        self.setup_delegate = CustomDelegate2()
        self.license_dependency = ShrinkablePushButton()
        self.file_dependency = ShrinkablePushButton()
        self.run_log_files = ShrinkablePushButton()

        pushbutton_style = """
            QPushButton {
                background-color: transparent;
                color: rgba(0, 0, 0, 0);
                border: none;
            }
            QPushButton:hover {
                background-color: transparent;
            }
        """
        self.license_dependency.setStyleSheet(pushbutton_style)
        self.file_dependency.setStyleSheet(pushbutton_style)
        self.run_log_files.setStyleSheet(pushbutton_style)

        self.run_combo = QComboBox()
        self.run_label = QLabel()

        # Save & Reset
        self.save_button = QPushButton('save')
        self.cancel_button = QPushButton('cancel')
        self.button_widget = QWidget()
        self.button_layout = QHBoxLayout()

        center(self)

        self.child = None
        self.init_ui()
        self.table_raw_setting, self.table_detailed_setting = self._read_table()
        self.run_setting = self.table_raw_setting['RUN']

        if self.read_only:
            self.disable_gui()

        common_pyqt5.auto_resize(self, 800, 800)
        self.resize_signal.emit(800, 800)

    def disable_gui(self):
        self.setup_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.save_button.setEnabled(False)
        self.line_edit_task_name.setEnabled(False)

    def check_path_validity(self, item: QStandardItem):
        try:
            if self.setup_model and item.whatsThis():
                what_is_this = item.whatsThis()
                key = what_is_this.split()[-1]

                if key == 'PATH':
                    value = self.setup_model.item(item.row(), 1).text().strip()

                    if value:
                        real_path = custom_format_map(value, self.replace_var_mapping) if isinstance(value, str) else value

                        if not os.path.exists(str(real_path)):
                            self.setup_model.item(item.row(), 0).setForeground(QColor(Qt.red))
                        else:
                            self.setup_model.item(item.row(), 0).setForeground(QColor(Qt.black))
        except Exception:
            pass

    def init_ui(self):
        # Top Layout
        self.top_widget.setLayout(self.top_layout)
        self.setCentralWidget(self.top_widget)

        # Task name
        self.label_task_name.setStyleSheet('font-weight : bold;font-size : 15px')
        self.line_edit_task_name.setFixedWidth(100)
        self.line_edit_task_name.returnPressed.connect(self.change_new_task)
        self.layout_task_name.addWidget(self.label_task_name)
        self.layout_task_name.addWidget(self.line_edit_task_name)
        self.layout_task_name.addWidget(self.reset_to_default_button)
        self.layout_task_name.setStretch(0, 1)
        self.layout_task_name.setStretch(1, 5)
        self.layout_task_name.setStretch(2, 20)
        self.widget_task_name.setLayout(self.layout_task_name)

        # Variable
        header = ['Item', 'Value']
        self.env_table.setModel(self.env_model)
        self.env_table.setColumnWidth(0, 180)
        self.env_model.setHorizontalHeaderLabels(header)
        self.env_table.setStyleSheet('font-family : calibri; font-size : 15px')
        self.env_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.env_table.setShowGrid(True)
        self.env_table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        self.setup_table.setMouseTracking(True)
        self.setup_table.entered.connect(self.show_tips)
        self.setup_table.setModel(self.setup_model)
        self.setup_table.setColumnWidth(0, 140)
        self.setup_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.setup_table.setItemDelegate(self.setup_delegate)

        self.setup_model.setHorizontalHeaderLabels(header)
        self.setup_table.setStyleSheet('font-family : calibri; font-size : 15px')
        self.setup_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.setup_table.setShowGrid(True)

        self.license_dependency.clicked.connect(functools.partial(self.edit_task_requirements, 'DEPENDENCY', 'LICENSE'))
        self.file_dependency.clicked.connect(functools.partial(self.edit_task_requirements, 'DEPENDENCY', 'FILE'))
        self.run_log_files.clicked.connect(functools.partial(self.edit_task_requirements, 'RUN', 'LOG'))
        self.license_dependency.setWhatsThis('DEPENDENCY LICENSE')
        self.file_dependency.setWhatsThis('DEPENDENCY FILE')
        self.run_log_files.setWhatsThis('RUN LOG')
        self.run_label.setStyleSheet("QLabel { color: gray; font-size: 14px; font-style: italic; }")

        if self.read_only:
            self.license_dependency.setEnabled(False)
            self.file_dependency.setEnabled(False)

        row = 0

        for category in self.var_mapping.keys():
            item = QStandardItem('${%s}' % category)
            item.setTextAlignment(Qt.AlignLeft)
            item.setTextAlignment(Qt.AlignVCenter)
            self.env_model.setItem(row, 0, item)

            item = QStandardItem('%s' % self.var_mapping[category])
            item.setTextAlignment(Qt.AlignLeft)
            item.setTextAlignment(Qt.AlignVCenter)
            self.env_model.setItem(row, 1, item)
            row += 1

        self.show_env_button.setCheckState(Qt.Checked)
        self.show_env_button.stateChanged.connect(self.show_var_values)
        self.float_env_button.clicked.connect(self.float_env_setting)
        self.reset_to_default_button.clicked.connect(self._reset_to_default)
        self.save_button.clicked.connect(self.save)
        self.cancel_button.clicked.connect(self.close)

        self.button_widget.setLayout(self.button_layout)
        self.button_layout.addStretch(1)
        self.button_layout.addWidget(self.save_button)
        self.button_layout.addWidget(self.cancel_button)

        setting_layout = QHBoxLayout()
        setting_layout.addWidget(self.widget_task_name)
        setting_layout.addWidget(self.reset_to_default_button)
        setting_layout.addStretch(1)
        setting_layout.addWidget(self.show_env_button)
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

        self.draw_table(self.raw_task)
        self.hide_env()

    def change_new_task(self):
        self.new_task = self.line_edit_task_name.text().strip()

    def update_table(self):
        for row in range(self.setup_model.rowCount()):
            standard_item = self.setup_model.item(row, 1)
            widget = self.setup_table.indexWidget(self.setup_model.index(row, 1))

            if standard_item is None:
                continue

            what_is_this = standard_item.whatsThis()

            if what_is_this.find('RUN') != -1 and what_is_this.find('RUN_METHOD') == -1:
                what_is_this = what_is_this.replace('RUN', self.show_run_mode)

            default_value = self.task_config_obj.DefaultSetting.get_definition(what_is_this)
            user_value = self.task_config_obj.UserSetting.get_definition(what_is_this)

            if user_value is not None:
                if isinstance(widget, QPushButton):
                    user_value = ','.join(user_value) if isinstance(user_value, list) else user_value

                standard_item.setData(user_value, Qt.DisplayRole)
            else:
                if isinstance(widget, QPushButton):
                    default_value = ','.join(default_value) if isinstance(default_value, list) else default_value

                standard_item.setData(default_value, Qt.DisplayRole)

            if default_value is not None:
                standard_item.setData(default_value, Qt.UserRole + 1)

            self.setup_model.setItem(row, 1, standard_item)

        if len(self.task_config_obj.RunInfo.keys()) != 1:
            if self.show_run_mode != self.task_config_obj.RunMode:
                self.run_label.setText(f'<- Click to view other modes, current is {self.task_config_obj.RunMode}')
            else:
                self.run_label.setText('<- Click to view other modes')

    def reset_to_default_table(self):
        for row in range(self.setup_model.rowCount()):
            standard_item = self.setup_model.item(row, 1)

            if standard_item is None:
                continue

            what_is_this = standard_item.whatsThis()
            default_value = self.task_config_obj.DefaultSetting.get_definition(what_is_this)
            user_value = self.task_config_obj.UserSetting.get_definition(what_is_this)

            if default_value is not None or (user_value is not None and default_value is None):
                if default_value is None:
                    default_value = ''

                if isinstance(default_value, list):
                    default_value = ','.join(default_value)

                standard_item.setData(default_value, Qt.DisplayRole)
                standard_item.setData(default_value, Qt.UserRole + 1)

            self.setup_model.setItem(row, 1, standard_item)

    def draw_table(self, new_task: str):
        self.env_model.clear()
        self.new_task = new_task
        self.env_model.setItem(7, 1, QStandardItem(new_task))
        self.setWindowTitle('Detailed setting for %s' % self.title)
        font = QFont('Calibri', 15)
        font.setBold(True)

        self.setup_model.setRowCount(0)
        row = 0

        for category in self.blank_setting.keys():
            item = QStandardItem('* %s' % category)
            item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            item.setEditable(False)
            item.setFont(font)
            item.setBackground(QBrush(QColor(245, 255, 250)))
            item.setForeground(QBrush(QColor(0, 0, 0)))
            self.setup_model.setItem(row, 0, item)
            self.setup_table.setSpan(row, 0, 1, 2)

            # For RUN
            if category == 'RUN':
                run_widget = self.gen_run_widget()
                index = self.setup_model.index(row, 0)
                self.setup_table.setIndexWidget(index, run_widget)

            row += 1

            for key in self.blank_setting[category].keys():
                item = QStandardItem(key)
                item.setTextAlignment(Qt.AlignLeft)
                item.setTextAlignment(Qt.AlignVCenter)
                item.setEditable(False)
                self.setup_model.setItem(row, 0, item)
                self.tips[row] = self.blank_setting[category][key]['example']

                item = QStandardItem('')
                item.setBackground(QBrush(QColor(255, 255, 255)))
                item.setTextAlignment(Qt.AlignLeft)
                item.setTextAlignment(Qt.AlignVCenter)
                item.setForeground(QBrush(EDIT_COLOR))
                item.setWhatsThis(f'{category} {key}')

                self.setup_model.setItem(row, 1, item)

                if category == 'DEPENDENCY' and key == 'LICENSE':
                    index = self.setup_model.indexFromItem(item)
                    self.setup_table.setIndexWidget(index, self.license_dependency)
                elif category == 'DEPENDENCY' and key == 'FILE':
                    index = self.setup_model.indexFromItem(item)
                    self.setup_table.setIndexWidget(index, self.file_dependency)
                elif category == 'RUN' and key == 'LOG':
                    index = self.setup_model.indexFromItem(item)
                    self.setup_table.setIndexWidget(index, self.run_log_files)

                row += 1

        self.update_table()

    def change_run_mode(self, index):
        new_run_mode = self.run_combo.itemText(index).replace('*', '').strip()

        if new_run_mode != self.show_run_mode:
            table_raw_setting, table_detailed_setting = self._read_table()
            new_run_setting = table_raw_setting['RUN']

            for key, value in new_run_setting.items():
                if self.run_setting[key] != value:
                    QMessageBox.critical(self, "Error", 'Configure modified, please save first!')
                    self.run_combo.disconnect()
                    self.run_combo.setCurrentText(f'* {self.show_run_mode}    ')
                    self.run_combo.currentIndexChanged.connect(self.change_run_mode)
                    return

        self.show_run_mode = new_run_mode
        self.update_table()
        self.table_raw_setting, self.table_detailed_setting = self._read_table()
        self.run_setting = self.table_raw_setting['RUN']

    def gen_run_widget(self) -> Qt.Widget:
        self.run_combo.addItems([f'* {mode}    ' for mode in self.run_mode_list])
        self.run_combo.setCurrentText(f'* {self.show_run_mode}    ')
        self.run_combo.currentIndexChanged.connect(self.change_run_mode)
        self.run_combo.setStyleSheet("""
        QComboBox {
            font: bold 20px 'Calibri';
            color: black;
            background-color: rgb(245, 255, 250);
            border: 1px solid transparent;
            border-radius: 0px;
        }
        QComboBox::drop-down {
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 15px;
            border-left-width: 0px;
            border-top-right-radius: 3px;
            border-bottom-right-radius: 3px;
            background: transparent;
        }
        """)
        run_widget = QWidget()
        run_widget.setStyleSheet('background: transparent;')
        run_layout = QHBoxLayout()
        run_layout.addWidget(self.run_combo, 1)
        run_layout.addWidget(self.run_label, 4)
        run_layout.addStretch(4)
        run_widget.setLayout(run_layout)
        run_layout.setContentsMargins(0, 0, 0, 0)
        run_layout.setSpacing(0)
        self.run_combo.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        return run_widget

    def _reset_to_default(self):
        reply = QMessageBox.question(self,
                                     "Warning",
                                     "Are you sure to reset all settings to default?",
                                     QMessageBox.Yes | QMessageBox.No)

        if reply == QMessageBox.Yes:
            self.reset_to_default_table()
        elif reply == QMessageBox.No:
            return

    def edit_task_requirements(self, category: str = 'DEPENDENCY', item: str = 'LICENSE'):
        row = self.setup_table.indexAt(self.sender().pos()).row()
        text = self.setup_model.index(row, 1).data() if self.setup_model.index(row, 1).data() else ''
        self.child = WindowForEditTaskRequirement(row, text, category, item)
        self.child.setWindowModality(Qt.ApplicationModal)
        self.child.message.connect(self.update_task_requirement)
        self.child.show()

    def update_task_requirement(self, row, text, category, item):
        if text == '':
            if dependency := self.default_task_setting.get(self.raw_task, {}).get(category, {}).get(item):
                text = ','.join(dependency)

        table_item = QStandardItem(text)
        table_item.setWhatsThis(f'{category} {item}')
        self.setup_model.setItem(row, 1, table_item)

    def show_tips(self, index):
        desktop = QApplication.desktop()
        screen_num = desktop.screenNumber(QCursor.pos())
        screen_rect = desktop.screenGeometry(screen_num)

        if index.data() == '' and index.column() == 1 and index.row() in self.tips.keys():
            QToolTip.showText(QCursor.pos(), 'Example : ' + self.tips[index.row()], self.setup_table, screen_rect, 10000)

    def save(self):
        self.save_button.setEnabled(False)

        if self.show_var_values_flag:
            self._show_var_values_false()

        if not self.raw_task == self.new_task:
            if self.new_task in self.all_tasks:
                QMessageBox.critical(self, "Error", "%s already exist, please update task name" % self.new_task, QMessageBox.Ok)
                self.save_button.setEnabled(True)
                return

            reply = QMessageBox.question(self, "Warning", "Are you sure to change task name from %s to %s? \n Flow will copy all setting, please confirm if any special setting for %s!" % (self.raw_task, self.new_task, self.new_task), QMessageBox.Yes | QMessageBox.No)

            if reply == QMessageBox.Yes:
                pass
            elif reply == QMessageBox.No:
                self.save_button.setEnabled(True)
                return

        setting = AutoVivification()
        warning_info = ''
        warning_num = 0

        for i in range(self.setup_model.rowCount()):
            model_item = self.setup_model.item(i, 1)
            widget = self.setup_table.indexWidget(self.setup_model.index(i, 1))

            if model_item is None:
                continue

            what_is_this = model_item.whatsThis().split()
            value = model_item.data(Qt.DisplayRole)
            category = what_is_this[0]
            item = what_is_this[1]

            if category == 'RUN':
                category = self.show_run_mode

            setting[category][item] = value

            if isinstance(widget, QPushButton) and isinstance(value, str):
                if category == 'RUN':
                    if isinstance(value, str) and len(value.split(',')) > 1:
                        setting[category][item] = [item.strip() for item in value.split(',')]

                    if isinstance(value, list) and len(value) < 2:
                        setting[category][item] = value[0].strip()
                else:
                    setting[category][item] = [item.strip() for item in value.split(',')] if value else []

            if value == '':
                if category in self.detailed_setting.keys() and category in self.default_task_setting[self.new_task].keys():
                    if item in self.detailed_setting[category].keys() and item in self.default_task_setting[self.new_task][category].keys():
                        if not self.detailed_setting[category][item] == {} and not self.default_task_setting[self.new_task][category][item] == {}:
                            warning_num += 1
                            warning_info += '%s. Remove user_defined_setting <b>[%s]</b> for %s/%s, flow will replace it with default_setting <b>[%s]</b><br/>\n' % (
                                warning_num, self.detailed_setting[category][item], category, item, self.default_task_setting[self.new_task][category][item])

        if warning_info:
            warning_info += '<br/>If you want to keep your setting, please return and press cancel button'
            reply = QMessageBox.question(self, "Confirm Your Changes", warning_info, QMessageBox.Yes | QMessageBox.No)

            if reply == QMessageBox.Yes:
                pass
            elif reply == QMessageBox.No:
                self.save_button.setEnabled(True)
                return

        for cat in self.detailed_setting:
            if cat not in setting:
                setting[cat] = copy.deepcopy(self.detailed_setting[cat])

        self.message.emit([setting, self.new_task])

        self.close_signal.emit(True)

    def float_env_setting(self):
        if self.env_floating_flag:
            self.float_env_button.setText('Show Variable ->')
            self.var_setting_table.hide()
            self.env_floating_flag = False
            common_pyqt5.auto_resize(self, 800, 800)
            self.resize_signal.emit(800, 800)
        else:
            self.hide_env()
            self.float_env_button.setText('<- Hide Variable')
            self.env_floating_flag = True
            self.var_setting_table.show()
            common_pyqt5.auto_resize(self, 1350, 800)
            self.show_env_button.setCheckState(Qt.Checked)
            self.resize_signal.emit(1350, 800)

    def hide_env(self):
        self.label_env.hide()
        self.env_table.hide()

    def _read_table(self) -> Tuple[dict, dict]:
        """
        Reading current task setting
        """
        setting = AutoVivification()
        detailed_setting = AutoVivification()

        for i in range(self.setup_model.rowCount()):
            item = self.setup_model.item(i, 1)

            if item is None:
                continue

            what_is_this = item.whatsThis().split()
            category = what_is_this[0]
            name = what_is_this[1]

            value = item.data(Qt.DisplayRole)
            detailed_value = custom_format_map(value, self.replace_var_mapping) if isinstance(value, str) else value
            setting[category][name] = value
            detailed_setting[category][name] = detailed_value

        return setting, detailed_setting

    def _update_table(self, show_value_flag: bool = False):
        """
        update table variable values.
        """
        for i in range(self.setup_model.rowCount()):
            item = self.setup_model.item(i, 1)

            if item is None:
                continue

            what_is_this = item.whatsThis().split()
            category = what_is_this[0]
            name = what_is_this[1]
            new_value = self.table_detailed_setting[category][name] if show_value_flag else self.table_raw_setting[category][name]

            if isinstance(new_value, list):
                new_value = ' '.join(new_value)

            self.setup_model.item(i, 1).setText(new_value)

            if show_value_flag:
                self.setup_model.item(i, 1).setForeground(QBrush(QColor(127, 127, 127)))
            else:
                self.setup_model.item(i, 1).setForeground(QBrush(EDIT_COLOR))

    def _show_var_values_true(self):
        self.table_raw_setting, self.table_detailed_setting = self._read_table()
        self.run_combo.setDisabled(True)
        self._update_table(show_value_flag=True)
        self.setup_table.setEditTriggers(QTableView.NoEditTriggers)
        self.setup_table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.setup_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setup_table.setTextElideMode(Qt.ElideNone)
        self.show_var_values_flag = True

    def _show_var_values_false(self):
        self.setup_table.setEditTriggers(QTableView.AllEditTriggers)
        self.run_combo.setDisabled(False)
        self._update_table(show_value_flag=False)
        self.show_var_values_flag = False

    def show_var_values(self, state):
        """
        show Variables' values.
        """
        if state == Qt.Checked:
            self._show_var_values_false()
        else:
            self._show_var_values_true()

        if self.read_only:
            self.disable_gui()

    def close(self):
        self.close_signal.emit(True)


class WindowForEditTaskRequirement(QMainWindow):
    message = pyqtSignal(int, str, str, str)

    def __init__(self, row, requirements, category: str, item: str = 'LICENSE'):
        super().__init__()
        self.requirement = requirements
        self.category = category
        self.item = item
        self.row = row

        if self.item == 'LICENSE':
            self.init_license_ui()
        elif self.item == 'FILE':
            self.init_file_ui(title='Edit Required File')
        elif self.item == 'LOG':
            self.init_file_ui(title='Edit Log Files')

    def init_license_ui(self):
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
        for i in self.requirement.split(','):
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

    def init_file_ui(self, title: str):
        self.setFixedWidth(600)
        self.setFixedHeight(300)
        self.setWindowTitle(title)

        self.top_widget = QWidget()
        self.top_layout = QVBoxLayout()
        self.top_widget.setLayout(self.top_layout)
        self.setCentralWidget(self.top_widget)
        self.setup_table = QTableView()
        self.setup_model = QStandardItemModel(10, 1)
        self.setup_table.setModel(self.setup_model)
        self.setup_table.setColumnWidth(0, 140)

        self.setup_model.setHorizontalHeaderLabels(['File'])
        self.setup_table.setStyleSheet('font-family : calibri; font-size : 15px')
        self.setup_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
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
        for i in self.requirement.split(','):
            item = QStandardItem(i)
            item.setTextAlignment(Qt.AlignLeft)
            item.setTextAlignment(Qt.AlignVCenter)
            item.setEditable(True)
            self.setup_model.setItem(row, 0, item)

            row += 1

    def save(self):
        text = []

        for i in range(self.setup_model.rowCount()):
            if self.item == 'LICENSE':
                feature = self.setup_model.index(i, 0).data()

                if not feature:
                    continue

                quantity = self.setup_model.index(i, 1).data()

                text.append('%s : %s' % (feature, quantity))
            elif self.item == 'FILE' or self.item == 'LOG':
                file = self.setup_model.index(i, 0).data()

                if not file:
                    continue

                text.append(file)

        text_content = str(',  '.join(text))

        self.message.emit(self.row, text_content, self.category, self.item)

        self.close()


class WindowForDependency(QMainWindow):
    message = pyqtSignal(str, dict)
    update = pyqtSignal(bool, str)

    def __init__(self, mode: str = 'window'):
        super().__init__()

        self.picture_dir = None
        self.dependency_priority_dic = {}
        self.origin_dependency_priority_dic = {}
        self.default_dependency_dic = {}
        self.current_block = None
        self.current_version = None
        self.current_dependency_priority_dic = {}

        self.mode = mode
        self.modify_item_set = set()
        self.dependency_clipboard = {}
        self.table_item_condition_dic = {}
        self.gui_enable_flag = True
        self.current_table = QTableWidget()

        screen_resolutions = self.get_screen_resolutions()

        for width, height in screen_resolutions:
            width_rate = int((width / 1100) * 10) / 10 if width < 1100 else 1
            self.width_scale_rate = width_rate if width_rate < 1 else 1

            height_rate = int((height / 650) * 10) / 10 if height < 650 else 1
            self.height_scale_rate = height_rate if height_rate < 1 else 1

        self.top_widget = QWidget()
        self.top_layout = QVBoxLayout()

        self.selection_widget = QWidget()
        self.selection_layout = QGridLayout()
        self.block_combo = QComboBox()
        self.version_combo = QComboBox()
        self.reset_to_default_button = QPushButton('Reset to Default', self.selection_widget)

        self.main_widget = QWidget()
        self.main_layout = QHBoxLayout()

        self.label_widget = QWidget()
        self.label_layout = QHBoxLayout()
        self.eog_button = QPushButton('Open Image')
        self.current_chart = QLabel()

        self.button_widget = QWidget()
        self.button_layout = QHBoxLayout()
        self.save_button = QPushButton('SAVE')

        if self.mode == 'window':
            self.cancel_button = QPushButton('CANCEL')
            self.cancel_button.clicked.connect(self.close)
        elif self.mode == 'widget':
            self.reset_button = QPushButton('RESET')
            self.reset_button.clicked.connect(self.reset)
            self.save_button.setEnabled(False)

        self.vis = []
        self.trace = []

        self.update_flag = 'dependency'

    def update_setting(self, dependency_priority_dic: dict = None, default_dependency_dic: dict = None):
        self.dependency_priority_dic = dependency_priority_dic
        self.origin_dependency_priority_dic = copy.deepcopy(self.dependency_priority_dic)
        self.default_dependency_dic = default_dependency_dic

        if self.dependency_priority_dic and self.dependency_priority_dic.get(self.current_block, {}).get(self.current_version) is None:
            self.current_block = list(self.dependency_priority_dic.keys())[0]
            self.current_version = list(self.dependency_priority_dic[self.current_block].keys())[0]

        if not os.access(os.getcwd(), os.W_OK):
            picture_base_dir = Path.home()
        else:
            picture_base_dir = os.getcwd()

        if not self.current_block or not self.current_version or not dependency_priority_dic.get(self.current_block, {}).get(self.current_version):
            self.current_dependency_priority_dic = {}
            self.picture_dir = os.path.join(picture_base_dir, '.ifp/pictures')
            self.gen_current_picture_dir()
        else:
            self.current_dependency_priority_dic = copy.deepcopy(dependency_priority_dic[self.current_block][self.current_version])
            self.picture_dir = os.path.join(picture_base_dir, '.ifp/pictures/%s/%s/' % (self.current_block, self.current_version))
            self.gen_current_picture_dir()

        self.update_ui()

    def update_ui(self):
        self._update_selection_button()
        self._update_table()
        self._update_dependency_chart()

    def gen_current_picture_dir(self):
        """
        mkdir CWD/.picture directory in order to save flow chart
        """
        if not os.path.exists(self.picture_dir):
            os.makedirs(self.picture_dir)

    def init_ui(self):
        title = 'Dependency Setting'
        self.setWindowTitle(title)

        label = QLabel('* Display complete tasks here, you can adjust the run order but IFP will ignore removed tasks in relation chain.')
        label.setStyleSheet("QLabel { color : gray; }")

        self.top_widget.setLayout(self.top_layout)
        self.setCentralWidget(self.top_widget)
        self.main_widget.setLayout(self.main_layout)

        self.eog_button.clicked.connect(self._eog_graph)
        self.label_widget.setLayout(self.label_layout)
        self.label_layout.addWidget(label, 10)
        self.label_layout.addWidget(self.eog_button, 1)

        self.top_layout.addWidget(self.selection_widget, 0)
        self.top_layout.addWidget(self.label_widget, 1)
        self.top_layout.addWidget(self.main_widget, 1)
        self.top_layout.setStretch(0, 2)
        self.top_layout.setStretch(1, 1)
        self.top_layout.setStretch(2, 10)

        self.gen_selection_button()
        self.gen_table()

        self.main_layout.addWidget(self.current_table, 1)
        self.main_layout.addWidget(self.current_chart, 2)

        self.save_button.clicked.connect(self.save)
        self.button_widget.setFixedHeight(50 * self.height_scale_rate)

        self.button_widget.setLayout(self.button_layout)
        self.button_layout.addStretch(1)
        self.button_layout.addWidget(self.save_button)

        if self.mode == 'window':
            self.button_layout.addWidget(self.cancel_button)
        elif self.mode == 'widget':
            self.button_layout.addWidget(self.reset_button)

        self.top_layout.addWidget(self.button_widget, 2)

        common_pyqt5.center_window(self)

        return self.top_widget

    def _eog_graph(self):
        try:
            os.popen('NO_AT_BRIDGE=1 /usr/bin/dbus-launch /bin/eog {}'.format(os.path.join(self.picture_dir, 'full_dependency.png')))
        except Exception as error:
            print(error)

    def gen_selection_button(self):
        """
        select current block/version
        """
        block_label = QLabel('Block', self.selection_widget)
        block_label.setStyleSheet("font-weight: bold;")
        block_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        version_label = QLabel('Version', self.selection_widget)
        version_label.setStyleSheet("font-weight: bold;")
        version_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.reset_to_default_button.clicked.connect(self.reset_to_default)
        self.selection_layout.addWidget(block_label, 0, 0)
        self.selection_layout.addWidget(self.block_combo, 0, 1)
        self.selection_layout.addWidget(version_label, 0, 2)
        self.selection_layout.addWidget(self.version_combo, 0, 3)
        self.selection_layout.addWidget(self.reset_to_default_button, 0, 4)
        self.selection_layout.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)

        self.selection_widget.setLayout(self.selection_layout)

    def _update_selection_button(self):
        self.block_combo.clear()
        self.version_combo.clear()
        self.block_combo.addItems(list(self.dependency_priority_dic.keys()))

        if self.current_block and self.dependency_priority_dic.get(self.current_block):
            self.block_combo.setCurrentText(self.current_block)
            self.version_combo.addItems(list(self.dependency_priority_dic[self.current_block].keys()))

        if self.current_version:
            self.version_combo.setCurrentText(self.current_version)

        self.block_combo.activated.connect(self.set_version_combo)
        self.version_combo.activated.connect(self.update_table_frame)

        if not set(self.default_dependency_dic.keys()).intersection(set(self.current_dependency_priority_dic.keys())):
            self.reset_to_default_button.setEnabled(False)

    def reset_to_default(self):
        modify_item_list = []

        for task in self.current_dependency_priority_dic:
            if task in self.default_dependency_dic:
                if self.current_dependency_priority_dic[task] != self.default_dependency_dic[task]:
                    modify_item_list.append(task)
                    self.current_dependency_priority_dic[task] = self.default_dependency_dic[task]

        self.update_dependency_show_info(modify_item_list=modify_item_list)

    def set_version_combo(self):
        block = self.block_combo.currentText().strip()

        if block and (block in self.dependency_priority_dic.keys()):
            self.version_combo.clear()

            for version in self.dependency_priority_dic[block].keys():
                self.version_combo.addItem(version)

        self.update_table_frame()

    def update_table_frame(self):
        self.current_block = self.block_combo.currentText().strip()
        self.current_version = self.version_combo.currentText().strip()
        self.gen_current_picture_dir()

        if not set(self.default_dependency_dic.keys()).intersection(set(self.current_dependency_priority_dic.keys())):
            self.reset_to_default_button.setEnabled(False)
        else:
            self.reset_to_default_button.setEnabled(True)

        if self.current_block and self.current_version:
            self.current_dependency_priority_dic = self.dependency_priority_dic[self.current_block][self.current_version]
            self._update_table()
            self._update_dependency_chart()

    def post_dependency_check(self):
        for task in self.current_dependency_priority_dic.keys():
            repeat_condition_list = self.current_dependency_priority_dic[task].split(',')
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

            self.current_dependency_priority_dic[task] = ','.join(new_repeat_condition_list)

        self.dependency_priority_dic[self.current_block][self.current_version] = copy.deepcopy(self.current_dependency_priority_dic)

    def gen_chart_frame(self, image_path, full_image_path):
        self.current_chart.clear()

        pixmap = QPixmap(image_path)
        self.current_chart.setPixmap(pixmap)
        self.current_chart.setToolTip('<img src="%s">' % str(full_image_path))

        self.current_chart.setAlignment(Qt.AlignCenter | Qt.AlignLeft)
        self.current_chart.setStyleSheet("background-color: white ;border: 1px solid lightgray ;")
        self.current_chart.setFixedWidth(600 * self.width_scale_rate)

    def _update_dependency_chart(self, graph_size=None):
        if graph_size is None:
            graph_size = [4.8, 3.2]

        dependency_dic = {**self.default_dependency_dic, **self.current_dependency_priority_dic}
        flow_chart_dic, node_list, edge_list = self.gen_dependency_chart_info(block=self.current_block, version=self.current_version, dependency_dic=dependency_dic)
        dot = graphviz.Digraph('round-table', comment='The Round Table')

        width = graph_size[0] * self.width_scale_rate
        height = graph_size[1] * self.height_scale_rate

        for node in node_list:
            if re.match(r'\d+', node['id']):
                dot.node(node['id'], node['label'], **{'width': '0.15', 'height': '0.15'})
            else:
                dot.node(node['id'], node['label'], shape='box')

        for edge in edge_list:
            dot.edge(edge['from'], edge['to'])

        dot.graph_attr['dpi'] = '300'
        dot.graph_attr['size'] = '10, 10'
        dot.render(os.path.join(self.picture_dir, 'full_dependency'), format='png')
        dot.graph_attr['dpi'] = '96'
        dot.graph_attr['size'] = '%s, %s' % (str(width), str(height))
        dot.render(os.path.join(self.picture_dir, 'dependency'), format='png')

        self.gen_chart_frame(image_path=os.path.join(self.picture_dir, r'dependency.png'), full_image_path=os.path.join(self.picture_dir, 'full_dependency.png'))

    def check_dependency_setting(self, dependency_dic: Dict[str, str] = None):
        """
        check dependency setting correctness
        including:
        1. loop -> dfs chart check
        2. the same condition (,, &, |)
        """
        if not dependency_dic:
            return True

        check_status = True
        flow_chart_dic, _, _ = self.gen_dependency_chart_info(block=self.current_block, version=self.current_version, dependency_dic=dependency_dic)

        self.vis = []
        self.trace = []

        for node in flow_chart_dic.keys():
            check_status = self.dfs_check_loop(node, flow_chart_dic)

            if not check_status:
                return check_status

        return check_status

    @staticmethod
    def gen_full_dependency_chart_info(dependency_dic: Dict[str, Dict[str, Dict[str, str]]]) -> Tuple[Dict[str, Dict[str, Dict[str, List[str]]]], List[Dict[str, str]], List[Dict[str, str]]]:
        """
        Args:
            dependency_dic: ex {<block>: {<version>: {'task1': 'task2&task3|task4, task5'}}}
        Returns:
            flow_chart_dic: ex {'task1': ['task2', '& link', '| link'], ...}
            node_list: ex [{'id': <node_id>, 'label': <node_name>}, ...]
            edge_list: ex [{'from': <start_node_id>, 'to': <end_node_id>}, ...]
        """
        full_node_list = []
        full_edge_list = []
        full_chart_dic = {}

        for block in dependency_dic:
            full_node_list.append({'id': f'{block}', 'label': block, 'size': 200, 'shape': 'box', 'color': {'background': 'white'}})
            full_chart_dic.setdefault(block, {})

            for version in dependency_dic[block]:
                full_edge_list.append({'from': f'{block}', 'to': f'{block}-{version}', 'length': 100})
                full_node_list.append({'id': f'{block}-{version}', 'label': version, 'size': 200, 'shape': 'box', 'color': {'background': 'white'}})
                full_chart_dic[block].setdefault(version, {})

                version_dependency_dic = dependency_dic[block][version]
                task_list = list(version_dependency_dic.keys())

                for task in version_dependency_dic.keys():
                    version_dependency_dic[task] = WindowForDependency.clean_dependency(item_list=task_list, item=task, dependency=version_dependency_dic[task])

                flow_chart_dic, node_list, edge_list = WindowForDependency.gen_dependency_chart_info(block=block, version=version, dependency_dic=version_dependency_dic)
                full_chart_dic[block][version] = flow_chart_dic
                node_dic = {node['id']: node for node in node_list}
                node_level_dic = WindowForDependency.gen_node_level(flow_chart_dic)

                for node, r_level in node_level_dic.items():
                    if max(node_level_dic.values()) == r_level:
                        edge_list.append({'from': f'{block}-{version}', 'to': f'{block}-{version}-{node}', 'length': 100})

                full_node_list += [node for node_id, node in node_dic.items()]
                full_edge_list += edge_list

        return full_chart_dic, full_node_list, full_edge_list

    @staticmethod
    def _discover_path(graph: Dict[str, List[str]], target_task: str, special_nodes: Dict[str, List[str]]) -> List[List[str]]:
        special_node_paths = {}
        final_paths = []

        for node in special_nodes:
            special_node_paths[node] = WindowForDependency.find_all_paths_to_node(graph=graph, target_node=node)

        target_paths = WindowForDependency.find_all_paths_to_node(graph=graph, target_node=target_task)

        for path in target_paths:
            final_paths += WindowForDependency.replace_special_nodes(path=path, special_node_paths=special_node_paths)

        unique_sublists = []
        seen_sublists = set()

        for sublist in final_paths:
            frozenset_sublist = frozenset(sublist)

            if frozenset_sublist not in seen_sublists:
                unique_sublists.append(sublist)
                seen_sublists.add(frozenset_sublist)

        return unique_sublists

    @staticmethod
    def discover_path(block: str, version: str, task_list: List[str], dependency: Dict[str, Dict[str, Dict[str, str]]]):
        paths = []
        flow_chart_dic, nodes, edges = WindowForDependency.gen_dependency_chart_info(block=block, version=version, dependency_dic=dependency[block][version])

        add_nodes = []

        for node in nodes:
            if node['label'] == '&':
                add_node = re.search(r'\d+$', node['id']).group(0)

                if add_node not in flow_chart_dic:
                    continue

                add_nodes.append(add_node)

        for task in task_list:
            discover_paths = WindowForDependency._discover_path(graph=flow_chart_dic, target_task=task, special_nodes={node: flow_chart_dic[node] for node in add_nodes})

            if len(discover_paths) > 1:
                return []

            paths += discover_paths

        path_set = set()

        for path in paths:
            path_set = path_set.union(set(path))

        return list(path_set)

    @staticmethod
    def replace_special_nodes(path: List[str], special_node_paths: Dict[str, List[List[str]]]) -> List[List[str]]:
        result = [[]]

        for element in path:
            if element in special_node_paths:
                temp_result = []

                for sublist in special_node_paths[element]:
                    for existing_list in result:
                        new_list = existing_list + [item for item in sublist if item not in existing_list]

                        if new_list not in temp_result:
                            temp_result.append(new_list)

                result = temp_result
            else:
                result = [existing_list + [element] if element not in existing_list else existing_list for existing_list in result]

        intermediate_result = []

        for list_a in result:
            if not any(set(list_a) < set(list_b) for list_b in result if list_a != list_b):
                intermediate_result.append(list_a)

        final_result = []

        for lst in intermediate_result:
            new_lst = [item for item in lst if not item.isdigit()]
            final_result.append(new_lst)

        return final_result

    @staticmethod
    def find_all_paths_to_node(graph, target_node) -> List[List[str]]:
        reverse_graph = {node: [] for node in graph}
        for node in graph:
            for neighbor in graph[node]:
                reverse_graph[neighbor].append(node)

        def dfs_reverse(node, path, all_paths):
            path.append(node)
            if len(reverse_graph[node]) == 0:
                all_paths.append(path.copy())
            else:
                for prev_node in reverse_graph[node]:
                    dfs_reverse(prev_node, path, all_paths)
            path.pop()

        all_paths = []
        dfs_reverse(target_node, [], all_paths)
        return all_paths

    @staticmethod
    def gen_node_level(graph) -> Dict[str, int]:
        levels = {}

        def assign_level(node):
            if node in levels:
                return levels[node]

            if node not in graph:
                levels[node] = 0
                return 0

            max_level = max((assign_level(child) for child in graph[node]), default=-1) + 1
            levels[node] = max_level
            return max_level

        for node in set(graph).union(set().union(*graph.values())):
            if node not in levels:
                assign_level(node)

        return levels

    @staticmethod
    def gen_dependency_chart_info(block: str, version: str, dependency_dic: Dict[str, str]) -> Tuple[Dict[str, List[str]], List[Dict[str, str]], List[Dict[str, str]]]:
        """
        Args:
            block: block,
            version: version,
            dependency_dic: ex {'task1': 'task2&task3|task4, task5'}
        Returns:
            flow_chart_dic: ex {'task1': ['task2', '& link', '| link'], ...}
            node_list: ex [{'id': <node_id>, 'label': <node_name>}, ...]
            edge_list: ex [{'from': <start_node_id>, 'to': <end_node_id>}, ...]
        """
        flow_chart_dic = {}
        node_list = []
        edge_list = []
        tag = f'{block}-{version}'

        # basic element
        for node in dependency_dic.keys():
            if not re.match(r'^\s+$', node):
                flow_chart_dic.setdefault(node, [])
                node_list.append({'id': f'{tag}-{node}',
                                  'label': node,
                                  'size': 100,
                                  'shape': 'box',
                                  })

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
                        node_list.append({'id': f'{tag}-{str(link_node)}',
                                          'label': '&',
                                          'size': 20,
                                          'shape': 'text',
                                          'disableContextMenu': True,
                                          'color': {'background': 'lightgrey',
                                                    'border': 'grey',
                                                    'highlight': 'lightgrey',
                                                    'hover': 'lightgrey'},
                                          'font': {'size': 20, 'vadjust': 0}
                                          })
                        flow_chart_dic.setdefault(str(link_node), [])
                        first_link_node = str(link_node)

                        for first_item in first_condition_list:
                            edge_list.append({'from': f'{tag}-{first_item}', 'to': f'{tag}-{str(link_node)}'})
                            flow_chart_dic.setdefault(first_item, [])
                            flow_chart_dic[first_item].append(str(link_node))
                    else:
                        continue

                    link_node += 1
                    first_link_list.append(first_link_node)

                if len(first_link_list) == 1:
                    second_link_node = first_link_list[0]
                elif len(first_link_list) > 1:
                    node_list.append({'id': f'{tag}-{str(link_node)}',
                                      'label': '|',
                                      'size': 20,
                                      'shape': 'text',
                                      'disableContextMenu': 'true',
                                      'color': {'background': 'lightgrey',
                                                'border': 'grey',
                                                'highlight': 'lightgrey',
                                                'hover': 'lightgrey'},
                                      'font': {'size': 20, 'vadjust': 0}
                                      })
                    flow_chart_dic.setdefault(str(link_node), [])
                    second_link_node = str(link_node)

                    for second_item in first_link_list:
                        edge_list.append({'from': f'{tag}-{second_item}', 'to': f'{tag}-{str(link_node)}'})
                        flow_chart_dic[second_item].append(str(link_node))
                else:
                    continue

                link_node += 1
                second_link_list.append(second_link_node)

            for third_link_node in second_link_list:
                edge_list.append({'from': f'{tag}-{third_link_node}', 'to': f'{tag}-{node}'})
                flow_chart_dic.setdefault(third_link_node, [])
                flow_chart_dic[third_link_node].append(node)

        return flow_chart_dic, node_list, edge_list

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
                    common_pyqt5.Dialog(title, info)
                    return check_status

        return check_status

    def gen_table(self):
        self.current_table.setMouseTracking(True)

        # table format
        self.current_table.setSortingEnabled(True)
        self.current_table.verticalHeader().setVisible(False)
        self.current_table.horizontalHeader().setVisible(True)

        # table row & column setting
        self.current_table.setColumnCount(4)
        self.current_table.setHorizontalHeaderLabels(['task', 'add', 'del', 'run_after'])

        # table.setColumnWidth(0, 80)
        self.current_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.current_table.setColumnWidth(1, 25)
        self.current_table.setColumnWidth(2, 25)
        self.current_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.current_table.setSortingEnabled(False)

        # table menu for add repeat setting
        self.current_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.current_table.customContextMenuRequested.connect(functools.partial(self.generate_table_menu, self.current_table))

    def _update_table(self):
        if isinstance(self.current_table, QTableWidget):
            self.current_table.clear()

        self.current_table.setHorizontalHeaderLabels(['task', 'add', 'del', 'run_after'])

        if not self.current_dependency_priority_dic:
            return

        # table context
        row_len = 0
        item_condition_dic = {}
        dependency_item_list = []
        item_condition_mapping = {}

        dependency_dic = copy.deepcopy(self.current_dependency_priority_dic)

        for key in self.default_dependency_dic:
            if key not in dependency_dic:
                dependency_dic[key] = self.default_dependency_dic[key]

        item_list = list(dependency_dic.keys())

        for item in item_list:
            item_condition_dic.setdefault(item, {})
            dependency_item_list = [task for task in dependency_dic.keys()]
            condition = dependency_dic[item]

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

        self.current_table.setRowCount(row_len)
        row = 0

        not_selectable_items = []

        for item in item_condition_dic.keys():
            item_name, _ = self.get_item_name(item)

            if item_name in self.current_dependency_priority_dic:
                continue

            not_selectable_items.append(item_name)

        for item in item_condition_dic.keys():
            item_name, _ = self.get_item_name(item)
            item_is_default = False if item_name in self.current_dependency_priority_dic else True

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

                    if item_is_default or not self.gui_enable_flag:
                        add_item.setFlags(add_item.flags() & ~Qt.ItemIsEditable)

                    self.current_table.setItem(row, 1, add_item)
                else:
                    name_item = QTableWidgetItem(item_name)

                    if dependency_dic.get(item_name) != self.default_dependency_dic.get(item_name):
                        name_item.setForeground(QBrush(EDIT_COLOR))

                    if self.mode == 'widget':
                        modify_tuple = ('%s-%s-flow' % (self.current_block, self.current_version), item_name)

                        if modify_tuple in self.modify_item_set:
                            name_item.setForeground(QBrush(QColor(100, 149, 237)))
                            name_item.setFont(QFont('Calibri', 10, 500))

                    name_item.setWhatsThis(item)
                    name_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                    add_item = QPushButton('+')
                    add_item.setDown(False)

                    if item_is_default or not self.gui_enable_flag:
                        add_item.setEnabled(False)

                    self.current_table.setCellWidget(row, 1, add_item)
                    add_item.clicked.connect(functools.partial(self.add_condition, item))

                delete_item = QPushButton('-')
                delete_item.setDown(False)

                if item_is_default:
                    dependency_item = QLineEdit('&'.join(item_condition_dic[item][parallel_condition]))
                    dependency_item.setEnabled(False)
                else:
                    dependency_item = common_pyqt5.QComboCheckBox(self.current_table)
                    dependency_item.setEditLineSeparator(separator='&')

                    dependency_item.addCheckBoxItems(selectable_item_list)
                    dependency_item.setItemsCheckStatus(item_condition_dic[item][parallel_condition])
                    dependency_item.setItemsCheckState(item_list=not_selectable_items, state=False)
                    dependency_item.stateChangedconnect(functools.partial(self.change_condition_dependency_list, dependency_item, item, same_item_line))

                    if not self.gui_enable_flag:
                        dependency_item.setItemsCheckEnable(False)

                name_item.setToolTip(r'%s' % item_condition_mapping[item])

                if item_is_default:
                    name_item.setForeground(QColor(169, 169, 169))

                self.current_table.setItem(row, 0, name_item)

                if not self.gui_enable_flag or item_is_default:
                    delete_item.setEnabled(False)

                self.current_table.setCellWidget(row, 2, delete_item)
                self.current_table.setCellWidget(row, 3, dependency_item)
                row += 1
                same_item_line += 1

                # table signal
                delete_item.clicked.connect(functools.partial(self.delete_condition, item, parallel_condition))

    @staticmethod
    def get_item_name(item):
        if my_match := re.match(r'(\S+)\s+-\s+(\d+)', item):
            item_name = my_match.group(1)
            item_num = int(my_match.group(2)) - 1
        else:
            item_name = item
            item_num = 0
        return item_name, item_num

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

    def add_condition(self, item_text=''):
        if not item_text:
            return

        item_name, item_num = self.get_item_name(item_text)
        repeat_condition_list = self.current_dependency_priority_dic[item_name].split(',')
        new_repeat_condition = '|'.join([repeat_condition_list[item_num], ''])
        new_repeat_condition_list = [repeat_condition_list[i] if i != item_num else new_repeat_condition for i in range(len(repeat_condition_list))]
        self.current_dependency_priority_dic[item_name] = ','.join(new_repeat_condition_list)
        self.update_dependency_show_info(modify_item=item_name)

        self.dependency_priority_dic[self.current_block][self.current_version] = self.current_dependency_priority_dic

    def delete_condition(self, item='', delete_condition=''):
        if not item:
            return

        item_name, item_num = self.get_item_name(item)
        repeat_condition_list = self.current_dependency_priority_dic[item_name].split(',')
        parallel_condition_list = repeat_condition_list[item_num].split('|')
        condition_list = []

        for condition in parallel_condition_list:
            if condition != delete_condition:
                condition_list.append(condition)

        new_repeat_condition = '|'.join(condition_list)
        new_repeat_condition_list = [repeat_condition_list[i] if i != item_num else new_repeat_condition for i in range(len(repeat_condition_list))]

        self.current_dependency_priority_dic[item_name] = ','.join(new_repeat_condition_list)
        self.update_dependency_show_info(modify_item=item_name)
        self.dependency_priority_dic[self.current_block][self.current_version] = self.current_dependency_priority_dic

    def change_condition_dependency_list(self,
                                         dependency_item,
                                         item='',
                                         condition_num=0):
        dependency_item_list = [item for index, item in dependency_item.selectedItems().items()]
        dependency_condition = '&'.join(dependency_item_list)
        condition_dic = {}

        item_name, item_num = self.get_item_name(item)
        repeat_condition_list = self.current_dependency_priority_dic[item_name].split(',')
        repeat_condition = repeat_condition_list[item_num]

        for i in range(len(repeat_condition.split('|'))):
            parallel_condition = repeat_condition.split('|')[i]

            if condition_num == i:
                condition_dic[dependency_condition] = ''
            else:
                condition_dic[parallel_condition] = ''

        new_repeat_condition = '|'.join(list(condition_dic.keys()))
        new_repeat_condition_list = [repeat_condition_list[i] if i != item_num else new_repeat_condition for i in range(len(repeat_condition_list))]

        new_dependency_dic = {**self.default_dependency_dic, **self.current_dependency_priority_dic, item_name: ','.join(new_repeat_condition_list)}
        check_status = self.check_dependency_setting(new_dependency_dic)

        if check_status:
            self.current_dependency_priority_dic[item_name] = ','.join(new_repeat_condition_list)

        self.update_dependency_show_info(modify_item=item_name)
        self.dependency_priority_dic[self.current_block][self.current_version] = self.current_dependency_priority_dic

    def generate_table_menu(self, table, pos):
        if not self.gui_enable_flag:
            return

        current_selected_row = table.currentIndex().row()
        current_selected_column = table.currentIndex().column()

        if current_selected_column != 0:
            return

        current_selected_item = table.item(current_selected_row, current_selected_column).whatsThis().strip()
        item_name, _ = self.get_item_name(current_selected_item)

        if not item_name:
            return

        if item_name in self.current_dependency_priority_dic:
            menu = QMenu()
            add_action = menu.addAction('Add Another Condition')
            add_action.triggered.connect(functools.partial(self.add_repeat_dependency, current_selected_item))

            delete_action = menu.addAction('Delete Current Condition')

            if item_name == current_selected_item:
                delete_action.setDisabled(True)

            delete_action.triggered.connect(functools.partial(self.delete_repeat_dependency, current_selected_item))

            reset_action = menu.addAction('Reset To Default Condition')
            reset_action.triggered.connect(functools.partial(self.reset_to_default_condition, current_selected_item))

            menu.exec_(table.mapToGlobal(pos))

    def add_repeat_dependency(self, item=''):
        if not item:
            return

        item_name, item_num = self.get_item_name(item)
        new_repeat_condition_list = self.current_dependency_priority_dic[item_name].split(',')
        new_repeat_condition_list.append('')

        self.current_dependency_priority_dic[item_name] = ','.join(new_repeat_condition_list)
        self.dependency_priority_dic[self.current_block][self.current_version] = self.current_dependency_priority_dic
        self.update_dependency_show_info(modify_item=item_name)

    def delete_repeat_dependency(self, item=''):
        if not item:
            return

        item_name, item_num = self.get_item_name(item)
        new_repeat_condition_list = []

        for condition in self.current_dependency_priority_dic[item_name].split(','):
            if condition != self.current_dependency_priority_dic[item_name].split(',')[item_num]:
                new_repeat_condition_list.append(condition)

        self.current_dependency_priority_dic[item_name] = ','.join(new_repeat_condition_list)
        self.update_dependency_show_info(modify_item=item_name)

        self.dependency_priority_dic[self.current_block][self.current_version] = self.current_dependency_priority_dic

    def reset_to_default_condition(self, item: str = ''):
        if not item:
            return

        item_name, item_num = self.get_item_name(item)
        self.current_dependency_priority_dic[item_name] = self.default_dependency_dic.get(item_name, '')
        self.update_dependency_show_info(modify_item=item_name)
        self.dependency_priority_dic[self.current_block][self.current_version] = self.current_dependency_priority_dic

    def update_dependency_show_info(self, modify_item=None, modify_item_list=None):
        if modify_item is not None:
            self.modify_item_set.add((r'%s-%s-task' % (self.current_block, self.current_version), modify_item))

        if modify_item_list is not None:
            for item in modify_item_list:
                self.modify_item_set.add((r'%s-%s-task' % (self.current_block, self.current_version), item))

        self._update_table()
        self._update_dependency_chart()

        if self.mode == 'widget':
            if self.modify_item_set:
                self.save_button.setEnabled(True)
                self.update.emit(True, 'Order')

    def dfs_check_loop(self, node, flow_chart_dic):
        check_status = True

        if node in self.vis:
            if node in self.trace:
                title = 'Warning'
                info = 'Dependencies contains a loop!'
                common_pyqt5.Dialog(title, info)
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
        self.post_dependency_check()
        self.message.emit(self.update_flag, self.dependency_priority_dic)
        self.origin_dependency_priority_dic = copy.deepcopy(self.dependency_priority_dic)

        if self.mode == 'window':
            self.close()
        elif self.mode == 'widget':
            self.modify_item_set = set()
            self.update_ui()
            self.save_button.setEnabled(False)
            self.update.emit(False, 'Order')

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
        # self.current_dependency_priority_dic = self.dependency_priority_dic[self.current_block][self.current_version]
        self.modify_item_set = set()
        self.update_setting(dependency_priority_dic=self.dependency_priority_dic, default_dependency_dic=self.default_dependency_dic)
        self.update.emit(False, 'Order')

    def disable_gui(self):
        self.gui_enable_flag = False
        self.reset_to_default_button.setEnabled(False)
        self.reset_to_default_button.setStyleSheet('QPushButton {color: gray;}')
        self.update_table_frame()

    def enable_gui(self):
        self.gui_enable_flag = True
        self.reset_to_default_button.setEnabled(True)
        self.reset_to_default_button.setStyleSheet('QPushButton {color: black;}')
        self.update_table_frame()


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

        if user in config.default_yaml_administrators:
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
        self.table.mousePressEvent = self.table_mouse_press_event
        self.main_label = QLabel()
        self.env_table = QTableWidget()
        self.env_label = QLabel()

        if self.window == 'config':
            self.table.setContextMenuPolicy(Qt.CustomContextMenu)
            self.table.customContextMenuRequested.connect(self.generate_table_menu)

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

        common_pyqt5.center_window(self)

        return self

    def table_mouse_press_event(self, event):
        if event.button() == Qt.RightButton:
            item = self.table.itemAt(event.pos())
            if item is None:
                self.table.clearSelection()

        # Call original mousePressEvent
        QTableWidget.mousePressEvent(self.table, event)

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
                value = str(value)

                # if key in self.common_var_set:
                #    continue

                if key not in self.common_var_set:
                    comment = 'Default variables set by admin,  can be edited for yourself but cannot be deleted'
                else:
                    comment = 'User redefined variables, different from default variable, it could be edited.'
                    value = self.user_var[key]

                key_item = QTableWidgetItem(key)
                key_item.setFlags(key_item.flags() & ~Qt.ItemIsEditable)
                key_item.setForeground(QBrush(QColor(125, 125, 125)))
                value_item = QTableWidgetItem(value)

                if self.window == 'config':
                    # comment_item = QTableWidgetItem('Default variables set by admin,  can be edited for yourself but cannot be deleted')
                    comment_item = QTableWidgetItem(comment)
                    comment_item.setFlags(key_item.flags() & ~Qt.ItemIsEditable)
                    comment_item.setForeground(QBrush(QColor(192, 192, 192)))

                    if key.strip() == 'BSUB_QUEUE' or key.strip() == 'MAX_RUNNING_JOBS':
                        key_item.setFlags(key_item.flags() & ~Qt.ItemIsEditable)
                        value_item.setFlags(value_item.flags() & ~Qt.ItemIsEditable)
                        key_item.setForeground(QBrush(QColor(125, 125, 125)))
                        value_item.setForeground(QBrush(QColor(125, 125, 125)))
                        comment_item = QTableWidgetItem(f'Modify {key.strip()} in Setting -> Cluster Management')
                        comment_item.setFlags(comment_item.flags() & ~Qt.ItemIsEditable)
                        comment_item.setForeground(QBrush(QColor(192, 192, 192)))

                    self.table.setItem(row, 2, comment_item)
                elif self.window == 'edit_task':
                    value_item.setFlags(value_item.flags() & ~Qt.ItemIsEditable)

                self.table.setItem(row, 0, key_item)
                self.table.setItem(row, 1, value_item)
                row += 1

            for key, value in self.user_var.items():
                if key in self.common_var_set:
                    continue

                value = str(value)
                key_item = QTableWidgetItem(key)
                value_item = QTableWidgetItem(value)

                if key.strip() == 'BSUB_QUEUE' or key.strip() == 'MAX_RUNNING_JOBS':
                    key_item.setFlags(key_item.flags() & ~Qt.ItemIsEditable)
                    value_item.setFlags(value_item.flags() & ~Qt.ItemIsEditable)
                    key_item.setForeground(QBrush(QColor(125, 125, 125)))
                    value_item.setForeground(QBrush(QColor(125, 125, 125)))
                    comment_item = QTableWidgetItem(f'Modify {key.strip()} in Setting -> Cluster Management')
                else:
                    comment_item = QTableWidgetItem('User customized variables, it could be edited/added/deleted')

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
                value = str(value)
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
            self.table.itemChanged.connect(self.on_item_changes)

        self.main_layout.addWidget(self.table)

        env_dic = common.get_env_dic()
        env_dic = {k: env_dic[k] for k in sorted(env_dic)}
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
            value = str(value)
            key_item = QTableWidgetItem(key)
            key_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            key_item.setForeground(QBrush(QColor(125, 125, 125)))

            value_item = QTableWidgetItem(value)
            value_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
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

        # Check if there's an item at the clicked position
        item = self.table.itemAt(pos)

        if not item:
            # No item at clicked position - show simple menu
            menu = QMenu()
            add_action = menu.addAction('Add Variable')
            add_action.triggered.connect(self.add_var)
        else:
            # Item exists - show full menu
            current_selected_item_row = item.row()
            current_selected_item = item.text()
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

    def return_table_dic(self):
        self.read_table()
        return self.table_dic

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
        self.save_button.setEnabled(False)

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

                if item.text() == 'BSUB_QUEUE' or item.text() == 'MAX_RUNNING_JOBS':
                    break

                item.setFlags(item.flags() | Qt.ItemIsEditable)

        self.table.itemChanged.connect(self.on_item_changes)


class WindowForAPI(QMainWindow):
    message = pyqtSignal(str, dict, str)
    update = pyqtSignal(bool, str)

    def __init__(self, api_yaml: str = 'api.yaml'):
        super().__init__()

        self.gui_enable_signal = True
        self.api_dic = common.parse_user_api(api_yaml)
        self.old_api_dic = copy.deepcopy(self.api_dic)

        self.title = 'API Setting'
        self.update_flag = 'API'
        self.user_api_yaml = os.path.join(common.get_user_ifp_config_path(), os.path.basename(api_yaml))
        self.general_api_yaml = common.get_default_yaml_path(key_word='api')
        self.api_item_list = ['Enable', 'Type', 'Label', 'Project', 'Group', 'Tab', 'Column', 'Path', 'Comment', 'Command',
                              'Block Name', 'Version Name', 'Flow Name', 'Task Name']
        self.api_item_button_dic = {}
        self.default_item_list = ['Enable', 'Type', 'Label', 'Project', 'Group']
        self.table_column_list = ['Enable', 'Type', 'Label', 'Project', 'Group', 'Tab', 'Column', 'Path', 'Command', 'Comment', 'Task_name',
                                  'Flow_name', 'Version_name', 'Block_name']
        self.api_order_list = ['Label', 'Enable', 'Type', 'Project', 'Group', 'Tab', 'Column', 'Path', 'Command', 'Comment', 'Task_name',
                               'Flow_name', 'Version_name', 'Block_name', 'API-2', 'GUI_BLOCKING', 'RELOAD', 'MENU_BAR_GROUP']
        self.label_index = 2
        self.column_button_count = 9

        self.top_widget = QWidget()
        self.top_layout = QVBoxLayout()
        self.main_widget = QWidget()
        self.main_layout = QVBoxLayout()
        self.button_widget = QWidget()
        self.button_layout = QHBoxLayout()

        self.table = QTableWidget()
        self.table_button = QWidget()
        self.save_button = QPushButton('SAVE')
        self.reset_button = QPushButton('RESET')

        self.api_edit_window = None

    def init_ui(self):
        # Top Layout
        self.setWindowTitle(self.title)
        self.top_widget.setLayout(self.top_layout)
        self.setCentralWidget(self.top_widget)
        self.top_layout.addWidget(self.main_widget)
        self.top_layout.addWidget(self.button_widget)
        self.top_layout.setStretch(0, 10)
        self.top_layout.setStretch(1, 1)

        # Main Layout
        self.main_widget.setLayout(self.main_layout)
        self.main_layout.setAlignment(Qt.AlignLeft)
        # self.main_layout.addWidget(self.table_button, 1)
        self.main_layout.addWidget(self.table, 10)

        # API table button
        for item in self.api_item_list:
            item = item.title()
            check_box = QCheckBox(item)
            check_box.clicked.connect(functools.partial(self.update_api_table, reset=False))

            if item in self.default_item_list:
                check_box.setCheckState(Qt.Checked)
                check_box.setEnabled(False)

            self.api_item_button_dic[item] = check_box

        row, column = 0, 0
        button_layout = QGridLayout(self.table_button)

        for item in self.api_item_button_dic:
            if column == self.column_button_count - 1:
                row += 1
                column = 0

            button_layout.addWidget(self.api_item_button_dic[item], row, column, Qt.AlignLeft)

            column += 1

        # API table
        self.table.setMouseTracking(True)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setVisible(True)
        self.table.horizontalHeader().setVisible(True)
        self.update_api_table()
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.generate_table_menu)

        # Button Layout
        self.save_button.clicked.connect(self.save)
        self.save_button.setEnabled(False)
        self.reset_button.clicked.connect(self.reset)
        self.button_widget.setLayout(self.button_layout)
        self.button_layout.addStretch(1)
        self.button_layout.addWidget(self.save_button)
        self.button_layout.addWidget(self.reset_button)

        common_pyqt5.center_window(self)

        return self

    def update_api_table(self, reset: bool = True):
        self.table.clear()

        self.table.setColumnCount(len(self.table_column_list))
        self.table.setHorizontalHeaderLabels(self.table_column_list)
        api_list = self.analysis_api(total_api_dic=self.api_dic)

        row = 0
        self.table.setRowCount(len(api_list))

        for api_dic in api_list:
            api_content = self.gen_api_content(api_dic)
            status_item = QCheckBox()

            if api_dic['ENABLE']:
                status_item.setCheckState(Qt.Checked)
            else:
                status_item.setCheckState(Qt.Unchecked)

            status_item.setStyleSheet("margin-left:25%;")
            status_item.setToolTip(api_content)

            self.table.setCellWidget(row, 0, status_item)
            status_item.stateChanged.connect(lambda state, row=row: self.table_status_changed(state, row))
            column = 1

            for item in self.table_column_list:
                item = item.upper()

                if item in api_dic:
                    table_item = QTableWidgetItem(api_dic[item])
                else:
                    table_item = QTableWidgetItem('')

                if item == 'ENABLE':
                    continue

                if not api_dic['ENABLE']:
                    table_item.setForeground(QBrush(QColor('grey')))

                table_item.setFlags(table_item.flags() & ~Qt.ItemIsEditable)
                table_item.setToolTip(api_content)

                self.table.setItem(row, column, table_item)
                column += 1

            row += 1

        self.table.resizeColumnsToContents()

    def generate_table_menu(self, pos):
        if not self.gui_enable_signal:
            return

        current_selected_row = self.table.currentIndex().row()
        current_selected_column = self.table.currentIndex().column()

        if self.table.item(current_selected_row, current_selected_column):
            current_selected_item_row = self.table.item(current_selected_row, current_selected_column).row()

            menu = QMenu()
            edit_action = menu.addAction('Add API')
            edit_action.triggered.connect(self.add_api)

            if self.table.item(current_selected_row, 1).text().strip().upper() in ['TABLE_RIGHT_KEY_MENU', 'PRE_IFP']:
                edit_action = menu.addAction('Edit API')
                edit_action.triggered.connect(functools.partial(self.edit_api, current_selected_item_row))

            delete_action = menu.addAction('Delete API')
            delete_action.triggered.connect(functools.partial(self.delete_api, current_selected_item_row))

            menu.exec_(self.table.mapToGlobal(pos))
        else:
            menu = QMenu()
            edit_action = menu.addAction('Add API')
            edit_action.triggered.connect(self.add_api)

            menu.exec_(self.table.mapToGlobal(pos))
            return

    def add_api(self):
        self.api_edit_window = WindowForAPIEdit(title='ADD API')
        self.api_edit_window.save_signal.connect(self.update_api_dic_after_edit)
        self.api_edit_window.show()

    def edit_api(self, row):
        api_dic, api_type = self._get_api_dic_from_row(row=row)

        if api_type not in ['TABLE_RIGHT_KEY_MENU', 'PRE_IFP']:
            return

        self.api_edit_window = WindowForAPIEdit('EDIT API', api_dic, api_type)
        self.api_edit_window.save_signal.connect(self.update_api_dic_after_edit)
        self.api_edit_window.show()

    def update_api_dic_after_edit(self, old_api_dic: dict, new_api_dic: dict, api_type: str):
        if not old_api_dic:
            same_label = 0

            for i, api_dic in enumerate(self.api_dic['API'][api_type]):
                if api_dic['LABEL'] == new_api_dic['LABEL']:
                    same_label += 1

            if same_label >= 1:
                QMessageBox.warning(self, 'Error', 'Please make sure that all API have <span style="color:red"> different labels </span>!', QMessageBox.Ok)
                return

            self.api_dic['API'].setdefault(api_type, [])
            self.api_dic['API'][api_type].append(new_api_dic)
        else:
            if api_type in self.api_dic['API']:
                old_api_label = old_api_dic['LABEL']
                temp_index = None
                same_label = 0

                for i, api_dic in enumerate(self.api_dic['API'][api_type]):
                    if api_dic['LABEL'] == old_api_label:
                        temp_index = i
                        same_label += 1

                if same_label > 1:
                    QMessageBox.warning(self, 'Error', 'Please make sure that all API have <span style="color:red"> labels </span>!', QMessageBox.Ok)
                    return

                if temp_index is not None:
                    self.api_dic['API'][api_type][temp_index] = new_api_dic
                else:
                    self.api_dic['API'][api_type].append(new_api_dic)

        self.update_api_table()
        self.reset_button.setEnabled(True)
        self.save_button.setEnabled(True)
        self.update.emit(True, self.update_flag)

    def _get_api_dic_from_row(self, row: int) -> Tuple[dict, str]:
        result_dic = {}
        result_type = ''
        api_label, api_type = '', ''

        # api label
        for index in range(self.table.columnCount()):
            column_name = self.table.horizontalHeaderItem(index).text()

            if column_name == 'Label':
                api_label = self.table.item(row, index).text().strip()
            elif column_name == 'Type':
                api_type = self.table.item(row, index).text().strip()

        if api_type in self.api_dic['API']:
            for index, api_dic in enumerate(self.api_dic['API'][api_type]):
                if api_dic['LABEL'] == api_label:
                    result_dic = api_dic
                    result_type = api_type
                    break

        return result_dic, result_type

    def delete_api(self, row: int):
        del_api_dic, del_api_type = self._get_api_dic_from_row(row=row)
        del_api_label = del_api_dic['LABEL']

        if del_api_type in self.api_dic['API']:
            del_api_index = None

            for index, api_dic in enumerate(self.api_dic['API'][del_api_type]):
                if api_dic['LABEL'] == del_api_label:
                    del_api_index = index
                    break

            if del_api_index is not None:
                self.api_dic['API'][del_api_type].pop(del_api_index)

        self.update_api_table()
        self.reset_button.setEnabled(True)
        self.save_button.setEnabled(True)
        self.update.emit(True, self.update_flag)

    def gen_api_content(self, api_dic: dict = None) -> str:
        if not api_dic or not isinstance(api_dic, dict):
            return ''

        content = '<table>'

        for column in self.table_column_list:
            if column.upper() in api_dic:
                content += '<tr><td><b>%s</b></td><td>%s</td></tr>' % (str(column.upper()), str(api_dic[column.upper()]))

        if 'API-2' in api_dic:
            content += '<tr><td><b>API-2</b></td><td></td></tr>'

            for i, api_2_dic in enumerate(api_dic['API-2']):
                for key, value in api_2_dic.items():
                    content += '<tr><td><b>{}---{}</b></td><td>{}</td></tr>'.format(str(i), str(key), str(value))

        return content

    def save(self, api_yaml: str = ''):
        if api_yaml:
            self.update_api_dic()
            self.message.emit(self.update_flag, self.api_dic, api_yaml)
        else:
            self.update_api_dic()
            self.message.emit(self.update_flag, self.api_dic, self.user_api_yaml)
            self.update.emit(False, self.update_flag)
            self.update_api_table()
            self.old_api_dic = copy.deepcopy(self.api_dic)

            self.save_button.setEnabled(False)

    def reset(self):
        self.api_dic = copy.deepcopy(self.old_api_dic)
        self.update_api_table()
        self.old_api_dic = copy.deepcopy(self.api_dic)
        self.save_button.setStyleSheet("")
        self.update.emit(False, self.update_flag)
        self.save_button.setEnabled(False)

    @staticmethod
    def analysis_api(total_api_dic=None):
        if not total_api_dic:
            return []

        api_list = []

        for api_type in ['TABLE_RIGHT_KEY_MENU', 'PRE_IFP', 'MENU_BAR', 'TOOL_BAR']:
            for api_dic in total_api_dic['API'][api_type]:
                api_dic['TYPE'] = api_type
                api_list.append(api_dic)

        return api_list

    def update_api_dic(self):
        row_count = self.table.rowCount()
        api_status_dic = {}

        for i in range(row_count):
            status = True if self.table.cellWidget(i, 0).checkState() == Qt.Checked else False
            label = self.table.item(i, self.label_index).text().strip()
            api_status_dic[label] = status

        for api_type in ['TABLE_RIGHT_KEY_MENU', 'PRE_IFP', 'MENU_BAR', 'TOOL_BAR']:
            if api_type not in self.api_dic['API']:
                continue

            for i in range(len(self.api_dic['API'][api_type])):
                self.api_dic['API'][api_type][i] = {k.upper(): self.api_dic['API'][api_type][i][k.upper()] for k in self.api_order_list if k.upper() in self.api_dic['API'][api_type][i]}
                label = self.api_dic['API'][api_type][i]['LABEL']

                if label in api_status_dic:
                    self.api_dic['API'][api_type][i]['ENABLE'] = api_status_dic[label]

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
        self.gui_enable_signal = False
        row_count = self.table.rowCount()

        for row in range(row_count):
            status_item = self.table.cellWidget(row, 0)
            status_item.setEnabled(False)

    def enable_gui(self):
        """
        Enable status_item in table
        """
        self.gui_enable_signal = True
        row_count = self.table.rowCount()

        for row in range(row_count):
            status_item = self.table.cellWidget(row, 0)
            status_item.setEnabled(True)


class WindowForAPIEdit(QMainWindow):
    save_signal = pyqtSignal(dict, dict, str)

    def __init__(self, title: str, api_dic: dict = None, api_type: str = None):
        super().__init__()

        self.title = title
        self.old_api_dic = {} if not api_dic else api_dic
        self.old_api_type = '' if not api_type else api_type
        self.temp_api_dic = copy.deepcopy(self.old_api_dic) if self.old_api_dic else {}

        if self.old_api_type == 'TABLE_RIGHT_KEY_MENU':
            if 'API-2' not in self.old_api_dic:
                self.temp_api_dic['API-2'] = []

            column_name = None

            for key in self.temp_api_dic.keys():
                if re.match(r'(\S+)_NAME', key):
                    column_name = key

            if column_name is None:
                column = self.temp_api_dic['COLUMN']
                self.temp_api_dic['{}_NAME'.format(column)] = ''

        self.current_api_type = self.old_api_type
        self.top_widget = QWidget()
        self.top_layout = QVBoxLayout()

        self.main_widget = QWidget()
        self.main_layout = QFormLayout()
        self.type_widget = None
        self.api_type_dic = {'PRE_IFP': ['LABEL', 'PROJECT', 'GROUP', 'PATH', 'COMMAND', 'ENABLE', 'COMMENT'],
                             'TABLE_RIGHT_KEY_MENU': ['LABEL', 'TAB', 'PROJECT', 'GROUP', 'PATH', 'COLUMN', 'ENABLE', 'COMMAND', 'COMMENT', 'API-2'],
                             }
        self.api_2_type_list = ['LABEL', 'ENABLE', 'COMMAND', 'COMMENT', 'PATH']
        self.column_name_list = ['TASK', 'FLOW', 'VERSION', 'BLOCK']
        self.tab_name_list = ['MAIN', 'CONFIG']
        self.enable_name_list = ['True', 'False']
        self.key_order_list = ['LABEL', 'TAB', 'PROJECT', 'GROUP', 'ENABLE', 'COLUMN', 'PATH', 'COMMAND', 'COMMENT', 'TASK_NAME', 'API-2',
                               'FLOW_NAME', 'VERSION_NAME', 'BLOCK_NAME']
        self.must_have_list = {'PRE_IFP': ['LABEL', 'PATH', 'COMMAND'],
                               'TABLE_RIGHT_KEY_MENU': ['LABEL', 'PATH', 'COMMAND'],
                               'API-2': ['LABEL', 'COMMAND']}
        self.api_widget_dic = {}

        self.button_widget = QWidget()
        self.button_layout = QHBoxLayout()
        self.save_button = QPushButton('SAVE')
        self.cancel_button = QPushButton('CANCEL')

        self._init_ui()

    def _ordered_api_dic(self):
        ordered_dic = {}

        for key in self.key_order_list:
            if key in self.temp_api_dic:
                if key != 'API-2':
                    ordered_dic[key] = self.temp_api_dic[key]
                else:
                    ordered_dic[key] = []

                    for api_2_dic in self.temp_api_dic['API-2']:
                        new_api_2_dic = {}

                        for api_2_key in self.api_2_type_list:
                            if api_2_key in api_2_dic:
                                new_api_2_dic[api_2_key] = api_2_dic[api_2_key]

                        ordered_dic[key].append(new_api_2_dic)

        self.temp_api_dic = ordered_dic

    def _init_ui(self):
        self._ordered_api_dic()
        self.setMinimumSize(QSize(800, 500))
        self.setCentralWidget(self.top_widget)
        self.setWindowTitle(self.title)

        scroll_area = QScrollArea()
        scroll_area.setWidget(self.main_widget)
        scroll_area.setWidgetResizable(True)

        # Top widget
        self.top_widget.setLayout(self.top_layout)
        self.top_layout.addWidget(scroll_area, 10)
        self.top_layout.addWidget(self.button_widget, 1)

        # Setting
        self.main_widget.setLayout(self.main_layout)

        if self.old_api_type:
            self.type_widget = QLabel(self.old_api_type)
            self.current_api_type = self.old_api_type
        else:
            self.type_widget = QComboBox()
            self.type_widget.addItems(list(self.api_type_dic.keys()))
            self.type_widget.currentTextChanged.connect(self._update_main_widget)
            self.current_api_type = self.type_widget.currentText().strip()

        self.main_layout.addRow('API Type', self.type_widget)
        self._update_main_widget()

        # Button
        self.button_widget.setLayout(self.button_layout)
        self.save_button.clicked.connect(self.save)
        self.cancel_button.clicked.connect(self.close)
        self.button_layout.addStretch(1)
        self.button_layout.addWidget(self.save_button)
        self.button_layout.addWidget(self.cancel_button)

        common_pyqt5.center_window(self)

    def _update_main_widget(self):
        while self.main_layout.rowCount() > 1:
            self.main_layout.removeRow(1)

        self.api_widget_dic = {'API Type': self.type_widget}

        if isinstance(self.type_widget, QComboBox):
            api_type = self.type_widget.currentText().strip()

            if api_type != self.current_api_type and api_type in self.api_type_dic:
                self.temp_api_dic = {key: '' for key in self.api_type_dic[api_type]}

                if api_type != 'PRE_IFP':
                    self.temp_api_dic['{}_NAME'.format(self.column_name_list[0])] = ''

                self.current_api_type = api_type

        if not self.temp_api_dic:
            self._update_main_widget_for_init()
        else:
            self._update_main_widget_for_edit()

    def _update_main_widget_for_init(self):
        api_type = self.type_widget.currentText().strip()

        if api_type not in self.api_type_dic:
            return
        else:
            self.temp_api_dic = {key: '' for key in self.api_type_dic[api_type]}
            self._update_basic_main_widget()

    def _update_main_widget_for_edit(self):
        self._update_basic_main_widget()

        if 'API-2' in self.temp_api_dic:
            self.api_widget_dic.setdefault('API-2-DICT', {})

            for index, api_2_dic in enumerate(self.temp_api_dic['API-2']):
                api_2_label = api_2_dic['LABEL']
                self.api_widget_dic['API-2-DICT'].setdefault(api_2_label, {})
                delete_button = QPushButton('DELETE')
                delete_button.setMaximumSize(100, 40)
                delete_button.clicked.connect(functools.partial(self._delete_api_2, label=api_2_label))
                self.main_layout.addRow(r'API-2 [{}]'.format(str(index)), delete_button)
                self.api_widget_dic['API-2-DICT'][api_2_label]['DELETE'] = delete_button

                for api_2_item in api_2_dic:
                    if api_2_item == 'ENABLE':
                        api_2_widget = QComboBox2()
                        api_2_widget.addItems(self.enable_name_list)
                        api_2_widget.setCurrentText(str(self.temp_api_dic[api_2_item]))
                    elif api_2_item == 'PATH':
                        path = str(api_2_dic[api_2_item]) if str(api_2_dic[api_2_item]) else self.temp_api_dic['PATH']
                        api_2_widget = QLineEdit(path)
                    else:
                        api_2_widget = QLineEdit(str(api_2_dic[api_2_item]))

                    label = QLabel(api_2_item)

                    if api_2_item in self.must_have_list['API-2']:
                        label.setStyleSheet("color: red; font-weight: bold")

                    self.main_layout.addRow(label, api_2_widget)
                    self.api_widget_dic['API-2-DICT'][api_2_label][api_2_item] = api_2_widget

    def _update_basic_main_widget(self):
        column = ''

        for api_item in self.temp_api_dic:
            api_content = self.temp_api_dic[api_item] if self.temp_api_dic[api_item] else ''

            if api_item == 'API-2':
                api_widget = QPushButton('ADD API-2')
                api_widget.setMaximumSize(100, 40)
                api_widget.clicked.connect(self._add_api_2)
            elif api_item == 'COLUMN':
                api_widget = QComboBox2()
                api_widget.addItems([''] + self.column_name_list)
                api_widget.setCurrentText(self.temp_api_dic[api_item])
            elif api_item == 'TAB':
                api_widget = QComboBox2()
                api_widget.addItems([''] + self.tab_name_list)
                api_widget.setCurrentText(self.temp_api_dic[api_item])
            elif api_item == 'ENABLE':
                api_widget = QComboBox2()
                api_widget.addItems(self.enable_name_list)
                api_widget.setCurrentText(str(self.temp_api_dic[api_item]))
            else:
                if re.match(r'(\S+)_NAME', api_item) and self.temp_api_dic[api_item]:
                    column = re.match(r'(\S+)_NAME', api_item).group(1)

                api_widget = QLineEdit(str(api_content))

            label = QLabel(api_item)

            if api_item in self.must_have_list[self.current_api_type]:
                label.setStyleSheet("color: red; font-weight: bold")

            self.main_layout.addRow(label, api_widget)
            self.api_widget_dic[api_item] = api_widget

        if 'COLUMN' in self.temp_api_dic:
            if column:
                self.api_widget_dic['COLUMN'].setCurrentText(column)

            self._change_column_name()
            self.api_widget_dic['COLUMN'].currentTextChanged.connect(self._change_column_name)

    def _read_temp_api(self, api_2: bool = False):
        old_temp_api_dic = copy.deepcopy(self.temp_api_dic)
        self.temp_api_dic = {}

        if api_2:
            if 'API-2' in old_temp_api_dic:
                self.temp_api_dic['API-2'] = old_temp_api_dic['API-2']

        for api_item in self.api_widget_dic:
            api_value = self.api_widget_dic[api_item]

            if isinstance(api_value, QLineEdit):
                self.temp_api_dic[api_item] = api_value.text().strip() if api_value.text() else ''
            elif isinstance(api_value, QComboBox):
                self.temp_api_dic[api_item] = api_value.currentText().strip() if api_value.currentText() else ''
            elif api_item == 'API-2-DICT':
                self.temp_api_dic.setdefault('API-2', [])

                for api_2_label in self.api_widget_dic['API-2-DICT']:
                    api_2_dic = {}

                    for api_2_item in self.api_widget_dic['API-2-DICT'][api_2_label]:
                        api_2_value = self.api_widget_dic['API-2-DICT'][api_2_label][api_2_item]

                        if isinstance(api_2_value, QLineEdit):
                            api_2_dic[api_2_item] = api_2_value.text() if api_2_value.text() else ''
                        elif isinstance(api_2_value, QComboBox):
                            api_2_dic[api_2_item] = api_2_value.currentText().strip() if api_2_value.currentText() else 'False'

                    self.temp_api_dic['API-2'].append(api_2_dic)

        self._ordered_api_dic()

    def _check_temp_api(self) -> bool:
        for item in self.must_have_list[self.current_api_type]:
            if 'API-2' in self.temp_api_dic and self.temp_api_dic['API-2']:
                for api_2_dic in self.temp_api_dic['API-2']:
                    for item_2 in self.must_have_list['API-2']:
                        if not api_2_dic[item_2]:
                            return False

                if item in ['COMMAND']:
                    continue

            if not self.temp_api_dic.get(item):
                return False

        return True

    def _delete_api_2(self, label: str):
        self._read_temp_api()
        api_2_list = []
        old_api_2_dic = {}

        if 'API-2' in self.temp_api_dic:
            for api_2_dic in self.temp_api_dic['API-2']:
                api_label = api_2_dic['LABEL']

                if api_label != label:
                    api_2_list.append(api_2_dic)
                else:
                    old_api_2_dic = api_2_dic

            self.temp_api_dic['API-2'] = api_2_list

        if not api_2_list:
            for key in list(self.temp_api_dic.keys()):
                if re.match(r'\S+_NAME', key):
                    del self.temp_api_dic[key]

            self.temp_api_dic['PATH'] = old_api_2_dic['PATH']
            self.temp_api_dic['COMMAND'] = old_api_2_dic['COMMAND']

        self._update_main_widget()

    def _add_api_2(self):
        self._read_temp_api()
        api_2_new_dic = {item: '' for item in self.api_2_type_list}

        if 'API-2' in self.temp_api_dic and self.temp_api_dic['API-2']:
            api_2_count = len(self.temp_api_dic['API-2'])
            api_2_new_dic['LABEL'] = self._generate_new_label(api_dic=self.temp_api_dic, count=api_2_count)
            self.temp_api_dic['API-2'].append(api_2_new_dic)
        else:
            api_2_new_dic['LABEL'] = 'API-2 [0]'
            api_2_new_dic['PATH'] = self.temp_api_dic['PATH']
            api_2_new_dic['COMMAND'] = self.temp_api_dic.get('COMMAND', '')
            self.temp_api_dic['API-2'] = [api_2_new_dic, ]

            if self.temp_api_dic.get('COMMAND'):
                del self.temp_api_dic['COMMAND']

            column = self.api_widget_dic['COLUMN'].currentText().strip()
            column_name = '{}_NAME'.format(column)
            self.temp_api_dic[column_name] = ''

        self._update_main_widget()

    def _change_column_name(self):
        column = self.api_widget_dic['COLUMN'].currentText().strip()
        column_name = '{}_NAME'.format(column) if column else 'COLUMN_NAME'
        self._read_temp_api(api_2=True)

        if column_name in self.temp_api_dic:
            return

        column_value = ''

        for key in list(self.temp_api_dic.keys()):
            if re.match(r'\S+_NAME', key):
                column_value = self.temp_api_dic[key]
                del self.temp_api_dic[key]

        self.temp_api_dic[column_name] = column_value

        for row in range(self.main_layout.rowCount()):
            label = self.main_layout.itemAt(row, QFormLayout.LabelRole).widget()

            if re.match(r'\S+_NAME', label.text()) and column_name != label:
                self.api_widget_dic[column_name] = self.api_widget_dic[label.text()]
                self.api_widget_dic.pop(label.text())
                label.setText(column_name)

    def _generate_new_label(self, api_dic: dict, count: int = 0) -> str:
        api_new_label = r'API-2[{}]'.format(str(count))

        for api_2_dic in self.temp_api_dic['API-2']:
            api_2_label = api_2_dic['LABEL']

            if api_2_label == api_new_label:
                self._generate_new_label(api_dic=api_dic, count=count + 1)

        return api_new_label

    def save(self):
        self._read_temp_api()
        check = self._check_temp_api()

        if not check:
            QMessageBox.warning(self, 'Error', 'Please make sure that all items marked as <span style="color:red"> red </span> have been filled in!', QMessageBox.Ok)
            return

        if 'API-2' in self.temp_api_dic and not self.temp_api_dic['API-2']:
            del self.temp_api_dic['API-2']

        self.save_signal.emit(self.old_api_dic, self.temp_api_dic, self.current_api_type)
        self.close()


class WindowForTaskInformation(QMainWindow):
    show_sig = pyqtSignal(bool)

    def __init__(self, task_obj: job_manager.TaskObject = None, user_config_obj: UserConfig = None, read_only: bool = False):
        super().__init__()
        self.task_obj = task_obj
        self.user_config_obj = user_config_obj
        self.read_only = read_only
        self.default_widget = 800
        self.default_height = 800

        self.title = '%s/%s/%s/%s' % (self.task_obj.block, self.task_obj.version, self.task_obj.flow, self.task_obj.task)
        self.title = '{}  (Read Only)'.format(self.title) if self.read_only else '{}'.format(self.title)
        self.setWindowTitle(self.title)

        self.cache_path = self.user_config_obj.info_cache_path.format_map({'BLOCK': self.task_obj.block,
                                                                           'VERSION': self.task_obj.version,
                                                                           'FLOW': self.task_obj.flow,
                                                                           'TASK': self.task_obj.task})
        self.cache = self._load_cache()
        self._load_cache()

        self.top_widget = QTabWidget()
        self.setCentralWidget(self.top_widget)

        self.detailed_task_window = None
        self.detailed_job_window = None
        self.detailed_log_window = None

        self.init_ui()

        self.resize_dic = {0: (800, 800), 1: (800, 800), 2: (800, 800)}
        common_pyqt5.auto_resize(self, self.default_widget, self.default_height)
        center(self)

    def _load_cache(self) -> TaskCache:
        os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)

        if not os.path.exists(self.cache_path):
            cache = TaskCache()
        else:
            try:
                with open(self.cache_path, 'r') as cf:
                    task_dic = json.load(cf)
            except Exception:
                task_dic = {}

            cache = TaskCache(run=TaskRunCache(**(task_dic.get('run', {}))),
                              log=TaskLogCache(**(task_dic.get('log', {}))),
                              block=task_dic.get('block'),
                              version=task_dic.get('version'),
                              flow=task_dic.get('flow'),
                              task=task_dic.get('task'))

        return cache

    def _save_cache(self):
        task_cache = TaskCache(block=self.task_obj.block,
                               version=self.task_obj.version,
                               flow=self.task_obj.flow,
                               task=self.task_obj.task,
                               timestamp=int(datetime.datetime.now().timestamp()),
                               run=self.detailed_job_window.export_cache(),
                               log=self.detailed_log_window.export_cache(),
                               )

        with open(self.cache_path, 'w') as cf:
            cf.write(json.dumps(asdict(task_cache)))

    def init_ui(self):
        # Detailed Task Info
        self.detailed_task_window = WindowForTaskConfig(blank_setting=self.user_config_obj.blank_setting,
                                                        task_obj=self.task_obj,
                                                        read_only=self.read_only)
        self.detailed_task_window.resize_signal.connect(self.resize_window)
        self.detailed_task_window.close_signal.connect(self.close_window)

        # Task Job Info
        self.detailed_job_window = WindowForTaskJobInfo(task_obj=self.task_obj, user_obj=self.user_config_obj, cache=self.cache)

        # Task Log Info
        log_files = self.user_config_obj.task_setting[self.task_obj.block][self.task_obj.version][self.task_obj.flow][self.task_obj.task].get('RUN', {}).get('LOG', [])
        log_files = log_files if log_files else self.user_config_obj.default_setting.get(self.task_obj.task, {}).get('RUN', {}).get('LOG', [])
        log_file_list = []

        if isinstance(log_files, str):
            log_file_list = [log_files, ]
        elif isinstance(log_files, list):
            log_file_list = copy.deepcopy(log_files)

        for i in range(len(log_file_list)):
            log_file_list[i] = custom_format_map(str(log_file_list[i]), {**self.user_config_obj.ifp_obj.config_obj.var_dic, **{'BLOCK': self.task_obj.block, 'VERSION': self.task_obj.version, 'FLOW': self.task_obj.flow, 'TASK': self.task_obj.task}})

            if not os.path.isabs(log_file_list[i]):
                log_file_list[i] = os.path.join(self.task_obj.task_obj.PATH if self.task_obj.task_obj.PATH else os.getcwd(), log_file_list[i])

            log_file_list[i] = custom_format_map(str(log_file_list[i]), {**self.user_config_obj.ifp_obj.config_obj.var_dic, **{'BLOCK': self.task_obj.block, 'VERSION': self.task_obj.version, 'FLOW': self.task_obj.flow, 'TASK': self.task_obj.task}})

        self.detailed_log_window = WindowForTaskLogInfo(task_obj=self.task_obj, log_files=log_file_list, cache=self.cache)

        self.top_widget.addTab(self.detailed_task_window, 'Detailed Setting')
        self.top_widget.addTab(self.detailed_job_window, 'Job Info')
        self.top_widget.addTab(self.detailed_log_window, 'Log')
        self.top_widget.currentChanged.connect(functools.partial(self.resize_window))

    def resize_window(self, width: int = 0, height: int = 0):
        tab_index = self.top_widget.currentIndex()

        if width and height:
            common_pyqt5.auto_resize(self, width, height)
            self.resize_dic[tab_index] = (width, height)
        else:
            width, height = self.resize_dic[tab_index]
            common_pyqt5.auto_resize(self, width, height)

    def close_window(self, close: True):
        if close is True:
            self.close()
        else:
            self.clean_thread()

    def closeEvent(self, a0):
        self.clean_thread()
        self._save_cache()
        self.show_sig.emit(False)
        super().closeEvent(a0)

    def clean_thread(self):
        if isinstance(self.detailed_job_window.timer, QTimer):
            self.detailed_job_window.timer.stop()

        if isinstance(self.detailed_job_window.job_check_thread, TaskJobCheckWorker):
            if self.detailed_job_window.job_check_thread.isRunning():
                self.detailed_job_window.job_check_thread.terminate()

        if isinstance(self.detailed_job_window.refresh_thread, TaskJobCheckWorker):
            if self.detailed_job_window.refresh_thread.isRunning():
                self.detailed_job_window.refresh_thread.terminate()

        if isinstance(self.detailed_log_window.gvim_thread, TaskLogViewer):
            if self.detailed_log_window.gvim_thread.isRunning():
                self.detailed_log_window.gvim_thread.terminate()


class TaskLogViewer(QThread):

    def __init__(self, file_path: str):
        super().__init__()
        self.file_path = file_path
        self.cmd = f'/bin/gvim {self.file_path}'
        self.process = QProcess()
        self.gvim_id = 0

    def run(self):
        self.process.start(self.cmd)
        self.gvim_id = self.find_child_processes(target_pid=self.process.processId())

    def terminate(self):
        super().terminate()

        if self.gvim_id:
            try:
                os.kill(self.gvim_id, 9)
            except Exception:
                return

    def isRunning(self):
        return True

    def find_child_processes(self, target_pid, check_interval: int = 2):
        try:
            target_process = psutil.Process(target_pid)
            start_time = target_process.create_time()
        except psutil.NoSuchProcess:
            return 0

        try:
            while True:
                for proc in psutil.process_iter(['pid', 'create_time', 'cmdline']):
                    if proc.info['create_time'] > start_time and self.cmd.split() == proc.info['cmdline']:
                        return proc.pid
                if time.time() - start_time > check_interval:
                    break
        except KeyboardInterrupt:
            print("Monitoring stopped.")

        return 0


class WindowForTaskJobInfo(QMainWindow):

    def __init__(self, task_obj: job_manager.TaskObject, user_obj: UserConfig, cache: TaskCache):
        super().__init__()
        self.task_obj = task_obj
        self.user_obj = user_obj
        self.cache = cache
        self.refresh_list = [3, 10, 30, 60]
        self.refresh_interval = self.refresh_list[0]
        self.refresh_button_list = []
        self.refresh_thread = None
        self.job_id = None
        self.job_type = None
        self.job_check_thread = None

        # GUI
        self.top_widget = QWidget()
        self.top_layout = QVBoxLayout()
        self.setCentralWidget(self.top_widget)

        # Button
        self.button_widget = QWidget()
        self.button_layout = QHBoxLayout()
        self.refresh_button_group = QButtonGroup()

        # Main
        self.main_widget = QWidget()
        self.main_layout = QGridLayout()
        self.job_task_line = QLineEdit()
        self.job_task_line.setReadOnly(True)
        self.job_refresh_button = QPushButton('Refresh')
        self.job_refresh_button.clicked.connect(self.refresh)
        self.job_refresh_button.setEnabled(False)
        self.job_state_line = QLineEdit()
        self.job_state_line.setReadOnly(True)
        self.job_bmonitor_button = QPushButton('Launch LsfMonitor')
        self.job_bmonitor_button.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/logo/monitor.ico'))
        self.job_bmonitor_button.clicked.connect(self._open_bmonitor)
        self.job_id_line = QLineEdit()
        self.job_id_line.setReadOnly(True)
        self.job_cmd_line = QTextEdit()
        self.job_cmd_line.setReadOnly(True)
        self.job_cwd_line = QLineEdit()
        self.job_cwd_line.setReadOnly(True)
        self.job_cwd_term_button = QPushButton('Open Terminal')
        self.job_cwd_term_button.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/other/terminal.png'))
        self.job_msg_line = QTextBrowser()
        self.job_msg_line.setReadOnly(True)
        self.job_msg_line.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.job_msg_line.setOpenExternalLinks(True)
        self.job_msg_line.setOpenLinks(False)
        self.job_msg_line.anchorClicked.connect(self.open_url)
        self.job_sub_time_line = QLineEdit()
        self.job_sub_time_line.setReadOnly(True)
        self.job_run_time_line = QLineEdit()
        self.job_run_time_line.setReadOnly(True)
        self.job_fin_time_line = QLineEdit()
        self.job_fin_time_line.setReadOnly(True)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(self.refresh_interval * 1000)

        self.init_ui()
        self.refresh()

    @staticmethod
    def open_url(url):
        try:
            if os.path.isdir(url.toLocalFile()):

                command = str('/bin/dbus-launch /bin/gnome-terminal --tab -- bash -c' + ' "cd ' + url.toLocalFile() + '; exec ' + str(os.environ['SHELL']) + '"; exit')
                subprocess.Popen(command, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            else:
                subprocess.Popen('gvim -geometry 160x30 %s' % url.toLocalFile(), shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except Exception as error:
            print(error)
            print(traceback.format_exc())

    def init_ui(self):
        # Top Layout
        frame = QFrame()
        frame.setFrameShape(QFrame.HLine)
        frame.setFrameShadow(QFrame.Sunken)

        self.top_widget.setLayout(self.top_layout)
        self.top_layout.addWidget(self.main_widget, 50)
        self.top_layout.addStretch(1)
        self.top_layout.addWidget(frame)
        self.top_layout.addWidget(self.button_widget, 1)

        # Button
        flash_label = QLabel('Refresh(s)', self.main_widget)
        flash_label.setStyleSheet("font-weight: bold;")
        flash_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.button_widget.setLayout(self.button_layout)
        self.button_layout.addStretch(2)
        self.button_layout.addWidget(flash_label, 2, Qt.AlignRight)

        for index, flash in enumerate(self.refresh_list):
            flash_button = QRadioButton(str(flash))
            flash_button.clicked.connect(self._reset_refresh)
            self.refresh_button_list.append(flash_button)
            self.refresh_button_group.addButton(flash_button, index)

        flash_button = QRadioButton('Manual')
        flash_button.clicked.connect(self._reset_refresh)
        self.refresh_button_list.append(flash_button)
        self.refresh_button_group.addButton(flash_button, len(self.refresh_button_list) + 1)

        self.refresh_button_group.button(0).setChecked(True)

        for i in range(len(self.refresh_button_list)):
            self.button_layout.addWidget(self.refresh_button_list[i], 1)

        self.button_layout.addStretch(20)
        self.button_layout.addWidget(self.job_refresh_button)

        # Main Layout
        for i in range(6):
            self.main_layout.setColumnStretch(i, 1)

        for i in range(40):
            self.main_layout.setRowStretch(i, 1)

        self.main_widget.setLayout(self.main_layout)
        self.job_cwd_term_button.clicked.connect(self._open_xterm)

        job_task_label = QLabel('Task Name')
        job_task_label.setStyleSheet("font-weight: bold;")
        job_task_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        job_id_label = QLabel('Job ID')
        job_id_label.setStyleSheet("font-weight: bold;")
        job_id_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        job_state_label = QLabel('State')
        job_state_label.setStyleSheet("font-weight: bold;")
        job_state_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        job_exit_code_label = QLabel('Exit Code')
        job_exit_code_label.setStyleSheet("font-weight: bold;")
        job_exit_code_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        job_cmd_label = QLabel('Command')
        job_cmd_label.setStyleSheet("font-weight: bold;")
        job_cmd_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        job_cwd_label = QLabel('Working Path')
        job_cwd_label.setStyleSheet("font-weight: bold;")
        job_cwd_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        job_msg_label = QLabel('Message')
        job_msg_label.setStyleSheet("font-weight: bold;")
        job_msg_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        job_sub_time_label = QLabel('Submit Time')
        job_sub_time_label.setStyleSheet("font-weight: bold;")
        job_sub_time_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        job_run_time_label = QLabel('Run Time')
        job_run_time_label.setStyleSheet("font-weight: bold;")
        job_run_time_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        job_fin_time_label = QLabel('Finish Time')
        job_fin_time_label.setStyleSheet("font-weight: bold;")
        job_fin_time_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.main_layout.addWidget(job_id_label, 1, 0)
        self.main_layout.addWidget(self.job_id_line, 1, 1)
        self.main_layout.addWidget(job_state_label, 1, 2)
        self.main_layout.addWidget(self.job_state_line, 1, 3)
        self.main_layout.addWidget(self.job_bmonitor_button, 1, 5)
        self.main_layout.addWidget(job_sub_time_label, 2, 0)
        self.main_layout.addWidget(self.job_sub_time_line, 2, 1)
        self.main_layout.addWidget(job_run_time_label, 2, 2)
        self.main_layout.addWidget(self.job_run_time_line, 2, 3)
        self.main_layout.addWidget(job_fin_time_label, 2, 4)
        self.main_layout.addWidget(self.job_fin_time_line, 2, 5)
        self.main_layout.addWidget(job_cwd_label, 3, 0)
        self.main_layout.addWidget(self.job_cwd_line, 3, 1, 1, 4)
        self.main_layout.addWidget(self.job_cwd_term_button, 3, 5)
        self.main_layout.addWidget(job_cmd_label, 4, 0)
        self.main_layout.addWidget(self.job_cmd_line, 4, 1, 1, 5)
        self.main_layout.addWidget(job_msg_label, 5, 0, 1, 1)
        self.main_layout.addWidget(self.job_msg_line, 5, 1, 40, 5)

        self.main_layout.setColumnStretch(0, 1)
        self.main_layout.setColumnStretch(1, 4)
        self.main_layout.setColumnStretch(2, 2)
        self.main_layout.setColumnStretch(3, 4)
        self.main_layout.setColumnStretch(4, 2)
        self.main_layout.setColumnStretch(5, 4)

    def _open_bmonitor(self):
        """
        View job information with tool 'lsfMonitor'.
        """
        job_id = self.job_id_line.text().strip()

        if not job_id:
            return

        bmonitor_location = shutil.which('bmonitor')
        bmonitor = bmonitor_location

        if not bmonitor_location:
            bmonitor = str(os.environ['IFP_INSTALL_PATH']) + '/tools/lsfMonitor/monitor/bin/bmonitor'

        if os.path.exists(bmonitor):
            command = str(bmonitor) + ' --disable_license -j ' + str(job_id)
            self.user_obj.ifp_obj.run_monitor(command, str(job_id))
        else:
            QMessageBox.warning(self, 'LSF Monitor Warning', 'Not find "bmonitor" on system.')

    @property
    def new_refresh_interval(self) -> str:
        for button in self.refresh_button_list:
            if not button.isChecked():
                continue

            return button.text()

    def _reset_refresh(self):
        if my_match := re.match(r'^(\d+)$', self.new_refresh_interval):
            self.job_refresh_button.setEnabled(False)
            new_interval = int(my_match.group(1))
            self.timer.stop()

            if not self.timer.isActive():
                self.timer.start(new_interval * 1000)
        else:
            self.job_refresh_button.setEnabled(True)
            self.timer.stop()

            if self.timer.isActive():
                self.timer.stop()

    def _get_history_job_id(self) -> Tuple[bool, str, dict]:
        job_id = ''
        find = False
        job_info = {}

        try:
            if os.path.exists(self.user_obj.history_cache_path):
                df = self.tail_csv_with_headers(filename=self.user_obj.history_cache_path)
                filtered_df = df[(df['block'] == self.task_obj.block) &
                                 (df['version'] == self.task_obj.version) &
                                 (df['flow'] == self.task_obj.flow) &
                                 (df['task'] == self.task_obj.task)]

                job_info = filtered_df.to_dict(orient='records')

                if not filtered_df.empty:
                    max_index = filtered_df['timestamp'].idxmax()
                    job_id = filtered_df.loc[max_index, 'job_id']

                    if job_id:
                        find = True
        except Exception:
            return False, '', {}

        return bool(find), str(job_id), job_info

    @staticmethod
    def tail_csv_with_headers(filename: str, n: int = 1000) -> pd.DataFrame:
        with open(filename, 'r') as file:
            headers = next(file).strip().split(',')

        with open(filename, 'r') as file:
            last_lines = deque(file, n + 1)

        return pd.read_csv(io.StringIO(''.join(last_lines)), header=None, skiprows=1, names=headers)

    def _load_cache(self):
        find, job_id, job_info = self._get_history_job_id()

        if find:
            check, job_dic = TaskJobCheckWorker.check_job_id(job_id=f'b:{job_id}')

            if check:
                self.refresh_thread = TaskJobCheckWorker(**job_dic)
                self.refresh_thread.job_dic.connect(self._update_gui)
                self.refresh_thread.start()
                return

    def export_cache(self) -> TaskRunCache:
        if my_match := re.match(r'(.*)\((\d+)\)', self.job_state_line.text().strip()):
            status = my_match.group(1)
            exit_code = my_match.group(2)
        else:
            status = self.job_state_line.text().strip()
            exit_code = None

        return TaskRunCache(job_id=self.job_id_line.text().strip(),
                            status=status,
                            exit_code=exit_code,
                            finish_time=self.job_fin_time_line.text().strip(),
                            submit_time=self.job_sub_time_line.text().strip(),
                            run_time=self.job_run_time_line.text().strip(),
                            cwd=self.job_cwd_line.text().strip(),
                            cmd=self.job_cmd_line.toPlainText().strip(),
                            message=self.job_msg_line.toPlainText().strip(),
                            refresh_interval=self.new_refresh_interval,
                            timestamp=int(datetime.datetime.now().timestamp())
                            )

    def refresh(self):
        job_id = str(self.task_obj.action_progress[common.action.run].job_id) if self.task_obj.action_progress[common.action.run].job_id else str(self.task_obj.job_id)
        check, job_dic = TaskJobCheckWorker.check_job_id(job_id=job_id)
        progress_messages = self.task_obj.action_progress[common.action.run].progress_message

        try:
            working_path = self.task_obj.working_path if self.task_obj.working_path else ''
            run_shell = self.task_obj.task_run_shell if self.task_obj.task_run_shell else ''

            html_parts = []

            if working_path:
                html_parts.append(f'<div style="background-color: #f0f0f0;"><b>[Working Path]:</b> {working_path}</div>')

            if run_shell:
                html_parts.append(f'<div style="background-color: #f0f0f0;"><b>[Run Shell]:</b> {run_shell}</div>')

            if progress_messages:
                formatted_lines = []
                html_parts.append("<b>[Progress Message]:</b><br>")

                for line in progress_messages:
                    if line.startswith("[") and "]" in line:
                        tag_end = line.find("]") + 1
                        tag = line[:tag_end]
                        rest = line[tag_end:]
                        formatted_line = f"<b>{tag}</b>{rest}"
                    else:
                        formatted_line = f"{line}"
                    formatted_lines.append(formatted_line)
                html_parts.append(f"{'<br>'.join(formatted_lines)}")

            html_content = "\n".join(html_parts)
            self.job_msg_line.setHtml(html_content)
        except Exception:
            self.job_msg_line.setText(str('\n'.join(self.task_obj.action_progress[common.action.run].progress_message)))

        if not check:
            self._load_cache()
        else:
            self.refresh_thread = TaskJobCheckWorker(**job_dic)
            self.refresh_thread.job_dic.connect(self._update_gui)
            self.refresh_thread.start()

    def _update_gui(self, job_info: TaskJobInfo):
        self.job_id_line.setText(job_info.id)
        # self.job_exit_code_line.setText(job_info.exit_code)

        if job_info.state.lower() == 'exit':
            self.job_state_line.setText('{}({})'.format(job_info.state, job_info.exit_code))
        else:
            self.job_state_line.setText(job_info.state)

        self.job_sub_time_line.setText(job_info.submit_time)
        self.job_run_time_line.setText(job_info.run_time)
        self.job_fin_time_line.setText(job_info.finish_time)
        self.job_cwd_line.setText(job_info.cwd)

        run_method = self.user_obj.task_setting[self.task_obj.block][self.task_obj.version][self.task_obj.flow][self.task_obj.task].get('RUN', {}).get('RUN_METHOD', '')
        cmd = '{} {}'.format(custom_format_map(run_method, {**self.user_obj.ifp_obj.config_obj.var_dic, **{'BLOCK': self.task_obj.block,
                                                                                                           'VERSION': self.task_obj.version,
                                                                                                           'FLOW': self.task_obj.flow,
                                                                                                           'TASK': self.task_obj.task}}), job_info.cmd)
        self.job_cmd_line.setText(cmd)

    def _open_xterm(self):
        path = self.job_cwd_line.text().strip()

        if not os.path.exists(path):
            path = os.getcwd()

        command = str('/bin/dbus-launch /bin/gnome-terminal --tab -- bash -c' + ' "cd ' + path + '; exec ' + str(os.environ['SHELL']) + '"; exit')
        thread_run = common.ThreadRun()
        thread_run.run([command, ])


class WindowForTaskLogInfo(QMainWindow):
    def __init__(self, task_obj: job_manager.TaskObject, cache: TaskCache, log_files: List[str]):
        super().__init__()
        self.task_obj = task_obj
        self.log_files = log_files

        for log_file in log_files:
            if os.path.exists(log_file):
                self.file_path = log_file
                break
        else:
            self.file_path = ''

        self.cache = cache

        # GUI
        self.top_widget = QWidget()
        self.top_layout = QVBoxLayout()

        # Main
        self.main_widget = QWidget()
        self.main_layout = QGridLayout()

        self.log_path_combo = QComboBox()
        self.log_path_combo.setMaximumWidth(int(self.top_widget.width() * 0.9))
        self.log_path_combo.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        self.log_path_combo.setEditable(True)
        self.log_path_combo.addItems(self.log_files)
        self.log_path_combo.editTextChanged.connect(self._load_file)
        self.log_path_combo.currentIndexChanged.connect(self._load_file)

        self.log_file_search = QPushButton('Find')
        self.log_file_search.clicked.connect(self._open_file_to_check)

        self.error_type_line = QLineEdit('ERROR')
        self.error_num_line = QLineEdit('0')
        self.warn_type_line = QLineEdit('WARNING')
        self.warning_num_line = QLineEdit('0')
        self.error_warn_check_button = QPushButton('Check')
        self.error_warn_check_button.clicked.connect(self._check_error_and_warning)

        self.search_line = QLineEdit()
        self.search_line.returnPressed.connect(self._search_file)
        self.search_num = QLineEdit('0')
        self.search_case_button = ToggleButton('Cc')
        self.search_case_button.clicked.connect(self._search_file)
        self.search_regex_button = ToggleButton('.*')
        self.search_regex_button.clicked.connect(self._search_file)
        self.search_up_button = QPushButton('UP')
        self.search_up_button.clicked.connect(functools.partial(self._search_and_jump_file, backward=True))
        self.search_down_button = QPushButton('DOWN')
        self.search_down_button.clicked.connect(self._search_and_jump_file)
        self.search_check_button = QPushButton('Check')
        self.search_check_button.clicked.connect(self._search_file)

        self.jump_to_line_line = QLineEdit()
        self.jump_to_line_button = QPushButton('Go to Line')
        self.jump_to_line_button.clicked.connect(self._jump_to_line)

        self.file_editor = CodeEditor()

        self.gvim_button = QPushButton('Gvim')
        self.gvim_button.setIcon(QIcon(str(os.environ['IFP_INSTALL_PATH']) + '/data/pictures/logo/gvim.png'))
        self.gvim_button.clicked.connect(self._gvim_file)
        self.gvim_thread = None

        self.refresh_button = QPushButton('Refresh')
        self.refresh_button.clicked.connect(self._load_file)

        self._load_cache()
        self.init_ui()
        self._check_error_and_warning()

    def _load_cache(self):
        if self.cache.log.error:
            self.error_type_line.setText(self.cache.log.error)

        if self.cache.log.warning:
            self.warn_type_line.setText(self.cache.log.warning)

        if self.cache.log.search:
            self.search_line.setText(self.cache.log.search)

    def export_cache(self) -> TaskLogCache:
        return TaskLogCache(error=self.error_type_line.text().strip(),
                            warning=self.warn_type_line.text().strip(),
                            search=self.search_line.text().strip(),
                            log=self.log_path_combo.lineEdit().text().strip(),
                            timestamp=int(datetime.datetime.now().timestamp())
                            )

    def init_ui(self):
        # TOP
        self.top_widget.setLayout(self.top_layout)
        self.setCentralWidget(self.top_widget)
        self.top_layout.addWidget(self.main_widget)

        # Main
        file_label = QLabel('File')
        file_label.setStyleSheet("font-weight: bold;")
        file_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        error_name_label = QLabel('Error')
        error_name_label.setStyleSheet("font-weight: bold;")
        error_name_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        error_num_label = QLabel('Error Num')
        error_num_label.setStyleSheet("font-weight: bold;")
        error_num_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        warn_name_label = QLabel('Warning')
        warn_name_label.setStyleSheet("font-weight: bold;")
        warn_name_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        warn_num_label = QLabel('Warning Num')
        warn_num_label.setStyleSheet("font-weight: bold;")
        warn_num_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        search_label = QLabel('Search')
        search_label.setStyleSheet("font-weight: bold;")
        search_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        search_num_label = QLabel('Search Num')
        search_num_label.setStyleSheet("font-weight: bold;")
        search_num_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        jump_line_label = QLabel('Go to Line')
        jump_line_label.setStyleSheet("font-weight: bold;")
        jump_line_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.main_layout.addWidget(file_label, 0, 0)
        self.main_layout.addWidget(self.log_path_combo, 0, 1, 1, 6)
        self.main_layout.addWidget(self.log_file_search, 0, 7)
        self.main_layout.addWidget(self.gvim_button, 0, 8)
        self.main_layout.addWidget(error_name_label, 1, 0)
        self.main_layout.addWidget(self.error_type_line, 1, 1)
        self.main_layout.addWidget(error_num_label, 1, 2)
        self.main_layout.addWidget(self.error_num_line, 1, 3)
        self.main_layout.addWidget(warn_name_label, 1, 4)
        self.main_layout.addWidget(self.warn_type_line, 1, 5)
        self.main_layout.addWidget(warn_num_label, 1, 6)
        self.main_layout.addWidget(self.warning_num_line, 1, 7)
        self.main_layout.addWidget(self.error_warn_check_button, 1, 8)

        self.main_layout.addWidget(search_label, 2, 0)
        self.main_layout.addWidget(self.search_line, 2, 1)
        self.main_layout.addWidget(search_num_label, 2, 2)
        self.main_layout.addWidget(self.search_num, 2, 3)
        self.main_layout.addWidget(self.search_case_button, 2, 4)
        self.main_layout.addWidget(self.search_regex_button, 2, 5)
        self.main_layout.addWidget(self.search_up_button, 2, 6)
        self.main_layout.addWidget(self.search_down_button, 2, 7)
        self.main_layout.addWidget(self.search_check_button, 2, 8)
        self.main_layout.addWidget(jump_line_label, 3, 0)
        self.main_layout.addWidget(self.jump_to_line_line, 3, 1)
        # self.main_layout.addWidget(self.jump_to_line_button, 3, 2, 1, 7)
        self.main_layout.addWidget(self.jump_to_line_button, 3, 2)
        self.main_layout.addWidget(self.refresh_button, 3, 8)
        self.main_layout.addWidget(self.file_editor, 4, 0, 50, 9)

        self.main_layout.setColumnStretch(0, 1)
        self.main_layout.setColumnStretch(1, 3)
        self.main_layout.setColumnStretch(2, 3)
        self.main_layout.setColumnStretch(3, 3)
        self.main_layout.setColumnStretch(4, 3)
        self.main_layout.setColumnStretch(5, 3)
        self.main_layout.setColumnStretch(6, 3)
        self.main_layout.setColumnStretch(7, 3)
        self.main_layout.setColumnStretch(8, 3)
        self.main_widget.setLayout(self.main_layout)

        if os.path.exists(self.file_path):
            self._load_file()

    def _open_file_to_check(self):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(self,
                                                   "Open Log File", self.task_obj.task_obj.PATH if self.task_obj.task_obj.PATH else '',
                                                   "All Files (*);;Python Files (*.py)", options=options)

        self.file_path = file_path if os.path.exists(str(file_path)) else self.file_path
        self.log_path_combo.lineEdit().setText(self.file_path)

    def _load_file(self):
        log_file = self.log_path_combo.currentText().strip()

        # For Test
        if not os.path.exists(log_file):
            self.file_path = log_file
            self.file_editor.setPlainText("")
        else:
            self.file_path = log_file
            last_lines = self.read_last_lines(self.file_path, 10000)

            if len(last_lines) >= 10000:
                last_lines.insert(0, "Show last 10000 lines Only")

            self.file_editor.setPlainText("\n".join(last_lines))

    @staticmethod
    def read_last_lines(file_path, num_lines=10000, buffer_size=8192):
        if not os.path.isfile(file_path):
            return []

        with open(file_path, 'rb') as f:
            f.seek(0, os.SEEK_END)
            file_size = f.tell()
            block_end = file_size
            data = b''
            lines = []

            while block_end > 0 and len(lines) <= num_lines:
                block_start = max(0, block_end - buffer_size)
                f.seek(block_start)
                block = f.read(block_end - block_start)
                data = block + data
                lines = data.splitlines()
                block_end = block_start

            return [line.decode('utf-8', errors='replace') for line in lines[-num_lines:]]

    def _search_file(self):
        search_word = self.search_line.text().strip()

        if not search_word:
            return

        case_sensitive = self.search_case_button.is_toggled
        use_regex = self.search_regex_button.is_toggled
        search_num = os.popen('grep {} {} | wc -l'.format(search_word, self.file_path)).read().strip()
        self.file_editor.set_search_term(search_word, case_sensitive=case_sensitive, use_regex=use_regex)
        self.file_editor.searchText(search_word, case_sensitive=case_sensitive, use_regex=use_regex, backward=False)
        self.search_num.setText(str(search_num))

        self._load_file()

    def _search_and_jump_file(self, backward: bool = False):
        search_word = self.search_line.text().strip()
        case_sensitive = self.search_case_button.is_toggled
        use_regex = self.search_regex_button.is_toggled
        self.file_editor.searchText(search_word, case_sensitive=case_sensitive, use_regex=use_regex, backward=backward)

    def _jump_to_line(self):
        try:
            line_num = int(self.jump_to_line_line.text())
        except ValueError as error:
            line_num = 0
            print(f'Please input a number. Error: {str(error)}')

        self.file_editor.jumpToLogicLine(line_num)

    def _check_error_and_warning(self):
        if not os.path.exists(self.file_path) or not os.path.isfile(self.file_path):
            return

        error_name = self.error_type_line.text().strip()
        warn_name = self.warn_type_line.text().strip()

        error_result = os.popen('tail -10000 {} | grep {} | wc -l'.format(self.file_path, error_name)).read().strip()
        warn_result = os.popen('tail -10000 {} | grep {} | wc -l'.format(self.file_path, warn_name)).read().strip()
        self.error_num_line.setText(error_result)
        self.warning_num_line.setText(warn_result)

    def _gvim_file(self):
        if not os.path.exists(self.file_path):
            return

        if isinstance(self.gvim_thread, TaskLogViewer) and self.gvim_thread.isRunning():
            self.gvim_thread.terminate()

        self.gvim_thread = TaskLogViewer(file_path=self.file_path)
        self.gvim_thread.run()

    def resizeEvent(self, a0):
        super().resizeEvent(a0)

        total_width = 0

        for col in range(1, 7):
            rect = self.main_layout.cellRect(0, col)
            total_width += rect.width()

        if total_width > 0:
            self.log_path_combo.setFixedWidth(total_width)


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
        task = self.model().index(row, 3).data()

        if col == 3 and event.buttons() == Qt.MidButton:
            self.drag_row = row
            self.label.setText(task)
            self.drag_widget.show()
            self.drag_flag = True

        super(DraggableTableView, self).mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        row, col = self.indexAt(event.pos()).row(), self.indexAt(event.pos()).column()

        if col == 3 and self.drag_flag:
            self.drag_widget.move(event.pos())
            self.set_row_bg_color(row, QColor(254, 163, 86))
            self.set_row_bg_color(row + 1, QColor(255, 255, 255))
            self.set_row_bg_color(row - 1, QColor(255, 255, 255))

        super(DraggableTableView, self).mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        row, col = self.indexAt(event.pos()).row(), self.indexAt(event.pos()).column()

        if col == 3 and self.drag_flag:
            self.set_row_bg_color(row, QColor(255, 255, 255))
            self.drop_row = row
            raw_block = self.model().index(self.drag_row, 0).data()
            raw_version = self.model().index(self.drag_row, 1).data()
            raw_flow = self.model().index(self.drag_row, 2).data()
            raw_task = self.model().index(self.drag_row, 3).data()

            new_block = self.model().index(self.drop_row, 0).data()
            new_version = self.model().index(self.drop_row, 1).data()
            new_flow = self.model().index(self.drop_row, 2).data()
            new_task = self.model().index(self.drop_row, 3).data()

            if raw_block == new_block and raw_version == new_version and raw_flow == new_flow and not raw_task == new_task:
                self.exchange_flag.emit([raw_block, raw_version, raw_flow, raw_task, new_task])

        self.drag_widget.hide()
        self.drag_flag = False
        super(DraggableTableView, self).mouseReleaseEvent(event)

    def set_row_bg_color(self, row, color):
        if row < 0:
            return

        item = self.model().itemFromIndex(self.model().index(row, 3))

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


class CustomDelegate2(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)

    def paint(self, painter, option, index):
        value = index.model().data(index, Qt.DisplayRole)
        default_value = index.model().data(index, Qt.UserRole + 1)

        if value == default_value:
            try:
                painter.save()
                painter.setPen(QPen(Qt.black))
                font = option.font
                font.setItalic(True)
                painter.setFont(font)
                painter.drawText(option.rect, Qt.AlignLeft | Qt.AlignVCenter, value)
                painter.restore()
            except Exception as error:
                print(str(error))
                super().paint(painter, option, index)
        else:
            super().paint(painter, option, index)

    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.editingFinished.connect(lambda: self.commitAndCloseEditor(editor))
        return editor

    def setEditorData(self, editor, index):
        text = index.model().data(index, Qt.DisplayRole)
        editor.setText(text)

    def commitAndCloseEditor(self, editor):
        self.commitData.emit(editor)
        self.closeEditor.emit(editor)

    def setModelData(self, editor, model, index):
        text = editor.text()
        default_value = model.data(index, Qt.UserRole + 1)

        if text:
            model.setData(index, text, Qt.EditRole)
        else:
            model.setData(index, default_value, Qt.EditRole)


class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.codeEditor = editor

    def sizeHint(self):
        return QSize(self.editor.lineNumberAreaWidth(), 0)

    def paintEvent(self, event):
        self.codeEditor.lineNumberAreaPaintEvent(event)


class CodeEditor(QPlainTextEdit):
    def __init__(self):
        super().__init__()
        self.lineNumberArea = LineNumberArea(self)

        self.setReadOnly(True)
        self.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)

        self.document().contentsChanged.connect(self.updateLogicLineStarts)
        self.logicLineStarts = []
        self.search_term = ''
        self.case_sensitive = False
        self.use_regex = False

        self.document().contentsChanged.connect(self.updateTextCache)
        self.text_cache = self.toPlainText()

        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.cursorPositionChanged.connect(self.highlightCurrentLine)
        self.cursorPositionChanged.connect(self.search)
        self.updateLineNumberAreaWidth(0)

        self._searchSelections = []
        self._currentLineSelection = None

    def updateTextCache(self):
        self.text_cache = self.toPlainText()

    def lineNumberAreaWidth(self):
        digits = len(str(self.blockCount()))
        return 10 + self.fontMetrics().horizontalAdvance('9') * digits

    def updateLineNumberAreaWidth(self, _):
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

    def updateLineNumberArea(self, rect, dy):
        if dy:
            self.lineNumberArea.scroll(0, dy)
        else:
            self.lineNumberArea.update(0, rect.y(), self.lineNumberArea.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.updateLineNumberAreaWidth(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.lineNumberArea.setGeometry(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height())

    def lineNumberAreaPaintEvent(self, event):
        painter = QPainter(self.lineNumberArea)
        painter.fillRect(event.rect(), Qt.lightGray)

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(Qt.black)
                painter.drawText(
                    0, int(top), self.lineNumberArea.width(), self.fontMetrics().height(),
                    Qt.AlignRight, number
                )
            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            block_number += 1

    def highlightCurrentLine(self):
        selection = QTextEdit.ExtraSelection()
        line_color = QColor(Qt.yellow).lighter(160)
        selection.format.setBackground(line_color)
        selection.format.setProperty(QTextFormat.FullWidthSelection, True)
        selection.cursor = self.textCursor()
        selection.cursor.clearSelection()
        self._currentLineSelection = selection
        self._applySelections()

    def _applySelections(self):
        extras = []
        if self._currentLineSelection is not None:
            extras.append(self._currentLineSelection)
        if self._searchSelections:
            extras.extend(self._searchSelections)
        self.setExtraSelections(extras)

    def set_search_term(self, pattern, case_sensitive=False, use_regex=False):
        self.search_term = pattern
        self.case_sensitive = case_sensitive
        self.use_regex = use_regex

    def search(self):
        if not self.search_term:
            self._searchSelections = []
            self._applySelections()
            return

        cursor = self.textCursor()
        current_position = cursor.position()
        start = max(0, current_position - 10240)
        end = min(len(self.toPlainText()), current_position + 10240)

        text = self.text_cache[start:end]
        flags = 0 if self.case_sensitive else re.IGNORECASE

        if self.use_regex:
            matches = re.finditer(self.search_term, text, flags)
        else:
            pattern = re.escape(self.search_term)
            matches = re.finditer(pattern, text, flags)

        self._searchSelections = []
        fmt = QTextCharFormat()
        fmt.setBackground(QColor("yellow"))

        for m in matches:
            s = QTextEdit.ExtraSelection()
            s.format = fmt
            c = self.textCursor()
            c.setPosition(start + m.start())
            c.setPosition(start + m.end(), QTextCursor.KeepAnchor)
            s.cursor = c
            self._searchSelections.append(s)

        self._applySelections()

    def searchText(self, text, case_sensitive=False, use_regex=False, backward=False):
        search_flag = QTextDocument.FindFlags()
        if backward:
            search_flag |= QTextDocument.FindBackward
        if case_sensitive:
            search_flag |= QTextDocument.FindCaseSensitively

        cursor = self.textCursor()
        document = self.document()

        if use_regex:
            regex = QRegularExpression(text)
            regex.setPatternOptions(QRegularExpression.NoPatternOption if case_sensitive
                                    else QRegularExpression.CaseInsensitiveOption)
            found = cursor = document.find(regex, cursor, search_flag)
        else:
            found = self.find(text, search_flag)

        if not found:
            self.moveCursor(QTextCursor.End if backward else QTextCursor.Start)
            if use_regex:
                regex = QRegularExpression(text)
                found = document.find(regex, cursor, search_flag)
            else:
                found = self.find(text, search_flag)
        return found

    def clearHighlights(self):
        self._searchSelections = []
        self._applySelections()

    def highlightText(self, start_pos, end_pos):
        fmt = QTextCharFormat()
        fmt.setBackground(QColor("yellow"))
        sel = QTextEdit.ExtraSelection()
        c = self.textCursor()
        c.setPosition(start_pos)
        c.setPosition(end_pos, QTextCursor.KeepAnchor)
        sel.cursor = c
        sel.format = fmt
        self._searchSelections.append(sel)
        self._applySelections()

    def updateLogicLineStarts(self):
        text = self.toPlainText()
        self.logicLineStarts = [0]
        for i, ch in enumerate(text):
            if ch == '\n':
                self.logicLineStarts.append(i + 1)

    def jumpToLogicLine(self, lineNum):
        if lineNum < 1 or lineNum > len(self.logicLineStarts):
            return
        start_pos = self.logicLineStarts[lineNum - 1]
        cursor = self.textCursor()
        cursor.setPosition(start_pos)
        self.setTextCursor(cursor)


class ToggleButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.default_color = "background-color: lightgray"
        self.toggled_color = "background-color: lightgreen"
        self.setStyleSheet(self.default_color)
        self.is_toggled = False
        self.clicked.connect(self.toggle_color)

    def toggle_color(self):
        if self.is_toggled:
            self.setStyleSheet(self.default_color)
        else:
            self.setStyleSheet(self.toggled_color)
        self.is_toggled = not self.is_toggled


class ShrinkablePushButton(QPushButton):
    def sizeHint(self):
        original = super().sizeHint()
        return QSize(100, original.height())  # 限死宽度
