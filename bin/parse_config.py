# -*- coding: utf-8 -*-
################################
# File Name   : parse_config.py
# Author      : jingfuyi
# Created On  : 2022-05-27 13:48:57
# Description :
################################
import os
import re
import sys
import yaml
import pickle

sys.path.append(str(os.environ['IFP_INSTALL_PATH']) + '/common')
import common

CWD = os.getcwd()


class Config:
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
        obj = getattr(cls, '__instance__', None)

        if not obj:
            obj = object.__new__(cls)
            cls.__instance__ = obj

        return obj

    def __init__(self, config_file):
        self.get_config_obj(config_file)

    @staticmethod
    def parse_config_file(config_file, kind='user'):
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
        # self.var_dic saves all VAR settings from user config file.
        self.var_dic = {'IFP_INSTALL_PATH': os.environ['IFP_INSTALL_PATH'],
                        'CWD': CWD}
        # self.block_dic saves all block configuration information.
        self.block_dic = {}
        # self.task_dic saves all task configuration information.
        self.task_dic = {}

        # Parse user config file. (With parallel tasks)
        user_config_dic = self.parse_config_file(config_file, kind='user')

        if user_config_dic:
            if 'PROJECT' in user_config_dic:
                self.PROJECT = user_config_dic['PROJECT']

            if 'GROUP' in user_config_dic:
                self.GROUP = user_config_dic['GROUP']

            if 'DEFAULT_YAML' in user_config_dic:
                self.default_config_file = user_config_dic['DEFAULT_YAML']

            if 'API_YAML' in user_config_dic:
                self.api_yaml = user_config_dic['API_YAML']

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
                    if isinstance(value, str) or isinstance(value, int) or isinstance(value, float):
                        self.var_dic[key] = value

        if user_config_dic:
            self.var_dic['PROJECT'] = self.PROJECT
            self.var_dic['GROUP'] = self.GROUP

            if ('VAR' in user_config_dic) and isinstance(user_config_dic['VAR'], dict):
                for (key, value) in user_config_dic['VAR'].items():
                    if isinstance(value, str) or isinstance(value, int) or isinstance(value, float):
                        self.var_dic[key] = value

            if ('BLOCK' in user_config_dic) and user_config_dic['BLOCK']:
                for block in user_config_dic['BLOCK'].keys():
                    block_obj = Block(block)

                    if user_config_dic['BLOCK'][block]:
                        for version in user_config_dic['BLOCK'][block].keys():
                            version_obj = Version(version)
                            flows = []

                            if user_config_dic['BLOCK'][block][version]:
                                for flow in user_config_dic['BLOCK'][block][version].keys():
                                    flows.append(flow)
                                    flow_obj = Flow(flow)

                                    if user_config_dic['BLOCK'][block][version][flow]:
                                        for task in user_config_dic['BLOCK'][block][version][flow].keys():
                                            task_obj = Task(task)
                                            user_task_dic = user_config_dic['BLOCK'][block][version][flow][task]
                                            # Update task_obj task attribute with default config file settings.
                                            if self.default_config_dic:
                                                # Get task information from default.yaml.
                                                if 'TASK' in self.default_config_dic:
                                                    task_mark = str(task_obj.NAME)

                                                    if self.default_config_dic['TASK'] and (task_mark in self.default_config_dic['TASK']) and self.default_config_dic['TASK'][task_mark]:
                                                        for action in self.default_config_dic['TASK'][task_mark].keys():
                                                            if action in ['COMMON', 'BUILD', 'RUN', 'CHECK', 'SUMMARIZE', 'RELEASE']:
                                                                default_action_dic = self.default_config_dic['TASK'][task_mark].get(action, {})

                                                                if default_action_dic:
                                                                    for action_attr in ['XTERM_COMMAND', 'PATH', 'COMMAND', 'RUN_METHOD', 'VIEWER', 'REPORT_FILE', 'REQUIRED_LICENSE']:
                                                                        if (action_attr in default_action_dic) and (default_action_dic[action_attr]):
                                                                            task_obj.ACTION.setdefault(action, {})
                                                                            task_obj.ACTION[action][action_attr] = default_action_dic[action_attr]

                                                        for para in self.default_config_dic['TASK'][task_mark].keys():
                                                            if para in ['RUN_AFTER']:
                                                                task_obj.RUN_AFTER = self.default_config_dic['TASK'][task_mark][para]

                                                        for para in self.default_config_dic['TASK'][task_mark].keys():
                                                            if para in ['DEPENDENCY']:
                                                                task_obj.DEPENDENCY = self.default_config_dic['TASK'][task_mark][para]

                                            # Re-write task_obj task attribute with user configuration.
                                            if user_task_dic and isinstance(user_task_dic, dict):
                                                for action in user_task_dic.keys():
                                                    if action in ['COMMON', 'BUILD', 'RUN', 'CHECK', 'SUMMARIZE', 'RELEASE']:
                                                        for action_attr in ['XTERM_COMMAND', 'PATH', 'COMMAND', 'RUN_METHOD', 'VIEWER', 'REPORT_FILE', 'REQUIRED_LICENSE']:
                                                            if (action_attr in user_task_dic[action]) and user_task_dic[action][action_attr]:
                                                                task_obj.ACTION.setdefault(action, {})
                                                                task_obj.ACTION[action][action_attr] = user_task_dic[action][action_attr]

                                                for para in user_task_dic.keys():
                                                    if para in ['RUN_AFTER']:
                                                        task_obj.RUN_AFTER = user_task_dic[para]

                                                for para in user_task_dic.keys():
                                                    if para in ['DEPENDENCY']:
                                                        task_obj.DEPENDENCY = user_task_dic[para]

                                            # Set task_obj.PATH.
                                            if not task_obj.PATH:
                                                if ('RUN' in task_obj.ACTION) and ('PATH' in task_obj.ACTION['RUN']):
                                                    task_obj.PATH = task_obj.ACTION['RUN']['PATH']
                                                elif ('BUILD' in task_obj.ACTION) and ('PATH' in task_obj.ACTION['BUILD']):
                                                    task_obj.PATH = task_obj.ACTION['BUILD']['PATH']
                                                else:
                                                    task_obj.PATH = CWD

                                            # Check task_obj.ACTION.
                                            if task_obj.ACTION:
                                                for action in task_obj.ACTION.keys():
                                                    # Set default action.
                                                    if action not in task_obj.ACTION:
                                                        task_obj.ACTION.setdefault(action, {})

                                                    # Set default 'PATH' to CWD for all task actions.
                                                    if ('PATH' not in task_obj.ACTION[action]) or (not task_obj.ACTION[action]['PATH']):
                                                        task_obj.ACTION[action]['PATH'] = CWD

                                                    # Make sure 'COMMAND' exists.
                                                    if action not in ['COMMON']:
                                                        if ('COMMAND' not in task_obj.ACTION[action]) or (not task_obj.ACTION[action]['COMMAND']):
                                                            common.print_warning('*Warning*: For task (' + str(task_obj.NAME) + ') action (' + str(action) + '), "COMMAND" is not defined.')

                                                    # For 'CHECK' and 'SUMMARY', make sure 'VIEWER' and 'REPORT_FILE' are defined.
                                                    # if action in ['CHECK', 'SUMMARY']:
                                                    #     if ('VIEWER' not in task_obj.ACTION[action]) or (not task_obj.ACTION[action]['VIEWER']):
                                                    #         common.print_warning('*Warning*: For task (' + str(task_obj.NAME) + ') action (' + str(action) + '), "VIEWER" is not defined.')
                                                    #     elif ('REPORT_FILE' not in task_obj.ACTION[action]) or (not task_obj.ACTION[action]['REPORT_FILE']):
                                                    #         common.print_warning('*Warning*: For task (' + str(task_obj.NAME) + ') action (' + str(action) + '), "REPORT_FILE" is not defined.')

                                            # Update self.taks_dic.
                                            self.task_dic.update({'{} {} {} {}'.format(block_obj.NAME, version_obj.NAME, flow_obj.NAME, task_obj.NAME): task_obj})

                                            flow_obj.update_field(task_obj)

                                        version_obj.update_field(flow_obj)

                                block_obj.update_field(version_obj)

                        self.block_dic.update({block: block_obj})

        for attr in self.var_dic.keys():
            self.var_dic[attr] = common.expand_var(self.var_dic[attr], ifp_var_dic=self.var_dic, show_warning=False)

    @property
    def main_table_info_list(self):
        # self.__item_list is a list, save some class 'IfpItem'.
        # One IfpItem means one line on IFP GUI.
        self.__item_list = []

        if self.block_dic:
            for block in self.block_dic.values():
                if block.VERSION:
                    for version in block.VERSION.values():
                        if version.FLOW:
                            for flow in version.FLOW.values():
                                if flow.TASK:
                                    for task in flow.TASK.values():
                                        item = IfpItem(block.NAME, version.NAME, flow.NAME, task)
                                        self.__item_list.append(item)

        return self.__item_list

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
                                        config_dic['BLOCK'][block.NAME][version.NAME][flow.NAME].update({task.NAME: task})

        return config_dic

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

    def get_task(self, block, version, flow, task_name):
        query = '{} {} {} {}'.format(block, version, flow, task_name)
        task_obj = self.task_dic.get(query, None)

        if not task_obj:
            raise Exception('*Error*: No task found for {}'.format(query))

        return task_obj

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


class IfpItem:
    def __init__(self, block, version, flow, task):
        self.Block = block
        self.Version = version
        self.Flow = flow
        self.Task = task.NAME
        self.__task = task
        self.item_list = ['Block', 'Version', 'Flow', 'Task']
        self.property_list = ['Visible', 'Selected', 'PATH', 'Status', 'Check', 'Summary', 'Job', 'Runtime', 'Xterm', 'BuildStatus', 'RunStatus', 'CheckStatus', 'SummarizeStatus', 'ReleaseStatus', 'Task_obj']

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
        self.Visible = True
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
                if str(val) == 'Fasle':
                    val = False

                setting[key] = val
        except Exception:
            common.print_error('*Error*: wrong setting as {}'.format(setting_str))
            sys.exit(1)

    return (setting_wo_parentheses, setting)
