import os
import sys
import stat

CWD = os.getcwd()
PYTHON_PATH = os.path.dirname(os.path.abspath(sys.executable))


def check_python_version():
    """
    Check python version.
    python3 is required, anaconda3 is better.
    """
    print('>>> Check python version.')

    current_python = sys.version_info[:2]
    required_python = (3, 8)

    if current_python < required_python:
        sys.stderr.write("""
==========================
Unsupported Python version
==========================
This version of lsfMonitor requires Python {}.{} (or greater version),
but you're trying to install it on Python {}.{}.
""".format(*(required_python + current_python)))
        sys.exit(1)
    else:
        print('    Required python version : ' + str(required_python))
        print('    Current  python version : ' + str(current_python))
        print('')


def gen_shell_tools():
    """
    Generate shell scripts under <LSFMONITOR_INSTALL_PATH>/tools.
    """
    tool_list = ['monitor/bin/bmonitor', 'monitor/bin/bsample', 'monitor/tools/akill', 'monitor/tools/check_issue_reason', 'monitor/tools/patch', 'monitor/tools/process_tracer', 'monitor/tools/seedb', 'monitor/tools/show_license_feature_usage']

    for tool_name in tool_list:
        tool = str(CWD) + '/' + str(tool_name)
        ld_library_path_setting = 'export LD_LIBRARY_PATH=$LSFMONITOR_INSTALL_PATH/lib:'

        if 'LD_LIBRARY_PATH' in os.environ:
            ld_library_path_setting = str(ld_library_path_setting) + str(os.environ['LD_LIBRARY_PATH'])

        print('>>> Generate script "' + str(tool) + '".')

        try:
            with open(tool, 'w') as SP:
                SP.write("""#!/bin/bash

# Set python3 path.
export PATH=""" + str(PYTHON_PATH) + """:$PATH

# Set install path.
export LSFMONITOR_INSTALL_PATH=""" + str(CWD) + """

# Set LD_LIBRARY_PATH.
""" + str(ld_library_path_setting) + """

# Execute """ + str(tool_name) + """.py.
python3 $LSFMONITOR_INSTALL_PATH/""" + str(tool_name) + '.py "$@"')

            os.chmod(tool, stat.S_IRWXU+stat.S_IRWXG+stat.S_IRWXO)
        except Exception as error:
            print('*Error*: Failed on generating script "' + str(tool) + '": ' + str(error))
            sys.exit(1)


def gen_config_file():
    """
    Generate config file <LSFMONITOR_INSTALL_PATH>/monitor/conf/config.py.
    """
    config_file = str(CWD) + '/monitor/conf/config.py'
    lmstat_path = str(CWD) + '/monitor/tools/lmstat'

    print('')
    print('>>> Generate config file "' + str(config_file) + '".')

    if os.path.exists(config_file):
        print('*Warning*: config file "' + str(config_file) + '" already exists, will not update it.')
    else:
        try:
            db_path = str(CWD) + '/db'

            with open(config_file, 'w') as CF:
                CF.write('''# Specify the database directory.
db_path = "''' + str(db_path) + '''"

# Specify lmstat path, example "/eda/synopsys/scl/2021.03/linux64/bin/lmstat".
lmstat_path = "''' + str(lmstat_path) + '''"

# Specify lmstat bsub command, example "bsub -q normal -Is".
lmstat_bsub_command = ""
''')

            os.chmod(config_file, stat.S_IRWXU+stat.S_IRWXG+stat.S_IRWXO)
            os.chmod(db_path, stat.S_IRWXU+stat.S_IRWXG+stat.S_IRWXO)
        except Exception as error:
            print('*Error*: Failed on opening config file "' + str(config_file) + '" for write: ' + str(error))
            sys.exit(1)


################
# Main Process #
################
def main():
    check_python_version()
    gen_shell_tools()
    gen_config_file()

    print('')
    print('Done, Please enjoy it.')


if __name__ == '__main__':
    main()
