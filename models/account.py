__author__ = 'magus0219'

from utils.mongo_handler import mongodb_client
from bson.objectid import ObjectId


class Account():
    def __init__(self, username, password, email, role, user_id=None):
        self.user_id = user_id  # string
        self.username = username
        self.password = password
        self.email = email
        self.role = role

    def save(self):
        if not self.user_id:
            mongodb_client['deployment']['account'].insert({
                'username': self.username,
                'password': self.password,
                'email': self.email,
                'role': self.role
            })
        else:
            mongodb_client['deployment']['account'].update(
                {'_id': ObjectId(self.user_id)},
                {'username': self.username,
                 'password': self.password,
                 'email': self.email,
                 'role': self.role}
            )

    def has_role(self, role):
        return role in self.role

    @staticmethod
    def find_by_user_id(user_id):
        rst = mongodb_client['deployment']['account'].find_one({
            '_id': ObjectId(user_id)
        })
        return Account(rst['username'], rst['password'], rst['email'], rst['role'], str(rst['_id']))