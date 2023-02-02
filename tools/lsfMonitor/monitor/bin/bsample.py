# -*- coding: utf-8 -*-

import os
import sys
import argparse
import datetime
import time
from multiprocessing import Process

sys.path.append(str(os.environ['LSFMONITOR_INSTALL_PATH']) + '/monitor')
from common import common
from common import lsf_common
from common import sqlite3_common
from conf import config

# Import local config file if exists.
local_config_dir = str(os.environ['HOME']) + '/.lsfMonitor/conf'
local_config = str(local_config_dir) + '/config.py'

if os.path.exists(local_config):
    sys.path.append(local_config_dir)
    import config

os.environ["PYTHONUNBUFFERED"] = '1'


def read_args():
    """
    Read arguments.
    """
    parser = argparse.ArgumentParser()

    parser.add_argument("-j", "--job",
                        action="store_true", default=False,
                        help='Sample running job info with command "bjobs -u all -r -UF".')
    parser.add_argument("-q", "--queue",
                        action="store_true", default=False,
                        help='Sample queue info with command "bqueues".')
    parser.add_argument("-H", "--host",
                        action="store_true", default=False,
                        help='Sample host info with command "bhosts".')
    parser.add_argument("-l", "--load",
                        action="store_true", default=False,
                        help='Sample host load info with command "lsload".')
    parser.add_argument("-u", "--user",
                        action="store_true", default=False,
                        help='Sample user info with command "busers".')
    parser.add_argument("-i", "--interval",
                        type=int,
                        default=0,
                        help='Specify the sampling interval, unit is second. Sampling only once by default".')

    args = parser.parse_args()

    if (not args.job) and (not args.queue) and (not args.host) and (not args.load) and (not args.user):
        common.print_error('*Error*: at least one argument of "job/queue/host/load/user" must be selected.')
        sys.exit(1)

    if args.interval < 0:
        common.print_error('*Error*: interval "' + str(args.interval) + '": Cannot be less than "0".')
        sys.exit(1)

    return(args.job, args.queue, args.host, args.load, args.user, args.interval)


