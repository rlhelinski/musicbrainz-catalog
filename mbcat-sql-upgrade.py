import sqlite3
import pickle
import os
import codecs
import mbcat
import logging

import musicbrainzngs.musicbrainz as mb
import musicbrainzngs.mbxml as mbxml
# Get the XML parsing exceptions to catch. The behavior changed with Python 2.7
# and ElementTree 1.3.
import xml.etree.ElementTree as etree
from xml.parsers import expat
if hasattr(etree, 'ParseError'):
    ETREE_EXCEPTIONS = (etree.ParseError, expat.ExpatError)
else:
    ETREE_EXCEPTIONS = (expat.ExpatError)

print 'pysqlite3:', sqlite3.version, 'sqlite3', sqlite3.sqlite_version

# Create a new database
dbname = 'mbcat.db'

class Splunge(list):
    """It's just a list"""

def splunge_adapt(x):
    return ';'.join(x)

def splunge_convert(x):
    return x.split(';')

sqlite3.register_adapter(Splunge, splunge_adapt)
sqlite3.register_converter("Splunge", splunge_convert)

rootPath = 'release-id'

# Create tables
with sqlite3.connect(dbname, detect_types=sqlite3.PARSE_DECLTYPES) as con:
    cur = con.cursor()
    cur.execute("CREATE TABLE releases("+\
        "id TEXT PRIMARY KEY, "+\
        # metadata from musicbrainz
        "meta TEXT, "+\
        # now all the extra data
        "count INT, "+\
        "comment TEXT, "+\
        "rating INT)")
    
    cur.execute('CREATE TABLE words('+\
            'word TEXT PRIMARY KEY, '+\
            'releases Splunge)')

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

    for relId in os.listdir(rootPath):
        #with codecs.open(os.path.join(rootPath, relId, 'metadata.xml'), encoding='utf-8') as f:
        with file(os.path.join(rootPath, relId, 'metadata.xml'), 'r') as f:
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

        cur.execute('insert into releases(id, meta, count, comment, rating) values (?, ?, ?, ?, ?)',
                (relId, metaXml.decode('utf-8'), 1, ed.comment if ed else '', ed.rating if ed else 0))

        #import pdb; pdb.set_trace()
        try:
            rel_words = mbcat.Catalog.getReleaseWords(metadata)
            for word in rel_words:
                #print 'Checking for: ' + word,
                cur.execute('select * from words where word = ?', (word,))
                row = cur.fetchall()
                #print 'Fetched row: ' + repr(row)
                #import pdb; pdb.set_trace()
                if not row:
                    #print 'Word not known. '
                    relList = Splunge()
                    relList.append(relId)
                    #print 'adding', repr((word, relList))
                    #print 'type of relList:', type(relList)
                    cur.execute('insert into words(word, releases) values (?, ?)',
                            (word, relList))
                    cur.execute('select * from words where word = ?', (word,))
                    #print 'added row:', cur.fetchone()
                else:
                    print 'Word known. '
                    print repr(row)
                    relList = Splunge(row[0][1])
                    relList.append(relId)
                    print 'adding', word, relList
                    cur.execute('replace into words(word, releases) values (?, ?)',
                            (word, relList))

        except KeyError as e:
            logging.error('Missing field from release '+relId+': '+str(e))


    con.commit()

with sqlite3.connect(dbname, detect_types=sqlite3.PARSE_DECLTYPES) as con:
    cur = con.cursor()
    cur.execute('select * from releases')
    rows = cur.fetchall()
    for row in rows[:10]:
        for e in row:
            if len(repr(e)) > 20:
                print repr(e)[:20] +'..., ',
            else:
                print repr(e) +', ',
        print
    print '...'





