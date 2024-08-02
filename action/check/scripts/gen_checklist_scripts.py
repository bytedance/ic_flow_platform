# -*- coding: utf-8 -*-
################################
# File Name   : gen_checklist_scripts.py
# Author      : liyanqing.1987
# Created On  : 2021-12-22 17:04:30
# Description :
################################
import os
import re
import sys
import argparse
import xlrd
import collections
import stat

os.environ['PYTHONUNBUFFERED'] = '1'
CWD = os.getcwd()


def readArgs():
    """
    Read in arguments.
    """
    parser = argparse.ArgumentParser()

    parser.add_argument('-i', '--input',
                        required=True,
                        help='Specify the input excel file.')
    parser.add_argument('-f', '--flow',
                        required=True,
                        help='Specify the checklist flow.')
    parser.add_argument('-v', '--vendor',
                        required=True,
                        help='Specify the checklist vendor.')
    parser.add_argument('-o', '--outdir',
                        default=CWD,
                        help='Specify the checklist script output directory, default is current directory.')

    args = parser.parse_args()

    if not os.path.exists(args.input):
        print('*Error*: ' + str(args.input) + ': No such input file.')
        sys.exit(1)

    if not os.path.exists(args.outdir):
        print('*Error*: ' + str(args.outdir) + ': No such output directory, please create it first.')
        sys.exit(1)

    return (args.input, args.flow, args.vendor, args.outdir)


