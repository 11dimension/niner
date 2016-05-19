from smtplib import SMTP_SSL as SMTP
from email.mime.text import MIMEText
import logging
import datetime
from utils.mongo_handler import mongodb_client
from utils.decorator import retry

from config import DEBUG as _DEBUG, EMAIL

logger_server = logging.getLogger("DeployServer.MailManager")

success_title = "[{instance_name}][小九来散花啦] {repo_name}部署{tag_name}成功！"
success_text = """
-------------------部署相关-----------------------------
部署者:{payload_pusher}
部署来源:{payload_src}
部署仓库:{repo_name}
部署TAG:{tag_name}
部署开始时间:{start_time}
部署完成时间:{end_time}
部署耗时:{cost_time}
部署事件id:{event_id}
-------------------Tag相关-----------------------------
{tag_str}
"""

cancel_success_title = "[{instance_name}][小九被调戏，自愈成功] {repo_name}部署{tag_name}时被取消，且回滚成功！"
cancel_success_text = """
-------------------部署相关----------------------------
部署者:{payload_pusher}
部署来源:{payload_src}
部署仓库:{repo_name}
部署TAG:{tag_name}
部署开始时间:{start_time}
部署事件id:{event_id}
-------------------取消相关----------------------------
取消者:{cancel_user}
取消时间:{cancel_time}
回滚完成时间:{end_time}
整体耗时:{cost_time}
-------------------Tag相关----------------------------
{tag_str}
"""

cancel_fail_title = "[{instance_name}][[小九被调戏，自愈失败，严重警告] {repo_name}部署{tag_name}时被取消，回滚失败！"
cancel_fail_text = """
-------------------部署相关----------------------------
部署者:{payload_pusher}
部署来源:{payload_src}
部署仓库:{repo_name}
部署TAG:{tag_name}
部署事件id:{event_id}
-------------------取消相关----------------------------
取消者:{cancel_user}
取消时间:{cancel_time}
回滚完成时间:{end_time}
-------------------回滚错误----------------------------
{rollback_stack_info}
-------------------Tag相关----------------------------
{tag_str}
"""

error_title = "[{instance_name}][[小九遭遇意外，求关注] {repo_name}部署{tag_name}时发生错误，准备回滚！"
error_text = """
-------------------部署相关----------------------------
部署者:{payload_pusher}
部署来源:{payload_src}
部署仓库:{repo_name}
部署TAG:{tag_name}
部署开始时间:{start_time}
部署事件id:{event_id}
-------------------错误相关-----------------------------
{stack_info}
-------------------Tag相关-----------------------------
{tag_str}
"""

rollback_success_title = "[{instance_name}][[小九遭遇意外，自愈成功] {repo_name}部署{tag_name}时发生错误，回滚成功！"
rollback_success_text = """
-------------------部署相关----------------------------
部署者:{payload_pusher}
部署来源:{payload_src}
部署仓库:{repo_name}
部署TAG:{tag_name}
部署开始时间:{start_time}
部署事件id:{event_id}
-------------------回滚相关----------------------------
回滚完成时间:{end_time}
整体耗时:{cost_time}
-------------------错误相关-----------------------------
{stack_info}
-------------------Tag相关-----------------------------
{tag_str}
"""

rollback_fail_title = "[{instance_name}][[小九遭遇意外，自愈失败，严重警告] {repo_name}部署{tag_name}时发生错误，回滚失败！"
rollback_fail_text = """
-------------------部署相关----------------------------
部署者:{payload_pusher}
部署来源:{payload_src}
部署仓库:{repo_name}
部署TAG:{tag_name}
部署开始时间:{start_time}
部署事件id:{event_id}
-------------------回滚相关----------------------------
回滚出错时间:{end_time}
整体耗时:{cost_time}
-------------------回滚错误----------------------------
{rollback_stack_info}
-------------------原始错误----------------------------
{stack_info}
-------------------Tag相关-----------------------------
{tag_str}
"""


