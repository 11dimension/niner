__author__ = 'magus0219'


def retry(times):
    def decorator(func):
        def wrapper(*args, **kwargs):
            run_times = 0
            succeed = False
            while run_times <= times and succeed == False:
                try:
                    func(*args, **kwargs)
                    succeed = True
                except Exception as ex:
                    if run_times < times:
                        run_times += 1
                    else:
                        raise ex

        return wrapper

    return decorator