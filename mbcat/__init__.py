__all__ = ["catalog", "utils", "barcode"]

import re
import time
import datetime

dateFmtStr = '%m/%d/%Y'
dateFmtUsr = 'MM/DD/YYYY'

defaultPathSpec = '{Artist}/{Title}'

def decodeDate(date):
    return time.strftime(dateFmtStr, time.localtime(float(date)))

def encodeDate(date):
    return time.strftime('%s', time.strptime(date, dateFmtStr))

def encodeDateTime(dt):
    # This is a workaround because '%s' does not exist for
    # datetime.strftime on the Windows platform.
    epoch = datetime.datetime.utcfromtimestamp(0)
    delta = dt - epoch
    return delta.total_seconds()

def decodeDateTime(dts):
    return datetime.datetime.fromtimestamp(dts)

def processWords(field, d):
    if field in d:
        return re.findall(r"[\w'.]+", d[field].lower(), re.UNICODE)
    elif field != 'disambiguation':
        _log.warning('Release '+relId+' is missing the '+field+' field')
    return set()

