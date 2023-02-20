import os
import re
import sys
import time
import datetime

sys.path.append(str(os.environ['LSFMONITOR_INSTALL_PATH']) + '/monitor')
from common import common

os.environ['PYTHONUNBUFFERED'] = '1'


class GetLicenseInfo():
    def __init__(self, specified_feature='', lmstat_path='lmstat', bsub_command='bsub -q normal -Is'):
        self.specified_feature = specified_feature
        self.lmstat_path = lmstat_path
        self.bsub_command = bsub_command
        self.lmstat_command = self.get_lmstat_command()

    def get_lmstat_command(self):
        """
        Get reasonable lmstat command, it is used to get license usage information.
        """
        lmstat_command = str(self.lmstat_path) + ' -a -i'

        if self.specified_feature:
            lmstat_command = str(lmstat_command) + ' ' + str(self.specified_feature)

        if self.bsub_command:
            lmstat_command = str(self.bsub_command) + ' "' + str(lmstat_command) + '"'
        elif 'lmstat_bsub_command' in os.environ:
            lmstat_command = str(os.environ['lmstat_bsub_command']) + ' "' + str(lmstat_command) + '"'

        return (lmstat_command)

    def init_license_dic(self):
        """
        Initial license_dic.
        """
        license_dic = {}

        if 'LM_LICENSE_FILE' in os.environ:
            lm_license_file_list = os.environ['LM_LICENSE_FILE'].split(':')

            for lm_license_file in lm_license_file_list:
                if lm_license_file:
                    license_dic[lm_license_file] = {'license_files': '',
                                                    'license_server_status': 'UNKNOWN',
                                                    'license_server_version': '',
                                                    'vendor_daemon': {}}

        return (license_dic)

    def get_license_info(self):
        """
        Get EDA liecnse feature usage and expires information on license_dic.
        license_dic format is like below:
        license_dic = {
                       'license_files': '',
                       'license_server_status': 'UNKNOWN',
                       'license_server_version': '',
                       'vendor_daemon': { vendor_daemon: {
                                                          'vendor_daemon_status': 'UP',
                                                          'vendor_daemon_version': '',
                                                          'feature': {feature: {
                                                                                'issued': 0,
                                                                                'in_use': 0,
                                                                                'in_use_info_string': [],
                                                                                'in_use_info': [],
                                                                               },
                                                                     },
                                                          'expires': {feature: {
                                                                                'version': '',
                                                                                'license': '',
                                                                                'vendor': '',
                                                                                'expires': '',
                                                                               },
                                                                     },
                                                         },
                                        },
                      }
        """
        # Get lmstat output message.
        (return_code, stdout, stderr) = common.run_command(self.lmstat_command)

        # Parse lmstat output message.
        license_dic = self.init_license_dic()
        license_server = ''
        vendor_daemon = ''
        feature = ''
        expires_mark = False
        vendor_daemon_status_mark = False

        license_compile_dic = {'empty_line': re.compile(r'^\s*$'),
                               'license_server_status': re.compile(r'^\s*License server status: (\S+)\s*$'),
                               'license_files': re.compile(r'^\s*License file\(s\) on (\S+): (\S+):\s*$'),
                               'license_server': re.compile(r'^\s*(\S+): license server (\S+?) .* (\S+?)\s*$'),
                               'vendor_daemon_status': re.compile(r'^\s*Vendor daemon status \(on (.+)\):\s*$'),
                               'vendor_daemon_up': re.compile(r'^\s*(\S+): UP (\S+)\s*$'),
                               'vendor_daemon_down': re.compile(r'^\s*(\S+): (The desired vendor daemon is down|Cannot read data from license server system)\..*$'),
                               'users_of_feature': re.compile(r'^Users of (\S+):  \(Total of ([0-9]+) license(s?) issued;  Total of ([0-9]+) license(s?) in use\)\s*$'),
                               'in_use_info': re.compile(r'^\s*(\S+)\s+(\S+)\s+(\S+)?\s*(.+)?\s*\((\S+)\)\s+\((\S+)\s+(\d+)\), start (.+?)(,\s+(\d+)\s+licenses)?\s*$'),
                               'reservation': re.compile(r'^\s*(\d+)\s+RESERVATION for (HOST|HOST_GROUP)\s+(\S+)\s+\((\S+)(\s+(\d+))?\)\s*$'),
                               'feature_expires': re.compile(r'^Feature .* Expires\s*$'),
                               'expire_info': re.compile(r'^(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(permanent\(no expiration date\)|[0-9]{1,2}-[a-zA-Z]{3}-[0-9]{4})\s*$')}

        for line in str(stdout, 'utf-8').split('\n'):
            line = line.strip()

            if license_compile_dic['empty_line'].match(line):
                continue
            elif expires_mark and license_compile_dic['expire_info'].match(line):
                my_match = license_compile_dic['expire_info'].match(line)
                feature = my_match.group(1)
                expire_dic = {'version': my_match.group(2),
                              'license': my_match.group(3),
                              'vendor': my_match.group(4),
                              'expires': my_match.group(5)}

                for vendor_daemon in license_dic[license_server]['vendor_daemon'].keys():
                    if feature in license_dic[license_server]['vendor_daemon'][vendor_daemon]['feature']:
                        license_dic[license_server]['vendor_daemon'][vendor_daemon]['expires'].setdefault(feature, [])
                        license_dic[license_server]['vendor_daemon'][vendor_daemon]['expires'][feature].append(expire_dic)
            elif license_compile_dic['users_of_feature'].match(line):
                my_match = license_compile_dic['users_of_feature'].match(line)
                feature = my_match.group(1)
                issued_num = my_match.group(2)
                in_use_num = my_match.group(4)

                license_dic[license_server]['vendor_daemon'][vendor_daemon]['feature'].setdefault(feature, {'issued': issued_num,
                                                                                                            'in_use': in_use_num,
                                                                                                            'in_use_info_string': [],
                                                                                                            'in_use_info': []})
            elif license_compile_dic['in_use_info'].match(line):
                my_match = license_compile_dic['in_use_info'].match(line)
                usage_dic = {'user': my_match.group(1),
                             'execute_host': my_match.group(2),
                             'submit_host': 'N/A',
                             'version': my_match.group(5),
                             'license_server': my_match.group(6),
                             'start_time': my_match.group(8),
                             'license_num': '1'}

                # Update submit_host.
                display_setting = my_match.group(3)

                if display_setting:
                    if re.match(r'^(.+):.+$', display_setting):
                        display_match = re.match(r'^(.+):.+$', display_setting)
                        usage_dic['submit_host'] = display_match.group(1)

                # Update start_time.
                if re.match(r'^(.+?)\s*\(.*\)\s*$', usage_dic['start_time']):
                    my_match = re.match(r'^(.+?)\s*\(.*\)\s*$', usage_dic['start_time'])
                    usage_dic['start_time'] = my_match.group(1)

                license_num_setting = my_match.group(9)

                if license_num_setting:
                    usage_dic['license_num'] = my_match.group(10)

                license_dic[license_server]['vendor_daemon'][vendor_daemon]['feature'][feature]['in_use_info_string'].append(line.strip())
                license_dic[license_server]['vendor_daemon'][vendor_daemon]['feature'][feature]['in_use_info'].append(usage_dic)
            elif license_compile_dic['reservation'].match(line):
                my_match = license_compile_dic['reservation'].match(line)
                usage_dic = {'user': 'N/A',
                             'execute_host': my_match.group(3),
                             'submit_host': 'N/A',
                             'version': 'N/A',
                             'license_server': my_match.group(4),
                             'start_time': 'N/A',
                             'license_num': my_match.group(1)}

                license_dic[license_server]['vendor_daemon'][vendor_daemon]['feature'][feature]['in_use_info_string'].append(line.strip())
                license_dic[license_server]['vendor_daemon'][vendor_daemon]['feature'][feature]['in_use_info'].append(usage_dic)
            elif license_compile_dic['license_server_status'].match(line):
                my_match = license_compile_dic['license_server_status'].match(line)
                license_server = my_match.group(1)
                license_dic.setdefault(license_server, {'license_files': '',
                                                        'license_server_status': 'UNKNOWN',
                                                        'license_server_version': '',
                                                        'vendor_daemon': {}})
                expires_mark = False
                vendor_daemon_status_mark = False
                vendor_daemon = ''
            elif license_compile_dic['license_files'].match(line):
                my_match = license_compile_dic['license_files'].match(line)
                license_dic[license_server]['license_files'] = my_match.group(2)
            elif license_compile_dic['license_server'].match(line):
                # License Manager Status—Status of each license server manager. Click the Update Status button to immediately refresh the status display for the license server.
                # • Up—License server is currently running.
                # • Down—License server is currently not running.
                # • Unknown—License server status is not known.
                # • Lost quorum—For license-server triads, this means that the quorum has been lost. A quorum requires that at least two of the three license servers are running and communicating with each other.
                my_match = license_compile_dic['license_server'].match(line)
                license_dic[license_server]['license_server_status'] = my_match.group(2)
                license_dic[license_server]['license_server_version'] = my_match.group(3)
            elif license_compile_dic['vendor_daemon_status'].match(line):
                vendor_daemon_status_mark = True
            elif vendor_daemon_status_mark and license_compile_dic['vendor_daemon_up'].match(line):
                my_match = license_compile_dic['vendor_daemon_up'].match(line)
                vendor_daemon = my_match.group(1)
                license_dic[license_server]['vendor_daemon'].setdefault(vendor_daemon, {'vendor_daemon_status': 'UP',
                                                                                        'vendor_daemon_version': my_match.group(2),
                                                                                        'feature': {},
                                                                                        'expires': {}})
            elif license_compile_dic['feature_expires'].match(line):
                expires_mark = True

                if vendor_daemon:
                    license_dic[license_server]['vendor_daemon'][vendor_daemon].setdefault('expires', {})
            elif vendor_daemon_status_mark and license_compile_dic['vendor_daemon_down'].match(line):
                my_match = license_compile_dic['vendor_daemon_down'].match(line)
                down_vendor_daemon = my_match.group(1)
                license_dic[license_server]['vendor_daemon'].setdefault(down_vendor_daemon, {'vendor_daemon_status': 'DOWN',
                                                                                             'vendor_daemon_version': '',
                                                                                             'feature': {},
                                                                                             'expires': {}})

        return (license_dic)


