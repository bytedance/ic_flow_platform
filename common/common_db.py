import datetime
import os
import re
import sys
import time
import uuid
from hashlib import sha1
from typing import Tuple, Dict, Union, List

from dateutil import parser
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker, declarative_base

sys.path.append(str(os.environ['IFP_INSTALL_PATH']) + 'config/')
import config

sys.path.append(str(os.environ['IFP_INSTALL_PATH']) + 'common/')
import common_lsf

Base = declarative_base()


class SqlDB:
    """
    Sqlite database simple command

    Attributes:
        self.create_table: create table.
        self.add(model): add data.
        self.update(model, model_id): update data.
        self.delete(model, model_id): delete data.
        self.get_all(): get all data.
    """
    def __init__(self, db_url):
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def create_table(self):
        Base.metadata.create_all(self.engine)

    def add(self, model):
        session = self.Session()
        try:
            session.add(model)
            session.commit()
        except OperationalError as e:
            session.rollback()

            if 'no such table' in str(e):
                self.create_table()
                session.add(model)
                session.commit()
            else:
                raise e
        finally:
            session.close()

    def update(self, model, model_id, **kwargs):
        session = self.Session()
        model = session.query(model).filter(model.id == model_id).first()

        if model:
            for key, value in kwargs.items():
                setattr(model, key, value)
            session.commit()
        session.close()

    def delete(self, model_class, model_id):
        session = self.Session()
        model = session.query(model_class).filter(model_class.id == model_id).first()

        if model:
            session.delete(model)
            session.commit()
        session.close()

    def get_all(self, model_class):
        session = self.Session()
        result = session.query(model_class).all()
        session.close()
        return result


class JobTemplate(Base):
    __abstract__ = True
    id = Column(String, primary_key=True)
    job_id = Column(Integer)
    job_name = Column(String)
    user = Column(String)
    command = Column(String)
    cwd = Column(String)
    project = Column(String)
    queue = Column(String)
    block = Column(String)
    version = Column(String)
    flow = Column(String)
    task = Column(String)
    rusage_mem = Column(Integer)  # Unit: MB
    max_mem = Column(Integer)  # Unit: MB
    start_time = Column(Integer)  # Timestamp


class IFPRecord(Base):
    __tablename__ = 'ifp_records'
    uuid = Column(String, primary_key=True)
    block = Column(String)
    version = Column(String)
    group = Column(String)
    project = Column(String)
    user = Column(String)
    file_path = Column(String)


class TaskJobs(Base):
    __tablename__ = 'task_jobs'
    uuid = Column(String, primary_key=True)
    job_id = Column(String)
    block = Column(String)
    version = Column(String)
    flow = Column(String)
    task = Column(String)
    status = Column(String)
    exit_code = Column(Integer)
    submitted_time = Column(String)
    finished_time = Column(String)
    cwd = Column(String)
    command = Column(String)
    command_file = Column(String)


def create_weekly_job_table(year: int, week_number: int):
    table_name = f'job_{str(year)}_{str(week_number)}'.lower()
    class_name = f'Job_{str(year)}_{str(week_number)}'

    if class_name in globals():
        return globals()[class_name]

    new_class = type(class_name, (JobTemplate,), {
        '__tablename__': table_name,
        '__module__': __name__
    })

    globals()[class_name] = new_class
    return new_class


def analysis_and_save_job(job_id: str, block: str, version: str, flow: str, task: str):
    time.sleep(10)

    if my_match := re.match(r'^b:(\d+)$', job_id):
        lsf_job_id = int(my_match.group(1))

        try:
            job_data, year, week_number = analysis_db(job_id=lsf_job_id, block=block, version=version, flow=flow, task=task)
            save_job(job_data=job_data, year=year, week_number=week_number)
        except Exception:
            return