class Sampling:
    """
    Sample LSF basic information with LSF bjobs/bqueues/bhosts/lshosts/lsload/busers commands.
    Save the infomation into sqlite3 DB.
    """
    def __init__(self, job_sampling, queue_sampling, host_sampling, load_sampling, user_sampling, interval):
        self.job_sampling = job_sampling
        self.queue_sampling = queue_sampling
        self.host_sampling = host_sampling
        self.load_sampling = load_sampling
        self.user_sampling = user_sampling

        self.interval = interval
        self.db_path = str(config.db_path) + '/monitor'
        job_db_path = str(self.db_path) + '/job'

        if not os.path.exists(job_db_path):
            try:
                os.system('mkdir -p ' + str(job_db_path))
            except Exception as error:
                common.print_error('*Error*: Failed on creating sqlite job db directory "' + str(job_db_path) + '".')
                common.print_error('         ' + str(error))
                sys.exit(1)

    def get_date_info(self):
        self.sample_time = datetime.datetime.today().strftime('%Y%m%d_%H%M%S')
        self.current_seconds = int(time.time())

    def sample_job_info(self):
        """
        Sample job info, especially the memory usage info.
        """
        self.get_date_info()

        print('>>> Sampling job info ...')

        command = 'bjobs -u all -r -UF'
        bjobs_dic = lsf_common.get_bjobs_uf_info(command)
        job_list = list(bjobs_dic.keys())
        job_range_dic = common.get_job_range_dic(job_list)
        job_sql_dic = {}

        key_list = ['sample_time', 'mem']

        for job_range in job_range_dic.keys():
            job_db_file = str(self.db_path) + '/job/' + str(job_range) + '.db'
            (result, job_db_conn) = sqlite3_common.connect_db_file(job_db_file, mode='read')

            if result == 'passed':
                job_table_list = sqlite3_common.get_sql_table_list(job_db_file, job_db_conn)
            else:
                job_table_list = []

            for job in job_range_dic[job_range]:
                job_table_name = 'job_' + str(job)

                print('    Sampling for job "' + str(job) + '" ...')

                job_sql_dic[job] = {
                                    'drop': False,
                                    'key_string': '',
                                    'value_string': '',
                                   }

                # If job table (with old data) has been on the job_db_file, drop it.
                if job_table_name in job_table_list:
                    data_dic = sqlite3_common.get_sql_table_data(job_db_file, job_db_conn, job_table_name, ['sample_time'])

                    if data_dic:
                        if len(data_dic['sample_time']) > 0:
                            last_sample_time = data_dic['sample_time'][-1]
                            last_seconds = int(time.mktime(datetime.datetime.strptime(str(last_sample_time), "%Y%m%d_%H%M%S").timetuple()))

                            if self.current_seconds-last_seconds > 3600:
                                common.print_warning('    *Warning*: table "' + str(job_table_name) + '" already existed even one hour ago, will drop it.')
                                job_sql_dic[job]['drop'] = True
                                job_table_list.remove(job_table_name)

                # If job table is not on the job_db_file, create it.
                if job_table_name not in job_table_list:
                    key_string = sqlite3_common.gen_sql_table_key_string(key_list)
                    job_sql_dic[job]['key_string'] = key_string

                # Insert sql table value.
                value_list = [self.sample_time, bjobs_dic[job]['mem']]
                value_string = sqlite3_common.gen_sql_table_value_string(value_list)
                job_sql_dic[job]['value_string'] = value_string

            if result == 'passed':
                job_db_conn.commit()
                job_db_conn.close()

        for job_range in job_range_dic.keys():
            job_db_file = str(self.db_path) + '/job/' + str(job_range) + '.db'
            (result, job_db_conn) = sqlite3_common.connect_db_file(job_db_file, mode='write')

            if result != 'passed':
                return

            for job in job_range_dic[job_range]:
                job_table_name = 'job_' + str(job)

                if job_sql_dic[job]['drop']:
                    sqlite3_common.drop_sql_table(job_db_file, job_db_conn, job_table_name, commit=False)

                if job_sql_dic[job]['key_string'] != '':
                    sqlite3_common.create_sql_table(job_db_file, job_db_conn, job_table_name, job_sql_dic[job]['key_string'], commit=False)

                if job_sql_dic[job]['value_string'] != '':
                    sqlite3_common.insert_into_sql_table(job_db_file, job_db_conn, job_table_name, job_sql_dic[job]['value_string'], commit=False)

            job_db_conn.commit()
            job_db_conn.close()

        print('    Committing the update to sqlite3 ...')
        print('    Done (' + str(len(job_list)) + ' jobs).')

    def sample_queue_info(self):
        """
        Sample queue info and save it into sqlite db.
        """
        self.get_date_info()
        queue_db_file = str(self.db_path) + '/queue.db'
        (result, queue_db_conn) = sqlite3_common.connect_db_file(queue_db_file, mode='write')

        if result != 'passed':
            return

        print('>>> Sampling queue info into ' + str(queue_db_file) + ' ...')

        queue_table_list = sqlite3_common.get_sql_table_list(queue_db_file, queue_db_conn)
        bqueues_dic = lsf_common.get_bqueues_info()
        queue_list = bqueues_dic['QUEUE_NAME']
        queue_list.append('ALL')
        queue_sql_dic = {}

        key_list = ['sample_time', 'NJOBS', 'PEND', 'RUN', 'SUSP']

        for i in range(len(queue_list)):
            queue = queue_list[i]
            queue_sql_dic[queue] = {
                                    'key_string': '',
                                    'value_string': '',
                                   }
            queue_table_name = 'queue_' + str(queue)

            print('    Sampling for queue "' + str(queue) + '" ...')

            # Generate sql table.
            if queue_table_name not in queue_table_list:
                key_string = sqlite3_common.gen_sql_table_key_string(key_list)
                queue_sql_dic[queue]['key_string'] = key_string

            # Insert sql table value.
            if queue == 'ALL':
                value_list = [self.sample_time, sum([int(i) for i in bqueues_dic['NJOBS']]), sum([int(i) for i in bqueues_dic['PEND']]), sum([int(i) for i in bqueues_dic['RUN']]), sum([int(i) for i in bqueues_dic['SUSP']])]
            else:
                value_list = [self.sample_time, bqueues_dic['NJOBS'][i], bqueues_dic['PEND'][i], bqueues_dic['RUN'][i], bqueues_dic['SUSP'][i]]

            value_string = sqlite3_common.gen_sql_table_value_string(value_list)
            queue_sql_dic[queue]['value_string'] = value_string

        for queue in queue_list:
            queue_table_name = 'queue_' + str(queue)

            if queue_sql_dic[queue]['key_string'] != '':
                sqlite3_common.create_sql_table(queue_db_file, queue_db_conn, queue_table_name, queue_sql_dic[queue]['key_string'], commit=False)

            if queue_sql_dic[queue]['value_string'] != '':
                sqlite3_common.insert_into_sql_table(queue_db_file, queue_db_conn, queue_table_name, queue_sql_dic[queue]['value_string'], commit=False)

        print('    Committing the update to sqlite3 ...')

        # Clean up queue database, only keep 10000 items.
        for queue in queue_list:
            queue_table_name = 'queue_' + str(queue)
            queue_table_count = int(sqlite3_common.get_sql_table_count(queue_db_file, queue_db_conn, queue_table_name))

            if queue_table_count != 'N/A':
                if int(queue_table_count) > 10000:
                    row_id = 'sample_time'
                    begin_line = 0
                    end_line = int(queue_table_count) - 10000

                    print('    Deleting database "' + str(queue_db_file) + '" table "' + str(queue_table_name) + '" ' + str(begin_line) + '-' + str(end_line) + ' lines to only keep 10000 items.')

                    sqlite3_common.delete_sql_table_rows(queue_db_file, queue_db_conn, queue_table_name, row_id, begin_line, end_line)

        queue_db_conn.commit()
        queue_db_conn.close()

    def sample_host_info(self):
        """
        Sample host info and save it into sqlite db.
        """
        self.get_date_info()
        host_db_file = str(self.db_path) + '/host.db'
        (result, host_db_conn) = sqlite3_common.connect_db_file(host_db_file, mode='write')

        if result != 'passed':
            return

        print('>>> Sampling host info into ' + str(host_db_file) + ' ...')

        host_table_list = sqlite3_common.get_sql_table_list(host_db_file, host_db_conn)
        bhosts_dic = lsf_common.get_bhosts_info()
        host_list = bhosts_dic['HOST_NAME']
        host_sql_dic = {}

        key_list = ['sample_time', 'NJOBS', 'RUN', 'SSUSP', 'USUSP']

        for i in range(len(host_list)):
            host = host_list[i]
            host_sql_dic[host] = {
                                  'key_string': '',
                                  'value_string': '',
                                 }
            host_table_name = 'host_' + str(host)

            print('    Sampling for host "' + str(host) + '" ...')

            # Generate sql table.
            if host_table_name not in host_table_list:
                key_string = sqlite3_common.gen_sql_table_key_string(key_list)
                host_sql_dic[host]['key_string'] = key_string

            # Insert sql table value.
            value_list = [self.sample_time, bhosts_dic['NJOBS'][i], bhosts_dic['RUN'][i], bhosts_dic['SSUSP'][i], bhosts_dic['USUSP'][i]]
            value_string = sqlite3_common.gen_sql_table_value_string(value_list)
            host_sql_dic[host]['value_string'] = value_string

        for host in host_list:
            host_table_name = 'host_' + str(host)

            if host_sql_dic[host]['key_string'] != '':
                sqlite3_common.create_sql_table(host_db_file, host_db_conn, host_table_name, host_sql_dic[host]['key_string'], commit=False)

            if host_sql_dic[host]['value_string'] != '':
                sqlite3_common.insert_into_sql_table(host_db_file, host_db_conn, host_table_name, host_sql_dic[host]['value_string'], commit=False)

        print('    Committing the update to sqlite3 ...')

        # Clean up host database, only keep 10000 items.
        for host in host_list:
            host_table_name = 'host_' + str(host)
            host_table_count = int(sqlite3_common.get_sql_table_count(host_db_file, host_db_conn, host_table_name))

            if host_table_count != 'N/A':
                if int(host_table_count) > 10000:
                    row_id = 'sample_time'
                    begin_line = 0
                    end_line = int(host_table_count) - 10000

                    print('    Deleting database "' + str(host_db_file) + '" table "' + str(host_table_name) + '" ' + str(begin_line) + '-' + str(end_line) + ' lines to only keep 10000 items.')

                    sqlite3_common.delete_sql_table_rows(host_db_file, host_db_conn, host_table_name, row_id, begin_line, end_line)

        host_db_conn.commit()
        host_db_conn.close()

    def sample_load_info(self):
        """
        Sample host load info and save it into sqlite db.
        """
        self.get_date_info()
        load_db_file = str(self.db_path) + '/load.db'
        (result, load_db_conn) = sqlite3_common.connect_db_file(load_db_file, mode='write')

        if result != 'passed':
            return

        print('>>> Sampling host load info into ' + str(load_db_file) + ' ...')

        load_table_list = sqlite3_common.get_sql_table_list(load_db_file, load_db_conn)
        lsload_dic = lsf_common.get_lsload_info()
        host_list = lsload_dic['HOST_NAME']
        load_sql_dic = {}

        key_list = ['sample_time', 'ut', 'tmp', 'swp', 'mem']

        for i in range(len(host_list)):
            host = host_list[i]
            load_sql_dic[host] = {
                                  'key_string': '',
                                  'value_string': '',
                                 }
            load_table_name = 'load_' + str(host)

            print('    Sampling for host "' + str(host) + '" ...')

            # Generate sql table.
            if load_table_name not in load_table_list:
                key_string = sqlite3_common.gen_sql_table_key_string(key_list)
                load_sql_dic[host]['key_string'] = key_string

            # Insert sql table value.
            value_list = [self.sample_time, lsload_dic['ut'][i], lsload_dic['tmp'][i], lsload_dic['swp'][i], lsload_dic['mem'][i]]
            value_string = sqlite3_common.gen_sql_table_value_string(value_list)
            load_sql_dic[host]['value_string'] = value_string

        for host in host_list:
            load_table_name = 'load_' + str(host)

            if load_sql_dic[host]['key_string'] != '':
                sqlite3_common.create_sql_table(load_db_file, load_db_conn, load_table_name, load_sql_dic[host]['key_string'], commit=False)

            if load_sql_dic[host]['value_string'] != '':
                sqlite3_common.insert_into_sql_table(load_db_file, load_db_conn, load_table_name, load_sql_dic[host]['value_string'], commit=False)

        print('    Committing the update to sqlite3 ...')

        # Clean up load database, only keep 10000 items.
        for host in host_list:
            load_table_name = 'load_' + str(host)
            load_table_count = int(sqlite3_common.get_sql_table_count(load_db_file, load_db_conn, load_table_name))

            if load_table_count != 'N/A':
                if int(load_table_count) > 10000:
                    row_id = 'sample_time'
                    begin_line = 0
                    end_line = int(load_table_count) - 10000

                    print('    Deleting database "' + str(load_db_file) + '" table "' + str(load_table_name) + '" ' + str(begin_line) + '-' + str(end_line) + ' lines to only keep 10000 items.')

                    sqlite3_common.delete_sql_table_rows(load_db_file, load_db_conn, load_table_name, row_id, begin_line, end_line)

        load_db_conn.commit()
        load_db_conn.close()

    def sample_user_info(self):
        """
        Sample user info and save it into sqlite db.
        """
        self.get_date_info()
        user_db_file = str(self.db_path) + '/user.db'
        (result, user_db_conn) = sqlite3_common.connect_db_file(user_db_file, mode='write')

        if result != 'passed':
            return

        print('>>> Sampling user info into ' + str(user_db_file) + ' ...')

        user_table_list = sqlite3_common.get_sql_table_list(user_db_file, user_db_conn)
        busers_dic = lsf_common.get_busers_info()
        user_list = busers_dic['USER/GROUP']
        user_sql_dic = {}

        key_list = ['sample_time', 'NJOBS', 'PEND', 'RUN', 'SSUSP', 'USUSP']

        for i in range(len(user_list)):
            user = user_list[i]
            user_sql_dic[user] = {
                                  'key_string': '',
                                  'value_string': '',
                                 }
            user_table_name = 'user_' + str(user)

            print('    Sampling for user "' + str(user) + '" ...')

            # Generate sql table.
            if user_table_name not in user_table_list:
                key_string = sqlite3_common.gen_sql_table_key_string(key_list)
                user_sql_dic[user]['key_string'] = key_string

            # Insert sql table value.
            value_list = [self.sample_time, busers_dic['NJOBS'][i], busers_dic['PEND'][i], busers_dic['RUN'][i], busers_dic['SSUSP'][i], busers_dic['USUSP'][i]]
            value_string = sqlite3_common.gen_sql_table_value_string(value_list)
            user_sql_dic[user]['value_string'] = value_string

        for user in user_list:
            user_table_name = 'user_' + str(user)

            if user_sql_dic[user]['key_string'] != '':
                sqlite3_common.create_sql_table(user_db_file, user_db_conn, user_table_name, user_sql_dic[user]['key_string'], commit=False)

            if user_sql_dic[user]['value_string'] != '':
                sqlite3_common.insert_into_sql_table(user_db_file, user_db_conn, user_table_name, user_sql_dic[user]['value_string'], commit=False)

        print('    Committing the update to sqlite3 ...')

        # Clean up user database, only keep 10000 items.
        for user in user_list:
            user_table_name = 'user_' + str(user)
            user_table_count = int(sqlite3_common.get_sql_table_count(user_db_file, user_db_conn, user_table_name))

            if user_table_count != 'N/A':
                if int(user_table_count) > 10000:
                    row_id = 'sample_time'
                    begin_line = 0
                    end_line = int(user_table_count) - 10000

                    print('    Deleting database "' + str(user_db_file) + '" table "' + str(user_table_name) + '" ' + str(begin_line) + '-' + str(end_line) + ' lines to only keep 10000 items.')

                    sqlite3_common.delete_sql_table_rows(user_db_file, user_db_conn, user_table_name, row_id, begin_line, end_line)

        user_db_conn.commit()
        user_db_conn.close()

    def sampling(self):
        while True:
            if self.job_sampling:
                p = Process(target=self.sample_job_info)
                p.start()

            if self.queue_sampling:
                p = Process(target=self.sample_queue_info)
                p.start()

            if self.host_sampling:
                p = Process(target=self.sample_host_info)
                p.start()

            if self.load_sampling:
                p = Process(target=self.sample_load_info)
                p.start()

            if self.user_sampling:
                p = Process(target=self.sample_user_info)
                p.start()

            p.join()

            if self.interval == 0:
                break
            elif self.interval > 0:
                time.sleep(self.interval)


#################
# Main Function #
#################
def main():
    (job, queue, host, load, user, interval) = read_args()
    my_sampling = Sampling(job, queue, host, load, user, interval)
    my_sampling.sampling()


if __name__ == '__main__':
    main()
