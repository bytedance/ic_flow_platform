# -*- coding: utf-8 -*-
################################
# File Name   : function.py
# Author      : liyanqing
# Created On  : 2022-06-07 20:08:51
# Description :
################################
import os
import sys
import threading
import datetime
from PyQt5.QtCore import QThread, pyqtSignal
from collections import defaultdict

sys.path.append(str(os.environ['IFP_INSTALL_PATH']) + '/common')
import common


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

    def print_output(self, block, version, flow, vendor, branch, task, output):
        self.debug_print('')
        self.debug_print('Block(' + str(block) + ')  Version(' + str(version) + ')  Flow(' + str(flow) + ')  Vendor(' + str(vendor) + ')  Branch(' + str(branch) + ')  Task(' + str(task) + ')')
        self.debug_print('----------------')

        try:
            for line in str(output, 'utf-8').split('\n'):
                if line:
                    self.debug_print(line)
        except:
            pass

        self.debug_print('----------------')
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

                self.print_output(block, version, flow, vendor, branch, task, stdout + stderr)
        else:
            result = 'BUILD undefined'

        # Tell GUI the build result.
        self.finish_one_signal.emit(block, version, flow, vendor, branch, task, result)

    def run(self):
        self.msg_signal.emit('>>> Building blocks ...')

        thread_list = []

        for item in self.task_list:
            thread = threading.Thread(target=self.build_one_task, args=(item,))
            thread.start()
            thread_list.append(thread)

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

    def __init__(self, task_list, config_dic, debug=False, ignore_fail=False, xterm_mode=False):
        super().__init__(task_list, config_dic, debug)

        self.ignore_fail = ignore_fail
        self.xterm_mode = xterm_mode
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

                if list(filter(lambda x: x.Status == 'Cancelled' or x.Status == 'Killed', pre_flows_bundle_tasks)):
                    for flow in flow_bundle.split('|'):
                        flow_tasks = list(filter(lambda x: x.Flow == flow, tasks))

                        for t in flow_tasks:
                            self.start_one_signal.emit(t.Block, t.Version, t.Flow, t.Vendor, t.Branch, t.Task, 'Cancelled')
                else:
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
        run_action = self.config_dic['BLOCK'][block][version][flow][vendor][branch][task]['ACTION'].get('RUN', None)
        result = ''
        start_time = datetime.datetime.now()

        if run_action and run_action.get('COMMAND'):
            # Tell GUI the task run start.
            self.start_one_signal.emit(block, version, flow, vendor, branch, task, 'Running')

            run_method = run_action.get('RUN_METHOD', 'local')
            self.msg_signal.emit('*Info*: running {} "{}" under {} for {} {} {} {} {} {}\n'.format(run_method,
                                                                                                   run_action['PATH'],
                                                                                                   run_action['COMMAND'],
                                                                                                   block,
                                                                                                   version,
                                                                                                   flow,
                                                                                                   vendor,
                                                                                                   branch,
                                                                                                   task))

            command = run_action['COMMAND']

            if ('PATH' in run_action) and (run_action['PATH']) and (os.path.exists(run_action['PATH'])):
                command = 'cd ' + str(run_action['PATH']) + '; ' + str(command)
            else:
                common.print_error('*Error*: Run path "' + str(run_action['PATH']) + '" is missing.')

            job_id = None

            if run_method == 'local':
                if self.xterm_mode:
                    command = 'xterm -e ' + str(command)

                process = common.spawn_process(command)
                job_id = 'l:{}'.format(process.pid)
            else:
                command = str(run_method) + ' "' + str(command) + '"'

                if self.xterm_mode:
                    command = 'xterm -e ' + str(command)

                process = common.spawn_process(command)
                stdout = process.stdout.readline()
                job_id = 'b:{}'.format(common.get_jobid(stdout))

            self.set_one_jobid_signal.emit(block, version, flow, vendor, branch, task, 'Job', str(job_id))
            stdout, stderr = process.communicate()
            return_code = process.returncode

            finish_time = datetime.datetime.now()
            last_status = self.config_dic['BLOCK'][block][version][flow][vendor][branch][task].get('Status', None)

            if return_code == 0:
                result = 'RUN PASS'
            else:
                result = 'RUN FAIL'

                self.print_output(block, version, flow, vendor, branch, task, stdout + stderr)

            if last_status == 'Killed':
                result = last_status
                self.msg_signal.emit('*Info*: job killed for {} {} {} {} {} {}\n'.format(block, version, flow, vendor, branch, task))
            else:
                self.msg_signal.emit('*Info*: job done for {} {} {} {} {} {}\n'.format(block, version, flow, vendor, branch, task))
        else:
            finish_time = datetime.datetime.now()
            result = 'RUN undefined'

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
                    pre_block, pre_version, pre_flow, pre_vendor, pre_branch, pre_task = tasks[i-1]
                    pre_task_obj = self.config_dic['BLOCK'][pre_block][pre_version][pre_flow][pre_vendor][pre_branch][pre_task]

                    if (pre_task_obj.get('Status') == 'RUN PASS') or self.ignore_fail:
                        self.run_one_task(block, version, flow, vendor, branch, task)

                    if (pre_task_obj.get('Status') in ['RUN FAIL', 'Killed', 'Killing', 'Cancelled']) and (not self.ignore_fail):
                        self.start_one_signal.emit(block, version, flow, vendor, branch, task, 'Cancelled')
                        self.config_dic['BLOCK'][block][version][flow][vendor][branch][task].Status = 'Cancelled'
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
            task.Status = 'Queued'
            self.start_one_signal.emit(task.Block, task.Version, task.Flow, task.Vendor, task.Branch, task.Task, 'Queued')
            self.set_run_time_signal.emit(task.Block, task.Version, task.Flow, task.Vendor, task.Branch, task.Task, 'Runtime', None)

    def run(self):
        self.msg_signal.emit('>>> Running tasks ...')

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

        self.msg_signal.emit('Killing {} {} {} {} {} {}'.format(block, version, flow, vendor, branch, task))
        self.config_dic['BLOCK'][block][version][flow][vendor][branch][task].Status = 'Killing'
        self.start_one_signal.emit(block, version, flow, vendor, branch, task, 'Killing')

        if str(jobid).startswith('b'):
            jobid = str(jobid)[2:]
            kill_bjob = 'bkill {}'.format(jobid)
            (return_code, stdout, stderr) = common.run_command(kill_bjob)

            if not return_code:
                self.config_dic['BLOCK'][block][version][flow][vendor][branch][task].Status = 'Killed'
                self.finish_one_signal.emit(block, version, flow, vendor, branch, task, 'Killed')
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

                self.print_output(block, version, flow, vendor, branch, task, stdout + stderr)
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

                self.print_output(block, version, flow, vendor, branch, task, stdout + stderr)
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


