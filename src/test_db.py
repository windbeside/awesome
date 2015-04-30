# -*- coding:utf-8 -*-
'''
Created on 2015年4月29日

@author: sayoko
'''
from transwarp import db
from models import User
db.create_engine(user = 'www-data', password = 'www-data', database = 'awesome')
u = User(name='Test', email='test@example.com', password='1234567890', image='about:blank')
u.insert()
print 'new user id:', u.id

u1 = User.find_first('where email=?', 'test@example.com')
print 'find user\'s name:', u1.name

u1.delete()

u2 = User.find_first('where email=?', 'test@example.com')
print 'find user:', u2