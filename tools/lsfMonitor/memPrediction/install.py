import os
import sys
import stat
import socket

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
This version of memory prediction requires Python {}.{} (or greater version),
but you're trying to install it on Python {}.{}.
""".format(*(required_python + current_python)))
        sys.exit(1)
    else:
        print('    Required python version : ' + str(required_python))
        print('    Current  python version : ' + str(current_python))


def gen_shell_tools():
    """
    Generate shell scripts under <MEM_PREDICTION_INSTALL_PATH>/tools.
    """
    tool_list = ['bin/sample', 'bin/report', 'bin/train', 'bin/predict', 'tools/update']

    for tool_name in tool_list:
        tool = str(CWD) + '/' + str(tool_name)
        ld_library_path_setting = 'export LD_LIBRARY_PATH=$MEM_PREDICTION_INSTALL_PATH/lib:'

        if 'LD_LIBRARY_PATH' in os.environ:
            ld_library_path_setting = str(ld_library_path_setting) + str(os.environ['LD_LIBRARY_PATH'])

        print('')
        print('>>> Generate script "' + str(tool) + '".')

        try:
            with open(tool, 'w') as SP:
                SP.write("""#!/bin/bash

# Set python3 path.
export PATH=""" + str(PYTHON_PATH) + """:$PATH

# Set install path.
export MEM_PREDICTION_INSTALL_PATH=""" + str(CWD) + """

# Set LD_LIBRARY_PATH.
""" + str(ld_library_path_setting) + """

