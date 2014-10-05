from __future__ import print_function
from __future__ import unicode_literals
import os
import sys
import time
import musicbrainzngs.mbxml as mbxml
import musicbrainzngs.util as mbutil
import musicbrainzngs.musicbrainz as mb
from . import formats
from . import amazonservices
from . import coverart
from . import userprefs
from . import utils
from . import extradata
from . import dialogs
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
        self.conn.execute('pragma foreign_keys=ON')

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
                    _log.debug(str(fun)+str(args)+str(kwargs))
                    result = fun(*args, **kwargs)
                except sqlite3.OperationalError as e:
                    _log.error(str(e))
                    result = e
                except sqlite3.IntegrityError as e:
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
        'medium_recordings',
        'discids'
        ]

    indexes = [
        'word_index',
        'trackword_index'
        ]

    badReleaseFilter = 'format like "%[unknown]%"'\
                ' or barcode=""'\
                ' or asin=""'\
                ' or label=""'\
                ' or catno=""'\
                ' or country=""'\
                ' or date=""'\
                ' or artist=""'\
                ' or title=""'

    def __init__(self, dbPath=None, cachePath=None):
        """Open or create a new catalog"""

        prefPath = os.path.join(os.path.expanduser('~'), '.mbcat')
        self.dbPath = dbPath if dbPath else os.path.join(prefPath, 'mbcat.db')
        self.cachePath = cachePath if cachePath else \
                os.path.join(prefPath, 'cache')

        if not os.path.isdir(prefPath):
            os.mkdir(prefPath)

        self.prefs = userprefs.PrefManager()

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
            'release TEXT'
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
            'id TEXT PRIMARY KEY, '
            'position INTEGER, '
            'format TEXT, '
            'release TEXT, '
            'FOREIGN KEY(release) REFERENCES releases(id) '
            'ON DELETE CASCADE ON UPDATE CASCADE)')

        self.cm.execute('CREATE TABLE recordings ('
            'id TEXT PRIMARY KEY, '
            'length INTEGER, '
            'number INTEGER, '
            'title TEXT)')

        self.cm.execute('CREATE TABLE medium_recordings ('
            'recording TEXT, '
            'position INTEGER, '
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

    class rebuildCacheTables(dialogs.ThreadedTask):
        def __init__(self, catalog):
            self.catalog = catalog
            dialogs.ThreadedTask.__init__(self, 0)

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
                self.numer += 1

            for index in self.catalog.indexes:
                if self.stopthread.isSet():
                    return
                self.catalog.cm.execute('drop index if exists '+index)
                self.numer += 1

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
        _log.info('Renaming existing release \'%s\' to \'%s\'' % (
                oldReleaseId, newReleaseId))
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

    def getReleaseIds(self, filter=None):
        return self.cm.executeAndChain('select id from releases'
            +((' '+filter) if filter else ''))

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

    def getReleaseCountByFormat(self, fmt):
        return self.cm.executeAndChain(
            'select count(id) from releases where sortformat=?', (fmt,))

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

    defaultZipPath='catalog.zip'
    class saveZip(dialogs.ThreadedTask):
        """Exports the database as a ZIP archive"""
        def __init__(self, catalog, zipName=None):
            dialogs.ThreadedTask.__init__(self, 0)
            self.catalog = catalog
            self.zipName = zipName if zipName else catalog.defaultZipPath

        def run(self):
            import zipfile
            _log.info('Saving ZIP file for catalog to \'%s\'' % self.zipName)

            self.numer=0
            self.denom=len(self.catalog)
            with zipfile.ZipFile(self.zipName, 'w', zipfile.ZIP_DEFLATED) as zf:
                for releaseId in self.catalog.getReleaseIds():
                    zipReleasePath = self.catalog.zipReleaseRoot+'/'+releaseId
                    zf.writestr(zipReleasePath+'/'+'metadata.xml',
                            self.catalog.getReleaseXml(releaseId))

                    # add coverart if is cached
                    # use 'store' method because JPEG is already compressed
                    coverArtPath = self.catalog._getCoverArtPath(releaseId)
                    if os.path.isfile(coverArtPath):
                        zf.write(coverArtPath,
                                zipReleasePath+'/cover.jpg',
                                zipfile.ZIP_STORED)

                    #ed = self.catalog.getExtraData(releaseId)
                    #zf.writestr(zipReleasePath+'/extra.xml',
                            #ed.toString())

                    self.numer += 1

    class loadZip(dialogs.ThreadedTask):
        """Imports the data from a ZIP archive into the database"""
        def __init__(self, catalog, zipName=None):
            dialogs.ThreadedTask.__init__(self, 0)
            self.catalog = catalog
            self.zipName = zipName if zipName else catalog.defaultZipPath

        def run(self):
            import zipfile
            _log.info('Loading ZIP file into catalog from \'%s\'' %\
                    self.zipName)

            self.numer = 0
            with zipfile.ZipFile(self.zipName, 'r') as zf:
                self.denom = len(zf.namelist())
                for fInfo in zf.infolist():
                    try:
                        rootPath, releaseId, fileName = \
                                fInfo.filename.split('/')
                    except ValueError:
                        # this must not be a file that is part of a release
                        continue

                    if rootPath!= self.catalog.zipReleaseRoot:
                        # must not be part of a release, do nothing for now
                        _log.warning('Ignoring zip element "%s"' % rootPath)
                        continue

                    if len(releaseId) != 36:
                        _log.error('Release ID in path \'%s\' not expected '
                                'length (36)' % releaseId)
                        continue

                    if fileName == 'metadata.xml':
                        self.catalog.digestReleaseXml(releaseId, zf.read(fInfo))

                    #if fileName == 'extra.xml':
                        #ed = extradata.ExtraData(releaseId)
                        #ed.loads(zf.read(fInfo))
                        #self.catalog.digestExtraData(releaseId, ed)

                    if fileName == 'cover.jpg':
                        coverArtPath = self.catalog._getCoverArtPath(releaseId)
                        with file(coverArtPath, 'w') as f:
                            f.write(zf.read(fInfo))

                    self.numer += 1
                self.catalog.cm.commit()

    @staticmethod
    def getReleaseWords(rel):
        words = set()
        relId = rel['id']

        for field in ['title', 'artist-credit-phrase', 'disambiguation']:
            words.update(processWords(field, rel))
        for credit in rel['artist-credit']:
            for field in ['sort-name', 'disambiguation', 'name']:
                if field in credit:
                    words.update(processWords(field, credit))

        return words

    @staticmethod
    @utils.deprecated
    def getReleaseTracks(rel):
        # Format of track (recording) title list
        # r['medium-list'][0]['track-list'][0]['recording']['title']
        for medium in rel['medium-list']:
            for track in medium['track-list']:
                yield track

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
                    # Add recording
                    self.cm.execute('insert or replace into recordings '
                        '(id, title, length) values (?,?,?)',
                            (track['recording']['id'],
                            track['recording']['title'],
                            track['recording']['length'] \
                            if 'length' in track['recording'] else None)
                        )
                    # and reference the release
                    self.cm.execute('insert into medium_recordings '
                        '(recording, position, medium) values (?,?,?)',
                            (track['recording']['id'],
                            track['position'],
                            medium_id)
                        )
                    if 'title' in track['recording']:
                        for word in processWords('title',
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
                    'select recording from medium_recordings where medium=?',
                    (mediumId,)):
                self.cm.execute('delete from trackwords where recording=?',
                    (recordingId[0],))
            # Then, delete the rows in the recordings table referencing this
            # medium ID
            self.cm.execute( 'delete from medium_recordings where medium=?',
                (mediumId,))
        # Then, delete the rows in the media table referencing this
        # release ID
        self.cm.execute('delete from media where release=?', (relId,))

    @utils.deprecated
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
        return self.cm.executeAndChain(
            'select releases.id from media '
            'inner join releases on media.release=releases.id '
            'inner join medium_recordings on medium_recordings.medium=media.id '
            'where medium_recordings.recording=?',
            (recordingId,))

    def formatRecordingInfo(self, recordingId):
        title,length = self.cm.executeAndFetchOne(
            'select title,length from recordings '
            'where id=?', (recordingId,))

        return '%s: %s (%s)' % (recordingId, title,
            catalog.recLengthAsString(length))

    def getRecordingTitle(self, recordingId):
        return self.cm.executeAndFetchOne('select title from recordings '
            'where id=?', (recordingId,))[0]

    def getRecordingLength(self, recordingId):
        return self.cm.executeAndFetchOne('select length from recordings '
            'where id=?', (recordingId,))[0]

    @staticmethod
    def getSortStringFromRelease(release):
        return ' - '.join ( [ \
                utils.formatSortCredit(release), \
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
        if matchFmt is not None:
            return self.cm.executeAndFetch(
                    'select id,sortstring from releases '
                    'where format=? '
                    'order by sortstring', (matchFmt,))
        else:
            return self.cm.executeAndFetch(
                    'select id,sortstring from releases '
                    'order by sortstring')

    def getSortNeighbors(self, releaseId, neighborHood=5, matchFormat=False):
        """
        Print release with context (neighbors) to assist in sorting and storage
        of releases.
        """

        if matchFormat:
            fmt = self.getReleaseFormat(releaseId)
        else:
            fmt = None
            _log.warning("Sorting release "+releaseId+" with no format"
                    " into a list of all releases.")
        rows = self.getSortedList(fmt)

        index = rows.index((releaseId, self.getReleaseSortStr(releaseId)))
        neighborhoodIndexes = range(max(0,index-neighborHood),
                min(len(rows), index+neighborHood))
        return (index, [rows[i] for i in neighborhoodIndexes])

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
        return self.cm.executeAndChain(
            'select path from digital where release=?',
            (releaseId,))

    def addDigitalPath(self, releaseId, format, path):
        self.cm.execute('insert into digital (release, format, path) '
                'values (?,?,?)', (releaseId, format, path))
        self.cm.commit()

    def deleteDigitalPath(self, releaseId, path):
        self.cm.execute('delete from digital where release=? and path=?',
                (releaseId, path))
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
                'where release=? order by date desc limit 1', (releaseId,))
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
        if not isinstance(date, float):
            raise ValueError ('Wrong type for date')
        if not isinstance(price, float):
            raise ValueError ('Wrong type for price')
        if not isinstance(vendor, str) and not isinstance(vendor, unicode):
            raise ValueError ('Wrong type for vendor')

        self.cm.execute('insert into purchases (date,price,vendor,release) '
            'values (?,?,?,?)', (date,price,vendor,releaseId))
        self.cm.commit()

    def deletePurchase(self, releaseId, date):
        if not isinstance(date, float):
            raise ValueError ('Wrong type for date argument')
        self.cm.execute('delete from purchases where release=? and date=?',
                (releaseId, date))
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

    def deleteListenDate(self, releaseId, date):
        if not isinstance(date, float):
            raise ValueError ('Wrong type for date argument')
        self.cm.execute('delete from listened_dates where release=? and date=?',
                (releaseId, date))
        self.cm.commit()

    @utils.deprecated
    def getExtraData(self, releaseId):
        """Put together all of the metadata added by mbcat. This might be
        removed in a later release, only need it when upgrading from 0.1."""
        purchases,added,lent,listened,digital,count,comment,rating = \
            self.cm.executeAndFetchOne(
                'select purchases,added,lent,listened,digital,count,'
                'comment,rating from releases where id=?', (releaseId,))

        ed = extradata.ExtraData(releaseId)
        ed.purchases = purchases
        ed.addDates = added
        ed.lendEvents = lent
        ed.listenEvents = listened
        ed.digitalPaths = digital
        # TODO no place for count yet in extradata
        ed.comment = comment
        ed.rating = rating

        return ed

    @utils.deprecated
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

        # Check for a merged release ID
        if relDict['release']['id'] != releaseId:
            _log.info('Release \'%s\' has been merged into \'%s\'.' %\
                (releaseId, relDict['release']['id']))
            if exists:
                if relDict['release']['id'] in self:
                    raise Exception('Can not rename release because the new '
                            'name already exists!')
                self.renameRelease(releaseId, relDict['release']['id'])
            releaseId = relDict['release']['id']

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
            ('artist', catalog.getArtistSortPhrase(
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
            ('sortformat', formats.getReleaseFormat(
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

        return releaseId # because it can change due to a merge

    def unDigestRelease(self, releaseId, delete=True):
        """Remove all references to a release from the data structures.
        Optionally, leave the release in the releases table.
        This function does not commit its changes to the connection.
        See also: digestReleaseXml()"""
        relDict = self.getRelease(releaseId)

        # Update words -> (word, recordings) and
        # recordings -> (recording, releases)
        self.unDigestTrackWords(releaseId)

        # Update words table
        rel_words = self.getReleaseWords(relDict)
        for word in rel_words:
            self.cm.execute('delete from words where release=?',
                (releaseId,))

        if delete:
            # Update releases table
            self.cm.execute('delete from releases where id = ?',
                (releaseId,))

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

    def getMetaTime(self, releaseId):
        r = self.cm.executeAndFetchOne(
            'select metatime from releases where id = ?',
            (releaseId,))
        return r[0] if r else 0

    def addRelease(self, releaseId, olderThan=0):
        """
        Get metadata XML from MusicBrainz and add to or refresh the catalog.
        This function does commit its changes.
        """

        releaseId = utils.getReleaseIdFromInput(releaseId)
        if releaseId in self:
            _log.info("Release %s is already in catalog." % releaseId)
        metaTime = self.getMetaTime(releaseId)
        if metaTime > (time.time() - olderThan):
            _log.info("Skipping fetch of metadata for %s because it is recent",
                    releaseId)
            return 0

        metaXml = self.fetchReleaseMetaXml(releaseId)
        releaseId = self.digestReleaseXml(releaseId, metaXml)
        self.cm.commit()

        _log.info("Added '%s'" % self.getReleaseTitle(releaseId))

        self.getCoverArt(releaseId, olderThan)

    def deleteRelease(self, releaseId):
        releaseId = utils.getReleaseIdFromInput(releaseId)
        if releaseId not in self:
            raise KeyError('Release does not exist')

        title = self.getReleaseTitle(releaseId)
        self.unDigestRelease(releaseId)
        self.cm.commit()

        _log.info("Deleted '%s'" % title)

    class refreshAllMetaData(dialogs.ThreadedTask):
        def __init__(self, catalog, olderThan=0):
            self.catalog = catalog
            self.olderThan = olderThan
            dialogs.ThreadedTask.__init__(self, 0)

        def run(self):
            self.status = 'Fetching all metadata older than %d seconds...'\
                    % self.olderThan
            self.numer = 0
            self.denom = len(self.catalog)
            for releaseId in self.catalog.getReleaseIds():
                _log.info("Refreshing release %s", releaseId)
                self.catalog.addRelease(releaseId, self.olderThan)
                self.numer += 1
            # NOTE Could delay commit in addRelease and commit once here, but
            # fetching from web is slow, so this extra delay might be
            # acceptable. Also, partial refreshes will be committed as they
            # progress.

    def checkReleases(self):
        """
        Check releases for ugliness such as no barcode, no release format, etc.
        For now, this creates warnings in the log.
        """
        return self.cm.executeAndFetch(
                'select id,sortstring from releases where '+\
                self.badReleaseFilter)

    # TODO maybe cover art tasks should be in another class
    def _getCoverArtPath(self, releaseId):
        return os.path.join(self.cachePath, releaseId[0], releaseId[0:2],
                releaseId, 'cover.jpg')

    def haveCoverArt(self, releaseId):
        return os.path.isfile(self._getCoverArtPath(releaseId))

    def getCoverArt(self, releaseId, maxage=60*60):
        imgPath = self._getCoverArtPath(releaseId)
        if os.path.isfile(imgPath) and os.path.getmtime(imgPath) > \
                (time.time() - maxage):
            _log.info("Already have cover art for " + releaseId + " at '" + \
                imgPath + "', skipping")
            return

        try:
            meta = coverart.getCoverArtMeta(releaseId)
            coverart.saveCoverArt(meta, imgPath)

        except mb.ResponseError as e:
            _log.warning('No cover art for ' + releaseId +
                    ' available from Cover Art Archive')

            # TODO can a release have more than one ASIN? If so, we'd need a
            # separate DB table
            asin = self.getReleaseASIN(releaseId)
            if asin:
                _log.info('Trying to fetch cover art from Amazon instead')
                amazonservices.saveImage(asin,
                        amazonservices.AMAZON_SERVER["amazon.com"],
                        imgPath)
            else:
                _log.warning('No ASIN for '+releaseId+
                        ', cannot fetch from Amazon.')

    def refreshAllCoverArt(self, maxage=60*60*24):
        for releaseId in self.getReleaseIds():
            self.getCoverArt(releaseId, maxage=maxage)

    class checkLevenshteinDistances(dialogs.ThreadedTask):
        """
        Compute the Levenshtein (edit) distance of each pair of releases.

        Returns a sorted list of the most similar releases
        """
        def __init__(self, catalog, limit=None):
            self.catalog = catalog
            self.limit = limit
            dialogs.ThreadedTask.__init__(self, 0)

        def run(self):
            import Levenshtein
            self.status = 'Comparing releases...'
            self.numer = 0
            # This expression results from the nested for loops below
            numRels = len(self.catalog)
            # Without proof,
            self.denom = (numRels**2 - numRels)/2 - \
                ((numRels-self.limit)**2 - (numRels-self.limit))/2
            dists = []

            def getRightUpper(leftIdx, limit):
                if limit is None:
                    return len(self.catalog)
                else:
                    return min(len(self.catalog), leftIdx+1+limit)

            releaseIds = self.catalog.getReleaseIds('order by sortstring')
            for leftIdx in xrange(len(self.catalog)):
                for rightIdx in xrange(leftIdx+1,
                        getRightUpper(leftIdx,self.limit)):
                    leftId = releaseIds[leftIdx]
                    rightId = releaseIds[rightIdx]
                    dist = Levenshtein.distance(
                            self.catalog.getReleaseSortStr(leftId),
                            self.catalog.getReleaseSortStr(rightId))

                    dists.append((dist, leftId, rightId))
                    self.numer += 1

            # TODO could sort the list and truncate it in each iteration above
            self.result = sorted(dists, key=lambda sortKey: sortKey[0])

    class syncCollection(dialogs.ThreadedTask):
        """
        Synchronize the catalog with a MusicBrainz collection.

        For now, only adds releases from the catalog to the collection
        if they do not already exist in the collection.

        In the future, should also reconcile releases in the collection
        that are not in the catalog.
        """
        releasesPerFetch = 25
        releasesPerPost = 100

        def __init__(self, catalog, collectionId):
            self.catalog = catalog
            self.collectionId = collectionId
            dialogs.ThreadedTask.__init__(self, 0)

        def run(self):
            self.status = 'Fetching list of releases in collection...'
            self.numer = 0
            self.denom = 0

            colRelIds = []
            while True:
                _log.info('Fetching %d releases in collection starting at %d.'\
                        % (self.releasesPerFetch, self.numer))
                result = mb.get_releases_in_collection(
                        self.collectionId,
                        limit=self.releasesPerFetch,
                        offset=self.numer)
                col = result['collection']
                relList = col['release-list']
                if len(relList) == 0:
                    break
                self.numer += len(relList)
                for rel in relList:
                    colRelIds.append(rel['id'])

            _log.info('Found %d / %d releases in collection.' % (
                    len(colRelIds), len(self.catalog)))

            relIdsToAdd = list(set(
                    self.catalog.getReleaseIds()) - set(colRelIds))

            _log.info('%d missing releases to add to collection.'\
                % len(relIdsToAdd))
            self.status = 'Going to add %d releases to collection...'\
                % len(relIdsToAdd)
            self.numer = 0
            self.denom = len(relIdsToAdd) / self.releasesPerPost
            for relIdChunk in utils.chunks(relIdsToAdd,
                    self.releasesPerPost):
                mb.add_releases_to_collection(self.collectionId, relIdChunk)
                self.numer += 1

    def makeLabelTrack(self, releaseId, outPath='Audacity Label Track.txt'):
        """
        Useful for importing a label track into Audacity for vinyl transfer.
        """
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
        for mediumId,position,format in self.cm.executeAndFetch(
                'select id,position,format from media '
                'where release=? order by position',
                (releaseId,)):
            stream.write('%-60s %6s\n' % (format+' %d'%position,
                    recLengthAsString(
                        self.getMediumLen(mediumId)
                    )))
            for recId,recLength,recPosition,title in self.cm.executeAndFetch(
                    'select recordings.id, recordings.length, '
                    'medium_recordings.position, recordings.title '
                    'from recordings '
                    'inner join medium_recordings on '
                    'medium_recordings.recording=recordings.id '
                    'inner join media on medium_recordings.medium=media.id '
                    'where media.id=? order by medium_recordings.position',
                    (mediumId,)):
                stream.write(
                    '%-60s ' % title +
                    '%6s' % recLengthAsString(recLength)
                    + '\n')
            stream.write('\n')

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

    def getBasicTable(self, filt=''):
        """
        Fetch "basic" information about all the releases and return a list of
        lists. Accepts SQL code for the 'where' clause in the 'filt' argument.
        """
        # TODO this does not sanitize the 'filt' argument!
        return self.cm.executeAndFetch(
            'select '+','.join(self.basicColumns)+' from releases'+\
            (((' where '+filt) if filt else '')+\
            ' order by sortstring'))

    def getReleaseTitle(self, releaseId):
        return self.cm.executeAndFetchOne(
            'select title from releases where id=?',
            (releaseId,))[0]

    def getReleaseDate(self, releaseId):
        return self.cm.executeAndFetchOne(
            'select date from releases where id=?', (releaseId,))[0]

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
            'select sum(recordings.length) from medium_recordings '
            'inner join recordings '
            'on medium_recordings.recording=recordings.id '
            'where medium_recordings.medium=?',
            (mediumId,))[0]

    def getReleaseLen(self, releaseId):
        return self.cm.executeAndFetchOne(
            'select sum(recordings.length) from releases '
            'inner join media '
            'on media.release=releases.id '
            'inner join medium_recordings '
            'on medium_recordings.medium = media.id '
            'inner join recordings '
            'on medium_recordings.recording=recordings.id '
            'where releases.id=?',
            (releaseId,))[0]

# TODO move to mbcat/ and change to lengthAsTime
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
    return ' + '.join(utils.mergeList(
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
