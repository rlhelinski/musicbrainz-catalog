from __future__ import print_function
import sqlite3
import cPickle as pickle
import os
import codecs
import mbcat
import logging
logging.basicConfig(level=logging.INFO)

import musicbrainzngs.musicbrainz as mb
import musicbrainzngs.mbxml as mbxml
import progressbar
# Get the XML parsing exceptions to catch. The behavior changed with Python 2.7
# and ElementTree 1.3.
import xml.etree.ElementTree as etree
from xml.parsers import expat
if hasattr(etree, 'ParseError'):
    ETREE_EXCEPTIONS = (etree.ParseError, expat.ExpatError)
else:
    ETREE_EXCEPTIONS = (expat.ExpatError)

print ('pysqlite3: '+sqlite3.version+' sqlite3: '+sqlite3.sqlite_version)

# Create a new database
dbname = 'mbcat.db'

# Problem: pickle dumps takes unicode strings but returns binary strings
# base64 encoding fixes it for now, but it will look ugly if the sql db 
# is inspected directly. 
import base64
def listAdapter(l):
    return base64.b64encode(pickle.dumps(l))

def listConverter(s):
    return pickle.loads(base64.b64decode(s))

sqlite3.register_adapter(list, listAdapter)
sqlite3.register_converter("list", listConverter)

rootPath = 'release-id'

def sql_list_append(cursor, table_name, field_name, key, value):
    cursor.execute('select * from '+table_name+' where '+field_name+' = ?', (key,))
    row = cursor.fetchall()
    if not row:
        relList = [value]
    else:
        relList = row[0][1]
        relList.append(relId)

    cur.execute(('replace' if row else 'insert')+' into '+table_name+'('+field_name+', releases) values (?, ?)',
            (key, relList))


# Create tables
with sqlite3.connect(dbname, detect_types=sqlite3.PARSE_DECLTYPES) as con:
    #con.text_factory = unicode 
    cur = con.cursor()
    cur.execute("CREATE TABLE releases("+\
        "id TEXT PRIMARY KEY, "+\
        # metadata from musicbrainz, maybe store a dict instead of the XML?
        "meta TEXT, "+\
        # now all the extra data
        "purchases LIST, "+\
        "added LIST, "+\
        "lent LIST, "+\
        "listened LIST, "+\
        "digital LIST, "+\
        "count INT, "+\
        "comment TEXT, "+\
        "rating INT)")
    
    cur.execute('CREATE TABLE words('+\
            'word TEXT PRIMARY KEY, '+\
            'releases list)')

    cur.execute('CREATE TABLE discids('+\
            'discid TEXT PRIMARY KEY, '+\
            'releases list)')

    cur.execute('CREATE TABLE barcodes('+\
            'barcode TEXT PRIMARY KEY, '+\
            'releases list)')

    cur.execute('CREATE TABLE formats('+\
            'format TEXT PRIMARY KEY, '+\
            'releases list)')

    con.commit()

    fileList = os.listdir(rootPath)
    widgets = ["Releases: ", progressbar.Bar(marker="=", left="[", right="]"), " ", progressbar.Percentage() ]
    if len(fileList):
        pbar = progressbar.ProgressBar(widgets=widgets, maxval=len(fileList)).start()
    for relId in fileList:
        #with codecs.open(os.path.join(rootPath, relId, 'metadata.xml'), encoding='utf-8') as f:
        with open(os.path.join(rootPath, relId, 'metadata.xml'), 'r') as f:
            metaXml = f.read()

        try:
            metadata = mbxml.parse_message(metaXml)['release']
        except UnicodeError as exc:
            raise mb.ResponseError(cause=exc)
        except Exception as exc:
            if isinstance(exc, ETREE_EXCEPTIONS):
                logging.error("Got some bad XML for %s!", releaseId)
            else:
                raise


        ed = mbcat.extradata.ExtraData(relId)
        try:
            ed.load()
        except IOError as e:
            ed = None

        cur.execute('insert into releases(id, meta, purchases, added, lent, listened, digital, count, comment, rating) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (relId, 
                    metaXml.decode('utf-8'), 
                    ed.purchases,
                    ed.addDates,
                    ed.lendEvents,
                    ed.listenEvents,
                    #[p.decode('utf-8') for p in ed.digitalPaths],
                    ed.digitalPaths,
                    1, 
                    ed.comment if ed else '',
                    ed.rating if ed else 0)
                )

        # Update words table
        rel_words = mbcat.Catalog.getReleaseWords(metadata)
        for word in rel_words:
            sql_list_append(cur, 'words', 'word', word, relId)

        # Update barcodes -> (barcode, releases)
        if 'barcode' in metadata and metadata['barcode']:
            sql_list_append(cur, 'barcodes', 'barcode', metadata['barcode'], relId)

        # Update discids -> (discid, releases)
        for medium in metadata['medium-list']:
            for disc in medium['disc-list']:
                sql_list_append(cur, 'discids', 'discid', disc['id'], relId)

        # Update formats -> (format, releases)
        fmt = mbcat.formats.getReleaseFormat(metadata).__class__.__name__
        sql_list_append(cur, 'formats', 'format', fmt, relId)

        pbar.update(pbar.currval + 1)

    con.commit()
    pbar.finish()

with sqlite3.connect(dbname, detect_types=sqlite3.PARSE_DECLTYPES) as con:
    cur = con.cursor()
    cur.execute('select * from releases')
    rows = cur.fetchall()
    for row in rows[:10]:
        for e in row:
            if len(repr(e)) > 20:
                print(repr(e)[:20] +'..., ', end='')
            else:
                print(repr(e) +', ', end='')
        print('...')
    print ('...')

