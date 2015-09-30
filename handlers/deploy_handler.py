__author__ = 'magus0219'

import logging
from config import DEBUG as _DEBUG, GITHUB as _GITHUB_CFG
from .common_handler import CommonHandler
from core.deploy_manager import dms
from core.payload import PayLoad
import threading
import json
import hmac
from utils.mongo_handler import mongodb_client

logger_server = logging.getLogger("DeployServer.DeployHandler")


class DeployHandler(CommonHandler):
    def post(self):
        # Auth git request
        self.event = self.request.headers.get('X-Github-Event', None)  # event name like 'push'...
        self.signature = self.request.headers.get('X-Hub-Signature', None).split('=')[
            1]  # e.g. sha1=a8d9e5c1c6e0f19b5a508c508d5204de171cbf1b
        self.delivery_uuid = self.request.headers.get('X-Github-Delivery', None)  # deliver uuid

        if _DEBUG == True:
            logger_server.debug(
                "Post Github Delivery[{uuid}] which type is [{type}] with signature [{signature}]".format(
                    uuid=self.delivery_uuid,
                    type=self.event,
                    signature=self.signature))
        h = hmac.new(_GITHUB_CFG['SECRET'].encode('utf8'), digestmod='sha1')
        h.update(self.request.body)
        # Fail
        if h.hexdigest() != self.signature:
            self.set_status(401)
        elif not self.event or not self.signature or not self.delivery_uuid:
            self.set_status(401)
        elif self.event == 'ping':
            if _DEBUG == True:
                logger_server.debug("Ping pass..")
        else:
            # Pass
            if _DEBUG == True:
                logger_server.debug("Auth pass..")
            self.payload = json.loads(self.request.body.decode("utf8"))
            payload = PayLoad.create_by_payload(self.delivery_uuid, self.event, self.payload)
            if _DEBUG == True:
                logger_server.debug("Is Tag:{istag}".format(istag=str(payload.is_tag)))
            repo_name = payload.repository_name
            if _DEBUG == True:
                logger_server.debug("Repo Name:{repo_name}".format(repo_name=repo_name))
            if payload and repo_name in dms:
                # Logging to db
                mongodb_client['deployment']['webhook'].insert({'event': self.event,
                                                                'signature': self.signature,
                                                                'delivery_uuid': self.delivery_uuid,
                                                                'payload': self.payload})
                t = threading.Thread(target=dms[repo_name].handle_event,
                                     args=(self.delivery_uuid, self.event, payload))
                t.start()







