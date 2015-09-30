__author__ = 'magus0219'


def remove_quota_pair(one_string):
    if len(one_string) > 1 and (one_string[0] == one_string[-1] == '"' or one_string[0] == one_string[-1] == "'"):
        return one_string[1:-1]
    else:
        return one_string
