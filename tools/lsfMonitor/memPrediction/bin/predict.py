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
import argparse
import logging
import pickle
import yaml
import numpy as np
import pandas as pd

sys.path.append(str(os.environ['MEM_PREDICTION_INSTALL_PATH']))

from config import config
from common import common, common_model, common_lsf

logger = common.get_logger(name='root', level=logging.DEBUG)


def read_args():
    """
    Read in arguments.
    """
    parser = argparse.ArgumentParser()

    # Predict args group
    predict_model_group = parser.add_argument_group('predict job memory')

    predict_model_group.add_argument('--job_yaml',
                                     default=os.path.join(os.getcwd(), 'job.yaml'),
                                     help='job infomation in order to predict job max memory(gb)')
    predict_model_group.add_argument('-c', '--config',
                                     default=os.path.join(os.path.join(config.model_db_path, 'latest'), 'config/config'),
                                     help='predict model config')
    predict_model_group.add_argument('--job_name', help='job name')
    predict_model_group.add_argument('--cwd', help='job exec path')
    predict_model_group.add_argument('--command', help='job command')
    predict_model_group.add_argument('--project', help='job project')
    predict_model_group.add_argument('--queue', help='job queue')
    predict_model_group.add_argument('--started_time', help='job begin time')
    predict_model_group.add_argument('--rusage_mem', default=0, help='job reserve memory')
    predict_model_group.add_argument('--user', default=0, help='job submission user')
    predict_model_group.add_argument('-d', '--debug', default=False, action='store_true', help='debug mode')

    args = parser.parse_args()

    return args


