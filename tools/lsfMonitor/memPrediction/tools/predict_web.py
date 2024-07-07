# -*- coding: utf-8 -*-
################################
# File Name   : predict_web.py
# Author      : zhangjingwen.silvia
# Created On  : 2023-12-14 14:28:30
# Description :
################################
import os
import sys
import yaml
import logging
import pandas as pd
from flask import Flask, request
from flask_restful import Api, Resource

sys.path.append(str(os.environ['MEM_PREDICTION_INSTALL_PATH']))

from common import common
from config import config
from bin import predict

logger = common.get_logger(name='root', level=logging.DEBUG)
config = os.path.join(config.predict_model, 'config/config')

if not os.path.exists(config):
    logger.error("Could not find config: %s, please check!" % config)
    sys.exit(1)

with open(config, 'r') as cf:
    config_dic = yaml.load(cf, Loader=yaml.FullLoader)

predict_model = predict.PredictModel(config_dic)


class MemoryPredictServer(Resource):
    def post(self):
        data = request.form
        data = pd.DataFrame(data,  index=[0])

        try:
            predict_memory = predict_model.predict(False, data)
        except Exception:
            predict_memory = 1024

        return predict_memory


app = Flask(__name__)
api = Api(app)
api.add_resource(MemoryPredictServer, "/memPrediction")
