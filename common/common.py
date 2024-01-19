import os
import re
import sys
import psutil
import signal
import subprocess
import threading
from PyQt5.QtCore import QThread
from PyQt5.QtWidgets import QMessageBox

import common_pyqt5


def print_error(message):
    """
    Print error message with red color.
    """
    print('\033[1;31m' + str(message) + '\033[0m')


def print_warning(message):
    """
    Print warning message with yellow color.
    """
    print('\033[1;33m' + str(message) + '\033[0m')


def run_command(command, shell=True):
    """
    Run shell command with subprocess.Popen.
    """
    SP = subprocess.Popen(command, shell=shell, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (stdout, stderr) = SP.communicate()
    return_code = SP.returncode
    return (return_code, stdout, stderr)


def spawn_process(command, shell=True):
    """
    Return the underlying Popen obj
    """
    SP = subprocess.Popen(command, shell=shell, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return SP


def get_jobid(stdout):
    """
    Get jobid information from LSF output message.
    The message just like "Job <29920> is submitted to ***".
    """
    jobid = None

    for line in stdout.split('\n'):
        if re.match(r'^Job\s+\<(\d+)\>\s+is\s+submitted\s+to.*$', line):
            my_match = re.match(r'^Job\s+\<(\d+)\>\s+is\s+submitted\s+to.*$', line)
            jobid = my_match.group(1)

    return jobid


def kill_pid_tree(pid):
    """
    Specify the top pid, then kill pid/sub-pid on the pid tree.
    """
    if re.match(r'^\d+$', str(pid)):
        p = psutil.Process(int(pid))

        for p_child in p.children():
            child_pid = p_child.pid
            kill_pid_tree(child_pid)
            os.kill(child_pid, signal.SIGTERM)


def gen_group_project_seq_list(project=None, group=None):
    """
    priorty: project, group --> group --> project --> none
    """
    group_project_seq_list = []

    if group and project:
        group_project_seq_list.append('.'.join([project, group]))
        group_project_seq_list.append('.'.join([group, project]))

    if group:
        group_project_seq_list.append(group)

    if project:
        group_project_seq_list.append(project)

    return group_project_seq_list


def get_default_yaml_path(project=None, group=None):
    """
    get default.yaml filepath from project & group
    dir priority: ~/.ifp/config/, <INSTALL_PATH>/config
    if can not find any default.yaml, return None
    """
    # default yaml dir:
    user_yaml_path = os.path.join(os.path.expanduser('~'), '.ifp/config')
    install_yaml_path = os.path.join(str(os.environ['IFP_INSTALL_PATH']), 'config')
    yaml_path_list = [user_yaml_path, install_yaml_path]

    # default yaml name:
    yaml_file_list = []
    group_project_seq_list = gen_group_project_seq_list(project, group)

    for seq in group_project_seq_list:
        yaml_file_list.append('default.' + seq + '.yaml')

    yaml_file_list.append('default.yaml')

    for path in yaml_path_list:
        for file in yaml_file_list:
            default_yaml_path = os.path.join(path, file)

            if os.path.exists(default_yaml_path):
                return default_yaml_path


def get_env_dic(project=None, group=None):
    env_dic = {}
    env_file = ''

    group_project_seq_list = gen_group_project_seq_list(project, group)

    env_path = str(os.environ['IFP_INSTALL_PATH']) + '/config'
    env_file_list = []

    if re.match('^.*/csh$', os.environ['SHELL']) or re.match('^.*/tcsh$', os.environ['SHELL']):
        env_postfix = '.csh'
    else:
        env_postfix = '.sh'

    for seq in group_project_seq_list:
        env_file_list.append('env.' + seq + env_postfix)

    env_file_list.append('env.sh')

    for file in env_file_list:
        env_file = os.path.join(env_path, file)

        if os.path.exists(env_file):
            break

    if os.path.exists(env_file):
        command = 'source ' + str(env_file) + '; env'
        (return_code, stdout, stderr) = run_command(command)
        env_compile = re.compile(r'^(\S+?)=(.+)$')

        for line in stdout.decode('utf-8').split('\n'):
            if env_compile.match(line):
                my_match = env_compile.match(line)

                if my_match.group(1).startswith('BASH_FUNC_'):
                    continue

                env_dic.setdefault(my_match.group(1), my_match.group(2))
    else:
        common_pyqt5.Dialog('Env configuration warning', 'Not find any environment configuration file "' + str(env_file) + '".', icon=QMessageBox.Warning)

    return env_dic


class ThreadRun(QThread):
    """
    This class is used to run command on a thread.
    """

    def __init__(self):
        super().__init__()

    def run(self, command_list):
        for command in command_list:
            thread = threading.Thread(target=run_command, args=(command,))
            thread.start()


class TaskStatus:
    def __init__(self):
        self.building = 'Building'
        self.running = 'Running'
        self.checking = 'Checking'
        self.summarizing = 'Summarizing'
        self.releasing = 'Releasing'
        self.killed = 'Killed'
        self.killing = 'Killing'
        self.queued = 'Queued'
        self.cancelled = 'Cancelled'
        self.passed = 'Pass'
        self.failed = 'Fail'
        self.undefined = 'Undefined'

class TaskAction:
    def __init__(self):
        self.build = 'Build'
        self.run = 'Run'
        self.check = 'Check'
        self.check_view = 'Check View'
        self.summarize = 'Summarize'
        self.summarize_view = 'Summarize View'
        self.release = 'Release'
        self.kill = 'Kill'

class ConfigSetting:
    def __init__(self):
        self.admin_setting_dic = {
                'default_yaml_administrators': {'value': '', 'note': 'Only default_yaml_administrators can edit default.yaml on ifp GUI directory.'},
                'system_log_path': {'value': '', 'note': 'system log'},
                'lmstat_path': {'value': '', 'note': 'Specify lmstat path, example "/eda/synopsys/scl/2021.03/linux64/bin/lmstat".'}
                }
        self.user_setting_dic = {
                'send_result_command': {'value': '', 'note': 'send result command'},
                'xterm_command': {'value': 'xterm -e', 'note': 'xterm command.'}, 
                'fullscreen_flag': {'value': True, 'note': 'launch ifp in fullscreen'}, 
                'rerun_flag': {'value': True, 'note': 'remind user to confirm if rerun passed tasks'},
                'ignore_fail': {'value': False, 'note': 'task will run even if dependent tasks failed'}, 
                'send_result': {'value': False, 'note': 'send result to users after action done'},
                'auto_import_tasks': {'value': True, 'note': 'import all tasks when add new block/version'}, 
                'rerun_check_or_summarize_before_view': {'value': True, 'note': 'Auto rerun CHECK(SUMMARIZE) command before view check(summarize) report'}
                }


config = ConfigSetting()
status = TaskStatus()
action = TaskAction()
status_ing = {action.build: status.building,
              action.run: status.running,
              action.check: status.checking,
              action.summarize: status.summarizing,
              action.release: status.releasing}
UNEXPECTED_JOB_STATUS = [status.killed, status.killing, status.cancelled, '{} {}'.format(action.run, status.failed)]
CLOSE_REMIND_STATUS = [status.building, status.running, status.checking, status.summarizing, status.releasing]
ING_STATUS = [status.building, status.running]
CONFIG_DIC = {**config.admin_setting_dic, **config.user_setting_dic}
