# -*- coding:utf-8 -*-
'''
Created on 2015年5月4日

@author: sayoko
'''
import threading
from datetime import datetime
import re
import urllib
import os
import mimetypes

#全局的ThreadLocal对象,用来存储request和response
ctx = threading.local

#字典对象
class Dict(dict):
    def __init__(self, names = (), values = (), **kw):
        super(Dict, self).__init__(**kw)
        for k, v in zip(names, values):
            self[k] = v
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError("'Dict' object has no attribute '%s'" % key)
    def __setattr__(self, key, value):
        self[key] = value

_TIMEDELTA_ZERO = datetime.timedelta(0)

class UTC(datetime.tzinfo):
    '''
    A UTC tzinfo object. 
    >>> tz0 = UTC('+00:00')
    >>> tz0.tzname(None)
    'UTC+00:00'
    >>> tz8 = UTC('+8:00')
    >>> tz8.tzname(None)
    'UTC+8:00'
    >>> tz7 = UTC('+7:30')
    >>> tz7.tzname(None)
    'UTC+7:30'
    >>> tz5 = UTC('-05:30')
    >>> tz5.tzname(None)
    'UTC-05:30'
    >>> from datetime import datetime
    >>> u = datetime.utcnow().replace(tzinfo=tz0)
    >>> l1 = u.astimezone(tz8)
    >>> l2 = u.replace(tzinfo=tz8)
    >>> d1 = u - l1
    >>> d2 = u - l2
    >>> d1.seconds
    0
    >>> d2.seconds
    28800
    '''
    def __init__(self, utc):
        utc = str(utc.strip().upper())
        mt = _RE_TZ.match(utc)
        if mt:
            minus = mt.group(1) == '-'
            h = int(mt.group(2))
            m = int(mt.group(3))
            if minus:
                h, m = (-h), (-m)
            self._utcoffset = datetime.timedelta(hours = h, minutes = m)
            self._tzname = 'UTC%s' % utc
        else:
            raise ValueError('bad utc time zone')
    def utcoffset(self, dt):
        return self._utcoffset
    def dst(self, dt):
        return _TIMEDELTA_ZERO
    def tzname(self, dt):
        return self._tzname
    def __str__(self):
        return 'UTC tzinfo object (%s)' % self._tzname
    
    __repr__ = __str__

# timezone as UTC+8:00, UTC-10:00
_RE_TZ = re.compile('^([\+\-])([0-9]{1,2})\:([0-9]{1,2})$')

#所有已知的响应状态
_RESPONSE_STATUSES = {
    # Informational
    100: 'Continue',
    101: 'Switching Protocols',
    102: 'Processing',
    
    # Successful
    200: 'OK',
    201: 'Created',
    202: 'Accepted',
    203: 'Non-Authoritative Information',
    204: 'No Content',
    205: 'Reset Content',
    206: 'Partial Content',
    207: 'Multi Status',
    226: 'IM Used',
    
    # Redirection
    300: 'Multiple Choices',
    301: 'Moved Permanently',
    302: 'Found',
    303: 'See Other',
    304: 'Not Modified',
    305: 'Use Proxy',
    307: 'Temporary Redirect',
    
    # Client Error
    400: 'Bad Request',
    401: 'Unauthorized',
    402: 'Payment Required',
    403: 'Forbidden',
    404: 'Not Found',
    405: 'Method Not Allowed',
    406: 'Not Acceptable',
    407: 'Proxy Authentication Required',
    408: 'Request Timeout',
    409: 'Conflict',
    410: 'Gone',
    411: 'Length Required',
    412: 'Precondition Failed',
    413: 'Request Entity Too Large',
    414: 'Request URI Too Long',
    415: 'Unsupported Media Type',
    416: 'Requested Range Not Satisfiable',
    417: 'Expectation Failed',
    418: "I'm a teapot",
    422: 'Unprocessable Entity',
    423: 'Locked',
    424: 'Failed Dependency',
    426: 'Upgrade Required',
    
    # Server Error
    500: 'Internal Server Error',
    501: 'Not Implemented',
    502: 'Bad Gateway',
    503: 'Service Unavailable',
    504: 'Gateway Timeout',
    505: 'HTTP Version Not Supported',
    507: 'Insufficient Storage',
    510: 'Not Extended'}

