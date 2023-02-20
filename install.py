import os
import sys
import stat
import subprocess

os.environ['PYTHONUNBUFFERED'] = '1'
CWD = os.getcwd()


def gen_wrapper_script(wrapper_script):
    """
    Generate wrapper script (shell) for python script.
    """
    print('>>> Generate wrapper script "' + str(wrapper_script) + '" ...')

    try:
        python_path = os.path.dirname(os.path.abspath(sys.executable))
        python_script = str(wrapper_script) + '.py'

        with open(wrapper_script, 'w') as TS:
            TS.write("""#!/bin/bash

# Set python3 path.
export PATH=""" + str(python_path) + """:$PATH

# Set install path.
export IFP_INSTALL_PATH=""" + str(CWD) + """

# Set LD_LIBRARY_PATH.
export LD_LIBRARY_PATH=""" + str(os.environ['LD_LIBRARY_PATH']) + """

# Execute ifp.py.
python3 $IFP_INSTALL_PATH/""" + str(python_script) + """ $@
""")

        os.chmod(wrapper_script, stat.S_IRWXU+stat.S_IRWXG+stat.S_IRWXO)
    except Exception as err:
        print('*Error*: Failed on generating top script "' + str(wrapper_script) + '": ' + str(err))
        sys.exit(1)


def gen_wrapper_scripts():
    script_list = ['bin/ifp',
                   'action/check/scripts/gen_checklist_scripts',
                   'action/check/scripts/gen_checklist_summary',
                   'action/check/scripts/ic_check',
                   'action/check/scripts/view_checklist_report']

    for wrapper_script in script_list:
        gen_wrapper_script(wrapper_script)


def gen_config_file():
    """
    Generate config file <IFP_INSTALL_PATH>/conf/config.py.
    """
    config_file = str(CWD) + '/config/config.py'

    print('')
    print('>>> Generate config file "' + str(config_file) + '".')

    if os.path.exists(config_file):
        print('*Warning*: config file "' + str(config_file) + '" already exists, will not update it.')
    else:
        try:
            with open(config_file, 'w') as CF:
                CF.write('''
# Only default_yaml_administrators can edit default.yaml on ifp GUI directory.
default_yaml_administrators = ""

# send result command
send_result_command = ""
''')

            os.chmod(config_file, stat.S_IRWXU+stat.S_IRWXG+stat.S_IRWXO)
        except Exception as error:
            print('*Error*: Failed on opening config file "' + str(config_file) + '" for write: ' + str(error))
            sys.exit(1)


def gen_top_sh_env():
    """
    Generate top environment file <IFP_INSTALL_PATH>/config/env.sh.
    """
    top_env_file = str(CWD) + '/config/env.sh'

    print('>>> Generate top sh environment file "' + str(top_env_file) + '" ...')

    try:
        with open(top_env_file, 'w') as TCF:
            TCF.write("""

#### Default EDA tool settings ####
# Set default TESSENT setting.

# Set default DC setting.

# Set default GENUS setting.

# Set default FORMALITY setting.

# Set default LEC setting.

# Set default PT setting.

# Set default TEMPUS setting.

# Set default ICC2 setting.

# Set default INNOVUS setting.

###################################

# Set lsfMonitor path.
export PATH=""" + str(CWD) + """/tools/lsfMonitor/monitor/bin:$PATH

# Set default soffice path.


""")
    except Exception as err:
        print('*Error*: Failed on generating top environment file "' + str(top_env_file) + '": ' + str(err))
        sys.exit(1)


def gen_top_csh_env():
    """
    Generate top csh environment file <IFP_INSTALL_PATH>/config/env.csh.
    """
    top_env_file = str(CWD) + '/config/env.csh'

    print('>>> Generate top csh environment file "' + str(top_env_file) + '" ...')

    try:
        with open(top_env_file, 'w') as TCF:
            TCF.write("""

#### Default EDA tool settings ####
# Set default TESSENT setting.

# Set default DC setting.

# Set default GENUS setting.

# Set default FORMALITY setting.

# Set default LEC setting.

# Set default PT setting.

# Set default TEMPUS setting.

# Set default ICC2 setting.

# Set default INNOVUS setting.

###################################

# Set lsfMonitor path.
setenv PATH """ + str(CWD) + """/tools/lsfMonitor/monitor/bin:$PATH

# Set default soffice path.


""")
    except Exception as err:
        print('*Error*: Failed on generating top envionment file "' + str(top_env_file) + '": ' + str(err))
        sys.exit(1)


def update_tools():
    """
    Update string "EXPECTED_PYTHON" and "IFP_INSTALL_PATH" on specified tools.
    """
    print('>>> Update EXPECTED_PYTHON/IFP_INSTALL_PATH settings for specified tools ...')

    expectedPython = os.path.abspath(sys.executable)
    toolList = [str(CWD) + '/action/check/scripts/gen_checklist_scripts.py',
                str(CWD) + '/action/check/scripts/gen_checklist_summary.py',
                str(CWD) + '/action/check/scripts/ic_check.py',
                str(CWD) + '/action/check/scripts/view_checklist_report.py']

    for tool in toolList:
        with open(tool, 'r+') as TOOL:
            lines = TOOL.read()
            TOOL.seek(0)
            lines = lines.replace('<EXPECTED_PYTHON>', expectedPython)
            lines = lines.replace('<IFP_INSTALL_PATH>', CWD)
            TOOL.write(lines)


def install_tools():
    print('>>> Install tool "lsfMonitor" ...')

    command = 'cd tools/lsfMonitor; ' + str(sys.executable) + ' install.py'
    SP = subprocess.Popen(command, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (stdout, stderr) = SP.communicate()
    return_code = SP.returncode

    if return_code != 0:
        print('*Error*: Failed on installing tool "lsfMonitor": ' + str(stdout, 'utf-8'))
        sys.exit(1)


################
# Main Process #
################
def main():
    gen_wrapper_scripts()
    gen_config_file()
    gen_top_sh_env()
    gen_top_csh_env()
    update_tools()
    install_tools()

    print('')
    print('Install successfully!')


if __name__ == '__main__':
    main()
