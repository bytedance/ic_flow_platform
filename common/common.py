import copy
import datetime
import os
import re
from string import Template

import psutil
import signal
import subprocess
import threading

import yaml
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import QMessageBox, QAction

import time

import common_pyqt5

def bprint(message, color='', background_color='', display_method='', date_format='', level='', indent=0, save_file='', save_file_method='a'):
    """
    Enhancement of "print" function.

    color:            Specify font foreground color, default to follow the terminal settings.
    background_color: Specify font background color, default to follow the terminal settings.
    display_method:   Specify font display method, default to follow the terminal settings.
    date_format:      Will show date/time information before the message, such as "%Y_%m_%d %H:%M:%S". Default is "", means silent mode.
    level:            Will show message level information after date/time information, default is "", means show nothing.
    Indent:           How much spaces to indent for specified message (with level information), default is 0, means no indentation.
    save_file:        Save message into specified file, default is "", means save nothing.
    save_file_method: Save message with "append" or "write" mode, default is "append" mode.

    For "color" and "background_color":
    -----------------------------------------------
    字体色   |   背景色   |   Color    |   颜色描述
    -----------------------------------------------
    30       |   40       |   black    |   黑色
    31       |   41       |   red      |   红色
    32       |   42       |   green    |   绿色
    33       |   43       |   yellow   |   黃色
    34       |   44       |   blue     |   蓝色
    35       |   45       |   purple   |   紫色
    36       |   46       |   cyan     |   青色
    37       |   47       |   white    |   白色
    -----------------------------------------------

    For "display_method":
    ---------------------------
    显示方式   |   效果
    ---------------------------
    0          |   终端默认设置
    1          |   高亮显示
    4          |   使用下划线
    5          |   闪烁
    7          |   反白显示
    8          |   不可见
    ---------------------------

    For "level":
    -------------------------------------------------------------
    层级      |   说明
    -------------------------------------------------------------
    Debug     |   程序运行的详细信息, 主要用于调试.
    Info      |   程序运行过程信息, 主要用于将系统状态反馈给用户.
    Warning   |   表明会出现潜在错误, 但是一般不影响系统继续运行.
    Error     |   发生错误, 不确定系统是否可以继续运行.
    Fatal     |   发生严重错误, 程序会停止运行并退出.
    -------------------------------------------------------------

    For "save_file_method":
    -----------------------------------------------------------
    模式   |   说明
    -----------------------------------------------------------
    a      |   append mode, append content to existing file.
    w      |   write mode, create a new file and write content.
    -----------------------------------------------------------
    """
    # Check arguments.
    color_dic = {'black': 30,
                 'red': 31,
                 'green': 32,
                 'yellow': 33,
                 'blue': 34,
                 'purple': 35,
                 'cyan': 36,
                 'white': 37}

    if color:
        if (color not in color_dic.keys()) and (color not in color_dic.values()):
            bprint('*Warning* (bprint): Meet some setting problem with below message.', date_format='', color=33, display_method=1)
            bprint('                    ' + str(message), date_format='', color=33, display_method=1)
            bprint('*Warning* (bprint): "' + str(color) + '": Invalid color setting, it must follow below rules.', date_format='', color=33, display_method=1)
            bprint('''
                    ----------------------------------
                    字体色   |   Color    |   颜色描述
                    ----------------------------------
                    30       |   black    |   黑色
                    31       |   red      |   红色
                    32       |   green    |   绿色
                    33       |   yellow   |   黃色
                    34       |   blue     |   蓝色
                    35       |   purple   |   紫色
                    36       |   cyan     |   青色
                    37       |   white    |   白色
                    ----------------------------------
            ''', date_format='', color=33, display_method=1)

            return

    background_color_dic = {'black': 40,
                            'red': 41,
                            'green': 42,
                            'yellow': 43,
                            'blue': 44,
                            'purple': 45,
                            'cyan': 46,
                            'white': 47}

    if background_color:
        if (background_color not in background_color_dic.keys()) and (background_color not in background_color_dic.values()):
            bprint('*Warning* (bprint): Meet some setting problem with below message.', date_format='', color=33, display_method=1)
            bprint('                    ' + str(message), date_format='', color=33, display_method=1)
            bprint('*Warning* (bprint): "' + str(background_color) + '": Invalid background_color setting, it must follow below rules.', date_format='', color=33, display_method=1)
            bprint('''
                    ----------------------------------
                    背景色   |   Color    |   颜色描述
                    ----------------------------------
                    40       |   black    |   黑色
                    41       |   red      |   红色
                    42       |   green    |   绿色
                    43       |   yellow   |   黃色
                    44       |   blue     |   蓝色
                    45       |   purple   |   紫色
                    46       |   cyan     |   青色
                    47       |   white    |   白色
                    ----------------------------------
            ''', date_format='', color=33, display_method=1)

            return

    if display_method:
        valid_display_method_list = [0, 1, 4, 5, 7, 8]

        if display_method not in valid_display_method_list:
            bprint('*Warning* (bprint): Meet some setting problem with below message.', date_format='', color=33, display_method=1)
            bprint('                    ' + str(message), date_format='', color=33, display_method=1)
            bprint('*Warning* (bprint): "' + str(display_method) + '": Invalid display_method setting, it must be integer between 0,1,4,5,7,8.', date_format='', color=33, display_method=1)
            bprint('''
                    ----------------------------
                    显示方式   |    效果
                    ----------------------------
                    0          |    终端默认设置
                    1          |    高亮显示
                    4          |    使用下划线
                    5          |    闪烁
                    7          |    反白显示
                    8          |    不可见
                    ----------------------------
            ''', date_format='', color=33, display_method=1)

            return

    if level:
        valid_level_list = ['Debug', 'Info', 'Warning', 'Error', 'Fatal']

        if level not in valid_level_list:
            bprint('*Warning* (bprint): Meet some setting problem with below message.', date_format='', color=33, display_method=1)
            bprint('                    ' + str(message), date_format='', color=33, display_method=1)
            bprint('*Warning* (bprint): "' + str(level) + '": Invalid level setting, it must be Debug/Info/Warning/Error/Fatal.', date_format='', color=33, display_method=1)
            bprint('''
                    -------------------------------------------------------------
                    层级      |   说明
                    -------------------------------------------------------------
                    Debug     |   程序运行的详细信息, 主要用于调试.
                    Info      |   程序运行过程信息, 主要用于将系统状态反馈给用户.
                    Warning   |   表明会出现潜在错误, 但是一般不影响系统继续运行.
                    Error     |   发生错误, 不确定系统是否可以继续运行.
                    Fatal     |   发生严重错误, 程序会停止运行并退出.
                    -------------------------------------------------------------
            ''', date_format='', color=33, display_method=1)
            return

    if not re.match(r'^\d+$', str(indent)):
        bprint('*Warning* (bprint): Meet some setting problem with below message.', date_format='', color=33, display_method=1)
        bprint('                    ' + str(message), date_format='', color=33, display_method=1)
        bprint('*Warning* (bprint): "' + str(indent) + '": Invalid indent setting, it must be a positive integer, will reset to "0".', date_format='', color=33, display_method=1)

        indent = 0

    if save_file:
        valid_save_file_method_list = ['a', 'append', 'w', 'write']

        if save_file_method not in valid_save_file_method_list:
            bprint('*Warning* (bprint): Meet some setting problem with below message.', date_format='', color=33, display_method=1)
            bprint('                    ' + str(message), date_format='', color=33, display_method=1)
            bprint('*Warning* (bprint): "' + str(save_file_method) + '": Invalid save_file_method setting, it must be "a" or "w".', date_format='', color=33, display_method=1)
            bprint('''
                    -----------------------------------------------------------
                    模式   |   说明
                    -----------------------------------------------------------
                    a      |   append mode, append content to existing file.
                    w      |   write mode, create a new file and write content.
                    -----------------------------------------------------------
            ''', date_format='', color=33, display_method=1)

            return

    # Set default color/background_color/display_method setting for different levels.
    if level:
        if level == 'Warning':
            if not display_method:
                display_method = 1

            if not color:
                color = 33
        elif level == 'Error':
            if not display_method:
                display_method = 1

            if not color:
                color = 31
        elif level == 'Fatal':
            if not display_method:
                display_method = 1

            if not background_color:
                background_color = 41

            if background_color == 41:
                if not color:
                    color = 37
            else:
                if not color:
                    color = 35

    # Get final color setting.
    final_color_setting = ''

    if color or background_color or display_method:
        final_color_setting = '\033['

        if display_method:
            final_color_setting = str(final_color_setting) + str(display_method)

        if color:
            if not re.match(r'^\d{2}$', str(color)):
                color = color_dic[color]

            if re.match(r'^.*\d$', final_color_setting):
                final_color_setting = str(final_color_setting) + ';' + str(color)
            else:
                final_color_setting = str(final_color_setting) + str(color)

        if background_color:
            if not re.match(r'^\d{2}$', str(background_color)):
                background_color = background_color_dic[background_color]

            if re.match(r'^.*\d$', final_color_setting):
                final_color_setting = str(final_color_setting) + ';' + str(background_color)
            else:
                final_color_setting = str(final_color_setting) + str(background_color)

        final_color_setting = str(final_color_setting) + 'm'

    # Get current_time if date_format is specified.
    current_time = ''

    if date_format:
        try:
            current_time = datetime.datetime.now().strftime(date_format)
        except Exception:
            bprint('*Warning* (bprint): Meet some setting problem with below message.', date_format='', color=33, display_method=1)
            bprint('                    ' + str(message), date_format='', color=33, display_method=1)
            bprint('*Warning* (bprint): "' + str(date_format) + '": Invalid date_format setting, suggest to use the default setting.', date_format='', color=33, display_method=1)
            return

    # Print message with specified format.
    final_message = ''

    if current_time:
        final_message = str(final_message) + '[' + str(current_time) + '] '

    if indent > 0:
        final_message = str(final_message) + ' ' * indent

    if level:
        final_message = str(final_message) + '*' + str(level) + '*: '

    final_message = str(final_message) + str(message)

    if final_color_setting:
        final_message_with_color = final_color_setting + str(final_message) + '\033[0m'
    else:
        final_message_with_color = final_message

    print(final_message_with_color)

    # Save file.
    if save_file:
        try:
            with open(save_file, save_file_method) as SF:
                SF.write(str(final_message) + '\n')
        except Exception as warning:
            bprint('*Warning* (bprint): Meet some problem when saveing below message into file "' + str(save_file) + '".', date_format='', color=33, display_method=1)
            bprint('                    ' + str(message), date_format='', color=33, display_method=1)
            bprint('*Warning* (bprint): ' + str(warning), date_format='', color=33, display_method=1)
            return


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


