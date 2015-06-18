# -*- coding:utf-8 -*- 
'''
Created on 2015年4月23日

@author: sayoko
'''
import threading
import logging
import functools
import time
import uuid

#数据库引擎对象
class _Engine(object):
    def __init__(self, connect):
        self._connect = connect
    def connect(self):
        return self._connect()
    
engine = None


class DBError(object):
    
    def __init__(self, param0):
        pass

class MultiColumnsError(DBError):
    pass

def create_engine(user, password, database, host = '127.0.0.1', port = '3306', **kw):
    import mysql.connector
    global engine
    if engine is not None:
        raise DBError('Engine is already initialized.')
    params = dict(user = user, password = password, database = database, host = host, port =port)
    defaults = dict(use_unicode = True, charset = 'utf8', collation = 'utf8_general_ci', autocommit = False)
    for k, v in defaults.iteritems():
        params[k] = kw.pop(k, v)
    params.update(kw)
    params['buffered'] = True
    engine = _Engine(lambda : mysql.connector.connect(**params))
    logging.info('Initialized mysql engine %s OK.' % hex(id(engine)))


class _LasyConnection(object):
    def __init__(self):
        self.connection = None
    def cursor(self):
        if self.connection is None:
            con = engine.connect()
            logging.info('open connection <%s>...' % hex(id(con)))
            self.connection = con
        return self.connection.cursor()
    def commit(self):
        self.connection.commit()
    def rollback(self):
        self.connection.rollback()
    def cleanup(self):
        if self.connection:
            con = self.connection
            #???为何不直接关闭
            self.connection = None
            logging.info('close connection <%s>' % hex(id(con)))
            con.close()
            


#持有数据库连接的上下文对象
class _DBContext(threading.local):
    def __init__(self):
        self.connection = None
        self.transactions = 0
    def init(self):
        self.connection = _LasyConnection()
        self.transactions = 0
    def is_init(self):
        return not self.connection is None
    def cleanup(self):
        self.connection.cleanup()
        self.connection = None
    def cursor(self):
        return self.connection.cursor()
_db_context = _DBContext()

#数据库连接上下文对象
#为了方便使用with..as..语句,我们定义了__enter__和__exit__方法
class _ConContext(object):
    def __enter__(self):
        global _db_context
        self.should_cleanup = False
        if not _db_context.is_init():
            _db_context.init()
            self.should_cleanup = True
        return self
    def __exit__(self, exceptiontype, exceptionvalue, traceback):
        global _db_context
        if self.should_cleanup:
            _db_context.cleanup()
            
def connection():
    return _ConContext()

def with_connection(fun):
    @functools.wraps(fun)
    def _wrapper(*args, **kw):
        with _ConContext():
            return fun(*args, **kw)
    return _wrapper

class Dict(dict):
    def __init__(self, names = (), values = (), **kw):
        super(Dict, self).__init__(**kw)
        for k, v in zip(names, values):
            self[k] = v
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError("'Dict' object has no attribute %s" % key)
    def __setattr__(self, key, value):
        self[key] = value
        
def next_id(t = None):
    '''
    Return next id as 50-char string.
    Args:
        t: unix timestamp, default to None and using time.time().
    '''
    if t is None:
        t = time.time()
    return '%015d%s000' % (int(t * 1000), uuid.uuid4().hex)

def _profiling(start, sql = ''):
    t = time.time() - start
    if t > 0.1:
        logging.warning('[PROFILING] [DB] %s : %s' % (t, sql))
    else:
        logging.info('[PROFILING] {DB} %s : %s' % (t, sql))
        
