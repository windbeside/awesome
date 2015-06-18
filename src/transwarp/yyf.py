# -*- coding:utf-8 -*-
import redis
r = redis.StrictRedis(host='172.27.18.82', port=6379,db=0)
from xml.dom import minidom
with open('filename.txt','r') as f:
    m=f.read()
doc = minidom.parse(m)
root = doc.documentElement
airlines = root.getElementsByTagName("AIRLINE")
for airline in airlines:
    print('--------')
    nameNode = airline.getElementsByTagName("CODE")[0]
    key=nameNode.childNodes[0].nodeValue
    print key
    print (nameNode.nodeName + ":" + nameNode.childNodes[0].nodeValue)
    ageNode = airline.getElementsByTagName("EN_NAME")[0]
    b={'EN_NAME': ageNode.childNodes[0].nodeValue}
    print (ageNode.nodeName + ":" + ageNode.childNodes[0].nodeValue)
    typeNode = airline.getElementsByTagName("AIRLINE_TYPE")[0]
    if len(typeNode.childNodes)==1:
        b={'AIRLINE_TYPE': typeNode.childNodes[0].nodeValue}
    print (typeNode.nodeName + ":" + typeNode.childNodes[0].nodeValue)
    cnNode = airline.getElementsByTagName("CN_NAME")[0]
    if len(cnNode.childNodes)==1:
        b={'CN_NAME': cnNode.childNodes[0].nodeValue}
    print (cnNode.nodeName + ":" + cnNode.childNodes[0].nodeValue).encode('utf-8','ignore')
    conNode = airline.getElementsByTagName("COUNTRY")[0]
    if len(conNode.childNodes)==1:
        b={'COUNTRY': conNode.childNodes[0].nodeValue}
    print (conNode.nodeName + ":" + conNode.childNodes[0].nodeValue)
    r.hmset(key,b)