class FilterLicenseDic():
    """
    Filter license_dic with server/vendor/feature/submit_host/execute_host/user/show_mode specification.
    Get a new license_dic.
    """
    def __init__(self):
        pass

    def filter_by_server(self, license_dic, server_list):
        new_license_dic = {}

        for license_server in license_dic.keys():
            if (license_server in server_list) or ('ALL' in server_list):
                new_license_dic.setdefault(license_server, license_dic[license_server])

        return (new_license_dic)

    def filter_by_vendor(self, license_dic, vendor_list):
        new_license_dic = {}

        for license_server in license_dic.keys():
            for vendor_daemon in license_dic[license_server]['vendor_daemon'].keys():
                if (vendor_daemon in vendor_list) or ('ALL' in vendor_list):
                    new_license_dic.setdefault(license_server, {'license_files': license_dic[license_server]['license_files'],
                                                                'license_server_status': license_dic[license_server]['license_server_status'],
                                                                'license_server_version': license_dic[license_server]['license_server_version'],
                                                                'vendor_daemon': {}})
                    new_license_dic[license_server]['vendor_daemon'].setdefault(vendor_daemon, license_dic[license_server]['vendor_daemon'][vendor_daemon])

        return (new_license_dic)

    def filter_by_feature(self, license_dic, feature_list):
        # Get filtered_feature_list from exact_feature_list/fuzzy_feature_list.
        exact_feature_list = []
        fuzzy_feature_list = []
        filtered_feature_list = []

        for license_server in license_dic.keys():
            for vendor_daemon in license_dic[license_server]['vendor_daemon'].keys():
                for feature in license_dic[license_server]['vendor_daemon'][vendor_daemon]['feature'].keys():
                    if (feature in feature_list) or ('ALL' in feature_list):
                        if feature not in exact_feature_list:
                            exact_feature_list.append(feature)

                    for specified_feature in feature_list:
                        if re.search(specified_feature.lower(), feature.lower()):
                            if feature not in fuzzy_feature_list:
                                fuzzy_feature_list.append(feature)

        if exact_feature_list:
            filtered_feature_list = exact_feature_list
        elif fuzzy_feature_list:
            filtered_feature_list = fuzzy_feature_list

        # Filter by feature.
        new_license_dic = {}

        if filtered_feature_list:
            for license_server in license_dic.keys():
                for vendor_daemon in license_dic[license_server]['vendor_daemon'].keys():
                    for feature in license_dic[license_server]['vendor_daemon'][vendor_daemon]['feature'].keys():
                        if feature in filtered_feature_list:
                            new_license_dic.setdefault(license_server, {'license_files': license_dic[license_server]['license_files'],
                                                                        'license_server_status': license_dic[license_server]['license_server_status'],
                                                                        'license_server_version': license_dic[license_server]['license_server_version'],
                                                                        'vendor_daemon': {}})
                            new_license_dic[license_server]['vendor_daemon'].setdefault(vendor_daemon, {'vendor_daemon_status': license_dic[license_server]['vendor_daemon'][vendor_daemon]['vendor_daemon_status'],
                                                                                                        'vendor_daemon_version': license_dic[license_server]['vendor_daemon'][vendor_daemon]['vendor_daemon_version'],
                                                                                                        'feature': {},
                                                                                                        'expires': {}})
                            new_license_dic[license_server]['vendor_daemon'][vendor_daemon]['feature'].setdefault(feature, license_dic[license_server]['vendor_daemon'][vendor_daemon]['feature'][feature])

                            if feature in license_dic[license_server]['vendor_daemon'][vendor_daemon]['expires']:
                                new_license_dic[license_server]['vendor_daemon'][vendor_daemon]['expires'].setdefault(feature, license_dic[license_server]['vendor_daemon'][vendor_daemon]['expires'][feature])

        return (new_license_dic)

    def filter_by_feature_usage_attribute(self, license_dic, feature_usage_attribute, feature_usage_attribute_list):
        new_license_dic = {}

        for license_server in license_dic.keys():
            for vendor_daemon in license_dic[license_server]['vendor_daemon'].keys():
                for feature in license_dic[license_server]['vendor_daemon'][vendor_daemon]['feature'].keys():
                    for (i, usage_dic) in enumerate(license_dic[license_server]['vendor_daemon'][vendor_daemon]['feature'][feature]['in_use_info']):
                        if (usage_dic[feature_usage_attribute] in feature_usage_attribute_list) or ('ALL' in feature_usage_attribute_list):
                            new_license_dic.setdefault(license_server, {'license_files': license_dic[license_server]['license_files'],
                                                                        'license_server_status': license_dic[license_server]['license_server_status'],
                                                                        'license_server_version': license_dic[license_server]['license_server_version'],
                                                                        'vendor_daemon': {}})
                            new_license_dic[license_server]['vendor_daemon'].setdefault(vendor_daemon, {'vendor_daemon_status': license_dic[license_server]['vendor_daemon'][vendor_daemon]['vendor_daemon_status'],
                                                                                                        'vendor_daemon_version': license_dic[license_server]['vendor_daemon'][vendor_daemon]['vendor_daemon_version'],
                                                                                                        'feature': {},
                                                                                                        'expires': license_dic[license_server]['vendor_daemon'][vendor_daemon]['expires']})
                            new_license_dic[license_server]['vendor_daemon'][vendor_daemon]['feature'].setdefault(feature, {'issued': license_dic[license_server]['vendor_daemon'][vendor_daemon]['feature'][feature]['issued'],
                                                                                                                            'in_use': license_dic[license_server]['vendor_daemon'][vendor_daemon]['feature'][feature]['in_use'],
                                                                                                                            'in_use_info_string': [],
                                                                                                                            'in_use_info': []})
                            new_license_dic[license_server]['vendor_daemon'][vendor_daemon]['feature'][feature]['in_use_info_string'].append(license_dic[license_server]['vendor_daemon'][vendor_daemon]['feature'][feature]['in_use_info_string'][i])
                            new_license_dic[license_server]['vendor_daemon'][vendor_daemon]['feature'][feature]['in_use_info'].append(usage_dic)

        return (new_license_dic)

    def filter_by_submit_host(self, license_dic, submit_host_list):
        new_license_dic = self.filter_by_feature_usage_attribute(license_dic, 'submit_host', submit_host_list)
        return (new_license_dic)

    def filter_by_execute_host(self, license_dic, execute_host_list):
        new_license_dic = self.filter_by_feature_usage_attribute(license_dic, 'execute_host', execute_host_list)
        return (new_license_dic)

    def filter_by_user(self, license_dic, user_list):
        new_license_dic = self.filter_by_feature_usage_attribute(license_dic, 'user', user_list)
        return (new_license_dic)

    def filter_show_mode_feature(self, license_dic, show_mode):
        new_license_dic = {}

        for license_server in license_dic.keys():
            for vendor_daemon in license_dic[license_server]['vendor_daemon'].keys():
                for feature in license_dic[license_server]['vendor_daemon'][vendor_daemon]['feature'].keys():
                    expire_dic_list = []

                    if show_mode == 'IN_USE':
                        if license_dic[license_server]['vendor_daemon'][vendor_daemon]['feature'][feature]['in_use'] == '0':
                            continue
                        else:
                            if feature in license_dic[license_server]['vendor_daemon'][vendor_daemon]['expires']:
                                for expire_dic in license_dic[license_server]['vendor_daemon'][vendor_daemon]['expires'][feature]:
                                    expire_dic_list.append(expire_dic)
                    elif show_mode in ['Expired', 'Nearly_Expired', 'Unexpired']:
                        if feature in license_dic[license_server]['vendor_daemon'][vendor_daemon]['expires']:
                            for expire_dic in license_dic[license_server]['vendor_daemon'][vendor_daemon]['expires'][feature]:
                                expire_mark = check_expire_date(expire_dic['expires'])

                                if (show_mode == 'Expired') and (expire_mark == -1):
                                    expire_dic_list.append(expire_dic)
                                elif (show_mode == 'Nearly_Expired') and ((expire_mark != -1) and (expire_mark != 0)):
                                    expire_dic_list.append(expire_dic)
                                elif (show_mode == 'Unexpired') and (expire_mark == 0):
                                    expire_dic_list.append(expire_dic)

                        if not expire_dic_list:
                            continue

                    new_license_dic.setdefault(license_server, {'license_files': license_dic[license_server]['license_files'],
                                                                'license_server_status': license_dic[license_server]['license_server_status'],
                                                                'license_server_version': license_dic[license_server]['license_server_version'],
                                                                'vendor_daemon': {}})
                    new_license_dic[license_server]['vendor_daemon'].setdefault(vendor_daemon, {'vendor_daemon_status': license_dic[license_server]['vendor_daemon'][vendor_daemon]['vendor_daemon_status'],
                                                                                                'vendor_daemon_version': license_dic[license_server]['vendor_daemon'][vendor_daemon]['vendor_daemon_version'],
                                                                                                'feature': {},
                                                                                                'expires': {}})
                    new_license_dic[license_server]['vendor_daemon'][vendor_daemon]['feature'].setdefault(feature, license_dic[license_server]['vendor_daemon'][vendor_daemon]['feature'][feature])
                    new_license_dic[license_server]['vendor_daemon'][vendor_daemon]['expires'].setdefault(feature, expire_dic_list)

        return (new_license_dic)

    def run(self, license_dic, server_list=[], vendor_list=[], feature_list=[], submit_host_list=[], execute_host_list=[], user_list=[], show_mode='ALL'):
        filtered_license_dic = license_dic

        if server_list:
            filtered_license_dic = self.filter_by_server(filtered_license_dic, server_list)

        if vendor_list:
            filtered_license_dic = self.filter_by_vendor(filtered_license_dic, vendor_list)

        if feature_list:
            filtered_license_dic = self.filter_by_feature(filtered_license_dic, feature_list)

        if submit_host_list:
            filtered_license_dic = self.filter_by_submit_host(filtered_license_dic, submit_host_list)

        if execute_host_list:
            filtered_license_dic = self.filter_by_execute_host(filtered_license_dic, execute_host_list)

        if user_list:
            filtered_license_dic = self.filter_by_user(filtered_license_dic, user_list)

        if show_mode != 'ALL':
            filtered_license_dic = self.filter_show_mode_feature(filtered_license_dic, show_mode)

        return (filtered_license_dic)


