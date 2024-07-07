# -*- coding: utf-8 -*-

import os
import sys
import argparse
import datetime
import time
import logging
import csv
import pandas as pd

sys.path.append(str(os.environ['MEM_PREDICTION_INSTALL_PATH']))

from common import common
from common import common_lsf
from common import common_sqlite3
from config import config

logger = common.get_logger(level=logging.INFO)


def read_args():
    """
    Read arguments.
    """
    parser = argparse.ArgumentParser()

    parser.add_argument("-c", "--csv",
                        action="store_true", default=False,
                        help='Sample done job info and save as csv file')
    parser.add_argument("-d", "--db",
                        action="store_true", default=False,
                        help='Sample done job info and save as sqlite')

    args = parser.parse_args()

    return args


class Sampling:
    """
    Sample lsf job information with LSF bjobs commands.
    Save the infomation into sqlite3 DB/csv file.
    """
    def __init__(self):
        # Get sample time.
        self.sample_second = int(time.time())
        self.current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.current_time_start = datetime.datetime.strptime(r'%s 00:00:00' % datetime.datetime.now().strftime('%Y-%m-%d'), '%Y-%m-%d %H:%M:%S')
        self.current_time_end = datetime.datetime.strptime(r'%s 23:59:59' % datetime.datetime.now().strftime('%Y-%m-%d'), '%Y-%m-%d %H:%M:%S')
        self.sample_month = datetime.datetime.today().strftime('%Y_%m')
        self.sample_date = datetime.datetime.today().strftime('%Y%m%d')
        self.sample_time = datetime.datetime.today().strftime('%Y%m%d_%H%M%S')
        self.sample_status_list = ['DONE', 'EXIT']
        self.head_list = ['job_id', 'started_time', 'job_name', 'user', 'status', 'project',
                          'queue', 'cwd', 'command', 'rusage_mem', 'max_mem', 'avg_mem',
                          'finished_time', 'job_description', 'interactive_mode', 'cpu_time', 'span_hosts', 'processors_requested']

        # Create db path.
        self.db_path = str(config.db_path)

        if not os.path.exists(self.db_path):
            try:
                os.makedirs(self.db_path)
            except Exception as error:
                logger.error(r'*Error*: Failed on creating sqlite job db directory %s' % (str(self.db_path)))
                logger.error(str(error))
                sys.exit(1)

    def sampling_lsf_finish_job(self, job_id_list=[]):
        """
        sampling lsf finished infomation and filter valid return
        """
        bjobs_dic = common_lsf.get_bjobs_uf_info('bjobs -u all -a -UF')
        finish_job_dic = {}
        finish_job_set = set(job_id_list)

        for job in bjobs_dic:
            if bjobs_dic[job]['status'].strip() not in self.sample_status_list:
                continue

            if bjobs_dic[job]['job_id'] in finish_job_set:
                continue

            job_finished_time = datetime.datetime.strptime(bjobs_dic[job]['finished_time'], '%a %b %d %H:%M:%S')
            job_finished_time = job_finished_time.replace(year=datetime.datetime.now().year)

            if job_finished_time < self.current_time_start or job_finished_time > self.current_time_end:
                continue

            finish_job_set.add(job)
            finish_job_dic[job] = bjobs_dic[job]

        return finish_job_dic, list(finish_job_dic.keys())

    @common.timer
    def sampling_db(self):
        """
        Sample job info to sqlite
        """
        logger.info('>>> Sampling job info ...')
        job_db_file = os.path.join(self.db_path, r'%s.db' % self.sample_month)
        job_table_name = self.sample_date
        (result, job_db_conn) = common_sqlite3.connect_db_file(job_db_file, mode='write')

        if result != 'passed':
            logger.error("Could not connect to sqlite database, please check!")
            sys.exit(1)

        job_table_list = common_sqlite3.get_sql_table_list(job_db_file, job_db_conn)
        key_list = self.head_list
        key_type_list = ['INT', 'TEXT', 'TEXT', 'TEXT', 'TEXT', 'TEXT', 'TEXT', 'TEXT', 'TEXT', 'TEXT', 'TEXT', 'TEXT', 'TEXT', 'TEXT', 'TEXT', 'TEXT', 'TEXT', 'TEXT']

        # Generate sql table if not exitst.
        if job_table_name not in job_table_list:
            key_string = common_sqlite3.gen_sql_table_key_string(key_list, key_type_list)
            common_sqlite3.create_sql_table(job_db_file, job_db_conn, job_table_name, key_string, commit=False)
            job_id_list = []
        else:
            job_id_list = list(common_sqlite3.get_sql_table_data(job_db_file, job_db_conn, job_table_name, ['job_id']).values())

        bjobs_dic, job_list = self.sampling_lsf_finish_job(job_id_list=job_id_list)

        for job in job_list:
            value_list = []

            for head_item in self.head_list:
                if head_item in bjobs_dic[job]:
                    value_list.append(bjobs_dic[job][head_item])
                else:
                    value_list.append('')

            value_string = common_sqlite3.gen_sql_table_value_string(value_list)

            logger.debug('Sampling for job %s ...' % str(job))

            # If job table (with old data) has been on the job_db_file, drop it.
            if job_table_name in job_table_list:
                common_sqlite3.insert_into_sql_table(job_db_file, job_db_conn, job_table_name, value_string, commit=False)

        job_db_conn.commit()
        job_db_conn.close()
        logger.info('    Done ( %s jobs).' % str(len(job_list)))

    @common.timer
    def sampling_csv(self):
        """
        sampling job infoamtion to csv (job_info_YYYYMMDD.csv)
        """
        logger.info('>>> Sampling job info ...')
        job_info_file = os.path.join(self.db_path, r'job_info_%s.csv' % self.sample_date)

        if os.path.exists(job_info_file):
            df = pd.read_csv(job_info_file)
            job_id_list = df['job_id'].tolist()
        else:
            job_id_list = []

        bjobs_dic, job_list = self.sampling_lsf_finish_job(job_id_list=job_id_list)
        content_list = []

        for job in job_list:
            job_content_list = []

            for head_item in self.head_list:
                if head_item in bjobs_dic[job]:
                    job_content_list.append(bjobs_dic[job][head_item])
                else:
                    job_content_list.append('')

            content_list.append(job_content_list)

        if content_list:
            if not os.path.exists(job_info_file):
                with open(job_info_file, 'w', newline='', encoding='utf-8') as OF:
                    writer = csv.writer(OF)
                    writer.writerow(self.head_list)

            with open(job_info_file, 'a', newline='', encoding='utf-8') as OF:
                writer = csv.writer(OF)
                writer.writerows(content_list)

        logger.info('    Done ( %s jobs).' % str(len(job_list)))


#################
# Main Function #
#################
def main():
    args = read_args()
    my_sampling = Sampling()

    if args.csv:
        my_sampling.sampling_csv()
    elif args.db:
        my_sampling.sampling_db()


if __name__ == '__main__':
    main()
