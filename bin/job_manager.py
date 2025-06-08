#!/ic/software/tools/python3/3.8.8/bin/python3
# -*- coding: utf-8 -*-
################################
# File Name   : job_manager.py
# Author      : jingfuyi
# Created On  : 2023-09-27 14:59:51
# Description :
################################
import datetime
import getpass
import os
import re
import sys
import threading
import time
import random
from typing import Dict

import requests
from PyQt5.QtCore import pyqtSignal, QThread, Qt, QTimer, QObject
from PyQt5.QtGui import QStandardItemModel, QStandardItem, QColor, QBrush
from PyQt5.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QTableView, QHeaderView

import common_lsf
import common_pyqt5

os.environ['PYTHONUNBUFFERED'] = '1'
sys.path.append(str(os.environ['IFP_INSTALL_PATH']) + '/common')
import common
import common_license
import common_db
import common_prediction

sys.path.append(str(os.environ['IFP_INSTALL_PATH']) + '/config')
import config as install_config


class AutoVivification(dict):
    def __getitem__(self, item):
        try:
            return dict.__getitem__(self, item)
        except KeyError:
            value = self[item] = type(self)()
            return value


def transfer_formula_to_list(formula):
    final_list = []
    if formula == '':
        return []

    for i in range(len(formula.split('|'))):
        for j in range(len(formula.split('|')[i].split('&'))):
            for k in range(len(formula.split('|')[i].split('&')[j].split(','))):
                final_list.append(formula.split('|')[i].split('&')[j].split(',')[k])

                if k < len(formula.split('|')[i].split('&')[j].split(',')) - 1:
                    final_list.append(',')

            if j < len(formula.split('|')[i].split('&')) - 1:
                final_list.append('&')
        if i < len(formula.split('|')) - 1:
            final_list.append('|')
    return final_list


def transfer_formula_list_to_task_equation(formula):
    new_formula_list = []

    if not formula:
        return new_formula_list

    for i in range(len(formula)):
        if formula[i] not in ['(', ')', '&', '|', '^']:
            if type(formula[i]) is list:
                if len(formula[i]) > 1:
                    new_formula_list.append('(')

                for j in range(len(formula[i])):
                    new_formula_list.append(formula[i][j].task)

                    if j < len(formula[i]) - 1:
                        new_formula_list.append('&')

                if len(formula[i]) > 1:
                    new_formula_list.append(')')
            else:
                new_formula_list.append(formula[i].task)
        else:
            new_formula_list.append(formula[i])

    return new_formula_list


def transfer_formula_list_to_bool_equation(task_obj, formula):
    new_formula_list = []

    if not formula:
        return new_formula_list

    for i in range(len(formula)):
        if formula[i] not in ['(', ')', '&', '|', ',']:
            if type(formula[i]) is list:
                if len(formula[i]) > 1:
                    new_formula_list.append('(')

                for j in range(len(formula[i])):
                    new_formula_list.append(task_obj.parent[formula[i][j]])

                    if j < len(formula[i]) - 1:
                        new_formula_list.append('&')

                if len(formula[i]) > 1:
                    new_formula_list.append(')')
            else:
                new_formula_list.append(task_obj.parent[formula[i]])
        else:
            new_formula_list.append(formula[i])

    return new_formula_list


class DebugWindow(QMainWindow):
    def __init__(self, debug=True):
        super().__init__()
        self.top_widget = QWidget()
        self.top_layout = QVBoxLayout()
        self.top_widget.setLayout(self.top_layout)
        self.setCentralWidget(self.top_widget)
        self.resize(2000, 800)
        self.setWindowTitle('Debug Window')

        self.table = QTableView()
        self.model = QStandardItemModel(0, 11)
        self.model.setHorizontalHeaderLabels(['Block', 'Version', 'Flow', 'Task', 'Equation', 'Bool Equation', 'Finish', 'Current Equation', 'Run Time', 'Action', 'Status'])
        self.table.setModel(self.model)
        self.table.setColumnWidth(4, 300)
        self.table.setColumnWidth(5, 150)
        self.table.setColumnWidth(7, 200)
        self.table.horizontalHeader().setSectionResizeMode(10, QHeaderView.Stretch)

        self.top_layout.addWidget(self.table)
        common_pyqt5.center_window(self)
        self.row_mapping = AutoVivification()
        self.debug = debug

    def update_gui(self, config_dic):
        row = 0
        for block in config_dic['BLOCK'].keys():
            for version in config_dic['BLOCK'][block].keys():
                for flow in config_dic['BLOCK'][block][version].keys():
                    for task in config_dic['BLOCK'][block][version][flow].keys():
                        self.model.setItem(row, 0, QStandardItem(block))
                        self.model.setItem(row, 1, QStandardItem(version))
                        self.model.setItem(row, 2, QStandardItem(flow))
                        self.model.setItem(row, 3, QStandardItem(task))
                        row += 1
                        self.table.setRowHeight(row, 100)

    def update_info(self, task_obj):
        if not self.debug:
            return

        run_times = list(task_obj.formula_list.keys())

        if not run_times:
            task_equation = ''
            bool_equation = ''
            current_equation = ''
            finish = ''
        else:
            task_equation = '\n'.join([''.join(transfer_formula_list_to_task_equation(task_obj.formula_list[i]['formula'])) + ' (' + str(task_obj.formula_list[i]['enable']) + ')' for i in run_times])
            bool_equation = '\n'.join([''.join(transfer_formula_list_to_bool_equation(task_obj, task_obj.formula_list[i]['formula'])) for i in run_times])
            current_equation = ''.join(transfer_formula_list_to_task_equation(task_obj.current_formula))
            finish = '\n'.join([str(task_obj.formula_list[i]['finish']) for i in run_times])

        self.model.setItem(self.row_mapping[task_obj], 4, QStandardItem(task_equation))
        self.model.setItem(self.row_mapping[task_obj], 5, QStandardItem(bool_equation))
        self.model.setItem(self.row_mapping[task_obj], 6, QStandardItem(finish))
        self.model.setItem(self.row_mapping[task_obj], 7, QStandardItem(current_equation))
        self.model.setItem(self.row_mapping[task_obj], 8, QStandardItem(str(task_obj.current_run_times)))
        self.model.setItem(self.row_mapping[task_obj], 9, QStandardItem(task_obj.action if task_obj.action else ''))

        status = task_obj.status if task_obj.status else ''
        item = QStandardItem(status)
        color = None
        if re.search(r'pass', status, flags=re.I):
            color = QColor(0, 204, 68)
        elif re.search(r'fail', status, flags=re.I):
            color = Qt.red
        elif re.search(r'undefined', status, flags=re.I):
            color = QColor(133, 51, 255)
        elif re.search(r'ing', status, flags=re.I):
            color = QColor(255, 153, 0)
        elif re.search(r'queue', status, flags=re.I):
            color = QColor(51, 153, 255)
        elif re.search(r'kill', status, flags=re.I):
            color = Qt.red

        if color:
            item.setForeground(QBrush(color))

        self.model.setItem(self.row_mapping[task_obj], 10, item)


