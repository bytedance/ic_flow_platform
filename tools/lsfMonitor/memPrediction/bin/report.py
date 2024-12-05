# -*- coding: utf-8 -*-
################################
# File Name   : rusage_rpt.py
# Author      : zhangjingwen.silvia
# Created On  : 2023-10-18 15:33:11
# Description :
################################
import os
import re
import sys
import copy
import getpass
import logging
import argparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from pandas.plotting import table
from sklearn.metrics import mean_squared_error as MSE
from sklearn.metrics import mean_absolute_error as MAE
from collections import Counter

sys.path.append(str(os.environ['MEM_PREDICTION_INSTALL_PATH']))

from config import config
from common import common, common_lsf

USER = getpass.getuser()
logger = common.get_logger(level=logging.DEBUG)


def read_args():
    """
    Read in arguments.
    """
    parser = argparse.ArgumentParser()

    rusage_rpt_group = parser.add_argument_group('rusage rpt csv')
    rusage_rpt_group.add_argument('-st', '--start_date', default=(datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'), help='analysis rpt from start date, format: YYYY-mm-dd, default 30days ago')
    rusage_rpt_group.add_argument('-et', '--end_date', default=datetime.now().strftime('%Y-%m-%d'), help='analysis rpt to end date, format: YYYY-mm-dd, default today')
    rusage_rpt_group.add_argument('-db', default=config.db_path, help='directory path including all job data')
    rusage_rpt_group.add_argument('-m', '--memory', action='store_true', default=False, help='memory analysis')
    rusage_rpt_group.add_argument('-c', '--cpu', action='store_true', default=False, help='cpu analysis')

    args = parser.parse_args()

    return args


def merge_data(start_date='', end_date='', csv_path=os.getcwd(), mode='memory'):
    num = 0
    merge_path = '/tmp/memPrediction.' + str(USER) + '.merge.csv'
    unit = common_lsf.get_lsf_unit_for_limits()

    if mode == 'memory':
        original_column_list = ['job_id', 'started_time', 'job_name', 'user', 'status', 'project', 'queue', 'cwd',
                                'command', 'rusage_mem', 'max_mem', 'avg_mem', 'finished_time', 'pre_mem']
    elif mode == 'cpu':
        original_column_list = ['job_id', 'started_time', 'job_name', 'user', 'status', 'project', 'interactive_mode', 'processors_requested',
                                'queue', 'cwd', 'command', 'cpu_time', 'finished_time', 'span_hosts']

    if os.path.exists(csv_path):
        for file in os.listdir(csv_path):
            df = None

            if hasattr(config, 'job_format') and config.job_format.lower() == 'json':
                file_date = datetime.strptime(file, '%Y%m%d')

                if datetime.strptime(start_date, '%Y-%m-%d') <= file_date <= datetime.strptime(end_date, '%Y-%m-%d'):
                    logger.info("reading %s data ..." % file_date)
                    file_path = os.path.join(csv_path, file)
                    df = pd.read_json(file_path, orient='index')
                    df.rename(columns={'index': 'job_id'}, inplace=True)
                    df.reset_index(inplace=True)
            else:
                if my_match := re.match(r'^job_info_(\S+).csv$', file):
                    file_date = datetime.strptime(my_match.group(1), '%Y%m%d')

                    if datetime.strptime(start_date, '%Y-%m-%d') <= file_date <= datetime.strptime(end_date, '%Y-%m-%d'):
                        logger.info("reading %s data ..." % file_date)
                        file_path = os.path.join(csv_path, file)
                        df = pd.read_csv(file_path)

            if df is not None:
                df = df.drop_duplicates(subset=['job_id'], keep='first')

                if mode == 'memory':
                    if 'job_description' in df.columns:
                        df['pre_mem'] = df['job_description'].apply(lambda x: get_mem_predict_value(x, unit=unit))
                    else:
                        df['pre_mem'] = 0.0

                df = df[original_column_list]

                if 'status' in df.columns:
                    df = df[df['status'] == 'DONE']

                if num == 0:
                    df.to_csv(merge_path, encoding='utf_8_sig', index=False)
                else:
                    df.to_csv(merge_path, encoding='utf_8_sig', index=False, header=False, mode='a+')

                num += 1

    if not os.path.exists(merge_path):
        logger.error("Could not find merge data result, please check data source!")
        sys.exit(1)
    else:
        total_df = pd.read_csv(merge_path)
        total_df = total_df.drop_duplicates(subset=['job_id'], keep='first')
        os.remove(merge_path)

    logger.debug("dataframe: %s\n" % str(total_df.describe()))

    return total_df


def get_mem_predict_value(job_description, unit='MB'):
    mem_predict_value = 0

    if job_description:
        if my_match := re.match(r'.*ALLOC_MEMORY_USER=memoryPrediction\(.*=(\d+(\.\d+)*)%s\)' % unit, str(job_description)):
            mem_predict_value = float(my_match.group(1))

    return mem_predict_value


class MemoryReport:
    def __init__(self, df, start_date, end_date):
        self.df = df
        self.start_date, self.end_date = start_date, end_date
        self.bins = [-float('inf'), 1, 2, 4, 8, 16, 32, 64, 128, 256, 512, float('inf')]
        self.tolerance_list = [4, 3, 2, 1, 1, 0.5, 0.5, 0.3, 0.3, 0.3, 0.3]
        self.x = [i for i in range(len(self.bins) - 1)]
        self.x_label = []

        for i in range(len(self.bins) - 1):
            self.x_label.append(r"%s-%s" % (str(self.bins[i]), str(self.bins[i + 1])))

        # convert memory data
        self.convert_memory_infomation()
        self.time_process()
        self.user_df, self.over_rusage_top_user_list = self.data_process()
        self.picture_dir = os.path.join(config.report_path, 'pictures_memory/%s_%s/' % (start_date, end_date))
        self.table_dir = os.path.join(config.report_path, 'tables_memory/%s_%s/' % (start_date, end_date))

        if not os.path.exists(self.picture_dir):
            try:
                os.makedirs(self.picture_dir)
            except Exception as error:
                logger.error(r'*Error*: Failed on creating report picture directory %s' % (str(self.picture_dir)))
                logger.error(str(error))
                sys.exit(1)

        if not os.path.exists(self.table_dir):
            try:
                os.makedirs(self.table_dir)
            except Exception as error:
                logger.error(r'*Error*: Failed on creating report picture directory %s' % (str(self.table_dir)))
                logger.error(str(error))
                sys.exit(1)

        self.picture_dic = {}
        self.table_dic = {}

    def convert_memory_infomation(self):
        memory_item_list = ['max_mem', 'rusage_mem', 'pre_mem']

        for mem_item in memory_item_list:
            if mem_item in self.df.columns:
                self.df[mem_item] = common.memory_unit_to_gb(self.df[mem_item], unit='MB')
                self.df[mem_item] = self.df[mem_item].fillna(0)
                self.df[r'%s_interval' % mem_item] = pd.cut(self.df[mem_item].values.reshape(-1), self.bins)
            else:
                logger.error("Could not find column %s in dataframe, please check!" % mem_item)
                sys.exit(1)

        logger.debug("self.df.columns : %s" % str(self.df.columns))

    def time_process(self):
        try:
            self.df["run_time"] = pd.to_datetime(self.df["finished_time"], format="%a %b %d %H:%M:%S", errors='coerce') - pd.to_datetime(self.df["started_time"], format="%a %b %d %H:%M:%S", errors='coerce')
            self.df["run_time"] = pd.to_timedelta(self.df["run_time"])
            self.df["total_hours"] = self.df["run_time"].dt.total_seconds() / 3600
        except ValueError:
            self.df["run_time"] = 0
            self.df["total_hours"] = 1 / 3600

        self.df['run_time'].fillna(0, inplace=True)
        self.df['total_hours'].fillna(1 / 3600, inplace=True)

        logger.debug("df runtime: \n %s \n df total_hours \n  %s" % (str(self.df["run_time"]), str(self.df["total_hours"])))

    def data_process(self):
        pre_df = copy.deepcopy(self.df)
        pre_df = pre_df[pre_df['status'].isin(['DONE', 'EXIT'])]

        pre_df["rusage_diff_mem"] = pre_df["rusage_mem"] - pre_df["max_mem"]
        pre_df["over_diff_mem"] = pre_df["rusage_diff_mem"].apply(lambda x: 0 if x < 0 else x)
        pre_df["under_diff_mem"] = pre_df["rusage_diff_mem"].apply(lambda x: 0 if x > 0 else x)
        pre_df["under_diff_mem"] = pre_df["under_diff_mem"].abs()
        pre_df["tolerance_rusage_mem"] = pre_df.apply(lambda row: self.gen_tolerance_over_rusage(row["max_mem"], row["over_diff_mem"]), axis=1)
        pre_df["over_total_mem_hours"] = pre_df["over_diff_mem"] * pre_df["total_hours"]
        pre_df["under_total_mem_hours"] = pre_df["under_diff_mem"] * pre_df["total_hours"]

        # over_rusage_sum
        over_sum_by_user = pre_df["over_diff_mem"].groupby(pre_df["user"]).sum()
        user_rusage_data = pd.DataFrame()
        user_rusage_data["over_rusage_sum"] = over_sum_by_user
        user_rusage_data["under_rusage_sum"] = pre_df["under_diff_mem"].groupby(pre_df["user"]).sum()

        # over_rusage_num
        over_user_size = pre_df.query("rusage_diff_mem > 0")["rusage_diff_mem"].groupby(pre_df["user"]).count()
        user_rusage_data["over_rusage_num"] = over_user_size
        user_rusage_data["under_rusage_num"] = pre_df.query("rusage_diff_mem < 0")["rusage_diff_mem"].groupby(pre_df["user"]).count()
        user_rusage_data["tolerance_over_rusage_sum"] = pre_df["tolerance_rusage_mem"].groupby(pre_df["user"]).sum()
        user_rusage_data["max_mem_sum"] = pre_df["max_mem"].groupby(pre_df["user"]).sum()
        user_rusage_data["max_mem_mean"] = pre_df["max_mem"].groupby(pre_df["user"]).mean()
        user_rusage_data["max_mem_std"] = pre_df["max_mem"].groupby(pre_df["user"]).std()
        user_rusage_data["3td_mean_mem"] = user_rusage_data["max_mem_mean"] + user_rusage_data["max_mem_std"] * 5
        user_rusage_data["95_quantile_mem"] = pre_df["max_mem"].groupby(pre_df["user"]).quantile(0.98)
        user_rusage_data["rusage_mem_mean"] = pre_df["rusage_mem"].groupby(pre_df["user"]).mean()
        user_rusage_data["over_mem_hours"] = pre_df["over_total_mem_hours"].groupby(pre_df["user"]).sum()
        user_rusage_data["over_mem_hours"] = user_rusage_data["over_mem_hours"] / 1024
        user_rusage_data["under_mem_hours"] = pre_df["under_total_mem_hours"].groupby(pre_df["user"]).sum()
        user_rusage_data["under_mem_hours"] = user_rusage_data["under_mem_hours"] / 1024
        user_rusage_data["job_hours_mean"] = pre_df["total_hours"].groupby(pre_df["user"]).mean()
        user_rusage_data["job_hours_sum"] = pre_df["total_hours"].groupby(pre_df["user"]).sum()

        # over_rusage_mean
        user_rusage_data["over_rusage_mean"] = pre_df["over_diff_mem"].groupby(pre_df["user"]).mean()
        user_rusage_data["over_rusage_mean_rate"] = (pre_df["over_diff_mem"] / pre_df["max_mem"] * 100).groupby(pre_df["user"]).mean()
        user_rusage_data["under_rusage_mean"] = pre_df["under_diff_mem"].groupby(pre_df["user"]).mean()
        user_rusage_data["under_rusage_mean_rate"] = (pre_df["under_diff_mem"] / pre_df["max_mem"] * 100).groupby(pre_df["user"]).mean()

        count_df = pre_df["status"].groupby(pre_df["user"]).value_counts().unstack(fill_value=0).fillna(0).reindex(columns=['DONE', 'EXIT'], fill_value=0)
        count_df.columns = ['done_count', 'exit_count']
        user_rusage_data['exit_count'] = count_df['exit_count']
        user_rusage_data['done_count'] = count_df['done_count']
        user_rusage_data['job_num'] = pre_df['job_id'].groupby(pre_df["user"]).count()
        user_rusage_data['exit_rate'] = user_rusage_data['exit_count'] / user_rusage_data['job_num'] * 100
        user_rusage_data['under_rusage_rate'] = user_rusage_data["under_rusage_num"] / user_rusage_data['job_num'] * 100

        over_user_list = user_rusage_data.sort_values("tolerance_over_rusage_sum", inplace=False, ascending=False).head(15).index

        return user_rusage_data, over_user_list

    def analysis(self):
        # analysis rusage
        # overall histogram
        self.draw_overall_histogram()

        # overal scatter
        self.draw_overall_scatter()

        # overall difference sum between rusage memory and max mem
        self.draw_difference_sum_histogram()

        # overall difference value between rusage memory and max mem
        self.draw_difference_value_histogram()

        # overall difference rate between rusage memory and max mem
        self.draw_difference_rate_histogram()

        # overall mem effienct
        self.draw_overall_mem_efficient()

        # non-rusage number histogram
        self.draw_non_rusage_mem_histogram()

        # total-over/under rusage memory
        self.write_total_over_rusage_mem_table()
        self.write_total_under_rusage_mem_table()
        self.draw_user_tolerance_rusage_pie_chart()
        self.write_user_tolerance_rusage_pie_table()
        self.draw_under_rusage_exit_histogram()
        self.write_under_rusage_exit_table()

        # analysis pre_mem
        self.write_error_table()
        self.write_predict_memory_table()
        self.draw_pre_mem_scatter()
        self.draw_pre_difference_value_histogram()
        self.draw_pre_difference_rate_histogram()
        self.draw_pre_difference_sum_histogram()
        self.write_user_tolerance_rusage_hour_pie_table()
        self.draw_user_tolerance_rusage_hour_pie_chart()
        self.write_user_under_rusage_hour_pie_table()
        self.draw_user_under_rusage_hour_pie_chart()
        self.over_rusage_user_histogram()
        self.under_rusage_user_histogram()

    def draw_overall_histogram(self):
        picture_dir = os.path.join(self.picture_dir, 'overall_histogram.png')
        lefts = range(len(self.x))
        plt.figure(figsize=(9, 9))
        plt.xticks(self.x, self.x_label)

        bar1 = plt.bar([i - 0.2 for i in self.x], self.df['max_mem_interval'].value_counts(), width=0.4, label="true max", color="green")
        bar2 = plt.bar([i + 0.2 for i in lefts], self.df['rusage_mem_interval'].value_counts(), width=0.4, label="human pre", color="blue")
        plt.xlabel("memory interval(GB)")
        plt.ylabel("job number")

        for rect in bar1:
            height = rect.get_height()
            plt.text(rect.get_x() + rect.get_width() / 2, height + 3, str(height), ha="center", va="bottom")

        for rect in bar2:
            height = rect.get_height()
            plt.text(rect.get_x() + rect.get_width() / 2, height + 3, str(height), ha="center", va="bottom")

        plt.legend()
        plt.savefig(picture_dir)
        plt.cla()

        self.picture_dic['$OVERALL_HISTOGRAM'] = picture_dir

    def draw_overall_scatter(self):
        picture_dic = os.path.join(self.picture_dir, 'overall_scatter.png')
        plt.figure(figsize=(9, 9))
        plt.scatter(self.df["max_mem"], self.df["rusage_mem"])

        sx = np.arange(0, 2000, 0.1)

        for t in sx:
            sy = sx

        plt.plot(sx, sy, label="standard", color="green")
        plt.xlabel("max mem(GB)")
        plt.ylabel("rusage_mem(GB)")
        plt.savefig(picture_dic)
        plt.cla()

        self.picture_dic['$OVERALL_SCATTER'] = picture_dic

    def draw_pre_mem_scatter(self):
        picture_dic = os.path.join(self.picture_dir, 'ml_overall_scatter.png')
        plt.figure(figsize=(9, 9))
        ml_df = self.df[self.df['pre_mem'] != 0]

        if ml_df.empty:
            logger.error('Could not find memory prediction result, ignore ml_overall_scatter.png.')
            return

        plt.scatter(ml_df["max_mem"], ml_df["rusage_mem"])

        sx = np.arange(0, (ml_df['max_mem']).max() * 1.2, 0.1)

        for t in sx:
            sy = sx

        plt.plot(sx, sy, label="standard", color="green")
        plt.xlabel("max mem(GB)")
        plt.ylabel("pre_mem(GB)")
        plt.savefig(picture_dic)
        plt.cla()

        self.picture_dic['$ML_PRE_SCATTER'] = picture_dic

    def draw_difference_sum_histogram(self):
        picture_dic = os.path.join(self.picture_dir, 'rusage_and_max_difference_sum.png')
        rusage_sum_diff = (self.df["rusage_mem"] - self.df["max_mem"]).groupby(self.df["max_mem_interval"]).sum()
        rusage_sum_diff = [round(value / 1024, 2) for value in rusage_sum_diff]
        colors = ["orange" if value > 0 else "green" for value in rusage_sum_diff]

        plt.figure(figsize=(9, 9))
        plt.xticks(self.x, self.x_label)

        bar = plt.bar(self.x, rusage_sum_diff, alpha=0.8, color=colors)
        plt.xlabel("true max memory interval(TB)")
        plt.ylabel("rusage difference sum in value(GB)")

        for rect in bar:
            height = rect.get_height()
            plt.text(rect.get_x() + rect.get_width() / 2, height + 3, str(height), ha="center", va="bottom")

        plt.savefig(picture_dic)
        plt.cla()

        self.picture_dic['$DIFFERENCE_SUM_HISTOGRAM'] = picture_dic

    def draw_pre_difference_sum_histogram(self):
        picture_dic = os.path.join(self.picture_dir, 'pre_and_max_difference_sum.png')
        ml_df = self.df[self.df['pre_mem'] != 0]
        rusage_sum_diff = (ml_df["rusage_mem"] - ml_df["max_mem"]).groupby(ml_df["max_mem_interval"]).sum()
        rusage_sum_diff = [round(value / 1024, 2) for value in rusage_sum_diff]
        colors = ["orange" if value > 0 else "green" for value in rusage_sum_diff]

        plt.figure(figsize=(9, 9))
        plt.xticks(self.x, self.x_label)

        bar = plt.bar(self.x, rusage_sum_diff, alpha=0.8, color=colors)
        plt.xlabel("true max memory interval(TB)")
        plt.ylabel("predict difference sum in value(GB)")

        for rect in bar:
            height = rect.get_height()
            plt.text(rect.get_x() + rect.get_width() / 2, height + 3, str(height), ha="center", va="bottom")

        plt.savefig(picture_dic)
        plt.cla()

        self.picture_dic['$PRE_DIFFERENCE_SUM_HISTOGRAM'] = picture_dic

    def draw_difference_value_histogram(self):
        picture_dir = os.path.join(self.picture_dir, 'rusage_and_max_difference_value.png')
        rusage_avg_diff = (self.df["rusage_mem"] - self.df["max_mem"]).groupby(self.df["max_mem_interval"]).mean()
        rusage_avg_diff = [round(value, 2) for value in rusage_avg_diff]
        colors = ["orange" if value > 0 else "green" for value in rusage_avg_diff]

        plt.figure(figsize=(9, 9))
        plt.xticks(self.x, self.x_label)

        bar = plt.bar(self.x, rusage_avg_diff, alpha=0.8, color=colors)
        plt.xlabel("true max memory interval(GB)")
        plt.ylabel("rusage difference in value(GB)")

        for rect in bar:
            height = rect.get_height()
            plt.text(rect.get_x() + rect.get_width() / 2, height + 3, str(height), ha="center", va="bottom")

        plt.savefig(picture_dir)
        plt.cla()

        self.picture_dic['$DIFFERENCE_VALUE_HISTOGRAM'] = picture_dir

    def draw_pre_difference_value_histogram(self):
        picture_dir = os.path.join(self.picture_dir, 'pre_and_max_difference_value.png')
        ml_df = self.df[self.df['pre_mem'] != 0]
        rusage_avg_diff = (ml_df["pre_mem"] - ml_df["max_mem"]).groupby(ml_df["max_mem_interval"]).mean()
        rusage_avg_diff = [round(value, 2) for value in rusage_avg_diff]
        colors = ["orange" if value > 0 else "green" for value in rusage_avg_diff]

        plt.figure(figsize=(9, 9))
        plt.xticks(self.x, self.x_label)

        bar = plt.bar(self.x, rusage_avg_diff, alpha=0.8, color=colors)
        plt.xlabel("true max memory interval(GB)")
        plt.ylabel("predict difference in value(GB)")

        for rect in bar:
            height = rect.get_height()
            plt.text(rect.get_x() + rect.get_width() / 2, height + 3, str(height), ha="center", va="bottom")

        plt.savefig(picture_dir)
        plt.cla()

        self.picture_dic['$PRE_DIFFERENCE_VALUE_HISTOGRAM'] = picture_dir

    def draw_difference_rate_histogram(self):
        picture_dir = os.path.join(self.picture_dir, 'rusage_and_max_difference_rate.png')
        rusage_avg_diff_rate = list(((self.df['rusage_mem'] - self.df["max_mem"]) / self.df["max_mem"] * 100).groupby(self.df['max_mem_interval']).mean())
        colors = ["orange" if value > 0 else "green" for value in rusage_avg_diff_rate]
        rusage_avg_diff_rate = [round(value, 0) for value in rusage_avg_diff_rate]

        plt.figure(figsize=(9, 9))
        bar = plt.bar(self.x, rusage_avg_diff_rate, alpha=0.8, color=colors)
        plt.xlabel("true max memory interval")
        plt.ylabel("rusage difference in rate(%)")

        plt.xticks(self.x, self.x_label)

        for rect in bar:
            height = rect.get_height()
            plt.text(rect.get_x() + rect.get_width() / 2, height + 3, str(height), ha="center", va="bottom")

        plt.savefig(picture_dir)
        plt.cla()

        self.picture_dic['$DIFFERENCE_RATE_HISTOGRAM'] = picture_dir

    def draw_pre_difference_rate_histogram(self):
        picture_dir = os.path.join(self.picture_dir, 'pre_and_max_difference_rate.png')
        ml_df = self.df[self.df['pre_mem'] != 0]
        rusage_avg_diff_rate = list(((ml_df['pre_mem'] - ml_df["max_mem"]) / ml_df["max_mem"] * 100).groupby(ml_df['max_mem_interval']).mean())
        colors = ["orange" if value > 0 else "green" for value in rusage_avg_diff_rate]
        rusage_avg_diff_rate = [round(value, 0) for value in rusage_avg_diff_rate]

        plt.figure(figsize=(9, 9))
        bar = plt.bar(self.x, rusage_avg_diff_rate, alpha=0.8, color=colors)
        plt.xlabel("true max memory interval")
        plt.ylabel("predict difference in rate(%)")
        plt.xticks(self.x, self.x_label)

        for rect in bar:
            height = rect.get_height()
            plt.text(rect.get_x() + rect.get_width() / 2, height + 3, str(height), ha="center", va="bottom")

        plt.savefig(picture_dir)
        plt.cla()

        self.picture_dic['$PRE_DIFFERENCE_RATE_HISTOGRAM'] = picture_dir

    def draw_overall_mem_efficient(self):
        # mem efficient
        picture_dir = os.path.join(self.picture_dir, 'rusage_efficienct.png')
        efficient_list = (self.df["rusage_mem"] / self.df["max_mem"]).groupby(self.df['max_mem_interval']).mean()
        efficient_list = [round(value, 2) for value in efficient_list]
        colors = ["blue" if value > 1 else "orange" for value in efficient_list]

        plt.figure(figsize=(9, 9))
        diff_bar = plt.bar(self.x, efficient_list, alpha=0.8, color=colors)
        plt.xticks(self.x, self.x_label)
        plt.xlabel("true max memory interval")
        plt.ylabel("rusage mem / true mem")
        plt.axhline(y=1, color="red")

        for rect in diff_bar:
            height = rect.get_height()
            plt.text(rect.get_x() + rect.get_width() / 2, height + 3, str(height), ha="center", va="bottom")

        plt.savefig(picture_dir)
        plt.cla()

        self.picture_dic['$MEM_EFFICIENT_INVERSE'] = picture_dir

    def draw_non_rusage_mem_histogram(self):
        picture_dir = os.path.join(self.picture_dir, 'non_rusage_job_count.png')
        non_rusage_list = (self.df.groupby(self.df['max_mem_interval']))['rusage_mem'].apply(lambda x: (x <= 0).sum())

        plt.figure(figsize=(9, 9))
        diff_bar = plt.bar(self.x, non_rusage_list, alpha=0.8)
        plt.xticks(self.x, self.x_label)
        plt.xlabel("true max memory interval")
        plt.ylabel("non-rusage count")

        for rect in diff_bar:
            height = rect.get_height()
            plt.text(rect.get_x() + rect.get_width() / 2, height + 3, str(height), ha="center", va="bottom")

        plt.savefig(picture_dir)
        plt.cla()

        self.picture_dic['$NON_RUSAGE_MEMORY_HISTOGRAM'] = picture_dir

    def gen_tolerance_over_rusage(self, max_mem, over_rusage_mem):
        for n in range(len(self.tolerance_list)):
            lower_limit = 2 ** n
            upper_limit = 2 ** (n + 1)

            if lower_limit <= max_mem <= upper_limit:
                tolerance = self.tolerance_list[n]

                if ((1 + tolerance) * max_mem) < over_rusage_mem:
                    return over_rusage_mem

        return 0

    def draw_user_rusage_data_mix_picture(self):
        picture_dir = os.path.join(self.picture_dir, 'rusage_user_overall.png')
        user_label = [i + 1 for i in range(len(self.over_rusage_top_user_list))]
        over_sum_list = [round(value / 1024, 0) for value in self.user_df.loc[self.over_rusage_top_user_list]["over_rusage_sum"]]
        over_mean_list = [round(value, 0) for value in self.user_df.loc[self.over_rusage_top_user_list]["over_rusage_mean"]]
        over_job_list = [value for value in self.user_df.loc[self.over_rusage_top_user_list]["over_rusage_num"]]
        width = 0.4
        x1_list = []
        x2_list = []
        x3_list = []

        for i in range(len(user_label)):
            x1_list.append(i)
            x2_list.append(i + width)
            x3_list.append(i + width)

        plt.figure(figsize=(9, 9))
        fig, ax1 = plt.subplots()

        ax1.set_ylabel('Over Rusage Sum(TB)')
        ax1.set_ylim(0, max(over_sum_list) * 1.1)
        ax1.ticklabel_format(style='plain')

        ax1.bar(x1_list, over_sum_list, width=width, color='tab:blue', align='edge', label="sum")
        ax1.set_xticklabels(ax1.get_xticklabels())
        ax1.legend(loc="upper left")

        ax2 = ax1.twinx()
        ax2.set_ylabel('Over Rusage Mean(GB)')
        ax2.set_ylim(0, max(over_mean_list) * 1.1)
        ax2.bar(x2_list, over_mean_list, width=width, color='lightseagreen', align='edge', tick_label=user_label, label="mean")
        ax2.legend(loc="upper right")

        ax3 = ax1.twinx()
        ax3.plot(x3_list, over_job_list, color="red", label="num")
        ax3.set_ylim(0, max(over_job_list) * 1.1)
        ax3.axes.get_yaxis().set_visible(False)
        ax3.legend(loc="center right")

        for a, b in zip(x3_list, over_job_list):
            plt.text(a, b, int(b), ha="center", va="bottom")

        plt.tight_layout()
        plt.savefig(picture_dir)
        plt.cla()

        self.picture_dic['$RUASGE_USER_MIX'] = picture_dir

    def draw_user_rusage_table(self):
        picture_dir = os.path.join(self.picture_dir, 'rusage_user_table.png')
        table_user_df = self.user_df.loc[self.over_rusage_top_user_list]
        table_user_df["index"] = [i + 1 for i in range(len(self.over_rusage_top_user_list))]
        table_user_df["over_rusage_sum(TB)"] = table_user_df["over_rusage_sum"] / 1024
        table_user_df["over_rusage_mean(GB)"] = table_user_df["over_rusage_mean"]
        ordered_column_list = ["index", "over_rusage_sum(TB)", "over_rusage_mean(GB)", "over_rusage_num"]
        table_user_df = table_user_df[ordered_column_list]
        fig = plt.figure(figsize=(12, 10))
        ax = fig.add_subplot(111, frame_on=False)
        ax.xaxis.set_visible(False)
        ax.yaxis.set_visible(False)

        table(ax, table_user_df.round(0), loc='center')
        plt.savefig(picture_dir)
        plt.cla()

        self.picture_dic['$RUASGE_USER_TABLE'] = picture_dir

    def draw_user_rusage_pie_chart(self):
        picture_dir = os.path.join(self.picture_dir, 'rusage_user_pie_chart.png')
        top10_user_data = self.user_df.sort_values("over_rusage_sum", inplace=False, ascending=False).head(8)
        top10_user_data.loc["others"] = self.user_df["over_rusage_sum"].sum() - top10_user_data["over_rusage_sum"].sum()

        plt.figure(figsize=(9, 9))
        plt.pie(top10_user_data["over_rusage_sum"], labels=top10_user_data.index, autopct='%1.1f%%', pctdistance=0.9)
        plt.legend(loc="center right")
        plt.savefig(picture_dir)
        plt.cla()

        self.picture_dic['$RUSAGE_USER_PIE'] = picture_dir

    def write_user_rusage_pie_table(self):
        table_name = 'user_rusage_pie_chart.table'
        table_dir = os.path.join(self.table_dir, table_name)
        self.user_df["pie_chart_rate"] = (self.user_df["over_rusage_sum"] / (self.user_df["over_rusage_sum"].sum()) * 100).apply(lambda x: f'{x:.2f}%')
        top10_user_data = self.user_df.sort_values("over_rusage_sum", inplace=False, ascending=False).head(10).index
        user_df = self.user_df.rename(columns={"over_rusage_sum": "over_rusage_sum(GB)", "over_rusage_mean": "over_rusage_mean(GB)"})
        show_column_list = ["over_rusage_sum(GB)", "over_rusage_mean(GB)", "pie_chart_rate", "over_rusage_mean_rate", "over_rusage_num", "3td_mean_mem", "95_quantile_mem"]

        with open(table_dir, 'w') as tf:
            tf.write(user_df.loc[top10_user_data, show_column_list].to_markdown(index=True))

        self.table_dic["$ABSOLUTELY_PIE_CHART_TABLE"] = table_dir

    def write_user_tolerance_rusage_pie_table(self):
        table_name = 'tolerance_user_rusage_pie_chart.md'
        table_dir = os.path.join(self.table_dir, table_name)
        self.user_df["pie_chart_rate"] = (self.user_df["tolerance_over_rusage_sum"] / (self.user_df["tolerance_over_rusage_sum"].sum()) * 100).apply(lambda x: f'{x:.2f}%')
        top_user_data = self.user_df.sort_values("tolerance_over_rusage_sum", inplace=False, ascending=False).head(30).index
        table_user_df = self.user_df.loc[top_user_data]
        table_user_df["index"] = [i + 1 for i in range(len(top_user_data))]
        table_user_df["over_rusage_sum(TB)"] = table_user_df["over_rusage_sum"] / 1024
        table_user_df["not_tolerance_over_rusage_sum(TB)"] = table_user_df["tolerance_over_rusage_sum"] / 1024
        table_user_df = table_user_df.rename(columns={"over_rusage_mean_rate": "over_rusage_mean_rate(%)", "over_rusage_mean": "over_rusage_mean(GB)"})
        show_column_list = ["index", "pie_chart_rate", "over_rusage_sum(TB)", "not_tolerance_over_rusage_sum(TB)", "over_rusage_mean(GB)",
                            "max_mem_mean", "rusage_mem_mean", "over_rusage_num", "3td_mean_mem", "95_quantile_mem"]

        with open(table_dir, 'w') as tf:
            tf.write(table_user_df.loc[top_user_data, show_column_list].to_markdown(index=True))

        self.table_dic["$TOLERANCE_PIE_CHART_TABLE"] = table_dir

    def write_user_tolerance_rusage_hour_pie_table(self):
        table_name = 'mem_hours_user_pie_chart.md'
        table_dir = os.path.join(self.table_dir, table_name)
        self.user_df["mem_hour_rate"] = (self.user_df["over_mem_hours"] / (self.user_df["over_mem_hours"].sum()) * 100).apply(lambda x: f'{x:.2f}%')
        top_user_data = self.user_df.sort_values("over_mem_hours", inplace=False, ascending=False).head(15).index
        table_user_df = self.user_df.loc[top_user_data]
        table_user_df["index"] = [i + 1 for i in range(len(top_user_data))]
        table_user_df["over_rusage_sum(TB)"] = table_user_df["over_rusage_sum"] / 1024
        table_user_df["not_tolerance_over_rusage_sum(TB)"] = table_user_df["tolerance_over_rusage_sum"] / 1024
        table_user_df = table_user_df.rename(
            columns={"over_rusage_mean_rate": "over_rusage_mean_rate(%)",
                     "over_rusage_mean": "over_rusage_mean(GB)",
                     "over_mem_hours": "over_mem_hours(TB*H)"})
        show_column_list = ["index", "mem_hour_rate", "over_rusage_mean(GB)", "over_mem_hours(TB*H)",
                            "not_tolerance_over_rusage_sum(TB)", "job_hours_mean",
                            "max_mem_mean", "rusage_mem_mean", "over_rusage_num", "95_quantile_mem"]

        with open(table_dir, 'w') as tf:
            tf.write(table_user_df.loc[top_user_data, show_column_list].to_markdown(index=True))

        self.table_dic["$MEM_RUNTIME_TABLE"] = table_dir

    def draw_user_tolerance_rusage_hour_pie_chart(self):
        picture_dir = os.path.join(self.picture_dir, 'mem_hours_user_pie_chart.png')
        top10_user_data = self.user_df.sort_values("over_mem_hours", inplace=False, ascending=False).head(5)
        logger.info(str(top10_user_data))
        logger.info("total: \n %s \n 10 \n %s \n" % (str(self.user_df["over_mem_hours"].sum()), str(top10_user_data["over_mem_hours"].sum())))
        top10_user_data.loc["others"] = self.user_df["over_mem_hours"].sum() - top10_user_data["over_mem_hours"].sum()

        plt.figure(figsize=(9, 9))
        plt.pie(top10_user_data["over_mem_hours"], labels=top10_user_data.index, autopct='%1.1f%%', pctdistance=0.9)
        plt.legend(loc="center right")
        plt.savefig(picture_dir)
        plt.cla()

        self.picture_dic['$MEM_RUNTIME_PIE'] = picture_dir

    def write_user_under_rusage_hour_pie_table(self):
        table_name = 'under_mem_hours_user_pie_chart.md'
        table_dir = os.path.join(self.table_dir, table_name)
        self.user_df["mem_hour_rate"] = (self.user_df["under_mem_hours"] / (self.user_df["under_mem_hours"].sum()) * 100).apply(lambda x: f'{x:.2f}%')
        top_user_data = self.user_df.sort_values("under_mem_hours", inplace=False, ascending=False).head(15).index
        table_user_df = self.user_df.loc[top_user_data]
        table_user_df["index"] = [i + 1 for i in range(len(top_user_data))]
        table_user_df["under_rusage_sum(TB)"] = table_user_df["under_rusage_sum"] / 1024
        table_user_df = table_user_df.rename(
            columns={"under_rusage_mean_rate": "under_rusage_mean_rate(%)",
                     "under_rusage_mean": "under_rusage_mean(GB)",
                     "under_mem_hours": "under_mem_hours(TB*H)"})
        show_column_list = ["index",
                            "mem_hour_rate",
                            "under_rusage_mean(GB)",
                            "under_mem_hours(TB*H)",
                            "job_hours_mean",
                            "max_mem_mean",
                            "rusage_mem_mean",
                            "under_rusage_num",
                            "95_quantile_mem"]

        with open(table_dir, 'w') as tf:
            tf.write(table_user_df.loc[top_user_data, show_column_list].to_markdown(index=True))

        self.table_dic["$MEM_RUNTIME_UNDER_TABLE"] = table_dir

    def draw_user_under_rusage_hour_pie_chart(self):
        picture_dir = os.path.join(self.picture_dir, 'under_mem_hours_user_pie_chart.png')
        top10_user_data = self.user_df.sort_values("under_mem_hours", inplace=False, ascending=False).head(7)
        logger.info(str(top10_user_data))
        logger.info("total: \n %s \n 10 \n %s \n" % (str(self.user_df["over_mem_hours"].sum()), str(top10_user_data["under_mem_hours"].sum())))
        top10_user_data.loc["others"] = self.user_df["under_mem_hours"].sum() - top10_user_data["under_mem_hours"].sum()

        plt.figure(figsize=(9, 9))
        plt.pie(top10_user_data["under_mem_hours"], labels=top10_user_data.index, autopct='%1.1f%%', pctdistance=0.9)
        plt.legend(loc="center right")
        plt.savefig(picture_dir)
        plt.cla()

        self.picture_dic['$MEM_RUNTIME_UNDER_PIE'] = picture_dir

    def write_total_over_rusage_mem_table(self):
        table_name = 'total_over_rusage_mem.table'
        table_dir = os.path.join(self.table_dir, table_name)
        total = round(self.user_df["over_rusage_sum"].sum() / 1024, 4)

        with open(table_dir, 'w') as tf:
            content = '%s' % str(total)
            tf.write(content)

        self.table_dic["$TOTAL_OVER_RUSAGE_MEMORY_TABLE"] = table_dir

    def write_total_under_rusage_mem_table(self):
        table_name = 'total_under_rusage_mem.table'
        table_dir = os.path.join(self.table_dir, table_name)
        total = round(self.user_df["under_rusage_sum"].sum() / 1024, 4)

        with open(table_dir, 'w') as tf:
            content = '%s' % str(total)
            tf.write(content)

        self.table_dic["$TOTAL_UNDER_RUSAGE_MEMORY_TABLE"] = table_dir

    def draw_user_tolerance_rusage_pie_chart(self):
        picture_dir = os.path.join(self.picture_dir, 'tolerance_rusage_user_pie_chart.png')

        top10_user_data = self.user_df.sort_values("tolerance_over_rusage_sum", inplace=False, ascending=False).head(10)
        top10_user_data.loc["others"] = self.user_df["tolerance_over_rusage_sum"].sum() - top10_user_data["tolerance_over_rusage_sum"].sum()

        plt.figure(figsize=(9, 9))
        plt.pie(top10_user_data["tolerance_over_rusage_sum"], labels=top10_user_data.index, autopct='%1.1f%%', pctdistance=0.9)
        plt.legend(loc="center right")
        plt.savefig(picture_dir)
        plt.cla()

        self.picture_dic['$TOLERANCE_RUSAGE_USER_PIE'] = picture_dir

    def write_under_rusage_exit_table(self):
        table_name = 'user_under_rusage_exit.md'
        table_dir = os.path.join(self.table_dir, table_name)
        self.user_df["sort_name"] = self.user_df["exit_rate"] * self.user_df["under_rusage_mean_rate"]
        exit_user_df = self.user_df.sort_values("sort_name", inplace=False, ascending=False).head(15)
        exit_user_list = exit_user_df.index
        exit_user_df = exit_user_df.rename(columns={"under_rusage_sum": "under_rusage_sum(GB)", "under_rusage_mean": "under_rusage_mean(GB)"})
        exit_user_df["index"] = [i + 1 for i in range(len(exit_user_list))]
        show_column_list = ["index", "under_rusage_mean_rate", "exit_rate", "under_rusage_sum(GB)", "under_rusage_rate", "under_rusage_mean(GB)"]

        with open(table_dir, 'w') as tf:
            tf.write(exit_user_df.loc[exit_user_list, show_column_list].to_markdown(index=True))

        self.table_dic["$UNDER_RUSAGE_TABLE"] = table_dir

    def draw_under_rusage_exit_histogram(self):
        picture_dir = os.path.join(self.picture_dir, 'under_exit_histogram.png')
        self.user_df["sort_name"] = self.user_df["exit_rate"] * self.user_df["under_rusage_mean_rate"]
        exit_user_df = self.user_df.sort_values("sort_name", inplace=False, ascending=False).head(15)
        exit_user_list = exit_user_df.index
        lefts = range(len(exit_user_list))

        plt.figure(figsize=(9, 9))
        exit_x = [i + 1 for i in range(len(exit_user_list))]
        exit_rate_list = [round(value, 0) for value in exit_user_df['exit_rate']]
        under_rusage_rate_list = [round(value, 0) for value in exit_user_df["under_rusage_mean_rate"]]
        bar1 = plt.bar([i - 0.2 for i in exit_x], exit_rate_list, width=0.4, label="exit job rate(%)", color="red")
        bar2 = plt.bar([i + 0.2 for i in lefts], under_rusage_rate_list, width=0.4, label="under rusage job rate(%)", color="blue")
        plt.xlabel("Eng.")
        plt.ylabel("rate")

        for rect in bar1:
            height = rect.get_height()
            plt.text(rect.get_x() + rect.get_width() / 2, height + 3, str(height), ha="center", va="bottom")
        for rect in bar2:
            height = rect.get_height()
            plt.text(rect.get_x() + rect.get_width() / 2, height + 3, str(height), ha="center", va="bottom")

        plt.legend()
        plt.savefig(picture_dir)
        plt.cla()

        self.picture_dic['$UNDER_RUASGE_HISTOGRAM'] = picture_dir

    def generate_rusage_rpt_md(self):
        rpt_md = r'rusage_mem_analysis_from_%s_to_%s.md' % (self.start_date, self.end_date)
        doc_dir = os.path.join(config.report_path, rpt_md)
        lines = ''

        # overall histogram
        with open(config.report_template, 'r') as tf:
            for line in tf:
                new_line = line.replace('$START_DATE', self.start_date).replace('$END_DATE', self.end_date)

                for var in self.picture_dic.keys():
                    new_line = new_line.replace(var, self.picture_dic[var])

                for var in self.table_dic.keys():
                    if line.find(var) != -1:
                        with open(self.table_dic[var], 'r') as vf:
                            content = vf.read()
                            new_line = content

                lines += new_line

        with open(doc_dir, 'w') as df:
            df.write(lines)

        logger.info("Report Path: %s" % str(rpt_md))

    def write_error_table(self):
        table_name = 'error.table'
        table_dir = os.path.join(self.table_dir, table_name)
        ml_df = self.df[self.df['pre_mem'] != 0]

        if ml_df.empty:
            ml_mse = 0
            ml_mae = 0
        else:
            ml_mse = np.sqrt(MSE(ml_df['max_mem'], ml_df['pre_mem']))
            ml_mae = MAE(ml_df['max_mem'], ml_df['pre_mem'])

        human_df = self.df[self.df['pre_mem'] == 0]
        human_mse = np.sqrt(MSE(human_df['max_mem'], human_df['rusage_mem']))
        human_mae = MAE(human_df['max_mem'], human_df['rusage_mem'])
        total_mse = np.sqrt(MSE(self.df['max_mem'], self.df['rusage_mem']))
        total_mae = MAE(self.df['max_mem'], self.df['rusage_mem'])

        with open(table_dir, 'w') as tf:
            content = 'human rusage memory rmse: %s\n' % str(round(human_mse, 5))
            content += 'model predict memory rmse: %s\n' % str(round(ml_mse, 5))
            content += 'total rusage memory rmse: %s\n' % str(round(total_mse, 5))
            content += 'human rusage memory mae: %s\n' % str(round(human_mae, 5))
            content += 'model predict memory mae: %s\n' % str(round(ml_mae, 5))
            content += 'total rusage memory mae: %s\n' % str(round(total_mae, 5))
            tf.write(content)

        self.table_dic["$ERROR_TABLE"] = table_dir

    def write_predict_memory_table(self):
        table_name = 'predict_memory.table'
        picture_dir = os.path.join(self.picture_dir, 'predict.png')
        table_dir = os.path.join(self.table_dir, table_name)
        value_bins = [-float('inf'), 1, 2, 4, 8, 16, 32, 64, float('inf')]
        x = [i for i in range(len(value_bins) - 1)]
        x_label_list = []

        for i in range(len(value_bins) - 1):
            x_label_list.append(r"%s-%s" % (str(value_bins[i]), str(value_bins[i + 1])))

        ml_df = self.df[self.df['pre_mem'] != 0]

        if ml_df.empty:
            logger.error('Could not find memory prediction result, ignore predict_memory.table.')
            return

        ml_df['difference_value'] = (ml_df['max_mem'] - ml_df['pre_mem'])
        ml_df['difference_value'] = ml_df['difference_value'].abs()

        human_df = self.df[self.df['pre_mem'] == 0]
        human_df['difference_value'] = (human_df['max_mem'] - human_df['rusage_mem'])
        human_df['difference_value'] = human_df['difference_value'].abs()

        total_df = pd.DataFrame()
        total_df['difference_value'] = (self.df['max_mem'] - self.df['rusage_mem'])
        total_df['difference_value'] = total_df['difference_value'].abs()

        ml_df['value_interval'] = pd.cut(ml_df['difference_value'].values.reshape(-1), value_bins)
        human_df['value_interval'] = pd.cut(human_df['difference_value'].values.reshape(-1), value_bins)
        total_df['value_interval'] = pd.cut(total_df['difference_value'].values.reshape(-1), value_bins)

        predict_table_df = pd.DataFrame()
        predict_table_df['predict'] = ml_df['value_interval'].value_counts(normalize=True).rename_axis('value_interval').to_frame(name='counts')
        predict_table_df['human'] = human_df['value_interval'].value_counts(normalize=True).rename_axis('value_interval').to_frame(name='counts')
        predict_table_df['total'] = total_df['value_interval'].value_counts(normalize=True).rename_axis('value_interval').to_frame(name='counts')
        predict_table_df = predict_table_df.round(2)

        bar_width = 0.25
        bars1 = predict_table_df['predict'].tolist()
        bars2 = predict_table_df['human'].tolist()
        bars3 = predict_table_df['total'].tolist()

        r1 = np.arange(len(bars1))
        r2 = [x + bar_width for x in r1]
        r3 = [x + bar_width for x in r2]

        plt.figure(figsize=(9, 9))
        plt.xticks(x, x_label_list)

        bar1 = plt.bar(r1, bars1, color='green', alpha=0.8, width=bar_width, label='model predict')
        bar2 = plt.bar(r2, bars2, color='purple', alpha=0.8, width=bar_width, label='human rusage')
        bar3 = plt.bar(r3, bars3, color='blue', alpha=0.8, width=bar_width, label='total')

        plt.xlabel('error interval')
        plt.ylabel('error rate')

        for rect in bar1:
            height = rect.get_height()
            plt.text(rect.get_x() + rect.get_width() / 2, height + 3, str(height), ha="center", va="bottom")

        for rect in bar2:
            height = rect.get_height()
            plt.text(rect.get_x() + rect.get_width() / 2, height + 3, str(height), ha="center", va="bottom")

        for rect in bar3:
            height = rect.get_height()
            plt.text(rect.get_x() + rect.get_width() / 2, height + 3, str(height), ha="center", va="bottom")

        plt.legend()
        plt.savefig(picture_dir)
        plt.cla()

        for column in predict_table_df.columns:
            predict_table_df[column] = predict_table_df[column].apply(lambda y: "{0:.0%}".format(y))

        with open(table_dir, 'w') as tf:
            tf.write(predict_table_df.to_markdown(index=True))

        self.table_dic["PREDICT_MEMORY_TABLE"] = table_dir
        self.table_dic["PREDICT_MEMORY_CHART"] = picture_dir

    def over_rusage_user_histogram(self):
        self.user_df["mem_hour_rate"] = (self.user_df["over_mem_hours"] / (self.user_df["over_mem_hours"].sum()) * 100).apply(lambda x: f'{x:.2f}%')
        top_user_data = self.user_df.sort_values("over_mem_hours", inplace=False, ascending=False).head(15).index

        # user df
        hist_user_df = self.user_df.loc[top_user_data]
        hist_user_df["index"] = [i + 1 for i in range(len(top_user_data))]

        # df
        hist_df = self.df[self.df['user'].isin(top_user_data)]

        for i in range(len(top_user_data)):
            command_list = self.df[self.df.user == top_user_data[i]]['command'].to_list()
            first_words = [sentence.split()[0] for sentence in command_list]
            word_counts = Counter(first_words)
            most_common_word, frequency = word_counts.most_common(1)[0]
            user_hist_df = hist_df[hist_df['user'].isin([top_user_data[i]])]

            if frequency / len(command_list) > 0.7:
                title = 'More User: %s Index: %s 95%% < %s [%s]' % (top_user_data[i], str(i + 1), str(round(self.user_df.loc[top_user_data[i]]["95_quantile_mem"].tolist(), 2)), most_common_word)
            else:
                title = 'More User: %s Index: %s 95%% < %s' % (top_user_data[i], str(i + 1), str(round(self.user_df.loc[top_user_data[i]]["95_quantile_mem"].tolist(), 2)))

            user_hist_df['rusage_mem'].fillna(0, inplace=True)

            # figure
            plt.figure(figsize=(9, 9))
            bins = np.histogram(np.hstack((user_hist_df['max_mem'], user_hist_df['rusage_mem'])), bins=30)[1]
            counts1, bins1, _ = plt.hist(user_hist_df['max_mem'], bins, alpha=0.5, label='max mem(GB)')
            counts2, bins2, _ = plt.hist(user_hist_df['rusage_mem'], bins, alpha=0.5, label='rusage mem(GB)')
            plt.axvline(self.user_df.loc[top_user_data[i]]["95_quantile_mem"].tolist(), label='95% quantile')

            plt.legend()
            plt.xlabel('Memory(GB)')
            plt.ylabel('Job count')
            plt.title(title)
            plt.savefig(os.path.join(self.picture_dir, 'more.%s.hist.png' % str(top_user_data[i])))
            plt.cla()

    def under_rusage_user_histogram(self):
        self.user_df["mem_hour_rate"] = (self.user_df["under_mem_hours"] / (self.user_df["under_mem_hours"].sum()) * 100).apply(lambda x: f'{x:.2f}%')
        top_user_data = self.user_df.sort_values("under_mem_hours", inplace=False, ascending=False).head(15).index

        # user df
        hist_user_df = self.user_df.loc[top_user_data]
        hist_user_df["index"] = [i + 1 for i in range(len(top_user_data))]

        # df
        hist_df = self.df[self.df['user'].isin(top_user_data)]

        for i in range(len(top_user_data)):
            command_list = self.df[self.df.user == top_user_data[i]]['command'].to_list()
            first_words = [sentence.split()[0] for sentence in command_list]
            word_counts = Counter(first_words)
            most_common_word, frequency = word_counts.most_common(1)[0]
            user_hist_df = hist_df[hist_df['user'].isin([top_user_data[i]])]

            if frequency / len(command_list) > 0.7:
                title = 'Less User: %s Index: %s 95%% < %s [%s]' % (top_user_data[i], str(i + 1), str(round(self.user_df.loc[top_user_data[i]]["95_quantile_mem"].tolist(), 2)), most_common_word)
            else:
                title = 'Less User: %s Index: %s 95%% < %s' % (top_user_data[i], str(i + 1), str(round(self.user_df.loc[top_user_data[i]]["95_quantile_mem"].tolist(), 2)))

            user_hist_df['rusage_mem'].fillna(0, inplace=True)

            # figure
            plt.figure(figsize=(9, 9))
            bins = np.histogram(np.hstack((user_hist_df['max_mem'], user_hist_df['rusage_mem'])), bins=30)[1]
            counts1, bins1, _ = plt.hist(user_hist_df['max_mem'], bins, alpha=0.5, label='max mem(GB)')
            counts2, bins2, _ = plt.hist(user_hist_df['rusage_mem'], bins, alpha=0.5, label='rusage mem(GB)')
            plt.axvline(self.user_df.loc[top_user_data[i]]["95_quantile_mem"].tolist(), label='95% quantile')

            plt.legend()
            plt.xlabel('Memory(GB)')
            plt.ylabel('Job count')
            plt.title(title)
            plt.savefig(os.path.join(self.picture_dir, 'less.%s.hist.png' % str(top_user_data[i])))
            plt.cla()


class SlotsReport:
    def __init__(self, df, start_date, end_date):
        self.df = df
        self.start_date, self.end_date = start_date, end_date

        # convert memory data
        self.data_process()
        self.user_df = self.user_data_process()
        self.picture_dir = os.path.join(config.report_path, 'pictures_cpu/%s_%s/' % (start_date, end_date))
        self.table_dir = os.path.join(config.report_path, 'tables_cpu/%s_%s/' % (start_date, end_date))

        if not os.path.exists(self.picture_dir):
            try:
                os.makedirs(self.picture_dir)
            except Exception as error:
                logger.error(r'*Error*: Failed on creating report picture directory %s' % (str(self.picture_dir)))
                logger.error(str(error))
                sys.exit(1)

        if not os.path.exists(self.table_dir):
            try:
                os.makedirs(self.table_dir)
            except Exception as error:
                logger.error(r'*Error*: Failed on creating report picture directory %s' % (str(self.table_dir)))
                logger.error(str(error))
                sys.exit(1)

        self.picture_dic = {}
        self.table_dic = {}

    def data_process(self):
        """
        compute run time(seconds), cpu utilization. fillna reserve hosts:1 for each job in dataframe.
        drop:
            self.df["started_time"] = NaN or could not recognize
            self.df["finished_time"] = NaN or could not recognize
        add:
            self.df["run_time"], self.df["processors_used"], self.df["processors_utilization"], self.df["over_processors_requested"]
        fill:
            self.df["span_hosts"], self.df["processors_requested"]
        """
        if hasattr(config, 'job_format') and config.job_format.lower() == 'json':
            self.df['start'] = pd.to_datetime(self.df["started_time"], format="%a-%b-%d %H:%M:%S", errors='coerce')
            self.df['end'] = pd.to_datetime(self.df['finished_time'], format="%a-%b-%d %H:%M:%S", errors='coerce')
        else:
            self.df['start'] = pd.to_datetime(self.df["started_time"], format="%a %b %d %H:%M:%S", errors='coerce')
            self.df['end'] = pd.to_datetime(self.df['finished_time'], format="%a %b %d %H:%M:%S", errors='coerce')

        self.df.dropna(subset=['start', 'end'], inplace=True)

        self.df["run_time"] = (self.df["end"] - self.df['start']).dt.total_seconds()
        self.df = self.df[self.df["run_time"] != 0]
        self.df["processors_used"] = self.df["cpu_time"] / self.df["run_time"]

        self.df["span_hosts"].fillna(0, inplace=True)
        self.df["processors_requested"].fillna(1, inplace=True)
        self.df = self.df[self.df["processors_requested"] != 1]

        self.df["processors_utilization"] = self.df["processors_used"] / self.df["processors_requested"]
        self.df["interactive_mode"].astype('bool')

        self.df["over_processors_requested"] = self.df["processors_requested"] * 0.7 - self.df["processors_used"]
        self.df["over_processors_requested"] = self.df["over_processors_requested"].apply(lambda x: 0 if x < 0 else x)

        logger.info("Data process done.")

    def user_data_process(self):
        """
        analysis cpu utilization group by user
        return:
            DataFrame data group by user
            DataFrame columns including processors_utilization_mean, processors_requests_sum, processors_requests_mean, processors_used_sum
                                        interactive_mode_count, job_num, interactive_rate
        """
        user_df = pd.DataFrame()
        user_df["over_processors_requested_sum"] = self.df["over_processors_requested"].groupby(self.df["user"]).sum()
        user_df['processors_utilization_mean'] = self.df["processors_utilization"].groupby(self.df["user"]).mean()
        user_df["processors_requests_sum"] = self.df["processors_requested"].groupby(self.df["user"]).sum()
        user_df["processors_requests_mean"] = self.df["processors_requested"].groupby(self.df["user"]).mean()
        user_df["processors_used_sum"] = self.df["processors_used"].groupby(self.df["user"]).sum()
        user_df["processors_used_mean"] = self.df["processors_used"].groupby(self.df["user"]).mean()
        user_df["interactive_mode_count"] = self.df["interactive_mode"].groupby(self.df["user"]).sum()
        user_df["job_num"] = self.df["job_id"].groupby(self.df["user"]).count()
        user_df["interactive_rate"] = user_df["interactive_mode_count"] / user_df["job_num"]

        return user_df

    def analysis(self):
        self.draw_user_requested_processors_pie_chart()
        self.write_user_requested_processors_table()

    def draw_user_requested_processors_pie_chart(self):
        picture_dir = os.path.join(self.picture_dir, 'over_processors_requested_user_pie_chart.png')
        top10_user_data = self.user_df.sort_values("over_processors_requested_sum", inplace=False, ascending=False).head(10)
        top10_user_data.loc["others"] = self.user_df["over_processors_requested_sum"].sum() - top10_user_data["over_processors_requested_sum"].sum()

        plt.figure(figsize=(9, 9))
        plt.pie(top10_user_data["over_processors_requested_sum"], labels=top10_user_data.index, autopct='%1.1f%%', pctdistance=0.9)
        plt.legend(loc="center right")
        plt.savefig(picture_dir)
        plt.cla()

        self.picture_dic['$OVER_PROCESSORS_REQUESTED_USER_PIE'] = picture_dir

    def write_user_requested_processors_table(self):
        table_name = 'over_processors_requested_user_pie_chart.table'
        table_dir = os.path.join(self.table_dir, table_name)
        self.user_df["pie_chart_rate"] = (self.user_df["over_processors_requested_sum"] / (self.user_df["over_processors_requested_sum"].sum()) * 100).apply(lambda x: f'{x:.2f}%')
        top_user_data = self.user_df.sort_values("over_processors_requested_sum", inplace=False, ascending=False).head(15).index
        table_user_df = self.user_df.loc[top_user_data]
        table_user_df["index"] = [i + 1 for i in range(len(top_user_data))]
        show_column_list = ["index", "pie_chart_rate", "over_processors_requested_sum", 'processors_utilization_mean',
                            "interactive_rate", "processors_requests_mean", "processors_used_mean"]

        with open(table_dir, 'w') as tf:
            tf.write(table_user_df.loc[top_user_data, show_column_list].to_markdown(index=True))

        self.table_dic["$OVER_PROCESSORS_REQUESTED_USER_PIE_TABLE"] = table_dir


def main():
    args = read_args()

    if args.start_date and args.end_date and args.db:
        if args.memory:
            df = merge_data(start_date=args.start_date, end_date=args.end_date, csv_path=args.db, mode='memory')

            if df.empty:
                logger.error('Could not find valid data, please check.')
                sys.exit(1)

            rusage_report = MemoryReport(df, args.start_date, args.end_date)
            rusage_report.analysis()
            rusage_report.generate_rusage_rpt_md()
        elif args.cpu:
            df = merge_data(start_date=args.start_date, end_date=args.end_date, csv_path=args.db, mode='cpu')

            if df.empty:
                logger.error('Could not find valid data, please check.')
                sys.exit(1)

            rusage_report = SlotsReport(df, args.start_date, args.end_date)
            rusage_report.analysis()
        else:
            logger.error("Please specific analysis cpu or memory!")


if __name__ == '__main__':
    main()