class GenScripts():
    """
    Parse checklist excel to generate checklist scripts.
    """
    def __init__(self, input, flow, vendor, outdir):
        self.input = input
        self.flow = flow
        self.vendor = vendor
        self.outdir = outdir

    def parse_checklist_excel(self):
        """
        Parse the checklist excel, collect checklist items into a dict.
        """
        self.checklist_dic = collections.OrderedDict()
        EXCEL = xlrd.open_workbook(self.input)
        SHEET = EXCEL.sheet_by_index(0)
        title_list = []

        for title in SHEET.row_values(0):
            if re.match(r'^\s*$', title):
                break
            else:
                title_list.append(title)

        for i in range(1, SHEET.nrows):
            line_num = int(i) + 1
            row_list = SHEET.row_values(i)

            if re.match(r'^\s*#.*$', row_list[0]):
                print('*Warning*: line ' + str(line_num) + ', ignore task "' + str(row_list[0]) + '".')
                continue
            else:
                # Get current task(s).
                tasks = row_list[0]

                if not re.match(r'^\s*$', tasks):
                    task_list = tasks.split('/')

                    for task in task_list:
                        if task not in self.checklist_dic.keys():
                            self.checklist_dic[task] = []

                # Get current item (The information on this line).
                item_dic = collections.OrderedDict()

                for j in range(1, len(title_list)):
                    title = title_list[j]
                    item_dic[title] = row_list[j]

                # Check, "FILE" cannot be empty.
                if not item_dic['FILE']:
                    print('*Error*: for below line, FILE cannot be empty.')
                    print('         ' + str(' | '.join(item_dic.values())))
                    sys.exit(1)

                # Check, "MESSAGE" must be empty with "check_file_exists" or "review_file", cannot be empty on other condition.
                if (item_dic['TYPE'] == 'check_file_exist') or (item_dic['TYPE'] == 'review_file'):
                    if item_dic['MESSAGE'] or item_dic['WAIVE_MESSAGE']:
                        print('*Error*: for below line, MESSAGE and WAIVE_MESSAGE must be empty.')
                        print('         ' + str(' | '.join(item_dic.values())))
                        sys.exit(1)
                else:
                    if not item_dic['MESSAGE']:
                        print('*Error*: for below line, MESSAGE can not be empty')
                        print('         ' + str(' | '.join(item_dic.values())))
                        sys.exit(1)

                # Append the item information into task(s).
                for task in task_list:
                    self.checklist_dic[task].append(item_dic)

    def process_file_setting(self, task, file_string, output_type):
        """
        Replace variables "<TASK>", "<BLOCK>" and "<CORNER>".
        Rerun file setting with specified output type.
        """
        if re.search(',', file_string):
            print('*Error*: Cannot include "," on FILE line.')
            sys.exit(1)

        file_list = [item.strip() for item in file_string.split('\n') if item.strip()]

        for (i, file_name) in enumerate(file_list):
            if re.search('<TASK>', file_name) or re.search('<BLOCK>', file_name) or re.search('<CORNER>', file_name):
                file_name = re.sub('<TASK>', task, file_name)
                file_name = re.sub('<', ' ', file_name)
                file_name = re.sub('>', ' ', file_name)
                file_name = re.sub('^', '', file_name)
                file_name = re.sub('$', '', file_name)
                file_name_list = file_name.split()

                file_list[i] = ''

                for file_name_item in file_name_list:
                    if (file_name_item == 'BLOCK') or (file_name_item == 'CORNER'):
                        if file_list[i] == '':
                            file_list[i] = 'str(' + str(file_name_item.lower()) + ')'
                        else:
                            file_list[i] = str(file_list[i]) + ' + str(' + str(file_name_item.lower()) + ')'
                    else:
                        if file_list[i] == '':
                            file_list[i] = "'" + str(file_name_item) + "'"
                        else:
                            file_list[i] = str(file_list[i]) + " + '" + str(file_name_item) + "'"
            else:
                file_list[i] = "'" + str(file_list[i]) + "'"

        if output_type == 'file':
            return (file_list[0])
        elif output_type == 'file_list':
            files = ''

            for file in file_list:
                if files == '':
                    files = str(file)
                else:
                    files = str(files) + ', ' + str(file)

            return (files)

    def process_message_setting(self, message_string, waive_string):
        """
        Read in message/waive strings, return message_list/waive_message_list.
        """
        message_list = []
        waive_message_list = []

        if not re.match(r'^\s*$', message_string):
            message_string_list = message_string.split('\n')

            for item in message_string_list:
                item = item.strip()

                if item:
                    message_list.append(item)

        if not re.match(r'^\s*$', waive_string):
            waive_string_list = waive_string.split('\n')

            for item in waive_string_list:
                item = item.strip()

                if item:
                    waive_message_list.append(item)

        return (message_list, waive_message_list)

    def write_task_script(self, task):
        """
        Write checklist script for one task.
        """
        task_script = str(self.outdir) + '/' + str(self.flow) + '_' + str(self.vendor) + '.' + str(task) + '.py'

        with open(task_script, 'w') as FL:
            FL.write("""#!/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import argparse

sys.path.append('""" + str(os.environ['IFP_INSTALL_PATH']) + """/common')
import common
import common_file_check

os.environ['PYTHONUNBUFFERED'] = '1'

def read_args():
    parser = argparse.ArgumentParser()

    parser.add_argument('-b', '--block',
                        default='',
                        help='Specify block name.')
    parser.add_argument('-t', '--task',
                        default='',
                        help='Specify task name.')
    parser.add_argument('-c', '--corner',
                        default='',
                        help='Specify corner name')

    args = parser.parse_args()

    return (args.block, args.task, args.corner)
""")

            FL.write("""
def file_check(block, task, corner):
    my_file_check = common_file_check.FileCheck()

""")

            for item_dic in self.checklist_dic[task]:
                FL.write('    ##\n')

                FL.write("    description = '" + str(item_dic['DESCRIPTION']) + "'\n")

                files = self.process_file_setting(task, item_dic['FILE'], 'file_list')
                FL.write('    file_list = [' + str(files) + ']\n')
                (message_list, waive_message_list) = self.process_message_setting(item_dic['MESSAGE'], item_dic['WAIVE_MESSAGE'])

                if message_list and waive_message_list:
                    FL.write('    message_list = ' + str(message_list) + '\n')
                    FL.write('    waive_message_list = ' + str(waive_message_list) + '\n')
                    FL.write('    my_file_check.' + str(item_dic['TYPE']) + '(description, file_list, message_list, waive_message_list)\n')
                elif message_list:
                    FL.write('    message_list = ' + str(message_list) + '\n')
                    FL.write('    my_file_check.' + str(item_dic['TYPE']) + '(description, file_list, message_list)\n')
                else:
                    FL.write('    my_file_check.' + str(item_dic['TYPE']) + '(description, file_list)\n')

                FL.write('\n')

            FL.write("""    if my_file_check.final_return_code == 0:
        print(str(task) + ' check pass')
    else:
        common.print_error(str(task) + ' check fail')

    CWD = os.getcwd()
    file_check_report = str(CWD) + '/file_check/file_check.rpt'

    print('Report please see ' + str(file_check_report))

    sys.exit(my_file_check.final_return_code)

#################
# Main Function #
#################
def main():
    (block, task, corner) = read_args()
""")

            if (self.flow == 'sta'):
                FL.write('    preprocess(task, corner)\n')

            FL.write("""    file_check(block, task, corner)

if __name__ == '__main__':
    main()""")

            FL.close()

            os.chmod(task_script, stat.S_IRWXU+stat.S_IRWXG+stat.S_IRWXO)

    def gen_scripts(self):
        """
        Generate check scripts with checklist excel.
        """
        self.parse_checklist_excel()

        for task in self.checklist_dic.keys():
            task_script = str(self.outdir) + '/' + str(self.flow) + '_' + str(self.vendor) + '.' + str(task) + '.py'
            print('>>> Generating checklist script for ' + str(self.flow) + ' task "' + str(task) + '" ...')
            print('    ' + str(task_script))
            self.write_task_script(task)


################
# Main Process #
################
def main():
    (input, flow, vendor, outdir) = readArgs()
    myGenQualityScript = GenScripts(input, flow, vendor, outdir)
    myGenQualityScript.gen_scripts()


if __name__ == '__main__':
    main()