class MailManager():
    def __init__(self, smtp, user, password):
        self.smtp = smtp
        self.user = user
        self.password = password

    def _connect(self):
        self.conn = SMTP(self.smtp)
        if _DEBUG:
            self.conn.set_debuglevel(True)
        self.conn.login(self.user, self.password)

    @retry(3)
    def send_mail(self, subject, text, mail_to):
        msg = MIMEText(text, 'plain')
        msg['Subject'] = subject
        msg['To'] = ','.join(mail_to)
        msg['From'] = self.user

        self._connect()

        try:
            self.conn.sendmail(self.user, mail_to, msg.as_string())
            return True
        except Exception as ex:
            logger_server.exception(str(ex))
        finally:
            self.conn.close()

        return False

    def send_success_mail(self, instance_name, payload, tag, start_time, end_time):
        try:
            self.send_mail(subject=success_title.format(instance_name=instance_name,
                                                        repo_name=payload.repository_name,
                                                        tag_name=payload.tag),
                           text=success_text.format(payload_pusher=payload.username,
                                                    payload_src=payload.src,
                                                    repo_name=payload.repository_name,
                                                    tag_name=payload.tag,
                                                    start_time=start_time.strftime("%Y-%m-%d %H:%M:%S"),
                                                    end_time=end_time.strftime("%Y-%m-%d %H:%M:%S"),
                                                    cost_time=str(end_time - start_time),
                                                    event_id=payload.event_id,
                                                    tag_str=str(tag)
                           ),
                           mail_to=self.get_developer_emails())
        except Exception as ex:
            logger_server.exception(ex)

    def send_cancel_success_mail(self, instance_name, payload, tag, start_time, end_time):
        try:
            rst = mongodb_client['deployment']['operation_log'].find_one({
                "operation": "cancel",
                "statusSnapshot.task_running": payload.event_id
            })

            cancel_username = rst['username']
            cancel_time = datetime.datetime.fromtimestamp(rst['createTimeStamp'])

            self.send_mail(subject=cancel_success_title.format(instance_name=instance_name,
                                                               repo_name=payload.repository_name,
                                                       tag_name=payload.tag),
                           text=cancel_success_text.format(payload_pusher=payload.username,
                                                   payload_src=payload.src,
                                                   repo_name=payload.repository_name,
                                                   tag_name=payload.tag,
                                                   start_time=start_time.strftime("%Y-%m-%d %H:%M:%S"),
                                                   end_time=end_time.strftime("%Y-%m-%d %H:%M:%S"),
                                                   cost_time=str(end_time - start_time),
                                                   event_id=payload.event_id,
                                                   tag_str=str(tag),
                                                   cancel_user=cancel_username,
                                                   cancel_time=cancel_time.strftime("%Y-%m-%d %H:%M:%S")
                           ),
                           mail_to=self.get_developer_emails())
        except Exception as ex:
            logger_server.exception(ex)

    def send_cancel_fail_mail(self, instance_name, payload, tag, end_time, stack_info):
        try:
            rst = mongodb_client['deployment']['operation_log'].find_one({
                "operation": "cancel",
                "statusSnapshot.task_running": payload.event_id
            })

            cancel_username = rst['username']
            cancel_time = datetime.datetime.fromtimestamp(rst['createTimeStamp'])

            self.send_mail(subject=cancel_fail_title.format(instance_name=instance_name,
                                                            repo_name=payload.repository_name,
                                                       tag_name=payload.tag),
                           text=cancel_fail_text.format(payload_pusher=payload.username,
                                                   payload_src=payload.src,
                                                   repo_name=payload.repository_name,
                                                   tag_name=payload.tag,
                                                   end_time=end_time.strftime("%Y-%m-%d %H:%M:%S"),
                                                   event_id=payload.event_id,
                                                   tag_str=str(tag),
                                                   cancel_user=cancel_username,
                                                   cancel_time=cancel_time.strftime("%Y-%m-%d %H:%M:%S"),
                                                   rollback_stack_info=stack_info
                           ),
                           mail_to=self.get_developer_emails())
        except Exception as ex:
            logger_server.exception(ex)

    def send_error_mail(self, instance_name, payload, tag, start_time, stack_info):
        try:
            self.send_mail(subject=error_title.format(instance_name=instance_name,
                                                      repo_name=payload.repository_name,
                                                      tag_name=payload.tag),
                           text=error_text.format(payload_pusher=payload.username,
                                                  payload_src=payload.src,
                                                  repo_name=payload.repository_name,
                                                  tag_name=payload.tag,
                                                  start_time=start_time.strftime("%Y-%m-%d %H:%M:%S"),
                                                  event_id=payload.event_id,
                                                  tag_str=str(tag),
                                                  stack_info=stack_info
                           ),
                           mail_to=self.get_developer_emails())
        except Exception as ex:
            logger_server.exception(ex)

    def send_rollback_success_mail(self, instance_name, payload, tag, start_time, end_time, stack_info):
        try:
            self.send_mail(subject=rollback_success_title.format(instance_name=instance_name,
                                                                 repo_name=payload.repository_name,
                                                                 tag_name=payload.tag),
                           text=rollback_success_text.format(payload_pusher=payload.username,
                                                             payload_src=payload.src,
                                                             repo_name=payload.repository_name,
                                                             tag_name=payload.tag,
                                                             start_time=start_time.strftime("%Y-%m-%d %H:%M:%S"),
                                                             end_time=end_time.strftime("%Y-%m-%d %H:%M:%S"),
                                                             cost_time=str(end_time - start_time),
                                                             event_id=payload.event_id,
                                                             tag_str=str(tag),
                                                             stack_info=stack_info
                           ),
                           mail_to=self.get_developer_emails())
        except Exception as ex:
            logger_server.exception(ex)

    def send_rollback_fail_mail(self, instance_name, payload, tag, start_time, end_time, stack_info, rollback_stack_info):
        try:
            self.send_mail(subject=rollback_fail_title.format(instance_name=instance_name,
                                                              repo_name=payload.repository_name,
                                                              tag_name=payload.tag),
                           text=rollback_fail_text.format(payload_pusher=payload.username,
                                                          payload_src=payload.src,
                                                          repo_name=payload.repository_name,
                                                          tag_name=payload.tag,
                                                          start_time=start_time.strftime("%Y-%m-%d %H:%M:%S"),
                                                          end_time=end_time.strftime("%Y-%m-%d %H:%M:%S"),
                                                          cost_time=str(end_time - start_time),
                                                          event_id=payload.event_id,
                                                          tag_str=str(tag),
                                                          stack_info=stack_info,
                                                          rollback_stack_info=rollback_stack_info
                           ),
                           mail_to=self.get_developer_emails())
        except Exception as ex:
            logger_server.exception(ex)

    def get_developer_emails(self):
        if _DEBUG:
            return "qinyang@baixing.com"
        else:
            to_list = []
            rst = mongodb_client['deployment']['account'].find()
            for one_dev in rst:
                to_list.append(one_dev['email'])

            return to_list

mail_manager = MailManager(EMAIL['SMTP'], EMAIL['USER'], EMAIL['PASSWORD'])

if __name__ == '__main__':
    text = "TEST"
    subject = "TEST SUBJECT"
    mail_manager.send_mail(subject, text, mail_manager.get_developer_emails())


