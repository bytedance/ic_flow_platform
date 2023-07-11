# -*- coding: utf-8 -*-
################################
# File Name   : config.py
# Author      : qushengrui
# Created On  : 2022-05-27 13:48:57
# Description :
################################
import os
import re
import sys
import yaml
import pickle
import copy
from string import Template

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
    >>> c.BLOCK['block1'].VERSION['block1_versionA'].RUN_ORDER
    ['flow1,flow2']
    >>> c.BLOCK['block1'].VERSION['block1_versionA'].FLOW.keys()
    dict_keys(['flow1', 'flow2'])
    >>> c.BLOCK['block1'].VERSION['block1_versionA'].FLOW['flow1'].VENDOR.keys()
    dict_keys(['vendor1'])
    >>> c.BLOCK['block1'].VERSION['block1_versionA'].FLOW['flow1'].VENDOR['vendor1'].BRANCH.keys()
    dict_keys(['branch1'])
    >>> c.BLOCK['block1'].VERSION['block1_versionA'].FLOW['flow1'].VENDOR['vendor1'].BRANCH['branch1'].TASK.keys()
    dict_keys(['task1'])
    >>> c.BLOCK['block1'].VERSION['block1_versionA'].FLOW['flow1'].VENDOR['vendor1'].BRANCH['branch1'].RUN_TYPE
    'serial'
    >>> c.BLOCK['block1'].VERSION['block1_versionA'].FLOW['flow1'].VENDOR['vendor1'].BRANCH['branch1'].TASK['task1'].ACTION.keys()
    dict_keys(['BUILD', 'RUN', 'CHECK', 'SUMMARY', 'RELEASE', 'POST_RUN'])
    >>> c.BLOCK['block1'].VERSION['block1_versionA'].FLOW['flow1'].VENDOR['vendor1'].BRANCH['branch1'].TASK['task1'].ACTION['BUILD']
    {'NAME': 'BUILD', 'COMMAND': 'task1_build_cmd', 'PATH': 'CWD', 'RUN_METHOD': 'local'}
    >>> c.BLOCK['block1'].VERSION['block1_versionA'].FLOW['flow1'].VENDOR['vendor1'].BRANCH['branch1'].TASK['task1'].PATH
    'CWD'
    >>> table_list = c.main_table_info_list
    >>> len(table_list)
    5
    >>> table_list[0]['Block']
    'block1'
    >>> c.config_dic['RUN_TYPE']['block2.block2_version.flow1.vendor1.branch1']
    'parallel'
    >>> c.config_dic['RUN_ORDER']['block1:block1_versionB']
    ['flow1', 'flow2']
    """
    def __new__(cls, *args, **kwargs):
        obj = getattr(cls, '__instance__', None)

        if not obj:
            obj = object.__new__(cls)
            cls.__instance__ = obj

        return obj

    def __init__(self, config_file):
        self.get_config_obj(config_file)

    def parse_config_file(self, config_file, kind='user'):
        config_dic = {}

        if os.path.exists(config_file):
            with open(config_file, 'r') as fh:
                config_dic = yaml.load(fh, Loader=yaml.FullLoader)

            if not config_dic:
                config_dic = {}
            else:
                if kind == 'user':
                    if ('PROJECT' not in config_dic) or (not config_dic['PROJECT']):
                        common.print_error('*Error*: failed to get PROJECT name from file {}.'.format(config_file))
                        sys.exit(1)

                    if ('VAR' not in config_dic) or (not config_dic['VAR']):
                        config_dic['VAR'] = {}

                    if ('BLOCK' not in config_dic) or (not config_dic['BLOCK']):
                        config_dic['BLOCK'] = {}

        return (config_dic)

    def expand_var(self, setting_str, **kwargs):
        """
        Expand variable settings on 'setting_str'.
        """
        if type(setting_str) is str:
            if setting_str.find('$') >= 0:
                # Merge IFP_INSTALL_PATH/CWD and **kwargs into var_dic.
                var_dic = copy.deepcopy(self.var_dic)
                var_dic.update(**kwargs)

                # Replease variables with var_dic on setting_str.
                try:
                    tpl = Template(setting_str)
                    setting_str = tpl.substitute(var_dic)
                except Exception as warning:
                    common.print_warning('*Warning*: Failed on expanding variable for "' + str(setting_str) + '" : ' + str(warning))

        return (setting_str)

    def get_config_obj(self, config_file):
        # self.PROJECT saves project information from user config file.
        self.PROJECT = ''
        # self.var_dic saves all VAR settings from user config file.
        self.var_dic = {'IFP_INSTALL_PATH': os.environ['IFP_INSTALL_PATH'],
                        'CWD': CWD}
        # self.block_dic saves all block configuration information.
        self.block_dic = {}
        # self.task_dic saves all task configuration information.
        self.task_dic = {}

        # Parse default config file.
        default_config_dic = {}
        default_config_file = str(os.environ['IFP_INSTALL_PATH']) + '/config/default.' + str(self.PROJECT) + '.yaml'

        if not os.path.exists(default_config_file):
            default_config_file = str(os.environ['IFP_INSTALL_PATH']) + '/config/default.yaml'

        if os.path.exists(default_config_file):
            default_config_dic = self.parse_config_file(default_config_file, kind='default')

            if ('VAR' in default_config_dic) and isinstance(default_config_dic['VAR'], dict):
                for (key, value) in default_config_dic['VAR'].items():
                    if isinstance(value, str):
                        self.var_dic[key] = value

        # Parse user config file. (With parallel tasks)
        user_config_dic = self.parse_config_file(config_file, kind='user')

        if user_config_dic:
            if 'PROJECT' in user_config_dic:
                self.PROJECT = user_config_dic['PROJECT']

            if ('VAR' in user_config_dic) and isinstance(user_config_dic['VAR'], dict):
                for (key, value) in user_config_dic['VAR'].items():
                    if isinstance(value, str):
                        self.var_dic[key] = value

            if ('BLOCK' in user_config_dic) and user_config_dic['BLOCK']:
                for block in user_config_dic['BLOCK'].keys():
                    block_expand = self.expand_var(block)
                    block_obj = Block(block_expand)

                    if user_config_dic['BLOCK'][block]:
                        for version in user_config_dic['BLOCK'][block].keys():
                            version_expand = self.expand_var(version)
                            version_obj = Version(version_expand)
                            flows = []

                            if user_config_dic['BLOCK'][block][version]:
                                for flow in user_config_dic['BLOCK'][block][version].keys():
                                    flow_expand = self.expand_var(flow)
                                    flows.append(flow)
                                    flow_obj = Flow(flow_expand)

                                    if user_config_dic['BLOCK'][block][version][flow]:
                                        for vendor in user_config_dic['BLOCK'][block][version][flow].keys():
                                            vendor_expand = self.expand_var(vendor)
                                            vendor_obj = Vendor(vendor_expand)

                                            if user_config_dic['BLOCK'][block][version][flow][vendor]:
                                                for branch in user_config_dic['BLOCK'][block][version][flow][vendor].keys():
                                                    branch_expand = self.expand_var(branch)
                                                    branch_obj = Branch(branch_expand)

                                                    if user_config_dic['BLOCK'][block][version][flow][vendor][branch]:
                                                        for task in user_config_dic['BLOCK'][block][version][flow][vendor][branch].keys():
                                                            task_expand = self.expand_var(task)
                                                            task_obj = Task(task_expand)
                                                            user_task_dic = user_config_dic['BLOCK'][block][version][flow][vendor][branch][task]

                                                            # Get task_var_dic, which contains variables from ifp.cfg.yaml/default.yaml and task BLOCK/VERSION/FLOW/VENDOR/BRACH/TASK information.
                                                            task_var_dic = {'BLOCK': block_obj.NAME,
                                                                            'VERSION': version_obj.NAME,
                                                                            'FLOW': flow_obj.NAME,
                                                                            'VENDOR': vendor_obj.NAME,
                                                                            'BRANCH': branch_obj.NAME,
                                                                            'TASK': task_obj.NAME}

                                                            for (key, value) in self.var_dic.items():
                                                                if isinstance(value, str):
                                                                    task_var_dic[key] = self.expand_var(value, **task_var_dic)

                                                            # Update task_obj task attribute with default config file settings.
                                                            if default_config_dic:
                                                                # Get task information from default.yaml.
                                                                if 'TASK' in default_config_dic:
                                                                    task_mark = str(flow_obj.NAME) + ':' + str(vendor_obj.NAME) + ':' + str(task_obj.NAME)

                                                                    if default_config_dic['TASK'] and (task_mark in default_config_dic['TASK']) and default_config_dic['TASK'][task_mark]:
                                                                        for action in default_config_dic['TASK'][task_mark].keys():
                                                                            if action in ['BUILD', 'RUN', 'CHECK', 'SUMMARY', 'POST_RUN', 'RELEASE']:
                                                                                default_action_dic = default_config_dic['TASK'][task_mark].get(action, {})

                                                                                if default_action_dic:
                                                                                    for action_attr in ['PATH', 'COMMAND', 'RUN_METHOD', 'VIEWER', 'REPORT_FILE']:
                                                                                        if (action_attr in default_action_dic) and (default_action_dic[action_attr]):
                                                                                            task_obj.ACTION.setdefault(action, {})
                                                                                            task_obj.ACTION[action][action_attr] = self.expand_var(default_action_dic[action_attr], **task_var_dic)
                                                                            else:
                                                                                common.print_warning('*Warning*: invalid action "' + str(action) + '" on ' + str(default_config_file) + '.')

                                                            # Re-write task_obj task attribute with user configuration.
                                                            if user_task_dic and isinstance(user_task_dic, dict):
                                                                for action in user_task_dic.keys():
                                                                    if action in ['BUILD', 'RUN', 'CHECK', 'SUMMARY', 'POST_RUN', 'RELEASE']:
                                                                        for action_attr in ['PATH', 'COMMAND', 'RUN_METHOD', 'VIEWER', 'REPORT_FILE']:
                                                                            if (action_attr in user_task_dic[action]) and user_task_dic[action][action_attr]:
                                                                                task_obj.ACTION.setdefault(action, {})
                                                                                task_obj.ACTION[action][action_attr] = self.expand_var(user_task_dic[action][action_attr], **task_var_dic)
                                                                    else:
                                                                        common.print_warning('*Warning*: invalid action "' + str(action) + '" on ' + str(config_file) + '.')

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
                                                                    if ('COMMAND' not in task_obj.ACTION[action]) or (not task_obj.ACTION[action]['COMMAND']):
                                                                        common.print_warning('*Warning*: For task (' + str(task_obj.NAME) + ') action (' + str(action) + '), "COMMAND" is not defined.')

                                                                    # For 'CHECK' and 'SUMMARY', make sure 'VIEWER' and 'REPORT_FILE' are defined.
                                                                    if action in ['CHECK', 'SUMMARY']:
                                                                        if ('VIEWER' not in task_obj.ACTION[action]) or (not task_obj.ACTION[action]['VIEWER']):
                                                                            common.print_warning('*Warning*: For task (' + str(task_obj.NAME) + ') action (' + str(action) + '), "VIEWER" is not defined.')
                                                                        elif ('REPORT_FILE' not in task_obj.ACTION[action]) or (not task_obj.ACTION[action]['REPORT_FILE']):
                                                                            common.print_warning('*Warning*: For task (' + str(task_obj.NAME) + ') action (' + str(action) + '), "REPORT_FILE" is not defined.')

                                                            # Update self.taks_dic.
                                                            self.task_dic.update({'{} {} {} {} {} {}'.format(block_obj.NAME,
                                                                                                             version_obj.NAME,
                                                                                                             flow_obj.NAME,
                                                                                                             vendor_obj.NAME,
                                                                                                             branch_obj.NAME,
                                                                                                             task_obj.NAME): task_obj})

                                                            branch_obj.update_field(task_obj)

                                                        vendor_obj.update_field(branch_obj)

                                                flow_obj.update_field(vendor_obj)

                                        version_obj.update_field(flow_obj)

                                if not version_obj.RUN_ORDER:
                                    version_obj.RUN_ORDER = flows

                                block_obj.update_field(version_obj)

                        self.block_dic.update({block: block_obj})

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
                                if flow.VENDOR:
                                    for vendor in flow.VENDOR.values():
                                        if vendor.BRANCH:
                                            for branch in vendor.BRANCH.values():
                                                if branch.TASK:
                                                    for task in branch.TASK.values():
                                                        item = IfpItem(block.NAME, version.NAME, flow.NAME, vendor.NAME, branch.NAME, task)
                                                        self.__item_list.append(item)

        return self.__item_list

    @property
    def config_dic(self):
        config_dic = {'PROJECT': self.PROJECT,
                      'VAR': self.var_dic,
                      'BLOCK': {},
                      'RUN_TYPE': {},
                      'RUN_ORDER': {}}

        if self.block_dic:
            for block in self.block_dic.values():
                config_dic['BLOCK'].update({block.NAME: {}})

                if block.VERSION:
                    for version in block.VERSION.values():
                        config_dic['RUN_ORDER'].update({'{}:{}'.format(block.NAME, version.NAME): version.RUN_ORDER})
                        config_dic['BLOCK'][block.NAME].update({version.NAME: {}})

                        if version.FLOW:
                            for flow in version.FLOW.values():
                                config_dic['BLOCK'][block.NAME][version.NAME].update({flow.NAME: {}})

                                if flow.VENDOR:
                                    for vendor in flow.VENDOR.values():
                                        config_dic['BLOCK'][block.NAME][version.NAME][flow.NAME].update({vendor.NAME: {}})

                                        if vendor.BRANCH:
                                            for branch in vendor.BRANCH.values():
                                                config_dic['RUN_TYPE'].update({'{}.{}.{}.{}.{}'.format(block.NAME, version.NAME, flow.NAME, vendor.NAME, branch.NAME): branch.RUN_TYPE})
                                                config_dic['BLOCK'][block.NAME][version.NAME][flow.NAME][vendor.NAME].update({branch.NAME: {}})

                                                if branch.TASK:
                                                    for task in branch.TASK.values():
                                                        config_dic['BLOCK'][block.NAME][version.NAME][flow.NAME][vendor.NAME][branch.NAME].update({task.NAME: task})

        return config_dic

    def __repr__(self):
        return str({
            'PROJECT': self.PROJECT,
            'VAR': self.var_dic,
            'BLOCK': self.block_dic
            })

    def update_task_field(self, block, version, flow, vendor, branch, task_name, field, field_value):
        task_obj = self.get_task(block, version, flow, vendor, branch, task_name)

        if not hasattr(task_obj, field):
            raise Exception('*Error*: Task has no attribute {}'.format(field))

        task_obj.__dict__[field] = field_value

    def get_task(self, block, version, flow, vendor, branch, task_name):
        query = '{} {} {} {} {} {}'.format(block, version, flow, vendor, branch, task_name)
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
                vendor = i_in_cur_session.Vendor
                branch = i_in_cur_session.Branch
                task = i_in_cur_session.Task

                for i in restored_item_list:
                    if block == i.Block and version == i.Version and flow == i.Flow and vendor == i.Vendor and branch == i.Branch and task == i.Task:
                        i_in_cur_session.Status = i.Status
                        i_in_cur_session.Runtime = i.Runtime
                        i_in_cur_session.Job = i.Job
                        break


class IfpItem:
    def __init__(self, block, version, flow, vendor, branch, task):
        self.Block = block
        self.Version = version
        self.Flow = flow
        self.Vendor = vendor
        self.Branch = branch
        self.Task = task.NAME
        self.__task = task
        self.item_list = ['Block', 'Version', 'Flow', 'Vendor', 'Branch', 'Task']
        self.property_list = ['Visible', 'Selected', 'PATH', 'Status', 'Check', 'Summary', 'Job', 'Runtime', 'Xterm']

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

        if not hasattr(self, 'RUN_ORDER'):
            self.RUN_ORDER = None
        else:
            self.RUN_ORDER = self.RUN_ORDER.split(',')

        self.FLOW = {}


class Flow(Common):
    def __init__(self, name):
        super().__init__(name)
        self.VENDOR = {}


class Vendor(Common):
    def __init__(self, name):
        super().__init__(name)
        self.BRANCH = {}


class Branch(Common):
    def __init__(self, name):
        super().__init__(name)

        if not hasattr(self, 'RUN_TYPE'):
            self.RUN_TYPE = 'serial'

        self.TASK = {}


class Task(Common):
    def __init__(self, name):
        super().__init__(name)
        self.ACTION = {}
        self.Visible = True
        self.Selected = True
        self.PATH = None
        self.Status = None
        self.Check = None
        self.Summary = None
        self.Job = None
        self.Runtime = None
        self.Xterm = None
        self.property_list = ['Visible', 'Selected', 'PATH', 'Status', 'Check', 'Summary', 'Job', 'Runtime', 'Xterm']

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
    """
    doctesting:
    >>> s1 = 'some(and)some(A=1;B=2;C=3)'
    >>> get_parentheses_setting(s1)
    ('some(and)some', {'A': '1', 'B': '2', 'C': '3'})
    >>> s2 = 'block1_version(RUN_ORDER=syn,fv|sta)'
    >>> get_parentheses_setting(s2)
    ('block1_version', {'RUN_ORDER': 'syn,fv|sta'})
    """
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
