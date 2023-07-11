import os
import re
import sys
import collections

sys.path.append(str(os.environ['LSFMONITOR_INSTALL_PATH']) + '/monitor')
from common import common


def get_command_dict(command):
    """
    Collect (common) LSF command info into a dict.
    It only works with the Title-Item type informations.
    """
    my_dic = collections.OrderedDict()
    key_list = []
    (return_code, stdout, stderr) = common.run_command(command)
    i = -1

    for line in str(stdout, 'utf-8').split('\n'):
        line = line.strip()

        if line:
            i += 1

            # Some speciall preprocess.
            if re.search(r'lsload', command):
                line = re.sub(r'\*', ' ', line)

            if i == 0:
                key_list = line.split()

                for key in key_list:
                    my_dic[key] = []
            else:
                command_info = line.split()

                if len(command_info) < len(key_list):
                    common.print_warning('*Warning* (get_command_dict) : For command "' + str(command) + '", below info line is incomplate/unexpected.')
                    common.print_warning('           ' + str(line))

                for j in range(len(key_list)):
                    key = key_list[j]

                    if j < len(command_info):
                        value = command_info[j]
                    else:
                        value = ''

                    my_dic[key].append(value)

    return my_dic


def get_bjobs_info(command='bjobs -u all -w'):
    """
    Get bjobs info with command 'bjobs'.
    ====
    JOBID   USER      STAT  QUEUE      FROM_HOST   EXEC_HOST   JOB_NAME            SUBMIT_TIME
    101     liyanqing RUN   normal     cmp01       2*cmp01     Tesf for lsfMonitor Oct 26 17:43
    ====
    """
    bjobs_dic = get_command_dict(command)
    return bjobs_dic


def get_bqueues_info(command='bqueues -w'):
    """
    Get bqueues info with command 'bqueues'.
    ====
    QUEUE_NAME      PRIO STATUS          MAX JL/U JL/P JL/H NJOBS  PEND   RUN  SUSP  RSV PJOBS
    normal           30  Open:Active       -    -    -    -     2     0     2     0    0     0
    ====
    """
    bqueues_dic = get_command_dict(command)
    return bqueues_dic


def get_bhosts_info(command='bhosts -w'):
    """
    Get bhosts info with command 'bhosts'.
    ====
    HOST_NAME          STATUS          JL/U    MAX  NJOBS    RUN  SSUSP  USUSP    RSV
    cmp01              ok              -       4    2        2    0      0        0
    ====
    """
    bhosts_dic = get_command_dict(command)
    return bhosts_dic


def get_bhosts_load_info(command='bhosts -l'):
    """
    Get "CURRENT LOAD USED FOR SCHEDULING" information with command
    ====
    HOST  n212-206-212
    STATUS           CPUF  JL/U    MAX  NJOBS    RUN  SSUSP  USUSP    RSV DISPATCH_WINDOW
    ok              15.00     -     48      2      2      0      0      0      -

     CURRENT LOAD USED FOR SCHEDULING:
                    r15s   r1m  r15m    ut    pg    io   ls    it   tmp   swp   mem  slots
     Total           0.0   0.0   0.0    2%   0.0     8    0 14324 1667_g 127.2_g  683_g     46
     Reserved        0.0   0.0   0.0    0%   0.0     0    0     0    0_m    0_m  178_g      -
    ====
    """
    bhosts_load_dic = collections.OrderedDict()
    load_info_mark = False
    hostname = ''
    head_list = []

    (return_code, stdout, stderr) = common.run_command(command)

    for line in str(stdout, 'utf-8').split('\n'):
        line = line.strip()

        if re.match(r'^\s*HOST\s+(.+?)\s*$', line):
            my_match = re.match(r'^\s*HOST\s+(.+?)\s*$', line)
            hostname = my_match.group(1)
            bhosts_load_dic.setdefault(hostname, {})
            load_info_mark = False
        elif re.match(r'^\s*CURRENT LOAD USED FOR SCHEDULING:\s*$', line):
            load_info_mark = True
        elif load_info_mark:
            if re.match(r'^\s*$', line):
                load_info_mark = False
            elif re.match(r'^\s*Total\s+(.+?)\s*$', line):
                bhosts_load_dic[hostname].setdefault('Total', {})

                my_match = re.match(r'^\s*Total\s+(.+?)\s*$', line)
                total_load_string = my_match.group(1)
                total_load_list = total_load_string.split()

                for (i, head_name) in enumerate(head_list):
                    load = re.sub(r'\*', '', total_load_list[i])
                    bhosts_load_dic[hostname]['Total'].setdefault(head_name, load)
            elif re.match(r'^\s*Reserved\s+(.+?)\s*$', line):
                bhosts_load_dic[hostname].setdefault('Reserved', {})

                my_match = re.match(r'^\s*Reserved\s+(.+?)\s*$', line)
                reserved_load_string = my_match.group(1)
                reserved_load_list = reserved_load_string.split()

                for (i, head_name) in enumerate(head_list):
                    load = re.sub(r'\*', '', reserved_load_list[i])
                    bhosts_load_dic[hostname]['Reserved'].setdefault(head_name, load)
            else:
                head_list = line.split()

    return bhosts_load_dic