# Execute """ + str(tool_name) + """.py.
python3 $MEM_PREDICTION_INSTALL_PATH/""" + str(tool_name) + '.py "$@"')

            os.chmod(tool, stat.S_IRWXU+stat.S_IRWXG+stat.S_IRWXO)
        except Exception as error:
            print('*Error*: Failed on generating script "' + str(tool) + '": ' + str(error))
            sys.exit(1)


def gen_predict_env_tools():
    """
    Generate web env scripts under <MEM_PREDICTION_INSTALL_PATH>/tools/*env.
    """
    tool = str(CWD) + '/' + 'tools/.env'
    ld_library_path_setting = 'LD_LIBRARY_PATH=$MEM_PREDICTION_INSTALL_PATH/lib:'

    if 'LD_LIBRARY_PATH' in os.environ:
        ld_library_path_setting = str(ld_library_path_setting) + str(os.environ['LD_LIBRARY_PATH'])

    print('')
    print('>>> Generate script "' + str(tool) + '".')

    try:
        with open(tool, 'w') as SP:
            SP.write("""
# Set python3 path.
PATH=""" + str(PYTHON_PATH) + """:$PATH

# Set install path.
MEM_PREDICTION_INSTALL_PATH=""" + str(CWD) + """

# Set LD_LIBRARY_PATH.
""" + str(ld_library_path_setting))

        os.chmod(tool, stat.S_IRWXU+stat.S_IRWXG+stat.S_IRWXO)
    except Exception as error:
        print('*Error*: Failed on generating script "' + str(tool) + '": ' + str(error))
        sys.exit(1)


def gen_web_service_tools():
    """
    Generate web service scripts under <MEM_PREDICTION_INSTALL_PATH>/tools/web_service.
    """
    # gen web service scripts
    web_service_tool = str(CWD) + '/' + 'tools/predict_web.service'

    print('')
    print('>>> Generate script "' + str(web_service_tool) + '".')

    try:
        with open(web_service_tool, 'w') as SP:
            SP.write("""
[Unit]
Description=LSF memory prediction web service
After=syslog.target network.target

[Service]
Type=simple
WorkingDirectory=""" + str(CWD) + '/tools' + """
EnvironmentFile=""" + str(CWD) + '/tools/.env' + ''"""
ExecStart=""" + str(PYTHON_PATH) + '/gunicorn' + """ -c predict_gconf.py predict_web:app
ExecStop=""" + str(CWD) + '/stopservice.sh' + """

Restart=on-failure

[Install]
WantedBy=multi-user.target""")

        os.chmod(web_service_tool, stat.S_IRWXU + stat.S_IRWXG + stat.S_IRWXO)
    except Exception as error:
        print('*Error*: Failed on generating script "' + str(web_service_tool) + '": ' + str(error))
        sys.exit(1)

    # generate stop service scripts
    stop_service_tool = str(CWD) + '/' + 'tools/stopservice.sh'

    print('')
    print('>>> Generate script "' + str(stop_service_tool) + '".')

    try:
        with open(stop_service_tool, 'w') as SP:
            SP.write("""#!/bin/bash

ps -elf|grep '""" + str(PYTHON_PATH) + '/gunicorn' + """ -c predict_gconf.py predict_web:app'|grep -v grep|awk '{print $4}'|xargs kill
 """)

        os.chmod(stop_service_tool, stat.S_IRWXU + stat.S_IRWXG + stat.S_IRWXO)
    except Exception as error:
        print('*Error*: Failed on generating script "' + str(stop_service_tool) + '": ' + str(error))
        sys.exit(1)


def gen_config_file():
    """
    Generate config file <MEM_PREDICTION_INSTALL_PATH>/monitor/conf/config.py.
    """
    config_file = str(CWD) + '/config/config.py'

    print('')
    print('>>> Generate config file "' + str(config_file) + '".')

    if os.path.exists(config_file):
        print('*Warning*: config file "' + str(config_file) + '" already exists, will not update it.')
    else:
        try:
            job_db_path = str(CWD) + '/db/job_db'
            report_db_path = str(CWD) + '/db/report_db'
            model_db_path = str(CWD) + '/db/model_db'
            report_template = str(CWD) + '/config/rusage_report_template.md'
            training_config = str(CWD) + '/config/training.config.yaml'
            default_predict_model = str(CWD) + '/db/model_db/latest'

            with open(config_file, 'w') as CF:
                CF.write('''# job infomation database save directory, format: csv/sqlite.
db_path = "''' + str(job_db_path) + '''"

# job rusage analysis report template
report_template = "''' + str(report_template) + '''"

# job rusage analysis report db path
report_path = "''' + str(report_db_path) + '''"

# training job memory model config yaml file
training_config_yaml = "''' + str(training_config) + '''"

# train and save model this directory
model_db_path = "''' + str(model_db_path) + '''"

# prediction model config yaml
predict_model = "''' + str(default_predict_model) + '''"

# model training max lines, default 10,000,000. if set to '0' or '', means infinity.
max_training_lines = 10000000
''')
            os.chmod(config_file, stat.S_IRWXU+stat.S_IRWXG+stat.S_IRWXO)
            os.chmod(job_db_path, stat.S_IRWXU + stat.S_IRWXG + stat.S_IRWXO)
            os.chmod(report_db_path, stat.S_IRWXU + stat.S_IRWXG + stat.S_IRWXO)
            os.chmod(model_db_path, stat.S_IRWXU + stat.S_IRWXG + stat.S_IRWXO)
        except Exception as error:
            print('*Error*: Failed on opening config file "' + str(config_file) + '" for write: ' + str(error))
            sys.exit(1)


def get_host_ip():
    """
    Get current host ip
    :return: ip
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    finally:
        s.close()

    if not ip:
        print("Could not find valid ip.")
        sys.exit(1)

    return ip


def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        _, port = s.getsockname()

    if not port:
        print("Could not find free port.")
        sys.exit(1)

    return port


def replace_key_word(ip=None, port=None):
    file_list = [
        os.path.join(str(CWD), 'tools/predict_gconf.py'),
        os.path.join(str(CWD), 'tools/esub.mem_predict')
    ]

    for file in file_list:
        print("Generate new %s ..." % str(file))

        line_list = []

        with open(file, 'r') as ff:
            for line in ff:
                line = line.replace('$IP', str(ip)).replace('$PORT', str(port))
                line_list.append(line)

        with open(file, 'w') as ff:
            ff.write(''.join(line_list))


def gen_training_scripts():
    """
    Generate training scripts under <MEM_PREDICTION_INSTALL_PATH>/tools/train.sh.
    """
    tool = str(CWD) + '/' + 'tools/train.sh'
    training_tool = os.path.join(str(CWD), 'bin/train')
    update_tool = os.path.join(str(CWD), 'tools/update')

    print('')
    print('>>> Generate script "' + str(tool) + '".')

    try:
        with open(tool, 'w') as SP:
            SP.write("""#!/bin/bash

# Training a new model
""" + str(training_tool) + """

exit_code=$?

if [ $exit_code -ne 0 ]; then
    echo "training failed."
fi

# Update config predict model after training
""" + str(update_tool) + """

exit_code=$?

if [ $exit_code -ne 0 ]; then
    echo "update failed."
fi
""")

        os.chmod(tool, stat.S_IRWXU + stat.S_IRWXG + stat.S_IRWXO)
    except Exception as error:
        print('*Error*: Failed on generating script "' + str(tool) + '": ' + str(error))
        sys.exit(1)


def gen_web_service_startup():
    """
    Generate training scripts under <MEM_PREDICTION_INSTALL_PATH>/tools/train.sh.
    """
    tool = str(CWD) + '/' + 'tools/web_startup.sh'
    service_tool = os.path.join(str(CWD), 'tools/predict_web.service')

    print('')
    print('>>> Generate script "' + str(tool) + '".')

    try:
        with open(tool, 'w') as SP:
            SP.write("""#!/bin/bash
echo "Start predict web service ..."

cp -rf """ + str(service_tool) + """ /lib/systemd/system/

echo "systemctl enable predict_web"
systemctl enable predict_web.service

echo "systemctl start predict_web"
systemctl start predict_web.service

echo "check predict web status..."
systemctl status predict_web.service

""")

        os.chmod(tool, stat.S_IRWXU + stat.S_IRWXG + stat.S_IRWXO)
    except Exception as error:
        print('*Error*: Failed on generating script "' + str(tool) + '": ' + str(error))
        sys.exit(1)


################
# Main Process #
################
def main():
    ip = get_host_ip()
    port = get_free_port()

    replace_key_word(ip=ip, port=port)
    check_python_version()
    gen_shell_tools()
    gen_predict_env_tools()
    gen_config_file()
    gen_web_service_tools()
    gen_training_scripts()
    gen_web_service_startup()

    print('')
    print('Done, Please enjoy it.')


if __name__ == '__main__':
    main()