def analysis_db(job_id: int, block: str, version: str, flow: str, task: str) -> Tuple[Dict[str, Union[str, int]], int, int]:
    job_origin_data = common_lsf.get_lsf_bjobs_uf_info('bjobs {} -UF'.format(str(job_id))).get(str(job_id), {})
    job_data = {}

    if not job_origin_data or job_origin_data['status'] != 'DONE':
        raise RuntimeError

    job_data['job_id'] = int(job_origin_data['job_id'])
    job_data['job_name'] = job_origin_data['job_name'] if job_origin_data['job_name'] else 'default'
    job_data['user'] = job_origin_data['user']
    job_data['command'] = job_origin_data['command']
    job_data['project'] = job_origin_data['project']
    job_data['queue'] = job_origin_data['queue']
    job_data['cwd'] = job_origin_data['cwd']
    job_data['start_time'] = int(parser.parse(job_origin_data['started_time']).timestamp())
    job_data['max_mem'] = int(job_origin_data['max_mem'])
    job_data['rusage_mem'] = int(job_origin_data['rusage_mem'])
    job_data['block'] = block
    job_data['version'] = version
    job_data['flow'] = flow
    job_data['task'] = task

    id_str = '-'.join([str(job_id), block, version, flow, task])
    sha1obj = sha1()
    sha1obj.update(id_str.encode('utf-8'))
    job_data['id'] = sha1obj.hexdigest()

    current_time = datetime.datetime.now()
    year = current_time.year
    week_number = current_time.isocalendar()[1]

    return job_data, year, week_number


def save_job(job_data: Dict[str, Union[str, int]], year: int, week_number: int):
    """
    Save job data to job database
    """
    if not hasattr(config, 'mem_prediction') or not config.mem_prediction:
        return

    if hasattr(config, 'db_path') and os.path.exists(config.db_path):
        db_path = config.db_path
    else:
        db_path = os.path.join(os.getcwd(), '.ifp/ifp_db')
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        db_path = f'sqlite:///{db_path}'

    engine = create_engine(db_path)
    Session = sessionmaker(bind=engine)
    session = Session()

    weekly_job_table = create_weekly_job_table(year, week_number)
    Base.metadata.create_all(engine)

    new_job = weekly_job_table(**job_data)

    session.add(new_job)
    session.commit()
    session.close()


def generate_uuid_from_components(item_list: List[str]) -> str:
    combined_string = '_'.join(item_list)
    return str(uuid.uuid3(uuid.NAMESPACE_DNS, combined_string))


def initialize_database(db_path: str):
    engine = create_engine(db_path)
    Base.metadata.create_all(engine, checkfirst=True)


def save_ifp_record(data: dict):
    if hasattr(config, 'db_path') and os.path.exists(config.db_path):
        db_path = config.db_path
    else:
        db_path = os.path.join(os.getcwd(), '.ifp/ifp_db')
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        db_path = f'sqlite:///{db_path}'

    initialize_database(db_path)

    engine = create_engine(db_path)
    Session = sessionmaker(bind=engine)
    session = Session()

    data['uuid'] = generate_uuid_from_components(item_list=[data['block'], data['version'], data['file_path']])

    existing_record = session.query(IFPRecord).filter_by(uuid=data['uuid']).first()

    if existing_record:
        for key, value in data.items():
            setattr(existing_record, key, value)

        session.commit()
    else:
        new_record = IFPRecord(**data)
        session.add(new_record)
        session.commit()

    session.close()


def setup_task_job():
    db_path = os.path.join(os.getcwd(), '.ifp/task_job')
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    db_path = f'sqlite:///{db_path}'
    initialize_database(db_path)
    engine = create_engine(db_path)
    Session = sessionmaker(bind=engine)
    session = Session()
    return session


def save_task_job(data: dict):
    try:
        session = setup_task_job()
        data['uuid'] = generate_uuid_from_components(item_list=[data['job_id'], data['block'], data['version'], data['flow'], data['task']])

        new_record = TaskJobs(**data)
        session.add(new_record)
        session.commit()
        session.close()
    except Exception:
        pass