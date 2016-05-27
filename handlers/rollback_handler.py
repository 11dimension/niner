__author__ = 'magus0219'

import logging
from tornado.web import authenticated
from .common_handler import CommonHandler
from core.deploy_manager import dmc
from core.payload import PayLoad
import threading
import time
from utils.mongo_handler import mongodb_client

logger_server = logging.getLogger("DeployServer.RollbackHandler")


class RollbackHandler(CommonHandler):
    @authenticated
    def put(self, repo_name, branch, commit_id, tag):
        if repo_name in dmc and branch in dmc[repo_name]:
            dm = dmc[repo_name][branch]
            payload = PayLoad.create_by_rollback(commit_id, tag, repo_name, self.get_current_user().username)

            mongodb_client['deployment']['webhook'].insert({'event': 'rollback',
                                                            "event_id": payload.event_id,
                                                            "repoName": repo_name,
                                                            "branch": branch,
                                                            'payload': vars(payload),
                                                            'createTimeStamp': int(time.time())})
            t = threading.Thread(target=dm.handle_event,
                                 args=(payload.event_id, payload.event_type, payload))
            t.start()

            # log to db
            mongodb_client['deployment']['operation_log'].insert({
                "userId": self.get_current_user().user_id,
                "username": self.get_current_user().username,
                "repoName": repo_name,
                "operation": "rollback",
                "event_id": payload.event_id,
                "rollback_to_commit": commit_id,
                "rollback_to_tag": tag,
                "createTimeStamp": int(time.time())
            })

            self.set_status(200)

