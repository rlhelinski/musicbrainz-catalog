from __future__ import print_function
from __future__ import unicode_literals
import os
import sys
import time
import re
import musicbrainzngs.mbxml as mbxml
import musicbrainzngs.util as mbutil
import musicbrainzngs.musicbrainz as mb
import mbcat.formats
import mbcat.amazonservices
import mbcat.coverart
import mbcat.userprefs
import mbcat.utils
import mbcat.extradata
import shutil
import zipfile
from datetime import datetime
from collections import defaultdict
import progressbar
import logging
_log = logging.getLogger("mbcat")
# for compatibility with Python 3
try:
    import cPickle as pickle
except ImportError:
    import pickle
import zlib

import sqlite3
# Problem: pickle dumps takes unicode strings but returns binary strings
def listAdapter(l):
    return buffer(pickle.dumps(l))

def listConverter(s):
    return pickle.loads(s)

sqlite3.register_adapter(list, listAdapter)
sqlite3.register_converter(str("list"), listConverter)

def sql_list_append(cursor, table_name, key_column, key, value, list_column='releases'):
    """Append to a list in an SQL table."""
    cursor.execute('select '+list_column+' from '+table_name+\
            ' where '+key_column+' = ?', (key,))
    row = cursor.fetchall()
    if not row:
        relList = [value]
    else:
        relList = row[0][0]
        if value not in relList:
            relList.append(value)

    cursor.execute(('replace' if row else 'insert')+
            ' into '+table_name+'('+key_column+', '+list_column+') '
            'values (?, ?)', (key, relList))

def sql_list_remove(cursor, table_name, key_column, key, value, list_column='releases'):
    """Remove an item from a list in an SQL table."""
    cursor.execute('select '+list_column+' from '+table_name+\
            ' where '+key_column+' = ?', (key,))
    row = cursor.fetchall()
    if row:
        relList = row[0][0]
        relList.remove(value)

        if relList:
            cursor.execute('replace into %s (%s, releases) values (?, ?)' % \
                    (table_name, key_column),
                    (key, relList))
        else:
            cursor.execute('delete from %s where %s=?' % \
                    (table_name, key_column),
                    (key,))

def recLengthAsString(recLength):
    if not recLength:
        return '?:??'
    # convert milli-seconds to seconds
    length = float(recLength)/1000
    return ('%d:%02d' % (length/60, length%60))

# For remembering user decision to overwrite existing data
overWriteAll = False

# Have to give an identity for musicbrainzngs
__version__ = '0.2'

mb.set_useragent(
    "musicbrainz-catalog",
    __version__,
    "https://github.com/rlhelinski/musicbrainz-catalog/",
)

# Get the XML parsing exceptions to catch. The behavior changed with Python 2.7
# and ElementTree 1.3.
import xml.etree.ElementTree as etree
from xml.parsers import expat
if hasattr(etree, 'ParseError'):
    ETREE_EXCEPTIONS = (etree.ParseError, expat.ExpatError)
else:
    ETREE_EXCEPTIONS = (expat.ExpatError)

