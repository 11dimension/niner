__author__ = 'magus0219'

import logging
from tornado.web import authenticated
from .common_handler import CommonHandler
from utils.saferedisclient import redis_manager

logger_server = logging.getLogger("DeployServer.LogoutHandler")


class LogoutHandler(CommonHandler):
    @authenticated
    def get(self):
        user_id = self.get_current_user()

        tokens = redis_manager.keys('{userid}:*'.format(userid=user_id))

        for one_token in tokens:
            redis_manager.delete(one_token)

        self.clear_cookie('d-token')

        self.redirect("/deploy/login")