class IfpPostRun(IfpCommon):
    """
    Some task may have post-run requirement, this class will execute specified command after run.
    """
    start_one_signal = pyqtSignal(str, str, str, str, str, str, str)
    finish_one_signal = pyqtSignal(str, str, str, str, str, str, str)
    finish_signal = pyqtSignal()
    msg_signal = pyqtSignal(str)

    def __init__(self, task_list, config_dic, debug=False):
        super().__init__(task_list, config_dic, debug)

    def post_run_one_task(self, block, version, flow, vendor, branch, task):
        # check_command can read and use these information.
        set_command_env(block, version, flow, vendor, branch, task)

        # Run check_command under branch directory.
        postrun_action = self.config_dic['BLOCK'][block][version][flow][vendor][branch][task]['ACTION'].get('POST_RUN', None)

        if postrun_action and postrun_action.get('COMMAND'):
            # Tell GUI the task check start.
            self.start_one_signal.emit(block, version, flow, vendor, branch, task, 'PostRunning')

            command = postrun_action.get('COMMAND')

            if ('PATH' in postrun_action) and (postrun_action['PATH']) and (os.path.exists(postrun_action['PATH'])):
                command = 'cd ' + str(postrun_action['PATH']) + '; ' + str(command)
            else:
                common.print_error('*Error*: Post_run path "' + str(postrun_action['PATH']) + '" is missing.')

            (return_code, stdout, stderr) = common.run_command(command)

            if return_code == 0:
                result = 'POSTRUN PASS'
            else:
                result = 'POSTRUN FAIL'

                self.print_output(block, version, flow, vendor, branch, task, stdout + stderr)
        else:
            result = 'POSTRUN undefined'

        # Tell GUI the check post_run result.
        self.finish_one_signal.emit(block, version, flow, vendor, branch, task, result)

    def run(self):
        self.msg_signal.emit('>>> PostRunning tasks...')

        thread_list = []

        for task in self.task_list:
            thread = threading.Thread(target=self.post_run_one_task, args=(task.Block, task.Version, task.Flow, task.Vendor, task.Branch, task.Task))
            thread_list.append(thread)
            thread.start()

        for thread in thread_list:
            thread.join()

        self.msg_signal.emit('>>> PostRun Done')
        # Tell GUI check done.
        self.finish_signal.emit()


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

                self.print_output(block, version, flow, vendor, branch, task, stdout + stderr)
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
