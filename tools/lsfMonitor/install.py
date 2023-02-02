import os
import sys
import stat

CWD = os.getcwd()


def check_python_version():
    """
    Check python version.
    python3 is required, anaconda3 is better.
    """
    print('>>> Check python version.')

    current_python = sys.version_info[:2]
    required_python = (3, 5)

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


def gen_bmonitor():
    """
    Generate script <LSFMONITOR_INSTALL_PATH>/monitor/bin/bmonitor.
    """
    bmonitor = str(CWD) + '/monitor/bin/bmonitor'

    print('')
    print('>>> Generate script "' + str(bmonitor) + '".')

    try:
        with open(bmonitor, 'w') as BM:
            python_path = os.path.dirname(os.path.abspath(sys.executable))

            BM.write("""#!/bin/bash

# Set python3 path.
export PATH=""" + str(python_path) + """:$PATH

# Set lsfMonitor install path.
export LSFMONITOR_INSTALL_PATH=""" + str(CWD) + """

# Execute bmonitor.py.
python3 $LSFMONITOR_INSTALL_PATH/monitor/bin/bmonitor.py $@
""")

        os.chmod(bmonitor, stat.S_IRWXU+stat.S_IRWXG+stat.S_IRWXO)
    except Exception as err:
        print('*Error*: Failed on generating script "' + str(bmonitor) + '": ' + str(err))
        sys.exit(1)


def gen_bsample():
    """
    Generate script <LSFMONITOR_INSTALL_PATH>/monitor/bin/bsample.
    """
    bsample = str(CWD) + '/monitor/bin/bsample'

    print('')
    print('>>> Generate script "' + str(bsample) + '".')

    try:
        with open(bsample, 'w') as BS:
            python_path = os.path.dirname(os.path.abspath(sys.executable))

            BS.write("""#!/bin/bash

# Set python3 path.
export PATH=""" + str(python_path) + """:$PATH

# Set lsfMonitor install path.
export LSFMONITOR_INSTALL_PATH=""" + str(CWD) + """

# Execute bsample.py.
python3 $LSFMONITOR_INSTALL_PATH/monitor/bin/bsample.py $@
""")

        os.chmod(bsample, stat.S_IRWXU+stat.S_IRWXG+stat.S_IRWXO)
    except Exception as err:
        print('*Error*: Failed on generating script "' + str(bsample) + '": ' + str(err))
        sys.exit(1)


def gen_config_file():
    """
    Generate config file <LSFMONITOR_INSTALL_PATH>/monitor/conf/config.py.
    """
    config_file = str(CWD) + '/monitor/conf/config.py'

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

# Specify lmstat path, example "/*/*/bin".
lmstat_path = ""

# Specify lmstat bsub command, example "bsub -q normal -Is".
lmstat_bsub_command = ""
''')

            os.chmod(config_file, stat.S_IRWXU+stat.S_IRWXG+stat.S_IRWXO)
            os.chmod(db_path, stat.S_IRWXU+stat.S_IRWXG+stat.S_IRWXO)
        except Exception as error:
            print('*Error*: Failed on opening config file "' + str(config_file) + '" for write: ' + str(error))
            sys.exit(1)


def update_tools():
    """
    Update string "LSFMONITOR_INSTALL_PATH_STRING" into environment variable LSFMONITOR_INSTALL_PATH.
    """
    expected_python = os.path.abspath(sys.executable)
    tool_list = [str(CWD) + '/monitor/tools/check_issue_reason.py', str(CWD) + '/monitor/tools/message.py', str(CWD) + '/monitor/tools/seedb.py', str(CWD) + '/monitor/tools/process_tracer.py', str(CWD) + '/monitor/tools/show_license_feature_usage.py']

    for tool in tool_list:
        with open(tool, 'r+') as TOOL:
            lines = TOOL.read()
            TOOL.seek(0)
            lines = lines.replace('EXPECTED_PYTHON', expected_python)
            lines = lines.replace('LSFMONITOR_INSTALL_PATH_STRING', CWD)
            TOOL.write(lines)


################
# Main Process #
################
def main():
    check_python_version()
    gen_bmonitor()
    gen_bsample()
    gen_config_file()
    update_tools()

    print('')
    print('Done, Please enjoy it.')


if __name__ == '__main__':
    main()