class _TransactionContext(object):
    '''
    _TransactionCtx object that can handle transactions.
    with _TransactionCtx():
        pass
    '''
    def __enter__(self):
        global _db_context
        self.should_close_conn = False
        if not _db_context.is_init():
            _db_context.init()
            self.should_close_conn = True
        _db_context.transactions = _db_context.transactions + 1
        logging.info('begin transaction...' if _db_context.transactions == 1 else 'join current transaction...')
        return self
    def __exit__(self, exceptiontype, exceptionvalue, traceback):
        global _db_context
        _db_context.transactions = _db_context.transactions - 1
        try:
            if _db_context.transactions == 0:
                if exceptiontype is None:
                    self.commit()
                else:
                    self.rollback()
        finally:
            if self.should_close_conn:
                _db_context.cleanup()
    def commit(self):
        global _db_context            
        logging.info('commit transaction...')
        try:
            _db_context.connection.commit()
            logging.info('commit done.')
        except:
            logging.warning('commit failed! try rollback...')
            _db_context.connection.rollback()
            logging.warning('rollback done.')
            raise
    def rollback(self):
        global _db_context
        logging.warning('rollback transaction...')
        _db_context.connection.rollback()
        logging.warning('rollback done.')
        
def transaction():
    '''
    Create a transaction object so can use with statement:
    with transaction():
        pass
    >>> def update_profile(id, name, rollback):
    ...     u = dict(id=id, name=name, email='%s@test.org' % name, passwd=name, last_modified=time.time())
    ...     insert('user', **u)
    ...     r = update('update user set passwd=? where id=?', name.upper(), id)
    ...     if rollback:
    ...         raise StandardError('will cause rollback...')
    >>> with transaction():
    ...     update_profile(900301, 'Python', False)
    >>> select_one('select * from user where id=?', 900301).name
    u'Python'
    >>> with transaction():
    ...     update_profile(900302, 'Ruby', True)
    Traceback (most recent call last):
      ...
    StandardError: will cause rollback...
    >>> select('select * from user where id=?', 900302)
    []
    '''
    return _TransactionContext()

def with_transaction(fun):
    @functools.wraps(fun)
    def _wrapper(*args, **kw):
        _start = time.time()
        return fun(*args, **kw)
        _profiling(_start)
    return _wrapper

def _select(sql, first, *args):
    global _db_context
    cursor = None
    sql = sql.replace('?', '%s')
    logging.info('SQL: %s, ARGS: %s' % (sql, args))
    try:
        cursor = _db_context.connection.cursor()
        cursor.execute(sql, args)
        if cursor.description:
            names = [x[0] for x in cursor.description]
        if first:
            values = cursor.fetchone()
            if not values:
                return None
            return Dict(names, values)
        return [Dict(names, v) for v in cursor.fetchall()]
    finally:
        if cursor:
            cursor.close()
            
@with_connection
def select_one(sql, *args):
    '''
    Execute select SQL and expected one result. 
    If no result found, return None.
    If multiple results found, the first one returned.
    >>> u1 = dict(id=100, name='Alice', email='alice@test.org', passwd='ABC-12345', last_modified=time.time())
    >>> u2 = dict(id=101, name='Sarah', email='sarah@test.org', passwd='ABC-12345', last_modified=time.time())
    >>> insert('user', **u1)
    1
    >>> insert('user', **u2)
    1
    >>> u = select_one('select * from user where id=?', 100)
    >>> u.name
    u'Alice'
    >>> select_one('select * from user where email=?', 'abc@email.com')
    >>> u2 = select_one('select * from user where passwd=? order by email', 'ABC-12345')
    >>> u2.name
    u'Alice'
    '''
    return _select(sql, True, *args)

