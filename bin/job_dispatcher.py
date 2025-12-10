import datetime
import os
import re
import shlex
import sys
import threading
import time
import subprocess
import traceback
from concurrent.futures import ThreadPoolExecutor
import getpass
from typing import Union

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ['PYTHONUNBUFFERED'] = '1'
sys.path.append(str(os.environ['IFP_INSTALL_PATH']))
from config import config

sys.path.append(str(os.environ['IFP_INSTALL_PATH']) + '/common')
import common
import common_db
import common_prediction

log_file = os.environ.get('IFP_LOG_FILE', None)

common.init_logger(log_path=log_file, console_log=False)
logger = common.get_logger()

_dispatch_lock = threading.Lock()


def _drain(stream):
    for _ in stream:
        pass


class JobDispatcher:
    dispatch_lock = threading.Lock()

    def __init__(self, session_factory, interval=1, max_workers=10):
        # Initialize dispatcher with thread pool and polling interval
        self.session_factory = session_factory
        self.interval = interval
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self.dispatch_loop, daemon=True)
        # self.dispatch_lock = threading.Lock()
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.predict = True if hasattr(config, 'mem_prediction') and config.mem_prediction else False
        self.predictor = LSFPrediction()
        self.log_dir = os.path.join(os.path.dirname(log_file), 'job_logs')
        os.makedirs(self.log_dir, exist_ok=True)

    def start(self):
        """
        Start the dispatcher loop (non-blocking).
        """
        if self.thread and self.thread.is_alive():
            logger.warning('[Dispatcher] Already running.')
            return

        logger.info('[Dispatcher] Starting job dispatcher... Cleaning old jobs.')
        self.clean_obsolete_jobs()
        logger.info('[Dispatcher] Cleanup completed. Starting dispatch loop.')

        self.stop_event.clear()
        self.thread = threading.Thread(target=self.dispatch_loop, daemon=True)
        self.thread.start()

    def run_forever(self):
        """
        Start the dispatcher loop and block the main process.
        """
        self.start()
        try:
            while self.thread.is_alive():
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        """
        Gracefully stop the dispatcher and thread pool.
        """
        logger.info('[Dispatcher] Stopping job dispatcher...')
        self.stop_event.set()

        if self.thread and self.thread.is_alive():
            self.thread.join()

        self.executor.shutdown(wait=True)
        logger.info('[Dispatcher] Dispatcher stopped.')

    def clean_obsolete_jobs(self):
        """
        Delete all jobs where status is not 'running'.
        """
        session = self.session_factory()
        jobs_to_delete = session.query(common_db.JobStore).filter(common_db.JobStore.status != common_db.JobStatus.running).all()
        deleted = len(jobs_to_delete)
        for job in jobs_to_delete:
            session.delete(job)
        session.commit()
        session.close()
        logger.info(f'[Dispatcher] Cleaned {deleted} obsolete jobs.')

    def dispatch_loop(self):
        """
        Main dispatcher loop with periodic database polling.
        """
        while not self.stop_event.is_set():
            try:
                with _dispatch_lock:
                    self.dispatch_once()
            except Exception as e:
                logger.error(f'[Dispatcher] Exception during dispatch: {str(e)}')
            time.sleep(self.interval)

    def dispatch_once(self):
        """
        Fetch all jobs waiting for dispatch and submit them asynchronously.
        """
        """
        """
        session = self.session_factory()
        try:
            jobs = session.query(common_db.JobStore).filter(
                common_db.JobStore.status == common_db.JobStatus.awaiting_dispatch
            ).all()

            for job in jobs:
                job.status = common_db.JobStatus.dispatching
                logger.info(f'[Dispatcher] Locking job {job.uuid} for dispatch.')

            session.commit()
            job_data = [job.to_dict() for job in jobs]

        finally:
            session.close()

        for job in job_data:
            self.executor.submit(self.submit_job, job)

    def submit_job(self, job):
        """
        Submit a single job asynchronously.
        """
        session = self.session_factory()
        uuid = job['uuid']

        try:
            job_in_db = session.query(common_db.JobStore).filter_by(uuid=uuid).first()

            if job_in_db is None:
                logger.info('[Dispatcher] {} -> {} -> {} -> {} is not in database.'.format(job['block'], job['version'], job['flow'], job['task']))
            else:
                if job['job_type'] == common_db.JobType.lsf.value:
                    logger.info('[Dispatcher] Submitting LSF job: {}'.format(job['command_file']))
                    lsf_job_id = self.submit_lsf_job(job)

                    if lsf_job_id:
                        job_in_db.job_id = lsf_job_id
                        job_in_db.status = common_db.JobStatus.dispatched
                        job_info = '{}/{}/{}/{}'.format(job['block'], job['version'], job['flow'], job['task'])
                        logger.info(f'[Dispatcher] LSF job {uuid}({job_info}) submitted successfully. LSF Job ID: {lsf_job_id}')
                    else:
                        job_in_db = session.query(common_db.JobStore).filter_by(uuid=uuid).first()
                        job_in_db.status = common_db.JobStatus.dispatched
                        logger.info('[Dispatcher] Failed to submit LSF job {}'.format(job['uuid']))

                elif job['job_type'] == common_db.JobType.local.value:
                    logger.info('[Dispatcher] Submitting local job: {}'.format(job['command_file']))
                    env = os.environ.copy()
                    env.update({
                        "UUID": uuid,
                        "USER_COMMAND": job['command_file'],
                        "IFP_LOG_FILE": self.log_dir,
                        "BLOCK": job['block'],
                        "VERSION": job['version'],
                        "TASK": job['task'],
                        'ACTION': job['action'],
                    })
                    command = '{}'.format(os.path.join(os.environ['IFP_INSTALL_PATH'], 'tools/local.sh'))
                    process = common.spawn_process_with_env(command, shell=True, env=env)
                    job_in_db.job_id = process.pid
                    job_in_db.status = common_db.JobStatus.dispatched
                    logger.info(f'[Dispatcher] Local job [{uuid} submitted successfully. PID: {process.pid}')

                session.commit()

        except Exception as e:
            logger.info(f'[Dispatcher] Exception while submitting job {uuid}: {str(e)}')
            logger.info(f'[Dispatcher] Traceback: {traceback.format_exc()}')

        finally:
            session.close()

    def submit_lsf_job(self, job) -> Union[int, None]:
        """
        Submit LSF job quickly and parse Job ID.
        """
        try:
            # if self.predict:
            #     self.predictor.predict(command_file=command) "${LOG_DIR}/${BLOCK}_${VERSION}_${TASK}_${ACTION}.stdout.log"

            stdout_file = os.path.join(self.log_dir, '{}_{}_{}_{}.stdout.log'.format(job['block'], job['version'], job['task'], job['action']))
            stderr_file = os.path.join(self.log_dir, '{}_{}_{}_{}.stderr.log'.format(job['block'], job['version'], job['task'], job['action']))

            bash_script = '"/bin/bash" "$0" ' \
                          '> >(tee "$1") ' \
                          '2> >(tee "$2" >&2)'

            process = subprocess.Popen(
                ["/bin/bash", "-c", bash_script, job["command_file"], stdout_file, stderr_file],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )

            first_line = process.stdout.readline()

            t1 = threading.Thread(target=_drain, args=(process.stdout,), daemon=True)
            t2 = threading.Thread(target=_drain, args=(process.stderr,), daemon=True)
            t1.start(); t2.start()  # noqa: E702

            if match := common.get_jobid(first_line):
                return int(match)
            else:
                logger.info(f'[Dispatcher] Failed to extract LSF Job ID. Output: {first_line.strip()}')

        except subprocess.TimeoutExpired:
            logger.error('[Dispatcher] LSF submission timeout: {}'.format('command_file'))
            process.kill()
        except Exception as e:
            logger.error(f'[Dispatcher] LSF submission exception: {str(e)}')

        return None


