import os
import re
import sys
import sqlite3

sys.path.append(str(os.environ['LSFMONITOR_INSTALL_PATH']) + '/monitor')
from common import common


def connect_db_file(db_file, mode='read'):
    result = 'passed'
    conn = ''

    if mode == 'write':
        journal_db_file = str(db_file) + '-journal'

        if os.path.exists(journal_db_file) and (mode == 'write'):
            common.print_warning('*Warning*: database file "' + str(db_file) + '" is on another connection, will not connect it.')
            result = 'locked'
            return(result, conn)
    elif mode == 'read':
        if not os.path.exists(db_file):
            common.print_error('*Error*: "' + str(db_file) + '" No such database file.')
            result = 'failed'
            return(result, conn)

    try:
        conn = sqlite3.connect(db_file)
    except Exception as error:
        common.print_error('*Error*: Failed on connecting database file "' + str(db_file) + '": ' + str(error))
        result = 'failed'

    return(result, conn)


def connect_preprocess(db_file, orig_conn, mode='read'):
    if orig_conn == '':
        (result, conn) = connect_db_file(db_file, mode)
    else:
        result = 'passed'
        conn = orig_conn

    curs = conn.cursor()

    return(result, conn, curs)


def get_sql_table_list(db_file, orig_conn):
    """
    Get all of the tables from the specified db file.
    """
    table_list = []
    (result, conn, curs) = connect_preprocess(db_file, orig_conn)

    if result == 'failed':
        return(table_list)

    try:
        command = "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        results = curs.execute(command)
        all_items = results.fetchall()

        for item in all_items:
            (key,) = item
            table_list.append(key)

        curs.close()

        if orig_conn == '':
            conn.close()
    except Exception as error:
        common.print_error('*Error* (get_sql_table_list) : Failed on getting table list on db_file "' + str(db_file) + '": ' + str(error))

    return(table_list)


def get_sql_table_count(db_file, orig_conn, table_name):
    """
    How many lines of the database table.
    """
    count = 'N/A'

    (result, conn, curs) = connect_preprocess(db_file, orig_conn)

    if result == 'failed':
        return(count)

    try:
        command = "SELECT count(*) FROM '" + str(table_name) + "'"
        curs.execute(command)
        return_list = curs.fetchall()
        return_tuple = return_list[0]
        count = return_tuple[0]
        curs.close()

        if orig_conn == '':
            conn.close()
    except Exception as error:
        common.print_error('*Error* (get_sql_table_count) : Failed on getting table count fro table "' + str(table_name) + '" on db_file "' + str(db_file) + '": ' + str(error))

    return(count)


def get_sql_table_key_list(db_file, orig_conn, table_name):
    """
    Get all of the tables from the specified db file.
    """
    key_list = []

    (result, conn, curs) = connect_preprocess(db_file, orig_conn)

    if result == 'failed':
        return(key_list)

    try:
        command = "SELECT * FROM '" + str(table_name) + "'"
        curs.execute(command)
        key_list = [tuple[0] for tuple in curs.description]
        curs.close()

        if orig_conn == '':
            conn.close()
    except Exception as error:
        common.print_error('*Error* (get_sql_table_key_list) : Failed on getting table key list on db_file "' + str(db_file) + '": ' + str(error))

    return(key_list)


def get_sql_table_data(db_file, orig_conn, table_name, key_list=[], limit=0):
    """
    With specified db_file-table_name, get all data from specified key_list.
    """
    data_dic = {}
    (result, conn, curs) = connect_preprocess(db_file, orig_conn)

    if result == 'failed':
        return(data_dic)

    try:
        command = "SELECT * FROM '" + str(table_name) + "'"

        if limit != 0:
            command = str(command) + ' limit ' + str(limit)

        results = curs.execute(command)
        all_items = results.fetchall()
        table_key_list = [tuple[0] for tuple in curs.description]
        curs.close()

        if orig_conn == '':
            conn.close()

        if len(key_list) == 0:
            key_list = table_key_list
        else:
            for key in key_list:
                if key not in table_key_list:
                    common.print_error('*Error* (get_sql_table_data) : "' + str(key) + '": invalid key on specified key list.')
                    return(data_dic)

        for item in all_items:
            value_list = list(item)

            for i in range(len(table_key_list)):
                key = table_key_list[i]

                if key in key_list:
                    value = value_list[i]

                    if key in data_dic.keys():
                        data_dic[key].append(value)
                    else:
                        data_dic[key] = [value, ]
    except Exception as error:
        common.print_error('*Error* (get_sql_table_data) : Failed on getting table info from table "' + str(table_name) + '" of db_file "' + str(db_file) + '": ' + str(error))

    return(data_dic)


