import re
import time
import logging
import datetime
import subprocess


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


def run_command(command, mystdin=subprocess.PIPE, mystdout=subprocess.PIPE, mystderr=subprocess.PIPE):
    """
    Run system command with subprocess.Popen, get returncode/stdout/stderr.
    """
    sp = subprocess.Popen(command, shell=True, stdin=mystdin, stdout=mystdout, stderr=mystderr)
    (stdout, stderr) = sp.communicate()

    return sp.returncode, stdout, stderr


def get_logger(save_log=False, log_path='log', name='root', level=logging.DEBUG):
    # create logger with 'spam_application'
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False

    # create console handler with a higher log level
    if not logger.handlers:
        ch = logging.StreamHandler()
        ch.setLevel(level)
        ch.setFormatter(CustomPrintFormatter())
        logger.addHandler(ch)

        if save_log:
            file_handler = logging.FileHandler(log_path)
            file_handler.setLevel(level=logging.INFO)
            file_handler.setFormatter(CustomFileFormatter())
            logger.addHandler(file_handler)

    return logger


def timer(func):
    """
    timer for timing function
    """
    def timer_wrapper(*args, **kwargs):
        time_start = time.time()
        result = func(*args, **kwargs)
        time_end = time.time()
        time_cost = time_end - time_start

        print('%s cost time: %.2f s' % (func.__name__, time_cost))
        return result

    return timer_wrapper


def memory_unit_to_gb(orig_data, unit='MB'):
    """
    converte storage unit from TB,GB,MB,KB,B to GB
    """
    unit = unit.upper()

    if unit == 'TB':
        out_data = orig_data * 1024
    elif unit == 'GB':
        out_data = orig_data
    elif unit == 'MB':
        out_data = orig_data / 1024
    elif unit == 'KB':
        out_data = (orig_data / (1024 * 1024))
    elif unit == 'B':
        out_data = (orig_data / (1024 * 1024 * 1024))
    else:
        out_data = (orig_data / (1024 * 1024 * 1024))

    return out_data


def memory_unit_from_gb_other(orig_data, unit='MB'):
    """
    converte storage unit from GB to TB,GB,MB,KB,B to GB
    """
    unit = unit.upper()

    if unit == 'TB':
        out_data = orig_data / 1024
    elif unit == 'GB':
        out_data = orig_data
    elif unit == 'MB':
        out_data = int(orig_data * 1024)
    elif unit == 'KB':
        out_data = int(orig_data * 1024 * 1024)
    elif unit == 'B':
        out_data = int(orig_data * 1024 * 1024 * 1024)
    else:
        out_data = int(orig_data * 1024 * 1024 * 1024)

    return out_data


class CustomPrintFormatter(logging.Formatter):
    # logging color setting
    grey = "\x1b[38;20m"
    bold_grey = "\x1b[38;1m"
    green = "\x1b[32;20m"
    bold_green = "\x1b[32;1m"
    yellow = "\x1b[33;20m"
    bold_yellow = "\x1b[33;1m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    purple = "\x1b[35;20m"
    bold_purple = "\x1b[35;1m"
    reset = "\x1b[0m"
    error_format = '[%(asctime)s] *Error*: %(message)s'
    warning_format = '[%(asctime)s] *Warning*: %(message)s'
    info_format = '[%(asctime)s] *Info*: %(message)s'
    format = '[%(asctime)s]%(message)s'

    FORMATS = {
        logging.DEBUG: purple + format + reset,
        logging.INFO: green + info_format + reset,
        logging.WARNING: yellow + warning_format + reset,
        logging.ERROR: red + error_format + reset,
        logging.CRITICAL: grey + format + reset,
    }

    def __init__(self):
        super().__init__(datefmt='%Y-%m-%d %H:%M:%S')

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(fmt=log_fmt, datefmt=self.datefmt)
        return formatter.format(record)


class CustomFileFormatter(logging.Formatter):
    error_format = '[%(asctime)s] *Error*: %(message)s'
    warning_format = '[%(asctime)s] *Warning*: %(message)s'
    info_format = '[%(asctime)s] *Info*: %(message)s'
    format = '[%(asctime)s]%(message)s'

    FORMATS = {
        logging.DEBUG: format,
        logging.INFO: info_format,
        logging.WARNING: warning_format,
        logging.ERROR: error_format,
        logging.CRITICAL: format,
    }

    def __init__(self):
        super().__init__(datefmt='%Y-%m-%d %H:%M:%S')

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(fmt=log_fmt, datefmt=self.datefmt)
        return formatter.format(record)
