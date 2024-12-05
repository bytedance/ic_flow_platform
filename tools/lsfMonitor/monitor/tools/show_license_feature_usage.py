# -*- coding: utf-8 -*-
import os
import re
import sys
import time
import datetime
import argparse

from PyQt5.QtWidgets import QApplication, QMainWindow, QTabWidget, QFrame, QGridLayout, QTableWidget, QTableWidgetItem, QHeaderView
from PyQt5.QtGui import QBrush
from PyQt5.QtCore import Qt, QThread

sys.path.insert(0, str(os.environ['LSFMONITOR_INSTALL_PATH']) + '/monitor')
from common import common_pyqt5
from common import common_license
from common import common_lsf

# Import local config file if exists.
local_config_dir = str(os.environ['HOME']) + '/.lsfMonitor/conf'
local_config = str(local_config_dir) + '/config.py'

if os.path.exists(local_config):
    sys.path.append(local_config_dir)
    import config
else:
    from conf import config

os.environ['PYTHONUNBUFFERED'] = '1'


def read_args():
    """
    Read in arguments.
    """
    parser = argparse.ArgumentParser()

    parser.add_argument('-s', '--server',
                        required=True,
                        default='',
                        help='Specify license server.')
    parser.add_argument('-v', '--vendor',
                        required=True,
                        default='',
                        help='Specify vendor daemon.')
    parser.add_argument('-f', '--feature',
                        required=True,
                        default='',
                        help='Specify license feature.')

    args = parser.parse_args()

    return args.server, args.vendor, args.feature


