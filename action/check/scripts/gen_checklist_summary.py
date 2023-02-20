# -*- coding: utf-8 -*-
################################
# File Name   : gen_checklist_summary.py
# Author      : liyanqing.1987
# Created On  : 2021-12-22 17:04:30
# Description :
################################
import os
import re
import sys
import argparse
import xlwt
import collections

sys.path.append(str(os.environ['IFP_INSTALL_PATH']) + '/bin')
import parse_config

os.environ['PYTHONUNBUFFERED'] = '1'
CWD = os.getcwd()


def read_args():
    """
    Read in arguments.
    """
    parser = argparse.ArgumentParser()

    parser.add_argument('-c', '--config_file',
                        default=str(CWD) + '/ifp.cfg.yaml',
                        help='Specify the configure file, default is "<CWD>/ifp.cfg.yaml".')
    parser.add_argument('-r', '--report',
                        default=str(CWD)+'/checklist.sum.xlsx',
                        help='Specify the checklist summary report, default is "<CWD>/checklist.sum.xlsx".')

    args = parser.parse_args()

    # Check report
    report_dir = os.path.dirname(args.report)

    if not os.path.exists(report_dir):
        print('*Error*: ' + str(report_dir) + ': No such report directory.')
        sys.exit(1)

    if os.path.exists(args.report) and os.path.isfile(args.report):
        try:
            os.remove(args.report)
        except Exception as error:
            print('*Error*: Failed on removing old report "' + str(args.report) + '": ' + str(error))
            sys.exit(1)

    return (args.config_file, args.report)


