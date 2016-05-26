__author__ = 'magus0219'

import logging
import hashlib
from tornado.web import authenticated
from .common_handler import CommonHandler
from utils.mongo_handler import mongodb_client
from models.account import Account
import time
from config import INSTANCE_NAME as _INSTANCE_NAME

logger_server = logging.getLogger("DeployServer.RegisterHandler")


class RegisterHandler(CommonHandler):
    @authenticated
    def get(self):
        self.render("register.html", msg="", instance_name=_INSTANCE_NAME)

    @authenticated
    def post(self):
        username = self.get_body_argument('inputUsername', '')
        password = self.get_body_argument('inputPassword', '')
        email = self.get_body_argument('inputEmail', '')

        if not username:
            self.render("register.html", msg="用户名不应为空", instance_name=_INSTANCE_NAME)
        elif not password:
            self.render("register.html", msg="密码不应为空", instance_name=_INSTANCE_NAME)
        elif not password:
            self.render("register.html", msg="邮箱不应为空", instance_name=_INSTANCE_NAME)
        elif not self.current_user.has_role('super'):
            self.render("register.html", msg="你没有权限创建用户", instance_name=_INSTANCE_NAME)
        else:
            # check username
            rst = mongodb_client['deployment']['account'].find_one({
                "username": username
            })

            if rst:
                self.render("register.html", msg="用户名已存在", instance_name=_INSTANCE_NAME)
            else:
                m = hashlib.md5()
                m.update(password.encode("utf8"))
                password = m.hexdigest()

                account = Account(username, password, email, ['dev'])

                account.save()

                # log to db
                mongodb_client['deployment']['operation_log'].insert({
                    "userId": self.get_current_user().user_id,
                    "username": self.get_current_user().username,
                    "operation": "register",
                    "register_username": username,
                    "createTimeStamp": int(time.time())
                })

                self.redirect('/deploy/repo')



