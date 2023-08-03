# -*- coding: utf-8 -*-
################################
# File Name   : function.py
# Author      : liyanqing
# Created On  : 2022-06-07 20:08:51
# Description :
################################
import os
import sys
import time
import datetime
import threading
import re
from PyQt5.QtCore import QThread, pyqtSignal
from collections import defaultdict

# Import common python files.
sys.path.append(str(os.environ['IFP_INSTALL_PATH']) + '/common')
import common
import common_lsf

# Import config settings.
sys.path.append(str(os.environ['IFP_INSTALL_PATH']) + '/config')
import config

UNEXPECTED_JOB_STATUS = ['Killed', 'Killing', 'Cancelled', 'RUN FAIL']

def set_command_env(block='', version='', flow='', vendor='', branch='', task=''):
    if block:
        os.environ['BLOCK'] = block

    if version:
        os.environ['VERSION'] = version

    if flow:
        os.environ['FLOW'] = flow

    if vendor:
        os.environ['VENDOR'] = vendor

    if branch:
        os.environ['BRANCH'] = branch

    if task:
        os.environ['TASK'] = task


class IfpCommon(QThread):
    """
    User customized process.
    """
    def __init__(self, task_list, config_dic, debug=False):
        super().__init__()
        self.task_list = task_list
        self.config_dic = config_dic
        self.debug = debug

    def debug_print(self, message):
        if self.debug:
            print(message)

    def print_output(self, block, version, flow, vendor, branch, task, result, output):
        self.debug_print('')
        self.debug_print('[DEBUG] Block(' + str(block) + ')  Version(' + str(version) + ')  Flow(' + str(flow) + ')  Vendor(' + str(vendor) + ')  Branch(' + str(branch) + ')  Task(' + str(task) + ')  :  ' + str(result))
        self.debug_print('[DEBUG] ----------------')

        try:
            for line in str(output, 'utf-8').split('\n'):
                if line:
                    self.debug_print('[DEBUG] ' + str(line))
        except Exception:
            pass

        self.debug_print('[DEBUG] ----------------')
        self.debug_print('')


class IfpBuild(IfpCommon):
    """
    Build EDA directory and environment.
    """
    start_one_signal = pyqtSignal(str, str, str, str, str, str, str)
    finish_one_signal = pyqtSignal(str, str, str, str, str, str, str)
    finish_signal = pyqtSignal()
    msg_signal = pyqtSignal(str)

    def __init__(self, task_list, config_dic, debug=False):
        super().__init__(task_list, config_dic, debug)

    def build_one_task(self, item):
        block = item.Block
        version = item.Version
        flow = item.Flow
        vendor = item.Vendor
        branch = item.Branch
        task = item.Task
        result = ''

        # build_command can read and use these information.
        set_command_env(block, version, flow, vendor, branch, task)

        # Run build_command under branch directory.
        build_action = self.config_dic['BLOCK'][block][version][flow][vendor][branch][task]['ACTION'].get('BUILD', None)

        if build_action and build_action.get('COMMAND'):
            self.start_one_signal.emit(block, version, flow, vendor, branch, task, 'Building')
            self.msg_signal.emit('Building {} {} {} {} {} {}'.format(block, version, flow, vendor, branch, task))

            command = build_action['COMMAND']

            if ('PATH' in build_action) and (build_action['PATH']) and (os.path.exists(build_action['PATH'])):
                command = 'cd ' + str(build_action['PATH']) + '; ' + str(command)
            else:
                common.print_error('*Error*: Build path "' + str(build_action['PATH']) + '" is missing.')

            (return_code, stdout, stderr) = common.run_command(command)

            if return_code == 0:
                result = 'BUILD PASS'
            else:
                self.msg_signal.emit('Build failed as: {}'.format(stderr.decode('utf-8')))
                result = 'BUILD FAIL'

            self.print_output(block, version, flow, vendor, branch, task, result, stdout + stderr)
        else:
            result = 'BUILD undefined'

        # Tell GUI the build result.
        self.finish_one_signal.emit(block, version, flow, vendor, branch, task, result)

    def run(self):
        self.msg_signal.emit('>>> Building blocks ...')

        thread_list = []

        build_warning = False

        for item in self.task_list:
            if item.Status in ['Running', 'Killing']:
                build_warning = True
            else:
                thread = threading.Thread(target=self.build_one_task, args=(item,))
                thread.start()
                thread_list.append(thread)

        if build_warning:
            self.msg_signal.emit('*Build Warning*: Partially selected tasks are either running or killing, which will not be Builded')

        # Wait for thread done.
        for thread in thread_list:
            thread.join()

        # Tell GUI build done.
        self.msg_signal.emit('Build Done.')
        self.finish_signal.emit()