class Catalog(object):

    mbUrl = 'http://'+mb.hostname+'/'
    artistUrl = mbUrl+'artist/'
    labelUrl = mbUrl+'label/'
    releaseUrl = mbUrl+'release/'

    zipReleaseRoot = 'release-id'

    releaseColumns = [
        'id',
        'meta',
        'sortstring',
        'artist',
        'title',
        'date',
        'country',
        'label',
        'catno',
        'barcode',
        'asin',
        'format',
        'metatime',
        'purchases',
        'added',
        'lent',
        'listened',
        'digital',
        'count',
        'comment',
        'rating'
        ]

    def __init__(self, dbPath=None, cachePath=None):
        """Open or create a new catalog"""

        prefPath = os.path.join(os.path.expanduser('~'), '.mbcat')
        self.dbPath = dbPath if dbPath else os.path.join(prefPath, 'mbcat.db')
        self.cachePath = cachePath if cachePath else \
                os.path.join(prefPath, 'cache')

        if not os.path.isdir(prefPath):
            os.mkdir(prefPath)

        self.prefs = mbcat.userprefs.PrefManager()

        # should we connect here, once and for all, or should we make temporary
        # connections to sqlite3?
        if not os.path.isfile(self.dbPath):
            self._createTables()

        _log.info('Using \'%s\' for the catalog database' % self.dbPath)
        _log.info('Using \'%s\' for the file cache path' % self.cachePath)

    def _connect(self):
        # Let's try here for now, just need to make sure we disconnect when this
        # object is deleted.
        return sqlite3.connect(self.dbPath,
                detect_types=sqlite3.PARSE_DECLTYPES)

    def _createTables(self):
        """Create the SQL tables for the catalog. Database is assumed empty."""
        with self._connect() as con:
            cur = con.cursor()

            cur.execute("CREATE TABLE releases("+\
                "id TEXT PRIMARY KEY, "+\
                # metadata from musicbrainz
                # TODO maybe store a dict instead of the XML?
                "meta BLOB, "+\
                "sortstring TEXT, "+\
                "artist TEXT, "+\
                "title TEXT, "+\
                "date TEXT, "+\
                "country TEXT, "+\
                "label TEXT, "+\
                "catno TEXT, "+\
                "barcode TEXT, "+\
                "asin TEXT, "+\
                "format TEXT, "+\
                "metatime FLOAT, "+\
                # now all the extra data
                "purchases LIST, "+\
                "added LIST, "+\
                "lent LIST, "+\
                "listened LIST, "+\
                "digital LIST, "+\
                "count INT, "+\
                "comment TEXT, "+\
                "rating INT)")

            self._createCacheTables(cur)

            con.commit()

    def _createCacheTables(self, cur):
        # tables that map specific things to a list of releases
        for columnName in [
                'word',
                'trackword',
                'discid',
                'barcode',
                'format'
                ]:

            cur.execute('CREATE TABLE '+columnName+'s('+\
                    columnName+' '+
                    ('INT' if columnName is 'barcode' else 'TEXT')+\
                    ' PRIMARY KEY, releases list)')

        cur.execute('CREATE TABLE recordings ('
            'recording TEXT PRIMARY KEY, '
            'title TEXT, '
            'length INTEGER, '
            'releases list)')


    def updateCacheTables(self, rebuild, pbar=None):
        """Use the releases table to populate the derived (cache) tables"""
        if pbar:
            pbar.maxval=len(self)
            pbar.set_status('Building release indexes')
            pbar.start()
        for releaseId in self.getReleaseIds():
            metaXml = self.getReleaseXml(releaseId)
            self.digestReleaseXml(releaseId, metaXml, rebuild=rebuild)
            if pbar:
                pbar.update(pbar.currval + 1)
            yield True
        if pbar:
            pbar.finish()
        yield False

    def rebuildCacheTables(self, pbar=None):
        """Drop the derived tables in the database and rebuild them"""
        if pbar:
            pbar.maxval = 15
            pbar.set_status('Dropping index tables')
            pbar.start()
        with self._connect() as con:
            cur = con.cursor()
            for tab in ['words', 'trackwords', 'recordings', 'discids',
                    'barcodes', 'formats']:
                cur.execute('drop table '+tab)
                pbar.step(1)
            self._createCacheTables(cur)

            # Add the columns if they don't exist
            for column in [
                'artist',
                'title',
                'date',
                'country',
                'label',
                'catno',
                'barcode',
                'asin',
                'format',
                ]:
                try:
                    cur.execute('alter table releases add column '+column+\
                        ' text')
                except sqlite3.OperationalError as e:
                    pass
                pbar.step(1)

        # Rebuild
        return self.updateCacheTables(rebuild=True, pbar=pbar)

    def renameRelease(self, releaseId, newReleaseId):
        self.deleteRelease(releaseId)
        self.addRelease(newReleaseId, olderThan=60)

    def getReleaseIds(self):
        with self._connect() as con:
            cur = con.cursor()
            cur.execute('select id from releases')
            listOfTuples = cur.fetchall()
            # return all of the tuples as a list
            return list(sum(listOfTuples, ()))

    @staticmethod
    def getReleaseDictFromXml(metaxml):
        try:
            metadata = mbxml.parse_message(metaxml)
        except UnicodeError as exc:
            raise ResponseError(cause=exc)
        except Exception as exc:
            if isinstance(exc, ETREE_EXCEPTIONS):
                _log.error("Got some bad XML for %s!", releaseId)
                return
            else:
                raise

        return metadata

    def getReleaseXml(self, releaseId):
        """Return a release's musicbrainz XML metadata"""

        with self._connect() as con:
            cur = con.cursor()
            cur.execute('select meta from releases where id = ?', (releaseId,))
            try:
                releaseXml = zlib.decompress(cur.fetchone()[0])
            except TypeError:
                raise KeyError ('release %s not found' % releaseId)
        return releaseXml

    def getRelease(self, releaseId):
        """Return a release's musicbrainz-ngs dictionary"""

        releaseXml = self.getReleaseXml(releaseId)
        # maybe it would be better to store the release as a serialized dict in
        # the table. Then, we would not need this parsing step

        metadata = self.getReleaseDictFromXml(releaseXml)

        return metadata['release']

    def getReleaseIdsByFormat(self, fmt):
        with self._connect() as con:
            cur = con.cursor()
            cur.execute('select releases from formats where format = ?',
                    (fmt,))
            return cur.fetchall()[0][0]

    def getFormats(self):
        with self._connect() as con:
            cur = con.cursor()
            cur.execute('select format from formats')
            return [t[0] for t in cur.fetchall()]

    def barCodeLookup(self, barcode):
        with self._connect() as con:
            cur = con.cursor()
            cur.execute('select releases from barcodes where barcode = ?',
                    (barcode,))
            result = cur.fetchall()
            if not result:
                raise KeyError('Barcode not found')
            return result[0][0]

    def __len__(self):
        """Return the number of releases in the catalog."""
        with self._connect() as con:
            cur = con.cursor()
            cur.execute('select count(id) from releases')
            return cur.fetchone()[0]

    def __contains__(self, releaseId):
        with self._connect() as con:
            cur = con.cursor()
            cur.execute('select count(id) from releases where id=?',
                    (releaseId,))
            count = cur.fetchone()[0]
        return count > 0

    def getCopyCount(self, releaseId):
        with self._connect() as con:
            cur = con.cursor()
            cur.execute('select count from releases where id=?',
                    (releaseId,))
            return cur.fetchone()[0]

    def setCopyCount(self, releaseId, count):
        with self._connect() as con:
            cur = con.cursor()
            cur.execute('update releases set count=? where id=?',
                    (count, releaseId))
            con.commit()

    def loadReleaseIds(self, pbar=None):
        fileList = os.listdir(self.rootPath)

        if pbar:
            pbar.start()
        if len(fileList) > 0:
            for releaseId in fileList:
                if len(releaseId) == 36:
                    if pbar:
                        pbar.update(pbar.currval + 1)
                    yield releaseId
            if pbar:
                pbar.finish()

    def saveZip(self, zipName='catalog.zip', pbar=None):
        """Exports the database as a ZIP archive"""

        _log.info('Saving ZIP file for catalog to \'%s\'' % zipName)

        if pbar:
            pbar.maxval=len(self)
            pbar.start()
        with zipfile.ZipFile(zipName, 'w', zipfile.ZIP_DEFLATED) as zf:
            for releaseId in self.getReleaseIds():
                zipReleasePath = self.zipReleaseRoot+'/'+releaseId
                zf.writestr(zipReleasePath+'/'+'metadata.xml',
                        self.getReleaseXml(releaseId))

                # add coverart if is cached
                # use store method because JPEG is already compressed
                coverArtPath = self._getCoverArtPath(releaseId)
                if os.path.isfile(coverArtPath):
                    zf.write(coverArtPath,
                            zipReleasePath+'/cover.jpg',
                            zipfile.ZIP_STORED)

                #zf.writestr('extra.xml', \
                #    self.extraIndex[releaseId].toString())
                ed = self.getExtraData(releaseId)
                zf.writestr(zipReleasePath+'/extra.xml',
                        ed.toString())

                if pbar:
                    pbar.update(pbar.currval + 1)
            if pbar:
                pbar.finish()

    def loadZip(self, zipName='catalog.zip', pbar=None):
        """Imports the data from a ZIP archive into the database"""

        _log.info('Loading ZIP file into catalog from \'%s\'' % zipName)

        if pbar:
            pbar.maxval=len(self)
            pbar.start()
        with zipfile.ZipFile(zipName, 'r') as zf:
            for fInfo in zf.infolist():
                try:
                    rootPath, releaseId, fileName = fInfo.filename.split('/')
                except ValueError:
                    # this must not be a file that is part of a release
                    continue

                if rootPath!= self.zipReleaseRoot:
                    # must not be part of a release, do nothing for now
                    continue

                if len(releaseId) != 36:
                    _log.error('Release ID in path \'%s\' not expected length '
                            '(36)' % releaseId)
                    continue

                if fileName == 'metadata.xml':
                    self.digestReleaseXml(releaseId, zf.read(fInfo))

                if fileName == 'extra.xml':
                    ed = mbcat.extradata.ExtraData(releaseId)
                    ed.loads(zf.read(fInfo))
                    self.digestExtraData(releaseId, ed)

                if fileName == 'cover.jpg':
                    coverArtPath = self._getCoverArtPath(releaseId)
                    with file(coverArtPath, 'w') as f:
                        f.write(zf.read(fInfo))

                if pbar:
                    pbar.update(pbar.currval + 1)
            if pbar:
                pbar.finish()

    @staticmethod
    def processWords(words, field, d):
        if field in d:
            words.update(re.findall(r"[\w'.]+", d[field].lower(), re.UNICODE))
        elif field != 'disambiguation':
            _log.warning('Missing field from release '+relId+': '+field)

    @staticmethod
    def getReleaseWords(rel):
        words = set()
        relId = rel['id']

        for field in ['title', 'artist-credit-phrase', 'disambiguation']:
            mbcat.Catalog.processWords(words, field, rel)
        for credit in rel['artist-credit']:
            for field in ['sort-name', 'disambiguation', 'name']:
                if field in credit:
                    mbcat.Catalog.processWords(words, field, credit)

        return words

    @staticmethod
    def getReleaseTracks(rel):
        # Format of track (recording) title list
        # r['medium-list'][0]['track-list'][0]['recording']['title']
        for medium in rel['medium-list']:
            for track in medium['track-list']:
                yield track

    def digestTrackWords(self, rel, cur, actionFun=sql_list_append):
        releaseTrackWords = set()
        relId = rel['id']

        for track in mbcat.Catalog.getReleaseTracks(rel):
            if 'recording' in track and 'title' in track['recording']:
                trackWords = set()
                mbcat.Catalog.processWords(trackWords, 'title',
                    track['recording'])
                for word in trackWords:
                    actionFun(cur, 'trackwords', 'trackword',
                        word, track['recording']['id'])
                releaseTrackWords = releaseTrackWords.union(trackWords)
                actionFun(cur, 'recordings', 'recording',
                    track['recording']['id'], relId)
                cur.execute('update recordings set title=?,length=? '
                    'where recording=?', (track['recording']['title'],
                        track['recording']['length'] if
                            'length' in track['recording'] else -1,
                        track['recording']['id']))

    def unDigestTrackWords(self, rel, cur):
        self.digestTrackWords(rel, cur, actionFun=sql_list_remove)

    @mbcat.utils.deprecated
    def mapWordsToRelease(self, words, releaseId):
        word_set = set(words)
        for word in word_set:
            if word in self.wordMap:
                self.wordMap[word].append(releaseId)
            else:
                self.wordMap[word] = [releaseId]

    # TODO this is used externally, but has an underscore prefix
    def _search(self, query, table='words', keycolumn='word'):
        query_words = query.lower().split(' ')
        matches = set()
        with self._connect() as con:
            cur = con.cursor()
            for word in query_words:
                cur.execute('select releases from %s where %s = ?' % \
                        (table, keycolumn),
                        (word,))
                # get the record, there should be one or none
                fetched = cur.fetchone()
                # if the word is in the table
                if fetched:
                    # for the first word
                    if word == query_words[0]:
                        # use the whole set of releases that have this word
                        matches = set(fetched[0])
                    else:
                        # intersect the releases that have this word with the
                        # current release set
                        matches = matches & set(fetched[0])
                else:
                    # this word is not contained in any releases and therefore
                    # no releases match
                    matches = set()
                    break

        return matches

    def searchTrackWords(self, query):
        return self._search(query, table='trackwords', keycolumn='trackword')

    def recordingGetReleases(self, recordingId):
        with self._connect() as con:
            cur = con.cursor()
            cur.execute('select releases from recordings where recording = ?',
                    (recordingId,))
            # get the record, there should be one or none
            fetched = cur.fetchone()

        # remember that the field is a list type
        return fetched[0]

    def formatDiscInfo(self, releaseId):
        release = self.getRelease(releaseId)
        return ' '.join( [
                releaseId, ':', \
                mbcat.utils.formatSortCredit(release), '-', \
                (release['date'] if 'date' in release else ''), '-', \
                release['title'], \
                '('+release['disambiguation']+')' if 'disambiguation' in \
                    release else '', \
                '['+str(mbcat.formats.getReleaseFormat(release))+']', \
                ] )

    @staticmethod
    @mbcat.utils.deprecated
    def formatRecordingLength(length):
        seconds = float(length)/1000 if length else None
        return (('%d:%02d' % (seconds/60, seconds%60)) \
            if seconds else '?:??')

    def formatRecordingInfo(self, recordingId):
        with self._connect() as con:
            cur = con.cursor()
            cur.execute('select title,length from recordings '
                'where recording=?', (recordingId,))
            recordingRow = cur.fetchall()[0]

        return '%s: %s (%s)' % (recordingId, recordingRow[0],
            mbcat.Catalog.formatRecordingLength(recordingRow[1]))

    def getRecordingTitle(self, recordingId):
        with self._connect() as con:
            cur = con.cursor()
            cur.execute('select title from recordings '
                'where recording=?', (recordingId,))
            return cur.fetchone()[0]

    def getRecordingLength(self, recordingId):
        with self._connect() as con:
            cur = con.cursor()
            cur.execute('select length from recordings '
                'where recording=?', (recordingId,))
            return cur.fetchone()[0]

    @staticmethod
    def getSortStringFromRelease(release):
        return ' - '.join ( [ \
                mbcat.utils.formatSortCredit(release), \
                release['date'] if 'date' in release else '', \
                release['title'] + \
                (' ('+release['disambiguation']+')' if 'disambiguation' in \
                    release else ''), \
                ] )

    def getReleaseSortStr(self, releaseId):
        """Return a string by which a release can be sorted."""

        with self._connect() as con:
            cur = con.cursor()
            cur.execute('select sortstring from releases where id = ?',
                    (releaseId,))
            sortstring = cur.fetchone()[0]

            if not sortstring:
                # cache it for next time
                sortstring = self.getSortStringFromRelease(
                        self.getRelease(releaseId))
                cur.execute('update releases set sortstring=? where id=?',
                        (sortstring, releaseId))
                cur.commit()

        return sortstring


    def getSortedList(self, matchFmt=None):
        relIds = self.getReleaseIdsByFormat(matchFmt.__name__) if matchFmt \
                else self.getReleaseIds()

        sortKeys = [(relId, self.getReleaseSortStr(relId)) for relId in relIds]

        return sorted(sortKeys, key=lambda sortKey: sortKey[1].lower())

    def getSortNeighbors(self, releaseId, neighborHood=5, matchFormat=False):
        """
        Print release with context (neighbors) to assist in sorting and storage
        of releases.
        """

        if matchFormat:
            try:
                sortedList = self.getSortedList(\
                    mbcat.formats.getReleaseFormat(\
                        self.getRelease(releaseId)).__class__)
            except KeyError as e:
                _log.warning("Sorting release " + releaseId + " with no format"
                        " into a list of all releases.")
                sortedList = self.getSortedList()
        else:
            sortedList = self.getSortedList()

        index = sortedList.index((releaseId,
                self.getReleaseSortStr(releaseId)))
        neighborhoodIndexes = range(max(0,index-neighborHood),
                min(len(sortedList), index+neighborHood))
        return (index,
                zip(neighborhoodIndexes,
                        [sortedList[i] for i in neighborhoodIndexes]))

    def getWordCount(self):
        """Fetch the number of words in the release search word table."""
        with self._connect() as con:
            cur = con.cursor()
            cur.execute('select count(word) from words')
            return cur.fetchone()[0]

    def getTrackWordCount(self):
        """Fetch the number of words in the track search word table."""
        with self._connect() as con:
            cur = con.cursor()
            cur.execute('select count(trackword) from trackwords')
            return cur.fetchone()[0]

    def getComment(self, releaseId):
        """Get the comment for a release (if any)."""
        with self._connect() as con:
            cur = con.cursor()
            cur.execute('select comment from releases where id=?',
                (releaseId,))
            return cur.fetchone()[0]

    def setComment(self, releaseId, comment):
        """Set the comment for a release."""
        with self._connect() as con:
            cur = con.cursor()
            cur.execute('update releases set comment=? where id=?',
                (comment, releaseId))
            con.commit()

    def getDigitalPaths(self, releaseId):
        with self._connect() as con:
            cur = con.cursor()
            cur.execute('select digital from releases where id=?',
                    (releaseId,))
            return cur.fetchall()[0][0]

    def addDigitalPath(self, releaseId, path):
        existingPaths = self.getDigitalPaths(releaseId)
        with self._connect() as con:
            cur = con.cursor()
            cur.execute('update releases set digital=? where id=?',
                    (existingPaths+[path],releaseId))
            con.commit()

    def getAddedDates(self, releaseId):
        with self._connect() as con:
            cur = con.cursor()
            cur.execute('select added from releases where id=?', (releaseId,))
            return cur.fetchall()[0][0]

    def addAddedDate(self, releaseId, date):
        # input error checking
        if (type(date) != float):
            try:
                date = float(date)
            except ValueError as e:
                raise ValueError('Date object must be a floating-point number')

        existingDates = self.getAddedDates(releaseId)
        with self._connect() as con:
            cur = con.cursor()
            cur.execute('update releases set added=? where id=?',
                (existingDates+[date],releaseId))
            con.commit()

    def getLendEvents(self, releaseId):
        with self._connect() as con:
            cur = con.cursor()
            cur.execute('select lent from releases where id=?', (releaseId,))
            return cur.fetchall()[0][0]

    def addLendEvent(self, releaseId, event):
        # Some precursory error checking
        if not isinstance(event, mbcat.extradata.CheckOutEvent) and \
            not isinstance(event, mbcat.extradata.CheckInEvent):
            raise ValueError ('Wrong type for lend event')
        existingEvents = self.getLendEvents(releaseId)
        with self._connect() as con:
            cur = con.cursor()
            cur.execute('update releases set lent=? where id=?',
                (existingEvents+[event],releaseId))
            con.commit()

    def getRating(self, releaseId):
        with self._connect() as con:
            cur = con.cursor()
            cur.execute('select rating from releases where id=?', (releaseId,))
            result = cur.fetchall()
        return result[0][0] if result else None

    def setRating(self, releaseId, rating):
        with self._connect() as con:
            cur = con.cursor()
            cur.execute('update releases set rating=? where id=?',
                    (rating, releaseId))
            con.commit()

    def getPurchases(self, releaseId):
        with self._connect() as con:
            cur = con.cursor()
            cur.execute('select purchases from releases where id=?',
                    (releaseId,))
            result = cur.fetchone()
            return result[0] if result else []

    def addPurchase(self, releaseId, purchaseObj):
        # Some precursory error checking
        if not isinstance(purchaseObj, mbcat.extradata.PurchaseEvent):
            raise ValueError ('Wrong type for purchase event')
        existingEvents = self.getLendEvents(releaseId)
        with self._connect() as con:
            cur = con.cursor()
            cur.execute('update releases set purchases=? where id=?',
                (existingEvents+[purchaseObj],releaseId))
            con.commit()

    def getListenDates(self, releaseId):
        with self._connect() as con:
            cur = con.cursor()
            cur.execute('select listened from releases where id=?',
                    (releaseId,))
            return cur.fetchall()[0][0]

    def addListenDate(self, releaseId, date):
        # Some precursory error checking
        if not isinstance(date, float):
            raise ValueError ('Wrong type for date argument')
        existingDates = self.getListenDates(releaseId)
        with self._connect() as con:
            cur = con.cursor()
            cur.execute('update releases set listened=? where id=?',
                (existingDates+[date],releaseId))
            con.commit()

    def getExtraData(self, releaseId):
        """Put together all of the metadata added by mbcat. This might be
        removed in a later release, only need it when upgrading from 0.1."""
        with self._connect() as con:
            cur = con.cursor()
            cur.execute('select purchases,added,lent,listened,digital,count,'
                    'comment,rating from releases where id=?', (releaseId,))
            purchases,added,lent,listened,digital,count,comment,rating = \
                    cur.fetchall()[0]

        ed = mbcat.extradata.ExtraData(releaseId)
        ed.purchases = purchases
        ed.addDates = added
        ed.lendEvents = lent
        ed.listenEvents = listened
        ed.digitalPaths = digital
        # TODO no place for count yet in extradata
        ed.comment = comment
        ed.rating = rating

        return ed

    def digestExtraData(self, releaseId, ed):
        """Take an ExtraData object and update the metadata in the catalog for
        a release"""
        # TODO there is no attempt to merge information that already exists in
        # the database
        with self._connect() as con:
            cur = con.cursor()
            cur.execute('update releases set '+\
                    'purchases=?, added=?, lent=?, listened=?, digital=?, '+\
                    'comment=?, rating=? where id=?',
                    (ed.purchases,
                    ed.addDates,
                    ed.lendEvents,
                    ed.listenEvents,
                    ed.digitalPaths,
                    # TODO no place for count yet in extradata
                    ed.comment,
                    ed.rating,
                    # don't forget the 'where' clause
                    releaseId))
            con.commit()

    def report(self):
        """Print some statistics about the catalog as a sanity check."""

        print("\n%d releases" % len(self))
        print("%d words in release search table" % self.getWordCount())
        print("%d words in track search table" % self.getTrackWordCount())

    def makeHtml(self, fileName=None, pbar=None):
        """
        Write HTML representing the catalog to a file
        """

        def fmt(s):
            return s.encode('ascii', 'xmlcharrefreplace').decode()

        if not fileName:
            fileName = os.path.join(self.prefs.htmlPubPath, "catalog.html")

        _log.info('Writing HTML to \'%s\'' % fileName)

        if pbar:
            pbar.maxval=len(self)
            pbar.start()

        htf = open(fileName, 'wt')

        # TODO need a more extensible solution for replacing symbols in this
        # template file
        with open ('mbcat/catalog_html.template') as template_file:
            htf.write(template_file.read())

        formatsBySize = sorted(self.getFormats(),
                key=lambda s: mbcat.formats.getFormatObj(s))

        htf.write('<a name="top">\n')
        htf.write('<div id="toc">\n')
        htf.write('<div id="toctitle">\n')
        htf.write('<h2>Contents</h2>\n')
        htf.write('<span class="toctoggle">&nbsp;[<a href="#" class="internal"'
                ' id="togglelink">hide</a>]&nbsp;</span>\n</div>\n')
        htf.write('<ul>\n')
        for releaseType in formatsBySize:
            htf.write('\t<li><a href="#'+releaseType+'">'+\
                releaseType+'</a></li>\n')
        htf.write('</ul>\n')
        htf.write('</div>\n')

        for releaseType in formatsBySize:
            sortedList = self.getSortedList(
                    mbcat.formats.getFormatObj(releaseType).__class__)
            if len(sortedList) == 0:
                continue
            htf.write("<h2><a name=\""+str(releaseType)+"\">" + \
                    str(releaseType) + (" (%d Releases)" %
            len(sortedList)) + " <a href=\"#top\">top</a></h2>\n")

            htf.write("<table class=\"formattable\">\n")
            mainCols = ['Artist',
                'Release Title',
                'Date',
                'Country',
                'Label',
                'Catalog #',
                'Barcode',
                'ASIN',
                ]
            htf.write('<tr>\n' + \
                '\n'.join(['<th>'+name+'</th>' for name in mainCols]) +\
                '\n</tr>\n')

            for (releaseId, releaseSortStr) in sortedList:
                rel = self.getRelease(releaseId)

                if pbar:
                    pbar.update(pbar.currval + 1)

                #coverartUrl = mbcat.amazonservices.getAsinImageUrl(rel.asin,
                #        mbcat.amazonservices.AMAZON_SERVER["amazon.com"], 'S')
                # Refer to local copy instead
                imgPath = self._getCoverArtPath(releaseId)
                coverartUrl = imgPath if os.path.isfile(imgPath) else None

                htf.write("<tr class=\"releaserow\">\n")
                htf.write("<td>" + ''.join( [\
                    credit if type(credit)==str else \
                    "<a href=\""+self.artistUrl+credit['artist']['id']+"\">"+\
                    fmt(credit['artist']['name'])+\
                    "</a>" for credit in rel['artist-credit'] ] ) + "</td>\n")
                htf.write("<td><a href=\""+self.releaseUrl+rel['id']+"\"" + \
                    ">"+fmt(rel['title'])\
                    +(' (%s)' % fmt(rel['disambiguation']) \
                        if 'disambiguation' in rel and rel['disambiguation'] \
                        else '')\
                    + "</a></td>\n")
                htf.write("<td>"+(fmt(rel['date']) if 'date' in rel else '') +\
                        "</td>\n")
                htf.write("<td>"+(fmt(rel['country']) \
                    if 'country' in rel else '')+"</td>\n")
                htf.write("<td>"+', '.join([\
                    "<a href=\""+self.labelUrl+info['label']['id']+"\">"+\
                    fmt(info['label']['name'])+\
                    "</a>" if 'label' in info else '' \
                    for info in rel['label-info-list']])+"</td>\n")
                # TODO handle empty strings here (remove from this list before
                # joining)
                htf.write("<td>"+', '.join([\
                    fmt(info['catalog-number']) if \
                    'catalog-number' in info else '' \
                    for info in rel['label-info-list']])+"</td>\n")
                htf.write("<td>"+\
                    ('' if 'barcode' not in rel else \
                    rel['barcode'] if rel['barcode'] else
                    '[none]')+"</td>\n")
                htf.write("<td>"+("<a href=\"" + \
                    mbcat.amazonservices.getAsinProductUrl(rel['asin']) + \
                    "\">" + rel['asin'] + "</a>" if 'asin' in rel else '') + \
                    "</td>\n")
                htf.write("</tr>\n")
                htf.write("<tr class=\"detailrow\">\n")
                htf.write("<td colspan=\""+str(len(mainCols))+"\">\n")
                htf.write("<div class=\"togglediv\">\n")
                htf.write('<table class="releasedetail">\n')
                htf.write('<tr>\n')
                detailCols = [
                    'Cover Art',
                    'Track List',
                    'Digital Paths',
                    'Date Added',
                    'Format(s)',
                    ]
                for name in detailCols:
                    htf.write('<th>'+fmt(name)+'</th>\n')
                htf.write('</tr>\n<tr>\n')
                htf.write('<td>'+('<img class="coverart" src="'+ coverartUrl +\
                        '">' if coverartUrl else '')+'</td>\n')
                htf.write('<td>\n')
                htf.write('<table class="tracklist">\n')
                for medium in rel['medium-list']:
                    for track in medium['track-list']:
                        rec = track['recording']
                        length = mbcat.Catalog.formatRecordingLength(
                            rec['length'] if 'length' in rec else None)
                        htf.write('<tr><td class="time">'+
                            fmt(rec['title']) + '</td><td>' + length + \
                            '</td></tr>\n')
                htf.write('</table>\n</td>\n')
                htf.write('<td>\n<table class="pathlist">'+\
                    ''.join([\
                        ('<tr><td><a href="'+fmt(path)+'">'+fmt(path)+\
                            '</a></td></tr>\n')\
                        for path in self.getDigitalPaths(releaseId)])+\
                    '</table>\n</td>\n')
                htf.write(\
                    "<td>"+(datetime.fromtimestamp( \
                        self.getAddedDates(releaseId)[0] \
                        ).strftime('%Y-%m-%d') if \
                    len(self.getAddedDates(releaseId)) else '')+"</td>\n")
                htf.write("<td>"+' + '.join([(medium['format'] \
                        if 'format' in medium else '(unknown)') \
                        for medium in rel['medium-list']])+"</td>\n")

                htf.write('</tr>\n')
                htf.write("</table>\n</div>\n</td>\n</tr>\n")

            htf.write("</table>")

        htf.write("<p>%d releases</p>" % len(self))

        # TODO this will become part of the template
        htf.write("""</body>
</html>""")
        htf.close()

        if pbar:
            pbar.finish()

    def fetchReleaseMetaXml(self, releaseId):
        """Fetch release metadata XML from musicbrainz"""
        # get_release_by_id() handles throttling on its own
        _log.info('Fetching metadata for ' + releaseId)
        mb.set_parser(mb.mb_parser_null)
        xml = mb.get_release_by_id(releaseId, includes=['artists', 'discids',
                'media', 'labels', 'recordings'])
        mb.set_parser()
        return xml

    @mbcat.utils.deprecated
    def writeXml(self, releaseId, metaData):
        global overWriteAll

        xmlPath = self._get_xml_path(releaseId)

        if not os.path.isdir(os.path.dirname(xmlPath)):
            os.mkdir(os.path.dirname(xmlPath))

        if (os.path.isfile(xmlPath) and not overWriteAll):
            print(xmlPath, "already exists. Continue? [y/a/N] ", end="")
            response = sys.stdin.readline().strip()
            if (not response or response[0] not in ['y', 'a']):
                return 1
            elif (response[0] == 'a'):
                overWriteAll = True

        _log.info("Writing metadata to '%s'", xmlPath)
        xmlf = open(xmlPath, 'wb')
        xml_writer = wsxml.MbXmlWriter()
        xml_writer.write(xmlf, metaData)
        xmlf.close()

        return 0

    @mbcat.utils.deprecated
    def fixMeta(self, discId, releaseId):
        results_meta = self.fetchReleaseMetaXml(releaseId)

        self.writeXml(discId, results_meta)

    @mbcat.utils.deprecated
    def loadMetaData(self, releaseId):
        """Load metadata from disk"""
        xmlPath = self._get_xml_path(releaseId)
        if (not os.path.isfile(xmlPath)):
            _log.error("No XML metadata for %s", releaseId)
            return None
        with open(xmlPath, 'r') as xmlf:
            metaxml = xmlf.read()

        return self.getReleaseDictFromXml(metaxml)['release']

    def digestReleaseXml(self, releaseId, metaXml, rebuild=False):
        """Update the appropriate data structes for a new release."""
        relDict = self.getReleaseDictFromXml(metaXml)

        exists = releaseId in self
        now = time.time()

        with self._connect() as con:
            cur = con.cursor()

            if not exists:
                # Update releases table
                newColumns = [
                    'id',
                    'meta',
                    'metatime',
                    'added',
                    'count',
                    ]

                try:
                    cur.execute('insert into releases (' + \
                            ','.join(newColumns) + \
                            ') values (' + \
                            ','.join(['?']*len(newColumns)) + \
                            ')',
                            (
                            releaseId,
                            buffer(zlib.compress(metaXml)),
                            now,
                            [now],
                            1, # set count to 1 for now
                            )
                    )
                except sqlite3.IntegrityError as e:
                    _log.error('Release already exists in catalog.')
            elif not rebuild:
                # Remove references to this release from the words, barcodes,
                # etc. tables so we can add the correct ones later
                self.unDigestRelease(releaseId, delete=False)
                cur.execute('update releases set meta=?,sortstring=?,'
                        'metatime=? where id=?',
                        (buffer(zlib.compress(metaXml)),
                        self.getSortStringFromRelease(relDict['release']),
                        now,
                        releaseId
                        )
                    )

            metaColumns = [
                ('sortstring', self.getSortStringFromRelease(relDict['release'])),
                ('artist', mbcat.catalog.getArtistSortPhrase(relDict['release'])),
                ('title', relDict['release']['title']),
                ('date', (relDict['release']['date'] if 'date' in relDict['release'] else '')),
                ('country', (relDict['release']['country'] if 'country' in relDict['release'] else '')),
                ('label', self.fmtLabel(relDict['release'])),
                ('catno', self.fmtCatNo(relDict['release'])),
                ('barcode', (relDict['release']['barcode'] if 'barcode' in relDict['release'] else '')),
                ('asin', (relDict['release']['asin'] if 'asin' in relDict['release'] else '')),
                ('format', mbcat.formats.getReleaseFormat(relDict['release'])\
                    .name()),
                ]

            cur.execute('update releases set '+\
                ','.join([key+'=?' for key,val in metaColumns])+\
                ' where id=?',
                [val for key,val in metaColumns] + [releaseId]
                )

            # Update words table
            rel_words = self.getReleaseWords(relDict['release'])
            for word in rel_words:
                sql_list_append(cur, 'words', 'word', word, releaseId)

            # Update words -> (word, recordings) and
            # recordings -> (recording, releases)
            self.digestTrackWords(relDict['release'], cur)

            # Update barcodes -> (barcode, releases)
            if 'barcode' in relDict['release'] and \
                    relDict['release']['barcode']:
                sql_list_append(cur, 'barcodes', 'barcode',
                        relDict['release']['barcode'], releaseId)

            # Update discids -> (discid, releases)
            for medium in relDict['release']['medium-list']:
                for disc in medium['disc-list']:
                    sql_list_append(cur, 'discids', 'discid', disc['id'],
                            releaseId)

            # Update formats -> (format, releases)
            fmt = mbcat.formats.getReleaseFormat(relDict['release'])\
                .name()
            sql_list_append(cur, 'formats', 'format', fmt, releaseId)

            con.commit()

    def unDigestRelease(self, releaseId, delete=True):
        """Remove all references to a release from the data structures.
        Optionally, leave the release in the releases table. """
        relDict = self.getRelease(releaseId)

        with self._connect() as con:
            cur = con.cursor()

            if delete:
                # Update releases table
                cur.execute('delete from releases where id = ?', (releaseId,))

            # Update words table
            rel_words = self.getReleaseWords(relDict)
            for word in rel_words:
                sql_list_remove(cur, 'words', 'word', word, releaseId)

            # Update words -> (word, recordings) and
            # recordings -> (recording, releases)
            self.unDigestTrackWords(relDict, cur)

            # Update barcodes -> (barcode, releases)
            if 'barcode' in relDict and relDict['barcode']:
                sql_list_remove(cur, 'barcodes', 'barcode', relDict['barcode'],
                        releaseId)

            # Update discids -> (discid, releases)
            for medium in relDict['medium-list']:
                for disc in medium['disc-list']:
                    sql_list_remove(cur, 'discids', 'discid', disc['id'],
                            releaseId)

            # Update formats -> (format, releases)
            fmt = mbcat.formats.getReleaseFormat(relDict).name()
            sql_list_remove(cur, 'formats', 'format', fmt, releaseId)

            con.commit()

    def fmtArtist(self, release):
        return ''.join([(cred['artist']['name'] \
            if isinstance(cred, dict) else cred)
            for cred in release['artist-credit']])

    def fmtLabel(self, rel):
        if 'label-info-list' not in rel:
            return ''
        return ', '.join([
            (info['label']['name'] if 'label' in info else '')
            for info in rel['label-info-list']])

    def fmtCatNo(self, rel):
        if 'label-info-list' not in rel:
            return ''
        return ', '.join([
            (info['catalog-number'] if 'catalog-number' in info else '')
            for info in rel['label-info-list']])

    def getArtistPathVariations(self, release):
        return set([
                # the non-sorting-friendly string
                release['artist-credit-phrase'],
                # if just the first artist is used
                release['artist-credit'][0]['artist']['sort-name'],
                # if just the first artist is used, sort-friendly
                release['artist-credit'][0]['artist']['name'],
                # the sort-friendly string with all artists credited
                mbcat.catalog.getArtistSortPhrase(release)
                ])

    @staticmethod
    def getTitlePathVariations(release):
        s = set()
        s.add(release['title'])
        if 'disambiguation' in release:
            s.add(release['disambiguation'])
            s.add(release['title']+' ('+release['disambiguation']+')')
        return s

    def getPathAlNumPrefixes(self, path):
        """Returns a set of prefixes used for directory balancing"""
        return set([
                '', # in case nothing is used
                path[0].lower(), # most basic implementation
                path[0:1].lower(), # have never seen this
                (path[0]+'/'+path[0:2]).lower(), # used by Wikimedia
                ])

    def getDigitalPathVariations(self, root, release):
        for artistName in self.getArtistPathVariations(release):
            for prefix in self.getPathAlNumPrefixes(artistName):
                artistPath = os.path.join(root, prefix, artistName)
                if os.path.isdir(artistPath):
                    for titleName in self.getTitlePathVariations(release):
                        yield os.path.join(artistPath, titleName)
                else:
                    _log.debug(artistPath+' does not exist')

    def searchDigitalPaths(self, releaseId='', pbar=None):
        """Search for files for a release in all locations and with variations
        """
        releaseIdList = [releaseId] if releaseId else self.getReleaseIds()

        if pbar:
            pbar.maxval = len(self)*len(self.prefs.pathRoots)
            pbar.start()
        # TODO need to be more flexible in capitalization and re-order of words
        for path in self.prefs.pathRoots:
            _log.info("Searching '%s'"%path)
            for relId in releaseIdList:
                rel = self.getRelease(relId)
                if pbar:
                    pbar.update(pbar.currval + 1)

                # Try to guess the sub-directory path
                for titlePath in self.getDigitalPathVariations(path, rel):
                    if os.path.isdir(titlePath):
                        _log.info('Found '+relId+' at '+titlePath)
                        self.addDigitalPath(relId, titlePath)
                    else:
                        _log.debug('Did not find '+relId+' at '+titlePath)
        if pbar:
            pbar.finish()

        if releaseId and not self.extraIndex[relId].digitalPaths:
            _log.warning('No digital paths found for '+releaseId)

    def getDigitalPath(self, releaseId, pathSpec=None):
        """Returns the file path for a release given a specific release ID and
        a path specification string (mbcat.digital)."""
        if not pathSpec:
            pathSpec = self.prefs.defaultPathSpec
        return mbcat.digital.DigitalPath(pathSpec).\
                toString(self.getRelease(releaseId))

    def fixDigitalPath(self, releaseId, digitalPathRoot=None):
        """This function moves a digital path to the correct location, which is
        specified by a path root string"""
        pathSpec = self.prefs.pathFmts[digitalPathRoot] \
            if digitalPathRoot else \
            self.prefs.defaultPathSpec
        if not digitalPathRoot:
            raise NotImplemented('You need to specify a digital path root')

        assert digitalPathRoot in self.prefs.pathRoots
        pathFmt = self.prefs.pathFmts[digitalPathRoot]
        correctPath = self.getDigitalPath(releaseId, pathFmt)
        for path in self.getDigitalPaths(releaseId):
            path = os.path.join(digitalPathRoot, DigitalPath(pathFmt))
            if path != correctPath:
                _log.info('Moving "%s" to "%s"' % (path, correctPath))
                shutil.move(path, correctPath)

    def getMetaTime(self, releaseId):
        with self._connect() as con:
            cur = con.cursor()
            cur.execute('select metatime from releases where id = ?',
                (releaseId,))
            return cur.fetchone()

    def addRelease(self, releaseId, olderThan=0):
        """
        Get metadata XML from MusicBrainz and add to or refresh the catalog.
        """

        releaseId = mbcat.utils.getReleaseIdFromInput(releaseId)
        if releaseId in self:
            _log.info("Release %s is already in catalog." % releaseId)
        metaTime = self.getMetaTime(releaseId)
        if (metaTime and (metaTime[0] > (time.time() - olderThan))):
            _log.info("Skipping fetch of metadata for %s because it is recent",
                    releaseId)
            return 0

        metaXml = self.fetchReleaseMetaXml(releaseId)
        self.digestReleaseXml(releaseId, metaXml)

    def deleteRelease(self, releaseId):
        releaseId = mbcat.utils.getReleaseIdFromInput(releaseId)
        self.unDigestRelease(releaseId)

    def refreshAllMetaData(self, olderThan=0, pbar=None):
        for releaseId in self.loadReleaseIds(pbar):
            _log.info("Refreshing %s", releaseId)
            self.addRelease(releaseId, olderThan)

    def checkReleases(self):
        """
        Check releases for ugliness such as no barcode, no release format, etc.
        For now, this creates warnings in the log.
        """
        for releaseId in self.getReleaseIds():
            release = self.getRelease(releaseId)
            if 'date' not in release or not release['date']:
                _log.warning("No date for " + releaseId)
            if 'barcode' not in release or not release['barcode']:
                _log.warning("No barcode for " + releaseId)
            for medium in release['medium-list']:
                if 'format' not in medium or not medium['format']:
                    _log.warning("No format for a medium of " + releaseId)

    def _getCoverArtPath(self, releaseId):
        return os.path.join(self.cachePath, releaseId[0], releaseId[0:2],
                releaseId, 'cover.jpg')

    def getCoverArt(self, releaseId, maxage=60*60):
        release = self.getRelease(releaseId)
        imgPath = self._getCoverArtPath(releaseId)
        if os.path.isfile(imgPath) and os.path.getmtime(imgPath) > \
                time.time() - maxage:
            _log.info("Already have cover art for " + releaseId + ", skipping")
            return

        try:
            meta = mbcat.coverart.getCoverArtMeta(releaseId)
            mbcat.coverart.saveCoverArt(meta, imgPath)

        except mb.ResponseError as e:
            _log.warning('No cover art for ' + releaseId +
                    ' available from Cover Art Archive')

            if 'asin' in release:
                _log.info('Trying to fetch cover art from Amazon instead')
                mbcat.amazonservices.saveImage(release['asin'],
                        mbcat.amazonservices.AMAZON_SERVER["amazon.com"],
                        imgPath)
            else:
                _log.warning('No ASIN for '+releaseId+
                        ', cannot fetch from Amazon.')

    def refreshAllCoverArt(self, maxage=60*60*24):
        for releaseId in self.getReleaseIds():
            self.getCoverArt(releaseId, maxage=maxage)

    def checkLevenshteinDistances(self, pbar=None):
        """
        Compute the Levenshtein (edit) distance of each pair of releases.

        Returns a sorted list of the most similar releases
        """
        import Levenshtein
        dists = []

        if pbar:
            pbar.maxval = (float(len(self)**2) - float(len(self)))/2
            pbar.start()
        for leftIdx in range(len(self)):
            for rightIdx in range(leftIdx, len(self)):
                if  leftIdx == rightIdx :
                    continue
                leftId = self.getReleaseIds()[leftIdx]
                rightId = self.getReleaseIds()[rightIdx]
                dist = Levenshtein.distance(self.getReleaseSortStr(leftId),
                        self.getReleaseSortStr(rightId))

                dists.append((dist,leftId, rightId))
                if pbar:
                    pbar.update(pbar.currval + 1)
        if pbar:
            pbar.finish()

        return sorted(dists, key=lambda sortKey: sortKey[0])

    def syncCollection(self, colId):
        """
        Synchronize the catalog with a MusicBrainz collection.

        For now, only adds releases from the catalog to the collection
        if they do not already exist in the collection.

        In the future, should also reconcile releases in the collection
        that are not in the catalog.
        """
        # this is a hack so that the progress will appear immediately
        import sys
        sys.stdout.write('Fetching list of releases in collection...')
        sys.stdout.flush()
        count = 0
        colRelIds = []
        while True:
            result = mb.get_releases_in_collection(colId, limit=25,
                    offset=count)
            col = result['collection']
            relList = col['release-list']
            if len(relList) == 0:
                break
            count += len(relList)
            sys.stdout.write('.')
            sys.stdout.flush()
            for rel in relList:
                colRelIds.append(rel['id'])

        #colRelList = mb.get_releases_in_collection(colId)
        print('OK')
        print('Found %d / %d releases.' % (len(colRelIds), len(self)))

        relIdsToAdd = list(set(self.getReleaseIds()) - set(colRelIds))

        print('Going to add %d releases to collection...' % len(relIdsToAdd))
        for relIdChunk in mbcat.utils.chunks(relIdsToAdd, 100):
            mb.add_releases_to_collection(colId, relIdChunk)
        print('DONE')

    def makeLabelTrack(self, releaseId, outPath='Audacity Label Track.txt'):
        """Useful for importing into Audacity."""
        rel = self.getRelease(releaseId)
        with open(outPath, 'w') as f:
            pos = 0.0
            for medium in rel['medium-list']:
                for track in medium['track-list']:
                    rec = track['recording']
                    if 'length' not in rec:
                        _log.warning('Track '+track['number']+
                                ' length is empty in '+releaseId)
                    length = float(rec['length'])/1000 \
                            if 'length' in rec else 2*60
                    line = '%.6f\t%.6f\t%s\n' % (pos, pos+length, rec['title'])
                    try:
                        f.write(line)
                    except ValueError:
                        # Python2 compatibility
                        f.write(line.encode('utf8'))
                    pos += length
        _log.info('Wrote label track for '+releaseId+' to '+outPath)

    def writeMetaTags(self, releaseId, outPath='Audacity Meta Tags.xml'):
        """Useful for importing metadata into Audacity."""
        myxml = etree.Element('tags')
        rel = self.getRelease(releaseId)

        for name, value in [
                ('ALBUM', rel['title'] + (' ('+rel['disambiguation']+')' \
                        if 'disambiguation' in rel else '')),
                ('YEAR', rel['date'] if 'date' in rel else ''),
                ('ARTIST', rel['artist-credit-phrase']),
                ('COMMENTS', self.releaseUrl+releaseId),
                ]:
            subTag = etree.SubElement(myxml, 'tag', attrib=\
                {'name': name, 'value':value})

        with open(outPath, 'wb') as xmlfile:
            xmlfile.write(etree.tostring(myxml))

        _log.info('Saved Audacity tags XML for '+releaseId+' to \'%s\'' % \
                outPath)

    def writeTrackList(self, stream, releaseId):
        """Write ASCII tracklist for releaseId to 'stream'. """
        stream.write('\n')
        _log.info('Printing tracklist for \'%s\'' % releaseId)
        rel = self.getRelease(releaseId)
        for medium in rel['medium-list']:
            for track in medium['track-list']:
                rec = track['recording']
                stream.write(
                    rec['title'] +
                    ' '*(60-len(rec['title'])) +
                    ('%6s' % recLengthAsString(rec['length'] if 'length' in rec else None)) + '\n')

    def getTrackList(self, releaseId):
        """
        Return a list of track titles, track length as strings tuples
        for a release.
        """
        l = []
        rel = self.getRelease(releaseId)
        for medium in rel['medium-list']:
            for track in medium['track-list']:
                rec = track['recording']
                l.append((
                    rec['id'],
                    rec['title'],
                    recLengthAsString(rec['length'] if 'length' in rec else None)))
        return l

    basicColumns = [
        'id',
        'sortstring',
        'artist',
        'title',
        'date',
        'country',
        'label',
        'catno',
        'barcode',
        'asin',
        'format',
        ]

    def getBasicTable(self, filt={}):
        """
        Fetch basic information about all the releases and return an iterator.
        If you need to get all the releases, this will be

        """
        with self._connect() as con:
            cur = con.cursor()
            cur.execute('select '+','.join(self.basicColumns)+\
                ' from releases'+\
                ((' where '+','.join(
                    key+'=?' for key in filt.keys()
                    )) if filt else ''),
                filt.values())
            return cur

    def getReleaseTitle(self, releaseId):
        with self._connect() as con:
            cur = con.cursor()
            cur.execute('select title from releases where id=?',
                (releaseId,))
            return cur.fetchone()[0]

    def getReleaseArtist(self, releaseId):
        with self._connect() as con:
            cur = con.cursor()
            cur.execute('select artist from releases where id=?',
                (releaseId,))
            return cur.fetchone()[0]

    def getReleaseFormat(self, releaseId):
        with self._connect() as con:
            cur = con.cursor()
            cur.execute('select format from releases where id=?',
                (releaseId,))
            return cur.fetchone()[0]

def getMediumLen(medium):
    try:
        return sum([int(track['recording']['length']) \
            for track in medium['track-list']])
    except KeyError as e:
        return None

def formatQueryArtist(releaseDict):
    return ''.join([((cred['artist']['name']) \
            if isinstance(cred, dict) else cred)
            for cred in releaseDict['artist-credit']])

def formatQueryMedia(releaseDict):
    return ' + '.join(mbcat.utils.mergeList(
         [[medium['format']] if medium and 'format' in medium else []
          for medium in releaseDict['medium-list']]))

def formatQueryRecordLabel(releaseDict):
    return (', '.join([(info['label']['name'] if 'label' in info \
            and 'name' in info['label'] else '') \
            for info in releaseDict['label-info-list']])) \
            if 'label-info-list' in releaseDict else ''

def formatQueryCatNo(releaseDict):
    return (', '.join([(info['catalog-number'] \
            if 'catalog-number' in info else '') \
            for info in releaseDict['label-info-list']])) \
            if 'label-info-list' in releaseDict else ''

def getArtistSortPhrase(release):
    """Join artist sort names together"""
    return ''.join([
            credit if type(credit)==str else \
            credit['artist']['sort-name'] \
            for credit in release['artist-credit']
            ])

