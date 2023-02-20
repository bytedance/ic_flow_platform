# -*- coding: utf-8 -*-
################################
# File Name   : seedb.py
# Author      : liyanqing
# Created On  : 2020-10-01 00:00:00
# Description :
################################
import os
import re
import sys
import argparse

sys.path.insert(0, str(os.environ['LSFMONITOR_INSTALL_PATH']) + '/monitor')
from common import common_sqlite3
from conf import config

# Import local config file if exists.
local_config_dir = str(os.environ['HOME']) + '/.lsfMonitor/conf'
local_config = str(local_config_dir) + '/config.py'

if os.path.exists(local_config):
    sys.path.append(local_config_dir)
    import config

os.environ['PYTHONUNBUFFERED'] = '1'


def read_args():
    """
    Read in arguments.
    """
    parser = argparse.ArgumentParser()

    parser.add_argument("-d", "--database",
                        required=True,
                        help='Required argument, specify the datebase file.')
    parser.add_argument("-t", "--tables",
                        nargs='+',
                        default=[],
                        help='Specify the tables you want to review, make sure the tables exist.')
    parser.add_argument("-k", "--keys",
                        nargs='+',
                        default=[],
                        help='Specify the table keys you want to review, make sure the table keys exist.')
    parser.add_argument("-n", "--number",
                        type=int,
                        default=0,
                        help='How many lines you want to see.')

    args = parser.parse_args()

    if not os.path.exists(args.database):
        if not re.match('^/.*$', args.database):
            database = str(config.db_path) + '/monitor/' + str(args.database)

            if os.path.exists(database):
                args.database = database
            else:
                print('*Error*: ' + str(args.database) + ': No such database file.')
                sys.exit(1)
        else:
            print('*Error*: ' + str(args.database) + ': No such database file.')
            sys.exit(1)

    return (args.database, args.tables, args.keys, args.number)


def get_length(input_list):
    """
    Get the length of the longest item on the input list.
    """
    length = 0

    for item in input_list:
        item_length = len(item)

        if item_length > length:
            length = item_length

    return (length)


def seedb(db_file, table_list, key_list, number):
    print('DB FILE : ' + str(db_file))

    if len(table_list) == 0:
        table_list = common_sqlite3.get_sql_table_list(db_file, '')

        print('TABLES :')
        print('========')

        for table in table_list:
            print(table)

        print('========')
    else:
        for table in table_list:
            print('TABLE : ' + str(table))
            print('========')

            data_dic = common_sqlite3.get_sql_table_data(db_file, '', table, key_list, number)
            key_list = list(data_dic.keys())

            if len(key_list) == 0:
                print('*Error*: No valid key_list is specified.')
            else:
                length = get_length(key_list)
                format_string = '%-' + str(length+10) + 's'

                for key in key_list:
                    print(format_string % (key), end='')

                print('')

                for key in key_list:
                    print(format_string % ('----'), end='')

                print('')

                first_key = key_list[0]
                first_value_list = data_dic[first_key]

                for i in range(len(first_value_list)):
                    for j in range(len(key_list)):
                        key = key_list[j]
                        value_list = data_dic[key]
                        value = value_list[i]

                        print(format_string % (value), end='')

                    print('')

            print('========')


################
# Main Process #
################
def main():
    (db_file, table_list, key_list, number) = read_args()
    seedb(db_file, table_list, key_list, number)


if __name__ == '__main__':
    main()