_RE_RESPONSE_STATUS = re.compile(r'^\d\d\d(\ [\w\ ]+)?$')

_RESPONSE_HEADERS = (
    'Accept-Ranges',
    'Age',
    'Allow',
    'Cache-Control',
    'Connection',
    'Content-Encoding',
    'Content-Language',
    'Content-Length',
    'Content-Location',
    'Content-MD5',
    'Content-Disposition',
    'Content-Range',
    'Content-Type',
    'Date',
    'ETag',
    'Expires',
    'Last-Modified',
    'Link',
    'Location',
    'P3P',
    'Pragma',
    'Proxy-Authenticate',
    'Refresh',
    'Retry-After',
    'Server',
    'Set-Cookie',
    'Strict-Transport-Security',
    'Trailer',
    'Transfer-Encoding',
    'Vary',
    'Via',
    'Warning',
    'WWW-Authenticate',
    'X-Frame-Options',
    'X-XSS-Protection',
    'X-Content-Type-Options',
    'X-Forwarded-Proto',
    'X-Powered-By',
    'X-UA-Compatible'
)

_RESPONSE_HEADER_DICT = dict(zip(map(lambda x : x.upper(), _RESPONSE_HEADERS),_RESPONSE_HEADERS))

_HEADER_X_POWERED_BY = ('X-Powered-By', 'transwarp/1.0')

#HTTP错误类
class HttpError(Exception):
    '''
    HttpError that defines http error code.
    >>> e = HttpError(404)
    >>> e.status
    '404 Not Found'
    '''
    def __init__(self, code):
        super(HttpError, self).__init__()
        self.status = '%d %s' % (code, _RESPONSE_STATUSES[code])
    def header(self, name, value):
        if not hasattr(self, '_headers'):
            self._headers = [_HEADER_X_POWERED_BY]
        self._headers.append(name, value)
    @property
    def headers(self):
        if hasattr(self, '_headers'):
            return self._headers
        return []
    def __str__(self):
        return self.status
    
    __repr__ = __str__
    
class RedirectError(HttpError):
    '''
    RedirectError that defines http redirect code.
    >>> e = RedirectError(302, 'http://www.apple.com/')
    >>> e.status
    '302 Found'
    >>> e.location
    'http://www.apple.com/'
    '''
    def __init__(self, code, location):
        super(RedirectError, self).__init__(code)
        self.location = location
    def __str__(self):
        return '%s, %s' % (self.status, self.location)
    
    __repr__ = __str__
    
def badrequest():
    '''
    Send a bad request response.
    >>> raise badrequest()
    Traceback (most recent call last):
      ...
    HttpError: 400 Bad Request
    '''
    return HttpError(400)

def unauthorized():
    '''
    Send an unauthorized response.
    >>> raise unauthorized()
    Traceback (most recent call last):
      ...
    HttpError: 401 Unauthorized
    '''
    return HttpError(401)

def forbidden():
    '''
    Send a forbidden response.
    >>> raise forbidden()
    Traceback (most recent call last):
      ...
    HttpError: 403 Forbidden
    '''
    return HttpError(403)

def notfound():
    '''
    Send a not found response.
    >>> raise notfound()
    Traceback (most recent call last):
      ...
    HttpError: 404 Not Found
    '''
    return HttpError(404)

def conflict():
    '''
    Send a conflict response.
    >>> raise conflict()
    Traceback (most recent call last):
      ...
    HttpError: 409 Conflict
    '''
    return HttpError(409)

def internalerror():
    '''
    Send an internal error response.
    >>> raise internalerror()
    Traceback (most recent call last):
      ...
    HttpError: 500 Internal Server Error
    '''
    return HttpError(500)

