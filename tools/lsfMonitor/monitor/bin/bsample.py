# -*- coding: utf-8 -*-

import os
import re
import sys
import argparse
import datetime
import time
from multiprocessing import Process

sys.path.append(str(os.environ['LSFMONITOR_INSTALL_PATH']) + '/monitor')
from common import common
from common import common_lsf
from common import common_sqlite3
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
                        help='Sample host load (ut/tmp/swp/mem) info with command "lsload".')
    parser.add_argument("-u", "--user",
                        action="store_true", default=False,
                        help='Sample user info with command "busers".')
    parser.add_argument("-U", "--utilization",
                        action="store_true", default=False,
                        help='Sample utilization (slot/cpu/mem) info with command "lsload/bhosts/lshosts".')

    args = parser.parse_args()

    if (not args.job) and (not args.queue) and (not args.host) and (not args.load) and (not args.user) and (not args.utilization):
        common.print_error('*Error*: at least one argument of "job/queue/host/load/user/utilization" must be selected.')
        sys.exit(1)

    return (args.job, args.queue, args.host, args.load, args.user, args.utilization)


class Sampling:
    """
    Sample LSF basic information with LSF bjobs/bqueues/bhosts/lshosts/lsload/busers commands.
    Save the infomation into sqlite3 DB.
    """
    def __init__(self, job_sampling, queue_sampling, host_sampling, load_sampling, user_sampling, utilization_sampling):
        self.job_sampling = job_sampling
        self.queue_sampling = queue_sampling
        self.host_sampling = host_sampling
        self.load_sampling = load_sampling
        self.user_sampling = user_sampling
        self.utilization_sampling = utilization_sampling

        # Get sample time.
        self.sample_second = int(time.time())
        self.sample_date = datetime.datetime.today().strftime('%Y%m%d')
        self.sample_time = datetime.datetime.today().strftime('%Y%m%d_%H%M%S')

        # Create db path.
        self.db_path = str(config.db_path) + '/monitor'
        job_db_path = str(self.db_path) + '/job'

        if not os.path.exists(job_db_path):
            try:
                os.makedirs(job_db_path)
            except Exception as error:
                common.print_error('*Error*: Failed on creating sqlite job db directory "' + str(job_db_path) + '".')
                common.print_error('         ' + str(error))
                sys.exit(1)

    def sample_job_info(self):
        """
        Sample job info, especially the memory usage info.
        """
        print('>>> Sampling job info ...')

        bjobs_dic = common_lsf.get_bjobs_uf_info('bjobs -u all -r -UF')
        job_list = list(bjobs_dic.keys())
        job_range_dic = common.get_job_range_dic(job_list)

        key_list = ['sample_second', 'sample_time', 'mem']
        key_type_list = ['INTEGER PRIMARY KEY', 'TEXT', 'TEXT']

        for job_range in job_range_dic.keys():
            job_db_file = str(self.db_path) + '/job/' + str(job_range) + '.db'
            (result, job_db_conn) = common_sqlite3.connect_db_file(job_db_file, mode='write')

            if result == 'passed':
                job_table_list = common_sqlite3.get_sql_table_list(job_db_file, job_db_conn)

                for job in job_range_dic[job_range]:
                    job_table_name = 'job_' + str(job)

                    print('    Sampling for job "' + str(job) + '" ...')

                    # If job table (with old data) has been on the job_db_file, drop it.
                    if job_table_name in job_table_list:
                        data_dic = common_sqlite3.get_sql_table_data(job_db_file, job_db_conn, job_table_name, ['sample_second'])

                        if data_dic:
                            if len(data_dic['sample_second']) > 0:
                                last_sample_second = int(data_dic['sample_second'][-1])

                                if self.sample_second - last_sample_second > 3600:
                                    common.print_warning('    *Warning*: table "' + str(job_table_name) + '" already existed even one hour ago, will drop it.')
                                    common_sqlite3.drop_sql_table(job_db_file, job_db_conn, job_table_name, commit=False)
                                    job_table_list.remove(job_table_name)

                    # Generate sql table if not exitst.
                    if job_table_name not in job_table_list:
                        key_string = common_sqlite3.gen_sql_table_key_string(key_list, key_type_list)
                        common_sqlite3.create_sql_table(job_db_file, job_db_conn, job_table_name, key_string, commit=False)

                    # Insert sql table value.
                    value_list = [self.sample_second, self.sample_time, bjobs_dic[job]['mem']]
                    value_string = common_sqlite3.gen_sql_table_value_string(value_list)
                    common_sqlite3.insert_into_sql_table(job_db_file, job_db_conn, job_table_name, value_string, commit=False)

                job_db_conn.commit()
                job_db_conn.close()

        print('    Done (' + str(len(job_list)) + ' jobs).')

    def sample_queue_info(self):
        """
        Sample queue info and save it into sqlite db.
        """
        print('>>> Sampling queue info ...')

        queue_db_file = str(self.db_path) + '/queue.db'
        (result, queue_db_conn) = common_sqlite3.connect_db_file(queue_db_file, mode='write')

        if result == 'passed':
            queue_table_list = common_sqlite3.get_sql_table_list(queue_db_file, queue_db_conn)
            bqueues_dic = common_lsf.get_bqueues_info()
            queue_list = bqueues_dic['QUEUE_NAME']
            queue_list.append('ALL')

            key_list = ['sample_second', 'sample_time', 'NJOBS', 'PEND', 'RUN', 'SUSP']
            key_type_list = ['INTEGER PRIMARY KEY', 'TEXT', 'TEXT', 'TEXT', 'TEXT', 'TEXT']

            for i in range(len(queue_list)):
                queue = queue_list[i]
                queue_table_name = 'queue_' + str(queue)

                print('    Sampling for queue "' + str(queue) + '" ...')

                # Clean up queue database, only keep 10000 items.
                if queue_table_name in queue_table_list:
                    queue_table_count = common_sqlite3.get_sql_table_count(queue_db_file, queue_db_conn, queue_table_name)

                    if queue_table_count != 'N/A':
                        if int(queue_table_count) > 10000:
                            row_id = 'sample_time'
                            begin_line = 0
                            end_line = int(queue_table_count) - 10000

                            print('    Deleting database "' + str(queue_db_file) + '" table "' + str(queue_table_name) + '" ' + str(begin_line) + '-' + str(end_line) + ' lines to only keep 10000 items.')

                            common_sqlite3.delete_sql_table_rows(queue_db_file, queue_db_conn, queue_table_name, row_id, begin_line, end_line)

                # Generate sql table if not exitst.
                if queue_table_name not in queue_table_list:
                    key_string = common_sqlite3.gen_sql_table_key_string(key_list, key_type_list)
                    common_sqlite3.create_sql_table(queue_db_file, queue_db_conn, queue_table_name, key_string, commit=False)

                # Insert sql table value.
                if queue == 'ALL':
                    value_list = [self.sample_second, self.sample_time, sum([int(i) for i in bqueues_dic['NJOBS']]), sum([int(i) for i in bqueues_dic['PEND']]), sum([int(i) for i in bqueues_dic['RUN']]), sum([int(i) for i in bqueues_dic['SUSP']])]
                else:
                    value_list = [self.sample_second, self.sample_time, bqueues_dic['NJOBS'][i], bqueues_dic['PEND'][i], bqueues_dic['RUN'][i], bqueues_dic['SUSP'][i]]

                value_string = common_sqlite3.gen_sql_table_value_string(value_list)
                common_sqlite3.insert_into_sql_table(queue_db_file, queue_db_conn, queue_table_name, value_string, commit=False)

        queue_db_conn.commit()
        queue_db_conn.close()

    def sample_host_info(self):
        """
        Sample host info and save it into sqlite db.
        """
        print('>>> Sampling host info ...')

        host_db_file = str(self.db_path) + '/host.db'
        (result, host_db_conn) = common_sqlite3.connect_db_file(host_db_file, mode='write')

        if result == 'passed':
            host_table_list = common_sqlite3.get_sql_table_list(host_db_file, host_db_conn)
            bhosts_dic = common_lsf.get_bhosts_info()
            host_list = bhosts_dic['HOST_NAME']

            key_list = ['sample_second', 'sample_time', 'NJOBS', 'RUN', 'SSUSP', 'USUSP']
            key_type_list = ['INTEGER PRIMARY KEY', 'TEXT', 'TEXT', 'TEXT', 'TEXT', 'TEXT']

            for i in range(len(host_list)):
                host = host_list[i]
                host_table_name = 'host_' + str(host)

                print('    Sampling for host "' + str(host) + '" ...')

                # Clean up host database, only keep 10000 items.
                if host_table_name in host_table_list:
                    host_table_count = common_sqlite3.get_sql_table_count(host_db_file, host_db_conn, host_table_name)

                    if host_table_count != 'N/A':
                        if int(host_table_count) > 10000:
                            row_id = 'sample_time'
                            begin_line = 0
                            end_line = int(host_table_count) - 10000

                            print('    Deleting database "' + str(host_db_file) + '" table "' + str(host_table_name) + '" ' + str(begin_line) + '-' + str(end_line) + ' lines to only keep 10000 items.')

                            common_sqlite3.delete_sql_table_rows(host_db_file, host_db_conn, host_table_name, row_id, begin_line, end_line)

                # Generate sql table if not exists.
                if host_table_name not in host_table_list:
                    key_string = common_sqlite3.gen_sql_table_key_string(key_list, key_type_list)
                    common_sqlite3.create_sql_table(host_db_file, host_db_conn, host_table_name, key_string, commit=False)

                # Insert sql table value.
                value_list = [self.sample_second, self.sample_time, bhosts_dic['NJOBS'][i], bhosts_dic['RUN'][i], bhosts_dic['SSUSP'][i], bhosts_dic['USUSP'][i]]
                value_string = common_sqlite3.gen_sql_table_value_string(value_list)
                common_sqlite3.insert_into_sql_table(host_db_file, host_db_conn, host_table_name, value_string, commit=False)

        host_db_conn.commit()
        host_db_conn.close()

    def sample_load_info(self):
        """
        Sample host load info and save it into sqlite db.
        """
        print('>>> Sampling host load info ...')

        load_db_file = str(self.db_path) + '/load.db'
        (result, load_db_conn) = common_sqlite3.connect_db_file(load_db_file, mode='write')

        if result == 'passed':
            load_table_list = common_sqlite3.get_sql_table_list(load_db_file, load_db_conn)
            lsload_dic = common_lsf.get_lsload_info()
            host_list = lsload_dic['HOST_NAME']

            key_list = ['sample_second', 'sample_time', 'ut', 'tmp', 'swp', 'mem']
            key_type_list = ['INTEGER PRIMARY KEY', 'TEXT', 'TEXT', 'TEXT', 'TEXT', 'TEXT']

            for i in range(len(host_list)):
                host = host_list[i]
                load_table_name = 'load_' + str(host)

                print('    Sampling for host "' + str(host) + '" ...')

                # Clean up load database, only keep 100000 items.
                if load_table_name in load_table_list:
                    load_table_count = common_sqlite3.get_sql_table_count(load_db_file, load_db_conn, load_table_name)

                    if load_table_count != 'N/A':
                        if int(load_table_count) > 100000:
                            row_id = 'sample_time'
                            begin_line = 0
                            end_line = int(load_table_count) - 100000

                            print('    Deleting database "' + str(load_db_file) + '" table "' + str(load_table_name) + '" ' + str(begin_line) + '-' + str(end_line) + ' lines to only keep 100000 items.')

                            common_sqlite3.delete_sql_table_rows(load_db_file, load_db_conn, load_table_name, row_id, begin_line, end_line)

                # Generate sql table if not exists.
                if load_table_name not in load_table_list:
                    key_string = common_sqlite3.gen_sql_table_key_string(key_list, key_type_list)
                    common_sqlite3.create_sql_table(load_db_file, load_db_conn, load_table_name, key_string, commit=False)

                # Insert sql table value.
                value_list = [self.sample_second, self.sample_time, lsload_dic['ut'][i], lsload_dic['tmp'][i], lsload_dic['swp'][i], lsload_dic['mem'][i]]
                value_string = common_sqlite3.gen_sql_table_value_string(value_list)
                common_sqlite3.insert_into_sql_table(load_db_file, load_db_conn, load_table_name, value_string, commit=False)

        load_db_conn.commit()
        load_db_conn.close()

    def sample_user_info(self):
        """
        Sample user info and save it into sqlite db.
        """
        print('>>> Sampling user info ...')

        user_db_file = str(self.db_path) + '/user.db'
        (result, user_db_conn) = common_sqlite3.connect_db_file(user_db_file, mode='write')

        if result == 'passed':
            user_table_list = common_sqlite3.get_sql_table_list(user_db_file, user_db_conn)
            busers_dic = common_lsf.get_busers_info()
            user_list = busers_dic['USER/GROUP']

            key_list = ['sample_second', 'sample_time', 'NJOBS', 'PEND', 'RUN', 'SSUSP', 'USUSP']
            key_type_list = ['INTEGER PRIMARY KEY', 'TEXT', 'TEXT', 'TEXT', 'TEXT', 'TEXT', 'TEXT']

            for i in range(len(user_list)):
                user = user_list[i]
                user_table_name = 'user_' + str(user)

                print('    Sampling for user "' + str(user) + '" ...')

                # Clean up user database, only keep 100000 items.
                if user_table_name in user_table_list:
                    user_table_count = common_sqlite3.get_sql_table_count(user_db_file, user_db_conn, user_table_name)

                    if user_table_count != 'N/A':
                        if int(user_table_count) > 100000:
                            row_id = 'sample_time'
                            begin_line = 0
                            end_line = int(user_table_count) - 100000

                            print('    Deleting database "' + str(user_db_file) + '" table "' + str(user_table_name) + '" ' + str(begin_line) + '-' + str(end_line) + ' lines to only keep 100000 items.')

                            common_sqlite3.delete_sql_table_rows(user_db_file, user_db_conn, user_table_name, row_id, begin_line, end_line)

                # Generate sql table if not exists.
                if user_table_name not in user_table_list:
                    key_string = common_sqlite3.gen_sql_table_key_string(key_list, key_type_list)
                    common_sqlite3.create_sql_table(user_db_file, user_db_conn, user_table_name, key_string, commit=False)

                # Insert sql table value.
                value_list = [self.sample_second, self.sample_time, busers_dic['NJOBS'][i], busers_dic['PEND'][i], busers_dic['RUN'][i], busers_dic['SSUSP'][i], busers_dic['USUSP'][i]]
                value_string = common_sqlite3.gen_sql_table_value_string(value_list)
                common_sqlite3.insert_into_sql_table(user_db_file, user_db_conn, user_table_name, value_string, commit=False)

        user_db_conn.commit()
        user_db_conn.close()

    def sample_utilization_info(self):
        """
        Sample host resource utilization info and save it into sqlite db.
        """
        print('>>> Sampling utilization info ...')

        utilization_db_file = str(self.db_path) + '/utilization.db'
        (result, utilization_db_conn) = common_sqlite3.connect_db_file(utilization_db_file, mode='write')

        if result == 'passed':
            utilization_table_list = common_sqlite3.get_sql_table_list(utilization_db_file, utilization_db_conn)
            bhosts_dic = common_lsf.get_bhosts_info()
            lshosts_dic = common_lsf.get_lshosts_info()
            lsload_dic = common_lsf.get_lsload_info()
            host_list = lsload_dic['HOST_NAME']

            key_list = ['sample_second', 'sample_time', 'slot', 'cpu', 'mem']
            key_type_list = ['INTEGER PRIMARY KEY', 'TEXT', 'TEXT', 'TEXT', 'TEXT']

            for i in range(len(host_list)):
                host = host_list[i]
                utilization_table_name = 'utilization_' + str(host)

                print('    Sampling for host "' + str(host) + '" ...')

                # Clean up utilization database, only keep 100000 items.
                if utilization_table_name in utilization_table_list:
                    utilization_table_count = common_sqlite3.get_sql_table_count(utilization_db_file, utilization_db_conn, utilization_table_name)

                    if utilization_table_count != 'N/A':
                        if int(utilization_table_count) > 100000:
                            row_id = 'sample_time'
                            begin_line = 0
                            end_line = int(utilization_table_count) - 100000

                            print('    Deleting database "' + str(utilization_db_file) + '" table "' + str(utilization_table_name) + '" ' + str(begin_line) + '-' + str(end_line) + ' lines to only keep 100000 items.')

                            common_sqlite3.delete_sql_table_rows(utilization_db_file, utilization_db_conn, utilization_table_name, row_id, begin_line, end_line)

                # Generate sql table if not exists.
                if utilization_table_name not in utilization_table_list:
                    key_string = common_sqlite3.gen_sql_table_key_string(key_list, key_type_list)
                    common_sqlite3.create_sql_table(utilization_db_file, utilization_db_conn, utilization_table_name, key_string, commit=False)

                # Get slot_utilization.
                slot_utilization = 0

                for (j, host_name) in enumerate(bhosts_dic['HOST_NAME']):
                    if (host_name == host) and re.match(r'^\d+$', bhosts_dic['NJOBS'][j]) and re.match(r'^\d+$', bhosts_dic['MAX'][j]) and (int(bhosts_dic['MAX'][j]) != 0):
                        slot_utilization = round(int(bhosts_dic['NJOBS'][j])/int(bhosts_dic['MAX'][j])*100, 1)
                        break

                # Get cpu_utilization.
                cpu_utilization = 0

                if re.match(r'^\d+%$', lsload_dic['ut'][i]):
                    cpu_utilization = re.sub('%', '', lsload_dic['ut'][i])

                # Get mem_utilization.
                mem_utilization = 0

                for (k, host_name) in enumerate(lshosts_dic['HOST_NAME']):
                    if (host_name == host) and re.match(r'^(\d+(\.\d+)?)([MGT])$', lshosts_dic['maxmem'][k]) and re.match(r'^(\d+(\.\d+)?)([MGT])$', lsload_dic['mem'][i]):
                        # Get maxmem with MB.
                        maxmem_match = re.match(r'^(\d+(\.\d+)?)([MGT])$', lshosts_dic['maxmem'][k])
                        maxmem = maxmem_match.group(1)
                        maxmem_unit = maxmem_match.group(3)

                        if maxmem_unit == 'G':
                            maxmem = float(maxmem)*1024
                        elif maxmem_unit == 'T':
                            maxmem = float(maxmem)*1024*1024

                        # Get mem with MB.
                        mem_match = re.match(r'^(\d+(\.\d+)?)([MGT])$', lsload_dic['mem'][i])
                        mem = mem_match.group(1)
                        mem_unit = mem_match.group(3)

                        if mem_unit == 'G':
                            mem = float(mem)*1024
                        elif mem_unit == 'T':
                            mem = float(mem)*1024*1024

                        mem_utilization = round((maxmem-mem)*100/maxmem, 1)
                        break

                # Insert sql table value.
                value_list = [self.sample_second, self.sample_time, slot_utilization, cpu_utilization, mem_utilization]
                value_string = common_sqlite3.gen_sql_table_value_string(value_list)
                common_sqlite3.insert_into_sql_table(utilization_db_file, utilization_db_conn, utilization_table_name, value_string, commit=False)

        utilization_db_conn.commit()
        utilization_db_conn.close()

        self.count_utilization_day_info()

    def get_utilization_day_info(self):
        """
        Get current day slot/cpu/mem utilizaiton info from sqlite3 database.
        Reture slot/cpu/mem average utilization info with utilization_day_dic.
        """
        utilization_day_dic = {}

        begin_time = str(self.sample_date) + ' 00:00:00'
        begin_second = time.mktime(time.strptime(begin_time, '%Y%m%d %H:%M:%S'))
        end_time = str(self.sample_date) + ' 23:59:59'
        end_second = time.mktime(time.strptime(end_time, '%Y%m%d %H:%M:%S'))
        select_condition = "WHERE sample_second BETWEEN '" + str(begin_second) + "' AND '" + str(end_second) + "'"

        utilization_db_file = str(self.db_path) + '/utilization.db'
        (result, utilization_db_conn) = common_sqlite3.connect_db_file(utilization_db_file, mode='write')

        if result == 'passed':
            utilization_table_list = common_sqlite3.get_sql_table_list(utilization_db_file, utilization_db_conn)

            for utilization_table_name in utilization_table_list:
                # Get current day issued/in_use/utilization from sqlite3 database.
                utilization_db_data_dic = common_sqlite3.get_sql_table_data(utilization_db_file, utilization_db_conn, utilization_table_name, ['slot', 'cpu', 'mem'], select_condition)

                if utilization_db_data_dic:
                    # Get slot_sum/cpu_sum/mem_sum info.
                    slot_utilization_sum = 0
                    cpu_utilization_sum = 0
                    mem_utilization_sum = 0

                    for (i, slot) in enumerate(utilization_db_data_dic['slot']):
                        slot_utilization_sum += float(utilization_db_data_dic['slot'][i])
                        cpu_utilization_sum += float(utilization_db_data_dic['cpu'][i])
                        mem_utilization_sum += float(utilization_db_data_dic['mem'][i])

                    # Get slot_avg/cpu_avg/mem_avg utilizaiton info.
                    slot_avg_utilization = round(slot_utilization_sum/len(utilization_db_data_dic['slot']), 1)
                    cpu_avg_utilization = round(cpu_utilization_sum/len(utilization_db_data_dic['slot']), 1)
                    mem_avg_utilization = round(mem_utilization_sum/len(utilization_db_data_dic['slot']), 1)

                    utilization_day_dic[utilization_table_name] = {'slot': slot_avg_utilization, 'cpu': cpu_avg_utilization, 'mem': mem_avg_utilization}

        return utilization_day_dic

    def count_utilization_day_info(self):
        """
        Count host resource utilization day average info and save it into sqlite db.
        """
        print('>>> Counting utilization (day average) info ...')

        utilization_day_db_file = str(self.db_path) + '/utilization_day.db'
        (result, utilization_day_db_conn) = common_sqlite3.connect_db_file(utilization_day_db_file, mode='write')

        if result == 'passed':
            utilization_day_table_list = common_sqlite3.get_sql_table_list(utilization_day_db_file, utilization_day_db_conn)
            utilization_day_dic = self.get_utilization_day_info()

            key_list = ['sample_date', 'slot', 'cpu', 'mem']
            key_type_list = ['TEXT PRIMARY KEY', 'TEXT', 'TEXT', 'TEXT']

            for (utilization_day_table_name, utilization_day_table_dic) in utilization_day_dic.items():
                host = re.sub('utilization_', '', utilization_day_table_name)

                print('    Counting utilization (day average) info for host "' + str(host) + '" ...')

                # Clean up utilization database, only keep 3650 items.
                if utilization_day_table_name in utilization_day_table_list:
                    utilization_day_table_count = common_sqlite3.get_sql_table_count(utilization_day_db_file, utilization_day_db_conn, utilization_day_table_name)

                    if utilization_day_table_count != 'N/A':
                        if int(utilization_day_table_count) > 3650:
                            row_id = 'sample_time'
                            begin_line = 0
                            end_line = int(utilization_day_table_count) - 3650

                            print('    Deleting database "' + str(utilization_day_db_file) + '" table "' + str(utilization_day_table_name) + '" ' + str(begin_line) + '-' + str(end_line) + ' lines to only keep 100000 items.')

                            common_sqlite3.delete_sql_table_rows(utilization_day_db_file, utilization_day_db_conn, utilization_day_table_name, row_id, begin_line, end_line)

                # Generate sql table.
                if utilization_day_table_name not in utilization_day_table_list:
                    key_string = common_sqlite3.gen_sql_table_key_string(key_list, key_type_list)
                    common_sqlite3.create_sql_table(utilization_day_db_file, utilization_day_db_conn, utilization_day_table_name, key_string, commit=False)

                    # Insert sql table value.
                    value_list = [self.sample_date, utilization_day_table_dic['slot'], utilization_day_table_dic['cpu'], utilization_day_table_dic['mem']]
                    value_string = common_sqlite3.gen_sql_table_value_string(value_list)
                    common_sqlite3.insert_into_sql_table(utilization_day_db_file, utilization_day_db_conn, utilization_day_table_name, value_string, commit=False)
                else:
                    select_condition = "WHERE sample_date='" + str(self.sample_date) + "'"
                    utilization_day_db_data_dic = common_sqlite3.get_sql_table_data(utilization_day_db_file, utilization_day_db_conn, utilization_day_table_name, ['slot', 'cpu', 'mem'], select_condition)

                    if utilization_day_db_data_dic:
                        # Replace sql table value.
                        set_condition = "SET slot='" + str(utilization_day_table_dic['slot']) + "', cpu='" + str(utilization_day_table_dic['cpu']) + "', mem='" + str(utilization_day_table_dic['mem']) + "'"
                        where_condition = "WHERE sample_date='" + str(self.sample_date) + "'"
                        common_sqlite3.update_sql_table_data(utilization_day_db_file, utilization_day_db_conn, utilization_day_table_name, set_condition, where_condition, commit=False)
                    else:
                        # Insert sql table value.
                        value_list = [self.sample_date, utilization_day_table_dic['slot'], utilization_day_table_dic['cpu'], utilization_day_table_dic['mem']]
                        value_string = common_sqlite3.gen_sql_table_value_string(value_list)
                        common_sqlite3.insert_into_sql_table(utilization_day_db_file, utilization_day_db_conn, utilization_day_table_name, value_string, commit=False)

            utilization_day_db_conn.commit()
            utilization_day_db_conn.close()

    def sampling(self):
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

        if self.utilization_sampling:
            p = Process(target=self.sample_utilization_info)
            p.start()

        p.join()


#################
# Main Function #
#################
def main():
    (job, queue, host, load, user, utilization) = read_args()
    my_sampling = Sampling(job, queue, host, load, user, utilization)
    my_sampling.sampling()


if __name__ == '__main__':
    main()
