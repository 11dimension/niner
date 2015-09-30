__author__ = 'magus0219'

import logging
from tornado.web import authenticated
from .common_handler import CommonHandler
from core.deploy_manager import dms
from utils.enums import *

logger_server = logging.getLogger("DeployServer.IndexHandler")


class IndexHandler(CommonHandler):
    @authenticated
    def get(self, repo_name):
        if repo_name in dms:
            self.set_status(200)
            if dms[repo_name].get_repo_strategy() == DeployStrategy.PRO_MODE:
                self.render("index_pro_mode.html", user=self.get_current_user(), status_info=dms[repo_name].get_status_info(), repos=list(dms.keys()))
            elif dms[repo_name].get_repo_strategy() == DeployStrategy.TEST_MODE:
                self.render("index_test_mode.html", user=self.get_current_user(), status_info=dms[repo_name].get_status_info(), repos=list(dms.keys()))