class IfpRun(IfpCommon):
    """
    Run specified task.
    """
    start_one_signal = pyqtSignal(str, str, str, str, str, str, str)
    finish_one_signal = pyqtSignal(str, str, str, str, str, str, str)
    finish_signal = pyqtSignal()
    msg_signal = pyqtSignal(str)
    set_one_jobid_signal = pyqtSignal(str, str, str, str, str, str, str, str)
    set_run_time_signal = pyqtSignal(str, str, str, str, str, str, str, str)

    def __init__(self, task_list, config_dic, action='RUN', debug=False, ignore_fail=False):
        super().__init__(task_list, config_dic, debug)

        self.action = action
        self.ignore_fail = ignore_fail
        self.block_version_to_run = list({(x.Block, x.Version): 1 for x in task_list}.keys())
        self.task_groups = self.group_tasks()

    def run_block_version(self):
        block_version_process = []

        for block, version in self.block_version_to_run:
            block_version_tasks = list(filter(lambda x: x.Block == block and x.Version == version, self.task_list))

            if block_version_tasks:
                flow_order = self.config_dic['RUN_ORDER']['{}:{}'.format(block, version)]
                p = threading.Thread(target=self.run_flows, args=(block_version_tasks, flow_order))
                p.start()
                block_version_process.append(p)

        for p in block_version_process:
            p.join()

    def run_flows(self, tasks, flow_order):
        for i, flow_bundle in enumerate(flow_order):
            if i == 0:
                flow_process = []

                for flow in flow_bundle.split('|'):
                    flow_tasks = list(filter(lambda x: x.Flow == flow, tasks))

                    if flow_tasks:
                        p = threading.Thread(target=self.run_flow, args=(flow_tasks,))
                        p.start()
                        flow_process.append(p)

                for p in flow_process:
                    p.join()
            else:
                pre_flows_bundle = flow_order[i-1]
                pre_flows_bundle_tasks = []

                for pre_flow in pre_flows_bundle.split('|'):
                    pre_flow_tasks = list(filter(lambda x: x.Flow == pre_flow, tasks))
                    pre_flows_bundle_tasks.extend(pre_flow_tasks)

                # Cancel next task if pre task is "Cancelled" or "Killed".
                if list(filter(lambda x: x.Status in str(UNEXPECTED_JOB_STATUS), pre_flows_bundle_tasks)) and not self.ignore_fail:
                    for flow in flow_bundle.split('|'):
                        flow_tasks = list(filter(lambda x: x.Flow == flow, tasks))

                        for t in flow_tasks:
                            self.start_one_signal.emit(t.Block, t.Version, t.Flow, t.Vendor, t.Branch, t.Task, 'Cancelled')

                    continue

                # Run all tasks.
                flow_process = []

                for flow in flow_bundle.split('|'):
                    flow_tasks = list(filter(lambda x: x.Flow == flow, tasks))

                    if flow_tasks:
                        p = threading.Thread(target=self.run_flow, args=(flow_tasks,))
                        p.start()
                        flow_process.append(p)

                for p in flow_process:
                    p.join()

    def run_flow(self, tasks):
        groups = []

        for t in tasks:
            key = '{}.{}.{}.{}.{}'.format(t.Block, t.Version, t.Flow, t.Vendor, t.Branch)

            if key not in groups:
                groups.append(key)

        group_process = []

        for group in groups:
            run_type = self.config_dic['RUN_TYPE'][group]
            tasks = self.task_groups[group]
            p = threading.Thread(target=self.run_group, args=(tasks, run_type))
            p.start()
            group_process.append(p)

        for p in group_process:
            p.join()

    def run_one_task(self, block, version, flow, vendor, branch, task):
        # run_command can read and use these information.
        set_command_env(block, version, flow, vendor, branch, task)

        # Run run_command under branch directory.
        run_action = self.config_dic['BLOCK'][block][version][flow][vendor][branch][task]['ACTION'].get(self.action, None)
        result = ''
        start_time = datetime.datetime.now()

        if run_action and run_action.get('COMMAND'):
            # Tell GUI the task run start.
            self.start_one_signal.emit(block, version, flow, vendor, branch, task, 'Running')

            run_method = run_action.get('RUN_METHOD', '')
            self.msg_signal.emit('*Info*: running {} "{}" under {} for {} {} {} {} {} {}\n'.format(run_method,
                                                                                                   run_action['PATH'],
                                                                                                   run_action['COMMAND'],
                                                                                                   block,
                                                                                                   version,
                                                                                                   flow,
                                                                                                   vendor,
                                                                                                   branch,
                                                                                                   task))
            # Set command
            command = run_action['COMMAND']

            if ('PATH' in run_action) and (run_action['PATH']) and (os.path.exists(run_action['PATH'])):
                command = 'cd ' + str(run_action['PATH']) + '; ' + str(command)
            else:
                common.print_error('*Error*: Run path "' + str(run_action['PATH']) + '" is missing.')

            # if run_method without -I option
            if re.match(r'^\s*bsub\s+', run_method) or re.match(r'^\s*bsub$', run_method) or re.match(r'\s+bsub\s+', run_method) or re.match(r'\s+bsub$', run_method):
                if not re.search('-I', run_method):
                    run_method = run_method + ' -I '

            # Run command
            jobid = None

            if run_method != '':
                command = str(run_method) + ' "' + str(command) + '"'

            if re.search(r'^\s*bsub', run_method):
                process = common.spawn_process(command)
                stdout = process.stdout.readline().decode('utf-8')
                jobid = 'b:{}'.format(common.get_jobid(stdout))
            else:
                process = common.spawn_process(command)
                jobid = 'l:{}'.format(process.pid)

            self.set_one_jobid_signal.emit(block, version, flow, vendor, branch, task, 'Job', str(jobid))
            stdout, stderr = process.communicate()
            return_code = process.returncode

            finish_time = datetime.datetime.now()
            last_status = self.config_dic['BLOCK'][block][version][flow][vendor][branch][task].get('Status', None)

            if last_status == 'Killing':
                if str(jobid).startswith('b'):
                    jobid = str(jobid)[2:]

                while True:
                    time.sleep(3)
                    bjobs_dic = common_lsf.get_bjobs_info('bjobs ' + str(jobid))

                    if ('STAT' in bjobs_dic.keys()) and bjobs_dic['STAT'] and (bjobs_dic['STAT'][0] == 'EXIT'):
                        result = 'Killed'
                        self.msg_signal.emit('*Info*: job killed for {} {} {} {} {} {}\n'.format(block, version, flow, vendor, branch, task))
                        break
            elif last_status == 'Killed':
                result = 'Killed'
                self.msg_signal.emit('*Info*: job killed for {} {} {} {} {} {}\n'.format(block, version, flow, vendor, branch, task))
            else:
                if return_code == 0:
                    result = str(self.action) + ' PASS'
                else:
                    result = str(self.action) + ' FAIL'

                self.print_output(block, version, flow, vendor, branch, task, result, stdout + stderr)
                self.msg_signal.emit('*Info*: job done for {} {} {} {} {} {}\n'.format(block, version, flow, vendor, branch, task))
        else:
            finish_time = datetime.datetime.now()
            result = str(self.action) + ' undefined'

        runtime = str(finish_time - start_time).split('.')[0]
        self.set_run_time_signal.emit(block, version, flow, vendor, branch, task, 'Runtime', runtime)

        # Tell GUI the task run finish.
        self.config_dic['BLOCK'][block][version][flow][vendor][branch][task].Status = result

        # Tell GUI the run result.
        self.finish_one_signal.emit(block, version, flow, vendor, branch, task, result)

    def group_tasks(self):
        """
        group tasks according to RUN_TYPE
        """
        groups = defaultdict(list)

        for task in self.task_list:
            key = '{}.{}.{}.{}.{}'.format(task.Block, task.Version, task.Flow, task.Vendor, task.Branch)
            groups[key].append((task.Block, task.Version, task.Flow, task.Vendor, task.Branch, task.Task))

        return groups

    def run_group(self, tasks, run_type):
        if run_type == 'serial':
            for i, t in enumerate(tasks):
                block, version, flow, vendor, branch, task = t

                if i > 0:
                    pre_block, pre_version, pre_flow, pre_vendor, pre_branch, pre_task = tasks[i - 1]
                    pre_task_obj = self.config_dic['BLOCK'][pre_block][pre_version][pre_flow][pre_vendor][pre_branch][pre_task]

                    if (pre_task_obj.get('Status') == str(self.action) + ' PASS') or self.ignore_fail:
                        self.run_one_task(block, version, flow, vendor, branch, task)

                    if (pre_task_obj.get('Status') in str(UNEXPECTED_JOB_STATUS)) and (not self.ignore_fail):
                        self.start_one_signal.emit(block, version, flow, vendor, branch, task, 'Cancelled')
                        self.config_dic['BLOCK'][block][version][flow][vendor][branch][task].Status = 'Cancelled'
                else:
                    current_task_obj = self.config_dic['BLOCK'][block][version][flow][vendor][branch][task]

                    if current_task_obj.get('Status') in ['Running', 'Killing']:
                        while current_task_obj.get('Status') in ['Running', 'Killing']:
                            time.sleep(5)
                    else:
                        self.run_one_task(block, version, flow, vendor, branch, task)

        elif run_type == 'parallel':
            thread_list = []

            for t in tasks:
                block, version, flow, vendor, branch, task = t
                thread = threading.Thread(target=self.run_one_task, args=(block, version, flow, vendor, branch, task))
                thread.start()
                thread_list.append(thread)

            for t in thread_list:
                t.join()

    def set_all_tasks_status_queued(self):
        for task in self.task_list:
            if task.Status not in ['Running', 'Killing']:
                task.Status = 'Queued'
                self.start_one_signal.emit(task.Block, task.Version, task.Flow, task.Vendor, task.Branch, task.Task, 'Queued')
                self.set_run_time_signal.emit(task.Block, task.Version, task.Flow, task.Vendor, task.Branch, task.Task, 'Runtime', None)

    def run(self):
        if self.action == 'RUN':
            self.msg_signal.emit('>>> Running tasks ...')
        elif self.action == 'POST_RUN':
            self.msg_signal.emit('>>> Post_Running tasks ...')

        self.set_all_tasks_status_queued()
        self.run_block_version()

        # Tell GUI run done.
        self.finish_signal.emit()


