__author__ = 'magus0219'

import logging

import pymongo
import copy

from config import SERVER_CONFIG as _SERVER_CFG


logger_server = logging.getLogger("DeployServer")

try:
    mongodb_client = pymongo.MongoClient(host=_SERVER_CFG["MONGO_HOST"], port=_SERVER_CFG["MONGO_PORT"])
    mongodb_client['deployment'].authenticate(_SERVER_CFG["MONGO_USER"], _SERVER_CFG["MONGO_PWD"])
except Exception as e:
    logger_server.info("MongoDB cannot connect, Please check...")


def serialize_status(status):
    """Rewrite custom object in status dictionary to string for writing to mongo db

    :param status: dictionary of status
    :return:
    """
    copy_status = copy.deepcopy(status)
    copy_status['task_running'] = repr(copy_status['task_running'])
    for i in range(len(copy_status['task_waiting'])):
        copy_status['task_waiting'][i] = repr(copy_status['task_waiting'][i])

    for i in range(len(copy_status['last_tags'])):
        copy_status['last_tags'][i] = repr(copy_status['last_tags'][i])

    copy_status['last_commit_tag'] = repr(copy_status['last_commit_tag'])

    return copy_status