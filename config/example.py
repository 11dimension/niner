import os
from utils.enums import DeployStrategy

DEBUG = False

# Server primary configuration
SERVER_CONFIG = {
    # Port of service
    "PORT": 7722,   
    # Mongo Section
    "MONGO_HOST": "192.168.100.1",
    "MONGO_PORT": 27017,
    "MONGO_USER": "superuser",
    "MONGO_PWD": "******",
    # Resource
    "RESOURCE_DIR": "./resource",
    # Log Section
    "LOG_DIR": "/log/",
    "LOG_FILE_NAME": "deploy_server",
    # Biz Section
    "TAG_LIST_SIZE": 10  # size of tag list in admin interface
}

# Configuration of Redis
REDIS = {
    "HOST": "192.168.100.5",
    "PORT": 6379,
    "DBID": 3
}

# Webhook secret of github 
GITHUB = {
    "SECRET": "********"
}

# SMTP to send email
EMAIL = {
    "SMTP": "smtp.exmail.qq.com",
    "USER": "zqhua@zqhua.cn",
    "PASSWORD": "********"
}

# ! Configurations of Repos. Using list if watching more than one repos
REPOSITORY = {
    "repoA": {  # repo name
        "GIT_PATH": "/home/deploy/_github/repoA/", # path where repo resides in, needed in both production/test mode
        "DEPLOY_PATH": "/home/deploy/_online/", # path where deploy to, needed in production mode
        "PACKAGE_PATH": "/home/deploy/_package/", # path where packages save to, need in production mode
        "BACKUP_PATH": "/home/deploy/_backup/", # path where backup tar file save to, need in production mode
        "STRATEGY": DeployStrategy.PRO_MODE, # mode switcher
        "BRANCH": "master", # branch filter
        # services should restart when files have changed, key is first child directory of repo root('*' matches anything else like finally), value is service name in supervisor, 'None' means no service need restart, also support list if multi services need restart.
        "SERVICES": { 
            "admin": "admin:admin_3377",
            "api": "api:api_2919",
            "dw": None,
            "config": ["mf2:mf2_3333", "poster:poster_2234", "telesales:telesales_3335"],
            "*": "ts:ts_3335",
        },
        # services priority as restart order, Key is service name in supervisor, value is priority level, little numbers have higher priorities. 
        "SERVICES_PRI": {
            "admin:admin_3377": 3,
            "api:api_2919": 1,
            "poster:poster_2234": 2,
            "pyds:pyds_3355": 2,
            "telesales:telesales_3335": 3,
            "mf2:mf2_3333": 2,
        },
        # map from hostname to roles of host
        "HOSTS": {
            "zqhua01": ["web", "data"],
            "zqhua02": ["web", "data", "weixin"]
        },
        # map from host role to service names
        "HOST_ROLE": {
            "web": [
                "admin:admin_3377",
                "api:api_2919",
                "mf2:mf2_3333",
                "telesales:telesales_3335"
            ],
            "data": [
                "pyds:pyds_3355",
            ],
        },
        # Command Strings to run after NPM or package install
        "POST_ACTIONS": [
            {"cmd": "npm start", "cwd": "/home/deploy/foo"},
        ],
        # Exclude filename which contains file pattern should not rsync
        "EXCLUDE_FILENAME": None
    }
}

LOGGING = {
    "version": 1,
    "formatters": {
        "verbose": {
            "format": "[%(levelname)s][%(module)s-%(lineno)d][thread-%(thread)d]%(asctime)s %(name)s:%(message)s"
        }
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "verbose"
        },
        "file": {
            "level": "DEBUG",
            "class": "logging.handlers.TimedRotatingFileHandler",
            "when": "D",
            "formatter": "verbose",
            "filename": SERVER_CONFIG["LOG_DIR"] + os.sep + SERVER_CONFIG["LOG_FILE_NAME"] + '.log'
        },
        "err_file": {
            "level": "ERROR",
            "class": "logging.handlers.TimedRotatingFileHandler",
            "when": "D",
            "formatter": "verbose",
            "filename": SERVER_CONFIG["LOG_DIR"] + os.sep + SERVER_CONFIG["LOG_FILE_NAME"] + '.err'
        },
        "t_access_file": {
            "level": "ERROR",
            "class": "logging.handlers.TimedRotatingFileHandler",
            "when": "D",
            "formatter": "verbose",
            "filename": SERVER_CONFIG["LOG_DIR"] + os.sep + 'tornado.access'
        },
        "t_error_file": {
            "level": "ERROR",
            "class": "logging.handlers.TimedRotatingFileHandler",
            "when": "D",
            "formatter": "verbose",
            "filename": SERVER_CONFIG["LOG_DIR"] + os.sep + 'tornado.error'
        }
    },
    "loggers": {
        "DeployServer": {
            "handlers": ["console", "file", "err_file"],
            "propagate": False,
            "level": "DEBUG"
        },
        "tornado.access": {
            "handlers": ["t_access_file"],
            "propagate": False
        },
        "tornado": {
            "handlers": ["t_error_file"],
            "propagate": False
        }
    }

}