class LSFPrediction:
    def __init__(self):
        self.predict_model = common_prediction.PredictionModel() if self.predict else None

    def predict(self, command_file: str):
        try:
            command = self.read_command(command_file=command_file)
            job_info = self.get_job_info(command=command)
            new_command = self.predict_model.predict_job(job_info=job_info, command=command)
            self.rewrite_command_file(command_file=command_file, new_command=new_command)
        except Exception as error:
            logger.error(f'[Dispatcher] LSF Memory Prediction Failed: {str(error)}')
            logger.debug(f'[Dispatcher] Traceback: {traceback.format_exc()}')

    @staticmethod
    def rewrite_command_file(command_file: str, new_command: str):
        with open(command_file, 'r') as f:
            lines = f.readlines()

        last_line = lines[-1].rstrip('\n')

        match = re.search(r'\bbsub\b.*', last_line)
        old_bsub_command = match.group().strip()
        new_line = last_line.replace(old_bsub_command, new_command)
        lines[-1] = new_line + '\n'

        with open(command_file, 'w') as f:
            f.writelines(lines)

    @staticmethod
    def get_job_info(command: str):
        predict_job_info = {
            'job_name': '',
            'project': 'IFP',
            'user': getpass.getuser(),
            'queue': '',
            'cwd': os.getcwd(),
            'command': command,
            'started_time': datetime.datetime.now().strftime('%a %b %d %H:%M:%S'),
            'res_req': ''
        }

        run_info_list = shlex.split(command)

        for i, item in enumerate(run_info_list):
            if item == '-q' and not predict_job_info['queue']:
                predict_job_info['queue'] = run_info_list[i + 1]
            elif item == '-J' and not predict_job_info['job_name']:
                predict_job_info['job_name'] = run_info_list[i + 1]
            elif item == '-R' and not predict_job_info['res_req']:
                predict_job_info['res_req'] = run_info_list[i + 1]

        return predict_job_info

    @staticmethod
    def read_command(command_file: str):
        with open(command_file, 'rb') as f:
            f.seek(0, 2)
            file_size = f.tell()
            block_size = 1024
            data = b''
            pos = file_size

            while pos > 0:
                read_size = min(block_size, pos)
                pos -= read_size
                f.seek(pos)
                data = f.read(read_size) + data
                if b'\n' in data:
                    break

            lines = data.split(b'\n')
            last_line = lines[-1] if lines[-1].strip() else lines[-2]
            last_line = last_line.decode('utf-8').strip()

            match = re.search(r'\bbsub\b.*', last_line)
            if match:
                bsub_command = match.group().strip()
                return bsub_command
            else:
                raise RuntimeError


def main():
    try:
        config_file, read, _, _, _ = common.readArgs()

        if read:
            return

        data_dir = os.path.join(os.path.dirname(config_file), common.gen_cache_file_name(config_file=os.path.basename(config_file))[-1])
        db_path = f'sqlite:///{os.path.join(data_dir, common_db.JobStoreTable)}'
        Session = sessionmaker(bind=create_engine(db_path, connect_args={'check_same_thread': False}))
        dispatcher = JobDispatcher(Session, interval=1, max_workers=10)
        dispatcher.run_forever()

    except Exception as error:
        logger.error(traceback.format_exc())
        logger.error(f'*Error*: {str(error)}.')


if __name__ == '__main__':
    main()
