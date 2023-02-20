# -*- coding: utf-8 -*-
################################
# File Name   : ic_check.py
# Author      : liyanqing.1987
# Created On  : 2021-12-22 17:04:30
# Description :
################################
import os
import sys
import argparse
import datetime
import shutil

sys.path.append(str(os.environ['IFP_INSTALL_PATH']) + '/common')
import common

os.environ['PYTHONUNBUFFERED'] = '1'
CWD = os.getcwd()


def read_args():
    """
    Read in arguments.
    """
    parser = argparse.ArgumentParser()

    parser.add_argument('-d', '--dir',
                        default=CWD,
                        help='Specify the check directory, default is current directory.')
    parser.add_argument('-f', '--flow',
                        required=True,
                        help='Specify the flow name.')
    parser.add_argument('-v', '--vendor',
                        required=True,
                        help='Specify the vendor name')
    parser.add_argument('-b', '--block',
                        required=True,
                        help='Specify the block name')
    parser.add_argument('-t', '--task',
                        default='',
                        help='Specify the task name')
    parser.add_argument('-c', '--corner',
                        default='',
                        help='Specify the corner name')

    args = parser.parse_args()

    if not os.path.exists(args.dir):
        print('*Error*: "' + str(args.dir) + '": No such directory.')
        sys.exit(1)

    return (args.dir, args.flow, args.vendor, args.block, args.task, args.corner)


def write_result_file(result, check_report):
    """
    Write result "PASS" or "FAIL" to the task directory, so the top script can collect task result with file.
    """
    result_file_list = ['./PASS', './FAIL']

    for result_file in result_file_list:
        if os.path.exists(result_file):
            try:
                os.remove(result_file)
            except Exception as warning:
                print('*Warning*: Failed on removing "' + str(result_file) + '": ' + str(warning))

    if os.path.exists(check_report):
        try:
            os.symlink(check_report, result)
        except Exception as warning:
            print('*Warning*: Failed on linking "' + str(check_report) + '" to "' + str(result) + '": ' + str(warning))
    else:
        with open(result, 'w') as RE:
            current_time = datetime.datetime.today().strftime('%Y-%m-%d %H:%M:%S')
            RE.write(str(current_time) + '\n')


def check_result(check_dir, flow, vendor, block, task, corner):
    """
    Check task run result with checklist script.
    Write the result file "PASS" or "FAIL" to mark the result.
    """
    if (flow == 'syn') or (flow == 'fv'):
        check_script = '/ic/software/cad_tools/flows/ic_flow_platform/function/check/' + str(flow) + '/' + str(vendor) + '/' + str(task) + '.py'
    elif flow == 'sta':
        if task == 'pnr':
            check_script = '/ic/software/cad_tools/flows/ic_flow_platform/function/check/' + str(flow) + '/' + 'postSTA.py'
        else:
            check_script = '/ic/software/cad_tools/flows/ic_flow_platform/function/check/' + str(flow) + '/' + 'preSTA.py'

    if not os.patt.exists(check_script):
        print('*Error*: check script "' + str(check_script) + '" is missing.')
        return (1)
    else:
        print('Come into ' + str(check_dir))

        os.chdir(check_dir)

        # Remove old check report directory.
        check_report_dir = str(check_dir) + '/file_check'

        if os.path.exists(check_report_dir):
            try:
                print('Remove ' + str(check_report_dir))
                shutil.rmtree(check_report_dir)
            except Exception as warning:
                print('*Warning*: Failed on removing old check report directory "' + str(check_report_dir) + '".')
                print('           ' + str(warning))

        # Create new check report directory.
        try:
            print('Create ' + str(check_report_dir))
            os.makedirs(check_report_dir)
        except Exception as error:
            print('*Error*: Failed on creating check report directory "' + str(check_report_dir) + '": ' + str(error))
            sys.exit(1)

        # Run checklist script.
        command = str(check_script) + ' -b ' + str(block)

        if task:
            command = str(command) + ' -t ' + str(task)

        if corner:
            command = str(command) + ' -c ' + str(corner)

        print(command)

        (returnCode, stdout, stderr) = common.run_command(command)

        # Check result.
        check_report = str(check_report_dir) + '/file_check.rpt'

        if returnCode == 0:
            if os.path.exists(check_report):
                print('Check pass')
                print('Check report : ' + str(check_report))
                write_result_file('PASS', check_report)
                return (0)
            else:
                print('Check fail')
                print('*Error*: Check report "' + str(check_report) + '" is missing.')
                write_result_file('FAIL', check_report)
                return (1)
        else:
            print('Check fail')
            print('Check report : ' + str(check_report))
            write_result_file('FAIL', check_report)
            return (1)


################
# Main Process #
################
def main():
    (check_dir, flow, vendor, block, task, corner) = read_args()
    check_result(check_dir, flow, vendor, block, task, corner)


if __name__ == '__main__':
    main()
