__author__ = 'magus0219'

import logging
from tornado.web import authenticated
from .common_handler import CommonHandler
from core.deploy_manager import dmc
from utils.enums import *
from config import INSTANCE_NAME as _INSTANCE_NAME

logger_server = logging.getLogger("DeployServer.IndexHandler")


class IndexHandler(CommonHandler):
    @authenticated
    def get(self, repo_name, branch):
        if repo_name in dmc and branch in dmc[repo_name]:
            self.set_status(200)
            if dmc[repo_name][branch].get_repo_strategy() == DeployStrategy.PRO_MODE:
                self.render("index_pro_mode.html", user=self.get_current_user(), status_info=dmc[repo_name][branch].get_status_info(),
                            repos=dmc.list_repos_with_branch(), instance_name=_INSTANCE_NAME)
            elif dmc[repo_name][branch].get_repo_strategy() == DeployStrategy.TEST_MODE:
                self.render("index_test_mode.html", user=self.get_current_user(), status_info=dmc[repo_name][branch].get_status_info(),
                            repos=dmc.list_repos_with_branch(), instance_name=_INSTANCE_NAME)

