from flask import request, jsonify, Blueprint, send_file
import datetime
import requests
import json
import io

from infra.utils import logger, get_global, get_job, get_db
from core.agent import Agent
from infra.decorators import process_job

submitter_api = Blueprint('submitter_api', __name__)
log = logger()


@submitter_api.route('/get_report', methods=['GET'])
def get_report():
    job_id = request.args.get('id')
    executor_url = get_job(job_id)['executor_url']
    executor_port = get_job(job_id)['executor_port']

    sio = io.BytesIO()
    rv = requests.get(f'http://{executor_url}:{executor_port}/report',
                      params={'job_id': job_id}).content
    sio.write(rv)
    sio.seek(0)
    return send_file(
        sio,
        as_attachment=True,
        attachment_filename=f'job{job_id[0:5]}')


def request_orchestrator(agent, required, job_id=None):
    agent.log(f'requesting orchestrating agents', report=True, job_id=job_id)
    orchestrator_agents = json.loads(requests.get(f'http://{get_global("tracker_host")}:3000/assign_agents',
                                                  params={'source': get_global('agent_name'),
                                                          'required': required}).content.decode("ascii"))[0]
    agent.log(f'acquired orchestrating agents: {orchestrator_agents}', report=True, job_id=job_id)
    return orchestrator_agents


@submitter_api.route('/submit', methods=['PUT', 'POST', 'GET'])
@process_job
def submit(job):
    agent = Agent(job_id=job.job_id, role='submit')
    try:

        agent.report_job(job.job_id, 'submitting')

        # todo - add tracker object
        orchestrator_agent = request_orchestrator(agent, 1, job_id=job.job_id)

        job.set('assigned_agent', orchestrator_agent)
        # agent.report(f'sending job: {job.job_id}, to orchestrator: {orchestrator_agent}', job_id=job.job_id)
        agent.report_job(job.job_id, f'sending to orchestrator: {orchestrator_agent}')

        submission_time = str(datetime.datetime.now())

        # todo - make sure api call is not waiting for response, then have job.set_may after call
        job_params = {
            'job_status': 'submitted',
            'submission_time': str(datetime.datetime.now()),
        }
        job.set_many(job_params)

        # todo - this is an agent skill
        # todo - handle async
        try:
            requests.get(f'http://{orchestrator_agent["url"]}:{orchestrator_agent["port"]}/orchestrate',
                         params={
                             'git_repo': job.get("git_repo"),
                             'file_name': job.get("file_name"),
                             'job_id': job.job_id,
                             'submission_time': submission_time,
                             'submitter_name': get_global('agent_name'),
                             'submitter_url': get_global('agent_url'),
                             'submitter_port': get_global('agent_port')
                         },
                         timeout=0.0000000001)
        except requests.exceptions.ReadTimeout:
            pass

        agent.set('agent_status', 'connected')

    except Exception as e:
        agent.log(e)
        return f'error submitting job {job.job_id}: {e}'

    return {
        'status': 'submitted',
        'timestamp': submission_time,
        'orchestrator': orchestrator_agent,
        'job_id': job.job_id
    }