class IfpKill(IfpCommon):
    """
    With distributed mode, this class is used to kill related jobs.
    """
    start_one_signal = pyqtSignal(str, str, str, str, str, str, str)
    finish_one_signal = pyqtSignal(str, str, str, str, str, str, str)
    finish_signal = pyqtSignal()
    msg_signal = pyqtSignal(str)

    def __init__(self, task_list, config_dic, debug=False):
        super().__init__(task_list, config_dic, debug)

    def kill_one_task(self, item):
        block = item.Block
        version = item.Version
        flow = item.Flow
        vendor = item.Vendor
        branch = item.Branch
        task = item.Task
        jobid = item.Job
        status = item.Status

        if status == 'Running':
            self.msg_signal.emit('Killing {} {} {} {} {} {}'.format(block, version, flow, vendor, branch, task))
            self.config_dic['BLOCK'][block][version][flow][vendor][branch][task].Status = 'Killing'
            self.start_one_signal.emit(block, version, flow, vendor, branch, task, 'Killing')

            if str(jobid).startswith('b'):
                jobid = str(jobid)[2:]
                (return_code, stdout, stderr) = common.run_command('bkill ' + str(jobid))

                if return_code:
                    self.msg_signal.emit('Failed on killing job "' + str(jobid) + '"')
            elif str(jobid).startswith('l'):
                jobid = str(jobid)[2:]
                kill_process = 'kill -9 {}'.format(jobid)
                (return_code, stdout, stderr) = common.run_command(kill_process)

                if not return_code:
                    self.config_dic['BLOCK'][block][version][flow][vendor][branch][task].Status = 'Killed'
                    self.finish_one_signal.emit(block, version, flow, vendor, branch, task, 'Killed')

    def run(self):
        for item in self.task_list:
            self.kill_one_task(item)


