import datetime

from flask import Flask, request, jsonify
import threading
import time
import os
import subprocess

app = Flask(__name__)

tasks = {}


def check_job_status(job_id):
    """
    Check LSF Job Status
    """
    try:
        result = subprocess.run(['bjobs', str(job_id)], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            return f"Error: Job {job_id} not found or inaccessible."
    except Exception as e:
        return f"Error: {e}"


def parse_job_status(output):
    """
    Parsing Job status
    """
    if "DONE" in output:
        return "DONE"
    elif "EXIT" in output:
        return "EXIT"
    elif "RUN" in output or "PEND" in output:
        return "RUNNING"
    else:
        return "UNKNOWN"


def monitor_task(task_id, path, command, notification, interval, start_interval: int = 120):
    """
    Monitoring Task
    """
    time.sleep(start_interval)

    while task_id in tasks:
        # Check Job Status
        status_output = check_job_status(task_id)
        job_status = parse_job_status(status_output)
        print(f"{datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S')}[{task_id}] Job {task_id} status: {job_status}")

        # Delete Task from tasks if status == DONE|EXIT
        if job_status in {"DONE", "EXIT"}:
            print(f"{datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S')}[{task_id}] Job {task_id} is {job_status}. Removing task.")
            del tasks[task_id]
            break

        try:
            result = subprocess.run(f'cd {path} && {command}', shell=True)
            return_code = result.returncode

            if return_code:
                os.popen(notification)
                del tasks[task_id]
                break

        except Exception as e:
            print(f"Error while checking: {e}")

        time.sleep(int(interval))


@app.route('/add_task', methods=['POST'])
def add_task():
    data = request.json

    if not data or not all(key in data for key in ['id', 'path', 'command', 'interval', 'notification', 'interval']):
        return jsonify({'error': 'Invalid data. Expected {"id": <job_id>, "path": <path>, "command": <command>, "interval": <interval>, "notification": <notification>}'}), 400

    task_id = data['id']
    path = data['path']
    command = data['command']
    interval = data['interval']
    start_interval = data['start_interval']
    notification = data['notification']

    if task_id in tasks:
        return jsonify({'error': f'Task {task_id} already exists.'}), 400

    tasks[task_id] = {'command': command, 'job_id': task_id, 'notification': notification, 'interval': interval, 'start_interval': start_interval}

    thread = threading.Thread(target=monitor_task, args=(task_id, path, command, notification, interval, start_interval), daemon=True)
    thread.start()

    return jsonify({'message': f'Task {task_id} added successfully.'}), 200


@app.route('/list_tasks', methods=['GET'])
def list_tasks():
    """
    List All Task
    """
    return jsonify({'tasks': list(tasks.keys())}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=12345)
