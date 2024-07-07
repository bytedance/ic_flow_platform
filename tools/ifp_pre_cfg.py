import datetime
import os
import sys
import yaml

os.environ['PYTHONUNBUFFERED'] = '1'

sys.path.append(str(os.environ['IFP_INSTALL_PATH']) + '/common')
import common

################
# Main Process #
################
def main():
    if os.environ.get('IFP_DEMO_MODE', 'FALSE') == 'TRUE':
        CWD = os.getcwd()
        USER = os.popen('whoami').read().strip()
        common.bprint('Execute IFP API (PRE_CFG) function to generate demo case database!', level='Info', color=37, background_color=44, display_method=1)
        common.bprint('USER : %s' % USER, level='Info', color=37, background_color=44, display_method=1)
        common.bprint('PROJECT : demo', level='Info', color=37, background_color=44, display_method=1)
        common.bprint('GROUP : dv', level='Info', color=37, background_color=44, display_method=1)
        ifp_cfg_yaml = '%s/ifp.cfg.yaml' % CWD
        project = 'demo'
        ifp_cfg_dict = {'VAR': {'BSUB_QUEUE': 'normal', 'DEMO_PATH': '%s/demo' % str(os.environ['IFP_INSTALL_PATH'])},
                        'BLOCK': {},
                        'PROJECT': project,
                        'GROUP': 'dv',
                        'DEFAULT_YAML': '%s/config/default.demo.dv.yaml' % str(os.environ['IFP_INSTALL_PATH']),
                        'API_YAML': '%s/config/api.demo.dv.yaml' % str(os.environ['IFP_INSTALL_PATH'])}
        block_version = 'RTL_A_Bench_1'
        ifp_cfg_dict['BLOCK'].setdefault(project, {})
        ifp_cfg_dict['BLOCK'][project].setdefault(block_version, {})

        with open('%s/config/default.demo.dv.yaml' % str(os.environ['IFP_INSTALL_PATH']), 'rb') as SF:
            default_yaml_dict = yaml.load(SF, Loader=yaml.FullLoader)

        branch = datetime.datetime.now().strftime('%Y_%m_%d')

        for item in default_yaml_dict['TASK'].keys():
            flow = item.split(':')[0]
            vendor = item.split(':')[1]
            task = item.split(':')[2]
            if flow not in ifp_cfg_dict['BLOCK'][project].keys():
                ifp_cfg_dict['BLOCK'][project][block_version].setdefault(flow, {})

            if vendor not in ifp_cfg_dict['BLOCK'][project][block_version][flow].keys():
                ifp_cfg_dict['BLOCK'][project][block_version][flow].setdefault(vendor, {})

            if branch not in ifp_cfg_dict['BLOCK'][project][block_version][flow][vendor].keys():
                ifp_cfg_dict['BLOCK'][project][block_version][flow][vendor].setdefault(branch, {})

            if task not in ifp_cfg_dict['BLOCK'][project][block_version][flow][vendor][branch].keys():
                ifp_cfg_dict['BLOCK'][project][block_version][flow][vendor][branch].setdefault(task, {})

        with open(ifp_cfg_yaml, 'w', encoding='utf-8') as SF:
            yaml.dump(ifp_cfg_dict, SF, indent=4, sort_keys=False)

if __name__ == '__main__':
    main()
