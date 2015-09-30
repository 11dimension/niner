__author__ = 'magus0219'

import logging
import hashlib
from tornado.web import authenticated
from .common_handler import CommonHandler
import time
from utils.mongo_handler import mongodb_client

logger_server = logging.getLogger("DeployServer.ChangePasswordHandler")


class ChangePasswordHandler(CommonHandler):
    @authenticated
    def get(self):
        self.render("chpwd.html", msg="")

    @authenticated
    def post(self):
        password = self.get_body_argument('password', '')
        password2 = self.get_body_argument('password2', '')

        if not password or not password2:
            self.render("chpwd.html", msg="请填写完整")
        elif password != password2:
            self.render("chpwd.html", msg="两次密码输入不一致")
        else:
            m = hashlib.md5()
            m.update(password.encode("utf8"))
            password = m.hexdigest()

            account = self.get_current_user()
            account.password = password
            account.save()

            # log to db
            mongodb_client['deployment']['operation_log'].insert({
                "userId": self.get_current_user().user_id,
                "username": self.get_current_user().username,
                "operation": "chpwd",
                "createTimeStamp": int(time.time())
            })

            self.redirect('/deploy/repo')



