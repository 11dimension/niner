#!/usr/bin/env python3

# Safe Redis Client for avoid 'too many clients' error under a multi-threaded environment
# Compatible with redis.StrictRedis

# Build By CCoffee 20140915 1738, caofei@baixing.com
# Consolidated By CCoffee 20140915, caofei@baixing.com

import os
import datetime
import time
import threading
# import yaml
from config import REDIS as _REDIS
import redis

class SafeRedisClient(object):
    REDIS_DB_CONN_POOLS = {}

    def __init__(self, host='localhost', port=6379, db=0, **kwargs):
        """
        得到一个与 StrictRedis 兼容的 redis 客户端，具备连接数限制能力，以及对可恢复的错误的自动重试能力；

        一个 host + port + db 的组合，对应一个连接池，连接数的限制是在本进程内（俗称“一个 main 里面”），所以对于一个进程内的多线程
        导致的 too many clients 错误，是能够有效避免的；

        但即便是限制了每个组合对应的连接数，但在多进程情况下，整体连接数还是可能超过 redis server 的最大连接数；

        一个 host + port + db 的组合，其最大连接数 pool_max_connections 在第一次指定的时候的取值，是不能被修改的，修改也无效；
        经过测试，在密集使用 redis 的环境中，一个 host + port + db 的组合，pool_max_connections 取 3 至 5 已经足够，因为 redis
        本身是单线程处理请求的，过大的并发量没有意义；

        :param host: 目标 redis 服务器的机器名或地址，默认是 localhost；
        :param port: 目标 redis 服务器的端口，默认是 6379；
        :param db: 目标 redis 服务器的数据库编号，默认是 0；
        :param kwargs: 可选参数：
            redis_operation_timeout_sec: 每一次 redis 操作允许的等待时间，如果操作在此时间内未返回，会被判为失败；默认是 10 秒；
            pool_max_connections: 在当前程序范围内，最多允许同时连接到目标服务器的连接数；默认是 3 个连接；
            下面是“软错误”重试的时间间隔，连接池最大连接数达到时，会等待一个很短的时间后，自动重新连接：
            error_pool_full_wait_sec: 在当前程序范围内，如果同时连接到目标服务器的连接数过多了，则等待多久重试；默认是 0.1 秒；
            下面是“硬错误”重试的时间间隔，由于咱们采用了 supervisor 等监控工具，所以即便是硬错误发生，也是可以被自动恢复的：
            error_server_full_wait_sec: 如果目标服务器已经处于 too many clients 的状态，则等待多久重试；默认是 2 秒；
            error_server_port_dead_wait_sec: 如果目标服务器无法连通（例如服务器当掉），则等待多久重试；默认是 5 秒；
            error_host_unknown_wait_sec: 如果到目标服务器之间的网络出现错误（例如找不到服务器地址），则等待多久重试；默认是 20 秒；
            error_hard_retry_limit: 上述“硬错误”发生时，连续重试多少次之后，才被认定是操作失败；默认是 100 次；
        :return: 一个与 StrictRedis 兼容的 redis 客户端实例；
        """
        # general connection pooling parameters
        self.redis_operation_timeout_sec = kwargs['redis_operation_timeout_sec'] \
            if 'redis_operation_timeout_sec' in kwargs else 10
        self.pool_max_connections = kwargs['pool_max_connections'] \
            if 'pool_max_connections' in kwargs else 3
        # soft error caused by connection pool limit
        self.error_pool_full_wait_sec = kwargs['error_pool_full_wait_sec'] \
            if 'error_pool_full_wait_sec' in kwargs else 0.1
        # hard error caused by server or network error
        self.error_server_full_wait_sec = kwargs['error_server_full_wait_sec'] \
            if 'error_server_full_wait_sec' in kwargs else 2
        self.error_server_port_dead_wait_sec = kwargs['error_server_port_dead_wait_sec'] \
            if 'error_server_port_dead_wait_sec' in kwargs else 5
        self.error_host_unknown_wait_sec = kwargs['error_host_unknown_wait_sec'] \
            if 'error_host_unknown_wait_sec' in kwargs else 20
        self.error_hard_retry_limit = kwargs['error_hard_retry_limit'] \
            if 'error_hard_retry_limit' in kwargs else 100

        conn_pool_key = (host, port, db)
        redis_conn_pool = None
        if conn_pool_key in SafeRedisClient.REDIS_DB_CONN_POOLS:
            redis_conn_pool = SafeRedisClient.REDIS_DB_CONN_POOLS[conn_pool_key]
        else:
            redis_conn_pool = redis.ConnectionPool(host=host, port=port, db=db, retry_on_timeout=True,
                                                   socket_timeout=self.redis_operation_timeout_sec,
                                                   max_connections=self.pool_max_connections)
            SafeRedisClient.REDIS_DB_CONN_POOLS[conn_pool_key] = redis_conn_pool
        self.redis_client = redis.StrictRedis(connection_pool=redis_conn_pool)

    def __getattr__(self, attr_name):
        def func(*args, **kwargs):
            result = None
            exec_finish = False
            hard_error_retry = 0
            while not exec_finish:
                try:
                    redis_command = getattr(self.redis_client, attr_name)
                    result = redis_command(*args, **kwargs)
                    exec_finish = True
                except AttributeError:
                    raise
                except (redis.ConnectionError, redis.ResponseError, redis.TimeoutError) as error:
                    error_msg = str(error).lower().strip()
                    if error_msg.startswith('too many connections'):    # Redis connection pool full (soft error)
                        time.sleep(self.error_pool_full_wait_sec)
                    elif error_msg.startswith('max number of clients'):  # Redis server too many clients
                        time.sleep(self.error_server_full_wait_sec)
                        hard_error_retry += 1
                    elif error_msg.startswith('error 111 '):    # Connection refused, redis is dead, waiting for restart
                        time.sleep(self.error_server_port_dead_wait_sec)
                        hard_error_retry += 1
                    elif error_msg.startswith('error -2 '):     # Host name or service not known
                        time.sleep(self.error_host_unknown_wait_sec)
                        hard_error_retry += 1
                    else:
                        raise
                except Exception:
                    raise
                if hard_error_retry >= self.error_hard_retry_limit:
                    exec_finish = True  # hard error limit reached, force return None
            return result
        return func

