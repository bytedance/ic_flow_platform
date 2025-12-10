# -*- coding: utf-8 -*-
################################
# File Name   : parse_config.py
# Author      : jingfuyi
# Created On  : 2022-05-27 13:48:57
# Description :
################################
import datetime
import getpass
import keyword
import os
import pprint
import re
import sys
import traceback
from collections import abc
from typing import Dict, Tuple, List, Union

import yaml
import pickle

sys.path.append(str(os.environ['IFP_INSTALL_PATH']) + '/common')
import common


class IfpItem:
    def __init__(self, block, version, flow, task):
        self.Block = block
        self.Version = version
        self.Flow = flow
        self.Task = task.NAME
        self.uuid = common.generate_uuid_from_components(item_list=[self.Block, self.Version, self.Flow, self.Task])
        self.__visible_index = None
        self.__index = None
        self.__task = task
        self.item_list = ['Block', 'Version', 'Flow', 'Task']
        self.property_list = ['Visible', 'Selected', 'PATH', 'Status', 'Check', 'Summary', 'Job', 'Runtime', 'Xterm', 'BuildStatus', 'RunStatus', 'CheckStatus', 'SummarizeStatus', 'ReleaseStatus', 'Task_obj', 'uuid', 'visible_index', 'index']

    @property
    def visible_index(self):
        return self.__visible_index

    @visible_index.setter
    def visible_index(self, index: int):
        self.__visible_index = index

    @property
    def index(self):
        return self.__index

    @index.setter
    def index(self, index: int):
        self.__index = index

    @property
    def OriRunMode(self):
        return self.__task.OriRunMode

    @property
    def RunMode(self):
        return self.__task.RunMode

    @RunMode.setter
    def RunMode(self, val: str):
        run_mode = 'RUN' if val == 'default' else f'RUN.{val}'

        # Switch Run Mode
        self.__task.RunMode = run_mode

        # Modify Run Actions
        run_action = self.__task.RunInfo[run_mode]

        for action_attr in ['XTERM_COMMAND', 'PATH', 'COMMAND', 'RUN_METHOD', 'VIEWER', 'REPORT_FILE', 'REQUIRED_LICENSE']:
            if action_attr in run_action:
                self.__task.ACTION.setdefault('RUN', {})

                if run_action[action_attr]:
                    self.__task.ACTION['RUN'][action_attr] = run_action[action_attr]
                else:
                    self.__task.ACTION['RUN'][action_attr] = self.__task.DefaultSetting.get('RUN', {}).get(action_attr, '')

    @property
    def RunModes(self) -> List[str]:
        return list([item.replace('RUN.', '') if re.match(r'^RUN\.\S+$', item) else 'default' for item in self.__task.RunInfo.keys()])

    @property
    def Visible(self):
        return self.__task.Visible

    @Visible.setter
    def Visible(self, val):
        self.__task.Visible = val

    @property
    def Status(self):
        return self.__task.Status

    @Status.setter
    def Status(self, val):
        self.__task.Status = val

    @property
    def BuildStatus(self):
        return self.__task.BuildStatus

    @BuildStatus.setter
    def BuildStatus(self, val):
        self.__task.BuildStatus = val

    @property
    def RunStatus(self):
        return self.__task.RunStatus

    @RunStatus.setter
    def RunStatus(self, val):
        self.__task.RunStatus = val

    @property
    def CheckStatus(self):
        return self.__task.CheckStatus

    @CheckStatus.setter
    def CheckStatus(self, val):
        self.__task.CheckStatus = val

    @property
    def SummarizeStatus(self):
        return self.__task.SummarizeStatus

    @SummarizeStatus.setter
    def SummarizeStatus(self, val):
        self.__task.SummarizeStatus = val

    @property
    def ReleaseStatus(self):
        return self.__task.ReleaseStatus

    @ReleaseStatus.setter
    def ReleaseStatus(self, val):
        self.__task.ReleaseStatus = val

    @property
    def Job(self):
        return self.__task.Job

    @Job.setter
    def Job(self, val):
        self.__task.Job = val

    @property
    def Runtime(self):
        return self.__task.Runtime

    @Runtime.setter
    def Runtime(self, val):
        self.__task.Runtime = val

    @property
    def Selected(self):
        return self.__task.Selected

    @Selected.setter
    def Selected(self, val):
        self.__task.Selected = val

    @property
    def Check(self):
        return self.__task.Check

    @Check.setter
    def Check(self, val):
        self.__task.Check = val

    @property
    def Summary(self):
        return self.__task.Summary

    @Summary.setter
    def Summary(self, val):
        self.__task.Summary = val

    @property
    def Xterm(self):
        return self.__task.Xterm

    @Xterm.setter
    def Xterm(self, val):
        self.__task.Xterm = val

    def __getitem__(self, key):
        if key in self.item_list:
            return self.__dict__[key]
        elif key in self.property_list:
            return self.__task.__dict__[key]
        else:
            raise KeyError(key)

    def get(self, key, default=None):
        try:
            return self.__getitem__(key)
        except Exception:
            return default

    def __setitem__(self, key, val):
        if key in self.item_list:
            self.__dict__[key] = val
        elif key in self.property_list:
            self.__task.__dict__[key] = val
        else:
            raise KeyError(key)

    def as_dict(self):
        dic = {}

        for key in self.item_list:
            dic.update({key: self.__dict__[key]})

        for key in self.property_list:
            dic.update({key: self.__task.__dict__[key]})

        return dic

    def __repr__(self):
        return str(self.as_dict())