def get_lshosts_info(command='lshosts -w'):
    """
    Get lshosts info with command 'lshosts'.
    ====
    HOST_NAME                     type       model           cpuf     ncpus maxmem maxswp server RESOURCES
    cmp01                         X86_64     Intel_Platinum  15.0     4     1.7_g   1.9_g   Yes    (mg)
    ====
    """
    lshosts_dic = get_command_dict(command)
    return lshosts_dic


def get_lsload_info(command='lsload -w'):
    """
    Get lsload info with command 'lsload'.
    ====
    HOST_NAME               status  r15s   r1m  r15m   ut    pg    ls    it   tmp    swp   mem
    cmp01                 ok      0.7    0.3  0.2    5%    0.0   1     0    7391_m  1.9_g  931_m
    ====
    """
    lsload_dic = get_command_dict(command)

    return lsload_dic


def get_busers_info(command='busers all'):
    """
    Get lsload info with command 'busers'.
    ====
    USER/GROUP          JL/P    MAX  NJOBS   PEND    RUN  SSUSP  USUSP    RSV
    liyanqing           -       -    2       0       2    0      0        0
    ====
    """
    busers_dic = get_command_dict(command)
    return busers_dic


def get_tool_name():
    """
    Make sure it is lsf or openlava.
    """
    command = 'lsid'
    (return_code, stdout, stderr) = common.run_command(command)

    for line in str(stdout, 'utf-8').split('\n'):
        line = line.strip()

        if re.search(r'LSF', line):
            return 'lsf'
        elif re.search(r'Open_lava', line) or re.search(r'openlava', line):
            return 'openlava'

    print('*Warning*: Not sure current cluster is LSF or Openlava.')
    return ''


def get_bjobs_uf_info(command='bjobs -u all -UF'):
    """
    Get job information with "bjobs -UF".
    """
    tool = get_tool_name()
    my_dic = {}

    if tool == 'lsf':
        my_dic = get_lsf_bjobs_uf_info(command)
    elif tool == 'openlava':
        my_dic = get_openlava_bjobs_uf_info(command)

    return my_dic