class PredictModel:
    def __init__(self, config_dic):
        self.config_dic = config_dic
        self.column_ori_list = ['started_time', 'job_name', 'user', 'status', 'project', 'queue', 'cwd', 'command', 'rusage_mem', 'max_mem']
        self.encode_ori_list = ['user', 'project', 'queue']
        self.factor_ori_list = ['user', 'project', 'queue', 'rusage_mem']
        self.result_ori_list = ['max_mem']

        if 'model' in self.config_dic and 'model_file' in self.config_dic['model']:
            self.model = self.read_binary_file(self.config_dic['model']['model_file'])
        else:
            logger.error("Could not find model file in model config, please check!")

        if 'cat_file' in self.config_dic:
            self.enc_cats = self.read_binary_file(self.config_dic['cat_file'])
        else:
            logger.error("Could not find enc_cats file in model config, please check!")

        if 'user_df_dic' in self.config_dic:
            self.user_df_dic = self.read_binary_file(self.config_dic['user_df_dic'])
        else:
            logger.error("Could not find user max memory dict in model config, please check!")

    @common.timer
    def predict(self, debug, job_info_dic):
        logger.info("predict max memory ... unit: %s" % str(common_lsf.get_lsf_unit_for_limits()))

        if debug:
            logger.debug("Debug mode, tool maybe crash.")
            predict_memory = self.get_predict_memory(job_info_dic)
        else:
            try:
                predict_memory = self.get_predict_memory(job_info_dic)
            except Exception as error:
                logger.error("Could not predict memory for this job, please check!")
                logger.error("Error: %s" % str(error))
                predict_memory = 1

        lsf_unit_for_limits = common_lsf.get_lsf_unit_for_limits()
        result_prediction = common.memory_unit_from_gb_other(predict_memory, unit=lsf_unit_for_limits)

        logger.info("predict max memory is %s %s" % (str(result_prediction), lsf_unit_for_limits))

        return result_prediction

    def get_predict_memory(self, job_info_dic):
        job_df = pd.DataFrame(job_info_dic, index=[0, ])
        job_df = self.data_preprocess(job_df)
        job_df = self.generate_feature(job_df)
        job_struct_data = self.encode(job_df)
        predict_memory = self.model_prediction(job_struct_data)

        return predict_memory

    def data_preprocess(self, job_df):
        for column in self.column_ori_list:
            if column in job_df.columns:
                dt = job_df[column].dtypes

                if dt == "int" or dt == "float":
                    job_df[column].fillna(0, inplace=True)
                elif dt == 'object':
                    job_df[column].fillna("None", inplace=True)

        job_df['rusage_mem'] = 0.0

        return job_df

    def read_binary_file(self, binary_file_path):
        if not os.path.exists(binary_file_path):
            logger.info("model path: %s is not exists, please check!" % binary_file_path)

        return pickle.load(open(binary_file_path, "rb"))

    def generate_feature(self, job_df):
        # generate time feature
        job_df = self.generate_time_feature(job_df)

        # generate user history max memory feature
        job_df = self.gen_user_max_mem_feature(job_df)

        # generate base model feature
        job_df = self.generate_base_model_feature(job_df)

        return job_df

    def post_generate_feature(self, job_struct_data):
        job_struct_data = self.fill_rusage_memory(job_struct_data)

        return job_struct_data

    def fill_rusage_memory(self, job_struct_data):
        logger.info("post df: %s" % str(job_struct_data))
        rusage_factor_list = ['day_of_weekday', 'hour_of_day', 'month', 'user', 'project', 'queue']
        job_null_rusage_df = job_struct_data.loc[job_struct_data['rusage_mem'] == 0, rusage_factor_list]
        job_struct_data.loc[job_struct_data['rusage_mem'] == 0, 'rusage_mem'] = self.rusage_model.predict(job_null_rusage_df)

        return job_struct_data

    def generate_time_feature(self, job_df):
        logger.info("Extract time feature ...")

        try:
            job_df["day_of_weekday"] = pd.to_datetime(job_df["started_time"], format="%a %b %d %H:%M:%S", errors='coerce').dt.day_name()
            job_df["hour_of_day"] = pd.to_datetime(job_df["started_time"], format="%a %b %d %H:%M:%S", errors='coerce').dt.hour
            job_df["month"] = pd.to_datetime(job_df["started_time"], format="%a %b %d %H:%M:%S", errors='coerce').dt.month
        except Exception as error:
            logger.error("Could not convert to time feature!")
            logger.error("Error: %s" % str(error))

            job_df["day_of_weekday"] = 'None'
            job_df["hour_of_day"] = 0
            job_df["month"] = 0

        job_df["day_of_weekday"].fillna('None', inplace=True)
        job_df["hour_of_day"].fillna(0, inplace=True)
        job_df["month"].fillna(0, inplace=True)

        return job_df

    def gen_user_max_mem_feature(self, job_df):
        logger.info('Generate user history max memory feature ...')

        user_max_mem_mean_dic = {key: value['user_max_mem_mean'] for key, value in self.user_df_dic.items()}
        user_max_mem_median_dic = {key: value['user_max_mem_median'] for key, value in self.user_df_dic.items()}

        job_df['user_max_mem_mean'] = job_df['user'].map(user_max_mem_mean_dic)
        job_df['user_max_mem_median'] = job_df['user'].map(user_max_mem_median_dic)

        logger.debug("mean: %s, median: %s" % (str(job_df['user_max_mem_mean']), str(job_df['user_max_mem_median'])))

        return job_df

    def generate_base_model_feature(self, job_df):
        logger.info("Extract base model feature in column cwd, command and job_name")

        if 'base_model' not in self.config_dic:
            return job_df

        for column in self.config_dic['base_model'].keys():
            logger.info("Process column: %s ..." % column)
            column_values = job_df[column].values
            pattern = re.compile(r"[^a-z|^A-Z]")
            column_sentences = [re.sub(pattern, " ", str(column_values)).split(), ]
            text_column = r'%s_text' % column
            df = pd.DataFrame()
            df[text_column] = np.array(column_sentences, dtype=object).tolist()
            model_list = list(self.config_dic['base_model'][column].keys())

            for model in model_list:
                if model == 'word2vec':
                    model_path = self.config_dic['base_model'][column][model]['model_path']
                    model_size = self.config_dic['base_model'][column][model]['emb_size']
                    word2vec_model = common_model.Word2VecModel(text_column, model_size, model_path)
                    emb_df = word2vec_model.generate_word2vec_feature(df)
                    job_df = pd.concat([job_df, emb_df], axis=1)

                    if 'cluster_model_path' in self.config_dic['base_model'][column][model].keys():
                        label_df = word2vec_model.gen_cluster_label(emb_df, self.config_dic['base_model'][column][model]['cluster_model_path'])
                        job_df = pd.concat([job_df, label_df], axis=1)

                if model == 'glove':
                    model_path = self.config_dic['base_model'][column][model]['model_path']
                    corpus_path = self.config_dic['base_model'][column][model]['corpus_path']
                    model_size = self.config_dic['base_model'][column][model]['emb_size']
                    glove_model = common_model.GloVeModel(text_column, model_size, corpus_path, model_path)
                    emb_df = glove_model.generate_glove_feature(df)
                    job_df = pd.concat([job_df, emb_df], axis=1)

                    if 'cluster_model_path' in self.config_dic['base_model'][column][model].keys():
                        label_df = glove_model.gen_cluster_label(emb_df, self.config_dic['base_model'][column][model]['cluster_model_path'])
                        job_df = pd.concat([job_df, label_df], axis=1)

        logger.info("job_df: %s" % str(job_df))

        return job_df

    def encode(self, job_struct_data):
        encode_list = self.config_dic['encode_list']

        for column in encode_list:
            job_struct_data[column] = job_struct_data[column].fillna(column)
            job_struct_data[column] = job_struct_data[column].astype('string')
            job_struct_data[column] = job_struct_data[column].astype('category')

        for column in encode_list:
            job_struct_data[column] = job_struct_data[column].map(lambda s: np.random.choice(self.enc_cats[column].classes_, 1)[0] if s not in self.enc_cats[column].classes_ else s)
            job_struct_data[column] = self.enc_cats[column].transform(list(job_struct_data[column].values))
            job_struct_data[column] = job_struct_data[column].astype('category')
            job_struct_data[column] = job_struct_data[column].astype('int')

        return job_struct_data

    def model_prediction(self, job_info_data):
        factor_list = self.config_dic['factor_list']
        job_info_list = []

        for factor in factor_list:
            if factor in job_info_data.columns:
                job_info_list.append(job_info_data[factor])

        job_info = pd.concat(job_info_list, axis=1)

        logger.debug("column: %s" % str(job_info.columns))

        if hasattr(self.model, 'best_iteration'):
            predict_memory = self.model.predict(job_info, iteration_range=(0, self.model.best_iteration + 1))
        else:
            predict_memory = self.model.predict(job_info)

        return predict_memory


