import re
import os
import sys
import datetime

sys.path.append(str(os.environ['MEM_PREDICTION_INSTALL_PATH']))
from common import common

logger = common.get_logger()


def main():
    config_path = os.path.join(str(os.environ['MEM_PREDICTION_INSTALL_PATH']), 'config/config.py')
    model_db_dir = os.path.join(str(os.environ['MEM_PREDICTION_INSTALL_PATH']), 'db/model_db/')

    if not os.path.exists(config_path):
        logger.error('Could not find %s, please check!' % str(config_path))
        sys.exit(1)

    if not os.path.exists(model_db_dir):
        logger.error('Could not find %s, please check!' % str(model_db_dir))
        sys.exit(1)

    if not os.listdir(model_db_dir):
        logger.error('Could not find any valid model in %s, please check!' % str(model_db_dir))
        sys.exit(1)

    latest_model_utc = datetime.datetime.strptime('1900_01_01_00_00', '%Y_%m_%d_%H_%M')
    latest_model = None

    for file in os.listdir(model_db_dir):
        try:
            file_utc = datetime.datetime.strptime(file, '%Y_%m_%d_%H_%M')
        except Exception:
            continue

        if file_utc > latest_model_utc:
            rpt_file_path = os.path.join(model_db_dir, '%s/rpt/rpt' % file)

            if not os.path.exists(rpt_file_path):
                continue

            latest_model_utc = file_utc
            latest_model = file

    if latest_model:
        latest_model_path = os.path.join(model_db_dir, latest_model)
    else:
        logger.error("Could not find latest model, please check!")
        sys.exit(1)

    old_rmse = 999

    with open(os.path.join(latest_model_path, 'rpt/rpt'), 'r') as RF:
        for line in RF:
            if my_match := re.match(r'\s*The\s*RMSE\s*is\s*(\d+\.\d+)\s*$', line):
                new_rmse = float(my_match.group(1))

    try:
        with open(config_path, 'r') as CF:
            line_list = []

            for line in CF:
                if my_match := re.match(r'^\s*predict_model\s*=\s*(.*)\s*$', line):
                    old_model_dir = my_match.group(1)
                    line = 'predict_model = "%s"' % str(latest_model_path)

                line_list.append(line)
    except Exception as error:
        logger.error('Could not open config file %s due to %s' % (str(config_path), str(error)))
        sys.exit(1)

    if os.path.exists(os.path.join(old_model_dir, 'rpt/rpt')):
        with open(os.path.join(old_model_dir, 'rpt/rpt'), 'r') as RF:
            for line in RF:
                if my_match := re.match(r'\s*The\s*RMSE\s*is\s*(\d+\.\d+)\s*$', line):
                    old_rmse = float(my_match.group(1))

    if new_rmse * 1.3 > old_rmse:
        logger.error("New model is not good, not udpate.")
        sys.exit(1)

    link_path = os.path.join(model_db_dir, 'latest')

    if os.path.exists(link_path):
        if os.path.islink(link_path):
            os.unlink(link_path)
            os.symlink(latest_model_path, link_path)
        else:
            logger.error('latest path is not a link: %s' % str(link_path))
            sys.exit(1)
    else:
        os.symlink(latest_model_path, link_path)

    logger.critical('Predict model is update. \n New Model: %s' % str(latest_model_path))


if __name__ == '__main__':
    main()