class Common:
    def __init__(self, name, *args, **kwargs):
        # 'NAME' is the default attributes.
        self.NAME, parentheses_setting = get_parentheses_setting(name)
        self.Visible = True
        self.__dict__.update({**parentheses_setting})

    def __repr__(self):
        dic = {}

        for k, v in self.__dict__.items():
            if k.startswith('_'):
                continue

            dic[k] = v

        return str(dic)

    def update_field(self, field_obj):
        field_name = field_obj.__class__.__name__.upper()

        if not hasattr(self, field_name):
            self.__dict__[field_name] = {}

        self.__dict__[field_name].update({field_obj.NAME: field_obj})

        if self.__class__.__name__ == 'Task':
            self.__dict__.update({field_obj.NAME: field_obj})


class Block(Common):
    def __init__(self, name):
        super().__init__(name)
        self.VERSION = {}


class Version(Common):
    def __init__(self, name):
        super().__init__(name)
        self.FLOW = {}


class Flow(Common):
    def __init__(self, name):
        super().__init__(name)
        self.TASK = {}


class Task(Common):
    def __init__(self, name):
        super().__init__(name)
        self.ACTION = {}
        self.RUN_AFTER = {'TASK': ''}
        self.DEPENDENCY = {'FILE': [], 'LICENSE': []}
        self.TASK_ORDER = ''
        self.RunInfo = {'RUN': {}}  # Recording RUN* -> RUN* Configure
        self.RunMode = 'RUN'  # Current RunMode
        self.OriRunMode = 'RUN'  # Default RunMode
        self.InProcessCheck = None
        self.Selected = False
        self.PATH = None
        self.Status = None
        self.BuildStatus = None
        self.RunStatus = None
        self.CheckStatus = None
        self.SummarizeStatus = None
        self.ReleaseStatus = None
        self.Check = None
        self.Summary = None
        self.Job = None
        self.Runtime = None
        self.Xterm = None
        self.DefaultSetting = None
        self.UserSetting = None
        self.property_list = ['Visible', 'Selected', 'PATH', 'Status', 'Check', 'Summary', 'Job', 'Runtime', 'Xterm', 'BuildStatus', 'RunStatus', 'CheckStatus', 'SummarizeStatus', 'ReleaseStatus']

    def get(self, key, default=None):
        try:
            return self.__getitem__(key)
        except Exception:
            return default

    def __getitem__(self, key):
        try:
            return self.__dict__[key]
        except Exception:
            raise KeyError(key)

    def __setitem__(self, key, val):
        if key in self.property_list:
            self.__task.__dict__[key] = val
        else:
            raise KeyError(key)