def get_job_predict_memory(args):
    job_dic = {}

    if args.user and args.job_name and args.queue and args.project and args.cwd and args.command and args.started_time:
        logger.debug("Try to get infomation from args")
        job_dic['job_name'] = args.job_name
        job_dic['cwd'] = args.cwd
        job_dic['command'] = args.command
        job_dic['project'] = args.project
        job_dic['started_time'] = args.started_time
        job_dic['rusage_mem'] = args.rusage_mem
        job_dic['queue'] = args.queue
        job_dic['user'] = args.user

    elif args.job_yaml:
        logger.debug("Try to get infomation from job.yaml")

        if not os.path.exists(args.job_yaml):
            logger.error("Could not find job.yaml: %s, please check!" % args.job_yaml)

        with open(args.job_yaml, 'r') as jf:
            job_dic = yaml.load(jf, Loader=yaml.FullLoader)
    else:
        logger.error("Could not find any valid job infomation, please check!")
        return 1

    if not os.path.exists(args.config):
        logger.error("Could not find config: %s, please check!" % config)
        return 1

    with open(args.config, 'r') as cf:
        config_dic = yaml.load(cf, Loader=yaml.FullLoader)

    predict_model = PredictModel(config_dic)
    predict_memory = predict_model.predict(args.debug, job_dic)

    return predict_memory


################
# Main Process
################
def main():
    try:
        args = read_args()
        predict = get_job_predict_memory(args)
    except Exception:
        predict_memory = 1
        lsf_unit_for_limits = common_lsf.get_lsf_unit_for_limits()
        predict = common.memory_unit_from_gb_other(predict_memory, unit=lsf_unit_for_limits)

    print("%s" % str(predict))


if __name__ == '__main__':
    main()