class IfpCheck(IfpCommon):
    """
    This calss is used to check task result.
    """
    start_one_signal = pyqtSignal(str, str, str, str, str, str, str)
    finish_one_signal = pyqtSignal(str, str, str, str, str, str, str)
    finish_signal = pyqtSignal()
    msg_signal = pyqtSignal(str)

    def __init__(self, task_list, config_dic, debug=False):
        super().__init__(task_list, config_dic, debug)

    def check_one_task(self, block, version, flow, vendor, branch, task):
        # check_command can read and use these information.
        set_command_env(block, version, flow, vendor, branch, task)

        # Run check_command under branch directory.
        check_action = self.config_dic['BLOCK'][block][version][flow][vendor][branch][task]['ACTION'].get('CHECK', None)
        result = ''

        if check_action and check_action.get('COMMAND'):
            # Tell GUI the task check start.
            self.start_one_signal.emit(block, version, flow, vendor, branch, task, 'Checking')

            command = check_action.get('COMMAND')

            if ('PATH' in check_action) and (check_action['PATH']) and (os.path.exists(check_action['PATH'])):
                command = 'cd ' + str(check_action['PATH']) + '; ' + str(command)
            else:
                common.print_error('*Error*: Check path "' + str(check_action['PATH']) + '" is missing.')

            return_code, stdout, stderr = common.run_command(command)

            if return_code == 0:
                result = 'PASSED'
            else:
                result = 'FAILED'

            self.print_output(block, version, flow, vendor, branch, task, result, stdout + stderr)
        else:
            result = 'CHECK undefined'

        # Tell GUI the check check result.
        self.finish_one_signal.emit(block, version, flow, vendor, branch, task, result)

    def run(self):
        self.msg_signal.emit('>>> Checking results ...')

        thread_list = []

        for task in self.task_list:
            thread = threading.Thread(target=self.check_one_task, args=(task.Block, task.Version, task.Flow, task.Vendor, task.Branch, task.Task))
            thread_list.append(thread)
            thread.start()

        for thread in thread_list:
            thread.join()

        # Tell GUI check done.
        self.finish_signal.emit()