class TaskConfig:
    def __init__(self, mapping):
        self._data = {}

        # Avoiding keyword in python
        for key, value in mapping.items():
            if keyword.iskeyword(key):
                key += '_'

            self._data[key] = value

    def __getattr__(self, name: str):
        if hasattr(self._data, name):
            return getattr(self._data, name)
        else:
            # raise AttributeError instead of KeyError
            try:
                return self._build(self._data[name])
            except KeyError:
                raise AttributeError

    def __repr__(self):
        return pprint.pformat(self._data, indent=4)

    @classmethod
    def _build(cls, obj):
        if isinstance(obj, abc.Mapping):
            return cls(obj)
        elif isinstance(obj, abc.MutableMapping):
            return [cls._build(item) for item in obj]
        else:
            return obj

    @staticmethod
    def get_template() -> Dict[str, Union[Dict[str, Union[str, None]], str, None]]:
        template_mapping = {
            'COMMON':
                {
                    'XTERM_COMMAND': None
                },
            'BUILD':
                {
                    'PATH': None,
                    'COMMAND': None,
                    'RUN_METHOD': None,
                },
            'RUN':
                {
                    'PATH': None,
                    'COMMAND': None,
                    'RUN_METHOD': None,
                    'LOG': None,
                },
            'CHECK':
                {
                    'PATH': None,
                    'COMMAND': None,
                    'RUN_METHOD': None,
                    'VIEWER': None,
                    'REPORT_FILE': None,
                },
            'SUMMARIZE':
                {
                    'PATH': None,
                    'COMMAND': None,
                    'RUN_METHOD': None,
                    'VIEWER': None,
                    'REPORT_FILE': None,
                },
            'RELEASE':
                {
                    'PATH': None,
                    'COMMAND': None,
                    'RUN_METHOD': None,
                },
            'DEPENDENCY':
                {
                    'LICENSE': None,
                    'FILE': None,
                },
            'RUN_AFTER':
                {
                    'TASK': None
                },
            'RUN_MODE': None
        }
        return template_mapping

    @staticmethod
    def get_nested_value(nested_dict, keys_list):
        current_value = nested_dict
        for key in keys_list:
            if isinstance(current_value, dict) and key in current_value:
                current_value = current_value[key]
            else:
                return None
        return current_value

    def get_definition(self, what_is_this: str) -> Union[None, str]:
        what_is_this_list = [item.strip() for item in what_is_this.split()]
        definition = self.get_nested_value(self._data, what_is_this_list)
        return definition


