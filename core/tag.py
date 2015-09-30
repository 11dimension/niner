__author__ = 'magus0219'
import re
import datetime

str_text = """
标签名:{name}
标签作者:{author}
标签作者email:{email}
标签commit:{commit_id}
标签时间:{tag_time}
标签描述:
{desc}
"""


class Tag():
    def __init__(self, name, author, email, commit_id, desc, tag_time):
        self.name = name
        self.author = author
        self.email = email
        self.commit_id = commit_id
        self.desc = desc
        self.tag_time = tag_time

    @staticmethod
    def create_by_tag_info(tag_info):
        """Create a tag object by parsing output of command git show tagname

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
        """
        name = None
        author = None
        email = None
        commit_id = None
        desc = None
        tag_time = None

        pattern_name = 'tag\s+(r\d+\.\d+\.\d+)\n'
        rst = re.search(pattern_name, tag_info)
        if rst:
            name = rst.group(1)

        pattern_auther_email = 'Tagger:\s(.+)\s<(.+)>'
        rst = re.search(pattern_auther_email, tag_info)
        if rst:
            author = rst.group(1)
            email = rst.group(2)

        pattern_tag_time = 'Tagger:.+\nDate:\s+(.+)\n'
        rst = re.search(pattern_tag_time, tag_info)
        if rst:
            tag_time = rst.group(1)
            tag_time = datetime.datetime.strptime(tag_time, '%a %b %d %H:%M:%S %Y %z')

        pattern_desc = 'Date:.+\n\n((.|\n)+)\ncommit'
        rst = re.search(pattern_desc, tag_info)
        if rst:
            desc = rst.group(1)

        pattern_commit_id = 'commit\s(.+)\n'
        rst = re.search(pattern_commit_id, tag_info)
        if rst:
            commit_id = rst.group(1)

        if name:
            return Tag(name, author, email, commit_id, desc, tag_time)
        else:
            return None

    def __repr__(self):
        return self.name

    def __str__(self):
        return str_text.format(name=self.name,
                               author=self.author,
                               email=self.email,
                               commit_id=self.commit_id,
                               tag_time=self.tag_time,
                               desc=self.desc)
