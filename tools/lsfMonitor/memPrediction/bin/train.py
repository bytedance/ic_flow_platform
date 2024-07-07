# -*- coding: utf-8 -*-
################################
# File Name   : training_model.py
# Author      : zhangjingwen.silvia
# Created On  : 2023-11-03 10:32:51
# Description :
################################
import os
import re
import sys
import getpass
import argparse
import logging
import pickle
import yaml
import copy
import numpy as np
import pandas as pd
import xgboost as xgb
from datetime import datetime, timedelta
from tabulate import tabulate
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from imblearn.over_sampling import SMOTE
from sklearn.metrics import mean_squared_error as MSE
from sklearn.ensemble import RandomForestRegressor

sys.path.append(str(os.environ['MEM_PREDICTION_INSTALL_PATH']))

from config import config
from common import common, common_model, common_lsf

USER = getpass.getuser()
LOG_PATH = '/tmp/memPrediction.' + str(USER) + '.train.log'

if not os.path.exists('/tmp/memPrediction'):
    os.makedirs('/tmp/memPrediction')

logger = common.get_logger(save_log=True, log_path=LOG_PATH, name='root', level=logging.DEBUG)


def read_args():
    """
    Read in arguments.
    """
    parser = argparse.ArgumentParser()

    # Training args group
    training_model_group = parser.add_argument_group('training model')

    training_model_group.add_argument('-st', '--start_date',
                                      default=(datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d'),
                                      help='analysis rpt from start date, format: YYYY-mm-dd, default 60 days ago')
    training_model_group.add_argument('-et', '--end_date',
                                      default=datetime.now().strftime('%Y-%m-%d'),
                                      help='analysis rpt to end date, format: YYYY-mm-dd, default today')
    training_model_group.add_argument('-db', '--data_path',
                                      default=config.db_path,
                                      help='directory path including all training data')
    training_model_group.add_argument('--training_cfg',
                                      default=config.training_config_yaml,
                                      help='config for training model parameter, format: yaml')

    args = parser.parse_args()

    return args


class TrainingModel:
    def __init__(self, start_date, end_date, data_path, training_cfg):
        self.start_date, self.end_date, self.data_path, self.training_yaml = (start_date, end_date, data_path, training_cfg)
        self.start_date_utc = datetime.strptime(start_date, '%Y-%m-%d')
        self.end_date_utc = datetime.strptime(end_date, '%Y-%m-%d')

        # training config
        self.training_config_dic = self.dump_training_config()

        # working main path
        if hasattr(config, 'model_db_path') and os.path.exists(config.model_db_path):
            work_dir = config.model_db_path
        else:
            work_dir = os.getcwd()

        self.working_dir = os.path.join(work_dir, r'%s/' % datetime.now().strftime('%Y_%m_%d_%H_%M'))
        self.model_dir = os.path.join(self.working_dir, r'model/')
        self.cat_dir = os.path.join(self.working_dir, r'cat_encs/')
        self.config_dir = os.path.join(self.working_dir, r'config/')
        self.rpt_dir = os.path.join(self.working_dir, r'rpt/')
        new_dir_list = [self.working_dir, self.model_dir, self.cat_dir, self.config_dir, self.rpt_dir]

        for new_dir in new_dir_list:
            self.generate_working_path(new_dir)

        sibling_path_list = os.listdir(work_dir)
        link_flag = False

        for sibling in sibling_path_list:
            if sibling == 'latest':
                if not os.path.islink(os.path.join(work_dir, sibling)):
                    logger.error('Could not create latest link, because latest exists!')

                link_flag = True
                break

        if not link_flag:
            os.symlink(self.working_dir, os.path.join(work_dir, 'latest'))

        self.model_config_dic = {}
        self.model_config_dic = copy.deepcopy(self.training_config_dic)

        # data_process
        self.column_name_list = ['started_time', 'job_name', 'user', 'project', 'queue', 'cwd', 'command', 'rusage_mem', 'max_mem']
        self.encode_name_list = ['user', 'project', 'queue']
        self.factor_name_list = ['user', 'project', 'queue', 'rusage_mem']
        self.result_name_list = ['max_mem']

        self.df = pd.DataFrame()
        self.struct_data = pd.DataFrame()
        self.train_df = pd.DataFrame()
        self.test_df = pd.DataFrame()
        self.X_test, self.y_test, self.X_train, self.y_train = pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
        self.cat_encs = {}
        self.mse = 0

    def training(self):
        self.model_config_dic['encode_list'] = self.encode_name_list
        self.model_config_dic['column_list'] = self.column_name_list
        self.model_config_dic['factor_list'] = self.factor_name_list
        self.model_config_dic['result_list'] = self.result_name_list

        self.data_preparation()
        self.prefeature_process()
        self.encode_data()
        self.data_training()

        # analysis data
        self.analysis_result()

        # dump config
        self.dump_config()

    def dump_training_config(self):
        if not os.path.exists(self.training_yaml):
            logger.error("Could not find a valid config for training: %s" % self.training_yaml)
            sys.exit(1)

        with open(self.training_yaml, 'r') as tf:
            training_config_dic = yaml.load(tf, Loader=yaml.FullLoader)

        if not training_config_dic:
            logger.error("Could not find training yaml infomation in %s, please check!" % self.training_yaml)
            sys.exit(1)

        return training_config_dic

    def data_training(self):
        # split training and test dataset
        self.split_train_test()

        # Under Sampling & Over Sampling
        self.sampling_data()

        # training with xgb
        self.training_mem_model()

    def analysis_result(self):
        pre_y_test = self.get_criteria()

        self.data_analysis_rpt(pre_y_test)

    def generate_working_path(self, new_dir):
        if not os.path.exists(new_dir):
            try:
                os.makedirs(new_dir)
            except Exception as error:
                logger.error(r'*Error*: Failed on creating report picture directory %s' % (str(new_dir)))
                logger.error(str(error))
                sys.exit(1)

    def data_preparation(self):
        self.merge_data()
        self.drop_data()
        self.fill_data()
        self.unit_convert()

    def merge_data(self):
        if not os.path.exists(self.data_path):
            logger.error("The db path is not exists: %s, please check!" % self.data_path)
            sys.exit(1)

        logger.info("Staring merge data from %s to %s, totally %s days" % (self.start_date, self.end_date, str((self.end_date_utc - self.start_date_utc).days)))

        num = 0
        merge_path = os.path.join(self.working_dir, 'merge.csv')

        try:
            original_column_list = self.column_name_list
        except Exception as error:
            logger.error("Could not find data column definition in yaml, please check!")
            logger.error("Error: %s" % str(error))
            sys.exit(1)

        if os.path.exists(self.data_path):
            for file in os.listdir(self.data_path):
                if my_match := re.match(r'^job_info_(\S+).csv$', file):
                    file_date = datetime.strptime(my_match.group(1), '%Y%m%d')

                    if self.start_date_utc <= file_date <= self.end_date_utc:
                        logger.info("reading %s data ..." % file_date)
                        file_path = os.path.join(self.data_path, file)
                        df = pd.read_csv(file_path)

                        if 'status' in df.columns:
                            df = df[df['status'] == 'DONE']

                        df = df.drop_duplicates(subset=['job_id'], keep='first')
                        df = df[original_column_list]
                        df['rusage_mem'] = 0

                        if num == 0:
                            df.to_csv(merge_path, encoding='utf_8_sig', index=False)
                        else:
                            df.to_csv(merge_path, encoding='utf_8_sig', index=False, header=False, mode='a+')

                        num += 1

        if not os.path.exists(merge_path):
            logger.error("Could not find merge result csv: %s, please check!" % str(merge_path))
            sys.exit(1)
        else:
            if hasattr(config, 'max_training_lines') and config.max_training_lines:
                self.df = pd.read_csv(merge_path, nrows=int(config.max_training_lines))
            else:
                self.df = pd.read_csv(merge_path)

            os.remove(merge_path)
            logger.info("Reading csv done, the db dateframe shape is %s" % str(self.df.shape))
            logger.info("dataframe column including: %s" % str(self.df))

            self.model_config_dic['training_shape'] = str(self.df.shape)

    def drop_data(self):
        """
        drop result=Null record
        """
        logger.info("Drop data whose result column is NULL")
        self.df.dropna(subset=self.result_name_list, inplace=True)

    def fill_data(self):
        """
        Fill Null record record with 0
        """
        logger.info("Replace data based on dataframe dtypes ...")

        for column in self.column_name_list:
            if column in self.df.columns:
                dt = self.df[column].dtypes

                if dt == "int" or dt == "float":
                    self.df[column].fillna(0, inplace=True)
                elif dt == 'object':
                    self.df[column].fillna("None", inplace=True)

    def unit_convert(self):
        """
        convert unit:mb to unit:gb
        """
        logger.info("Convert unit from mb to gb")

        lsf_unit_for_limits = common_lsf.get_lsf_unit_for_limits()
        memory_item_list = ['max_mem', 'rusage_mem']

        for mem_item in memory_item_list:
            if mem_item in self.df.columns:
                self.df[mem_item] = common.memory_unit_to_gb(self.df[mem_item], unit=lsf_unit_for_limits)
            else:
                logger.error("Could not find column %s in dataframe, please check!" % mem_item)
                sys.exit(1)

    def prefeature_process(self):
        # extract feature from started time
        self.gen_time_feature()

        # generate user history feature
        self.gen_user_max_mem_feature()

        # word2vector model
        self.training_base_model()

    def postfeature_process(self):
        self.replace_rusage_memory()

    def replace_rusage_memory(self):
        """
        replace rusage memory when rusage memory is 0G
        """
        logger.info("Replace rusage memory is 0G ...")

        rusage_factor_list = ['day_of_weekday', 'hour_of_day', 'month', 'user', 'project', 'queue']
        rusage_result_list = ['rusage_mem']

        train_dataset = self.struct_data[self.struct_data['rusage_mem'] != 0]
        fill_dataset = self.struct_data[self.struct_data['rusage_mem'] == 0]

        X_train, y_train = train_dataset[rusage_factor_list], train_dataset[rusage_result_list]
        rf_rusage_model = RandomForestRegressor(n_estimators=64, random_state=6)
        rf_rusage_model.fit(X_train, y_train)

        fill_rusage_data = rf_rusage_model.predict(fill_dataset[rusage_factor_list])

        self.struct_data.loc[self.struct_data['rusage_mem'] == 0, ['rusage_mem']] = fill_rusage_data

        rusage_model_file = os.path.join(self.model_dir, 'rusage.model')
        pickle.dump(rf_rusage_model, open(rusage_model_file, "wb"))

        self.model_config_dic['rusage_model'] = rusage_model_file

    def gen_time_feature(self):
        """
        extract time feature including month , the hour of day and the day of week
        """
        logger.info("Extract feature from time column ...")

        try:
            self.df["day_of_weekday"] = pd.to_datetime(self.df["started_time"], format="%a %b %d %H:%M:%S", errors='coerce').dt.day_name()
            self.df["hour_of_day"] = pd.to_datetime(self.df["started_time"], format="%a %b %d %H:%M:%S", errors='coerce').dt.hour
            self.df["month"] = pd.to_datetime(self.df["started_time"], format="%a %b %d %H:%M:%S", errors='coerce').dt.month
        except Exception as error:
            logger.error("Could not convert to time feature!")
            logger.error("Error: %s" % str(error))

            self.df["day_of_weekday"] = 'None'
            self.df["hour_of_day"] = 0
            self.df["month"] = 0

        self.df["day_of_weekday"].fillna('None', inplace=True)
        self.df["hour_of_day"].fillna(0, inplace=True)
        self.df["month"].fillna(0, inplace=True)

        self.factor_name_list += ['day_of_weekday', 'hour_of_day', 'month']
        self.column_name_list += ['day_of_weekday', 'hour_of_day', 'month']
        self.encode_name_list.append('day_of_weekday')

    def gen_user_max_mem_feature(self):
        """
        Generate user history max memory feature, including mean, median, max mem interval mode
        """
        logger.info("Generate user history feature ...")

        # mean
        user_df = pd.DataFrame()
        user_df["user_max_mem_mean"] = self.df["max_mem"].groupby(self.df["user"]).mean()
        user_df["user_max_mem_median"] = self.df["max_mem"].groupby(self.df["user"]).median()

        user_df_dic = user_df.to_dict(orient='index')
        user_df_dic_file = os.path.join(self.model_dir, 'user_df.dic')
        pickle.dump(user_df_dic, open(user_df_dic_file, "wb"))
        self.model_config_dic['user_df_dic'] = user_df_dic_file

        self.df['user_max_mem_mean'] = self.df.groupby('user')['max_mem'].transform('mean')
        self.df['user_max_mem_median'] = self.df.groupby('user')['max_mem'].transform('median')

        self.factor_name_list += ['user_max_mem_mean', 'user_max_mem_median']
        self.column_name_list += ['user_max_mem_mean', 'user_max_mem_median']

    def training_base_model(self):
        if 'base_model' not in self.training_config_dic:
            return

        logger.info("Starting training base model in column ...")
        model_dic = {}

        for column in self.training_config_dic['base_model'].keys():
            logger.info("Process column: %s ..." % column)
            model_dic.setdefault(column, {})
            column_values = self.df[column].values
            column_sentences = []
            pattern = re.compile(r"[^a-z|^A-Z]")

            for i in range(len(column_values)):
                column_sentences.append(re.sub(pattern, " ", str(column_values[i])).split())

            text_column = r'%s_text' % column
            df = pd.DataFrame()
            df[text_column] = np.array(column_sentences, dtype=object)
            model_list = list(self.training_config_dic['base_model'][column].keys())

            for model in model_list:
                if model == 'word2vec':
                    # word vector model
                    logger.info("Starting training Word Vector model on %s ..." % column)

                    model_dic[column].setdefault('word2vec', {})
                    model_dic[column]['word2vec']['model_path'] = os.path.join(self.model_dir, r'%s_word2vec.model' % column)
                    model_dic[column]['word2vec']['model'] = common_model.Word2VecModel(text_column, self.training_config_dic['base_model'][column]['word2vec']['emb_size'], model_dic[column]['word2vec']['model_path'])
                    emb_df = model_dic[column]['word2vec']['model'].training_model(df)
                    self.df = pd.concat([self.df, emb_df], axis=1)
                    self.model_config_dic['base_model'][column][model]['model_path'] = model_dic[column]['word2vec']['model_path']

                    if 'cluster' in self.training_config_dic['base_model'][column]['word2vec']:
                        n_cluster = self.training_config_dic['base_model'][column]['word2vec']['cluster']
                        model_dic[column]['word2vec']['cluster_model_path'] = os.path.join(self.model_dir, r'%s_word2vec.cluster.model' % column)
                        label_df = model_dic[column]['word2vec']['model'].kmeans_cluster(emb_df, model_dic[column]['word2vec']['cluster_model_path'], n_cluster=n_cluster)
                        self.df = pd.concat([self.df, label_df], axis=1)
                        self.model_config_dic['base_model'][column][model]['cluster_model_path'] = model_dic[column]['word2vec']['cluster_model_path']
                        self.column_name_list.append('%s_%s_cluster_label' % (model, text_column))
                        self.factor_name_list.append('%s_%s_cluster_label' % (model, text_column))

                    for i in range(self.training_config_dic['base_model'][column][model]['emb_size']):
                        self.column_name_list.append('{}_{}_text_{}'.format(model, column, i))
                        self.factor_name_list.append('{}_{}_text_{}'.format(model, column, i))

                    logger.info("Training Word Vector model on %s done." % column)

                if model == 'glove':
                    # global vector model
                    logger.info("Starting training Global Vector model on %s ..." % column)

                    model_dic[column].setdefault('glove', {})
                    model_dic[column]['glove']['model_path'] = os.path.join(self.model_dir, r'%s_glove.model' % column)
                    model_dic[column]['glove']['corpus_path'] = os.path.join(self.model_dir, r'%s_glove.corpus' % column)
                    model_dic[column]['glove']['model'] = common_model.GloVeModel(text_column, self.training_config_dic['base_model'][column]['glove']['emb_size'], model_dic[column]['glove']['corpus_path'], model_dic[column]['glove']['model_path'])
                    emb_df = model_dic[column]['glove']['model'].training_model(df)
                    self.df = pd.concat([self.df, emb_df], axis=1)
                    self.model_config_dic['base_model'][column][model]['model_path'] = model_dic[column]['glove']['model_path']
                    self.model_config_dic['base_model'][column][model]['corpus_path'] = model_dic[column]['glove']['corpus_path']

                    if 'cluster' in self.training_config_dic['base_model'][column]['glove']:
                        n_cluster = int(self.training_config_dic['base_model'][column]['glove']['cluster'])
                        model_dic[column]['glove']['cluster_model_path'] = os.path.join(self.model_dir, r'%s_glove.cluster.model' % column)
                        label_df = model_dic[column]['glove']['model'].kmeans_cluster(emb_df, model_dic[column]['glove']['cluster_model_path'], n_cluster=n_cluster)
                        self.df = pd.concat([self.df, label_df], axis=1)
                        self.model_config_dic['base_model'][column][model]['cluster_model_path'] = model_dic[column]['glove']['cluster_model_path']
                        self.column_name_list.append('%s_%s_cluster_label' % (model, text_column))
                        self.factor_name_list.append('%s_%s_cluster_label' % (model, text_column))

                    for i in range(self.training_config_dic['base_model'][column][model]['emb_size']):
                        self.column_name_list.append('{}_{}_text_{}'.format(model, column, i))
                        self.factor_name_list.append('{}_{}_text_{}'.format(model, column, i))

                    logger.info("Training Glove Vector model on %s done." % column)

    def encode_data(self):
        self.struct_data = copy.deepcopy(self.df)
        self.struct_data.fillna(0, inplace=True)

        for column in self.encode_name_list:
            logger.info("category %s ..." % column)
            self.struct_data[column] = self.struct_data[column].fillna(column)
            self.struct_data[column] = self.struct_data[column].astype('string')
            self.struct_data[column] = self.struct_data[column].astype('category')

        # encode construction
        for column in self.encode_name_list:
            cats = list(self.struct_data.dtypes[column].categories)
            enc = LabelEncoder()
            enc.fit(cats)
            self.cat_encs[column] = enc

        cat_file = os.path.join(self.cat_dir, r'cat_encs.file')
        pickle.dump(self.cat_encs, open(cat_file, "wb"))
        self.model_config_dic['cat_file'] = cat_file

        # encode
        for column in self.struct_data.columns:
            if column in self.encode_name_list:
                logger.info("encoding %s ..." % column)
                self.struct_data[column] = self.cat_encs[column].transform(list(self.struct_data[column].values))
                self.struct_data[column] = self.struct_data[column].astype('category')
                self.struct_data[column] = self.struct_data[column].astype('int')

    def split_train_test(self):
        try:
            cross_validation_dic = self.training_config_dic['cross_validation']
        except Exception as error:
            logger.error("Could not find valid cross validation parameter, will use default setting!")
            logger.error("Error: %s" % str(error))
            cross_validation_dic = {'train_size': 0.99, 'test_size': 0.01, 'random_state': 6}

        logger.info("Split train and test data set using train rate %s and test rate %s" % (cross_validation_dic['train_size'], cross_validation_dic['test_size']))

        self.train_df, self.test_df = train_test_split(self.struct_data, **cross_validation_dic)

    def sampling_data(self):
        if 'Sampling' not in self.training_config_dic:
            return

        logger.info("Sampling data ")

        column_list = copy.deepcopy(self.factor_name_list)
        column_list += self.result_name_list
        self.train_df = self.train_df[column_list]

        logger.debug("Sampling column: %s" % str(self.train_df.columns))

        for column in self.training_config_dic['Sampling'].keys():
            status = self.training_config_dic['Sampling'][column]['status']

            if status:
                bins = self.training_config_dic['Sampling'][column]['bins']

                logger.debug("bins: %s" % str(bins))

                bins_column = r'%s_bins' % column
                self.train_df[bins_column] = pd.cut(self.train_df[column].values.reshape(-1), bins)
                icat_encs = {}
                icats = list(self.train_df.dtypes[bins_column].categories)
                ienc = LabelEncoder()

                ienc.fit(icats)
                icat_encs[bins_column] = ienc

                self.train_df[bins_column] = icat_encs[bins_column].transform(list(self.train_df[bins_column].values))
                self.train_df[bins_column] = self.train_df[bins_column].astype('category')
                self.train_df[bins_column] = self.train_df[bins_column].astype('int')

                logger.debug("sampling:%s" % str(self.train_df))

                if self.training_config_dic['Sampling'][column]['over_sample']['status']:
                    method = self.training_config_dic['Sampling'][column]['over_sample']['method']
                    sampling_strategy = self.training_config_dic['Sampling'][column]['over_sample']['sampling_strategy']

                    if method == 'SMOTE':
                        over_sampling = SMOTE(sampling_strategy=sampling_strategy)
                        train_df, train_df[bins_column] = over_sampling.fit_resample(self.train_df, self.train_df[bins_column])

    def training_mem_model(self):
        logger.info("Split factor and result ...")

        for column in self.result_name_list:
            if column in self.factor_name_list:
                self.factor_name_list.remove(column)

        self.X_train, self.X_test, self.y_train, self.y_test = self.train_df[self.factor_name_list], self.test_df[self.factor_name_list], self.train_df[self.result_name_list], self.test_df[self.result_name_list]

        logger.info("Training XGBoost Regression Model ...")

        model_name = self.training_config_dic['model']['model_name']

        if model_name == 'xgboost':
            training_parameter_dic = self.training_config_dic['model']['training_parameter']
            self.model = xgb.XGBRegressor(**training_parameter_dic)

            if 'fitting_parameter' in self.training_config_dic['model']:
                fit_parameter_dic = self.training_config_dic['model']['fitting_parameter']

                if 'early_stopping_rounds' in fit_parameter_dic:
                    fit_parameter_dic['eval_set'] = [(self.X_train, self.y_train), (self.X_test, self.y_test)]
                    self.model.fit(self.X_train, self.y_train, **fit_parameter_dic)
                else:
                    self.model.fit(self.X_train, self.y_train)

            xgb_reg_model_file = os.path.join(self.model_dir, 'xgb_reg.model')
            pickle.dump(self.model, open(xgb_reg_model_file, "wb"))

            self.model_config_dic['model']['model_file'] = xgb_reg_model_file

    def data_analysis_rpt(self, pre_y_test):
        result_df = pd.DataFrame()
        self.test_df['pre_mem'] = pre_y_test

        try:
            bins = self.training_config_dic['report']['bins']
        except Exception as error:
            logger.error("Could not find valis report memory binning category, use default setting!")
            logger.error("Error: %s" % str(error))
            bins = [-float('inf'), 1, 2, 4, 8, 16, 32, 64, 128, 256, 512, float('inf')]

        self.test_df['max_mem_interval'] = pd.cut(self.test_df['max_mem'].values.reshape(-1), bins)
        logger.info("max mem interval value counts is \n %s" % str(self.test_df["max_mem_interval"].value_counts()))

        result_df['max_mem_num'] = self.test_df["max_mem"].groupby(self.test_df['max_mem_interval']).count()
        result_df['pre_mem_diff'] = (self.test_df['pre_mem'] - self.test_df["max_mem"]).groupby(self.test_df['max_mem_interval']).mean()
        result_df['pre_mem_diff_rate'] = (((self.test_df['pre_mem'] - self.test_df["max_mem"]) / self.test_df["max_mem"]) * 100).groupby(self.test_df['max_mem_interval']).mean()

        report_file = os.path.join(self.rpt_dir, 'rpt')

        with open(report_file, 'w') as rf:
            content = 'The RMSE is %s \n' % str(self.mse)
            content += tabulate(result_df, headers='keys', tablefmt='psql')

            rf.write(content)

    def get_criteria(self):
        if hasattr(self.model, 'best_iteration'):
            pre_y_test = self.model.predict(self.X_test, iteration_range=(0, self.model.best_iteration + 1))
        else:
            pre_y_test = self.model.predict(self.X_test)

        self.mse = np.sqrt(MSE(self.y_test, pre_y_test))
        self.model_config_dic['RMSE'] = str(self.mse)

        logger.info("Training mse is %s ..." % str(self.mse))

        return pre_y_test

    def dump_config(self):
        config_file = os.path.join(self.config_dir, 'config')

        self.model_config_dic['encode_list'] = self.encode_name_list
        self.model_config_dic['factor_list'] = self.factor_name_list
        self.model_config_dic['column_list'] = self.column_name_list
        self.model_config_dic['result_list'] = self.result_name_list

        with open(config_file, 'w') as cf:
            cf.write(yaml.dump(self.model_config_dic, allow_unicode=True))


################
# Main Process
################
@common.timer
def main():
    args = read_args()
    training_model = TrainingModel(args.start_date, args.end_date, args.data_path, args.training_cfg)
    training_model.training()


if __name__ == '__main__':
    main()
