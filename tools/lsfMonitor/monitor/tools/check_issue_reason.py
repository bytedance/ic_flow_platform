# -*- coding: utf-8 -*-
import os
import re
import sys
import yaml
import argparse

from PyQt5.QtWidgets import QApplication, QMainWindow, QTabWidget, QFrame, QGridLayout, QLabel, QLineEdit, QComboBox, QPushButton, QTextEdit
from PyQt5.QtCore import QThread

sys.path.insert(0, str(os.environ['LSFMONITOR_INSTALL_PATH']) + '/monitor')
from common import common_lsf
from common import common_pyqt5

os.environ['PYTHONUNBUFFERED'] = '1'


def read_args():
    """
    Read in arguments.
    """
    parser = argparse.ArgumentParser()

    parser.add_argument('-j', '--job',
                        default='',
                        help='Specify jobid.')
    parser.add_argument('-i', '--issue',
                        default='PEND',
                        choices=['PEND', 'SLOW', 'FAIL'],
                        help='Specify issue type, default is "PEND".')

    args = parser.parse_args()

    return args.job, args.issue


class MainWindow(QMainWindow):
    """
    Main window of check_issue_reason.
    """
    def __init__(self, job, issue):
        super().__init__()
        self.job = job
        self.issue = issue
        self.exit_code_dic = self.get_exit_code_info()

        self.init_ui()
        self.process_args()

    def get_exit_code_info(self):
        """
        Get exit_code&exit_reason from config/exit_code.yaml.
        """
        exit_code_dic = {}
        exit_code_file = str(os.environ['LSFMONITOR_INSTALL_PATH']) + '/monitor/conf/exit_code.yaml'

        if os.path.exists(exit_code_file):
            with open(exit_code_file, 'r') as ECF:
                exit_code_dic = yaml.load(ECF, Loader=yaml.FullLoader)

        return exit_code_dic

    def init_ui(self):
        """
        Main process, draw the main graphic frame.
        """
        # Define main Tab widget
        self.main_tab = QTabWidget(self)
        self.setCentralWidget(self.main_tab)

        # Defaint sub-frames
        self.select_frame = QFrame(self.main_tab)
        self.info_frame = QFrame(self.main_tab)

        self.select_frame.setFrameShadow(QFrame.Raised)
        self.select_frame.setFrameShape(QFrame.Box)
        self.info_frame.setFrameShadow(QFrame.Raised)
        self.info_frame.setFrameShape(QFrame.Box)

        # Grid
        main_grid = QGridLayout()

        main_grid.addWidget(self.select_frame, 0, 0)
        main_grid.addWidget(self.info_frame, 1, 0)

        main_grid.setRowStretch(0, 1)
        main_grid.setRowStretch(1, 20)

        self.main_tab.setLayout(main_grid)

        # Generate main_table
        self.gen_select_frame()
        self.gen_info_frame()

        # Show main window
        self.setWindowTitle('Check Issue Reason')
        common_pyqt5.auto_resize(self, 600, 300)
        common_pyqt5.center_window(self)

    def process_args(self):
        """
        Process argument if user specified jobid.
        """
        if self.job:
            self.job_line.setText(self.job)
            self.check_issue()

    def gen_select_frame(self):
        # self.select_frame
        job_label = QLabel(self.select_frame)
        job_label.setText('Job')

        self.job_line = QLineEdit()

        issue_label = QLabel(self.select_frame)
        issue_label.setText('Issue')

        self.issue_combo = QComboBox(self.select_frame)
        self.set_issue_combo()

        check_button = QPushButton('Check', self.select_frame)
        check_button.clicked.connect(self.check_issue)

        empty_label = QLabel(self.select_frame)

        # self.select_frame - Grid
        select_frame_grid = QGridLayout()

        select_frame_grid.addWidget(job_label, 0, 0)
        select_frame_grid.addWidget(self.job_line, 0, 1)
        select_frame_grid.addWidget(empty_label, 0, 2)
        select_frame_grid.addWidget(issue_label, 0, 3)
        select_frame_grid.addWidget(self.issue_combo, 0, 4)
        select_frame_grid.addWidget(empty_label, 0, 5)
        select_frame_grid.addWidget(check_button, 0, 6)

        select_frame_grid.setColumnStretch(0, 1)
        select_frame_grid.setColumnStretch(1, 3)
        select_frame_grid.setColumnStretch(2, 3)
        select_frame_grid.setColumnStretch(3, 1)
        select_frame_grid.setColumnStretch(4, 3)
        select_frame_grid.setColumnStretch(5, 3)
        select_frame_grid.setColumnStretch(6, 1)

        self.select_frame.setLayout(select_frame_grid)

    def gen_info_frame(self):
        # self.info_frame
        self.info_text = QTextEdit(self.info_frame)

        # self.info_frame - Grid
        info_frame_grid = QGridLayout()
        info_frame_grid.addWidget(self.info_text, 0, 0)
        self.info_frame.setLayout(info_frame_grid)

    def set_issue_combo(self):
        self.issue_combo.addItem(self.issue)

        issue_list = ['PEND', 'SLOW', 'FAIL']

        for issue in issue_list:
            if issue != self.issue:
                self.issue_combo.addItem(issue)

    def check_issue(self):
        self.info_text.clear()
        job = self.job_line.text().strip()

        if not job:
            self.info_text.append('<font color="#FF0000">*Error*: Please specify "Job" first.</font>')
        else:
            command = 'bjobs -UF ' + str(job)
            job_dic = common_lsf.get_bjobs_uf_info(command)

            if job not in job_dic:
                self.info_text.append('<font color="#FF0000">*Error*: "' + str(job) + '": No such job.</font>')
            else:
                if self.issue_combo.currentText().strip() == 'PEND':
                    self.check_pend_issue(job, job_dic)
                elif self.issue_combo.currentText().strip() == 'SLOW':
                    self.check_slow_issue(job, job_dic)
                elif self.issue_combo.currentText().strip() == 'FAIL':
                    self.check_fail_issue(job, job_dic)

    def check_pend_issue(self, job, job_dic):
        self.info_text.clear()

        if job_dic[job]['status'] != 'PEND':
            self.info_text.append('<font color="#FF0000">*Error*: Job status is "' + str(job_dic[job]['status']) + '"!</font>')
        else:
            for (i, line) in enumerate(job_dic[job]['pending_reasons']):
                self.info_text.append('[Reason ' + str(i) + '] : ' + str(line))

                if re.search(r'New job is waiting for scheduling',  line):
                    self.info_text.append('                    任务分发中, 请耐心等待')
                elif re.search(r'Not enough job slot',  line):
                    self.info_text.append('                    cpu需求不能满足, 请耐心等待队列资源.')

                    if job_dic[job]['processors_requested']:
                        self.info_text.append('                    cpu : ' + str(job_dic[job]['processors_requested']) + ' slot(s)')
                elif re.search(r'Job slot limit reached',  line):
                    self.info_text.append('                    cpu需求不能满足, 请耐心等待队列资源.')

                    if job_dic[job]['processors_requested']:
                        self.info_text.append('                    cpu : ' + str(job_dic[job]['processors_requested']) + ' slot(s)')
                elif re.search(r'Not enough processors to meet the job\'s spanning requirement',  line):
                    self.info_text.append('                    cpu需求不能满足, 请耐心等待队列资源.')

                    if job_dic[job]['processors_requested']:
                        self.info_text.append('                    cpu : ' + str(job_dic[job]['processors_requested']) + ' slot(s)')
                elif re.search(r'Job requirements for reserving resource \(mem\) not satisfied',  line):
                    self.info_text.append('                    mem需求不能满足, 请耐心等待队列资源, 如有必要申请专有队列.')

                    if job_dic[job]['requested_resources']:
                        self.info_text.append('                    mem : ' + str(job_dic[job]['requested_resources']))
                elif re.search(r'Job\'s requirements for resource reservation not satisfied \(Resource: mem\)',  line):
                    self.info_text.append('                    mem需求不能满足, 请耐心等待队列资源, 如有必要申请专有队列.')

                    if job_dic[job]['requested_resources']:
                        self.info_text.append('                    mem : ' + str(job_dic[job]['requested_resources']))
                elif re.search(r'There are no suitable hosts for the job',  line):
                    self.info_text.append('                    资源申请不能满足, 请检查资源申请条件是否过于苛刻.')

                    if job_dic[job]['processors_requested']:
                        self.info_text.append('                    cpu : ' + str(job_dic[job]['processors_requested']) + ' slot(s)')

                    if job_dic[job]['requested_resources']:
                        self.info_text.append('                    mem : ' + str(job_dic[job]['requested_resources']))
                elif re.search(r'User has reached the per-user job slot limit of the queue',  line):
                    self.info_text.append('                    queue限制, 请耐心等待队列资源.')

            self.info_text.append('')
            self.info_text.append('备注 : job PEND原因浮动变化, 仅了解PEND的核心瓶颈所在即可.')

    def check_slow_issue(self, job, job_dic):
        if job_dic[job]['status'] != 'RUN':
            self.info_text.append('<font color="#FF0000">*Error*: Job status is "' + str(job_dic[job]['status']) + '"!</font>')
        else:
            self.info_text.clear()
            self.info_text.append('Step 1: Check "STAT" on Process Tracer.')
            self.info_text.append('            STAT "R" means "RUN".')
            self.info_text.append('            STAT "S" means "SLEEP".')
            self.info_text.append('Step 2: If there is "R" STAT on any process.')
            self.info_text.append('            Process status is ok, Please check EDA tool setting.')
            self.info_text.append('Step 3: If all STAT are "S".')
            self.info_text.append('            Find key command, click command pid on Process Tracer.')
            self.info_text.append('            Check what EDA tool is doing with strace terminal.')

            self.my_process_tracer = ProcessTracer(job)
            self.my_process_tracer.start()

    def check_fail_issue(self, job, job_dic):
        self.info_text.clear()
        self.info_text.append('Status: ' + str(job_dic[job]['status']))

        if job_dic[job]['status'] == 'DONE':
            self.info_text.append('Job done sucessfully.')
            self.info_text.append('The issue should be from your command, please check your command log.')
        elif job_dic[job]['status'] == 'EXIT':
            if job_dic[job]['exit_code']:
                self.info_text.append('Exit Code: ' + str(job_dic[job]['exit_code']))

                if job_dic[job]['exit_code'] in self.exit_code_dic:
                    self.info_text.append('Exit Reason: ' + str(self.exit_code_dic[job_dic[job]['exit_code']]))

            self.info_text.append('')

            if job_dic[job]['exit_code'] and (int(job_dic[job]['exit_code']) <= 127):
                self.info_text.append('* Exit code <= 127, LSF job command run fail, please check command log.')
            elif job_dic[job]['exit_code'] and (int(job_dic[job]['exit_code']) > 127):
                self.info_text.append('* Exit code > 127, possible fail for system or LSF reason.')

            if job_dic[job]['term_owner']:
                self.info_text.append('* Find message "' + str(job_dic[job]['term_owner']) + '".')

            if job_dic[job]['lsf_signal']:
                self.info_text.append('* Find message "Exited by LSF signal ' + str(job_dic[job]['lsf_signal']) + '".')
        else:
            self.info_text.append('<font color="#FF0000">*Error*: Job is not finished!</font>')


class ProcessTracer(QThread):
    """
    Start tool process_tracer to trace job process.
    """
    def __init__(self, job):
        super(ProcessTracer, self).__init__()
        self.job = job

    def run(self):
        command = str(str(os.environ['LSFMONITOR_INSTALL_PATH'])) + '/monitor/tools/process_tracer -j ' + str(self.job)
        os.system(command)


################
# Main Process #
################
def main():
    (job, issue) = read_args()
    app = QApplication(sys.argv)
    mw = MainWindow(job, issue)
    mw.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
