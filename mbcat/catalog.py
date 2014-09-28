from __future__ import print_function
from __future__ import unicode_literals
import os
import sys
import time
import musicbrainzngs.mbxml as mbxml
import musicbrainzngs.util as mbutil
import musicbrainzngs.musicbrainz as mb
import mbcat.formats
import mbcat.amazonservices
import mbcat.coverart
import mbcat.userprefs
import mbcat.utils
import mbcat.extradata
import mbcat.dialogs
import shutil
from datetime import datetime
from collections import defaultdict
from collections import Counter
import progressbar
import logging
_log = logging.getLogger("mbcat")
import zlib
import sqlite3
import itertools
from uuid import uuid4

# Have to give an identity for musicbrainzngs
__version__ = '0.3'

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

import threading
from collections import deque
class ConnectionManager(threading.Thread):
    def __init__(self, *args, **kwargs):
        self.child_args = args
        self.child_kwargs = kwargs
        threading.Thread.__init__(self)
        self.setDaemon(True) # terminate when the main thread does
        # to hold commands until the connection is ready
        self.isReady = threading.Event()
        self.cmdReady = threading.Event()
        self.shutdown = threading.Event()
        self.cmdQueue = deque()
        self.results = dict()

        self.start()

    def _create_children(self):
        # Open and retain a connection to the database
        # The single, coveted connection object
        self.conn = sqlite3.connect(*self.child_args, **self.child_kwargs)
        # this connection is closed when this object is deleted

        # This connection and cursor should be enough for most work. You might
        # need a second cursor if you, for example, have a double-nested 'for'
        # loop where you are cross-referencing things:
        #
        # myconn = self._connection()
        # mycur = myconn.cursor()
        # self.curs.execute('first query')
        # mycur.execute('second query')
        # for first in self.curs:
        #     for second in mycur:
        #         "do something with 'first' and 'second'"
        self.curs = self.conn.cursor()

        self.isReady.set()

    def run(self):
        # The child objects have to be created here for them to be owned by
        # this in this thread.
        self._create_children()

        # Go ahead and get a cursor
        while not self.shutdown.isSet():
            self.cmdReady.wait()
            self.cmdReady.clear()
            if self.shutdown.isSet():
                break
            # If more cmdReady was set more than once before we got here, we
            # would miss commands, so we process the queue until it is empty.
            while len(self.cmdQueue):
                # popleft removes and returns an element from the left side
                fun, event, args, kwargs = self.cmdQueue.popleft()
                try:
                    result = fun(*args, **kwargs)
                except sqlite3.OperationalError as e:
                    _log.error(str(e))
                    result = e
                if event:
                    self.results[event] = result
                    event.set()

    def _queueCmd(self, fun, event, *args, **kwargs):
        # append adds x to the right side of the deque
        self.cmdQueue.append((fun, event, args, kwargs))
        self.cmdReady.set() # wake the thread loop out of wait

    def queueQuery(self, fun, *args, **kwargs):
        """
        Queue a function with arguments to be executed by the manager thread.
        This will return an event which can be used to fetch the result of the
        function. If the result is not fetched, the result dictionary will
        leak---use queueCmd instead.
        """
        event = threading.Event()
        self._queueCmd(fun, event, *args, **kwargs)
        return event

    def queueCmd(self, fun, *args, **kwargs):
        """
        Queue a function with arguments to be executed by the manager thread.
        This will discard the result of the function.
        """
        self._queueCmd(fun, None, *args, **kwargs)

    def getResult(self, event):
        """
        Get the result associated with an event. Return None if the event was
        not found.
        """
        return self.results.pop(event, None)

    def queueAndGet(self, fun, *args, **kwargs):
        """
        A convenience function which queues the command, waits until it is
        done, and then returns the result.
        """
        event = self.queueQuery(fun, *args, **kwargs)
        event.wait()
        return self.getResult(event)

    def stop(self):
        self.shutdown.set()
        self.cmdReady.set()

    def execute(self, *argv, **kwargs):
        """
        A convenience function that queues a command to be executed on the
        cursor and expects no results. Result is discarded.
        """
        self.isReady.wait() # wait for the connection to be ready
        self.queueCmd(self.curs.execute, *argv, **kwargs)

    def executeAndFetch(self, *argv):
        """
        A convenience function that queues a command to be executed, waits for
        it to finish and returns the result.
        """
        self.isReady.wait() # wait for the connection to be ready
        self.queueAndGet(self.curs.execute, *argv)
        # PROBLEM: another command might get the result before this does
        return self.queueAndGet(self.curs.fetchall)

    def executeAndFetchOne(self, *argv):
        """
        A convenience function that queues a command to be executed, waits for
        and fetches a one-row result.
        """
        self.isReady.wait() # wait for the connection to be ready
        self.queueAndGet(self.curs.execute, *argv)
        # PROBLEM: another command might get the result before this does
        return self.queueAndGet(self.curs.fetchone)

    def executeAndChain(self, *argv):
        """
        A convenience function that queues a command to be executed, fetches the
        results and chains them together (e.g., [('a',), ('b',)] -> ['a', 'b']).
        """
        self.isReady.wait() # wait for the connection to be ready
        self.queueAndGet(self.curs.execute, *argv)
        # PROBLEM: another command might get the result before this does
        # Possible solution: create a cursor for each execute()?
        return list(itertools.chain.from_iterable(
            self.queueAndGet(self.curs.fetchall)))

    def commit(self):
        """
        A convenience function that queues a commit on the connection and waits
        for it to complete.
        """
        e = self.queueQuery(self.conn.commit)
        e.wait()
        return self.getResult(e)

