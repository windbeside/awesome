# -*- coding:utf-8 -*- 
'''
Created on 2015年5月11日

@author: sayoko
'''
import logging; logging.basicConfig(level=logging.INFO)
import os

from transwarp.web import WSGIApplication, Jinja2TemplateEngine
from transwarp import db

from config import configs

#初始化数据库
db.create_engine(**configs.db)

#创建一个WSGIApplication
wsgi = WSGIApplication(os.path.dirname(os.path.abspath(__file__)))
#初始化jinja2模板引擎
template_engine = Jinja2TemplateEngine(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates'))
wsgi.template_engine = template_engine

#加载带有@view, @get的URL处理函数
import urls
wsgi.add_module(urls)

if __name__ == '__main__':
    wsgi.run(9000)