redis_manager = SafeRedisClient(_REDIS['HOST'],_REDIS['PORT'],_REDIS['DBID'])

# --- 下列为测试用代码 ---

def do_redis_test_thread(thread_id, redis_index, redis_client):
    print("Thread {0} {1} started...".format(thread_id, redis_index))
    for i in range(0, 500):
        # print("thread id = {0} , redis client id = {1}".format(thread_id, id(redis_client)))
        rdb_available = False
        while not rdb_available:
            redis_client.lpush('test_key_list', 'wahahaha_{0}_{1}_{2}'.format(thread_id, redis_index, i))
            redis_client.incr('test_key_int', amount=redis_index + 1)
            rdb_available = True
    print("Thread {0} {1} finished...".format(thread_id, redis_index))
    return


if __name__ == '__main__':

    start_stamp = "#### Test Start {0} ####".format(datetime.datetime.now())
    raw_redis_client = redis.StrictRedis()
    safe_redis_client = SafeRedisClient()
    raw_redis_clients = [
        redis.StrictRedis(host='localhost', port=6380, db=0),
        redis.StrictRedis(host='localhost', port=6381, db=0),
        redis.StrictRedis(host='localhost', port=6382, db=0)
    ]
    safe_redis_clients = [
        SafeRedisClient(host='localhost', port=6380, db=0),
        SafeRedisClient(host='localhost', port=6381, db=0),
        SafeRedisClient(host='localhost', port=6382, db=0)
    ]
    threads = []
    for i in range(0, 50):
        for redis_index in range(0, 3):
            thread = threading.Thread(target=do_redis_test_thread,
                                      args=(i, redis_index, safe_redis_clients[redis_index],))
            thread.start()
            threads.append(thread)
    threads_all_end = False
    while not threads_all_end:
        threads_all_end = True
        for thread in threads:
            if thread.is_alive():
                threads_all_end = False
                break
        if not threads_all_end:
            time.sleep(1)
    end_stamp = "#### Test End {0} ####".format(datetime.datetime.now())
    print(start_stamp)
    print(end_stamp)
    print('OK')
