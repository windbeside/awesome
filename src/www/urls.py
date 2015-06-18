# -*- coding:utf-8 -*- 
'''
Created on 2015年5月11日

@author: sayoko
'''
from models import User
from transwarp.web import get, view

@view('test_users.html')
@get('/') 
def test_users():
    users = User.find_all()
    return dict(users = users)