class IfpCheckView(IfpCommon):
    """
    This calss is used to view checklist result.
    """
    def __init__(self, task_list, config_dic, debug=False):
        super().__init__(task_list, config_dic, debug)

    def check_one_task(self, block, version, flow, vendor, branch, task):
        # check_command can read and use these information.
        set_command_env(block, version, flow, vendor, branch, task)

        # Run viewer command under task check directory.
        check_action = self.config_dic['BLOCK'][block][version][flow][vendor][branch][task]['ACTION'].get('CHECK', None)

        if check_action:
            if ('PATH' in check_action) and check_action['PATH'] and (os.path.exists(check_action['PATH'])):
                if ('REPORT_FILE' in check_action) and check_action['REPORT_FILE']:
                    if ('VIEWER' in check_action) and check_action['VIEWER']:
                        command = 'cd ' + str(check_action['PATH']) + '; ' + str(check_action['VIEWER']) + ' ' + str(check_action['REPORT_FILE'])
                        common.run_command(command)
            else:
                common.print_error('*Error*: Check path "' + str(check_action['PATH']) + '" is missing.')

    def run(self):
        thread_list = []

        for task in self.task_list:
            thread = threading.Thread(target=self.check_one_task, args=(task.Block, task.Version, task.Flow, task.Vendor, task.Branch, task.Task))
            thread_list.append(thread)
            thread.start()

        for thread in thread_list:
            thread.join()


class IfpSummary(IfpCommon):
    start_one_signal = pyqtSignal(str, str, str, str, str, str, str)
    finish_one_signal = pyqtSignal(str, str, str, str, str, str, str)
    finish_signal = pyqtSignal()
    msg_signal = pyqtSignal(str)

    def __init__(self, task_list, config_dic, debug=False):
        super().__init__(task_list, config_dic, debug)

    def sum_one_task(self, block, version, flow, vendor, branch, task):
        # check_command can read and use these information.
        set_command_env(block, version, flow, vendor, branch, task)

        # Run check_command under branch directory.
        sum_action = self.config_dic['BLOCK'][block][version][flow][vendor][branch][task]['ACTION'].get('SUMMARY', None)

        if sum_action and sum_action.get('COMMAND'):
            # Tell GUI the task check start.
            self.start_one_signal.emit(block, version, flow, vendor, branch, task, 'Summing')

            command = sum_action.get('COMMAND')

            if ('PATH' in sum_action) and (sum_action['PATH']) and (os.path.exists(sum_action['PATH'])):
                command = 'cd ' + str(sum_action['PATH']) + '; ' + str(command)
            else:
                common.print_error('*Error*: Summary path "' + str(sum_action['PATH']) + '" is missing.')

            (return_code, stdout, stderr) = common.run_command(command)

            if return_code == 0:
                result = 'SUM PASS'
            else:
                result = 'SUM FAIL'

            self.print_output(block, version, flow, vendor, branch, task, result, stdout + stderr)
        else:
            result = 'SUMMARY undefined'

        # Tell GUI the check summary result.
        self.finish_one_signal.emit(block, version, flow, vendor, branch, task, result)

    def run(self):
        self.msg_signal.emit('>>> Summarying results ...')

        thread_list = []

        for task in self.task_list:
            thread = threading.Thread(target=self.sum_one_task, args=(task.Block, task.Version, task.Flow, task.Vendor, task.Branch, task.Task))
            thread_list.append(thread)
            thread.start()

        for thread in thread_list:
            thread.join()

        self.msg_signal.emit('>>> Summarying Done')
        # Tell GUI check done.
        self.finish_signal.emit()


