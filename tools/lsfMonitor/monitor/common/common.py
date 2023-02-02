import re
import subprocess


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


def run_command(command, mystdin=subprocess.PIPE, mystdout=subprocess.PIPE, mystderr=subprocess.PIPE):
    """
    Run system command with subprocess.Popen, get returncode/stdout/stderr.
    """
    SP = subprocess.Popen(command, shell=True, stdin=mystdin, stdout=mystdout, stderr=mystderr)
    (stdout, stderr) = SP.communicate()

    return(SP.returncode, stdout, stderr)


def get_job_range_dic(job_list):
    job_range_dic = {}

    for job in job_list:
        job_org = job
        job = re.sub('\[.*', '', job)
        job_head = (int(int(job)/10000))*10000
        job_tail = job_head + 9999
        job_range = str(job_head) + '_' + str(job_tail)
        job_range_dic.setdefault(job_range, [])
        job_range_dic[job_range].append(job_org)

    return(job_range_dic)
