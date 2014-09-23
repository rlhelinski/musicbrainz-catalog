from mbcat.catalog import *

dateFmtStr = '%m/%d/%Y'
dateFmtUsr = 'MM/DD/YYYY'

def decodeDate(date):
    return time.strftime(mbcat.dateFmtStr, time.localtime(float(date)))

def encodeDate(date):
    return time.strftime('%s', time.strptime(date, mbcat.dateFmtStr))

