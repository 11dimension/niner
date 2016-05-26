__author__ = 'magus0219'
from .repository import Repository, RepositoryException
from config import REPOSITORY as _REPOSITORY_CFG, DEBUG as _DEBUG
from utils.mongo_handler import mongodb_client, serialize_status
from utils.enums import *
from utils.mail import mail_manager
import datetime
import logging
import time
import re
import threading
import traceback

logger_server = logging.getLogger("DeployServer.DeployManager")


class DeployManagerException(Exception):
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return self.msg


class DeployCancel(Exception):
    pass


class DeployManagerStatus:
    def __init__(self, repo):
        self.repo = repo
        self.status = {
            'repo_name': repo.repo_name,  # 仓库名称
            'auto_deploy_enable': True,  # 是否启动自动部署
            'status': DeployStatus.IDLE,  # 当前部署状态
            'task_running': None,  # 正在执行的payload
            'task_waiting': [],  # 等待执行的payload
            'last_commit': None,  # 当前仓库的commit(供展示，与仓库实际情况不完全同步)
            'last_commit_tag': None,  # 当前仓库last_commit对应的tag object(供展示，与仓库实际情况不完全同步)
            'last_tags': None,  # 仓库最后N个标签，tag object的列表
            'backup_filename': None,  # 备份文件
            'package_filename': None,  # package文件
            'hosts': repo.hosts,  # host列表
            'hosts_roles': repo.hosts_roles,  # host角色字典
            'hosts_status': {},  # host状态字典{ hostname1: HostStatus, hostname2: HostStatus }
            'stage': None,  # 当前部署阶段
            'cancel_flag': False,  # 是否取消部署
            'process_percent': 0  # 部署进度, 整数
        }
        self.locks = threading.RLock()
        self.init_host_status()
        self.update_last_commit()
        self.update_last_release_tags()

    def update_last_release_tags(self):
        self.status['last_tags'] = self.repo.get_last_release_tags()

    def get_process_percent(self):
        return self.status['process_percent']

    def calculate_process_interval(self, total, steps):
        """Calculate_process_interval by every host during release packages

        :param total: total percent to divide
        :param steps: release steps
        :return:
        """
        return int(total / (len(self.get_hosts()) * steps))

    def init_host_status(self):
        for one_host in self.repo.hosts:
            self.status['hosts_status'][one_host] = HostStatus.NORMAL

    def set_host_status(self, host, status):
        self.status['hosts_status'][host] = status

    def get_hosts(self):
        return self.status['hosts']

    def get_fault_count(self):
        return self.status['fault_count']

    def is_enable_auto_deploy(self):
        return self.status['auto_deploy_enable']

    def enable_auto_deploy(self):
        self.status['auto_deploy_enable'] = True

    def disable_auto_deploy(self):
        self.status['auto_deploy_enable'] = False

    def get_status(self):
        return self.status['status']

    def set_status(self, status):
        self.status['status'] = status

    def set_running_task(self, payload):
        self.status['task_running'] = payload

    def get_running_task(self):
        return self.status['task_running']

    def add_waiting_task(self, payload):
        self.status['task_waiting'].append(payload)

    def has_waiting_task(self):
        if len(self.status['task_waiting']) > 0:
            return True
        return False

    def get_first_waiting_task(self):
        return self.status['task_waiting'].pop(0)

    def update_last_commit(self):
        """Update last commit & tag

        :return:
        """
        self.status['last_commit'] = self.repo.get_last_commit()
        self.status['last_commit_tag'] = self.repo.get_commit_tag(self.status['last_commit'])

    def get_last_commit(self):
        return self.status['last_commit']

    def get_last_tags(self):
        self.status['last_tags'] = self.repo.get_last_release_tags()

    def export_status(self):
        return self.status

    def set_backup_filename(self, backup_filename):
        self.status['backup_filename'] = backup_filename

    def get_backup_filename(self):
        return self.status['backup_filename']

    def set_package_filename(self, package_filename):
        self.status['package_filename'] = package_filename

    def get_package_filename(self):
        return self.status['package_filename']

    def lock_acquire(self):
        self.locks.acquire()

    def lock_release(self):
        self.locks.release()

    def set_stage_info(self, stage_info, process_percent=0):
        """Set stage & process percent

        :param stage_info:
        :param process_percent:
        :return:
        """
        self.status['stage'] = stage_info
        self.status['process_percent'] = process_percent

    def set_cancel_flag(self, flag):
        self.status['cancel_flag'] = flag

    def is_cancel(self):
        return self.status['cancel_flag']


