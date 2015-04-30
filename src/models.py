# -*- coding:utf-8 -*-
'''
Created on 2015年4月29日

@author: 冯鹏斌
'''
from transwarp.orm import Model, StringField, BooleanField, FloatField,\
    TextField
from transwarp.db import next_id
import time
import uuid

def next_id():
    return '%015d%s000' % (int(time.time() * 1000), uuid.uuid4().hex)

class User(Model):
    __table__ = 'user'
    
    id = StringField(primary_key = True, default = next_id, ddl = 'varchar(50)')
    email = StringField(updatable = False, ddl = 'varchar(50)')
    password = StringField(ddl = 'varchar(50)')
    admin = BooleanField()
    name = StringField(ddl = 'varchar(50)')
    image = StringField(ddl = 'varchar(50)')
    created_at = FloatField(updatable = False, default = time.time)
    
class Blog(Model):
    __table__ = 'blog'
    
    id = StringField(primary_key = True, default = next_id, ddl = 'varchar(50)')
    user_id = StringField(updatable = False, ddl = 'varchar(50)')
    user_name = StringField(ddl = 'varchar(50)')
    user_image = StringField(ddl = 'varchar(500)')
    name = StringField(ddl = 'varchar(50)')
    summary = StringField(ddl = 'varchar(200)')
    content = TextField()
    created_at = FloatField(updatable = False, default = time.time)
    def pre_insert(self):
        self.created_at = time.time()
    
class Comment(Model):
    __table__ = 'comment'

    id = StringField(primary_key = True, default = next_id, ddl = 'varchar(50)')
    blog_id = StringField(updatable = False, ddl = 'varchar(50)')
    user_id = StringField(updatable = False, ddl = 'varchar(50)')
    user_name = StringField(ddl = 'varchar(50)')
    user_image = StringField(ddl = 'varchar(500)')
    content = TextField()
    created_at = FloatField(updatable = False, default = time.time)