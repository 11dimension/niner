__author__ = 'magus0219'
from config import DEBUG as _DEBUG, SERVER_CONFIG as _SERVER_CFG
from utils.decorator import retry
from utils.string_util import remove_quota_pair
import subprocess
import traceback
import uuid
import re
import os
import shutil
import logging
import datetime
import time
from collections import OrderedDict
from core.tag import Tag
import shlex

logger_server = logging.getLogger("DeployServer.Repository")


def release_tag_cmp(release_tag):
    nums = release_tag[1:].split('.')
    major = int(nums[0])
    minor = int(nums[1])
    patch = int(nums[2])

    return major * 10000 * 10000 + minor * 10000 + patch


class RepositoryException(Exception):
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return self.msg


class Repository():
    def __init__(self, repo_name, repo_config):
        """Initialize this repository

        Here set static configurations which will not change at runtime.
        """
        self.repo_name = repo_name
        self.git_path = repo_config['GIT_PATH']
        self.deploy_path = repo_config.get('DEPLOY_PATH', None)
        self.package_path = repo_config.get('PACKAGE_PATH', None)
        self.backup_path = repo_config.get('BACKUP_PATH', None)
        self.strategy = repo_config['STRATEGY']
        self.branch = repo_config['BRANCH']
        self.services = repo_config['SERVICES']
        self.service_pri = repo_config['SERVICES_PRI']
        self.hosts_roles = repo_config['HOSTS']
        self.post_actions = repo_config['POST_ACTIONS']
        self.hosts = sorted(list(repo_config['HOSTS'].keys()))

        self._gen_service_index(repo_config)

    def get_commit_tag(self, commit_id):
        """Get tag of this commit

        :param commit_id: commit
        :return: tag object
        """
        command = "git describe --abbrev=0 --exact-match {commit}".format(commit=commit_id)

        logger_server.info("Get tag of commit[CMD:{cmd}]...".format(cmd=command))

        self.cwd(self.git_path)

        try:
            tag_name = self._run_shell_command(command=command)
        except RepositoryException as ex:
            # commit not map to annotation tag
            return None

        return self.get_tag_info(tag_name[:-1])


    def _gen_service_index(self, repo_config):
        """Generate index from service to host

        Index format:
           {
                service1: [host1,host2...],
                service2: [host1]...
            }
        :param repo_config: config of repository
        :return:
        """
        self.service_index = {}

        role = repo_config['HOST_ROLE']
        hosts_roles = self.hosts_roles

        services = {}

        # services[host] = [service1, service2...]
        for host in self.hosts:
            for one_role in hosts_roles[host]:
                if host not in services:
                    services[host] = []
                services[host].extend(role[one_role])
        for host in services.keys():
            services[host] = set(services[host])

        for host in services.keys():
            for one_service in services[host]:
                if one_service not in self.service_index:
                    self.service_index[one_service] = []
                self.service_index[one_service].append(host)

        if _DEBUG:
            logger_server.debug("service_index:" + str(self.service_index))

    def _need_restart(self, host, service):
        """Adjust if host need restart this service by service index

        :param host: hostname
        :param service: servicename
        :return:
        """
        if host in self.service_index[service]:
            return True
        else:
            return False

    def __hash__(self):
        return hash(self.repo_name)

    def _run_shell_command(self, command, cwd=None):
        """Inner method to run a shell command

        Run a shell command described in param command and redirect stdout and stderr to a temp text file which
        content will be returned if succeed, else the content will be contained in a RepositoryException raised.

        :param command: content of a shell command.
        :return: stdout/stderr content
        :raise: RepositoryException if failed
        """
        success = True

        # command = command.split(' ')

        # # remove quota pair
        # for i in range(len(command)):
        #     command[i] = remove_quota_pair(command[i])

        command = shlex.split(command)

        tmp_filename = '/tmp/' + str(uuid.uuid4())

        with open(tmp_filename, 'w', encoding='utf-8') as w_tmpfile:
            kwargs = {
                'args': command,
                'stdout': w_tmpfile,
                'stderr': w_tmpfile
            }
            if cwd:
                kwargs['cwd'] = cwd
            return_code = subprocess.call(**kwargs)
            if return_code > 0:
                success = False

        with open(tmp_filename, 'r', encoding='utf-8') as r_tmpfile:
            std_content = r_tmpfile.read()

        os.remove(tmp_filename)

        if not success:
            raise RepositoryException(std_content)
        else:
            return std_content

    def handle_post_actions(self):
        """Hook to handle post actions

        """
        if self.post_actions:
            logger_server.info("Handle post actions...")
            for one_action in self.post_actions:
                logger_server.info("Handle post actions {action}".format(action=one_action))
                try:
                    self._run_shell_command(one_action['cmd'], one_action['cwd'])
                except Exception as ex:
                    logger_server.info("Fail to execute post action: {action}".format(action=one_action))
                    raise ex

    def cwd(self, path=None):
        """Change current work directory

        :param path: Target directory to change, using git_path if None
        :return:
        """
        if not path:
            path = self.git_path
        try:
            if os.getcwd() != path:
                logger_server.info("Change current dir to {path}...".format(path=path))
                os.chdir(path)
        except Exception as ex:
            logger_server.info("Fail to change current dir to {path}".format(path=path))
            raise RepositoryException(traceback.print_exc())

    def clean(self):
        """Clean git work directory

        Cleaning includes two parts:
        First files not in git version control will be removed.
        Second files have been modified but not committed will be reverted.

        :return:
        """
        command1 = "git clean -f"
        command2 = "git reset --hard HEAD"

        logger_server.info("Clean files not in version control[CMD:{cmd}]...".format(cmd=command1))

        self.cwd(self.git_path)

        rst = self._run_shell_command(command=command1)

        logger_server.info("Clean modified files in version control[CMD:{cmd}]...".format(cmd=command2))
        rst = self._run_shell_command(command=command2)

    @retry(times=3)
    def fetch(self):
        """Fetch data

        Fetch data from remote

        :return: pull content text
        """
        command = "git fetch origin"

        logger_server.info("Fetch data from github[CMD:{cmd}]...".format(cmd=command))

        self.cwd(self.git_path)

        fetch_content = self._run_shell_command(command=command)

        if _DEBUG:
            logger_server.debug("fetch_content:" + fetch_content)

        return fetch_content

    @retry(times=3)
    def pull(self):
        """Pull data

        Pull data from remote master branch

        :return: pull content text
        """
        command = "git pull --rebase origin " + self.branch

        logger_server.info("Pull data from github[CMD:{cmd}]...".format(cmd=command))

        self.cwd(self.git_path)

        pull_content = self._run_shell_command(command=command)

        if _DEBUG:
            logger_server.debug("pull_content:" + pull_content)

        return pull_content

    def reset(self, commit):
        """Reset git head to commit

        :param commit: commit id
        :return:
        """
        command = "git reset --hard {commit}".format(commit=commit)

        logger_server.info("Reset to Commit {commit} [CMD:{cmd}]...".format(commit=commit, cmd=command))

        self.cwd(self.git_path)

        self._run_shell_command(command=command)

    def get_change_files(self, start_commit, end_commit):
        """Analyze commit range and export names of changed files

        :param start_commit: commit str
        :param end_commit: commit str
        :return: list of names of change files or none
        """
        command = "git diff --name-only {start} {end}".format(start=start_commit, end=end_commit)

        logger_server.info(
            "Get change files from {start}...{end} [CMD:{cmd}]...".format(start=start_commit, end=end_commit,
                                                                          cmd=command))

        self.cwd(self.git_path)

        change_files = []

        if start_commit is not None and end_commit is not None:
            change_content = self._run_shell_command(command=command)

        for one_file in change_content.split('\n'):
            change_files.append(one_file)
        # reduce 1 more blank line
        change_files = change_files[:-1]

        if change_files:
            return change_files
        else:
            return None


    def get_last_commit(self):
        """Get last commit id

        :return: commit id
        """
        command = "git log -n 1 --oneline"

        logger_server.info("Get last commit id [CMD:{cmd}]...".format(cmd=command))

        self.cwd(self.git_path)

        last_commit = self._run_shell_command(command=command)

        return last_commit.split(' ')[0]

    def get_last_release_tags(self):
        """Get last release tags and parse tag to get tag object

        We only recognize annotation tag here, example of output of git show tagname here:
        ================================================
        tag r0.0.3
        Tagger: Arthur.Qin <magus0219@gmail.com>
        Date:   Wed May 6 11:42:55 2015 +0800

        release3

        commit 04591b7527b85182dc517e1068e4cc94bd7d38d4
        Merge: 32eff1d 9d9b243
        Author: Arthur.Qin <magus0219@gmail.com>
        Date:   Wed May 6 10:55:19 2015 +0800

            Merge pull request #6 from baixing/master

            merger baixing/master
        ================================================
        :return: list of tag object
        """
        command = 'git tag -l "r*.*.*"'

        logger_server.info("Get last release tags [CMD:{cmd}]...".format(cmd=command))

        self.cwd(self.git_path)

        tags = self._run_shell_command(command=command)

        if _DEBUG:
            logger_server.debug("Get release tags: {tags}".format(tags=tags))

        tag_list = tags.split('\n')
        # remove last blank line
        tag_list = tag_list[:-1]
        tag_list.sort(key=release_tag_cmp, reverse=True)

        tags = []
        for i in range(_SERVER_CFG['TAG_LIST_SIZE']):
            if i + 1 <= len(tag_list):
                one_tag = tag_list[i]
                tag = self.get_tag_info(one_tag)
                if tag:
                    tags.append(tag)

        return tags

    def get_tag_info(self, tag_name):
        """Get tag object from tag_name

        :param tag_name:
        :return:
        """
        command = "git show {tagname}".format(tagname=tag_name)
        logger_server.info("Get tag info of {tagname},[CMD:{cmd}]...".format(tagname=tag_name, cmd=command))

        self.cwd(self.git_path)
        tag_info = self._run_shell_command(command=command)
        tag = Tag.create_by_tag_info(tag_info)

        return tag


    def install_pkg(self, files):
        """Install packages depend on different package files

        :param files:
        :return:
        """
        for one_file in files:
            dir_name = one_file.split('/')[:-1]
            filename = one_file.split('/')[-1]

            # adjust file exist
            if not os.path.exists(one_file):
                logger_server.info("{file} not exist.".format(file=one_file))
            else:
                if filename == "package.json":
                    abs_dir = self.git_path + os.sep.join(dir_name)
                    command = "npm install"
                    self.cwd(abs_dir)
                    logger_server.info(
                        "Install node package in {file}[CMD:{cmd}]...".format(file=abs_dir + os.sep + filename,
                                                                              cmd=command))
                    # self._run_shell_command(command=command)
                elif filename == "requirements.txt":
                    command = "pip3 install -r {file}".format(file=self.git_path + one_file)
                    logger_server.info(
                        "Install python package in {file}[CMD:{cmd}]...".format(file=self.git_path + one_file,
                                                                                cmd=command))
                    self._run_shell_command(command=command)

    def restart_services(self, services, host):
        """Restart services

        Services has own priority, which we used to adjust which to restart first.

        The lower pri number is, the higher pri this service is.

        :param services: List of services to restart
        :return:
        """
        if not services:
            logger_server.info("Nothing to restart.")
        else:
            # Order services by pri.
            order_services = {}
            for one_service in services:
                pri = self.service_pri[one_service]
                order_services[one_service] = pri
            order_services = OrderedDict(sorted(order_services.items(), key=lambda t: t[1]))

            for one_service in order_services.keys():
                self.restart_service(one_service, host)


    @retry(3)
    def restart_service(self, service, host):
        """Restart one service

        Here service is identified as supervisor program name. For example: pyds:pyds_3355

        After restart we also check service status to confirm it is really running

        :param service: service name
        :param host: hostname
        :return:
        """
        if self._need_restart(host, service):
            command = "supervisorctl -s {server_url} restart {service}".format(
                server_url="http://{hostname}:9001".format(hostname=host), service=service)
            logger_server.info("Restart service {service} at {hostname}[CMD:{cmd}]...".format(service=service,
                                                                                              cmd=command,
                                                                                              hostname=host))
            self._run_shell_command(command=command)

            # sleep to restart
            time.sleep(5)

            self._check_service_running(service, host)
        else:
            logger_server.info("{hostname} do not need start service {service}".format(service=service,
                                                                                       hostname=host))

    def _check_service_running(self, service, host):
        """Check service

        Here service is identified as supervisor program name. For example: pyds:pyds_3355

        :param service: service to restart
        :param host: hostname
        :return:
        """
        command = "supervisorctl -s {server_url} status {service}".format(
            server_url="http://{hostname}:9001".format(hostname=host), service=service)
        logger_server.info("Check service {service} at {hostname} [CMD:{cmd}]...".format(service=service,
                                                                                         cmd=command,
                                                                                         hostname=host))
        result_content = self._run_shell_command(command=command)
        result = re.match(".+RUNNING.+", result_content)
        # Status is not running
        if not result:
            logger_server.info("Fail to restart {service} at {host}".format(service=service, host=host))
            raise RepositoryException("Fail to restart {service} at {host}".format(service=service, host=host))


    def backup_deploy_dir(self):
        """Backup deploy directory

        """
        now = datetime.datetime.now()
        target_filename = self.backup_path + '{repo_name}_{time_str}.tar.gz'.format(repo_name=self.repo_name,
                                                                                    time_str=now.strftime(
                                                                                        "%Y_%m_%d_%H_%M_%S"))

        self.cwd(self.deploy_path)
        command = "tar -zcvf {target_filename} {src_path} --exclude='{src_path}/.git'".format(
            target_filename=target_filename,
            src_path=self.repo_name)

        logger_server.info("Backup deploy path [CMD:{cmd}]...".format(cmd=command))

        self._run_shell_command(command=command)

        return target_filename


    def tar_git_dir(self, tag_name):
        """Release git directory with a tag without .git directory

        """
        target_filename = self.package_path + '{repo_name}_{tag_name}.tar.gz'.format(repo_name=self.repo_name,
                                                                                     tag_name=tag_name)
        # if file exist, do not tar again
        if not os.path.exists(target_filename):
            self.cwd(self.git_path)
            self.cwd('..')
            command = "tar -zcvf {target_filename} {src_path} --exclude='{src_path}/.git'".format(
                target_filename=target_filename,
                src_path=self.repo_name)

            logger_server.info("Tar git path [CMD:{cmd}]...".format(cmd=command))

            self._run_shell_command(command=command)

        return target_filename

    def release(self, release_package, host):
        """Release release_file to deploy_path

        :param release_package: package to release
        :param host: hostname to release
        :return:
        """

        # Delete first, ignore error if not exsit.
        shutil.rmtree("/tmp/{repo_name}".format(repo_name=self.repo_name), ignore_errors=True)

        # TODO here i just untar package every time, to be optimized.
        command = "tar -zxvf {release_package} -C /tmp/".format(release_package=release_package)

        logger_server.info("Decompress release_package [CMD:{cmd}]...".format(cmd=command))

        self._run_shell_command(command=command)

        command = "rsync -a --delete /tmp/{repo_name} {desc}".format(repo_name=self.repo_name,
                                                                     desc="deploy@{host}:{deploy_path}".format(
                                                                         host=host, deploy_path=self.deploy_path))

        logger_server.info("Release to deploy directory...".format(cmd=command))

        self._run_shell_command(command=command)

        shutil.rmtree("/tmp/{repo_name}".format(repo_name=self.repo_name), ignore_errors=True)

        return


    def get_commits_range(self, pull_content):
        """Analyze commit range from output of git pull

        :param pull_content: output of git pull
        :return: start_commit,end_commit
        """
        pattern = r'^Updating (\w{7})\.\.(\w{7})'

        for one_line in pull_content.split('\n'):
            match = re.match(pattern, one_line)
            if match:
                start_commit = match.group(1)
                end_commit = match.group(2)
                return start_commit, end_commit

        return None, None


    def get_pkg_to_install(self, files):
        """Filter package files from changed file names

        :param files: changed file names
        :return: package file names relative to git root
        """
        pkg_list_file_names = ['package.json', 'requirements.txt']
        pkg_list_files = []

        for one_file in files:
            if one_file.split('/')[-1] in pkg_list_file_names:
                pkg_list_files.append(one_file)
        return pkg_list_files


    def get_service_to_restart(self, files):
        """Analyze file names to get services to restart

        Split first directory of relative file names as projects
        Using configuration to map projects to service ids

        :param files: relative files to git repository path
        :return: service ids
        """
        projects = []
        service_to_restart = []

        for one_file in files:
            projcet = one_file.split('/')[0]
            projects.append(projcet)

        for one_project in set(projects):
            if one_project in self.services:
                services = self.services[one_project]
                if type(services) == list:
                    for one_service in services:
                        service_to_restart.append(one_service)
                elif type(services) == str:
                    service_to_restart.append(services)
            # If any file will trigger restart this service, for flat structure of project
            elif '*' in self.services:
                service_to_restart.append(self.services['*'])

        return set(service_to_restart)