class DeployManager:
    def __init__(self, repo_name, repo_config):
        self.repo = Repository(repo_name, repo_config)
        self.status = DeployManagerStatus(self.repo)
        if _DEBUG:
            logger_server.debug("Init status" + str(self.status.export_status()))

    def handle_event(self, event_id, event_type, payload):
        if self.need_handle(payload):
            # Acquire lock here to get enable_auto_deploy and status
            self.status.lock_acquire()
            if self.status.is_enable_auto_deploy():
                if _DEBUG:
                    logger_server.debug(self.status.export_status())

                repo_status = self.status.get_status()
                # If idle, start deployment
                if repo_status == DeployStatus.IDLE:
                    self.deploy(payload)
                elif repo_status in (DeployStatus.RUNNING, DeployStatus.ROLLBACK):
                    # Add to Task List
                    if self.need_handle(payload):
                        self.status.add_waiting_task(payload)
                    self.status.lock_release()
                    if _DEBUG:
                        logger_server.debug("after adding waiting:" + str(self.status.export_status()))

    def stage(self, stage_info, process_percent=0):
        self.status.set_stage_info(stage_info, process_percent)
        # Adjust if deploy canceled
        if self.status.is_cancel() and self.status.get_status() == DeployStatus.RUNNING:
            payload = self.status.get_running_task()
            try:
                self.rollback(payload)
            except Exception as ex:
                datetime_end = datetime.datetime.now()
                exception_str = str(ex)
                stack_info = traceback.format_exc()
                mongodb_client['deployment']['deploy_log'].insert({'event_id': payload.event_id,
                                                                   'type': 'deploy_cancel',
                                                                   'result': 'fail',
                                                                   'exception': exception_str,
                                                                   'trace': stack_info,
                                                                   'createdTimeStamp': int(time.time())})
                if self.get_repo_strategy() == DeployStrategy.PRO_MODE:
                    mail_manager.send_cancel_fail_mail(payload,
                                                       self.repo.get_tag_info(payload.tag), datetime_end, stack_info)
            else:
                raise DeployCancel()

    def get_status_info(self):
        return self.status.export_status()

    def get_repo_strategy(self):
        return self.repo.strategy

    def deploy(self, payload):
        raise NotImplementedError

    def rollback(self, payload):
        raise NotImplementedError