def get_lsf_bjobs_uf_info(command):
    """
    Parse job info which are from command 'bjobs -u all -UF'.
    ====
    Job <101>, Job Name <Tesf for lsfMonitor>, User <liyanqing>, Project <lsf_test>, Status <RUN>, Queue <normal>, Command <sleep 12345>, Share group charged </liyanqing>
    Mon Oct 26 17:43:07: Submitted from host <cmp01>, CWD <$HOME>, 2 Task(s), Requested Resources <span[hosts=1] rusage[mem=123]>;
    Mon Oct 26 17:43:07: Started 2 Task(s) on Host(s) <2*cmp01>, Allocated 2 Slot(s) on Host(s) <2*cmp01>, Execution Home </home/liyanqing>, Execution CWD </home/liyanqing>;
    Mon Oct 26 17:46:17: Resource usage collected. MEM: 2 Mbytes; SWAP: 238 Mbytes; NTHREAD: 4; PGID: 10643; PIDs: 10643 10644 10646;


     MEMORY USAGE:
     MAX MEM: 2 Mbytes;  AVG MEM: 2 Mbytes

     SCHEDULING PARAMETERS:
               r15s   r1m  r15m   ut      pg    io   ls    it    tmp    swp    mem
     load_sched   -     -     -     -       -     -    -     -     -      -      -
     load_stop    -     -     -     -       -     -    -     -     -      -      -

     RESOURCE REQUIREMENT DETAILS:
     Combined: select[type == local] order[r15s:pg] rusage[mem=123.00] span[hosts=1]
     Effective: select[type == local] order[r15s:pg] rusage[mem=123.00] span[hosts=1]
    ====
    """
    job_compile_dic = {
                       'job_compile': re.compile(r'.*Job <([0-9]+(\[[0-9]+\])?)>.*'),
                       'job_name_compile': re.compile(r'.*Job Name <([^>]+)>.*'),
                       'user_compile': re.compile(r'.*User <([^>]+)>.*'),
                       'project_compile': re.compile(r'.*Project <([^>]+)>.*'),
                       'status_compile': re.compile(r'.*Status <([A-Z]+)>*'),
                       'queue_compile': re.compile(r'.*Queue <([^>]+)>.*'),
                       'command_compile': re.compile(r'.*Command <(.+?\S)>.*$'),
                       'submitted_from_compile': re.compile(r'.*Submitted from host <([^>]+)>.*'),
                       'submitted_time_compile': re.compile(r'(.*): Submitted from host.*'),
                       'cwd_compile': re.compile(r'.*CWD <([^>]+)>.*'),
                       'processors_requested_compile': re.compile(r'.* (\d+) Task\(s\).*'),
                       'requested_resources_compile': re.compile(r'.*Requested Resources <(.+)>;.*'),
                       'span_hosts_compile': re.compile(r'.*Requested Resources <.*span\[hosts=([1-9][0-9]*).*>.*'),
                       'rusage_mem_compile': re.compile(r'.*Requested Resources <.*rusage\[mem=([1-9][0-9]*).*>.*'),
                       'started_on_compile': re.compile(r'(.*): (\[\d+\] )?[sS]tarted \d+ Task\(s\) on Host\(s\) (.+?), Allocated (\d+) Slot\(s\) on Host\(s\).*'),
                       'finished_time_compile': re.compile(r'(.*): (Done successfully|Exited with exit code|Exited by LSF signal|Completed <exit>).*'),
                       'exit_code_compile': re.compile(r'.*Exited with exit code (\d+)\..*'),
                       'lsf_signal_compile': re.compile(r'.*Exited by LSF signal (\S+?)\..*'),
                       'term_owner_compile': re.compile(r'.*TERM_OWNER: (.+?\.).*'),
                       'cpu_time_compile': re.compile(r'.*The CPU time used is (\d+(\.\d+)?) seconds.*'),
                       'mem_compile': re.compile(r'.*MEM:\s*(\d+(\.\d+)?)\s*([KMGT]bytes).*'),
                       'swap_compile': re.compile(r'.*SWAP:\s*(\d+(\.\d+)?)\s*([KMGT]bytes).*'),
                       'run_limit_compile': re.compile(r'\s*RUNLIMIT\s*'),
                       'pids_compile': re.compile(r'PIDs:\s+(.+?);'),
                       'max_mem_compile': re.compile(r'\s*MAX MEM: (\d+(\.\d+)?) ([KMGT]bytes);\s*AVG MEM: (\d+(\.\d+)?) ([KMGT]bytes)\s*'),
                       'pending_reasons_compile': re.compile(r'\s*PENDING REASONS:\s*'),
                       'empty_line_compile': re.compile(r'^\s*$'),
                      }

    my_dic = collections.OrderedDict()
    job = ''
    run_limit_mark = False
    pending_mark = False

    (return_code, stdout, stderr) = common.run_command(command)

    for line in stdout.decode('utf-8', 'ignore').split('\n'):
        line = line.strip()

        if re.match(r'Job <' + str(job) + '> is not found', line):
            continue
        else:
            if job_compile_dic['job_compile'].match(line):
                my_match = job_compile_dic['job_compile'].match(line)
                job = my_match.group(1)

                # Initialization for my_dic[job].
                my_dic[job] = collections.OrderedDict()
                my_dic[job]['job_info'] = ''
                my_dic[job]['job_id'] = job
                my_dic[job]['job_name'] = ''
                my_dic[job]['user'] = ''
                my_dic[job]['project'] = ''
                my_dic[job]['status'] = ''
                my_dic[job]['queue'] = ''
                my_dic[job]['command'] = ''
                my_dic[job]['submitted_from'] = ''
                my_dic[job]['submitted_time'] = ''
                my_dic[job]['cwd'] = ''
                my_dic[job]['processors_requested'] = '1'
                my_dic[job]['requested_resources'] = ''
                my_dic[job]['span_hosts'] = ''
                my_dic[job]['rusage_mem'] = ''
                my_dic[job]['started_on'] = ''
                my_dic[job]['started_time'] = ''
                my_dic[job]['finished_time'] = ''
                my_dic[job]['exit_code'] = ''
                my_dic[job]['lsf_signal'] = ''
                my_dic[job]['term_owner'] = ''
                my_dic[job]['cpu_time'] = ''
                my_dic[job]['mem'] = ''
                my_dic[job]['swap'] = ''
                my_dic[job]['run_limit'] = ''
                my_dic[job]['pids'] = []
                my_dic[job]['max_mem'] = ''
                my_dic[job]['avg_mem'] = ''
                my_dic[job]['pending_reasons'] = []

            if job != '':
                if my_dic[job]['job_info']:
                    my_dic[job]['job_info'] = str(my_dic[job]['job_info']) + '\n' + str(line)
                else:
                    my_dic[job]['job_info'] = line

                if job_compile_dic['empty_line_compile'].match(line):
                    if run_limit_mark:
                        run_limit_mark = False

                    if pending_mark:
                        pending_mark = False
                else:
                    if run_limit_mark:
                        my_dic[job]['run_limit'] = re.sub(r'min', '', line)
                        my_dic[job]['run_limit'] = re.sub(r'\s', '', my_dic[job]['run_limit'])
                        continue

                    if pending_mark:
                        my_dic[job]['pending_reasons'].append(line.strip())
                        continue

                    if job_compile_dic['job_name_compile'].match(line):
                        my_match = job_compile_dic['job_name_compile'].match(line)
                        my_dic[job]['job_name'] = my_match.group(1)

                    if job_compile_dic['user_compile'].match(line):
                        my_match = job_compile_dic['user_compile'].match(line)
                        my_dic[job]['user'] = my_match.group(1)

                    if job_compile_dic['project_compile'].match(line):
                        my_match = job_compile_dic['project_compile'].match(line)
                        my_dic[job]['project'] = my_match.group(1)

                    if job_compile_dic['status_compile'].match(line):
                        my_match = job_compile_dic['status_compile'].match(line)
                        my_dic[job]['status'] = my_match.group(1)

                    if job_compile_dic['queue_compile'].match(line):
                        my_match = job_compile_dic['queue_compile'].match(line)
                        my_dic[job]['queue'] = my_match.group(1)

                    if job_compile_dic['command_compile'].match(line):
                        my_match = job_compile_dic['command_compile'].match(line)
                        my_dic[job]['command'] = my_match.group(1)
                        continue

                    if job_compile_dic['submitted_time_compile'].match(line):
                        my_match = job_compile_dic['submitted_time_compile'].match(line)
                        my_dic[job]['submitted_time'] = my_match.group(1)

                    if job_compile_dic['cwd_compile'].match(line):
                        my_match = job_compile_dic['cwd_compile'].match(line)
                        my_dic[job]['cwd'] = my_match.group(1)

                    if job_compile_dic['processors_requested_compile'].match(line):
                        my_match = job_compile_dic['processors_requested_compile'].match(line)
                        my_dic[job]['processors_requested'] = my_match.group(1)

                    if job_compile_dic['requested_resources_compile'].match(line):
                        my_match = job_compile_dic['requested_resources_compile'].match(line)
                        my_dic[job]['requested_resources'] = my_match.group(1)

                    if job_compile_dic['span_hosts_compile'].match(line):
                        my_match = job_compile_dic['span_hosts_compile'].match(line)
                        my_dic[job]['span_hosts'] = my_match.group(1)

                    if job_compile_dic['rusage_mem_compile'].match(line):
                        my_match = job_compile_dic['rusage_mem_compile'].match(line)
                        my_dic[job]['rusage_mem'] = my_match.group(1)

                    if job_compile_dic['submitted_from_compile'].match(line):
                        my_match = job_compile_dic['submitted_from_compile'].match(line)
                        my_dic[job]['submitted_from'] = my_match.group(1)
                        continue

                    if job_compile_dic['started_on_compile'].match(line):
                        my_match = job_compile_dic['started_on_compile'].match(line)
                        my_dic[job]['started_time'] = my_match.group(1)
                        started_host = my_match.group(3)
                        started_host = re.sub(r'<', '', started_host)
                        started_host = re.sub(r'>', '', started_host)
                        started_host = re.sub(r'\d+\*', '', started_host)
                        my_dic[job]['started_on'] = started_host
                        continue

                    if job_compile_dic['cpu_time_compile'].match(line):
                        my_match = job_compile_dic['cpu_time_compile'].match(line)
                        my_dic[job]['cpu_time'] = my_match.group(1)

                    if job_compile_dic['mem_compile'].match(line) and (not my_dic[job]['mem']):
                        my_match = job_compile_dic['mem_compile'].match(line)
                        my_dic[job]['mem'] = my_match.group(1)
                        unit = my_match.group(3)

                        if unit == 'Kbytes':
                            my_dic[job]['mem'] = float(my_dic[job]['mem'])/1024
                        elif unit == 'Gbytes':
                            my_dic[job]['mem'] = float(my_dic[job]['mem'])*1024
                        elif unit == 'Tbytes':
                            my_dic[job]['mem'] = float(my_dic[job]['mem'])*1024*1024

                    if job_compile_dic['swap_compile'].match(line):
                        my_match = job_compile_dic['swap_compile'].match(line)
                        my_dic[job]['swap'] = my_match.group(1)
                        unit = my_match.group(3)

                        if unit == 'Kbytes':
                            my_dic[job]['swap'] = float(my_dic[job]['swap'])/1024
                        elif unit == 'Gbytes':
                            my_dic[job]['swap'] = float(my_dic[job]['swap'])*1024
                        elif unit == 'Tbytes':
                            my_dic[job]['swap'] = float(my_dic[job]['swap'])*1024*1024

                    if job_compile_dic['finished_time_compile'].match(line):
                        my_match = job_compile_dic['finished_time_compile'].match(line)
                        my_dic[job]['finished_time'] = my_match.group(1)

                    if job_compile_dic['exit_code_compile'].match(line):
                        my_match = job_compile_dic['exit_code_compile'].match(line)
                        my_dic[job]['exit_code'] = my_match.group(1)

                    if job_compile_dic['lsf_signal_compile'].match(line):
                        my_match = job_compile_dic['lsf_signal_compile'].match(line)
                        my_dic[job]['lsf_signal'] = my_match.group(1)

                    if job_compile_dic['term_owner_compile'].match(line):
                        my_match = job_compile_dic['term_owner_compile'].match(line)
                        my_dic[job]['term_owner'] = my_match.group(1)

                    if job_compile_dic['pids_compile'].findall(line):
                        my_match = job_compile_dic['pids_compile'].findall(line)
                        my_string = ' '.join(my_match)
                        my_dic[job]['pids'] = my_string.split()
                        continue

                    if job_compile_dic['max_mem_compile'].match(line):
                        my_match = job_compile_dic['max_mem_compile'].match(line)
                        my_dic[job]['max_mem'] = my_match.group(1)
                        unit = my_match.group(3)

                        if unit == 'Kbytes':
                            my_dic[job]['max_mem'] = float(my_dic[job]['max_mem'])/1024
                        elif unit == 'Gbytes':
                            my_dic[job]['max_mem'] = float(my_dic[job]['max_mem'])*1024
                        elif unit == 'Tbytes':
                            my_dic[job]['max_mem'] = float(my_dic[job]['max_mem'])*1024*1024

                        my_dic[job]['avg_mem'] = my_match.group(4)
                        unit = my_match.group(6)

                        if unit == 'Kbytes':
                            my_dic[job]['avg_mem'] = float(my_dic[job]['avg_mem'])/1024
                        elif unit == 'Gbytes':
                            my_dic[job]['avg_mem'] = float(my_dic[job]['avg_mem'])*1024
                        elif unit == 'Tbytes':
                            my_dic[job]['avg_mem'] = float(my_dic[job]['avg_mem'])*1024*1024

                        continue

                    if job_compile_dic['run_limit_compile'].match(line):
                        run_limit_mark = True

                    if job_compile_dic['pending_reasons_compile'].match(line):
                        pending_mark = True

    return my_dic


