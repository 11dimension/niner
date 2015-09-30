__author__ = 'magus0219'
import uuid


class PayLoad():
    def __init__(self, event_id, event_type, repository_name, is_tag, is_branch, head_commit, username, src,
                 branch=None, tag=None):
        self.event_id = event_id
        self.event_type = event_type
        self.repository_name = repository_name
        self.is_tag = is_tag
        self.is_branch = is_branch
        self.head_commit = head_commit
        self.branch = branch
        self.tag = tag
        self.username = username
        self.src = src

    @staticmethod
    def create_by_payload(event_id, event_type, payload):
        repository_name = payload['repository']['name']
        # tag or branch push?
        try:
            is_tag = payload['ref'].split('/')[1] == 'tags'
        except:
            is_tag = False
        try:
            is_branch = payload['ref'].split('/')[1] == 'heads'
        except:
            is_branch = False

        if is_branch:
            tag = None
            branch = payload['ref'].split('/')[-1]
        elif is_tag:
            branch = None
            tag = payload['ref'].split('/')[-1]

        username = payload['pusher']['name']

        if not payload['deleted']:
            return PayLoad(event_id, event_type, repository_name, is_tag, is_branch, payload['head_commit']['id'], username,
                           "webhook", branch, tag)
        else:
            return None

    @staticmethod
    def create_by_rollback(commit_id, tag, repository_name, username):
        event_id = str(uuid.uuid4())
        event_type = 'rollback'
        is_tag = True
        is_branch = False
        tag = tag
        return PayLoad(event_id, event_type, repository_name, is_tag, is_branch, commit_id, username, "手工回滚", tag=tag)

    def __repr__(self):
        return str(self.event_id)
