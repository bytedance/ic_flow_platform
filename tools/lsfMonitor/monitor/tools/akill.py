# -*- coding: utf-8 -*-
import os
import re
import sys
import copy
import argparse

sys.path.insert(0, str(os.environ['LSFMONITOR_INSTALL_PATH']) + '/monitor')
from common import common
from common import common_lsf

os.environ['PYTHONUNBUFFERED'] = '1'


def read_args():
    """
    Read in arguments.
    """
    parser = argparse.ArgumentParser()

    parser.add_argument('-j', '--jobid',
                        nargs='+',
                        default=[],
                        help='kill specified job(s) based on jobid(s), support fuzzy matching, also support jobid range like "10200-10450".')
    parser.add_argument('-J', '--job_name',
                        nargs='+',
                        default=[],
                        help='kill specified job(s) based on job_name(s), support fuzzy matching.')
    parser.add_argument('-c', '--command',
                        nargs='+',
                        default=[],
                        help='kill specified job(s) based on command(s), support fuzzy matching.')
    parser.add_argument('-s', '--submit_time',
                        nargs='+',
                        default=[],
                        help='kill specified job(s) based on submit_time(s), support fuzzy matching.')
    parser.add_argument('-m', '--execute_host',
                        nargs='+',
                        default=[],
                        help='kill specified job(s) based on execute host(s).')
    parser.add_argument('-q', '--queue',
                        nargs='+',
                        default=[],
                        help='kill specified job(s) based on queue(s).')
    parser.add_argument('-u', '--user',
                        nargs='+',
                        default=[],
                        help='kill specified job(s) based on user(s).')

    args = parser.parse_args()

    return args.jobid, args.job_name, args.command, args.submit_time, args.execute_host, args.queue, args.user


class AutoKill():
    def __init__(self, jobid_list, job_name_list, command_list, submit_time_list, execute_host_list, queue_list, user_list):
        self.jobid_list = jobid_list
        self.job_name_list = job_name_list
        self.command_list = command_list
        self.submit_time_list = submit_time_list
        self.execute_host_list = execute_host_list
        self.queue_list = queue_list
        self.user_list = user_list

    def parse_jobid_range(self, start_jobid, end_jobid):
        """
        Get jobid list based on start_jobid ~ end_jobid.
        """
        if start_jobid >= end_jobid:
            common.bprint('Start jobid "' + str(start_jobid) + '" must be smaller than end jobid "' + str(end_jobid) + '".', level='Error')
            sys.exit(1)
        else:
            jobid_list = []

            for jobid in range(start_jobid, end_jobid+1):
                jobid_list.append(str(jobid))

            return jobid_list

    def get_real_jobid_list(self):
        orig_jobid_list = copy.deepcopy(self.jobid_list)
        self.jobid_list = []

        for jobid in orig_jobid_list:
            if jobid == '0':
                self.jobid_list = ['0',]
                break
            elif re.match(r'^\d+$', jobid):
                self.jobid_list.append(jobid)
            elif re.search(r'\*', jobid):
                self.jobid_list.append(re.sub(r'\*', '.*', jobid))
            elif re.match(r'^(\d+)-(\d+)$', jobid):
                my_match = re.match(r'^(\d+)-(\d+)$', jobid)
                start_jobid = int(my_match.group(1))
                end_jobid = int(my_match.group(2))
                jobid_range_list = self.parse_jobid_range(start_jobid, end_jobid)
                self.jobid_list.extend(jobid_range_list)
            else:
                common.bprint('"' + str(jobid) + '": Invalid jobid format.', level='Error')
                sys.exit(1)

    def run_command(self, command):
        print('* ' + str(command))

        (return_code, stdout, stderr) = common.run_command(command)

        for line in str(stdout, 'utf-8').split('\n'):
            if line:
                print('  ' + str(line))

        for line in str(stderr, 'utf-8').split('\n'):
            if line:
                print('  ' + str(line))

    def kill_base_jobid(self, jobs_dic):
        self.get_real_jobid_list()

        for (job, job_dic) in jobs_dic.items():
            for jobid in self.jobid_list:
                if re.match(jobid, job):
                    command = 'bkill ' + str(job)
                    self.run_command(command)

    def kill_base_job_name(self, jobs_dic):
        for (job, job_dic) in jobs_dic.items():
            for job_name in self.job_name_list:
                if re.search(r'\*', job_name):
                    job_name = re.sub(r'\*', '.*', job_name)

                if job_dic['job_name'] and re.match(job_name, job_dic['job_name']):
                    command = 'bkill ' + str(job)
                    self.run_command(command)

    def kill_base_command(self, jobs_dic):
        for (job, job_dic) in jobs_dic.items():
            for command in self.command_list:
                if re.search(r'\*', command):
                    command = re.sub(r'\*', '.*', command)

                if re.match(command, job_dic['command']):
                    command = 'bkill ' + str(job)
                    self.run_command(command)

    def kill_base_submit_time(self, jobs_dic):
        for (job, job_dic) in jobs_dic.items():
            for submit_time in self.submit_time_list:
                if re.search(r'\*', submit_time):
                    submit_time = re.sub(r'\*', '.*', submit_time)

                if re.search(submit_time, job_dic['submitted_time']):
                    command = 'bkill ' + str(job)
                    self.run_command(command)

    def kill_base_execute_host(self):
        for execute_host in self.execute_host_list:
            command = 'bkill -m ' + str(execute_host) + ' 0'
            self.run_command(command)

    def kill_base_queue(self):
        for queue in self.queue_list:
            command = 'bkill -q ' + str(queue) + ' 0'
            self.run_command(command)

    def kill_base_user(self):
        for user in self.user_list:
            command = 'bkill -u ' + str(user) + ' 0'
            self.run_command(command)

    def run(self):
        if self.jobid_list or self.job_name_list or self.command_list or self.submit_time_list:
            jobs_dic = common_lsf.get_bjobs_uf_info(command='bjobs -r -p -UF')

            if self.jobid_list:
                self.kill_base_jobid(jobs_dic)

            if self.job_name_list:
                self.kill_base_job_name(jobs_dic)

            if self.command_list:
                self.kill_base_command(jobs_dic)

            if self.submit_time_list:
                self.kill_base_submit_time(jobs_dic)

        if self.execute_host_list:
            self.kill_base_execute_host()

        if self.queue_list:
            self.kill_base_queue()

        if self.user_list:
            self.kill_base_user()


################
# Main Process #
################
def main():
    (jobid_list, job_name_list, command_list, submit_time_list, execute_host_list, queue_list, user_lise) = read_args()
    my_auto_kill = AutoKill(jobid_list, job_name_list, command_list, submit_time_list, execute_host_list, queue_list, user_lise)
    my_auto_kill.run()


if __name__ == '__main__':
    main()