class GitBaseDeployManager(DeployManager):
    def need_handle(self, payload):
        # Must be the same branch
        if payload.is_branch and self.repo.branch == payload.branch:
            return True

        return False

    def deploy(self, payload):
        try:
            event_id = payload.event_id
            repo = self.repo
            logger_server.info("Start deploy Event[{event_id}]...".format(event_id=event_id))
            datetime_start = datetime.datetime.now()

            # Change & init status to Running
            self.status.set_status(DeployStatus.RUNNING)
            self.status.set_running_task(payload)
            self.status.init_host_status()
            self.status.set_cancel_flag(False)
            # Release lock to let other event occur
            self.status.lock_release()
            if _DEBUG:
                logger_server.debug(self.status.export_status())

            # Step 1.Clean Git Work Dir
            self.stage("Clean Git Work Dir", 20)
            repo.clean()
            # Step 2.Pull data
            self.stage("Pull data", 30)
            pull_content = repo.pull()

            # Step 3.Get change files
            self.stage("Get change files", 40)
            commit_after_pull = self.repo.get_last_commit()
            commit_before_pull = self.status.get_last_commit()

            if _DEBUG:
                logger_server.debug(
                    "Start commit:{start},end commit:{end}".format(start=commit_before_pull, end=commit_after_pull))

            change_files = self.repo.get_change_files(commit_before_pull, commit_after_pull)

            if _DEBUG:
                logger_server.debug("Change files:" + str(change_files))

            if change_files:
                # Step 4.NPM & Python Package Install
                self.stage("NPM & Python Package Install", 60)
                repo.install_pkg(repo.get_pkg_to_install(change_files))
                # Step 5.Run Post-actions
                self.stage("Run Post-actions", 70)
                repo.handle_post_actions()

                # Step 6.Release
                self.stage("Release", 80)
                for one_host in self.status.get_hosts():
                    try:
                        self.status.set_host_status(one_host, HostStatus.DEPLOYING)
                        # Step 6.1.SYNC
                        if _DEBUG:
                            logger_server.debug("Rsync files to {host}".format(host=one_host))
                        self.stage("Rsync files to {host}".format(host=one_host),
                                   self.status.get_process_percent() + self.status.calculate_process_interval(20, 2))
                        repo.rsync(self.repo.git_path[:-1],
                                   "deploy@{host}:{deploy}".format(host=one_host, deploy=self.repo.deploy_path),
                                   "{git_path}{file}".format(git_path=self.repo.git_path,file=self.repo.exclude_filename) if
                                       self.repo.exclude_filename else None)

                        # Step 6.2.Get Services to restart
                        restart_services = repo.get_service_to_restart(change_files)
                        if _DEBUG:
                            logger_server.debug("service to restart:" + str(restart_services))
                        # Step 6.3.Restart Services
                        if _DEBUG:
                            logger_server.debug("Restart services at {host}".format(host=one_host))
                        self.stage("Restart services at {host}".format(host=one_host),
                                   self.status.get_process_percent() + self.status.calculate_process_interval(20, 2))
                        repo.restart_services(restart_services, one_host)
                        self.status.set_host_status(one_host, HostStatus.SUCCESS)
                    except RepositoryException as ex:
                        self.status.set_host_status(one_host, HostStatus.FAULT)
                        raise ex

                """
                # Step 6.Get Services to restarts
                self.stage("Get Services to restart", 80)
                restart_services = repo.get_service_to_restart(change_files)
                if _DEBUG:
                    logger_server.debug("service to restart:" + str(restart_services))
                # Step 7.Restart Services
                self.stage("Restart Services", 90)
                repo.restart_services(restart_services, self.status.get_hosts()[0])
                """
                self.stage("Finish", 100)

            else:
                logger_server.info("Nothing has been changed")

            # Logging
            logger_server.info(
                "Deploy Event[{event_id}] done.".format(event_id=event_id))
            datetime_end = datetime.datetime.now()
            mongodb_client['deployment']['deploy_log'].insert({'event_id': payload.event_id,
                                                               'type': 'deploy',
                                                               'repo_name': self.repo.repo_name,
                                                               'result': "success",
                                                               'cost_time': str(datetime_end - datetime_start),
                                                               'createdTimeStamp': int(time.time())})

            # Check if exist waiting task to run
            self.status.lock_acquire()
            self.status.update_last_commit()

            if self.status.has_waiting_task():
                self.deploy(self.status.get_first_waiting_task())
                return

            # Change Status to Idle, Trick: Here will be reached once during one working list
            self.status.set_status(DeployStatus.IDLE)
            self.stage(None)
            self.status.set_running_task(None)
            self.status.set_cancel_flag(False)
            if _DEBUG:
                logger_server.debug("Status" + str(self.status.export_status()))

            self.status.lock_release()
        except DeployCancel as ex:
            mongodb_client['deployment']['deploy_log'].insert({'event_id': payload.event_id,
                                                               'type': 'deploy_cancel',
                                                               'result': 'success',
                                                               'createdTimeStamp': int(time.time())})
        except Exception as ex:
            exception_str = str(ex)
            stack_info = traceback.format_exc()
            mongodb_client['deployment']['deploy_log'].insert({'event_id': payload.event_id,
                                                               'type': 'deploy',
                                                               'result': 'exception',
                                                               'exception': exception_str,
                                                               'trace': stack_info,
                                                               'createdTimeStamp': int(time.time()),
                                                               'status_snapshot': serialize_status(
                                                                   self.status.export_status())})
            mail_manager.send_error_mail(payload, '', datetime_start, stack_info)
            try:
                self.rollback(payload)
                datetime_end = datetime.datetime.now()
                mongodb_client['deployment']['deploy_log'].insert({'event_id': payload.event_id,
                                                                   'type': 'deploy_rollback',
                                                                   'result': 'success',
                                                                   'exception': exception_str,
                                                                   'trace': stack_info,
                                                                   'createdTimeStamp': int(time.time()),
                                                                   'status_snapshot': serialize_status(
                                                                       self.status.export_status())})
                mail_manager.send_rollback_success_mail(payload, '', datetime_start,
                                                        datetime_end, stack_info)

            except Exception as rollback_ex:
                rollback_exception_str = str(rollback_ex)
                rollback_stack_info = traceback.format_exc()
                datetime_end = datetime.datetime.now()
                mongodb_client['deployment']['deploy_log'].insert({'event_id': payload.event_id,
                                                                   'type': 'deploy_rollback',
                                                                   'result': 'fail',
                                                                   'exception_original': exception_str,
                                                                   'trace_original': stack_info,
                                                                   'exception_rollback': rollback_exception_str,
                                                                   'trace_rollback': rollback_stack_info,
                                                                   'createdTimeStamp': int(time.time()),
                                                                   'status_snapshot': serialize_status(
                                                                       self.status.export_status())})
                mail_manager.send_rollback_fail_mail(payload, '', datetime_start,
                                                        datetime_end, stack_info, rollback_stack_info)

    def rollback(self, payload):
        try:
            event_id = payload.event_id
            head_commit = payload.head_commit
            repo = self.repo

            logger_server.info("Start rollback Event[{event_id}]...".format(event_id=event_id))

            # Change Status to Rollback and disable auto deployment
            self.status.lock_acquire()
            self.status.disable_auto_deploy()
            self.status.set_status(DeployStatus.ROLLBACK)
            self.status.lock_release()

            # Step 1.Get change files
            self.stage("Get change files", 20)
            try:
                change_files = repo.get_change_files(self.status.get_last_commit(), head_commit)
                if _DEBUG:
                    logger_server.debug("change files:" + str(change_files))
            except:
                # May be pull failed so head_commit is not a valid object
                change_files = []

            # Step 2.Get Services to restart
            self.stage("Get Services to restart", 40)
            restart_services = repo.get_service_to_restart(change_files)
            if _DEBUG:
                logger_server.debug("service to restart:" + str(restart_services))

            # Step 3.Git Reset
            self.stage("Git Reset", 60)
            repo.reset(self.status.get_last_commit())

            # Step 4.Release
            self.stage("Release", 80)
            for one_host in self.status.get_hosts():
                try:
                    self.status.set_host_status(one_host, HostStatus.DEPLOYING)
                    # Step 4.1.SYNC
                    if _DEBUG:
                        logger_server.debug("Rsync files to {host}".format(host=one_host))
                    self.stage("Rsync files to {host}".format(host=one_host),
                               self.status.get_process_percent() + self.status.calculate_process_interval(20, 2))
                    repo.rsync(self.repo.git_path[:-1],
                               "deploy@{host}:{deploy}".format(host=one_host, deploy=self.repo.deploy_path),
                               "{git_path}{file}".format(git_path=self.repo.git_path,file=self.repo.exclude_filename) if
                                    self.repo.exclude_filename else None)

                    # Step 4.2.Restart Services
                    if _DEBUG:
                        logger_server.debug("Restart services at {host}".format(host=one_host))
                    self.stage("Restart services at {host}".format(host=one_host),
                               self.status.get_process_percent() + self.status.calculate_process_interval(20, 2))
                    repo.restart_services(restart_services, one_host)
                    self.status.set_host_status(one_host, HostStatus.SUCCESS)
                except RepositoryException as ex:
                    self.status.set_host_status(one_host, HostStatus.FAULT)
                    raise ex

            """
            # Step 4.Restart Services
            self.stage("Restart Services", 80)
            repo.restart_services(restart_services, self.status.get_hosts()[0])
            """
            # Logging
            logger_server.info(
                "Rollback Event[{event_id}] done.".format(event_id=event_id))

            # Change Status to Idle
            self.status.lock_acquire()
            self.status.set_status(DeployStatus.IDLE)
            self.status.set_running_task(None)
            self.stage(None)
            self.status.update_last_commit()
            if _DEBUG:
                logger_server.debug("Status" + str(self.status.export_status()))
            self.status.lock_release()
        except Exception as ex:
            mongodb_client['deployment']['deploy_log'].insert({'event_id': payload.event_id,
                                                               'type': 'rollback',
                                                               'result': 'fail',
                                                               'exception': str(ex),
                                                               'createdTimeStamp': int(time.time()),
                                                               'status_snapshot': serialize_status(
                                                                   self.status.export_status())})
            raise ex