def delete_sql_table_rows(db_file, orig_conn, table_name, row_id, begin_line, end_line, commit=True):
    """
    Delete specified table rows (from begin_line to end_line).
    """
    (result, conn, curs) = connect_preprocess(db_file, orig_conn, mode='write')

    if (result == 'failed') or (result == 'locked'):
        return

    try:
        command = "DELETE FROM '" + str(table_name) + "' WHERE " + str(row_id) + " IN (SELECT " + str(row_id) + " FROM '" + str(table_name) + "' ORDER BY " + str(row_id) + " LIMIT " + str(begin_line) + "," + str(end_line) + ")"
        curs.execute(command)
        curs.close()

        if commit:
            conn.commit()

            if orig_conn == '':
                conn.close()
    except Exception as error:
        common.print_error('*Error* (drop_sql_table) : Failed on deleting table "' + str(table_name) + '" lines ' + str(begin_line) + '-' + str(end_line) + ': ' + str(error))


def drop_sql_table(db_file, orig_conn, table_name, commit=True):
    """
    Drop table if it exists.
    """
    (result, conn, curs) = connect_preprocess(db_file, orig_conn, mode='write')

    if (result == 'failed') or (result == 'locked'):
        return

    try:
        command = "DROP TABLE IF EXISTS '" + str(table_name) + "'"
        curs.execute(command)
        curs.close()

        if commit:
            conn.commit()

            if orig_conn == '':
                conn.close()
    except Exception as error:
        common.print_error('*Error* (drop_sql_table) : Failed on drop table "' + str(table_name) + '" from db_file "' + str(db_file) + '": ' + str(error))


def create_sql_table(db_file, orig_conn, table_name, init_string, commit=True):
    """
    Create a table if it not exists, initialization the setting.
    """
    (result, conn, curs) = connect_preprocess(db_file, orig_conn, mode='write')

    if (result == 'failed') or (result == 'locked'):
        return

    try:
        command = "CREATE TABLE IF NOT EXISTS '" + str(table_name) + "' " + str(init_string)
        curs.execute(command)
        curs.close()

        if commit:
            conn.commit()

            if orig_conn == '':
                conn.close()
    except Exception as error:
        common.print_error('*Error* (create_sql_table) : Failed on creating table "' + str(table_name) + '" on db file "' + str(db_file) + '": ' + str(error))


def insert_into_sql_table(db_file, orig_conn, table_name, value_string, commit=True):
    """
    Insert new value into sql table.
    """
    (result, conn, curs) = connect_preprocess(db_file, orig_conn, mode='write')

    if (result == 'failed') or (result == 'locked'):
        return

    try:
        command = "INSERT INTO '" + str(table_name) + "' VALUES " + str(value_string)
        curs.execute(command)
        curs.close()

        if commit:
            conn.commit()

            if orig_conn == '':
                conn.close()
    except Exception as error:
        common.print_error('*Error* (insert_into_sql_table) : Failed on inserting specified values into table "' + str(table_name) + '" on db file "' + str(db_file) + '": ' + str(error))


def gen_sql_table_key_string(key_list, key_type_list=[], auto_increment=False):
    """
    Switch the input key_list into the sqlite table key string.
    """
    key_string = '('

    for i in range(len(key_list)):
        key = key_list[i]

        if len(key_type_list) == len(key_list):
            key_type = key_type_list[i]
        else:
            key_type = 'VARCHAR(255)'

        if i == 0:
            if auto_increment:
                key_string = str(key_string) + "id INTEGER PRIMARY KEY AUTOINCREMENT, '" + str(key) + "' " + str(key_type) + ","
            else:
                key_string = str(key_string) + "'" + str(key) + "' " + str(key_type) + " PRIMARY KEY,"
        elif i == len(key_list)-1:
            key_string = str(key_string) + " '" + str(key) + "' " + str(key_type) + ");"
        else:
            key_string = str(key_string) + " '" + str(key) + "' " + str(key_type) + ","

    return(key_string)


def gen_sql_table_value_string(value_list, auto_increment=False):
    """
    Switch the input value_list into the sqlite table value string.
    """
    value_string = '('

    for i in range(len(value_list)):
        value = value_list[i]

        if re.search("'", str(value)):
            value = str(value).replace("'", "''")

        if i == 0:
            if auto_increment:
                value_string = str(value_string) + "NULL, '" + str(value) + "',"
            else:
                value_string = str(value_string) + "'" + str(value) + "',"
        elif i == len(value_list)-1:
            value_string = str(value_string) + " '" + str(value) + "');"
        else:
            value_string = str(value_string) + " '" + str(value) + "',"

    return(value_string)