def switch_start_time(start_time):
    new_start_time = start_time

    if start_time and (start_time != 'N/A'):
        # Switch start_time to start_seconds.
        current_year = datetime.date.today().year
        start_time_with_year = str(current_year) + ' ' + str(start_time)

        try:
            start_seconds = time.mktime(time.strptime(start_time_with_year, '%Y %a %m/%d %H:%M'))
        except Exception:
            print('*Error*: variable "start_time_with_year", value is "' + str(start_time_with_year) + '", not follow the time format "%Y %a %m/%d %H:%M".')

        current_seconds = time.time()

        if int(start_seconds) > int(current_seconds):
            current_year = int(datetime.date.today().year) - 1
            start_time_with_year = str(current_year) + ' ' + str(start_time)
            start_seconds = time.mktime(time.strptime(start_time_with_year, '%Y %a %m/%d %H:%M'))

        # Switch start_seconds to expected time format.
        new_start_time = time.strftime('%Y-%m-%d %H:%M', time.localtime(start_seconds))

    return (new_start_time)


def switch_expires_date(expires_date):
    new_expires_date = expires_date

    if re.match(r'^\d+-[a-zA-Z]+-\d{4}$', expires_date):
        new_expires_date = datetime.datetime.strptime(expires_date, '%d-%b-%Y').strftime('%Y-%m-%d')

    return (new_expires_date)