class Catalog(object):

    mbUrl = 'http://'+mb.hostname+'/'
    artistUrl = mbUrl+'artist/'
    labelUrl = mbUrl+'label/'
    releaseUrl = mbUrl+'release/'
    groupUrl = mbUrl+'release-group/'
    recordingUrl = mbUrl+'recording/'

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
        'sortformat',
        'metatime',
        'count',
        'comment',
        'rating'
        ]

    derivedTables = [
        'words',
        'trackwords',
        'media',
        'recordings',
        'discids'
        ]

    indexes = [
        'word_index',
        'trackword_index'
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

        _log.info('Using \'%s\' for the catalog database' % self.dbPath)
        _log.info('Using \'%s\' for the file cache path' % self.cachePath)

        self.cm = ConnectionManager(self.dbPath)

        if not self._checkTables():
            self._createTables()

    def copy(self):
        return Catalog(self.dbPath, self.cachePath)

    def _checkTables(self):
        """Connect to and check that the basic tables exist in the database."""

        tables = self.cm.executeAndChain(
            'select name from sqlite_master where type="table"')

        # TODO this should check the complete schema
        return 'releases' in tables

    def _createTables(self):
        """Create the SQL tables for the catalog. Database is assumed empty."""

        # TODO maybe store the metadata dict from musicbrainz instead of the XML?
        self.cm.execute("CREATE TABLE releases("
            "id TEXT PRIMARY KEY, "
            "meta BLOB, "
            "sortstring TEXT, "
            "artist TEXT, "
            "title TEXT, "
            # This date is for printing, so we will keep it in a string
            "date TEXT, "
            "country TEXT, "
            "label TEXT, "
            "catno TEXT, "
            "barcode TEXT, "
            "asin TEXT, "
            "format TEXT, "
            "sortformat TEXT, "
            "metatime FLOAT, "
            "count INT DEFAULT 1, "
            "comment TEXT, "
            "rating INT DEFAULT 0)")

        # Indexes for speed (it's all about performance...)
        self.cm.execute('create unique index release_id on releases(id)')
        for col in ['sortstring', 'catno', 'barcode', 'asin']:
            self.cm.execute('create index release_'+col+\
                ' on releases('+col+')')

        self._createMetaTables()

        self._createCacheTables()

        self.cm.commit()

    def _createMetaTables(self):
        """Add the user (meta) data tables to the database.
        This method does not commit its changes."""

        self.cm.execute('CREATE TABLE added_dates('
            'date FLOAT, '
            'release TEXT, '
            'FOREIGN KEY(release) REFERENCES releases(id)'
            ')')

        self.cm.execute('CREATE TABLE listened_dates('
            'date FLOAT, '
            'release TEXT, '
            'FOREIGN KEY(release) REFERENCES releases(id) '
            'ON UPDATE CASCADE ON DELETE CASCADE)')

        self.cm.execute('CREATE TABLE purchases ('
            'date FLOAT, '
            'price FLOAT, '
            'vendor TEXT, '
            'release TEXT, '
            'FOREIGN KEY(release) REFERENCES releases(id) '
            'ON DELETE CASCADE ON UPDATE CASCADE)')

        # checkout, checkin (lent out, returned) tables
        self.cm.execute('CREATE TABLE checkout_events ('
            'borrower TEXT, '
            'date FLOAT, '
            'release TEXT, '
            'FOREIGN KEY(release) REFERENCES releases(id) '
            'ON DELETE CASCADE ON UPDATE CASCADE)')

        self.cm.execute('CREATE TABLE checkin_events ('
            'date FLOAT, '
            'release TEXT, '
            'FOREIGN KEY(release) REFERENCES releases(id) '
            'ON DELETE CASCADE ON UPDATE CASCADE)')

        # Digital copy table
        self.cm.execute('CREATE TABLE digital ('
            'release TEXT, '
            'format TEXT, '
            'path TEXT, '
            'FOREIGN KEY(release) REFERENCES releases(id) '
            'ON DELETE CASCADE ON UPDATE CASCADE)')

    def _createCacheTables(self):
        """Add the release-derived tables to the database.
        This method does not commit its changes."""
        # tables that map specific things to a list of releases
        for columnName, columnType in [
                ('word', 'TEXT'),
                ]:

            self.cm.execute('CREATE TABLE '+columnName+'s('+\
                columnName+' '+columnType+', release TEXT, '
                'FOREIGN KEY(release) REFERENCES releases(id) '
                'ON DELETE CASCADE ON UPDATE CASCADE)')

        self.cm.execute('CREATE TABLE media ('
            'id TEXT, '
            'position INTEGER, '
            'format TEXT, '
            'release TEXT, '
            'FOREIGN KEY(release) REFERENCES releases(id) '
            'ON DELETE CASCADE ON UPDATE CASCADE)')

        self.cm.execute('CREATE TABLE recordings ('
            'id TEXT, '
            'length INTEGER, '
            'number INTEGER, '
            'position INTEGER, '
            'title TEXT, '
            'medium TEXT, '
            'FOREIGN KEY(medium) REFERENCES media(id) '
            'ON DELETE CASCADE ON UPDATE CASCADE)')

        self.cm.execute('CREATE TABLE trackwords('
            'trackword TEXT, recording TEXT, '
            'FOREIGN KEY(recording) REFERENCES recordings(id) '
            'ON DELETE CASCADE ON UPDATE CASCADE)')

        self.cm.execute('CREATE TABLE discids ('
            'id TEXT, '
            'sectors INTEGER, '
            'medium TEXT, '
            'FOREIGN KEY(medium) REFERENCES media(id) '
            'ON DELETE CASCADE ON UPDATE CASCADE)')

        # Indexes for speed (it's all about performance...)
        self.cm.execute('create index word_index on words (word)')
        self.cm.execute('create index trackword_index '
            'on trackwords (trackword)')

    class rebuildCacheTables(mbcat.dialogs.ThreadedTask):
        def __init__(self, catalog):
            self.catalog = catalog
            mbcat.dialogs.ThreadedTask.__init__(self, 0)

        def run(self):
            self.rebuildCacheTables()

        def rebuildCacheTables(self):
            """Drop the derived tables in the database and rebuild them"""
            self.status = 'Dropping tables...'
            self.numer = 0
            self.denom = len(self.catalog.derivedTables) + \
                len(self.catalog.indexes)

            for tab in self.catalog.derivedTables:
                if self.stopthread.isSet():
                    return
                # Note: the added_dates, listened_dates, and purchases tables are
                # not transient.
                self.catalog.cm.execute('drop table if exists '+tab)

            for index in self.catalog.indexes:
                if self.stopthread.isSet():
                    return
                self.catalog.cm.execute('drop index if exists '+index)

            self.catalog._createCacheTables()

            # Rebuild
            g = self.updateCacheTables()

        def updateCacheTables(self):
            """Use the releases table to populate the derived (cache) tables"""
            self.status = 'Rebuilding tables...'
            self.numer = 0
            self.denom = len(self.catalog)
            for releaseId in self.catalog.getReleaseIds():
                if self.stopthread.isSet():
                    return
                metaXml = self.catalog.getReleaseXml(releaseId)
                self.catalog.digestReleaseXml(releaseId, metaXml, rebuild=True)
                self.numer += 1

            self.denom = 0
            self.status = 'Committing changes...'
            self.catalog.cm.commit()

    def vacuum(self):
        """Vacuum the SQLite3 database. Frees up unused space on disc."""
        _log.info('Vacuuming database')
        self.cm.execute('vacuum')

    def renameRelease(self, oldReleaseId, newReleaseId):
        # TODO this does not update purchases, checkout_events, checkin_events,
        # digital
        # Record the new release ID in the added_dates table
        self.cm.execute('insert into added_dates (date, release) '
            'values (?,?)', (time.time(), newReleaseId))
        # Replace the release ID with the new one
        # this will cascade to all appropriate table references
        self.cm.execute('update releases set id=? where id=?',
            (newReleaseId, oldReleaseId))
        self.addRelease(newReleaseId)

    def getReleaseIds(self):
        return self.cm.executeAndChain('select id from releases')

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
        """Return a release's musicbrainz XML metadata from the local cache"""

        if releaseId not in self:
            raise KeyError ('release %s not found' % releaseId)

        return zlib.decompress(
            self.cm.executeAndFetchOne(
                'select meta from releases where id = ?', (releaseId,))[0])

    def getRelease(self, releaseId):
        """Return a release's musicbrainz-ngs dictionary.
        For convenience, only the value of the 'release' key is returned.
        This function should be used sparingly."""

        releaseXml = self.getReleaseXml(releaseId)
        # maybe it would be better to store the release as a serialized dict in
        # the table. Then, we would not need this parsing step

        metadata = self.getReleaseDictFromXml(releaseXml)

        return metadata['release']

    def getReleaseIdsByFormat(self, fmt):
        return self.cm.executeAndChain(
            'select id from releases where sortformat=?', (fmt,))

    def getFormats(self):
        return self.cm.executeAndChain(
            'select distinct sortformat from releases')

    # TODO rename to getReleaseByBarCode
    def barCodeLookup(self, barcode):
        result = self.cm.executeAndChain(
            'select id from releases where barcode=?', (barcode,))
        if not result:
            raise KeyError('Barcode not found')
        return result

    def __len__(self):
        """Return the number of releases in the catalog."""
        return self.cm.executeAndFetchOne('select count(id) from releases')[0]

    def __contains__(self, releaseId):
        count = self.cm.executeAndFetchOne(
                'select count(id) from releases where id=?',
                (releaseId,)) [0]
        return count > 0

    def getCopyCount(self, releaseId):
        if releaseId not in self:
            raise KeyError('Release does not exist')
        return self.cm.executeAndFetchOne(
                'select count from releases where id=?', (releaseId,))[0]

    def setCopyCount(self, releaseId, count):
        self.cm.execute('update releases set count=? where id=?',
                (count, releaseId))
        self.cm.commit()

    def saveZip(self, zipName='catalog.zip', pbar=None):
        """Exports the database as a ZIP archive"""
        import zipfile

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
        import zipfile

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
            self.cm.commit()
            if pbar:
                pbar.finish()

    @staticmethod
    def getReleaseWords(rel):
        words = set()
        relId = rel['id']

        for field in ['title', 'artist-credit-phrase', 'disambiguation']:
            words.update(mbcat.processWords(field, rel))
        for credit in rel['artist-credit']:
            for field in ['sort-name', 'disambiguation', 'name']:
                if field in credit:
                    words.update(mbcat.processWords(field, credit))

        return words

    @staticmethod
    @mbcat.utils.deprecated
    def getReleaseTracks(rel):
        # Format of track (recording) title list
        # r['medium-list'][0]['track-list'][0]['recording']['title']
        for medium in rel['medium-list']:
            for track in medium['track-list']:
                yield track

    @staticmethod
    def _addRelTableRow(cursor, table_name, key_column, key, release_id):
        cursor.execute('insert into '+table_name+' (key_column, release) '
            'values ('+key+', '+release_id+')')

    def digestTrackWords(self, rel):
        """
        Digest all of the words in the track titles of a release.
        This function does not commit.
        """

        # uuid4() returns a random UUID. Need to make sure this row is deleted
        # before this row needs to be added again.
        for medium in rel['medium-list']:
            medium_id = str(uuid4())
            self.cm.execute('insert into media'
                '(id,position,format,release) values (?,?,?,?)',
                (medium_id,
                medium['position'],
                medium['format'] if 'format' in medium else '',
                rel['id']))
            for disc in medium['disc-list']:
                self.cm.execute('insert into discids (id, sectors, medium) '
                    'values (?,?,?)',
                    (disc['id'], disc['sectors'], medium_id))
            for track in medium['track-list']:
                if 'recording' in track:
                    # Add recording and reference the release
                    self.cm.execute('insert into recordings '
                        '(id, title, length, medium) values (?,?,?,?)',
                        (   track['recording']['id'],
                            track['recording']['title'],
                            track['recording']['length'] \
                            if 'length' in track['recording'] else None,
                            medium_id)
                        )
                    if 'title' in track['recording']:
                        for word in mbcat.processWords('title',
                            track['recording']):
                            # Reference each word to this recording
                            self.cm.execute('insert into trackwords '
                                '(trackword, recording) values (?,?)',
                                (word, track['recording']['id']))

    def unDigestTrackWords(self, relId):
        """
        Undo what digestTrackWords() does.
        This function does not commit.
        """
        # Query for recordings for this release ID
        media = self.cm.executeAndFetch(
            'select id from media where release=?', (relId,))
        for (mediumId,) in media:
            self.cm.execute('delete from discids where medium=?',
                (mediumId,))

            # Iterate through the results
            for recordingId in self.cm.executeAndFetch(
                    'select id from recordings where medium=?',
                    (mediumId,)):
                self.cm.execute('delete from trackwords where recording=?',
                    (recordingId[0],))
            # Then, delete the rows in the recordings table referencing this
            # medium ID
            self.cm.execute( 'delete from recordings where medium=?',
                (mediumId,))
        # Then, delete the rows in the media table referencing this
        # release ID
        self.cm.execute('delete from media where release=?', (relId,))

    @mbcat.utils.deprecated
    def mapWordsToRelease(self, words, releaseId):
        word_set = set(words)
        for word in word_set:
            if word in self.wordMap:
                self.wordMap[word].append(releaseId)
            else:
                self.wordMap[word] = [releaseId]

    # TODO this is used externally, but has an underscore prefix
    def _search(self, query, table='words', keycolumn='word',
            outcolumn='release'):
        query_words = query.lower().split(' ')
        matches = set()
        for word in query_words:
            # get the record, there should be one or none
            fetched = self.cm.executeAndChain(
                    'select %s from %s where %s = ?' % \
                    (outcolumn, table, keycolumn),
                    (word,))
            # if the word is in the table
            if fetched:
                # for the first word
                if word == query_words[0]:
                    # use the whole set of releases that have this word
                    matches = set(fetched)
                else:
                    # intersect the releases that have this word with the
                    # current release set
                    matches = matches & set(fetched)
            else:
                # this word is not contained in any releases and therefore
                # no releases match
                matches = set()
                break

        return matches

    def searchTrackWords(self, query):
        return self._search(query, table='trackwords', keycolumn='trackword')

    def recordingGetReleases(self, recordingId):
# need a join?
#> select discids.discid, releases.id from discids inner join releases on discids.release=releases.id;
        return self.cm.executeAndChain(
            #'select medium from recordings where id = ?',
            'select releases.id from media '
            'inner join releases on media.release=releases.id '
            'inner join recordings on recordings.medium=media.id '
            'where recordings.id=?',
#select releases.id from media inner join releases on media.release=releases.id inner join recordings on recordings.medium=media.id where recordings.id='a8247cc4-2cce-408a-bbdb-78318a7a459f';
            (recordingId,))

    def formatRecordingInfo(self, recordingId):
        title,length = self.cm.executeAndFetchOne(
            'select title,length from recordings '
            'where id=?', (recordingId,))

        return '%s: %s (%s)' % (recordingId, title,
            mbcat.catalog.recLengthAsString(length))

    def getRecordingTitle(self, recordingId):
        return self.cm.executeAndFetchOne('select title from recordings '
            'where id=?', (recordingId,))[0]

    def getRecordingLength(self, recordingId):
        return self.cm.executeAndFetchOne('select length from recordings '
            'where id=?', (recordingId,))[0]

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

        sortstring = self.cm.executeAndFetchOne(
            'select sortstring from releases where id = ?',
                (releaseId,))[0]

        # TODO isn't this done while digesting XML?
        if not sortstring:
            # cache it for next time
            sortstring = self.getSortStringFromRelease(
                    self.getRelease(releaseId))
            self.cm.execute('update releases set sortstring=? where id=?',
                    (sortstring, releaseId))
            self.cm.commit()

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

        # TODO use 'SELECT id FROM releases ORDER BY sortstring' instead
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
        result = self.cm.executeAndFetchOne(
                'select count(distinct word) from words')[0]
        if type(result) == sqlite3.OperationalError:
            # This can happen if the words table does not exist yet
            return 0
        return result

    def getTrackWordCount(self):
        """Fetch the number of words in the track search word table."""
        result = self.cm.executeAndFetchOne(
                'select count(distinct trackword) from trackwords')[0]
        if type(result) == sqlite3.OperationalError:
            # This can happen if the trackwords table does not exist yet
            return 0
        return result

    def getComment(self, releaseId):
        """Get the comment for a release (if any)."""
        return self.cm.executeAndFetchOne(
            'select comment from releases where id=?',
            (releaseId,))[0]

    def setComment(self, releaseId, comment):
        """Set the comment for a release."""
        self.cm.execute(
            'update releases set comment=? where id=?',
            (comment, releaseId))
        self.cm.commit()

    def getDigitalPaths(self, releaseId):
        return self.cm.executeAndFetchOne(
            'select digital from releases where id=?',
            (releaseId,))[0]

    def addDigitalPath(self, releaseId, format, path):
        existingPaths = self.getDigitalPaths(releaseId)
        self.cm.execute('insert into digital (release, format, path) '
                'values (?,?,?)', (releaseId, format, path))
        self.cm.commit()

    def getFirstAdded(self, releaseId):
        return self.cm.executeAndFetchOne(
            'select min(date) from added_dates where release=?',
            (releaseId,))[0]

    def getLastListened(self, releaseId):
        return self.cm.executeAndFetchOne(
            'select max(date) from listened_dates where release=?',
            (releaseId,))[0]

    def getAddedDates(self, releaseId):
        return self.cm.executeAndFetchOne(
            'select date from added_dates where release=?',
            (releaseId,))[0]

    def addAddedDate(self, releaseId, date):
        # input error checking
        if (type(date) != float):
            try:
                date = float(date)
            except ValueError as e:
                raise ValueError('Date object should be a floating-point number')

        self.cm.execute('insert into added_dates (date, release) '
            'values (?,?)', (date, releaseId))
        self.cm.commit()

    def getCheckOutEvents(self, releaseId):
        # TODO should use sqlite3.Row as the conn.row_factory for these fetches
        return self.cm.executeAndFetch(
            'select date,borrower from checkout_events where release=?',
            (releaseId,))

    def getCheckInEvents(self, releaseId):
        # TODO should use sqlite3.Row as the conn.row_factory for these fetches
        return self.cm.executeAndFetch(
            'select date from checkin_events where release=?',
            (releaseId,))

    def getCheckOutHistory(self, releaseId):
        checkOutEvents = self.getCheckOutEvents(releaseId)
        checkInEvents = self.getCheckInEvents(releaseId)
        eventHistory = sorted(checkOutEvents + checkInEvents,
            key=lambda x: x[0])
        return eventHistory

    def getCheckOutStatus(self, releaseId):
        latestCheckOut = self.cm.executeAndFetchOne(
            'select max(date) from checkout_events where release=?',
            (releaseId,))[0]
        latestCheckIn = self.cm.executeAndFetchOne(
            'select max(date) from checkin_events where release=?',
            (releaseId,))[0]

        if latestCheckIn > latestCheckOut:
            return None
        else:
            info = self.cm.executeAndFetchOne(
                'select borrower, date from checkout_events '
                'where release=? order by date limit 1', (releaseId,))
            return info

    def addCheckOutEvent(self, releaseId, borrower, date):
        self.cm.execute('insert into checkout_events '
            '(borrower, date, release) values (?,?,?)',
            (borrower, date, releaseId))
        self.cm.commit()

    def addCheckInEvent(self, releaseId, date):
        self.cm.execute('insert into checkin_events (date,release) '
            'values (?,?)', (date, releaseId))
        self.cm.commit()

    def getRating(self, releaseId):
        result = self.cm.executeAndFetchOne(
            'select rating from releases where id=?',
            (releaseId,))
        return result[0] if result else None

    def setRating(self, releaseId, rating):
        self.cm.execute('update releases set rating=? where id=?',
                (rating, releaseId))
        self.cm.commit()

    def getPurchases(self, releaseId):
        return self.cm.executeAndFetch(
            'select date,price,vendor from purchases where release=?',
            (releaseId,))

    def addPurchase(self, releaseId, date, price, vendor):
        # Some error checking
        if not isinstance(date, str) and not isinstance(date, unicode):
            raise ValueError ('Wrong type for date')
        if not isinstance(price, str) and not isinstance(price, unicode):
            raise ValueError ('Wrong type for date')
        if not isinstance(vendor, str) and not isinstance(vendor, unicode):
            raise ValueError ('Wrong type for date')

        self.cm.execute('insert into purchases (date,price,vendor,release) '
            'values (?,?,?,?)', (date,price,vendor,releaseId))
        self.cm.commit()

    def getListenDates(self, releaseId):
        return self.cm.executeAndChain('select date from listened_dates '
            'where release=?', (releaseId,))

    def addListenDate(self, releaseId, date):
        # Some precursory error checking
        if not isinstance(date, float):
            raise ValueError ('Wrong type for date argument')
        self.cm.execute('insert into listened_dates (date, release) '
            'values (?,?)', (date,releaseId))
        self.cm.commit()

    @mbcat.utils.deprecated
    def getExtraData(self, releaseId):
        """Put together all of the metadata added by mbcat. This might be
        removed in a later release, only need it when upgrading from 0.1."""
        purchases,added,lent,listened,digital,count,comment,rating = \
            self.cm.executeAndFetchOne(
                'select purchases,added,lent,listened,digital,count,'
                'comment,rating from releases where id=?', (releaseId,))

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

    @mbcat.utils.deprecated
    def digestExtraData(self, releaseId, ed):
        """Take an ExtraData object and update the metadata in the catalog for
        a release"""
        # TODO there is no attempt to merge information that already exists in
        # the database
        self.cm.execute('update releases set '+\
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
        self.cm.commit()

    def report(self):
        """Print some statistics about the catalog as a sanity check."""

        print("\n%d releases" % len(self))
        print("%d words in release search table" % self.getWordCount())
        print("%d words in track search table" % self.getTrackWordCount())

    def fetchReleaseMetaXml(self, releaseId):
        """Fetch release metadata XML from musicbrainz"""
        # get_release_by_id() handles throttling on its own
        _log.info('Fetching metadata for ' + releaseId)
        mb.set_parser(mb.mb_parser_null)
        xml = mb.get_release_by_id(releaseId, includes=['artists', 'discids',
                'media', 'labels', 'recordings'])
        mb.set_parser()
        return xml

    def digestReleaseXml(self, releaseId, metaXml, rebuild=False):
        """Update the appropriate data structes for a new release."""
        relDict = self.getReleaseDictFromXml(metaXml) # parse the XML

        exists = releaseId in self
        now = time.time()

        if not exists:
            self.cm.execute('insert into added_dates '
                '(date, release) values (?, ?)',
                (now, releaseId))
            # Update releases table
            newColumns = [
                'id',
                'meta',
                'metatime',
                ]

            try:
                self.cm.execute('insert into releases (' + \
                        ','.join(newColumns) + \
                        ') values (' + \
                        ','.join(['?']*len(newColumns)) + \
                        ')',
                        (
                        releaseId,
                        buffer(zlib.compress(metaXml)),
                        now,
                        )
                )
            except sqlite3.IntegrityError as e:
                _log.error('Release already exists in catalog.')
        elif not rebuild:
            # Remove references to this release from the words, barcodes,
            # etc. tables so we can add the correct ones later
            self.unDigestRelease(releaseId, delete=False)
            self.cm.execute('update releases set meta=?,sortstring=?,'
                    'metatime=? where id=?',
                    (buffer(zlib.compress(metaXml)),
                    self.getSortStringFromRelease(relDict['release']),
                    now,
                    releaseId
                    )
                )

        # Whether the release already existed or not
        metaColumns = [
            ('sortstring', self.getSortStringFromRelease(
                relDict['release'])),
            ('artist', mbcat.catalog.getArtistSortPhrase(
                relDict['release'])),
            ('title', self.fmtTitle(relDict['release'])),
            ('date', (relDict['release']['date'] \
                if 'date' in relDict['release'] else '')),
            ('country', (relDict['release']['country'] \
                if 'country' in relDict['release'] else '')),
            ('label', self.fmtLabel(relDict['release'])),
            ('catno', self.fmtCatNo(relDict['release'])),
            ('barcode', (relDict['release']['barcode'] \
                if 'barcode' in relDict['release'] else '')),
            ('asin', (relDict['release']['asin'] \
                if 'asin' in relDict['release'] else '')),
            ('format', formatReleaseFormat(relDict['release'])),
            ('sortformat', mbcat.formats.getReleaseFormat(
                relDict['release']).name()),
            ]

        self.cm.execute('update releases set '+\
            ','.join([key+'=?' for key,val in metaColumns])+\
            ' where id=?',
            [val for key,val in metaColumns] + [releaseId]
            )

        # Update words table
        rel_words = self.getReleaseWords(relDict['release'])
        for word in rel_words:
            self.cm.execute('insert into words (word,release) values (?,?)',
                (word, releaseId))

        # Update words -> (word, recordings) and
        # recordings -> (recording, releases)
        self.digestTrackWords(relDict['release'])

    def unDigestRelease(self, releaseId, delete=True):
        """Remove all references to a release from the data structures.
        Optionally, leave the release in the releases table.
        This function does not commit its changes to the connection.
        See also: digestReleaseXml()"""
        relDict = self.getRelease(releaseId)

        if delete:
            # Update releases table
            self.cm.execute('delete from releases where id = ?',
                (releaseId,))

        # Update words table
        rel_words = self.getReleaseWords(relDict)
        for word in rel_words:
            self.cm.execute('delete from words where release=?',
                (releaseId,))

        # Update words -> (word, recordings) and
        # recordings -> (recording, releases)
        self.unDigestTrackWords(releaseId)

        # Update discids -> (id, media)
        #self.curs.execute('delete from discids where release=?', (releaseId,))

    @staticmethod
    def fmtTitle(relDict):
        return relDict['title'] \
                +(' (%s)' % relDict['disambiguation'] \
                if 'disambiguation' in relDict else '')

    @staticmethod
    def fmtArtist(release):
        return ''.join([(cred['artist']['name'] \
            if isinstance(cred, dict) else cred)
            for cred in release['artist-credit']])

    @staticmethod
    def fmtLabel(rel):
        if 'label-info-list' not in rel:
            return ''
        return ', '.join([
            (info['label']['name'] if 'label' in info else '')
            for info in rel['label-info-list']])

    @staticmethod
    def fmtCatNo(rel):
        if 'label-info-list' not in rel:
            return ''
        return ', '.join([
            (info['catalog-number'] if 'catalog-number' in info else '')
            for info in rel['label-info-list']])

    # TODO move this to a Digital class
    @staticmethod
    def getArtistPathVariations(release):
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

    # TODO move this to a Digital class
    @staticmethod
    def getTitlePathVariations(release):
        s = set()
        s.add(release['title'])
        if 'disambiguation' in release:
            s.add(release['disambiguation'])
            s.add(release['title']+' ('+release['disambiguation']+')')
        return s

    # TODO move this to a Digital class
    @staticmethod
    def getPathAlNumPrefixes(path):
        """Returns a set of prefixes used for directory balancing"""
        return set([
                '', # in case nothing is used
                path[0].lower(), # most basic implementation
                path[0:1].lower(), # have never seen this
                (path[0]+'/'+path[0:2]).lower(), # used by Wikimedia
                ])

    # TODO move this to a Digital class
    def getDigitalPathVariations(self, root, release):
        for artistName in self.getArtistPathVariations(release):
            for prefix in self.getPathAlNumPrefixes(artistName):
                artistPath = os.path.join(root, prefix, artistName)
                if os.path.isdir(artistPath):
                    for titleName in self.getTitlePathVariations(release):
                        yield os.path.join(artistPath, titleName)
                else:
                    _log.debug(artistPath+' does not exist')

    # TODO move this to a Digital class
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

    # TODO move this to a Digital class
    def getDigitalPath(self, releaseId, pathSpec=None):
        """Returns the file path for a release given a specific release ID and
        a path specification string (mbcat.digital)."""
        if not pathSpec:
            pathSpec = self.prefs.defaultPathSpec
        return mbcat.digital.DigitalPath(pathSpec).\
                toString(self.getRelease(releaseId))

    # TODO move this to a Digital class
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
        r = self.cm.executeAndFetchOne(
            'select metatime from releases where id = ?',
            (releaseId,))
        return r[0] if r else 0

    def addRelease(self, releaseId, olderThan=0):
        """
        Get metadata XML from MusicBrainz and add to or refresh the catalog.
        """

        releaseId = mbcat.utils.getReleaseIdFromInput(releaseId)
        if releaseId in self:
            _log.info("Release %s is already in catalog." % releaseId)
        metaTime = self.getMetaTime(releaseId)
        if metaTime > (time.time() - olderThan):
            _log.info("Skipping fetch of metadata for %s because it is recent",
                    releaseId)
            return 0

        metaXml = self.fetchReleaseMetaXml(releaseId)
        self.digestReleaseXml(releaseId, metaXml)
        self.cm.commit()

        _log.info("Added '%s'" % self.getReleaseTitle(releaseId))

        self.getCoverArt(releaseId)

    def deleteRelease(self, releaseId):
        releaseId = mbcat.utils.getReleaseIdFromInput(releaseId)
        self.unDigestRelease(releaseId)
        self.cm.commit()

    def refreshAllMetaData(self, olderThan=0, pbar=None):
        for releaseId in self.loadReleaseIds(pbar):
            _log.info("Refreshing %s", releaseId)
            self.addRelease(releaseId, olderThan)
            # NOTE Could delay commit in addRelease and commit once here, but
            # fetching from web is slow, so this extra delay might be
            # acceptable. Also, partial refreshes will be committed as they
            # progress.

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

    # TODO maybe cover art tasks should be in another class
    def _getCoverArtPath(self, releaseId):
        return os.path.join(self.cachePath, releaseId[0], releaseId[0:2],
                releaseId, 'cover.jpg')

    def getCoverArt(self, releaseId, maxage=60*60):
        imgPath = self._getCoverArtPath(releaseId)
        if os.path.isfile(imgPath) and os.path.getmtime(imgPath) > \
                time.time() - maxage:
            _log.info("Already have cover art for " + releaseId + " at '" + \
                imgPath + "', skipping")
            return

        try:
            meta = mbcat.coverart.getCoverArtMeta(releaseId)
            mbcat.coverart.saveCoverArt(meta, imgPath)

        except mb.ResponseError as e:
            _log.warning('No cover art for ' + releaseId +
                    ' available from Cover Art Archive')

            # TODO can a release have more than one ASIN? If so, we'd need a
            # separate DB table
            asin = self.getReleaseASIN(releaseId)
            if asin:
                _log.info('Trying to fetch cover art from Amazon instead')
                mbcat.amazonservices.saveImage(asin,
                        mbcat.amazonservices.AMAZON_SERVER["amazon.com"],
                        imgPath)
            else:
                _log.warning('No ASIN for '+releaseId+
                        ', cannot fetch from Amazon.')

    def refreshAllCoverArt(self, maxage=60*60*24):
        for releaseId in self.getReleaseIds():
            self.getCoverArt(releaseId, maxage=maxage)

    class checkLevenshteinDistances(mbcat.dialogs.ThreadedTask):
        """
        Compute the Levenshtein (edit) distance of each pair of releases.

        Returns a sorted list of the most similar releases
        """
        def __init__(self, catalog):
            self.catalog = catalog
            mbcat.dialogs.ThreadedTask.__init__(self, 0)

        def run(self):
            import Levenshtein
            self.status = 'Comparing releases...'
            self.numer = 0
            # This expression results from the nested for loops below
            numRels = len(self.catalog)
            self.denom = (numRels**2 - numRels)/2
            dists = []

            releaseIds = self.catalog.getReleaseIds()
            for leftIdx in range(len(self.catalog)):
                for rightIdx in range(leftIdx+1, len(self.catalog)):
                    leftId = releaseIds[leftIdx]
                    rightId = releaseIds[rightIdx]
                    dist = Levenshtein.distance(
                            self.catalog.getReleaseSortStr(leftId),
                            self.catalog.getReleaseSortStr(rightId))

                    dists.append((dist, leftId, rightId))
                    self.numer += 1

            # TODO could sort the list and truncate it in each iteration above
            self.result = sorted(dists, key=lambda sortKey: sortKey[0])

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
                    ('%6s' % recLengthAsString(rec['length'] 
                        if 'length' in rec else None)) + '\n')

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
                    recLengthAsString(rec['length'] \
                        if 'length' in rec else None)))
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
        return self.cm.executeAndFetch(
            'select '+','.join(self.basicColumns)+' from releases'+\
            ((' where '+','.join(
                key+'=?' for key in filt.keys()
                )) if filt else '')+\
            ' order by sortstring',
            filt.values())
        # could return the cursor here for efficiency, but then it would have
        # left the object

    def getReleaseTitle(self, releaseId):
        return self.cm.executeAndFetchOne(
            'select title from releases where id=?',
            (releaseId,))[0]

    def getReleaseCountry(self, releaseId):
        return self.cm.executeAndFetchOne(
            'select country from releases where id=?',
            (releaseId,))[0]

    def getReleaseArtist(self, releaseId):
        return self.cm.executeAndFetchOne(
            'select artist from releases where id=?',
            (releaseId,))[0]

    def getReleaseFormat(self, releaseId):
        return self.cm.executeAndFetchOne(
            'select format from releases where id=?',
            (releaseId,))[0]

    def getReleaseASIN(self, releaseId):
        cols = self.cm.executeAndFetchOne(
            'select asin from releases where id=?',
            (releaseId,))
        return cols[0] if cols else None

    def getMediumLen(self, mediumId):
        return self.cm.executeAndFetchOne(
            'select sum(length) from recordings where medium=?',
            (mediumId,))[0]

def recLengthAsString(recLength):
    if not recLength:
        return '?:??'
    # convert milli-seconds to seconds
    length = float(recLength)/1000
    return ('%d:%02d' % (length/60, round(length%60)))

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

# TODO maybe this should live in mbcat.formats
def formatReleaseFormat(release):
    """Return a string representing the media that are part of a release"""
    if 'medium-list' not in release:
        return '[unknown]'
    format_counter = Counter(medium['format'] \
        if 'format' in medium else '[unknown]' \
        for medium in release['medium-list'])
    return ' + '.join([
            ((('%d\u00d7' % count) if count > 1 else '') + fmt) \
            for fmt, count in format_counter.most_common()])