class PackageBaseDeployManager(DeployManager):
    def need_handle(self, payload):
        # Must be release tag: r*.*.*
        pattern = '^r\d+\.\d+\.\d+$'
        if payload.is_tag:
            rst = re.match(pattern, payload.tag)
            if rst:
                return True
            else:
                logger_server.info("Tag {tag} is not a release tag".format(tag=payload.tag))

        return False

    def deploy(self, payload):
        try:
            event_id = payload.event_id
            repo = self.repo
            logger_server.info("Start deploy Event[{event_id}]...".format(event_id=event_id))
            datetime_start = datetime.datetime.now()

            # Change & init status to Running
            self.status.set_status(DeployStatus.RUNNING)
            self.status.set_running_task(payload)
            self.status.init_host_status()
            self.status.set_cancel_flag(False)
            # Release lock to let other event occur
            self.status.lock_release()
            if _DEBUG:
                logger_server.debug(self.status.export_status())

            # Step 1.Clean Git Work Dir
            self.stage("Clean Git Work Dir", 10)
            repo.clean()
            # Step 2.Fetch data
            self.stage("Fetch data", 20)
            fetch_content = repo.fetch()
            # Step 3.Reset to tag
            self.stage("Reset to tag", 30)
            repo.reset(payload.tag)

            commit_after_pull = self.repo.get_last_commit()
            commit_before_pull = self.status.get_last_commit()

            if _DEBUG:
                logger_server.debug(
                    "Start commit:{start},end commit:{end}".format(start=commit_before_pull, end=commit_after_pull))

            change_files = self.repo.get_change_files(commit_before_pull, commit_after_pull)

            if _DEBUG:
                logger_server.debug("Change files:" + str(change_files))

            if change_files:
                # Step 4.NPM & Python Package Install
                self.stage("NPM & Python Package Install", 40)
                repo.install_pkg(repo.get_pkg_to_install(change_files))
                # Step 5.Run Post-actions
                self.stage("Run Post-actions", 50)
                repo.handle_post_actions()
                # Step 6.Backup Deploy Directory
                self.stage("Backup Deploy Directory", 60)
                backup_tar_file = repo.backup_deploy_dir()
                self.status.set_backup_filename(backup_tar_file)

                if _DEBUG:
                    logger_server.debug("Backup File:" + backup_tar_file)

                # Step 7.Tar directory
                self.stage("Tar directory", 70)
                package_file = repo.tar_git_dir(payload.tag)
                self.status.set_package_filename(package_file)

                if _DEBUG:
                    logger_server.debug("Package File:" + package_file)

                # Step 8.Release Tar
                self.stage("Release Package", 80)
                for one_host in self.status.get_hosts():
                    try:
                        self.status.set_host_status(one_host, HostStatus.DEPLOYING)
                        # Step 8.1.SYNC package
                        if _DEBUG:
                            logger_server.debug("Rsync files to {host}".format(host=one_host))
                        self.stage("Rsync files to {host}".format(host=one_host),
                                   self.status.get_process_percent() + self.status.calculate_process_interval(20, 2))
                        repo.release(package_file, one_host)

                        # Step 8.2.Get Services to restart
                        restart_services = repo.get_service_to_restart(change_files)
                        if _DEBUG:
                            logger_server.debug("service to restart:" + str(restart_services))
                        # Step 8.3.Restart Services
                        if _DEBUG:
                            logger_server.debug("Restart services at {host}".format(host=one_host))
                        self.stage("Restart services at {host}".format(host=one_host),
                                   self.status.get_process_percent() + self.status.calculate_process_interval(20, 2))
                        repo.restart_services(restart_services, one_host)
                        self.status.set_host_status(one_host, HostStatus.SUCCESS)
                    except RepositoryException as ex:
                        self.status.set_host_status(one_host, HostStatus.FAULT)
                        raise ex
                self.stage("Finish", 100)

            else:
                logger_server.info("Nothing has been changed")

            # Logging
            logger_server.info(
                "Deploy Event[{event_id}] done.".format(event_id=event_id))

            datetime_end = datetime.datetime.now()
            mongodb_client['deployment']['deploy_log'].insert({'event_id': payload.event_id,
                                                               'type': 'deploy',
                                                               'repo_name': self.repo.repo_name,
                                                               'result': "success",
                                                               'cost_time': str(datetime_end - datetime_start),
                                                               'createdTimeStamp': int(time.time())})

            mail_manager.send_success_mail(payload, self.repo.get_tag_info(payload.tag), datetime_start, datetime_end)

            # Check if exist waiting task to run
            self.status.lock_acquire()
            self.status.update_last_commit()

            if self.status.has_waiting_task():
                self.deploy(self.status.get_first_waiting_task())
                return

            # Change Status to Idle, Trick: Here will be reached once during one working list
            self.status.set_status(DeployStatus.IDLE)
            self.status.init_host_status()
            self.stage(None)
            self.status.update_last_release_tags()
            self.status.set_running_task(None)
            self.status.set_cancel_flag(False)
            self.status.set_backup_filename(None)
            self.status.set_package_filename(None)
            if _DEBUG:
                logger_server.debug("Status" + str(self.status.export_status()))

            self.status.lock_release()
        except DeployCancel as ex:
            datetime_end = datetime.datetime.now()
            mongodb_client['deployment']['deploy_log'].insert({'event_id': payload.event_id,
                                                               'type': 'deploy_cancel',
                                                               'result': 'success',
                                                               'createdTimeStamp': int(time.time())})
            mail_manager.send_cancel_success_mail(payload, self.repo.get_tag_info(payload.tag), datetime_start, datetime_end)

        except Exception as ex:
            exception_str = str(ex)
            stack_info = traceback.format_exc()
            mail_manager.send_error_mail(payload, self.repo.get_tag_info(payload.tag), datetime_start,
                                         stack_info)
            mongodb_client['deployment']['deploy_log'].insert({'event_id': payload.event_id,
                                                               'type': 'deploy',
                                                               'result': 'exception',
                                                               'exception': exception_str,
                                                               'trace': stack_info,
                                                               'createdTimeStamp': int(time.time()),
                                                               'status_snapshot': serialize_status(
                                                                   self.status.export_status())})
            try:
                self.rollback(payload)
                datetime_end = datetime.datetime.now()
                mongodb_client['deployment']['deploy_log'].insert({'event_id': payload.event_id,
                                                                   'type': 'deploy_rollback',
                                                                   'result': 'success',
                                                                   'exception': exception_str,
                                                                   'trace': stack_info,
                                                                   'createdTimeStamp': int(time.time()),
                                                                   'status_snapshot': serialize_status(
                                                                       self.status.export_status())})
                mail_manager.send_rollback_success_mail(payload, self.repo.get_tag_info(payload.tag), datetime_start,
                                                        datetime_end, stack_info)

            except Exception as rollback_ex:
                rollback_exception_str = str(rollback_ex)
                rollback_stack_info = traceback.format_exc()
                datetime_end = datetime.datetime.now()
                mongodb_client['deployment']['deploy_log'].insert({'event_id': payload.event_id,
                                                                   'type': 'deploy_rollback',
                                                                   'result': 'fail',
                                                                   'exception_original': exception_str,
                                                                   'trace_original': stack_info,
                                                                   'exception_rollback': rollback_exception_str,
                                                                   'trace_rollback': rollback_stack_info,
                                                                   'createdTimeStamp': int(time.time()),
                                                                   'status_snapshot': serialize_status(
                                                                       self.status.export_status())})
                mail_manager.send_rollback_fail_mail(payload, self.repo.get_tag_info(payload.tag), datetime_start,
                                                        datetime_end, stack_info, rollback_stack_info)


    def rollback(self, payload):
        try:
            event_id = payload.event_id
            head_commit = payload.head_commit
            repo = self.repo

            logger_server.info("Start rollback Event[{event_id}]...".format(event_id=event_id))

            # Change Status to Rollback and disable auto deployment
            self.status.lock_acquire()
            self.status.disable_auto_deploy()
            self.status.set_status(DeployStatus.ROLLBACK)
            self.status.init_host_status()
            self.status.lock_release()

            backup_package = self.status.get_backup_filename()
            release_package = self.status.get_package_filename()
            # adjust if has backup_package and release_package, before this stage need not deploy
            if backup_package and release_package:
                # Step 1.Get change files
                self.stage("Get change files", 20)
                try:
                    change_files = repo.get_change_files(self.status.get_last_commit(), head_commit)
                    if _DEBUG:
                        logger_server.debug("change files:" + str(change_files))
                except:
                    # May be pull failed so head_commit is not a valid object
                    change_files = []

                if change_files:
                    # Step 2.Get Services to restart
                    self.stage("Get Services to restart", 40)
                    restart_services = repo.get_service_to_restart(change_files)
                    if _DEBUG:
                        logger_server.debug("service to restart:" + str(restart_services))

                    # Step 3.Release backup package
                    self.stage("Release backup package", 50)
                    for one_host in self.status.get_hosts():
                        # Step 3.1 SYNC package
                        self.status.set_host_status(one_host, HostStatus.DEPLOYING)
                        if _DEBUG:
                            logger_server.debug("Rsync files to {host}".format(host=one_host))
                        self.stage("Rsync files to {host}".format(host=one_host),
                                   self.status.get_process_percent() + self.status.calculate_process_interval(30, 2))
                        self.repo.release(backup_package, one_host)

                        # Step 3.2.Restart Services
                        if _DEBUG:
                            logger_server.debug("Restart services at {host}".format(host=one_host))
                        self.stage("Restart services at {host}".format(host=one_host),
                                   self.status.get_process_percent() + self.status.calculate_process_interval(30, 2))
                        repo.restart_services(restart_services, one_host)
                        self.status.set_host_status(one_host, HostStatus.SUCCESS)
                else:
                    logger_server.info("Nothing has been changed")
            else:
                logger_server.info("Nothing need deploy")

            # Step 5/Step 1.Git Reset
            self.stage("Git Reset", 90)
            repo.reset(self.status.get_last_commit())

            # Logging
            logger_server.info(
                "Rollback Event[{event_id}] done.".format(event_id=event_id))

            # Change Status to Idle
            self.status.lock_acquire()
            self.status.set_status(DeployStatus.IDLE)
            self.status.init_host_status()
            self.stage(None)
            self.status.update_last_release_tags()
            self.status.set_running_task(None)
            self.status.set_cancel_flag(False)
            self.status.set_backup_filename(None)
            self.status.set_package_filename(None)
            self.status.update_last_commit()
            if _DEBUG:
                logger_server.debug("Status" + str(self.status.export_status()))
            self.status.lock_release()
        except Exception as ex:
            mongodb_client['deployment']['deploy_log'].insert({'event_id': payload.event_id,
                                                               'type': 'rollback',
                                                               'result': 'fail',
                                                               'exception': str(ex),
                                                               'createdTimeStamp': int(time.time()),
                                                               'status_snapshot': serialize_status(
                                                                   self.status.export_status())})
            raise ex


class DeployManagerFactory():
    @staticmethod
    def create_deploy_manager(repo_name, repo_config):
        if repo_config['STRATEGY'] == DeployStrategy.TEST_MODE:
            return GitBaseDeployManager(repo_name, repo_config)
        elif repo_config['STRATEGY'] == DeployStrategy.PRO_MODE:
            return PackageBaseDeployManager(repo_name, repo_config)


dms = {}

for repo_name, repo_config in _REPOSITORY_CFG.items():
    dms[repo_name] = DeployManagerFactory.create_deploy_manager(repo_name, repo_config)