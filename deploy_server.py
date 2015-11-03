__author__ = 'magus0219'

import logging.config
import tornado.ioloop
import tornado.web
import argparse
import os

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Deploy Server.')
    parser.add_argument('-e', '--env', choices=['production', 'test', 'development'], default='test',
                        help='Environment String to decide which config file to load')
    parser.add_argument('-p', '--port', type=int, default=None, help='Port to listen')
    args = parser.parse_args()

    # load config
    import config

    config.load_config_by_env(args.env)

    from config import SERVER_CONFIG as _SERVER_CFG, LOGGING as _LOGGING_CFG

    logging.config.dictConfig(_LOGGING_CFG)
    logger_server = logging.getLogger("DeployServer")
    logger_server.info('Loading configuration file [{env}.py] done'.format(env=args.env))

    # decide listen port
    if args.port:
        listen_port = args.port
    else:
        listen_port = _SERVER_CFG["PORT"]

    logger_server.info('Deploy Server started at port: ' + str(listen_port))
    logger_server.info('Connected Mongodb at {ip}:{port}'.format(ip=_SERVER_CFG["MONGO_HOST"],
                                                                 port=_SERVER_CFG["MONGO_PORT"]))

    dir_path = os.path.dirname(os.path.realpath(__file__))

    try:
        from urls import URLS

        application = tornado.web.Application(URLS,
                                              template_path=dir_path + os.sep + 'templates',
                                              compiled_template_cache=False,
                                              cookie_secret='9snq23jd0-9;',
                                              login_url='/deploy/login')
        application.listen(listen_port)
        tornado.ioloop.IOLoop.instance().start()
    except KeyboardInterrupt as e:
        logger_server.info("DeployServer Stopped...")
    except Exception as e:
        logger_server.exception(str(e))
