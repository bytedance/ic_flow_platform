import os
import re
import subprocess
import threading
from PyQt5.QtCore import QThread


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
    SP = subprocess.Popen(command, shell=shell, executable=os.environ['SHELL'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    return (SP)


def get_jobid(stdout):
    """
    Get jobid information from LSF output message.
    The message just like "Job <29920> is submitted to ***".
    """
    jobid = ''

    for line in stdout.split('\n'):
        if re.match(r'^Job\s+\<(\d+)\>\s+is\s+submitted\s+to\s+queue.*$', line):
            my_match = re.match(r'^Job\s+\<(\d+)\>\s+is\s+submitted\s+to\s+queue.*$', line)
            jobid = my_match.group(1)

    return (jobid)


class ThreadRun(QThread):
    """
    This calss is used to run command on a thread.
    """
    def __init__(self):
        super().__init__()

    def run(self, command_list):
        for command in command_list:
            thread = threading.Thread(target=run_command, args=(command,))
            thread.start()