def get_openlava_bjobs_uf_info(command):
    """
    Parse job info which are from command 'bjobs -u all -UF'.
    ====
    Job <205>, User <liyanqing>, Project <default>, Status <PEND>, Queue <normal>, Command <sleep 1000>
    Sun May 13 18:08:26: Submitted from host <lava_host1>, CWD <$HOME>, 2 Processors Requested, Requested Resources <rusage[mem=1234] span[hosts=1]>;
    PENDING REASONS:
    New job is waiting for scheduling: 1 host;

    SCHEDULING PARAMETERS:
              r15s   r1m  r15m   ut      pg    io   ls    it    tmp    swp    mem
    load_sched   -     -     -     -       -     -    -     -     -      -      -
    load_stop    -     -     -     -       -     -    -     -     -      -      -

    RESOURCE REQUIREMENT DETAILS:
    Combined: rusage[mem=1234] span[hosts=1]
    Effective: rusage[mem=1234] span[hosts=1]
    ====
    """
    job_compile_dic = {
                       'job_compile': re.compile(r'.*Job <([0-9]+(\[[0-9]+\])?)>.*'),
                       'job_name_compile': re.compile(r'.*Job Name <([^>]+)>.*'),
                       'user_compile': re.compile(r'.*User <([^>]+)>.*'),
                       'project_compile': re.compile(r'.*Project <([^>]+)>.*'),
                       'status_compile': re.compile(r'.*Status <([A-Z]+)>*'),
                       'queue_compile': re.compile(r'.*Queue <([^>]+)>.*'),
                       'command_compile': re.compile(r'.*Command <(.+?\S)>\s*$'),
                       'submitted_from_compile': re.compile(r'.*Submitted from host <([^>]+)>.*'),
                       'submitted_time_compile': re.compile(r'(.*): Submitted from host.*'),
                       'cwd_compile': re.compile(r'.*CWD <([^>]+)>.*'),
                       'processors_requested_compile': re.compile(r'.* ([1-9][0-9]*) Processors Requested.*'),
                       'requested_resources_compile': re.compile(r'.*Requested Resources <(.+)>;.*'),
                       'span_hosts_compile': re.compile(r'.*Requested Resources <.*span\[hosts=([1-9][0-9]*).*>.*'),
                       'rusage_mem_compile': re.compile(r'.*Requested Resources <.*rusage\[mem=([1-9][0-9]*).*>.*'),
                       'started_on_compile': re.compile(r'.*[sS]tarted on ([0-9]+ Hosts/Processors )?([^;,]+).*'),
                       'started_time_compile': re.compile(r'(.*): (\[\d+\])?\s*[sS]tarted on.*'),
                       'finished_time_compile': re.compile(r'(.*): (Done successfully|Exited with).*'),
                       'exit_code_compile': re.compile(r'.*Exited with exit code (\d+)\..*'),
                       'lsf_signal_compile': re.compile(r'.*Exited by LSF signal (\S+?)\..*'),
                       'term_owner_compile': re.compile(r'.*TERM_OWNER: (.+?\.).*'),
                       'cpu_time_compile': re.compile(r'.*The CPU time used is ([1-9][0-9]*) seconds.*'),
                       'mem_compile': re.compile(r'.*MEM: ([1-9][0-9]*) Mbytes.*'),
                      }

    my_dic = collections.OrderedDict()
    job = ''

    (return_code, stdout, stderr) = common.run_command(command)

    for line in str(stdout, 'utf-8').split('\n'):
        line = line.strip()

        if re.match(r'Job <' + str(job) + '> is not found', line):
            continue
        else:
            if job_compile_dic['job_compile'].match(line):
                my_match = job_compile_dic['job_compile'].match(line)
                job = my_match.group(1)

                # Initialization for my_dic[job].
                my_dic[job] = collections.OrderedDict()
                my_dic[job]['job_info'] = ''
                my_dic[job]['job_id'] = job
                my_dic[job]['job_name'] = ''
                my_dic[job]['user'] = ''
                my_dic[job]['project'] = ''
                my_dic[job]['status'] = ''
                my_dic[job]['queue'] = ''
                my_dic[job]['command'] = ''
                my_dic[job]['submitted_from'] = ''
                my_dic[job]['submitted_time'] = ''
                my_dic[job]['cwd'] = ''
                my_dic[job]['processors_requested'] = '1'
                my_dic[job]['requested_resources'] = ''
                my_dic[job]['span_hosts'] = ''
                my_dic[job]['rusage_mem'] = ''
                my_dic[job]['started_on'] = ''
                my_dic[job]['started_time'] = ''
                my_dic[job]['finished_time'] = ''
                my_dic[job]['exit_code'] = ''
                my_dic[job]['lsf_signal'] = ''
                my_dic[job]['term_owner'] = ''
                my_dic[job]['cpu_time'] = ''
                my_dic[job]['mem'] = ''
                my_dic[job]['swap'] = ''
                my_dic[job]['run_limit'] = ''
                my_dic[job]['pids'] = []
                my_dic[job]['max_mem'] = ''
                my_dic[job]['avg_mem'] = ''
                my_dic[job]['pending_reasons'] = []

            if job != '':
                if my_dic[job]['job_info']:
                    my_dic[job]['job_info'] = str(my_dic[job]['job_info']) + '\n' + str(line)
                else:
                    my_dic[job]['job_info'] = line

                if job_compile_dic['job_name_compile'].match(line):
                    my_match = job_compile_dic['job_name_compile'].match(line)
                    my_dic[job]['job_name'] = my_match.group(1)

                if job_compile_dic['user_compile'].match(line):
                    my_match = job_compile_dic['user_compile'].match(line)
                    my_dic[job]['user'] = my_match.group(1)

                if job_compile_dic['project_compile'].match(line):
                    my_match = job_compile_dic['project_compile'].match(line)
                    my_dic[job]['project'] = my_match.group(1)

                if job_compile_dic['status_compile'].match(line):
                    my_match = job_compile_dic['status_compile'].match(line)
                    my_dic[job]['status'] = my_match.group(1)

                if job_compile_dic['queue_compile'].match(line):
                    my_match = job_compile_dic['queue_compile'].match(line)
                    my_dic[job]['queue'] = my_match.group(1)

                if job_compile_dic['command_compile'].match(line):
                    my_match = job_compile_dic['command_compile'].match(line)
                    my_dic[job]['command'] = my_match.group(1)

                if job_compile_dic['submitted_from_compile'].match(line):
                    my_match = job_compile_dic['submitted_from_compile'].match(line)
                    my_dic[job]['submitted_from'] = my_match.group(1)

                if job_compile_dic['submitted_time_compile'].match(line):
                    my_match = job_compile_dic['submitted_time_compile'].match(line)
                    my_dic[job]['submitted_time'] = my_match.group(1)

                if job_compile_dic['cwd_compile'].match(line):
                    my_match = job_compile_dic['cwd_compile'].match(line)
                    my_dic[job]['cwd'] = my_match.group(1)

                if job_compile_dic['processors_requested_compile'].match(line):
                    my_match = job_compile_dic['processors_requested_compile'].match(line)
                    my_dic[job]['processors_requested'] = my_match.group(1)

                if job_compile_dic['requested_resources_compile'].match(line):
                    my_match = job_compile_dic['requested_resources_compile'].match(line)
                    my_dic[job]['requested_resources'] = my_match.group(1)

                if job_compile_dic['span_hosts_compile'].match(line):
                    my_match = job_compile_dic['span_hosts_compile'].match(line)
                    my_dic[job]['span_hosts'] = my_match.group(1)

                if job_compile_dic['rusage_mem_compile'].match(line):
                    my_match = job_compile_dic['rusage_mem_compile'].match(line)
                    my_dic[job]['rusage_mem'] = my_match.group(1)

                if job_compile_dic['started_on_compile'].match(line):
                    my_match = job_compile_dic['started_on_compile'].match(line)
                    started_host = my_match.group(2)
                    started_host = re.sub(r'<', '', started_host)
                    started_host = re.sub(r'>', '', started_host)
                    my_dic[job]['started_on'] = started_host

                if job_compile_dic['started_time_compile'].match(line):
                    my_match = job_compile_dic['started_time_compile'].match(line)
                    my_dic[job]['started_time'] = my_match.group(1)

                if job_compile_dic['finished_time_compile'].match(line):
                    my_match = job_compile_dic['finished_time_compile'].match(line)
                    my_dic[job]['finished_time'] = my_match.group(1)

                if job_compile_dic['exit_code_compile'].match(line):
                    my_match = job_compile_dic['exit_code_compile'].match(line)
                    my_dic[job]['exit_code'] = my_match.group(1)

                if job_compile_dic['lsf_signal_compile'].match(line):
                    my_match = job_compile_dic['lsf_signal_compile'].match(line)
                    my_dic[job]['lsf_signal'] = my_match.group(1)

                if job_compile_dic['term_owner_compile'].match(line):
                    my_match = job_compile_dic['term_owner_compile'].match(line)
                    my_dic[job]['term_owner'] = my_match.group(1)

                if job_compile_dic['cpu_time_compile'].match(line):
                    my_match = job_compile_dic['cpu_time_compile'].match(line)
                    my_dic[job]['cpu_time'] = my_match.group(1)

                if job_compile_dic['mem_compile'].match(line):
                    my_match = job_compile_dic['mem_compile'].match(line)
                    my_dic[job]['mem'] = my_match.group(1)

    return my_dic


