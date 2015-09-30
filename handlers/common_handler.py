__author__ = 'magus0219'

import tornado.web
import logging
from models.account import Account
from utils.saferedisclient import redis_manager
from config import DEBUG as _DEBUG

logger_server = logging.getLogger("DeployServer.DeployHandler")


class CommonHandler(tornado.web.RequestHandler):
    def prepare(self):
        if _DEBUG:
            logger_server.info("{method}:{uri}".format(method=self.request.method, uri=self.request.uri))

    def get_current_user(self):
        redis_key = self.get_secure_cookie('d-token')

        # get cookie
        if not redis_key:
            return None
        else:
            # check redis
            found = redis_manager.get(redis_key)
            if not found:
                return None
            else:
                user_id = redis_key.decode('utf=8').split(':')[0]
                try:
                    return Account.find_by_user_id(user_id)
                except Exception as ex:
                    return None