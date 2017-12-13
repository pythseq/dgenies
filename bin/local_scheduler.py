#!/usr/bin/env python3

import os
import time
import sys
import psutil
import atexit
from pony.orm import db_session, select
from tendo import singleton

# Allow only one instance:
me = singleton.SingleInstance()

app_folder = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "srv")
os.environ["PATH"] = os.path.join(app_folder, "bin") + ":" + os.environ["PATH"]
sys.path.insert(0, app_folder)

from database import Job, db
from config_reader import AppConfigReader
from lib.job_manager import JobManager

config_reader = AppConfigReader()

# Add DRMAA lib in env:
if config_reader.drmaa_lib_path is not None:
    os.environ["DRMAA_LIBRARY_PATH"] = config_reader.drmaa_lib_path
    try:
        import drmaa
        from lib.drmaa import DrmaaSession
        DRMAA_SESSION = DrmaaSession()
    except ImportError:
        pass

NB_RUN = config_reader.local_nb_runs
NB_PREPARE = config_reader.nb_data_prepare

DEBUG=True


def _printer(*messages):
    if DEBUG:
        print(*messages)


@db_session
def start_job(id_job, batch_system_type="local"):
    _printer("Start job", id_job)
    job = Job.get(id_job=id_job)
    job.status = "starting"
    db.commit()
    job_mng = JobManager(id_job=id_job, email=job.email)
    job_mng.set_inputs_from_res_dir()
    job_mng.run_job_in_thread(batch_system_type)


@db_session
def get_scheduled_local_jobs():
    all_jobs = []
    jobs = select(j for j in Job if j.batch_type == "local" and (j.status == "prepared" or j.status == "scheduled")).\
        sort_by(Job.date_created)
    for job in jobs:
        all_jobs.append(job.id_job)
        job.status = "scheduled"
    db.commit()
    return all_jobs


@db_session
def get_scheduled_cluster_jobs():
    all_jobs = []
    jobs = select(j for j in Job if j.batch_type != "local" and (j.status == "prepared" or j.status == "scheduled")).\
        sort_by(Job.date_created)
    for job in jobs:
        all_jobs.append({"job_id":job.id_job, "batch_type": job.batch_type})
        job.status = "scheduled"
    db.commit()
    return all_jobs


@db_session
def prepare_job(id_job):
    _printer("Prepare data for job:", id_job)
    job = Job.get(id_job=id_job)
    job.status = "preparing"
    db.commit()
    job_mng = JobManager(id_job=id_job, email=job.email)
    job_mng.set_inputs_from_res_dir()
    job_mng.prepare_data_in_thread()


@db_session
def get_prep_scheduled_jobs():
    all_jobs = []
    jobs = select(j for j in Job if j.status == "waiting").\
        sort_by(Job.date_created)
    for job in jobs:
        all_jobs.append(job.id_job)
    db.commit()
    return all_jobs


@db_session
def get_preparing_jobs_nb():
    return len(select(j for j in Job if j.status == "preparing"))


@db_session
def parse_started_jobs():
    jobs_started = []  # Only local jobs
    cluster_jobs_started = []  # Only cluster jobs
    jobs = select(j for j in Job if j.status == "started" or j.status == "starting"
                  or j.status == "merging" or j.status == "scheduled-cluster")
    for job in jobs:
        pid = job.id_process
        if job.batch_type == "local":
            if job.status != "started" or psutil.pid_exists(pid):
                jobs_started.append(job.id_job)
            else:
                print("Job %s (pid: %d) has died!" % (job.id_job, job.id_process))
                job.status = "fail"
                job.error = "<p>Your job has failed for an unexpected reason. Please contact the support.</p>"
                db.commit()
                # Todo: send mail about the error
        else:
            if job.status in ["started", "scheduled-cluster"]:
                s = DRMAA_SESSION.session
                decodestatus = {drmaa.JobState.UNDETERMINED: 'process status cannot be determined',
                        drmaa.JobState.QUEUED_ACTIVE: 'job is queued and active',
                        drmaa.JobState.SYSTEM_ON_HOLD: 'job is queued and in system hold',
                        drmaa.JobState.USER_ON_HOLD: 'job is queued and in user hold',
                        drmaa.JobState.USER_SYSTEM_ON_HOLD: 'job is queued and in user and system hold',
                        drmaa.JobState.RUNNING: 'job is running',
                        drmaa.JobState.SYSTEM_SUSPENDED: 'job is system suspended',
                        drmaa.JobState.USER_SUSPENDED: 'job is user suspended',
                        drmaa.JobState.DONE: 'job finished normally',
                        drmaa.JobState.FAILED: 'job finished, but failed'}
                status = s.jobStatus(str(job.id_process))
                if status not in [drmaa.JobState.RUNNING, drmaa.JobState.DONE, drmaa.JobState.QUEUED_ACTIVE,
                                  drmaa.JobState.SYSTEM_ON_HOLD, drmaa.JobState.USER_ON_HOLD,
                                  drmaa.JobState.USER_SYSTEM_ON_HOLD]:
                    if job.batch_type == "slurm":
                        os.system("scancel %s" % job.id_process)
                    elif job.batch_type == "sge":
                        os.system("qdel %s" % job.id_process)
                    print("Job %s (id on cluster: %d) has died!" % (job.id_job, job.id_process))
                    job.status = "fail"
                    job.error = "<p>Your job has failed for an unexpected reason. Please contact the support.</p>"
                    db.commit()
                    # Todo: send mail about the error
                else:
                    if job.status == "scheduled-cluster" and status == drmaa.JobState.RUNNING:
                        job.status = "started"
                        db.commit()
                    cluster_jobs_started.append(job.id_job)
            else:
                cluster_jobs_started.append(job.id_job)
    return jobs_started, cluster_jobs_started


@atexit.register
def cleaner():
    if "DRMAA_SESSION" in globals():
        DRMAA_SESSION.exit()


if __name__ == '__main__':

    while True:
        _printer("Checking jobs...")
        scheduled_jobs_local = get_scheduled_local_jobs()
        scheduled_jobs_cluster = get_scheduled_cluster_jobs()
        prep_scheduled_jobs = get_prep_scheduled_jobs()
        _printer("Waiting for preparing:", len(prep_scheduled_jobs))
        nb_preparing_jobs = get_preparing_jobs_nb()
        _printer("Preparing:", nb_preparing_jobs)
        _printer("Scheduled:", len(scheduled_jobs_local), "(local),", len(scheduled_jobs_cluster), "(cluster)")
        started_jobs, cluster_started_jobs = parse_started_jobs()
        nb_started = len(started_jobs)
        _printer("Started:", nb_started, "(local),", len(cluster_started_jobs), "(cluster)")
        while len(prep_scheduled_jobs) > 0 and nb_preparing_jobs < NB_PREPARE:
            prepare_job(prep_scheduled_jobs.pop(0))
            nb_preparing_jobs += 1
        while len(scheduled_jobs_local) > 0 and nb_started < NB_RUN:
            start_job(scheduled_jobs_local.pop(0))
            nb_started += 1
        for job in scheduled_jobs_cluster:
            start_job(job["job_id"], job["batch_type"])
        # Wait before return
            _printer("Sleeping...")
        time.sleep(15 if nb_preparing_jobs == 0 else 5)
