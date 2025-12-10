import json
import sys
import threading
import time
import os
import traceback
import psutil
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine


os.environ['PYTHONUNBUFFERED'] = '1'
sys.path.append(str(os.environ['IFP_INSTALL_PATH']))
sys.path.append(str(os.environ['IFP_INSTALL_PATH']) + '/common')
import common
import common_db


log_file = os.environ.get('IFP_LOG_FILE', None)

common.init_logger(log_path=log_file, console_log=False)
logger = common.get_logger()


class JobWatcher:
    def __init__(self, session_factory, interval=5):
        self.session_factory = session_factory
        self.interval = interval
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self.watch_loop, daemon=True)
        self.log_dir = os.path.join(os.path.dirname(log_file), 'job_logs')

    def start(self):
        if self.thread and self.thread.is_alive():
            logger.warning("[Watcher] Already running.")
            return

        logger.info('[Watcher] Starting job watcher...')

        self.stop_event.clear()
        self.thread = threading.Thread(target=self.watch_loop, daemon=True)
        self.thread.start()

    def run_forever(self):
        self.start()

        try:
            while self.thread.is_alive():
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        logger.info('[Watcher] Stopping job watcher...')
        self.stop_event.set()

        if self.thread:
            self.thread.join()
            logger.info('[Watcher] Job watcher stopped.')
        else:
            logger.info('[Watcher] No active thread to stop.')

    def watch_loop(self):
        while not self.stop_event.is_set():
            try:
                self.watch_once()
            except Exception as e:
                logger.warning(f'[Watcher] Exception during watching: {str(e)}')
            time.sleep(self.interval)

    def watch_once(self):
        session = self.session_factory()
        jobs = session.query(common_db.JobStore).filter(common_db.JobStore.status.in_([common_db.JobStatus.queued, common_db.JobStatus.running, common_db.JobStatus.undefined])).all()

        lsf_jobs = [job for job in jobs if job.job_type == common_db.JobType.lsf]
        local_jobs = [job for job in jobs if job.job_type == common_db.JobType.local]

        lsf_status_map = self.batch_get_lsf_job_status([str(job.job_id) for job in lsf_jobs])
        local_status_map = self.batch_get_local_job_status([int(job.job_id) for job in local_jobs])

        for job in jobs:
            try:
                if job.job_type == common_db.JobType.lsf:
                    status = lsf_status_map.get(str(job.job_id), common_db.JobStatus.undefined.value)
                elif job.job_type == common_db.JobType.local:
                    status = local_status_map.get(str(job.job_id), common_db.JobStatus.undefined.value)

                    if status == common_db.JobStatus.passed.value:
                        log_json = os.path.join(self.log_dir, f'{job.block}_{job.version}_{job.task}_{job.action.value}.job.json')

                        if os.path.exists(log_json):
                            with open(log_json) as f:
                                try:
                                    result = json.load(f)
                                    if result.get("return_code", 0) != 0:
                                        status = common_db.JobStatus.failed.value
                                except Exception as e:
                                    logger.warning(f"Failed to parse job log {log_json}: {e}")

                else:
                    status = None

                if status and status != job.status:
                    job.status = status

            except Exception as e:
                logger.error(f'[Watcher] Error watching job {job.uuid}: {str(e)}')

        session.commit()
        session.close()

    def handle_completed_job(self, job):
        pass

    @staticmethod
    def batch_get_lsf_job_status(job_ids):
        status_map = {}

        if not job_ids:
            return status_map

        job_id_str = ' '.join(job_ids)

        try:
            output = os.popen(f'bjobs {job_id_str}').read()

            for line in output.strip().split('\n'):
                if line.startswith('JOBID'):
                    continue  # Skip header

                parts = line.strip().split()
                if len(parts) < 3:
                    continue  # Skip invalid lines

                job_id = parts[0]
                job_status = parts[2]

                if job_status == 'RUN':
                    status_map[job_id] = common_db.JobStatus.running.value
                elif job_status == 'DONE':
                    status_map[job_id] = common_db.JobStatus.passed.value
                elif job_status == 'EXIT':
                    status_map[job_id] = common_db.JobStatus.failed.value
                elif job_status == 'PEND' or job_status == 'QUEUE':
                    status_map[job_id] = common_db.JobStatus.queued.value
                else:
                    continue
                    # status_map[job_id] = common_db.JobStatus.undefined.value

        except Exception as e:
            print(e)
            print(traceback.format_exc())
            logger.info(f'[Watcher] Batch LSF query exception: {str(e)}')

        return status_map

    @staticmethod
    def batch_get_local_job_status(pids):
        status_map = {str(pid): common_db.JobStatus.passed.value for pid in pids}  # Default: assume finished

        try:
            all_processes = {proc.pid: proc for proc in psutil.process_iter(['pid', 'status'])}

            for pid in pids:
                proc = all_processes.get(pid)
                if proc:
                    if proc.status() == psutil.STATUS_ZOMBIE:
                        os.waitpid(pid, 0)
                    else:
                        status_map[str(pid)] = common_db.JobStatus.running.value

        except Exception as e:
            logger.error(f'[Watcher] Batch local query exception: {str(e)}')

        return status_map


def main():
    try:
        config_file, read, _, _, _ = common.readArgs()

        if read:
            return

        data_dir = os.path.join(os.path.dirname(config_file), common.gen_cache_file_name(config_file=os.path.basename(config_file))[-1])
        db_path = f'sqlite:///{os.path.join(data_dir, common_db.JobStoreTable)}'
        Session = sessionmaker(bind=create_engine(db_path, connect_args={'check_same_thread': False}))
        watcher = JobWatcher(Session, interval=5)
        watcher.run_forever()

    except Exception as error:
        logger.error(traceback.format_exc())
        logger.error(f'*Error*: {str(error)}.')


if __name__ == '__main__':
    main()