class JobManager(QThread):
    disable_gui_signal = pyqtSignal(bool)
    finish_signal = pyqtSignal(str, str, str, str)
    close_signal = pyqtSignal()

    def __init__(self, ifp_obj, debug=False):
        super().__init__()
        self.ifp_obj = ifp_obj
        self.config_dic = None
        self.all_tasks = AutoVivification()
        self.monitor_flag = False
        self.send_result_flag = False
        self.close_flag = False
        self.current_running_jobs = 0

        # Define QTimer
        timer = QTimer(self)
        timer.start(1000)
        timer.timeout.connect(self.launch_task)

        self.debug = debug
        self.debug_window = DebugWindow(self.debug)

        if self.debug:
            self.debug_window.show()

    def record_formula(self, task_obj=None, task_formula=None, formula=None, run_time=None):
        task_obj.formula_list.setdefault(run_time, {})
        task_obj.formula_list[run_time]['task_formula'] = task_formula
        task_obj.formula_list[run_time]['formula'] = formula
        task_obj.formula_list[run_time]['enable'] = False
        task_obj.formula_list[run_time]['finish'] = False
        for item in formula:
            if item not in ['(', ')', '|', '&']:
                if type(item) is list:
                    for child_item in item:

                        if isinstance(child_item, TaskObject) and task_obj not in child_item.child:
                            child_item.child.append(task_obj)
                else:
                    if isinstance(item, TaskObject) and task_obj not in item.child:
                        item.child.append(task_obj)

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

    def update(self, config_dic):

        self.config_dic = config_dic

        row = 0

        total_tasks = AutoVivification()
        for block in self.config_dic['BLOCK'].keys():
            for version in self.config_dic['BLOCK'][block].keys():
                total_tasks[block][version] = []

                for flow in self.config_dic['BLOCK'][block][version].keys():
                    for task in self.config_dic['BLOCK'][block][version][flow].keys():
                        total_tasks[block][version].append(task)

                        if self.all_tasks[block][version][flow][task] == {}:
                            task_obj = TaskObject(self.config_dic, block, version, flow, task, self.ifp_obj, self.debug_window, self)
                            task_obj.update_status_signal.connect(self.ifp_obj.update_task_status)
                            task_obj.msg_signal.connect(self.ifp_obj.update_message_text)
                            task_obj.send_result_signal.connect(self.ifp_obj.send_result_to_user)
                            task_obj.set_one_jobid_signal.connect(self.ifp_obj.update_main_table_item)
                            task_obj.set_run_time_signal.connect(self.ifp_obj.update_main_table_item)
                            task_obj.update_debug_info_signal.connect(self.debug_window.update_info)
                            self.all_tasks[block][version][flow][task] = task_obj
                            self.debug_window.row_mapping[task_obj] = row
                        else:
                            self.all_tasks[block][version][flow][task].config_dic = config_dic
                            self.debug_window.row_mapping[self.all_tasks[block][version][flow][task]] = row

                        row += 1
        # update parent/child/formula
        for block in self.config_dic['BLOCK'].keys():
            for version in self.config_dic['BLOCK'][block].keys():
                # No repeated tasks belongs to specific block/version
                for flow in self.config_dic['BLOCK'][block][version].keys():
                    for task in self.config_dic['BLOCK'][block][version][flow].keys():

                        if self.all_tasks[block][version][flow][task].action:
                            continue

                        # run_after_task = []
                        task_formula = []

                        if self.config_dic['BLOCK'][block][version][flow][task].get('RUN_AFTER', {}).get('TASK', {}):
                            run_after = self.clean_dependency(item_list=total_tasks[block][version], item=task, dependency=self.config_dic['BLOCK'][block][version][flow][task]['RUN_AFTER']['TASK'])
                            # run_after_task = set(run_after.replace('|', '&').replace(',', '&').split('&'))
                            task_formula = transfer_formula_to_list(run_after)

                        for prepositive_task in task_formula:
                            if prepositive_task in ['', '&', '|', ',']:
                                continue

                            for flow2 in self.config_dic['BLOCK'][block][version].keys():
                                for task2 in self.config_dic['BLOCK'][block][version][flow2].keys():
                                    if prepositive_task == task2:

                                        task_obj = self.all_tasks[block][version][flow2][prepositive_task]

                                        if task_obj not in self.all_tasks[block][version][flow][task].parent.keys():
                                            self.all_tasks[block][version][flow][task].parent[task_obj] = 'True'

                                        task_formula[task_formula.index(prepositive_task)] = task_obj

                        task_object = self.all_tasks[block][version][flow][task]
                        task_object.formula_list = {}
                        task_formula_child = []
                        run_time = 1
                        if not len(task_formula) == 0:
                            for j in range(len(task_formula)):
                                task_obj = task_formula[j]

                                if not task_obj == ',' and not j == len(task_formula) - 1:
                                    task_formula_child.append(task_obj)
                                    continue

                                if j == len(task_formula) - 1:
                                    task_formula_child.append(task_obj)

                                formula = task_formula_child
                                self.record_formula(task_obj=task_object, task_formula=task_formula_child, formula=formula, run_time=run_time)
                                run_time += 1
                                task_formula_child = []

                        self.debug_window.update_info(task_object)

        self.debug_window.update_gui(self.config_dic)

    def receive_action(self, action_name, task_dic_list, run_all_steps=False):
        self.disable_gui_signal.emit(True)
        self.monitor_flag = True

        if not self.pre_check(action_name, task_dic_list):
            self.disable_gui_signal.emit(False)
            return

        self.refresh_parent_state_for_child_task(action_name, task_dic_list)
        self.send_action(action_name, task_dic_list, run_all_steps=run_all_steps)

        if action_name in common.action.run:
            self.send_result_flag = True

    def pre_check(self, action_name, task_dic_list):
        total_selected_tasks = []
        for line in task_dic_list:
            block = line['Block']
            version = line['Version']
            flow = line['Flow']
            task = line['Task']
            task_obj = self.all_tasks[block][version][flow][task]
            total_selected_tasks.append(task_obj)

        for line in task_dic_list:
            block = line['Block']
            version = line['Version']
            flow = line['Flow']
            task = line['Task']
            task_obj = self.all_tasks[block][version][flow][task]
            # Check

            # 1. Can't insert prepositive tasks
            if action_name in [common.action.run]:

                def flatten(lst):
                    result = []
                    for element in lst:
                        if len(element.child) > 0:
                            result.extend(flatten(element.child))
                        result.append(element)
                    return result

                all_elements = set(flatten(task_obj.child))

                for child_task in all_elements:
                    if child_task.status in [common.status.running]:
                        info = '<br>Post-position task (%s) is running, cant execute RUN action for %s</br>' % (child_task.task, task)
                        title = 'Error!'
                        common_pyqt5.Dialog(title, info)
                        return False

        return True

    def refresh_parent_state_for_child_task(self, action_name, task_dic_list):
        if action_name not in [common.action.run]:
            return

        total_selected_tasks = []
        for line in task_dic_list:
            block = line['Block']
            version = line['Version']
            flow = line['Flow']
            task = line['Task']
            task_obj = self.all_tasks[block][version][flow][task]
            total_selected_tasks.append(task_obj)

        for line in task_dic_list:

            block = line['Block']
            version = line['Version']
            flow = line['Flow']
            task = line['Task']
            # Update formula
            task_obj = self.all_tasks[block][version][flow][task]

            # Skip tasks which already have actions (except kill)
            if task_obj.action and task_obj.action not in [common.action.kill]:
                continue

            if len(list(task_obj.formula_list.keys())) == 0:
                task_obj.total_run_times = 1
            else:
                task_obj.total_run_times = 0

            for child_task in task_obj.child:
                child_task.parent[task_obj] = 'False'

            enable_count = 0
            for i in task_obj.formula_list.keys():
                task_obj.formula_list[i]['finish'] = False
                task_formula = task_obj.formula_list[i]['task_formula']
                for obj in task_formula:
                    if obj in ['(', ')', '&', '|']:
                        continue
                    else:
                        if obj in total_selected_tasks or obj.action == common.action.run:
                            task_obj.formula_list[i]['enable'] = True
                            enable_count += 1
                            break

            if enable_count == 0:
                if task_obj.formula_list:
                    task_obj.formula_list[1]['enable'] = True

                task_obj.total_run_times = 1
            else:
                task_obj.total_run_times = enable_count

            task_obj.current_run_times = 0

        self.debug_window.update_gui(self.config_dic)

    def send_action(self, action_name, task_dic_list, run_all_steps=False):
        """
        Refresh action for task
        """
        for line in task_dic_list:
            block = line['Block']
            version = line['Version']
            flow = line['Flow']
            task = line['Task']

            task_obj = self.all_tasks[block][version][flow][task]

            if action_name in [common.action.check_view, common.action.summarize_view]:
                task_obj.receive_view_action(action_name)
            else:
                # If task already has one action (Except Kill), flow will ignore new action (Except Kill)
                if task_obj.action and task_obj.action not in [common.action.kill] and not action_name == common.action.kill:
                    continue

                # Kill tasks which already own action and job_id / or status is QUEUED
                if action_name == common.action.kill:
                    if task_obj.status in [common.status.queued]:
                        pass
                    elif not task_obj.action or task_obj.status in [common.status.killing]:
                        continue

                # If task is processing run_all_steps, flow will ignore new action (Except Kill)
                if task_obj.run_all_steps and not action_name == common.action.kill:
                    continue

                task_obj.receive_action(action_name, run_all_steps=run_all_steps)

    def launch_task(self):
        """
        Launch task to execute action
        """

        if not self.monitor_flag:
            return

        all_finished_flag = True

        for block in self.all_tasks.keys():
            for version in self.all_tasks[block].keys():
                for flow in self.all_tasks[block][version].keys():
                    for task in self.all_tasks[block][version][flow].keys():
                        task_obj = self.all_tasks[block][version][flow][task]

                        # Task must already own one action
                        if not task_obj.action:
                            continue
                        else:
                            all_finished_flag = False

                        # Launch when status is not killing or killed for KILL action
                        if task_obj.action == common.action.kill:
                            if task_obj.status not in [common.status.killing, common.status.killed]:
                                task_obj.launch()

                        # Launch when status is not running for RUN action
                        elif task_obj.action == common.action.run:
                            # If user define run_all_steps, flow will execute build before run
                            if task_obj.status not in [common.status.building, common.status.running]:
                                task_obj.launch()
                        # Launch when status is not ING
                        elif task_obj.status not in common.status_ing.values():
                            task_obj.launch()

        if all_finished_flag:
            self.disable_gui_signal.emit(False)
            self.monitor_flag = False

            if self.send_result_flag:
                self.send_result_flag = False

            if self.close_flag:
                self.close_signal.emit()

    def kill_all_jobs_before_close_window(self):
        # Send kill action to all tasks
        for block in self.all_tasks.keys():
            for version in self.all_tasks[block].keys():
                for flow in self.all_tasks[block][version].keys():
                    for task in self.all_tasks[block][version][flow].keys():
                        task_obj = self.all_tasks[block][version][flow][task]

                        # Task must already own one action
                        if not task_obj.action:
                            continue
                        else:
                            # If tasks not killed
                            self.close_flag = True
                            if task_obj.action == common.action.kill or task_obj.status in [common.status.killing]:
                                continue

                            task_obj.receive_action(common.action.kill)

        # If all tasks has been killed, close main window
        if self.close_flag:
            return True
        else:
            return False