def timer(func):
    def timer_wrapper(*args, **kwargs):
        time_start = time.time()
        result = func(*args, **kwargs)
        time_end = time.time()

        time_cost = time_end - time_start

        print('%s cost time: %.2f s' % (func.__name__, time_cost))
        return result
    return timer_wrapper


def run_command(command, shell=True):
    """
    Run shell command with subprocess.Popen.
    """
    SP = subprocess.Popen(command, shell=shell, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (stdout, stderr) = SP.communicate()
    return_code = SP.returncode
    return (return_code, stdout, stderr)


def run_command_for_api(command, msg_signal, path, gating_flag=False):
    """
    Run shell command with subprocess.Popen.
    """
    SP = subprocess.Popen(command, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=path)

    while SP.poll() is None:
        line = SP.stdout.readline().decode('utf8').strip()

        if line:
            if msg_signal:
                msg_signal.emit({'message': '[API] : %s' % line, 'color': 'black'})
            else:
                print('[API] : %s' % line)

    if gating_flag:
        (stdout, stderr) = SP.communicate()
        stderr = str(stderr, 'utf-8').strip()
        if msg_signal:
            msg_signal.emit({'message': '[API] : %s' % stderr, 'color': 'red'})
        else:
            print_error(stderr)


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


def get_user_ifp_config_path():
    return os.path.join(os.path.expanduser('~'), '.ifp/config')


def get_install_ifp_config_path():
    return os.path.join(str(os.environ['IFP_INSTALL_PATH']), 'config')


def get_default_yaml_path(project=None, group=None, key_word='default'):
    """
    get default.yaml filepath from project & group
    dir priority: ~/.ifp/config/, <INSTALL_PATH>/config
    if can not find any default.yaml, return None
    """
    # default yaml dir:
    user_yaml_path = get_user_ifp_config_path()
    install_yaml_path = get_install_ifp_config_path()
    yaml_path_list = [user_yaml_path, install_yaml_path]

    # default yaml name:
    yaml_file_list = []
    group_project_seq_list = gen_group_project_seq_list(project, group)

    for seq in group_project_seq_list:
        yaml_file_list.append('%s.' % str(key_word) + seq + '.yaml')

    yaml_file_list.append('%s.yaml' % str(key_word))

    for path in yaml_path_list:
        for file in yaml_file_list:
            default_yaml_path = os.path.join(path, file)

            if os.path.exists(default_yaml_path):
                return default_yaml_path


def parse_user_api(api_yaml):
    try:
        with open(api_yaml, 'r') as AF:
            yaml_file = yaml.load(AF, Loader=yaml.CLoader)
    except Exception:
        yaml_file = {}

    if not yaml_file:
        yaml_file = {}

    if 'API' not in yaml_file.keys():
        yaml_file['API'] = {}

    if 'PRE_CFG' in yaml_file['API'].keys():
        for item in yaml_file['API']['PRE_CFG']:
            if 'LABEL' not in item.keys():
                print('Please define LABEL for each API item!')
                exit(1)

            pre_ifp_items = ['LABEL', 'PATH', 'COMMAND', 'ENABLE', 'COMMENT']
            pre_ifp_must_items = ['LABEL', 'PATH', 'COMMAND']

            for key in pre_ifp_items:
                if key not in item.keys():
                    if key in pre_ifp_must_items:
                        print('You must define %s for PRE_CFG API, corresponding label is %s' % (key, item['LABEL']))
                        exit(1)

                    if key == 'ENABLE':
                        item[key] = True
                    else:
                        item[key] = ''
    else:
        yaml_file['API']['PRE_CFG'] = []

    if 'PRE_IFP' in yaml_file['API'].keys():
        for item in yaml_file['API']['PRE_IFP']:
            if 'LABEL' not in item.keys():
                print('Please define LABEL for each API item!')
                exit(1)

            pre_ifp_items = ['LABEL', 'PROJECT', 'GROUP', 'PATH', 'COMMAND', 'ENABLE', 'COMMENT']
            pre_ifp_must_items = ['LABEL', 'PATH', 'COMMAND']

            for key in pre_ifp_items:
                if key not in item.keys():
                    if key in pre_ifp_must_items:
                        print('You must define %s for PRE_IFP API, corresponding label is %s' % (key, item['LABEL']))
                        exit(1)

                    if key == 'ENABLE':
                        item[key] = True
                    else:
                        item[key] = ''
    else:
        yaml_file['API']['PRE_IFP'] = []

    if 'TABLE_RIGHT_KEY_MENU' in yaml_file['API'].keys():
        for item in yaml_file['API']['TABLE_RIGHT_KEY_MENU']:
            if 'LABEL' not in item.keys():
                print('Please define LABEL for each API item!')
                exit(1)

            right_key_items = ['LABEL', 'PROJECT', 'GROUP', 'TAB', 'COLUMN', 'PATH', 'COMMAND', 'ENABLE', 'COMMENT']
            right_key_must_items = ['LABEL', 'TAB', 'COLUMN', 'PATH', 'COMMAND']

            for key in right_key_items:
                if key not in item.keys():
                    if key in right_key_must_items:
                        if 'API-2' in item.keys() and key == 'COMMAND':
                            continue
                        else:
                            print('You must define %s for TABLE_RIGHT_KEY_MENU API, corresponding label is %s' % (key, item['LABEL']))
                            exit(1)

                    if key == 'ENABLE':
                        item[key] = True
                    else:
                        item[key] = ''

                elif key == 'API-2':
                    for item2 in item[key]:
                        if 'LABEL' not in item2.keys():
                            print('Please define LABEL for each API item!')
                            exit(1)

                        stage2_right_key_items = ['LABEL', 'COMMAND', 'ENABLE', 'COMMENT']
                        stage2_right_key_must_items = ['LABEL', 'COMMAND']

                        for key2 in stage2_right_key_items:
                            if key2 not in item2.keys():
                                if key2 in stage2_right_key_must_items:
                                    print('You must define %s for TABLE_RIGHT_KEY_MENU API, corresponding label is %s' % (key, item2['LABEL']))
                                    exit(1)

                                if key == 'ENABLE':
                                    item[key] = True
                                else:
                                    item2[key2] = ''

    else:
        yaml_file['API']['TABLE_RIGHT_KEY_MENU'] = []

    return yaml_file


def add_api_menu(ifp_obj, user_api, menu, project=None, group=None, tab=None, column=None, var_dic=None):
    if 'TABLE_RIGHT_KEY_MENU' in user_api['API'].keys():
        for item in user_api['API']['TABLE_RIGHT_KEY_MENU']:
            if not item['ENABLE']:
                continue

            if (not item['PROJECT'] or project == item['PROJECT']) and (not item['GROUP'] or group == item['GROUP']):
                pass
            else:
                continue

            match_flag = True
            tags = ['BLOCK', 'VERSION', 'FLOW', 'VENDOR', 'BRANCH', 'TASK']

            for tag in tags:
                if column == tag and '%s_NAME' % tag in item.keys() and tag in var_dic.keys() and item['%s_NAME' % tag]:
                    if not item['%s_NAME' % tag] == var_dic[tag]:
                        match_flag = False

            if not match_flag:
                continue

            if (not item['TAB'] or item['TAB'] == tab) and (not item['COLUMN'] or item['COLUMN'] == column):
                pass
            else:
                continue

            if 'API-2' in item.keys():
                sub_menu = menu.addMenu('[API]  ' + item['LABEL'])

                for item2 in item['API-2']:
                    if not item2['ENABLE']:
                        continue

                    action_obj = CreateAction('[API]  ' + item2['LABEL'], expand_var(item2['COMMAND'], ifp_var_dic=ifp_obj.config_obj.var_dic, **var_dic), expand_var(item2['PATH'], ifp_var_dic=ifp_obj.config_obj.var_dic, **var_dic))
                    action_obj.msg_signal.connect(ifp_obj.update_message_text)
                    sub_menu.addAction(action_obj.run())
            else:
                action_obj = CreateAction('[API]  ' + item['LABEL'], expand_var(item['COMMAND'], ifp_var_dic=ifp_obj.config_obj.var_dic, **var_dic), expand_var(item['PATH'], ifp_var_dic=ifp_obj.config_obj.var_dic, **var_dic))
                action_obj.msg_signal.connect(ifp_obj.update_message_text)
                menu.addAction(action_obj.run())


class CreateAction(QThread):
    msg_signal = pyqtSignal(dict)

    def __init__(self, action_name, command, path, checked=None):
        super().__init__()
        self.action_name = action_name
        self.command = command
        self.action = QAction(self.action_name)
        self.path = path

        if checked is not None:
            self.action.setCheckable(True)
            self.action.setChecked(checked)

    def run(self):
        self.action.triggered.connect(lambda: self.execute_action())
        return self.action

    def execute_action(self):
        self.msg_signal.emit({'message': '[API]: %s' % self.command, 'color': 'black'})
        thread = threading.Thread(target=run_command_for_api, args=(self.command, self.msg_signal, self.path))
        thread.start()


def expand_var(setting_str, ifp_var_dic=None, **kwargs):
    """
    Expand variable settings on 'setting_str'.
    """
    common_var = {'CWD': CWD,
                  'USER': USER}

    if type(setting_str) is str:
        # Merge IFP_INSTALL_PATH/CWD and **kwargs into var_dic.
        var_dic = copy.deepcopy(ifp_var_dic)
        var_dic.update(**kwargs)
        var_dic.update(common_var)

        while setting_str.find('$') >= 0:
            # Replace variables with var_dic on setting_str.
            try:
                tpl = Template(setting_str)
                setting_str = tpl.substitute(var_dic)
            except Exception as warning:
                print_warning('*Warning*: Failed on expanding variable for "' + str(setting_str) + '" : ' + str(warning))
                break

    return setting_str


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
        self.skipped = 'Skipped'


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
            'rerun_check_or_summarize_before_view': {'value': True, 'note': 'Auto rerun CHECK(SUMMARIZE) command before view check(summarize) report'},
            'enable_variable_interface': {'value': False, 'note': "Show variable interface and can edit variables with effect only in IFP"},
            'enable_dependency_interface': {'value': False, 'note': "Show dependency interface and can adjust dependency between flow sand tasks"},
            'enable_api_interface': {'value': False, 'note': "Show API interface and can enable/disable API"}

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
USER = os.popen('whoami').read().strip()
CWD = os.getcwd()
