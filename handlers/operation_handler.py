__author__ = 'magus0219'

import logging
from tornado.web import authenticated
from .common_handler import CommonHandler
from core.deploy_manager import dms
from utils.mongo_handler import mongodb_client, serialize_status
import json
import time

logger_server = logging.getLogger("DeployServer.OperationHandler")


class OperationHandler(CommonHandler):
    @authenticated
    def put(self, repo_name, operation):
        if repo_name in dms:
            dm = dms[repo_name]
            if operation == 'cancel':
                dm.status.lock_acquire()
                dm.status.set_cancel_flag(True)
                dm.status.lock_release()

                # log to db
                mongodb_client['deployment']['operation_log'].insert({
                    "userId": self.get_current_user().user_id,
                    "username": self.get_current_user().username,
                    "repoName": repo_name,
                    "operation": operation,
                    "statusSnapshot": serialize_status(dm.get_status_info()),
                    "createTimeStamp": int(time.time())
                })

                return

            elif operation == 'enable_auto':
                dm.status.lock_acquire()
                dm.status.enable_auto_deploy()
                dm.status.lock_release()

            elif operation == 'disable_auto':
                dm.status.lock_acquire()
                dm.status.disable_auto_deploy()
                dm.status.lock_release()

                # log to db
                mongodb_client['deployment']['operation_log'].insert({
                    "userId": self.get_current_user().user_id,
                    "username": self.get_current_user().username,
                    "repoName": repo_name,
                    "operation": operation,
                    "createTimeStamp": int(time.time())
                })

    @authenticated
    def get(self, repo_name, operation):
        if repo_name in dms:
            dm = dms[repo_name]
            if operation == 'status':
                status = dm.get_status_info()

                if not status["task_running"]:
                    task_running = ''
                elif status["task_running"].tag:
                    task_running = status["task_running"].tag
                else:
                    task_running = status["task_running"].head_commit

                fresh_status = {
                    "status": status["status"],
                    "hosts_status": status["hosts_status"],
                    "stage": status["stage"],
                    "last_commit": status["last_commit"],
                    "last_commit_tag": status["last_commit_tag"].name if status["last_commit_tag"] else '',
                    "cancel_flag": status["cancel_flag"],
                    "auto_deploy_enable": status["auto_deploy_enable"],
                    "task_running": task_running,
                    "process_percent": status["process_percent"],
                    "task_waiting": [one_payload.tag for one_payload in status["task_waiting"]]
                }
                self.set_header('Content-Type', 'application/json; charset=UTF-8')
                self.write(json.dumps(fresh_status, ensure_ascii=False).encode('utf-8'))
                self.set_status(200)

