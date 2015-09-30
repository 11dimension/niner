__author__ = 'magus0219'


class DeployStrategy():
    TEST_MODE = 1
    PRO_MODE = 2


class DeployStatus:
    RUNNING = 1
    ROLLBACK = 2
    IDLE = 3


class HostStatus:
    NORMAL = 1
    DEPLOYING = 2
    SUCCESS = 3
    FAULT = 4