@with_connection
def select_int(sql, *args):
    '''
    Execute select SQL and expected one int and only one int result. 
    >>> n = update('delete from user')
    >>> u1 = dict(id=96900, name='Ada', email='ada@test.org', passwd='A-12345', last_modified=time.time())
    >>> u2 = dict(id=96901, name='Adam', email='adam@test.org', passwd='A-12345', last_modified=time.time())
    >>> insert('user', **u1)
    1
    >>> insert('user', **u2)
    1
    >>> select_int('select count(*) from user')
    2
    >>> select_int('select count(*) from user where email=?', 'ada@test.org')
    1
    >>> select_int('select count(*) from user where email=?', 'notexist@test.org')
    0
    >>> select_int('select id from user where email=?', 'ada@test.org')
    96900
    >>> select_int('select id, name from user where email=?', 'ada@test.org')
    Traceback (most recent call last):
        ...
    MultiColumnsError: Expect only one column.
    '''
    r = _select(sql, True, *args)
    if len(r) != 1:
        raise MultiColumnsError('Expect only one column.')
    #???不用加[0],因为结果只有一个
    return r.values()[0]

@with_connection
def select(sql, *args):
    '''
    Execute select SQL and return list or empty list if no result.
    >>> u1 = dict(id=200, name='Wall.E', email='wall.e@test.org', passwd='back-to-earth', last_modified=time.time())
    >>> u2 = dict(id=201, name='Eva', email='eva@test.org', passwd='back-to-earth', last_modified=time.time())
    >>> insert('user', **u1)
    1
    >>> insert('user', **u2)
    1
    >>> L = select('select * from user where id=?', 900900900)
    >>> L
    []
    >>> L = select('select * from user where id=?', 200)
    >>> L[0].email
    u'wall.e@test.org'
    >>> L = select('select * from user where passwd=? order by id desc', 'back-to-earth')
    >>> L[0].name
    u'Eva'
    >>> L[1].name
    u'Wall.E'
    '''
    return _select(sql, False, *args)

@with_connection            
def _update(sql, *args):
    global _db_context
    cursor = None
    sql = sql.replace('?', '%s')
    logging.info('SQL: %s, ARGS: %s' % (sql, args))
    try:
        cursor = _db_context.connection.cursor()
        cursor.execute(sql, args)
        rc = cursor.rowcount
        if _db_context.transactions == 0:
            logging.info('auto commit.')
            _db_context.connection.commit()
        return rc
    finally:
        if cursor:
            cursor.close()

def update(sql, *args):
    '''
    Execute update SQL.
    >>> u1 = dict(id=1000, name='Michael', email='michael@test.org', passwd='123456', last_modified=time.time())
    >>> insert('user', **u1)
    1
    >>> u2 = select_one('select * from user where id=?', 1000)
    >>> u2.email
    u'michael@test.org'
    >>> u2.passwd
    u'123456'
    >>> update('update user set email=?, passwd=? where id=?', 'michael@example.org', '654321', 1000)
    1
    >>> u3 = select_one('select * from user where id=?', 1000)
    >>> u3.email
    u'michael@example.org'
    >>> u3.passwd
    u'654321'
    >>> update('update user set passwd=? where id=?', '***', '123\' or id=\'456')
    0
    '''
    return _update(sql, *args)

def insert(tbl, **kw):
    '''
    Execute insert SQL.
    >>> u1 = dict(id=2000, name='Bob', email='bob@test.org', passwd='bobobob', last_modified=time.time())
    >>> insert('user', **u1)
    1
    >>> u2 = select_one('select * from user where id=?', 2000)
    >>> u2.name
    u'Bob'
    >>> insert('user', **u2)
    Traceback (most recent call last):
      ...
    IntegrityError: 1062 (23000): Duplicate entry '2000' for key 'PRIMARY'
    '''
    cols, args = zip(*kw.iteritems())
    sql = 'insert into `%s` (%s) values (%s)' % (tbl, ','.join(['`%s`'% col for col in cols]), ','.join(['?' for i in range(len(cols))]))
    return _update(sql, *args)

if __name__ == '__main__':
    logging.basicConfig(level = logging.DEBUG)
    create_engine('root', 'root', 'awesome')
    update('drop table if exists user')
    update('create table user (id int primary key, name text, email text, passwd text, last_modified real)')
    #import doctest
    #doctest.testmod()  