def check_long_runtime(start_time, second_threshold=259200):
    """
    Runtime is more than second_threshold (default is 3 days), return True.
    Runtime is less than second_threshold (default is 3 days), return False.
    """
    if start_time and (start_time != 'N/A'):
        current_year = datetime.date.today().year
        start_time_with_year = str(current_year) + ' ' + str(start_time)
        start_seconds = int(time.mktime(time.strptime(start_time_with_year, '%Y %a %m/%d %H:%M')))
        current_seconds = int(time.time())

        if start_seconds > current_seconds:
            current_year = int(datetime.date.today().year) - 1
            start_time_with_year = str(current_year) + ' ' + str(start_time)
            start_seconds = int(time.mktime(time.strptime(start_time_with_year, '%Y %a %m/%d %H:%M')))

        if current_seconds - start_seconds >= second_threshold:
            return (True)

    return (False)


def check_expire_date(expire_date, second_threshold=1209600):
    """
    Expired, return -1.
    Expire in second_threshold (default is 14 days), return day number.
    Expire later than second_threshold (default is 14 days), return 0.
    """
    if re.search(r'permanent', expire_date):
        return (0)
    else:
        expire_seconds = int(time.mktime(time.strptime(expire_date, '%d-%b-%Y')))
        expire_seconds = expire_seconds + 86400
        current_seconds = int(time.time())

        if expire_seconds < current_seconds:
            return (-1)
        elif expire_seconds - current_seconds <= second_threshold:
            return ((expire_seconds - current_seconds)//86400 + 1)
        else:
            return (0)


def parse_license_file(license_file):
    license_file_dic = {'server': {},
                        'vendor': {},
                        'feature': []}
    server_compile = re.compile(r'^\s*SERVER\s+(\S+)\s+(\S+)\s+(\S+)\s*$')
    vendor_daemon_compile = re.compile(r'^\s*(VENDOR|DAEMON)\s+(\S+)\s*(\S+)?\s*(.+)?$')
    feature_compile = re.compile(r'^\s*(FEATURE|INCREMENT)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+.*$')

    with open(license_file,  'r', errors='ignore') as LF:
        for line in LF.readlines():
            if feature_compile.match(line):
                my_match = feature_compile.match(line)
                feature_dic = {'feature': my_match.group(2),
                               'vendor': my_match.group(3),
                               'version': my_match.group(4),
                               'expire_date': my_match.group(5),
                               'num': my_match.group(6)}
                license_file_dic['feature'].append(feature_dic)
            elif server_compile.match(line):
                my_match = server_compile.match(line)
                license_file_dic['server'] = {'host': my_match.group(1),
                                              'hostid': my_match.group(2),
                                              'port': my_match.group(3)}
            elif vendor_daemon_compile.match(line):
                my_match = vendor_daemon_compile.match(line)
                license_file_dic['vendor'] = {'vendor': my_match.group(2),
                                              'vendor_daemon_path': my_match.group(3)}

    return (license_file_dic)
