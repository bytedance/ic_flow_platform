import os
import sys
import uuid

from pymongo import MongoClient

sys.path.append(str(os.environ['IFP_INSTALL_PATH']) + 'config/')
import config


def generate_uuid_from_file_path(file_path: str) -> str:
    return str(uuid.uuid3(uuid.NAMESPACE_DNS, file_path))


def save_ifp_records(data_dic: dict):
    if not hasattr(config, 'mongo_db'):
        return

    client = MongoClient(config.mongo_db)
    db = client[data_dic['project']]
    collection = db['ifp_records']
    data_dic['_id'] = generate_uuid_from_file_path(file_path=data_dic['file_path'])
    collection.update_one(
        {'_id': data_dic['_id']},
        {'$set': data_dic},
        upsert=True)