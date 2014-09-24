from . import catalog
import re
import time

dateFmtStr = '%m/%d/%Y'
dateFmtUsr = 'MM/DD/YYYY'

def decodeDate(date):
    return time.strftime(dateFmtStr, time.localtime(float(date)))

def encodeDate(date):
    return time.strftime('%s', time.strptime(date, dateFmtStr))

def processWords(field, d):
    if field in d:
        return re.findall(r"[\w'.]+", d[field].lower(), re.UNICODE)
    elif field != 'disambiguation':
        _log.warning('Release '+relId+' is missing the '+field+' field')
    return set()

