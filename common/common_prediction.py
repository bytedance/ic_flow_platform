import os
import re
import subprocess
from typing import Dict

import yaml


def read_conf() -> dict:
    config_path = os.path.join(str(os.environ['IFP_INSTALL_PATH']), 'config/mem_prediction.yaml')

    if not os.path.exists(config_path):
        return {}

    with open(config_path, 'r') as cf:
        conf_dic = yaml.load(cf, Loader=yaml.FullLoader)

    return conf_dic if conf_dic is not None else {}


class PredictionModel:
    def __init__(self):
        self.config_dic = read_conf()

    def predict_job(self, job_info: Dict[str, str], run_method: str) -> str:
        new_run_method = run_method

        try:
            ori_res_req = job_info['res_req']
            # Check for job parameter
            check = self.check_job_res_req(res_req=ori_res_req)

            # If check failed, return
            if not check:
                return new_run_method

            # If Check passed, predicting max memory for job, generating new res_req and modifying job res_req
            predict_mem = self.predict_job_memory(job_info)
            new_res_req = self._gen_res_req(res_req=ori_res_req, memory=predict_mem)
            new_run_method = self._gen_run_method(run_method=run_method, new_res_req=new_res_req, old_res_req=ori_res_req)
        except Exception:
            pass

        return new_run_method

    @staticmethod
    def check_job_res_req(res_req: str) -> bool:
        """
        Checking job resource request, finding job without a resource request of memory.
        """
        if not res_req:
            return True
        elif res_req.find('rusage') == -1:
            return True
        elif res_req.find('rusage') != -1 and res_req.find('mem') == -1:
            return True

        return False

    def predict_job_memory(self, job_info: Dict[str, str]) -> int:
        """
        Predicting max memory usage of job based on job information.
        """
        service = self.config_dic.get('model_service')
        factor_list = self.config_dic.get('factors')

        if service is None or factor_list is None:
            raise RuntimeError

        factor_data = (' '.join([f'--data-urlencode {factor}="{{{factor}}}"' for factor in factor_list])).format_map(job_info)
        command = f'curl -m 3 {service} -s -X POST {factor_data}'
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        mem_predict = process.stdout.readlines()[-1]

        return int(mem_predict)

    def _gen_res_req(self, res_req: str, memory: int) -> str:
        if res_req.find('rusage') != -1:
            new_res_req = re.sub(r"rusage\[", f"rusage[mem={str(memory)}:", res_req)
        else:
            new_res_req = f"rusage[mem={str(memory)}]"

        return new_res_req

    def _gen_run_method(self, run_method: str, new_res_req: str, old_res_req: str) -> str:
        if not old_res_req:
            run_method = f'{run_method} -R "{new_res_req}"'
        else:
            run_method = run_method.replace(f'-R "{old_res_req}"', f'-R "{new_res_req}"')

        return run_method