class GenChecklistSummary():
    def __init__(self, config_file, report):
        config_obj = parse_config.Config(config_file)
        self.config_dic = config_obj.config_dic
        self.report = report

    def get_task_checklist_dic(self):
        task_checklist_dic = collections.OrderedDict()

        for block in self.config_dic['BLOCK'].keys():
            for version in self.config_dic['BLOCK'][block].keys():
                for flow in self.config_dic['BLOCK'][block][version].keys():
                    for vendor in self.config_dic['BLOCK'][block][version][flow].keys():
                        for branch in self.config_dic['BLOCK'][block][version][flow][vendor].keys():
                            for task in self.config_dic['BLOCK'][block][version][flow][vendor][branch].keys():
                                task_path = ''
                                task_obj = self.config_dic['BLOCK'][block][version][flow][vendor][branch][task]

                                if 'CHECK' in task_obj.ACTION.keys():
                                    if 'PATH' in task_obj.ACTION['CHECK'].keys():
                                        if os.path.exists(task_obj.ACTION['CHECK']['PATH']):
                                            task_path = task_obj.ACTION['CHECK']['PATH']

                                if task_path:
                                    task_checklist_result_dic = self.get_task_checklist_result(task_path)

                                    task_checklist_dic.setdefault(flow, collections.OrderedDict())
                                    task_checklist_dic[flow].setdefault(vendor, collections.OrderedDict())
                                    task_checklist_dic[flow][vendor].setdefault(block, collections.OrderedDict())
                                    task_checklist_dic[flow][vendor][block].setdefault(str(version)+'_'+str(branch), collections.OrderedDict())
                                    task_checklist_dic[flow][vendor][block][str(version)+'_'+str(branch)].setdefault(task, collections.OrderedDict())
                                    task_checklist_dic[flow][vendor][block][str(version)+'_'+str(branch)][task] = task_checklist_result_dic

        return (task_checklist_dic)

    def get_task_checklist_result(self, task_path):
        task_checklist_result_dic = collections.OrderedDict()

        if task_path:
            file_check_report = str(task_path) + '/file_check/file_check.rpt'

            if not os.path.exists(file_check_report):
                print('*Warning*: file_check report "' + str(file_check_report) + '" is missing.')

                result = 'NA'
                description = 'NA'
                review_file = ''
                task_checklist_result_dic.setdefault(description, collections.OrderedDict())
                task_checklist_result_dic[description]['result'] = result
                task_checklist_result_dic[description]['review_file'] = review_file
            else:
                with open(file_check_report, 'r') as FCR:
                    for line in FCR.readlines():
                        if re.match(r'^\s*(\w+?)\s*:\s*(.+?)\s*(\(details please see (.+?)\))?\s*$', line):
                            my_match = re.match(r'^\s*(\w+?)\s*:\s*(.+?)\s*(\(details please see (.+?)\))?\s*$', line)
                            result = my_match.group(1)
                            description = my_match.group(2)
                            review_file = my_match.group(4)
                            task_checklist_result_dic.setdefault(description, collections.OrderedDict())
                            task_checklist_result_dic[description]['result'] = result
                            task_checklist_result_dic[description]['review_file'] = review_file

        return (task_checklist_result_dic)

    def write_excel(self, task_checklist_dic):
        workbook = xlwt.Workbook(encoding='utf-8')

        for flow in task_checklist_dic.keys():
            for vendor in task_checklist_dic[flow].keys():
                worksheet = workbook.add_sheet(str(flow) + '_' + str(vendor))

                title_style = xlwt.XFStyle()
                font = xlwt.Font()
                font.bold = True
                title_style.font = font
                borders = xlwt.Borders()
                borders.left = 1
                borders.right = 1
                borders.top = 1
                borders.bottom = 1
                title_style.borders = borders
                pattern = xlwt.Pattern()
                pattern.pattern = xlwt.Pattern.SOLID_PATTERN
                pattern.pattern_fore_colour = 22
                title_style.pattern = pattern
                alignment = xlwt.Alignment()
                alignment.horz = 0x02
                alignment.vert = 0x01
                title_style.alignment = alignment

                content_style = xlwt.XFStyle()
                content_style.alignment = alignment
                content_style.borders = borders

                left_content_style = xlwt.XFStyle()
                left_alignment = xlwt.Alignment()
                left_alignment.horz = 0x01
                left_content_style.alignment = left_alignment
                left_content_style.borders = borders

                red_content_style = xlwt.XFStyle()
                red_content_style.alignment = alignment
                red_content_style.borders = borders
                red_font = xlwt.Font()
                red_font.colour_index = 2
                red_content_style.font = red_font

                green_content_style = xlwt.XFStyle()
                green_content_style.alignment = alignment
                green_content_style.borders = borders
                green_font = xlwt.Font()
                green_font.colour_index = 3
                green_content_style.font = green_font

                pink_content_style = xlwt.XFStyle()
                pink_content_style.alignment = alignment
                pink_content_style.borders = borders
                pink_font = xlwt.Font()
                pink_font.colour_index = 2
                pink_content_style.font = pink_font

                (block_version_dic, task_list, task_checklist_description_dic) = self.get_block_version_task_info(task_checklist_dic[flow][vendor])

                # Column 0-1 title
                worksheet.write_merge(0, 1, 0, 0, 'Task', title_style)
                worksheet.write_merge(0, 1, 1, 1, 'Description', title_style)

                # Column 0, tasks (row 1-end)
                row = 2
                max_length = 0

                for task in task_list:
                    if len(task) > max_length:
                        max_length = len(task)
                        worksheet.col(0).width = 256*(max_length+4)

                    if len(task_checklist_description_dic[task]) > 1:
                        worksheet.write_merge(row, row+len(task_checklist_description_dic[task])-1, 0, 0, task, content_style)
                    else:
                        worksheet.write(row, 0, task, content_style)

                    row += len(task_checklist_description_dic[task])

                # Column 1, task checklist description (row 1-end)
                row = 2
                max_length = 0

                for task in task_list:
                    for description in task_checklist_description_dic[task]:
                        worksheet.write(row, 1, description, left_content_style)

                        if len(description) > max_length:
                            max_length = len(description)
                            worksheet.col(1).width = 256*(max_length+4)

                        row += 1

                # Column 2-end, block checklist result (row 1-end)
                column = 2

                for (index, block) in enumerate(list(block_version_dic.keys())):
                    worksheet.write_merge(0, 0, column, column+(len(block_version_dic[block])-1), block, title_style)

                    for version in block_version_dic[block]:
                        worksheet.write(1, column, version, title_style)
                        worksheet.col(column).width = 256*(len(version)+4)

                        row = 2
                        max_length = len(block)

                        for task in task_list:
                            if task in task_checklist_dic[flow][vendor][block][version].keys():
                                for description in task_checklist_dic[flow][vendor][block][version][task].keys():
                                    result = task_checklist_dic[flow][vendor][block][version][task][description]['result']
                                    review_file = task_checklist_dic[flow][vendor][block][version][task][description]['review_file']

                                    if result == 'PASSED':
                                        worksheet.write(row, column, result, green_content_style)
                                    elif result == 'FAILED':
                                        if review_file and os.path.exists(review_file):
                                            worksheet.write(row, column, xlwt.Formula('HYPERLINK("file://' + str(review_file) + '"; "' + str(result) + '")'), red_content_style)
                                        else:
                                            worksheet.write(row, column, result, red_content_style)
                                    elif result == 'REVIEW':
                                        if review_file and os.path.exists(review_file):
                                            worksheet.write(row, column, xlwt.Formula('HYPERLINK("file://' + str(review_file) + '"; "' + str(result) + '")'), pink_content_style)
                                        else:
                                            worksheet.write(row, column, result, pink_content_style)
                                    else:
                                        worksheet.write(row, column, result, content_style)

                                    if len(result) > max_length:
                                        max_length = len(result)
                                        worksheet.col(column).width = 256*(max_length+4)

                                    row += 1

                            else:
                                for description in task_checklist_description_dic[task]:
                                    worksheet.write(row, column, 'NA', content_style)
                                    row += 1

                        column += 1

        workbook.save(self.report)

    def get_block_version_task_info(self, task_checklist_dic):
        task_list = []
        task_checklist_description_dic = collections.OrderedDict()
        block_version_dic = collections.OrderedDict()

        for block in task_checklist_dic.keys():
            block_version_dic.setdefault(block, [])

            for version in task_checklist_dic[block].keys():
                block_version_dic[block].append(version)

                for task in task_checklist_dic[block][version].keys():
                    if task not in task_list:
                        task_list.append(task)
                        task_checklist_description_dic.setdefault(task, [])

                        for description in task_checklist_dic[block][version][task].keys():
                            task_checklist_description_dic[task].append(description)

        return (block_version_dic, task_list, task_checklist_description_dic)

    def gen_checklist_summary(self):
        task_checklist_dic = self.get_task_checklist_dic()
        self.write_excel(task_checklist_dic)

        print('')
        print('SUMMARY REPORT : ' + str(self.report))


################
# Main Process #
################
def main():
    (config_file, report) = read_args()
    my_gen_checklist_summary = GenChecklistSummary(config_file, report)
    my_gen_checklist_summary.gen_checklist_summary()


if __name__ == '__main__':
    main()