def get_host_list():
    """
    Get all of the hosts.
    """
    bhosts_dic = get_bhosts_info()
    host_list = bhosts_dic['HOST_NAME']
    return host_list


def get_queue_list():
    """
    Get all of the queues.
    """
    bqueues_dic = get_bqueues_info()
    queue_list = bqueues_dic['QUEUE_NAME']
    return queue_list


def get_host_group_members(host_group_name):
    """
    Get host group members with bmgroup.
    ====
    [yanqing.li@nxnode03 lsfMonitor]$ bmgroup pd
    GROUP_NAME    HOSTS
    pd           dm006 dm007 dm010 dm009 dm002 dm003 dm005
    ====
    """
    host_list = []
    command = 'bmgroup -w -r ' + str(host_group_name)
    (return_code, stdout, stderr) = common.run_command(command)

    for line in str(stdout, 'utf-8').split('\n'):
        line = line.strip()

        if re.search(r'No such user/host group', line):
            break
        elif re.match(r'^' + str(host_group_name) + ' .*$', line):
            my_list = line.split()
            host_list = my_list[1:]

    return host_list


def get_user_group_members(user_group_name):
    """
    Get user group members with bugroup.
    ====
    [yanqing.li@nxnode03 lsfMonitor]$ bugroup pd
    GROUP_NAME    USERS
    pd           yanqing.li san.zhang si.li
    ====
    """
    user_list = []
    command = 'bugroup -r ' + str(user_group_name)
    (return_code, stdout, stderr) = common.run_command(command)

    for line in str(stdout, 'utf-8').split('\n'):
        line = line.strip()

        if re.match(r'^' + str(user_group_name) + ' .*$', line):
            my_list = line.split()
            user_list = my_list[1:]

    return user_list