class ShowLicenseFreatureUsage(QMainWindow):
    def __init__(self, server, vendor, feature):
        super().__init__()
        self.server = server
        self.vendor = vendor
        self.feature = feature

        # Get License info.
        my_show_message = ShowMessage('Info', 'Checking "' + str(self.feature) + '" usage info ...')
        my_show_message.start()

        self.license_feature_usage_dic_list = self.get_license_feature_usage()

        my_show_message.terminate()

        # Get LSF job info.
        my_show_message = ShowMessage('Info', 'Checking LSF job info ...')
        my_show_message.start()

        self.job_dic = common_lsf.get_bjobs_info()

        my_show_message.terminate()

        self.init_ui()

    def get_license_feature_usage(self):
        # Get self.license_dic.
        my_get_license_info = common_license.GetLicenseInfo(specified_server=self.server, specified_feature=self.feature, lmstat_path=config.lmstat_path, bsub_command=config.lmstat_bsub_command)
        license_dic = my_get_license_info.get_license_info()
        license_feature_usage_dic_list = []

        if self.server in license_dic:
            if self.vendor in license_dic[self.server]['vendor_daemon']:
                if self.feature in license_dic[self.server]['vendor_daemon'][self.vendor]['feature']:
                    if 'in_use_info' in license_dic[self.server]['vendor_daemon'][self.vendor]['feature'][self.feature]:
                        for usage_dic in license_dic[self.server]['vendor_daemon'][self.vendor]['feature'][self.feature]['in_use_info']:
                            license_feature_usage_dic_list.append(usage_dic)

        return license_feature_usage_dic_list

    def init_ui(self):
        # Add main_tab
        self.main_tab = QTabWidget(self)
        self.setCentralWidget(self.main_tab)

        self.main_frame = QFrame(self.main_tab)

        # Grid
        main_grid = QGridLayout()
        main_grid.addWidget(self.main_frame, 0, 0)
        self.main_tab.setLayout(main_grid)

        # Generate main_table
        self.gen_main_frame()

        # Show main window
        self.setWindowTitle('"' + str(self.feature) + '" usage on ' + str(self.server) + '/' + str(self.vendor))

        common_pyqt5.auto_resize(self, 900, 400)
        common_pyqt5.center_window(self)

    def gen_main_frame(self):
        self.main_table = QTableWidget(self.main_frame)

        # Grid
        main_frame_grid = QGridLayout()
        main_frame_grid.addWidget(self.main_table, 0, 0)
        self.main_frame.setLayout(main_frame_grid)

        self.gen_main_table()

    def switch_bjobs_submit_time(self, submit_time, compare_second='', format=''):
        """
        Switch submit_time format from "%a %m/%d %H:%M" to specified format (or start_second by default).
        """
        new_submit_time = submit_time

        if submit_time and (submit_time != 'N/A') and (submit_time != 'RESERVATION'):
            # Switch submit_time to start_second.
            current_year = datetime.date.today().year
            submit_time_with_year = str(current_year) + ' ' + str(submit_time)
            submit_time_with_year = re.sub('  ', ' ', submit_time_with_year)

            try:
                start_second = time.mktime(time.strptime(submit_time_with_year, '%Y %b %d %H:%M'))
            except Exception:
                print('*Warning*: Variable "submit_time_with_year", value is "' + str(submit_time_with_year) + '", not follow the time format "%Y %b %d %H:%M".')

            if not compare_second:
                compare_second = time.time()

            if int(start_second) > int(compare_second):
                current_year = int(datetime.date.today().year) - 1
                submit_time_with_year = str(current_year) + ' ' + str(submit_time)
                start_second = time.mktime(time.strptime(submit_time_with_year, '%Y %b %d %H:%M'))

            # Switch start_second to expected time format.
            if format:
                new_submit_time = time.strftime(format, time.localtime(start_second))
            else:
                new_submit_time = start_second

        return new_submit_time

    def get_job_info(self, user, submit_host, execute_host, start_time):
        jobid_list = []

        for (i, jobid) in enumerate(self.job_dic['JOBID']):
            if (user == self.job_dic['USER'][i]) and ((submit_host == self.job_dic['FROM_HOST'][i]) or (submit_host == 'N/A')) and re.search(execute_host, self.job_dic['EXEC_HOST'][i]):
                license_start_time = common_license.switch_start_time(start_time)
                job_submit_time = self.switch_bjobs_submit_time(self.job_dic['SUBMIT_TIME'][i])

                if int(license_start_time) >= int(job_submit_time):
                    jobid_list.append(jobid)

        if len(jobid_list) == 0:
            return ''
        elif len(jobid_list) == 1:
            return jobid_list[0]
        elif len(jobid_list) > 1:
            return '*'

    def gen_main_table(self):
        self.main_table.setShowGrid(True)
        self.main_table.setColumnCount(0)
        self.main_table.setColumnCount(7)
        self.main_table.setHorizontalHeaderLabels(['USER', 'SUBMIT_HOST', 'EXECUTE_HOST', 'NUM', 'VERSION', 'START_TIME', 'JOB'])

        # Set column width
        self.main_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.main_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.main_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.main_table.setColumnWidth(3, 50)
        self.main_table.setColumnWidth(4, 80)
        self.main_table.setColumnWidth(5, 120)
        self.main_table.setColumnWidth(6, 80)

        # Set item
        self.main_table.setRowCount(len(self.license_feature_usage_dic_list))

        title_list = ['user', 'submit_host', 'execute_host', 'license_num', 'version', 'start_time']

        for (row, license_feature_usage_dic) in enumerate(self.license_feature_usage_dic_list):
            for (column, title) in enumerate(title_list):
                item = QTableWidgetItem()
                item.setText(license_feature_usage_dic[title])

                if column == 5:
                    if common_license.check_long_runtime(license_feature_usage_dic[title]):
                        # Set red color for long runtime item.
                        item.setForeground(QBrush(Qt.red))

                self.main_table.setItem(row, column, item)

            # Set "JOB" info.
            jobid = self.get_job_info(license_feature_usage_dic['user'], license_feature_usage_dic['submit_host'], license_feature_usage_dic['execute_host'], license_feature_usage_dic['start_time'])
            item = QTableWidgetItem()
            item.setText(jobid)
            self.main_table.setItem(row, 6, item)


class ShowMessage(QThread):
    """
    Show message with tool message.
    """
    def __init__(self, title, message):
        super(ShowMessage, self).__init__()
        self.title = title
        self.message = message

    def run(self):
        command = 'python3 ' + str(os.environ['LSFMONITOR_INSTALL_PATH']) + '/monitor/tools/message.py --title "' + str(self.title) + '" --message "' + str(self.message) + '"'
        os.system(command)


################
# Main Process #
################
def main():
    (server, vendor, feature) = read_args()
    app = QApplication(sys.argv)
    my_show = ShowLicenseFreatureUsage(server, vendor, feature)
    my_show.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