def redirect(location):
    '''
    Do permanent redirect.
    >>> raise redirect('http://www.itranswarp.com/')
    Traceback (most recent call last):
      ...
    RedirectError: 301 Moved Permanently, http://www.itranswarp.com/
    '''
    return RedirectError(301, location)

def found(location):
    '''
    Do temporary redirect.
    >>> raise found('http://www.itranswarp.com/')
    Traceback (most recent call last):
      ...
    RedirectError: 302 Found, http://www.itranswarp.com/
    '''
    return RedirectError(302, location)

def seeother(location):
    '''
    Do temporary redirect.
    >>> raise seeother('http://www.itranswarp.com/')
    Traceback (most recent call last):
      ...
    RedirectError: 303 See Other, http://www.itranswarp.com/
    >>> e = seeother('http://www.itranswarp.com/seeother?r=123')
    >>> e.location
    'http://www.itranswarp.com/seeother?r=123'
    '''
    return RedirectError(303, location)

def _to_str(s):
    '''
    Convert to str.
    >>> _to_str('s123') == 's123'
    True
    >>> _to_str(u'\u4e2d\u6587') == '\xe4\xb8\xad\xe6\x96\x87'
    True
    >>> _to_str(-123) == '-123'
    True
    '''
    if isinstance(s, str):
        return s
    elif isinstance(s, unicode):
        return s.encode('utf-8')
    return str(s)

def _to_unicode(s, encoding = 'utf-8'):
    '''
    Convert to unicode.
    >>> _to_unicode('\xe4\xb8\xad\xe6\x96\x87') == u'\u4e2d\u6587'
    True
    '''
    return s.decode('utf-8')

def _quote(s, encoding = 'utf-8'):
    '''
    Url quote as str.
    >>> _quote('http://example/test?a=1+')
    'http%3A//example/test%3Fa%3D1%2B'
    >>> _quote(u'hello world!')
    'hello%20world%21'
    '''
    if isinstance(s, unicode):
        s.encode(encoding)
    return urllib.quote(s)

def _unquote(s, encoding = 'utf-8'):
    '''
    Url unquote as unicode.
    >>> _unquote('http%3A//example/test%3Fa%3D1+')
    u'http://example/test?a=1+'
    '''
    return urllib.unquote(s).decode(encoding)


#Request对象
class Request(object):
    #根据key返回value
    def get(self, key, default = None):
        pass
    #返回key-value的dict
    def input(self):
        pass
    #返回URL的path
    @property
    def path_info(self):
        pass
    #返回HTTP的Headers
    @property
    def headers(self):
        pass
    #根据key返回Cookie的value
    def cookie(self, name, default = None):
        pass
    

#Response对象
class Response(object):
    #设置header
    def set_header(self, key, value):
        pass
    #设置Cookie
    def set_cookie(self, name, value, max_age = None, expires = None, path = '/'):
        pass
    #设置status
    @property
    def status(self):
        pass
    @status.setter
    def status(self, value):
        pass
    
#GET
def get(path):
    '''
    A @get decorator.
    @get('/:id')
    def index(id):
        pass
    >>> @get('/test/:id')
    ... def test():
    ...     return 'ok'
    ...
    >>> test.__web_route__
    '/test/:id'
    >>> test.__web_method__
    'GET'
    >>> test()
    'ok'
    '''
    def _decorator(fun):
        fun.__web_route__ = path
        fun.__web_method__ = 'GET'
        return fun
    return _decorator

#POST
def post(path):
    def _decorator(fun):
        fun.__web_route__ = path
        fun.__web_method__ = 'POST'
        return fun
    return _decorator

_RE_ROUTE = re.compile(r'(\:[a-zA-Z_]\w*)')