def get_queue_host_info():
    """
    Get hosts on (specified) queues.
    """
    queue_host_dic = {}
    queue_compile = re.compile(r'^QUEUE:\s*(\S+)\s*$')
    hosts_compile = re.compile(r'^HOSTS:\s*(.*?)\s*$')
    queue = ''

    command = 'bqueues -l'
    (return_code, stdout, stderr) = common.run_command(command)

    for line in str(stdout, 'utf-8').split('\n'):
        line = line.strip()

        if queue_compile.match(line):
            my_match = queue_compile.match(line)
            queue = my_match.group(1)
            queue_host_dic[queue] = []

        if hosts_compile.match(line):
            my_match = hosts_compile.match(line)
            hosts_string = my_match.group(1)

            if hosts_string == 'all':
                common.print_warning('*Warning* (get_queue_host_info) : queue "' + str(queue) + '" is not well configured, all of the hosts are on the same queue.')
                queue_host_dic[queue] = get_host_list()
            else:
                queue_host_dic.setdefault(queue, [])
                hosts_list = hosts_string.split()

                for hosts in hosts_list:
                    if re.match(r'.+/', hosts):
                        host_group_name = re.sub(r'/$', '', hosts)
                        host_list = get_host_group_members(host_group_name)

                        if len(host_list) > 0:
                            queue_host_dic[queue].extend(host_list)
                    elif re.match(r'^(.+)\+\d+$', hosts):
                        my_match = re.match(r'^(.+)\+\d+$', hosts)
                        host_group_name = my_match.group(1)
                        host_list = get_host_group_members(host_group_name)

                        if len(host_list) == 0:
                            queue_host_dic[queue].append(hosts)
                        else:
                            queue_host_dic[queue].extend(host_list)
                    else:
                        queue_host_dic[queue].append(hosts)

    return queue_host_dic


def get_host_queue_info():
    """
    Get queues which (specified) host belongs to.
    """
    host_queue_dic = {}

    queue_host_dic = get_queue_host_info()
    queue_list = list(queue_host_dic.keys())

    for queue in queue_list:
        host_list = queue_host_dic[queue]

        for host in host_list:
            if host in host_queue_dic.keys():
                host_queue_dic[host].append(queue)
            else:
                host_queue_dic[host] = [queue, ]

    return host_queue_dic


def get_lsf_unit_for_limits():
    """
    Get LSF LSF_UNIT_FOR_LIMITS setting, it could be KB/MB/GB/TB.
    """
    lsf_unit_for_limits = 'MB'
    command = 'badmin showconf mbd all'

    (return_code, stdout, stderr) = common.run_command(command)

    for line in str(stdout, 'utf-8').split('\n'):
        line = line.strip()

        if re.match(r'^\s*LSF_UNIT_FOR_LIMITS\s*=\s*(\S+)\s*$', line):
            my_match = re.match(r'^\s*LSF_UNIT_FOR_LIMITS\s*=\s*(\S+)\s*$', line)
            lsf_unit_for_limits = my_match.group(1)
            break

    return lsf_unit_for_limits