class IfpSummaryView(IfpCommon):
    """
    This calss is used to view summary result.
    """
    def __init__(self, task_list, config_dic, debug=False):
        super().__init__(task_list, config_dic, debug)

    def sum_one_task(self, block, version, flow, vendor, branch, task):
        # sum_command can read and use these information.
        set_command_env(block, version, flow, vendor, branch, task)

        # Run viewer command under task summary directory.
        sum_action = self.config_dic['BLOCK'][block][version][flow][vendor][branch][task]['ACTION'].get('SUMMARY', None)

        if sum_action:
            if ('PATH' in sum_action) and sum_action['PATH'] and (os.path.exists(sum_action['PATH'])):
                if ('REPORT_FILE' in sum_action) and sum_action['REPORT_FILE']:
                    if ('VIEWER' in sum_action) and sum_action['VIEWER']:
                        command = 'cd ' + str(sum_action['PATH']) + '; ' + str(sum_action['VIEWER']) + ' ' + str(sum_action['REPORT_FILE'])
                        common.run_command(command)
            else:
                common.print_error('*Error*: Summary path "' + str(sum_action['PATH']) + '" is missing.')

    def run(self):
        thread_list = []

        for task in self.task_list:
            thread = threading.Thread(target=self.sum_one_task, args=(task.Block, task.Version, task.Flow, task.Vendor, task.Branch, task.Task))
            thread_list.append(thread)
            thread.start()

        for thread in thread_list:
            thread.join()


class IfpRelease(IfpCommon):
    """
    This class is used to release if needed.
    """
    start_one_signal = pyqtSignal(str, str, str, str, str, str, str)
    finish_one_signal = pyqtSignal(str, str, str, str, str, str, str)
    finish_signal = pyqtSignal()
    msg_signal = pyqtSignal(str)

    def __init__(self, task_list, config_dic, debug=False):
        super().__init__(task_list, config_dic, debug)

    def release_one_task(self, block, version, flow, vendor, branch, task):
        # check_command can read and use these information.
        set_command_env(block, version, flow, vendor, branch, task)

        # Run check_command under branch directory.
        release_action = self.config_dic['BLOCK'][block][version][flow][vendor][branch][task]['ACTION'].get('RELEASE', None)

        if release_action and release_action.get('COMMAND'):
            # Tell GUI the task check start.
            self.start_one_signal.emit(block, version, flow, vendor, branch, task, 'Releasing')

            command = release_action.get('COMMAND')

            if ('PATH' in release_action) and (release_action['PATH']) and (os.path.exists(release_action['PATH'])):
                command = 'cd ' + str(release_action['PATH']) + '; ' + str(command)
            else:
                common.print_error('*Error*: Release path "' + str(release_action['PATH']) + '" is missing.')

            (return_code, stdout, stderr) = common.run_command(command)

            if return_code == 0:
                result = 'RELEASE PASS'
            else:
                result = 'RELEASE FAIL'

            self.print_output(block, version, flow, vendor, branch, task, result, stdout + stderr)
        else:
            result = 'RELEASE undefined'

        # Tell GUI the check release result.
        self.finish_one_signal.emit(block, version, flow, vendor, branch, task, result)

    def run(self):
        self.msg_signal.emit('>>> Releasing...')

        thread_list = []

        for task in self.task_list:
            thread = threading.Thread(target=self.release_one_task, args=(task.Block, task.Version, task.Flow, task.Vendor, task.Branch, task.Task))
            thread_list.append(thread)
            thread.start()

        for thread in thread_list:
            thread.join()

        self.msg_signal.emit('>>> Release Done')
        # Tell GUI check done.
        self.finish_signal.emit()