def _build_regex(path):
    '''
    Convert route path to regex.
    >>> _build_regex('/path/to/:file')
    '^\\/path\\/to\\/(?P<file>[^\\/]+)$'
    >>> _build_regex('/:user/:comments/list')
    '^\\/(?P<user>[^\\/]+)\\/(?P<comments>[^\\/]+)\\/list$'
    >>> _build_regex(':id-:pid/:w')
    '^(?P<id>[^\\/]+)\\-(?P<pid>[^\\/]+)\\/(?P<w>[^\\/]+)$'
    '''
    re_list = ['^']
    var_list = []
    is_var = False
    for v in _RE_ROUTE.split(path):
        if is_var:
            var_name = v[1:]
            var_list.append(var_name)
            re_list.append(r'(?P<%s>[^\/]+)' % var_name)
        else:
            s = ''
            for ch in v:
                if ch >= '0' and ch <= '9':
                    s = s + ch
                elif ch >= 'a' and ch <= 'z':
                    s = s + ch
                elif ch >= 'A' and ch <= 'Z':
                    s = s + ch
                else:
                    s = s + '\\' + ch
            re_list.append(s)
        is_var = not is_var
    re_list.append('$')
    return ''.join(re_list)

class Route(object):
    def __init__(self, fun):
        self.path = fun.__web_route__
        self.method = fun.__web_method__
        self.is_static = _RE_ROUTE.search(self.path) is None
        if not self.is_static:
            self.route = re.compile(_build_regex(self.path))
        self.fun = fun
    def match(self, url):
        m = self.route.match(url)
        if m:
            return m.groups()
        return None
    def __call__(self, *args):
        return self.fun(*args)
    def __str__(self):
        if self.is_static:
            return 'Route(static, %s, path = %s)' % (self.method, self.path)
        return 'Route(dynamic, %s, path = %s)' % (self.method, self.path)
    
    __repr__ = __str__
    
def _static_file_generator(fpath):
    BLOCK_SIZE = 8192
    with open(fpath, 'rb') as f:
        block = f.read(BLOCK_SIZE)
        while block:
            yield block
            block = f.read(BLOCK_SIZE)

class StaticFileRoute(object):
    def __init__(self):
        self.method = 'GET'
        self.is_static = False
        self.route = re.compile('^/static/(.+)$')
    def match(self, url):
        if url.startswith('/static/'):
            return (url[1:],)
        return None
    def __call__(self, *args):
        fpath = os.path.join(ctx.application.document_root, args[0])
        if not os.path.isfile(fpath):
            raise notfound()
        fext = os.path.splitext(fpath)[1]
        ctx.response.content_type = mimetypes.types_map.get(fext.lower(), 'application/octet-stream')
        return _static_file_generator(fpath)
    
def favicon_handler():
    return static_file_handler('/favicon.ico')

class MultipartFile(object):
    '''
    Multipart file storage get from request input.
    f = ctx.request['file']
    f.filename # 'test.png'
    f.file # file-like object
    '''
    def __init__(self, storage):
        self.filename = _to_unicode(storage.filename)
        self.file = storage.file
    
#模板
def view(path):
    pass

#拦截器
def interceptor(pattern):
    pass

#模板引擎
class TemplateEngine(object):
    def call(self, path, model):
        pass
    
#缺省使用jinja2
class Jinja2TemplateEngine(object):
    def __init__(self, templ_dir, **kw):
        from jinja2 import Environment, FileSystemLoader
        self._env = Environment(loader = FileSystemLoader(templ_dir), **kw)
    def __call__(self, path, model):
        self._env.get_template(path).render(**model).encode('utf-8')
        
        
class WSGIApplication(object):
    def __init__(self, document_root = None, **kw):
        pass
    #添加一个URL定义
    def add_url(self, fun):
        pass
    #添加一个Interceptor定义
    def add_interceptor(self, fun):
        pass
    #设置TemplateEngine
    @property
    def template_engine(self):
        pass
    @template_engine.setter
    def template_engin(self, engine):
        pass
    #返回WSGI的处理函数
    def get_wsgi_application(self):
        def wsgi(env, start_response):
            pass
        return wsgi
    #开发模式下直接启动服务
    def run(self, port = 9000, host = '127.0.0.1'):
        from wsgiref.simple_server import make_server
        server = make_server(host, port, self.get_wsgi_application())
        server.serve_forever()
        
wsgi = WSGIApplication()
if __name__ == '__main__':
    wsgi.run()
else:
    application = wsgi.get_wsgi_application()