class Config:
    _instance = None
    """
    This class is used to parse a configure file into a Object.
    Below is the data structure.
    >>> c = Config('test.yaml')
    >>> c.PROJECT
    'project_name'
    >>> c.BLOCK.keys()
    dict_keys(['block1', 'block2'])
    >>> c.BLOCK['block1'].VERSION.keys()
    dict_keys(['block1_versionA', 'block1_versionB'])
    >>> c.BLOCK['block2'].VERSION.keys()
    dict_keys(['block2_version'])
    >>> c.BLOCK['block1'].VERSION['block1_versionA'].FLOW.keys()
    dict_keys(['flow1', 'flow2'])
    >>> c.BLOCK['block1'].VERSION['block1_versionA'].FLOW['flow1'].TASK.keys()
    dict_keys(['task1'])
    >>> c.BLOCK['block1'].VERSION['block1_versionA'].FLOW['flow1'].TASK['task1'].RUN_AFTER
    >>> c.BLOCK['block1'].VERSION['block1_versionA'].FLOW['flow1'].TASK['task1'].ACTION.keys()
    dict_keys(['COMMON', 'BUILD', 'RUN', 'CHECK', 'SUMMARIZE', 'RELEASE'])
    >>> c.BLOCK['block1'].VERSION['block1_versionA'].FLOW['flow1'].TASK['task1'].ACTION['BUILD']
    {'NAME': 'BUILD', 'COMMAND': 'task1_build_cmd', 'PATH': 'CWD'}
    >>> c.BLOCK['block1'].VERSION['block1_versionA'].FLOW['flow1'].TASK['task1'].PATH
    'CWD'
    >>> table_list = c.main_table_info_list
    >>> len(table_list)
    5
    >>> table_list[0]['Block']
    'block1'
    """

    def __new__(cls, *args, **kwargs):
        """
        Singleton mode.
        """
        if not cls._instance:
            cls._instance = super(Config, cls).__new__(cls)
        return cls._instance

    def __init__(self, config_file):
        if config_file is not None:
            self.get_config_obj(config_file)

    @staticmethod
    def parse_config_file(config_file, kind='user') -> dict:
        config_dic = {}

        if not config_file:
            return config_dic

        if os.path.exists(config_file):
            with open(config_file, 'r') as fh:
                config_dic = yaml.load(fh, Loader=yaml.FullLoader)

            if not config_dic:
                config_dic = {}
            else:
                if kind == 'user':
                    if ('PROJECT' not in config_dic) or (not config_dic['PROJECT']):
                        config_dic['PROJECT'] = ''

                    if ('GROUP' not in config_dic) or (not config_dic['GROUP']):
                        config_dic['GROUP'] = ''

                    if ('VAR' not in config_dic) or (not config_dic['VAR']):
                        config_dic['VAR'] = {}

                    if ('BLOCK' not in config_dic) or (not config_dic['BLOCK']):
                        config_dic['BLOCK'] = {}

        return config_dic

    def get_config_obj(self, config_file):
        # self.PROJECT saves project information from user config file.
        self.PROJECT = ''
        self.GROUP = ''
        self.default_config_file = ''
        self.api_yaml = ''
        self.default_config_file_mtime = datetime.datetime.strptime('2100-01-01', '%Y-%m-%d')
        self.api_file_mtime = datetime.datetime.strptime('2100-01-01', '%Y-%m-%d')
        # self.var_dic saves all VAR settings from user config file.
        cache_file_path = os.path.join(os.getcwd(), common.gen_cache_file_name(os.path.basename(config_file))[0])
        self.var_dic = {'IFP_INSTALL_PATH': os.environ['IFP_INSTALL_PATH'],
                        'CWD': common.CWD,
                        'IFP_CONFIG_FILE': os.path.abspath(config_file),
                        'IFP_STATUS_FILE': cache_file_path
                        }
        # self.block_dic saves all block configuration information.
        self.block_dic = {}
        # self.task_dic saves all task configuration information.
        self.task_dic = {}
        self.current_config_file = config_file

        # Parse user config file. (With parallel tasks)
        self.user_config_dic = self.parse_config_file(config_file, kind='user')

        if self.user_config_dic:
            if 'PROJECT' in self.user_config_dic:
                self.PROJECT = self.user_config_dic['PROJECT'].strip()

            if 'GROUP' in self.user_config_dic:
                self.GROUP = self.user_config_dic['GROUP'].strip()

            if 'DEFAULT_YAML' in self.user_config_dic:
                self.default_config_file = self.user_config_dic['DEFAULT_YAML'].strip()

            if 'API_YAML' in self.user_config_dic:
                self.api_yaml = self.find_available_api_yaml(config_file)

            try:
                if os.path.exists(self.default_config_file):
                    self.default_config_file_mtime = datetime.datetime.fromtimestamp(os.path.getmtime(self.default_config_file))

                if os.path.exists(self.api_yaml):
                    self.api_file_mtime = datetime.datetime.fromtimestamp(os.path.getmtime(self.api_yaml))
            except Exception:
                pass

        # Parse default config file.
        if self.default_config_file:
            pass
        else:
            self.default_config_file = common.get_default_yaml_path(self.PROJECT, self.GROUP)

        if self.api_yaml:
            pass
        else:
            self.api_yaml = common.get_default_yaml_path(self.PROJECT, self.GROUP, key_word='api')

        # self.var_dic saves all VAR settings from env VAR
        self.env_dic = common.get_env_dic(project=self.PROJECT, group=self.GROUP)
        self.var_dic.update(self.env_dic)

        self.default_config_dic = {}

        if os.path.exists(self.default_config_file):
            self.default_config_dic = self.parse_config_file(self.default_config_file, kind='default')
            # default_config_dic = self.filter_dependency(default_config_dic)

            if ('VAR' in self.default_config_dic) and isinstance(self.default_config_dic['VAR'], dict):
                for (key, value) in self.default_config_dic['VAR'].items():
                    if key == 'MAX_RUNNING_JOBS':
                        if isinstance(value, str) and value.isdigit():
                            self.var_dic[key] = value
                        elif isinstance(value, int):
                            self.var_dic[key] = str(value)
                            self.default_config_dic['VAR']['MAX_RUNNING_JOBS'] = str(value)
                    elif isinstance(value, str) or isinstance(value, int) or isinstance(value, float):
                        self.var_dic[key] = value

        if self.user_config_dic:
            self.var_dic['PROJECT'] = self.PROJECT
            self.var_dic['GROUP'] = self.GROUP

            if ('VAR' in self.user_config_dic) and isinstance(self.user_config_dic['VAR'], dict):
                for (key, value) in self.user_config_dic['VAR'].items():
                    if key == 'MAX_RUNNING_JOBS':
                        if isinstance(value, str) and value.isdigit():
                            self.var_dic[key] = value
                        elif isinstance(value, int):
                            self.var_dic[key] = str(value)
                            self.user_config_dic['VAR']['MAX_RUNNING_JOBS'] = str(value)
                    elif isinstance(value, str) or isinstance(value, int) or isinstance(value, float):
                        self.var_dic[key] = value

            if ('BLOCK' in self.user_config_dic) and self.user_config_dic['BLOCK']:
                for block in self.user_config_dic['BLOCK'].keys():
                    block_obj = Block(block)

                    if self.user_config_dic['BLOCK'][block]:
                        for version in self.user_config_dic['BLOCK'][block].keys():
                            version_obj = Version(version)
                            flows = []

                            if self.user_config_dic['BLOCK'][block][version]:
                                for flow in self.user_config_dic['BLOCK'][block][version].keys():
                                    flows.append(flow)
                                    flow_obj = Flow(flow)

                                    if self.user_config_dic['BLOCK'][block][version][flow]:
                                        for task in self.user_config_dic['BLOCK'][block][version][flow].keys():
                                            task_obj = Task(task)
                                            user_task_dic = self.user_config_dic['BLOCK'][block][version][flow][task]
                                            default_task_dic = self.default_config_dic.get('TASK', {}).get(task, {})

                                            # Update task_obj task attribute with default config file settings.
                                            default_task_obj = self.update_task(task_config=default_task_dic, task=task_obj, mode='default')

                                            # Update task_obj task attribute with default config file settings.
                                            task_obj = self.update_task(task_config=user_task_dic, task=default_task_obj, mode='user')

                                            # Set task_obj.PATH.
                                            if not task_obj.PATH:
                                                if ('RUN' in task_obj.ACTION) and ('PATH' in task_obj.ACTION['RUN']):
                                                    task_obj.PATH = task_obj.ACTION['RUN']['PATH']
                                                elif ('BUILD' in task_obj.ACTION) and ('PATH' in task_obj.ACTION['BUILD']):
                                                    task_obj.PATH = task_obj.ACTION['BUILD']['PATH']
                                                else:
                                                    task_obj.PATH = common.CWD

                                            # Update self.task_dic.
                                            self.task_dic.update({'{} {} {} {}'.format(block_obj.NAME, version_obj.NAME, flow_obj.NAME, task_obj.NAME): task_obj})

                                            flow_obj.update_field(task_obj)

                                        version_obj.update_field(flow_obj)

                                block_obj.update_field(version_obj)

                        self.block_dic.update({block: block_obj})

        for attr in self.var_dic.keys():
            self.var_dic[attr] = common.expand_var(self.var_dic[attr], ifp_var_dic=self.var_dic, show_warning=False)

    def find_available_api_yaml(self, config_file: str) -> str:
        api_yaml = self.user_config_dic['API_YAML'].strip()

        if os.path.exists(api_yaml) and os.access(api_yaml, os.R_OK):
            return api_yaml

        api_yaml = os.path.join(os.path.dirname(config_file), f'.ifp/config/{os.path.basename(config_file)}')

        if os.path.exists(api_yaml) and os.access(api_yaml, os.R_OK):
            return api_yaml

        api_yaml = common.get_default_yaml_path(project=self.PROJECT, group=self.GROUP, key_word='api')

        if os.path.exists(api_yaml) and os.access(api_yaml, os.R_OK):
            return api_yaml

        return ''

    def update_task(self, task_config: dict, task: Task, mode: str = 'default') -> Task:
        if not isinstance(task_config, dict):
            return task

        template_config = TaskConfig.get_template()

        for item in task_config.keys():
            #  Template config
            if isinstance(task_config[item], str):
                template_config[item] = task_config[item]
            elif isinstance(task_config[item], dict):
                if item not in template_config:
                    template_config.setdefault(item, {})

                for key, value in task_config[item].items():
                    template_config[item][key] = value

            if item in ['COMMON', 'BUILD', 'CHECK', 'SUMMARIZE', 'RELEASE']:
                default_action_dic = task_config.get(item, {})

                if default_action_dic:
                    for action_attr in ['XTERM_COMMAND', 'PATH', 'COMMAND', 'RUN_METHOD', 'VIEWER', 'REPORT_FILE', 'REQUIRED_LICENSE']:
                        if (action_attr in default_action_dic) and (default_action_dic[action_attr]):
                            task.ACTION.setdefault(item, {})
                            task.ACTION[item][action_attr] = default_action_dic[action_attr]

            if item in ['RUN_AFTER']:
                task.RUN_AFTER = task_config[item]
                task.TASK_ORDER = task_config[item].get('TASK', '')

            if item in ['DEPENDENCY']:
                task.DEPENDENCY = task_config[item]

            if item in ['RUN_MODE']:
                task.RunMode = (common.expand_var(task_config[item], ifp_var_dic=self.var_dic)).strip()
                task.OriRunMode = (common.expand_var(task_config[item], ifp_var_dic=self.var_dic)).strip()

            if re.match(r'^RUN(?:\.(\w+))?$', item):
                task.RunInfo[item] = task_config[item]

            if item == 'IN_PROCESS_CHECK':
                task.InProcessCheck = task_config[item]

        # For Action: Run
        run_action = task.RunInfo.get(task.RunMode, {})

        for action_attr in ['XTERM_COMMAND', 'PATH', 'COMMAND', 'LOG', 'RUN_METHOD', 'VIEWER', 'REPORT_FILE', 'REQUIRED_LICENSE']:
            if (action_attr in run_action) and run_action[action_attr]:
                task.ACTION.setdefault('RUN', {})
                task.ACTION['RUN'][action_attr] = run_action[action_attr]

        for item in template_config.keys():
            if re.match(r'^RUN(?:\.(\w+))?$', item) and item != 'RUN':
                for action_attr in ['XTERM_COMMAND', 'PATH', 'COMMAND', 'LOG', 'RUN_METHOD', 'VIEWER', 'REPORT_FILE', 'REQUIRED_LICENSE']:
                    if action_attr not in template_config[item]:
                        if mode == 'default':
                            value = task_config.get('RUN', {}).get(action_attr, '')
                            template_config[item][action_attr] = value
                            task.RunInfo[item][action_attr] = value
                        elif mode == 'user':
                            value = task_config.get('RUN', {}).get(action_attr, '')

                            if not value:
                                value = task.DefaultSetting.get('RUN', {}).get(action_attr, '')

                            template_config[item][action_attr] = value
                            task.RunInfo[item][action_attr] = value

        task_config_obj = TaskConfig(template_config)

        if mode == 'default':
            task.DefaultSetting = task_config_obj
        elif mode == 'user':
            task.UserSetting = task_config_obj

        return task

    @property
    def main_table_info_list(self):
        # self.__item_list is a list, save some class 'IfpItem'.
        # One IfpItem means one line on IFP GUI.
        self.__item_list = []
        self.main_table_item_dic = {}
        visible_index = -1
        index = -1

        if self.block_dic:
            for block in self.block_dic.values():
                if block.VERSION:
                    for version in block.VERSION.values():
                        if version.FLOW:
                            for flow in version.FLOW.values():
                                if flow.TASK:
                                    for task in flow.TASK.values():
                                        item = IfpItem(block.NAME, version.NAME, flow.NAME, task)

                                        if item.Visible:
                                            visible_index += 1

                                        index += 1

                                        item.visible_index = visible_index
                                        item.index = index
                                        self.__item_list.append(item)
                                        self.main_table_item_dic[item.uuid] = item

        return self.__item_list

    @property
    def table_visible_status(self) -> Dict[Tuple[int, int], bool]:
        visible_dic = {}
        row = 0

        if self.block_dic:
            for block in self.block_dic.values():
                visible_dic[(row, 0)] = block.Visible

                if block.VERSION:
                    for version in block.VERSION.values():
                        visible_dic[(row, 1)] = version.Visible

                        if version.FLOW:
                            for flow in version.FLOW.values():
                                visible_dic[(row, 2)] = flow.Visible

                                if flow.TASK:
                                    for task in flow.TASK.values():
                                        visible_dic[(row, 3)] = task.Visible
                                        row += 1

        return visible_dic

    @property
    def default_task_setting(self) -> common.AutoVivification:
        task_setting = common.AutoVivification()

        if 'TASK' in self.default_config_dic:
            task_setting.update(self.default_config_dic['TASK'])

        return task_setting

    @property
    def default_var_setting(self) -> common.AutoVivification:
        var_setting = common.AutoVivification()

        if 'VAR' in self.default_config_dic:
            var_setting.update(self.default_config_dic['VAR'])

        return var_setting

    @property
    def default_flow_setting(self) -> common.AutoVivification:
        flow_setting = common.AutoVivification()

        if 'FLOW' in self.default_config_dic:
            flow_setting.update(self.default_config_dic['FLOW'])

        return flow_setting

    @property
    def default_dependency_setting(self) -> Dict[str, str]:
        return {task: self.default_task_setting[task].get('RUN_AFTER', {}).get('TASK', '') for task in self.default_task_setting}

    @property
    def user_task_setting(self) -> common.AutoVivification:
        task_setting = common.AutoVivification()

        if 'BLOCK' in self.user_config_dic:
            task_setting.update(self.user_config_dic['BLOCK'])

        task_setting = common.convert_to_autovivification(task_setting)

        return task_setting

    @property
    def user_var_setting(self) -> common.AutoVivification:
        var_setting = common.AutoVivification()

        if 'VAR' in self.user_config_dic:
            var_setting.update(self.user_config_dic['VAR'])
        return var_setting

    @property
    def real_task_dependency(self) -> Dict[str, Dict[str, Dict[str, str]]]:
        dependency_priority = {}

        if self.block_dic:
            for block in self.block_dic.values():
                dependency_priority.setdefault(block.NAME, {})

                if block.VERSION:
                    for version in block.VERSION.values():
                        dependency_priority[block.NAME].setdefault(version.NAME, {})

                        if version.FLOW:
                            for flow in version.FLOW.values():

                                if flow.TASK:
                                    for task in flow.TASK.values():
                                        dependency_priority[block.NAME][version.NAME][task.NAME] = task.TASK_ORDER

        return dependency_priority

    def update_batch_visible(self, view_status: Dict[str, Dict[str, bool]]):
        if self.block_dic:
            for block in self.block_dic.values():
                block.Visible = view_status['block'][block.NAME]

                if block.VERSION:
                    for version in block.VERSION.values():
                        if version.FLOW:
                            for flow in version.FLOW.values():
                                if flow.TASK:
                                    for task in flow.TASK.values():
                                        if block.Visible:
                                            task.Visible = view_status['task'][task.NAME]
                                        else:
                                            task.Visible = block.Visible

    @property
    def config_dic(self):
        config_dic = {'PROJECT': self.PROJECT,
                      'GROUP': self.GROUP,
                      'VAR': self.var_dic,
                      'BLOCK': {}}

        if self.block_dic:
            for block in self.block_dic.values():
                config_dic['BLOCK'].update({block.NAME: {}})

                if block.VERSION:
                    for version in block.VERSION.values():
                        config_dic['BLOCK'][block.NAME].update({version.NAME: {}})

                        if version.FLOW:
                            for flow in version.FLOW.values():
                                config_dic['BLOCK'][block.NAME][version.NAME].update({flow.NAME: {}})

                                if flow.TASK:
                                    for task in flow.TASK.values():
                                        self.update = config_dic['BLOCK'][block.NAME][version.NAME][flow.NAME].update({task.NAME: task})

        return config_dic

    def update_for_read_mode(self, cwd: str, user: str):
        self.var_dic.update({'USER': user,
                             'CWD': cwd})

    def __repr__(self):
        return str({
            'PROJECT': self.PROJECT,
            'VAR': self.var_dic,
            'BLOCK': self.block_dic
        })

    def update_task_field(self, block, version, flow, task_name, field, field_value):
        task_obj = self.get_task(block, version, flow, task_name)

        if not hasattr(task_obj, field):
            raise Exception('*Error*: Task has no attribute {}'.format(field))

        task_obj.__dict__[field] = field_value

    def get_task(self, block, version, flow, task_name) -> Task:
        query = '{} {} {} {}'.format(block, version, flow, task_name)
        task_obj = self.task_dic.get(query, None)

        if not task_obj:
            raise Exception('*Error*: No task found for {}'.format(query))

        return task_obj

    def get_block_task_list(self, block: str) -> List[Task]:
        task_list = []

        if self.block_dic:
            for block_obj in self.block_dic.values():
                if block_obj.NAME != block:
                    continue

                if block_obj.VERSION:
                    for version_obj in block_obj.VERSION.values():
                        if version_obj.FLOW:
                            for flow_obj in version_obj.FLOW.values():
                                if flow_obj.TASK:
                                    for task_obj in flow_obj.TASK.values():
                                        task_list.append(task_obj)

        return task_list

    def restore_task_info(self, session_file):
        with open(session_file, 'rb') as fh:
            restored_item_list = pickle.load(fh)

            for i_in_cur_session in self.__item_list:
                block = i_in_cur_session.Block
                version = i_in_cur_session.Version
                flow = i_in_cur_session.Flow
                task = i_in_cur_session.Task

                for i in restored_item_list:
                    if block == i.Block and version == i.Version and flow == i.Flow and task == i.Task:
                        i_in_cur_session.Status = i.Status
                        i_in_cur_session.Runtime = i.Runtime
                        i_in_cur_session.Job = i.Job
                        break

    def save_ifp_records(self):
        project = 'UNKNOWN' if not self.PROJECT else self.PROJECT

        data_dic = {'user': getpass.getuser(),
                    'file_path': self.current_config_file,
                    'group': self.GROUP,
                    'project': project,
                    'blocks': []
                    }

        if self.block_dic:
            for block in self.block_dic.values():
                block_dic = {'block_id': block.NAME,
                             'versions': []}

                if block.VERSION:
                    for version in block.VERSION.values():
                        block_dic['versions'].append({'version_id': version.NAME})

                data_dic['blocks'].append(block_dic)

        try:
            sys.path.append(str(os.environ['IFP_INSTALL_PATH']) + '/common')
            import common_nosql_db
            common_nosql_db.save_ifp_records(data_dic=data_dic)
        except Exception as error:
            print(str(error))
            print(traceback.format_exc())


def get_parentheses_setting(setting_str):
    setting_str = str(setting_str)
    setting_wo_parentheses = setting_str
    setting = {}
    pat = re.compile(r'^.*\((.*)\)$')
    match = pat.match(setting_str)

    if match:
        vals = match.group(1)
        setting_wo_parentheses = setting_str[:-len('({})'.format(vals))]
        vals = vals.strip()

        try:
            for pair in vals.split(';'):
                key, val = pair.split('=')

                if str(val) == 'True':
                    val = True
                if str(val) == 'False':
                    val = False

                setting[key] = val
        except Exception:
            common.print_error('*Error*: wrong setting as {}'.format(setting_str))
            sys.exit(1)

    return setting_wo_parentheses, setting