class TaskObject(QObject):
    update_status_signal = pyqtSignal(object, str, str)
    msg_signal = pyqtSignal(dict)
    send_result_signal = pyqtSignal(str, str, str, str, str)
    set_one_jobid_signal = pyqtSignal(str, str, str, str, str, str)
    set_run_time_signal = pyqtSignal(str, str, str, str, str, str)
    update_debug_info_signal = pyqtSignal(object)

    def __init__(self, config_dic, block, version, flow, task, ifp_obj, debug_window, job_manager):
        super().__init__()
        self.config_dic = config_dic
        self.block = block
        self.version = version
        self.flow = flow
        self.task = task
        self.job_manager = job_manager
        self.parent = {}
        self.child = []
        self.formula_list = None
        self.current_formula_id = None
        self.current_formula = None
        self.action = None
        self.view_action = None
        self.killed_action = None
        self.debug = False
        self.status = None
        self.check_status = None
        self.summarize_status = None
        self.kill_status = None
        self.ifp_obj = ifp_obj
        self.ifp_cache_dir = self.ifp_obj.ifp_cache_dir
        self.job_id = None
        self.debug_window = debug_window
        self.total_run_times = 0
        self.current_run_times = 0
        self.is_checking_license = False
        self.rerun_command_before_view = None
        self.run_all_steps = False
        self.skipped = False
        self.ignore_fail = False
        self.dependency_traceback_stage = 0
        self.predict = True if hasattr(install_config, 'mem_prediction') and install_config.mem_prediction else False
        self.predict_model = common_prediction.PredictionModel() if self.predict else None

        self.task_obj = self.ifp_obj.config_obj.get_task(self.block,
                                                         self.version,
                                                         self.flow,
                                                         self.task)

        self.in_process_check = True if isinstance(self.task_obj.InProcessCheck, dict) and self.task_obj.InProcessCheck.get('ENABLE') is True else False
        self.in_process_check_server = install_config.in_process_check_server if hasattr(install_config, 'in_process_check_server') and install_config.in_process_check_server else '10.232.134.66'

        self.action_progress = {common.action.build: ActionProgressObject(common.action.build),
                                common.action.run: ActionProgressObject(common.action.run),
                                common.action.check: ActionProgressObject(common.action.check),
                                common.action.summarize: ActionProgressObject(common.action.summarize)}

    def __eq__(self, other):
        if not isinstance(other, TaskObject):
            return False
        if self.block == other.block and self.version == other.version and self.flow == other.flow and self.task == other.task:
            return True
        return False

    def __hash__(self):
        return hash((self.block, self.version, self.flow, self.task))

    def print_task_progress(self, task, message, prefix=''):
        if self.action:
            self.action_progress[self.action].progress_message.append('%s %s' % (prefix, message))

    def calculate_strong_dependency(self, task_obj, formula_list, dependency_traceback_stage):
        result = False
        cancelled_num = 0
        dependency_traceback_stage += 1

        for run_time in formula_list.keys():
            formula = formula_list[run_time]['formula']
            new_formula_list = []
            for i in range(len(formula)):
                if formula[i] not in ['(', ')', '&', '|', ',']:
                    if type(formula[i]) is list:
                        if len(formula[i]) > 1:
                            new_formula_list.append('(')

                        for j in range(len(formula[i])):
                            # Parent task is on-schedule
                            if task_obj.parent[formula[i][j]] in ['False', 'Cancel']:
                                new_formula_list.append(task_obj.parent[formula[i][j]])
                            # Parent task do not have any pre-dependency
                            elif not formula[i][j].formula_list:
                                new_formula_list.append(task_obj.parent[formula[i][j]])
                            # Calculate parent task dependency
                            else:
                                new_formula_list.append(self.calculate_strong_dependency(formula[i][j], formula[i][j].formula_list, dependency_traceback_stage)[0])

                            if j < len(formula[i]) - 1:
                                new_formula_list.append('&')

                        if len(formula[i]) > 1:
                            new_formula_list.append(')')
                    else:
                        if task_obj.parent[formula[i]] in ['False', 'Cancel']:
                            traceback_result = task_obj.parent[formula[i]]
                        elif not formula[i].formula_list:
                            traceback_result = task_obj.parent[formula[i]]
                        else:
                            traceback_result = self.calculate_strong_dependency(formula[i], formula[i].formula_list, dependency_traceback_stage)[0]

                        new_formula_list.append(traceback_result)
                else:
                    new_formula_list.append(formula[i])

            if 'Cancel' in new_formula_list:
                equation_wo_cancel = ''.join(str(x) for x in new_formula_list).replace('Cancel', 'False')
                result = eval(equation_wo_cancel)

                if not result:
                    all_finish_flag = True
                    for task_obj2 in task_obj.parent.keys():
                        if task_obj2 in formula:
                            if task_obj2.status in [common.status.running, common.status.queued]:
                                all_finish_flag = False
                                break

                    if all_finish_flag:
                        cancelled_num += 1

            else:
                result = eval(''.join(str(x) for x in new_formula_list))

            if result:
                if not formula_list[run_time]['finish']:
                    break
                else:
                    continue

        if 0 < task_obj.total_run_times == cancelled_num:
            result = 'Cancel'
        elif task_obj.total_run_times == 0 and cancelled_num > 0:
            result = 'Cancel'

        return [result, cancelled_num]

    def receive_view_action(self, action_name):
        self.view_action = action_name

        while self.status == common.status.killing:
            time.sleep(2)

        self.rerun_command_before_view = None

        if not self.action:
            if action_name == common.action.check_view:
                if self.ifp_obj.rerun_check_or_summarize_before_view or self.check_status is None:
                    self.rerun_command_before_view = common.action.check

            elif action_name == common.action.summarize_view:
                if self.ifp_obj.rerun_check_or_summarize_before_view or self.summarize_status is None:
                    self.rerun_command_before_view = common.action.summarize

        thread = threading.Thread(target=self.view)
        thread.start()

    def receive_action(self, action_name, run_all_steps=False):
        if action_name == common.action.kill:
            self.killed_action = self.action

        self.action = action_name

        self.action_progress[self.action] = ActionProgressObject(self.action)
        self.current_run_times = 0
        self.run_all_steps = run_all_steps
        # If task is Killing, need wait killed and execute action

        while self.status == common.status.killing:
            time.sleep(2)

        if self.action == common.action.run:
            self.status = common.status.queued
            self.update_debug_info_signal.emit(self)
            self.update_status_signal.emit(self, self.action, common.status.queued)
            self.set_one_jobid_signal.emit(self.block, self.version, self.flow, self.task, 'Job', '')
            self.set_run_time_signal.emit(self.block, self.version, self.flow, self.task, 'Runtime', "pending")

        elif self.action == common.action.kill and self.status == common.status.queued:
            self.status = common.status.killed
            self.action = None
            self.set_cancel_for_child_tasks()
            self.update_status_signal.emit(self, self.killed_action, self.status)

        self.update_debug_info_signal.emit(self)

    def launch(self):
        self.action_progress[self.action].progress_message = []

        if self.action == common.action.kill:
            pass
        # If pre-task is A|B for C, must avoid A and B emit C to run twice
        elif self.status in [common.status.running] and self.action == common.action.run or self.current_formula:
            return
        elif self.config_dic.get('VAR', {}).get('MAX_RUNNING_JOBS') and self.job_manager.current_running_jobs >= int(self.config_dic['VAR']['MAX_RUNNING_JOBS']) > 0:
            self.print_task_progress(self.task, 'Wait! Max running jobs[%s] reached!' % self.config_dic['VAR']['MAX_RUNNING_JOBS'])
            return

        if self.is_checking_license:
            return

        self.action_progress[self.action].progress_message = []
        if self.action == common.action.run:
            if self.formula_list:
                # weak
                cancelled_num = 0
                for i in self.formula_list.keys():

                    if not self.formula_list[i]['enable']:
                        continue

                    equation = transfer_formula_list_to_bool_equation(self, self.formula_list[i]['formula'])
                    # self.print_task_progress(self.task, 'Condition-%s equation : %s' % (i, equation))

                    if 'Cancel' in equation:
                        equation_wo_cancel = ''.join(equation).replace('Cancel', 'False')
                        result = eval(equation_wo_cancel)

                        if not result:
                            all_finish_flag = True
                            for task_obj in self.parent.keys():
                                if task_obj in self.formula_list[i]['formula']:
                                    if task_obj.status in [common.status.running, common.status.queued]:
                                        all_finish_flag = False
                                        break

                            if all_finish_flag:
                                cancelled_num += 1
                        else:
                            if not self.formula_list[i]['finish']:
                                self.current_formula_id = i
                                self.current_formula = self.formula_list[i]['formula']
                                break

                    else:

                        result = eval(''.join(equation))
                        if result:
                            if not self.formula_list[i]['finish']:
                                self.current_formula_id = i
                                self.current_formula = self.formula_list[i]['formula']
                                break
                            else:
                                continue

                # strong dependency
                # if result is True:
                self.dependency_traceback_stage = -1
                [result, cancelled_num] = self.calculate_strong_dependency(self, self.formula_list, self.dependency_traceback_stage)
                if result is False:
                    self.print_task_progress(self.task, '[RUN_ORDER] : Cant start due to pre-tasks are running')
                    self.current_formula_id = None
                    self.current_formula = None

                if cancelled_num == self.total_run_times or result == 'Cancel':
                    self.print_task_progress(self.task, '[RUN_ORDER] : Cancelled due to pre-tasks are failed or cancelled')
                    self.status = common.status.cancelled
                    self.action = None
                    self.run_all_steps = None
                    self.update_status_signal.emit(self, self.action, self.status)
                    self.current_formula = None

                    def set_parent_dict_to_true(parent):
                        for obj in parent.keys():
                            parent[obj] = 'True'

                            if len(obj.parent) > 0:
                                set_parent_dict_to_true(obj.parent)

                    set_parent_dict_to_true(self.parent)

                    self.update_debug_info_signal.emit(self)

                    for child_task in self.child:
                        child_task.parent[self] = 'Cancel'
                        self.update_debug_info_signal.emit(child_task)
            else:
                result = True

        else:
            result = True

        if self.action and result:
            self.print_task_progress(self.task, '[RUN_ORDER] : Pre-tasks are all finished!')
            self.set_run_time_signal.emit(self.block, self.version, self.flow, self.task, 'Runtime', None)

            if self.action == common.action.run:
                self.job_manager.current_running_jobs += 1

            if self.action == common.action.kill:
                thread = threading.Thread(target=self.kill_action)
            else:
                thread = threading.Thread(target=self.manage_action)

            thread.start()

    def get_run_method(self, run_action):
        run_method = run_action.get('RUN_METHOD', '')
        command = run_action.get('COMMAND')

        if re.search('bsub', run_method):

            # if run_method with -K option
            if re.search('-K', run_method):
                run_method = run_method.replace('-K', '-I')

            # if run_method without -I option
            if not re.search('-I', run_method):
                run_method = run_method + ' -I'

        if re.search('xterm', run_method) and (not re.search('-T', run_method)):
            run_method = re.sub(r'xterm', f'xterm -T "{self.block}/{self.version}/{self.flow}/{self.task}: {command}"', run_method)
        elif re.search('gnome-terminal --', run_method) and (not re.search('-c', run_method)):
            run_method = re.sub(r'gnome-terminal --', f'gnome-terminal -t "{self.block}/{self.version}/{self.flow}/{self.task}: {command}"' + f" --wait -- {str(os.environ['SHELL'])} -c '", run_method)
        elif re.search('terminator -e', run_method) and (not re.search('-T', run_method)):
            if re.search('bsub', run_method):
                run_method = re.sub(r'terminator -e', f'terminator -u -T "{self.block}/{self.version}/{self.flow}/{self.task}: {command}"' + r" -e '", run_method)
            else:
                run_method = re.sub(r'terminator -e', f'terminator -u -T "{self.block}/{self.version}/{self.flow}/{self.task}: {command}"' + r" -e ", run_method)

        return run_method

    def check_file_and_license(self):
        check_result = True

        run_action = self.expand_var(self.config_dic['BLOCK'][self.block][self.version][self.flow][self.task]['ACTION'].get(common.action.run.upper(), None),
                                     {'BLOCK': self.block, 'VERSION': self.version, 'FLOW': self.flow, 'TASK': self.task})

        run_dependency = self.expand_var(self.config_dic['BLOCK'][self.block][self.version][self.flow][self.task].get('DEPENDENCY', {}), {'BLOCK': self.block, 'VERSION': self.version, 'FLOW': self.flow, 'TASK': self.task})

        if not run_action:
            return check_result

        if run_action and run_action.get('LOG', ''):
            self.action_progress[common.action.run].log_path = run_action.get('LOG', '')

        if run_dependency.get('FILE', []):

            required_files = run_dependency.get('FILE', [])

            for file in required_files:
                self.print_task_progress(self.task, '[DEPENDENCY] : check %s if exists' % file)

                if file and not os.path.exists(file):
                    self.print_task_progress(self.task, '[RUN_ORDER] : waiting for %s' % file)
                    check_result = False
                    time.sleep(5)
                    return check_result

        if run_dependency.get('LICENSE', []):
            required_license = run_dependency.get('LICENSE', [])
            required_feature = {}

            try:
                self.is_checking_license = True

                for i in required_license:
                    if len(i.split(':')) == 2:
                        feature = i.split(':')[0].strip()
                        quantity = i.split(':')[1].strip()
                        required_feature[feature] = quantity

                if len(list(required_feature.keys())) > 0:

                    run_method = self.get_run_method(run_action)

                    if re.search(r'^\s*bsub', run_method):
                        license_dic = common_license.GetLicenseInfo(lmstat_path=install_config.lmstat_path, bsub_command=run_method).get_license_info()
                    else:
                        license_dic = common_license.GetLicenseInfo(lmstat_path=install_config.lmstat_path).get_license_info()

                    filtered_license_dic = common_license.FilterLicenseDic().run(license_dic=license_dic, feature_list=list(required_feature.keys()))

                    for specified_feature in required_feature.keys():
                        self.print_task_progress(self.task, '[DEPENDENCY] : check %s if is sufficient' % specified_feature)
                        total_issued = 0
                        total_in_use = 0
                        for license_server in filtered_license_dic.keys():
                            for vendor_daemon in filtered_license_dic[license_server]['vendor_daemon'].keys():
                                issued = filtered_license_dic[license_server]['vendor_daemon'][vendor_daemon]['feature'][specified_feature]['issued']
                                in_use = filtered_license_dic[license_server]['vendor_daemon'][vendor_daemon]['feature'][specified_feature]['in_use']
                                total_issued += int(issued)
                                total_in_use += int(in_use)

                        if int(required_feature[specified_feature]) <= (total_issued - total_in_use):
                            pass
                        else:
                            self.msg_signal.emit({'message': '*Info*: waiting for {} (Required : {}, Total issued : {}, Total in used : {}) for {} {} {} {}'.format(specified_feature,
                                                                                                                                                                    required_feature[specified_feature],
                                                                                                                                                                    total_issued,
                                                                                                                                                                    total_in_use,
                                                                                                                                                                    self.block,
                                                                                                                                                                    self.version,
                                                                                                                                                                    self.flow,
                                                                                                                                                                    self.task),
                                                  'color': 'black'})
                            self.print_task_progress(self.task, '[RUN_ORDER] : waiting for {} (Required : {}, Total issued : {}, Total in used : {})'.format(specified_feature, required_feature[specified_feature], total_issued, total_in_use))
                            time.sleep(5)
                            check_result = False
                            break
            except Exception:
                pass
            finally:
                self.is_checking_license = False

        return check_result

    def expand_var(self, action_dict, task_dict):
        if not action_dict:
            return None

        new_action = {}

        for attr in action_dict.keys():
            new_action[attr] = common.expand_var(action_dict[attr], ifp_var_dic=self.ifp_obj.config_obj.var_dic, **task_dict)

        return new_action

    def execute_action(self, action):
        """
        Execute action for BUILD/RUN/CHECK/SUMMARIZE/RELEASE
        """
        # Avoid kill action when task is building for Run all steps
        if action == common.action.kill:
            return

        run_action = self.expand_var(self.config_dic['BLOCK'][self.block][self.version][self.flow][self.task]['ACTION'].get(action.upper(), None),
                                     {'BLOCK': self.block, 'VERSION': self.version, 'FLOW': self.flow, 'TASK': self.task})

        self.status = None

        # Record runtimes for task which will run for several conditions
        if action == common.action.run:
            self.current_run_times += 1

        self.update_debug_info_signal.emit(self)

        if self.skipped:
            self.status = '{} {}'.format(action, common.status.skipped)
            self.update_status_signal.emit(self, action, self.status)
            self.set_one_jobid_signal.emit(self.block, self.version, self.flow, self.task, 'Job', '')
            return

        if (not run_action) or (not run_action.get('COMMAND')):
            self.status = '{} {}'.format(action, common.status.undefined)
            self.msg_signal.emit({'message': '[%s/%s/%s/%s] Undefined %s command, not submit!' % (self.block, self.version, self.flow, self.task, action), 'color': 'red'})

            if action in [common.action.check, common.action.check_view]:
                self.check_status = self.status
            elif action in [common.action.summarize, common.action.summarize_view]:
                self.summarize_status = self.status

            self.update_status_signal.emit(self, action, self.status)
        else:
            run_method = self.get_run_method(run_action)
            self.status = common.status_ing[action]
            # self.update_status_signal.emit(self, common.action.check, None)
            self.update_status_signal.emit(self, self.action, self.status)
            self.update_debug_info_signal.emit(self)
            self.msg_signal.emit({'message': '[%s/%s/%s/%s] %s : %s "%s"' % (self.block, self.version, self.flow, self.task, self.status, run_method, run_action['COMMAND']), 'color': 'black'})

            if self.predict and re.search(r'^\s*bsub', run_method):
                predict_job_info = self.update_predict_info(run_method=run_method, cwd=run_action.get('PATH', os.getcwd()), command=run_action['COMMAND'])
                run_method = self.predict_model.predict_job(job_info=predict_job_info, run_method=run_method)

            # Get command
            command = run_action['COMMAND']

            if (not re.search(r'^\s*$', run_method)) and (not re.search(r'^\s*local\s*$', run_method, re.I)):
                command = str(run_method) + ' "' + str(command) + '"'

            if re.search(r'gnome-terminal', run_method):
                command = str(command) + "; exit'"
                # command = str(command) + f"; exec {str(os.environ['SHELL'])}" + "'"
            elif re.search(r'terminator', run_method) and re.search(r'bsub', run_method):
                command = str(command) + r"'"

            if ('PATH' in run_action) and run_action['PATH']:
                if os.path.exists(run_action['PATH']):
                    command = 'cd ' + str(run_action['PATH']) + '; ' + str(command)
                    cwd = run_action['PATH']
                    command_dir = '%s/%s/' % (str(run_action['PATH']), os.path.basename(self.ifp_cache_dir))
                else:
                    cwd = os.getcwd()
                    # self.msg_signal.emit({'message': '*Warning*: {} PATH "'.format(action) + str(run_action['PATH']) + '" not exists.', 'color': 'orange'})
                    command_dir = '%s/%s/' % (os.getcwd(), os.path.basename(self.ifp_cache_dir))
            else:
                cwd = os.getcwd()
                self.msg_signal.emit({'message': '*Warning*: {} PATH is not defined for task "'.format(action) + str(self.task) + '".', 'color': 'orange'})
                command_dir = '%s/%s/' % (os.getcwd(), os.path.basename(self.ifp_cache_dir))

            # Record command
            if not os.path.exists(command_dir):
                os.system('mkdir -p %s' % command_dir)

            self.action_progress[action].current_path = command_dir
            command_file = '%s/%s_%s.sh' % (command_dir, action, self.task)
            command_f = open(command_file, 'w')
            command_f.write('#!/bin/bash\n')

            for (key, value) in self.ifp_obj.config_obj.var_dic.items():
                command_f.write('export %s=%s\n' % (key, value))

            command_f.write(command)
            command_f.close()
            self.action_progress[action].current_command = command

            # Run command
            if re.search(r'^\s*bsub', run_method):
                process = common.spawn_process(command)
                stdout = process.stdout.readline().decode('utf-8')

                if common.get_jobid(stdout):
                    self.job_id = 'b:{}'.format(common.get_jobid(stdout))

                    if action in [common.action.run]:
                        self.set_one_jobid_signal.emit(self.block, self.version, self.flow, self.task, 'Job', str(self.job_id))
                        self.set_run_time_signal.emit(self.block, self.version, self.flow, self.task, 'Runtime', "pending")

                    while True:
                        current_job = self.job_id[2:]
                        current_job_dic = common_lsf.get_bjobs_uf_info(command='bjobs -UF ' + str(current_job))

                        self.action_progress[action].current_job_dict = current_job_dic

                        if current_job_dic:
                            job_status = current_job_dic[current_job]['status']

                            if job_status in ['RUN', 'EXIT', 'DONE']:
                                if action in [common.action.run]:
                                    self.start_in_process_check(job_id=current_job)
                                    self.set_run_time_signal.emit(self.block, self.version, self.flow, self.task, 'Runtime', "00:00:0%s" % str(random.randint(3, 5)))

                                break

                        time.sleep(10)
                else:
                    self.job_id = 'submit fail'
                    self.msg_signal.emit({'message': '[%s/%s/%s/%s] %s submit fail : %s "%s"' % (self.block, self.version, self.flow, self.task, action, run_method, run_action['COMMAND']),
                                          'color': 'red'})

            else:
                process = common.spawn_process(command)
                self.job_id = 'l:{}'.format(process.pid)

                if action in [common.action.run]:
                    self.set_one_jobid_signal.emit(self.block, self.version, self.flow, self.task, 'Job', str(self.job_id))
                    self.set_run_time_signal.emit(self.block, self.version, self.flow, self.task, 'Runtime', "00:00:00")

            self.action_progress[action].job_id = self.job_id
            task_job = {
                'job_id': self.job_id,
                'block': self.block,
                'version': self.version,
                'flow': self.flow,
                'task': self.task,
                'submitted_time': datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S'),
                'cwd': cwd if cwd is not None else os.getcwd(),
                'command': command,
                'command_file': command_file
            }
            stdout, stderr = process.communicate()
            return_code = process.returncode

            task_job.update({
                'finished_time': datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S'),
                'status': 'DONE' if not process.returncode else 'EXIT',
                'exit_code': process.returncode
            })

            # Save job data to database
            save_db_thread = threading.Thread(target=common_db.save_task_job, args=(task_job, ))
            save_db_thread.daemon = True
            save_db_thread.start()

            stdout = str(stdout, 'utf-8').strip()
            stderr = str(stderr, 'utf-8').strip()

            while self.status == common.status.killing:
                time.sleep(3)

            if self.status == common.status.killed:
                pass
            else:

                if return_code == 0:
                    self.status = '{} {}'.format(action, common.status.passed)
                    self.msg_signal.emit({'message': '[%s/%s/%s/%s] %s done' % (self.block, self.version, self.flow, self.task, action), 'color': 'green'})

                    # Save job data to database
                    save_db_thread = threading.Thread(target=common_db.analysis_and_save_job, args=(self.job_id, self.block, self.version, self.flow, self.task))
                    save_db_thread.daemon = True
                    save_db_thread.start()
                else:
                    self.status = '{} {}'.format(action, common.status.failed)
                    self.msg_signal.emit({'message': '[%s/%s/%s/%s] %s failed: %s "%s"' % (self.block, self.version, self.flow, self.task, action, run_method, run_action['COMMAND']), 'color': 'red'})
                    if action == common.action.run or action == common.action.check:
                        self.send_result_signal.emit(self.block, self.version, self.flow, self.task, action)
                    self.print_task_progress(self.task, '[RUN_RESULT] : %s' % stderr)
                    self.print_task_progress(self.task, '[RUN_RESULT] : %s' % stdout)

            if action in [common.action.check, common.action.check_view]:
                self.check_status = self.status
            elif action in [common.action.summarize, common.action.summarize_view]:
                self.summarize_status = self.status

            self.update_status_signal.emit(self, action, self.status)

    def start_in_process_check(self, job_id: str):
        if not self.in_process_check:
            return

        if not self.in_process_check_server:
            self.ifp_obj.update_message_text({
                'message': 'In Process Check Server not found.',
                'color': 'red'})

        task_var_dic = {'BLOCK': self.block, 'VERSION': self.version, 'FLOW': self.flow, 'TASK': self.task}
        path = common.expand_var(self.task_obj.InProcessCheck.get('PATH', os.getcwd()), ifp_var_dic=self.ifp_obj.config_obj.var_dic, **task_var_dic)
        command = common.expand_var(self.task_obj.InProcessCheck.get('COMMAND'), ifp_var_dic=self.ifp_obj.config_obj.var_dic, **task_var_dic)
        interval = self.task_obj.InProcessCheck.get('INTERVAL')
        notification = common.expand_var(self.task_obj.InProcessCheck.get('NOTIFICATION'), ifp_var_dic=self.ifp_obj.config_obj.var_dic, **task_var_dic)
        start_interval = self.task_obj.InProcessCheck.get('START_INTERVAL', 120)

        if command is None or notification is None or not interval:
            self.ifp_obj.update_message_text({
                'message': 'Definition of COMMAND or NOTIFICATION not found or INTERVAL is invalid.',
                'color': 'red'})

        url = f'http://{str(self.in_process_check_server)}:12345/add_task'
        data = {
            'id': job_id,
            'path': path,
            'command': command,
            'notification': notification,
            'interval': interval,
            'start_interval': start_interval
        }

        response = requests.post(url, json=data)

        if not self.in_process_check_server:
            self.ifp_obj.update_message_text({
                'message': str(response),
                'html': True})

    def update_predict_info(self, run_method: str, cwd: str, command: str) -> Dict[str, str]:
        predict_job_info = {'job_name': '',
                            'project': self.ifp_obj.config_obj.PROJECT,
                            'user': getpass.getuser(),
                            'queue': '',
                            'cwd': cwd,
                            'command': command,
                            'started_time': datetime.datetime.now().strftime('%a %b %d %H:%M:%S'),
                            'res_req': ''
                            }

        run_info_list = run_method.split()

        for i, item in enumerate(run_info_list):
            if item == '-q' and not predict_job_info['queue']:
                predict_job_info['queue'] = run_info_list[i + 1]
            elif item == '-J' and not predict_job_info['job_name']:
                predict_job_info['job_name'] = run_info_list[i + 1]
            elif item == '-R' and not predict_job_info['res_req']:
                predict_job_info['res_req'] = run_info_list[i + 1]

        return predict_job_info

    def manage_action(self):
        """
        Manage action for BUILD/RUN/CHECK/SUMMARIZE/RELEASE
        """
        # Check license for RUN action
        if self.action in [common.action.run] and not self.skipped:
            if not self.check_file_and_license():
                self.current_formula_id = None
                self.current_formula = None
                return

        # Return if user killed task when checking license
        if not self.action:
            return

        if self.run_all_steps and not self.skipped:
            self.action = common.action.build
            self.execute_action(common.action.build)
            self.action = common.action.run

        # Execute action
        self.print_task_progress(self.task, '[ACTION] : Start execute %s action' % self.action)
        self.execute_action(self.action)

        all_finished_flag = True
        # If action is RUN or KILL, flow will update dependency state in child based on current task's result
        if self.action == common.action.run or (self.action == common.action.kill and self.killed_action == common.action.run):

            # Force execute CHECK after RUN
            if self.action == common.action.run and not self.skipped and self.ifp_obj.auto_check and not self.run_all_steps:
                check_action = self.expand_var(self.config_dic['BLOCK'][self.block][self.version][self.flow][self.task]['ACTION'].get(common.action.check.upper(), None),
                                               {'BLOCK': self.block, 'VERSION': self.version, 'FLOW': self.flow, 'TASK': self.task})

                if (not check_action) or (not check_action.get('COMMAND')):
                    pass
                else:
                    self.action = common.action.check
                    self.execute_action(common.action.check)

            # Judge if all conditions are finished or not
            if self.formula_list:
                self.formula_list[self.current_formula_id]['finish'] = True

                for i in self.formula_list.keys():
                    if self.formula_list[i]['enable'] and not self.formula_list[i]['finish']:
                        all_finished_flag = False

            # If status is PASSED or user set ignore fail tasks, set TRUE for dependency state in self.child
            if self.status in ['{} {}'.format(common.action.run, common.status.passed), '{} {}'.format(common.action.check, common.status.passed), '{} {}'.format(common.action.run, common.status.skipped)] or \
                    ((self.ifp_obj.ignore_fail or self.ignore_fail) and self.status in ['{} {}'.format(common.action.run, common.status.failed), '{} {}'.format(common.action.check, common.status.failed)]):

                if all_finished_flag:
                    self.action = None

                # Only first condition is passed , set True in child
                if self.current_run_times == 1:
                    time.sleep(2)

                    for child_task in self.child:
                        child_task.parent[self] = 'True'
                        self.update_debug_info_signal.emit(child_task)

            # If state is FAILED or COMMAND UNDEFINED and all conditions are finished, set CANCEL for dependency state
            elif self.status in ['{} {}'.format(common.action.run, common.status.failed), '{} {}'.format(common.action.run, common.status.undefined), '{} {}'.format(common.action.check, common.status.failed), common.status.killed]:  # Cancel child tasks if failed or run undefined
                # If all conditions of task finished, and all failed, then cancel child task, otherwise, keep False in child
                if all_finished_flag:
                    self.action = None
                    self.set_cancel_for_child_tasks()

            # If state is KILLED, set CANCEL for dependency state
            elif self.status == common.status.killed:
                self.action = None
                self.set_cancel_for_child_tasks()

            # Change dependency state to True for parent tasks in self.parent
            for task_obj in self.parent.keys():
                if self.formula_list:
                    if task_obj not in self.current_formula:
                        continue
                    else:
                        self.parent[task_obj] = 'True'
                else:
                    self.parent[task_obj] = 'True'

            self.job_manager.current_running_jobs -= 1
        elif self.action == common.action.kill:
            self.action = None
            self.killed_action = None
        else:
            self.action = None

        # Reset all important parameters to None
        self.current_formula = None
        self.current_formula_id = None
        self.job_id = None

        # If user defined run_all_steps and all run times have finished which means RUN action has finished and need to execute CHECK and SUMMARIZE
        if self.run_all_steps and all_finished_flag and not self.skipped:
            check_action = self.expand_var(self.config_dic['BLOCK'][self.block][self.version][self.flow][self.task]['ACTION'].get(common.action.check.upper(), None),
                                           {'BLOCK': self.block, 'VERSION': self.version, 'FLOW': self.flow, 'TASK': self.task})

            if (not check_action) or (not check_action.get('COMMAND')):
                pass
            else:
                self.action = common.action.check
                self.execute_action(common.action.check)

            if self.status in ['{} {}'.format(common.action.run, common.status.passed), '{} {}'.format(common.action.check, common.status.passed)] or \
                    ((self.ifp_obj.ignore_fail or self.ignore_fail) and self.status in ['{} {}'.format(common.action.run, common.status.failed), '{} {}'.format(common.action.check, common.status.failed)]):

                self.action = common.action.summarize
                self.execute_action(common.action.summarize)
                self.action = common.action.release
                self.execute_action(common.action.release)
                self.action = None

            self.run_all_steps = False

        self.update_debug_info_signal.emit(self)

    def kill_action(self):
        """
        Kill action for BUILD/RUN/CHECK/SUMMARIZE/RELEASE
        """

        self.status = common.status.killing
        self.msg_signal.emit({'message': '[%s/%s/%s/%s] is %s' % (self.block, self.version, self.flow, self.task, common.status.killing), 'color': 'red'})
        self.update_status_signal.emit(self, self.killed_action, common.status.killing)

        timeout = 0
        while self.killed_action and not self.job_id:
            time.sleep(2)

            timeout += 2
            if timeout >= 30:
                break

        if str(self.job_id).startswith('b'):
            jobid = str(self.job_id)[2:]
            common.run_command('bkill ' + str(jobid))
        elif str(self.job_id).startswith('l'):
            jobid = str(self.job_id)[2:]

            try:
                common.kill_pid_tree(jobid)
            except Exception:
                pass

        self.status = common.status.killed
        self.run_all_steps = False

    def view(self):
        if not self.ifp_obj.read_mode and self.rerun_command_before_view:
            self.execute_action(self.rerun_command_before_view)

        # Run viewer command under task check directory.
        action = self.expand_var(self.config_dic['BLOCK'][self.block][self.version][self.flow][self.task]['ACTION'].get(self.view_action.split()[0].upper(), None),
                                 {'BLOCK': self.block, 'VERSION': self.version, 'FLOW': self.flow, 'TASK': self.task})

        command = ''

        if action:
            if ('PATH' in action) and action['PATH']:
                if os.path.exists(action['PATH']):
                    command = 'cd ' + str(action['PATH']) + ';'
                else:
                    self.msg_signal.emit({'message': '*Warning*: %s PATH "' % self.view_action + str(action['PATH']) + '" not exists.', 'color': 'orange'})
            else:
                self.msg_signal.emit({'message': '*Warning*: %s PATH is not defined for task "' % self.view_action + str(self.task) + '".', 'color': 'orange'})

            if ('VIEWER' in action) and action['VIEWER']:
                if ('REPORT_FILE' in action) and action['REPORT_FILE']:
                    if (os.path.exists(action['REPORT_FILE'])) or (os.path.exists(str(action['PATH']) + '/' + str(action['REPORT_FILE']))):
                        command = str(command) + ' ' + str(action['VIEWER']) + ' ' + str(action['REPORT_FILE'])
                        common.run_command(command)
                    else:
                        if not re.match('^/.*$', action['REPORT_FILE']):
                            self.msg_signal.emit({'message': '      *Error*: {} REPORT_FILE "{}/{}" not exists.'.format(self.view_action, action['PATH'], action['REPORT_FILE']), 'color': 'red'})
                        else:
                            self.msg_signal.emit({'message': '      *Error*: {} REPORT_FILE "{}" not exists.'.format(self.view_action, action['REPORT_FILE']), 'color': 'red'})
                else:
                    self.msg_signal.emit({'message': '*Error*: %s REPORT_FILE is not defined for task "' % self.view_action + str(self.task) + '".', 'color': 'red'})
            else:
                self.msg_signal.emit({'message': '*Error*: %s is not defined for task "' % self.view_action + str(self.task) + '".', 'color': 'red'})

        self.rerun_command_before_view = None

    def set_cancel_for_child_tasks(self):
        for child_task in self.child:
            if child_task.parent[self] == 'False':
                child_task.parent[self] = 'Cancel'
                # if child_task.action:
                #     child_task.parent[self] = 'Cancel'
                # else:
                #     child_task.parent[self] = 'True'
                self.update_debug_info_signal.emit(child_task)

    def print_output(self, block, version, flow, task, result, output):
        self.debug_print('')
        self.debug_print('[DEBUG] Block(' + str(block) + ')  Version(' + str(version) + ')  Flow(' + str(flow) + ')  Task(' + str(task) + ')  :  ' + str(result))
        self.debug_print('[DEBUG] ----------------')

        try:
            for line in str(output, 'utf-8').split('\n'):
                if line:
                    self.debug_print('[DEBUG] ' + str(line))
        except Exception:
            pass

        self.debug_print('[DEBUG] ----------------')
        self.debug_print('')

    def debug_print(self, message):
        if self.debug:
            print(message)


class ActionProgressObject:
    def __init__(self, action):
        self.action = action
        self.job_id = None
        self.current_path = None
        self.current_command = None
        self.progress_message = []
        self.log_path = None
        self.current_job_dict = None
