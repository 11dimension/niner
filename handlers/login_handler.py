__author__ = 'magus0219'

import logging
import hashlib
import uuid
import datetime
from .common_handler import CommonHandler
from utils.mongo_handler import mongodb_client
from utils.saferedisclient import redis_manager
from config import INSTANCE_NAME as _INSTANCE_NAME

logger_server = logging.getLogger("DeployServer.LoginHandler")


class LoginHandler(CommonHandler):
    def get(self):
        if not self.get_current_user() is None:
            self.redirect("/deploy/repo")
        else:
            self.render("login.html", msg="", instance_name=_INSTANCE_NAME)

    def post(self):
        username = self.get_body_argument('inputUsername', '')
        password = self.get_body_argument('inputPassword', '')

        if not username:
            self.render("login.html", msg="用户名不应为空", instance_name=_INSTANCE_NAME)
        elif not password:
            self.render("login.html", msg="密码不应为空", instance_name=_INSTANCE_NAME)
        else:
            # check password
            m = hashlib.md5()
            m.update(password.encode("utf8"))
            password = m.hexdigest()

            rst = mongodb_client['deployment']['account'].find_one({
                "username": username,
                "password": password
            })

            if not rst:
                self.render("login.html", msg="用户名或密码不正确", instance_name=_INSTANCE_NAME)
            else:
                user_id = rst['_id']
                # Generate token
                token = str(uuid.uuid1())
                d = datetime.timedelta(days=30)
                redis_key = "{userid}:{token}".format(userid=user_id, token=token)

                redis_manager.setex(redis_key, d, "1")

                self.set_secure_cookie('d-token', redis_key)

                self.redirect("/deploy/repo")




