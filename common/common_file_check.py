import os
import re
import sys


class FileCheck():
    """
    Basic function for file check:
    * check_file_exist       : Check file exist or not, result is PASSED/FAILED.
    * check_error_message    : Check error message exist or not, result is PASSED/FAILED.
    * check_warning_message  : Check warning message exist or not, result is PASSED/FAILED/REVIEW.
    * check_expected_message : Check expected message exist or not, result is PASSED/FAILED.
    * reiew_file             : Reivew file, result is FAILED/REVIEW.
    """

    def __init__(self, report_dir='', log_head='file_check'):
        self.report_dir = report_dir
        self.log_head = log_head

        # Set default check report_dir.
        if self.report_dir == '':
            CWD = os.getcwd()
            self.report_dir = str(CWD) + '/file_check'

        # Create report_dir if it not exists.
        if not os.path.exists(self.report_dir):
            try:
                os.makedirs(self.report_dir)
            except Exception as error:
                print('*Error*: Failed on creating report directory "' + str(self.report_dir) + '": ' + str(error))
                sys.exit(1)

        self.report = str(self.report_dir) + '/' + str(self.log_head) + '.rpt'

        if os.path.exists(self.report):
            os.remove(self.report)

        self.counter = 0
        self.final_return_code = 0
        self.check_result_list = []

    def get_log_file(self):
        """
        Specify an unique log file for every check item.
        Remove old log file.
        """
        # Increasing self.counter can avoid repeating log name.
        self.counter += 1
        log_file = str(self.report_dir) + '/' + str(self.log_head) + '.' + str(self.counter) + '.log'

        if os.path.exists(log_file):
            try:
                os.remove(log_file)
            except Exception as error:
                print('*Error*: Failed on removing old log file "' + str(log_file) + '": ' + str(error))
                sys.exit(1)

        return(log_file)

    def write_report(self, description, log_file, result):
        """
        Write result (PASSED/FAILED/REVIEW) into check report.
        """
        result_string = str(result) + ' : ' + str(description)

        if (result == 'FAILED') or (result == 'REVIEW'):
            if result == 'FAILED':
                self.final_return_code += 1

            result_string = str(result_string) + '    (details please see ' + str(log_file) + ')'

        with open(self.report, 'a') as REPORT:
            REPORT.write(str(result_string) + '\n')

    def save_result(self, description, file_list, result, message_list=[], waive_message_list=[]):
        """
        Save specified result into self.check_result_list.
        """
        result_dic = {'description': description,
                      'file_list': file_list,
                      'result': result,
                      'message_list': message_list,
                      'waive_message_list': waive_message_list}

        self.check_result_list.append(result_dic)

    def check_file_exist(self, description, file_list):
        """
        Check specified files exist or not.
        Return "PASSED" if all files exists.
        Return "FAILED" if any one is missing.
        """
        log_file = self.get_log_file()
        result = 'PASSED'

        with open(log_file, 'w') as LOG:
            for file_name in file_list:
                LOG.write('>>> File : ' + str(file_name) + ' (check file exist)\n')

                if not os.path.exists(file_name):
                    LOG.write('    File "' + str(file_name) + '" is missing.\n')
                    result = 'FAILED'

        self.write_report(description, log_file, result)
        self.save_result(description, file_list, result)

        return(result)

    def search_message(self, line, message_list, waive_message_list=[]):
        """
        Try to find the specified message(s) on line string.
        """
        for message in message_list:
            if re.search(message, line):
                for waive_message in waive_message_list:
                    if re.search(waive_message, line):
                        return(False, '')

                return(True, message)

        return(False, '')

    def check_message(self, check_type, description, file_list, message_list, waive_message_list=[]):
        """
        Check error/warning/expected messages with specified files.
        Type "error":
        Return "PASSED" if not find any error message.
        Return "FAILED" if find any error message.
        Type "warning":
        Return "PASSED" if not find any warning message.
        Return "FAILED" if the specified file is missing.
        Return "REVIEW" if find any warning message.
        Type "expected":
        Return "PASSED" if find all expected messages.
        Return "FAILED" if not find all expected messages.
        """
        log_file = self.get_log_file()
        result = 'PASSED'

        with open(log_file, 'w') as LOG:
            for file in file_list:
                LOG.write('>>> File : ' + str(file) + ' (check ' + str(check_type) + 'message)\n')

                if not os.path.exists(file):
                    LOG.write('    File "' + str(file) + '" is missing\n')
                    result = 'FAILED'
                else:
                    match_dic = {}

                    for message in message_list:
                        match_dic[message] = 0

                    try:
                        with open(file, 'rb') as FILE:
                            line_num = 0

                            for line in FILE.readlines():
                                try:
                                    line = str(line, 'utf-8')
                                    line = line.strip()
                                except Exception as warning:
                                    print('*Warning*: Failed on reading line ' + str(line_num) + ': ' + str(warning))
                                    continue

                                line_num += 1
                                (match, match_message) = self.search_message(line, message_list, waive_message_list)

                                if match:
                                    match_dic[match_message] += 1

                                    LOG.write('    Line ' + str(line_num) + ' : ' + str(line) + '\n')

                                    if check_type == 'error':
                                        result = 'FAILED'
                                    elif check_type == 'warning':
                                        if result == 'PASSED':
                                            result = 'REVIEW'
                    except Exception as error:
                        print('*Error*: Failed on opening file "' + str(file) + '" for read: ' + str(error))
                        LOG.write('    *Error*: Failed on opening file "' + str(file) + '" for read: ' + str(error) + '\n')
                        result = 'FAILED'

                    if check_type == 'expected':
                        for (key, value) in match_dic.items():
                            if value == 0:
                                result = 'FAILED'

        self.write_report(description, log_file, result)
        self.save_result(description, file_list, result, message_list, waive_message_list)

        return(result)

    def check_error_message(self, description, file_list, error_message_list, waive_message_list=[]):
        result = self.check_message('error', description, file_list, error_message_list, waive_message_list)
        return(result)

    def check_warning_message(self, description, file_list, warning_message_list, waive_message_list=[]):
        result = self.check_message('warning', description, file_list, warning_message_list, waive_message_list)
        return(result)

    def check_expected_message(self, description, file_list, expected_message_list, waive_message_list=[]):
        result = self.check_message('expected', description, file_list, expected_message_list, waive_message_list)
        return(result)

    def review_file(self, description, file_list):
        """
        Link specified file to log file.
        Return "REVIEW" if all files exist.
        Return "FAILED" if any file missing.
        """
        result = 'REVIEW'

        for file in file_list:
            file = os.path.abspath(file)
            log_file = self.get_log_file()

            if os.path.exists(file):
                try:
                    os.symlink(file, log_file)
                except Exception as error:
                    with open(log_file, 'w') as LOG:
                        LOG.write('>>> File : ' + str(file) + ' (review file)\n')
                        LOG.write('    Failed on linking "' + str(file) + '" to "' + str(log_file) + '": ' + str(error))
            else:
                with open(log_file, 'w') as LOG:
                    LOG.write('>>> File : ' + str(file) + ' (review file)\n')
                    LOG.write('    File "' + str(file) + '" is missing\n')

        self.write_report(description, log_file, result)
        self.save_result(description, file_list, result)

        return(result)
