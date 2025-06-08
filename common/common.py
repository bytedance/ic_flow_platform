import copy
import datetime
import os
import re
import traceback
from string import Template
from typing import Tuple

import psutil
import signal
import subprocess
import threading
from ansi2html import Ansi2HTMLConverter

import yaml
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QMessageBox, QAction
from PIL import Image, ImageDraw, ImageFont

import time
import common_pyqt5


def bprint(message, color='', background_color='', display_method='', date_format='', level='', indent=0, end='\n', save_file='', save_file_method='a'):
    """
    Enhancement of "print" function.

    color:            Specify font foreground color, default to follow the terminal settings.
    background_color: Specify font background color, default to follow the terminal settings.
    display_method:   Specify font display method, default to follow the terminal settings.
    date_format:      Will show date/time information before the message, such as "%Y_%m_%d %H:%M:%S". Default is "", means silent mode.
    level:            Will show message level information after date/time information, default is "", means show nothing.
    indent:           How much spaces to indent for specified message (with level information), default is 0, means no indentation.
    end:              Specify the character at the end of the output, default is "\n".
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

    print(final_message_with_color, end=end)

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


def run_command(command, shell=True, xterm=False):
    """
    Run shell command with subprocess.Popen.
    """
    SP = subprocess.Popen(command, shell=shell, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (stdout, stderr) = SP.communicate()
    return_code = SP.returncode

    if xterm and return_code > 0 and re.search(r'Couldn\'t connect to accessibility bus', str(stdout, 'utf-8').strip(), re.I):
        SP = subprocess.Popen('/usr/bin/dbus-launch ' + command, shell=shell, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (stdout, stderr) = SP.communicate()
        return_code = SP.returncode

    return return_code, stdout, stderr


def run_command_for_api(command, msg_signal, path, info_signal=None, finish_signal=None):
    """
    Run shell command with subprocess.Popen.
    """

    if not os.path.exists(path):
        msg_signal.emit({'message': '[API] : %s not exists!' % path, 'color': 'red'})
        return

    SP = subprocess.Popen(command, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=path)

    while SP.poll() is None:
        line = SP.stdout.readline().decode('utf8').strip()

        if line:
            if msg_signal:
                conv = Ansi2HTMLConverter(inline=True)
                line = conv.convert(line, full=False)

                msg_signal.emit({'message': '[API] : %s' % line, 'color': 'black', 'html': True})

                if info_signal:
                    info_signal.emit('[API] : %s' % line)
            else:
                print('[API] : %s' % line)

    (stdout, stderr) = SP.communicate()
    stderr = str(stderr, 'utf-8').strip()

    if stderr:
        errs = []

        for line in stderr.splitlines():
            line = line.strip()

            if line.startswith('memoryPrediction') or line.startswith('<<Waiting') or line.startswith('<<Starting'):
                continue

            if line:
                errs.append(line)

        if msg_signal and errs:
            msg_signal.emit({'message': '[API] : %s' % '\n'.join(errs), 'color': 'red'})
        else:
            print_error(errs)

    if finish_signal:
        finish_signal.emit()


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
    except Exception as error:
        print(f'*Error*: {str(error)}')
        print(traceback.print_exc())
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

            item['ENABLE'] = item['ENABLE'] if item.get('ENABLE') is not None else True
            item['COMMENT'] = item['COMMENT'] if item.get('COMMENT') is not None else ''
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

            item['ENABLE'] = item['ENABLE'] if item.get('ENABLE') is not None else True
            item['COMMENT'] = item['COMMENT'] if item.get('COMMENT') is not None else ''
            item['GROUP'] = item['GROUP'] if item.get('GROUP') is not None else ''
            item['PROJECT'] = item['PROJECT'] if item.get('PROJECT') is not None else ''
    else:
        yaml_file['API']['PRE_IFP'] = []

    if 'TABLE_RIGHT_KEY_MENU' in yaml_file['API'].keys():
        for item in yaml_file['API']['TABLE_RIGHT_KEY_MENU']:
            if 'LABEL' not in item.keys():
                print('Please define LABEL for each API item!')
                exit(1)

            right_key_items = ['LABEL', 'PROJECT', 'GROUP', 'TAB', 'COLUMN', 'PATH', 'COMMAND', 'ENABLE', 'COMMENT', 'GUI_BLOCKING', 'RELOAD']  # noqa: F841
            right_key_must_items = ['LABEL', 'TAB', 'COLUMN', 'PATH', 'COMMAND']

            for key in right_key_must_items:
                if key not in item.keys():
                    if key == 'COMMAND' and 'API-2' in item.keys():
                        continue

                    print('You must define %s for TABLE_RIGHT_KEY_MENU API, corresponding label is %s' % (key, item['LABEL']))
                    exit(1)

            item['ENABLE'] = item['ENABLE'] if 'ENABLE' in item else True
            item['GUI_BLOCKING'] = item['GUI_BLOCKING'] if 'GUI_BLOCKING' in item else False
            item['RELOAD'] = item['RELOAD'] if 'RELOAD' in item else False
            item['COMMENT'] = item['COMMENT'] if item.get('COMMENT') is not None else ''
            item['GROUP'] = item['GROUP'] if item.get('GROUP') is not None else ''
            item['PROJECT'] = item['PROJECT'] if item.get('PROJECT') is not None else ''

            if 'API_2' in item.keys():
                for item2 in item['API-2']:
                    if 'LABEL' not in item2.keys():
                        print('Please define LABEL for each API item!')
                        exit(1)

                    stage2_right_key_items = ['LABEL', 'COMMAND', 'ENABLE', 'COMMENT', 'GUI_BLOCKING', 'RELOAD']  # noqa: F841
                    stage2_right_key_must_items = ['LABEL', 'COMMAND']

                    for key in stage2_right_key_must_items:
                        if key not in item2.keys():
                            print('You must define %s for TABLE_RIGHT_KEY_MENU(API-2) API, corresponding label is %s' % (key, item2['LABEL']))
                            exit(1)

                    item2['ENABLE'] = item2['ENABLE'] if 'ENABLE' in item2 else True
                    item2['GUI_BLOCKING'] = item2['GUI_BLOCKING'] if 'GUI_BLOCKING' in item2 else False
                    item2['RELOAD'] = item2['RELOAD'] if 'RELOAD' in item2 else False
                    item['COMMENT'] = item['COMMENT'] if item.get('COMMENT') is not None else ''
    else:
        yaml_file['API']['TABLE_RIGHT_KEY_MENU'] = []

    if 'MENU_BAR' in yaml_file['API'].keys():
        for item in yaml_file['API']['MENU_BAR']:
            if 'LABEL' not in item.keys():
                print('Please define LABEL for each API item!')
                exit(1)

            menu_bar_items = ['LABEL', 'MENU_BAR_GROUP', 'PATH', 'COMMAND', 'ENABLE', 'COMMENT', 'GUI_BLOCKING', 'RELOAD']  # noqa: F841
            menu_bar_must_items = ['LABEL', 'MENU_BAR_GROUP', 'PATH', 'COMMAND']

            for key in menu_bar_must_items:
                if key not in item.keys():
                    print('You must define %s for MENU_BAR API, corresponding label is %s' % (key, item['LABEL']))
                    exit(1)

            item['ENABLE'] = item['ENABLE'] if 'ENABLE' in item else True
            item['GUI_BLOCKING'] = item['GUI_BLOCKING'] if 'GUI_BLOCKING' in item else False
            item['RELOAD'] = item['RELOAD'] if 'RELOAD' in item else False
            item['COMMENT'] = item['COMMENT'] if item.get('COMMENT') is not None else ''

    else:
        yaml_file['API']['MENU_BAR'] = []

    if 'TOOL_BAR' in yaml_file['API'].keys():
        for item in yaml_file['API']['TOOL_BAR']:
            if 'LABEL' not in item.keys():
                print('Please define LABEL for each API item!')
                exit(1)

            menu_bar_items = ['LABEL', 'PATH', 'COMMAND', 'ENABLE', 'COMMENT', 'GUI_BLOCKING', 'RELOAD']  # noqa: F841
            menu_bar_must_items = ['LABEL', 'PATH', 'COMMAND']

            for key in menu_bar_must_items:
                if key not in item.keys():
                    print('You must define %s for MENU_BAR API, corresponding label is %s' % (key, item['LABEL']))
                    exit(1)

            item['ENABLE'] = item['ENABLE'] if 'ENABLE' in item else True
            item['GUI_BLOCKING'] = item['GUI_BLOCKING'] if 'GUI_BLOCKING' in item else False
            item['RELOAD'] = item['RELOAD'] if 'RELOAD' in item else False
            item['COMMENT'] = item['COMMENT'] if item.get('COMMENT') is not None else ''

    else:
        yaml_file['API']['TOOL_BAR'] = []

    return yaml_file


def add_api_menu_bar(ifp_obj, user_api, menubar):
    if 'MENU_BAR' in user_api['API'].keys():
        all_menus = {}
        for item in user_api['API']['MENU_BAR']:
            if not item['ENABLE']:
                continue

            group = item['MENU_BAR_GROUP']

            if group not in all_menus.keys():
                all_menus[group] = []

            all_menus[item['MENU_BAR_GROUP']].append(item)

        for group in all_menus.keys():
            group_menu = menubar.addMenu(group)

            for item in all_menus[group]:
                action_obj = CreateAction(item['LABEL'],
                                          expand_var(item['COMMAND'], ifp_var_dic=ifp_obj.config_obj.var_dic),
                                          expand_var(item['PATH'], ifp_var_dic=ifp_obj.config_obj.var_dic),
                                          ifp_obj=ifp_obj,
                                          blocking=item['GUI_BLOCKING'],
                                          reload=item['RELOAD'])
                action_obj.msg_signal.connect(ifp_obj.update_message_text)
                group_menu.addAction(action_obj.run())


def add_api_tool_bar(ifp_obj, user_api):
    toolbar_list = []

    if 'TOOL_BAR' in user_api['API'].keys():
        for item in user_api['API']['TOOL_BAR']:
            if not item['ENABLE']:
                continue

            action_obj = CreateAction(item['LABEL'],
                                      expand_var(item['COMMAND'], ifp_var_dic=ifp_obj.config_obj.var_dic),
                                      expand_var(item['PATH'], ifp_var_dic=ifp_obj.config_obj.var_dic),
                                      ifp_obj=ifp_obj,
                                      blocking=item['GUI_BLOCKING'],
                                      reload=item['RELOAD'])

            if 'ICON' in item and os.path.exists(expand_var(item['ICON'], ifp_var_dic=ifp_obj.config_obj.var_dic)):
                icon_path = expand_var(item['ICON'], ifp_var_dic=ifp_obj.config_obj.var_dic)
            else:
                icon_path = os.path.join(os.getcwd(), f'.ifp/API/icons/{action_obj.action_name}.png')
                os.makedirs(os.path.dirname(icon_path), exist_ok=True)
                create_api_icon(word=action_obj.action_name[:3], save_path=icon_path, img_size=(300, 300))

            action_obj.action.setIcon(QIcon(icon_path))

            action_obj.msg_signal.connect(ifp_obj.update_message_text)
            toolbar = ifp_obj.addToolBar(action_obj.action_name)
            toolbar.addAction(action_obj.run())
            toolbar_list.append(toolbar)

    return toolbar_list


def add_api_menu(ifp_obj, user_api, menu, project=None, group=None, tab=None, column=None, var_dic=None):
    if 'TABLE_RIGHT_KEY_MENU' in user_api['API'].keys():
        menu.addSeparator()

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

                    if 'PATH' not in item2:
                        if 'PATH' in item:
                            item2['PATH'] = item['PATH']
                        else:
                            item2['PATH'] = '${CWD}'

                    action_obj = CreateAction('[API]  ' + item2['LABEL'],
                                              expand_var(item2['COMMAND'], ifp_var_dic=ifp_obj.config_obj.var_dic, **var_dic),
                                              expand_var(item2['PATH'], ifp_var_dic=ifp_obj.config_obj.var_dic, **var_dic),
                                              ifp_obj=ifp_obj,
                                              blocking=item['GUI_BLOCKING'],
                                              reload=item['RELOAD']
                                              )
                    action_obj.msg_signal.connect(ifp_obj.update_message_text)
                    sub_menu.addAction(action_obj.run())
            else:
                action_obj = CreateAction(
                    '[API]  ' + item['LABEL'],
                    expand_var(item['COMMAND'], ifp_var_dic=ifp_obj.config_obj.var_dic, **var_dic),
                    expand_var(item['PATH'], ifp_var_dic=ifp_obj.config_obj.var_dic, **var_dic),
                    ifp_obj=ifp_obj,
                    blocking=item['GUI_BLOCKING'],
                    reload=item['RELOAD'])
                action_obj.msg_signal.connect(ifp_obj.update_message_text)
                menu.addAction(action_obj.run())


class CreateAction(QThread):
    msg_signal = pyqtSignal(dict)
    save_status_signal = pyqtSignal(str)
    info_signal = pyqtSignal(str)
    finish_signal = pyqtSignal()
    blocking_signal = pyqtSignal(str)

    def __init__(self, action_name, command, path, checked=None, ifp_obj=None, blocking=False, reload=False):
        super().__init__()
        self.action_name = action_name
        self.command = command
        self.action = QAction(self.action_name, ifp_obj)
        self.path = path
        self.blocking = blocking
        self.reload = reload
        self.ifp_obj = ifp_obj
        self.progress_dialog = None

        if checked is not None:
            self.action.setCheckable(True)
            self.action.setChecked(checked)

        if self.blocking and self.ifp_obj:
            self.blocking_signal.connect(self.ifp_obj.blocking_gui)
            self.finish_signal.connect(self.ifp_obj.unblocking_gui)

        if self.ifp_obj and self.reload:
            self.finish_signal.connect(self.ifp_obj.reload_config_after_finished_api)

        if self.ifp_obj:
            self.save_status_signal.connect(self.ifp_obj.save_status_file)

    def run(self):
        self.action.triggered.connect(lambda: self.execute_action())
        return self.action

    def execute_action(self):
        self.msg_signal.emit({'message': '[API]: %s' % self.command, 'color': 'black'})
        self.save_status_signal.emit(self.ifp_obj.ifp_status_file)

        thread = threading.Thread(target=run_command_for_api, args=(self.command, self.msg_signal, self.path, self.info_signal, self.finish_signal))
        thread.start()

        if self.blocking:
            self.blocking_signal.emit(self.action_name)


def expand_var(setting_str, ifp_var_dic=None, show_warning=True, **kwargs):
    """
    Expand variable settings on 'setting_str'.
    """
    common_var = {'CWD': CWD,
                  'USER': USER}
    settings = []
    new_settings = []

    if type(setting_str) is str:
        settings = [setting_str]
    elif type(setting_str) is int:
        settings = [str(setting_str)]
    elif type(setting_str) is list:
        settings = setting_str

    for setting_str2 in settings:
        if type(setting_str2) is str:
            # Merge IFP_INSTALL_PATH/CWD and **kwargs into var_dic.
            var_dic = copy.deepcopy(ifp_var_dic)
            var_dic.update(**kwargs)
            var_dic.update(common_var)

            if setting_str2.find('$') >= 0:
                while setting_str2.find('$') >= 0:
                    # Replace variables with var_dic on setting_str.
                    try:
                        tpl = Template(setting_str2)
                        setting_str2 = tpl.substitute(var_dic)
                    except Exception as warning:
                        traceback.format_exc()
                        if show_warning:
                            print_warning('*Warning*: Failed on expanding variable for "' + str(setting_str2) + '" : ' + str(warning))
                        new_settings.append(setting_str2)
                        break
                else:
                    new_settings.append(setting_str2)
            else:
                new_settings.append(setting_str2)

        else:
            new_settings.append(setting_str2)

    if type(setting_str) is str:
        return new_settings[-1]
    elif type(setting_str) is int:
        return new_settings[-1]
    elif type(setting_str) is list:
        return new_settings


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


def get_user_cache_path() -> str:
    try:
        home_path = os.path.expanduser('~')
    except Exception as error:
        print_error(f'Find user homepath failed!\nError: {str(error)}')
        home_path = os.getcwd()

    cache_path = os.path.join(home_path, '.ifp/cache')
    os.makedirs(cache_path, exist_ok=True)

    return cache_path


def create_api_icon(word, img_size=(300, 200), font_size=150, save_path='output.png'):
    img = Image.new('RGBA', img_size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)

    circle_radius = img_size[1] // 2
    circle_center = (img_size[0] // 2, img_size[1] // 2)
    circle_bounds = [
        circle_center[0] - circle_radius, circle_center[1] - circle_radius,
        circle_center[0] + circle_radius, circle_center[1] + circle_radius
    ]
    draw.ellipse(circle_bounds, fill=(255, 200, 200, 255))

    # font_size = img_size[1]
    font_path = os.path.join(str(os.environ['IFP_INSTALL_PATH']), 'data/ttf/api_icon.ttf')
    font = ImageFont.truetype(font_path, font_size)
    text_bbox = draw.textbbox((0, 0), word, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]

    x = (img_size[0] - text_width) / 2
    y = (img_size[1] - text_height) / 2 - text_bbox[1]

    draw.text((x, y), word, font=font, fill=(65, 105, 225, 255))
    img.save(save_path)


def gen_cache_file_name(config_file: str) -> Tuple[str, str]:
    status_file = '.ifp.status.yaml' if config_file == 'ifp.cfg.yaml' else '.{}.status.yaml'.format(config_file.replace('.', '_'))
    ifp_cache_dir = '.ifp' if config_file == 'ifp.cfg.yaml' else '.{}_ifp'.format(config_file.replace('.', '_'))
    return status_file, ifp_cache_dir


class ThreadRun(QThread):
    """
    This class is used to run command on a thread.
    """

    def __init__(self, xterm=False):
        super().__init__()
        self.xterm = xterm

    def run(self, command_list):
        for command in command_list:
            thread = threading.Thread(target=run_command, args=(command, True, self.xterm))
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
            'lmstat_path': {'value': '', 'note': 'Specify lmstat path, example "/eda/synopsys/scl/2021.03/linux64/bin/lmstat".'},
            'mem_prediction': {'value': False, 'note': "Enable/Disable Memory Prediction Feature"},
            'in_process_check_server': {'value': '', 'note': "service host for Task in process check."}
        }
        self.user_setting_dic = {
            'send_result_command': {'value': '', 'note': 'send result command'},
            'xterm_command': {'value': 'xterm -e', 'note': 'xterm command.'},
            'fullscreen_flag': {'value': True, 'note': 'launch ifp in fullscreen'},
            'rerun_flag': {'value': True, 'note': 'remind user to confirm if rerun passed tasks'},
            'ignore_fail': {'value': False, 'note': 'task will run even if dependent tasks failed'},
            'send_result': {'value': False, 'note': 'send result to users after action done'},
            'auto_check': {'value': True, 'note': 'auto execute check action after run finish'},
            'auto_import_tasks': {'value': True, 'note': 'import all tasks when add new block/version'},
            'rerun_check_or_summarize_before_view': {'value': True, 'note': 'Auto rerun CHECK(SUMMARIZE) command before view check(summarize) report'},
            'enable_variable_interface': {'value': False, 'note': "Show variable interface and can edit variables with effect only in IFP"},
            'enable_order_interface': {'value': False, 'note': "Show run order interface and can adjust order between flows and tasks"},
            'enable_api_interface': {'value': False, 'note': "Show API interface and can enable/disable API"},
            'makefile_mode': {'value': False, 'note': "Automatically select the prerequisite tasks for a Task."}
        }


class AutoVivification(dict):
    def __getitem__(self, item):
        try:
            return dict.__getitem__(self, item)
        except KeyError:
            value = self[item] = type(self)()
            return value

    def __bool__(self):
        return False if self == type(self)() or self == {} else True


def convert_to_autovivification(d):
    if isinstance(d, dict):
        av = AutoVivification()
        for k, v in d.items():
            av[k] = convert_to_autovivification(v)
        return av
    elif isinstance(d, list):
        return [convert_to_autovivification(v) for v in d]
    else:
        return d


config = ConfigSetting()
status = TaskStatus()
action = TaskAction()
status_ing = {action.build: status.building,
              action.run: status.running,
              action.check: status.checking,
              action.summarize: status.summarizing,
              action.release: status.releasing}
UNEXPECTED_JOB_STATUS = [status.killed, status.killing, status.cancelled, '{} {}'.format(action.run, status.failed)]
CLOSE_REMIND_STATUS = [status.building, status.running, status.checking, status.summarizing, status.releasing, status.queued]
ING_STATUS = [status.building, status.running]
CONFIG_DIC = {**config.admin_setting_dic, **config.user_setting_dic}
USER = os.popen('whoami').read().strip()
CWD = os.getcwd()


def update_for_read_mode(cwd: str, user: str):
    global CWD
    CWD = cwd

    global USER
    USER = user
