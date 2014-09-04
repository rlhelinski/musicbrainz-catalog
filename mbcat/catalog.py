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
from datetime import datetime
from collections import defaultdict
import progressbar
import logging
_log = logging.getLogger("mbcat")
import zlib
import sqlite3
import itertools

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

        self._connect()

    def _connect(self):
        # Open and retain a connection to the database
        self.conn = self._get_connection()
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

    def _get_connection(self):
        # this connection should be closed when this object is deleted
        return sqlite3.connect(self.dbPath,
                detect_types=sqlite3.PARSE_DECLTYPES)

    def _createTables(self):
        """Create the SQL tables for the catalog. Database is assumed empty."""
        # TODO maybe store the metadata dict from musicbrainz instead of the XML?
        self.curs.execute("CREATE TABLE releases("
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
            "metatime FLOAT, "
            "count INT DEFAULT 1, "
            "comment TEXT, "
            "rating INT DEFAULT 0)")

        # Indexes for speed (it's all about performance...)
        cursor.execute('create unique index release_id on releases (id)')
        for col in ['sortstring', 'catno', 'barcode', 'asin']:
            cursor.execute('create index release_'+col+\
                ' on releases ('+col+')')

        self._createMetaTables()

        self._createCacheTables()

        self.conn.commit()

    def _createMetaTables(self):
        for columnName, columnType in [
                ('added_date', 'FLOAT'),
                ('listened_date', 'FLOAT'),
                ]:

            self.curs.execute('CREATE TABLE '+columnName+'s('+\
                columnName+' '+columnType+', release TEXT, '
                'FOREIGN KEY(release) REFERENCES releases(id) '
                'ON DELETE CASCADE)')

        self.curs.execute('CREATE TABLE purchases ('
            'date FLOAT, '
            'price FLOAT, '
            'vendor TEXT, '
            'release TEXT, '
            'FOREIGN KEY(release) REFERENCES releases(id) '
            'ON DELETE CASCADE)')

        # checkout, checkin (lent out, returned) tables
        self.curs.execute('CREATE TABLE checkout_events ('
            'borrower TEXT, '
            'date FLOAT, '
            'release TEXT, '
            'FOREIGN KEY(release) REFERENCES releases(id) '
            'ON DELETE CASCADE)')

        self.curs.execute('CREATE TABLE checkin_events ('
            'date FLOAT, '
            'release TEXT, '
            'FOREIGN KEY(release) REFERENCES releases(id) '
            'ON DELETE CASCADE)')

        # Digital copy table
        self.curs.execute('CREATE TABLE digital ('
            'release TEXT, '
            'format TEXT, '
            'path TEXT, '
            'FOREIGN KEY(release) REFERENCES releases(id) '
            'ON DELETE CASCADE)')

    def _createCacheTables(self):
        """Add the release-derived tables to the database.
        This method does not commit its changes."""
        # tables that map specific things to a list of releases
        for columnName, columnType in [
                ('word', 'TEXT'),
                ]:

            self.curs.execute('CREATE TABLE '+columnName+'s('+\
                columnName+' '+columnType+', release TEXT, '
                'FOREIGN KEY(release) REFERENCES releases(id) '
                'ON DELETE CASCADE)')

        self.curs.execute('CREATE TABLE recordings ('
            'id TEXT, '
            'title TEXT, '
            'length INTEGER, '
            'release TEXT, '
            'FOREIGN KEY(release) REFERENCES releases(id) '
            'ON DELETE CASCADE)')

        self.curs.execute('CREATE TABLE trackwords('
            'trackword TEXT, recording TEXT, '
            'FOREIGN KEY(recording) REFERENCES recordings(id) '
            'ON DELETE CASCADE)')

        self.curs.execute('CREATE TABLE discids ('
            'discid TEXT, '
            'release TEXT, '
            'FOREIGN KEY(release) REFERENCES releases(id) '
            'ON DELETE CASCADE)')

        # Indexes for speed (it's all about performance...)
        self.curs.execute('create index word_index on words (word)')
        self.curs.execute('create index trackword_index '
            'on trackwords (trackword)')

    def updateCacheTables(self, rebuild, pbar=None):
        """Use the releases table to populate the derived (cache) tables"""
        yield 'Rebuilding tables...'
        yield len(self)
        for releaseId in self.getReleaseIds():
            metaXml = self.getReleaseXml(releaseId)
            self.digestReleaseXml(releaseId, metaXml, rebuild=rebuild)
            yield True
        yield 'Committing changes...'
        self.conn.commit()
        yield False

    def rebuildCacheTables(self, pbar=None):
        """Drop the derived tables in the database and rebuild them"""
        # Get our own connection and cursor for this thread
        self._connect()
        yield 'Dropping tables...'
        yield 15

        for tab in ['words', 'trackwords', 'recordings', 'discids']:
            # Note: the added_dates, listened_dates, and purchases tables are
            # not transient.
            try:
                self.curs.execute('drop table '+tab)
            except sqlite3.OperationalError as e:
                pass
            yield True

        for index in ['word_index', 'trackword_index']:
            try:
                self.curs.execute('drop index if exists '+index)
            except sqlite3.OperationalError as e:
                pass
            yield True

        self._createCacheTables()

        # Rebuild
        g = self.updateCacheTables(rebuild=True)
        for r in g:
            yield r

        yield False

    def renameRelease(self, releaseId, newReleaseId):
        # TODO this does not update purchases, checkout_events, checkin_events,
        # digital
        self.deleteRelease(releaseId)
        self.addRelease(newReleaseId, olderThan=60)

    def getReleaseIds(self):
        self.curs.execute('select id from releases')
        listOfTuples = self.curs.fetchall()
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
        """Return a release's musicbrainz XML metadata from the local cache"""

        self.curs.execute('select meta from releases where id = ?',
            (releaseId,))
        try:
            releaseXml = zlib.decompress(self.curs.fetchone()[0])
        except TypeError:
            raise KeyError ('release %s not found' % releaseId)
        return releaseXml

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
        self.curs.execute('select id from releases where format=?', (fmt,))
        return itertools.chain.from_iterable(self.curs.fetchall())

    def getFormats(self):
        self.curs.execute('select distinct format from releases')
        return itertools.chain.from_iterable(self.curs.fetchall())

    # TODO rename to getReleaseByBarCode
    def barCodeLookup(self, barcode):
        self.curs.execute('select id from releases where barcode=?', (barcode,))
        result = self.curs.fetchall()
        if not result:
            raise KeyError('Barcode not found')
        return result[0][0]

    def __len__(self):
        """Return the number of releases in the catalog."""
        self.curs.execute('select count(id) from releases')
        return self.curs.fetchone()[0]

    def __contains__(self, releaseId):
        self.curs.execute('select count(id) from releases where id=?',
                (releaseId,))
        count = self.curs.fetchone()[0]
        return count > 0

    def getCopyCount(self, releaseId):
        self.curs.execute('select count from releases where id=?',
                (releaseId,))
        # TODO error not handled if release does not exist
        return self.curs.fetchone()[0]

    def setCopyCount(self, releaseId, count):
        self.curs.execute('update releases set count=? where id=?',
                (count, releaseId))
        self.conn.commit()

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
            self.conn.commit()
            if pbar:
                pbar.finish()

    @staticmethod
    def processWords(field, d):
        if field in d:
            return re.findall(r"[\w'.]+", d[field].lower(), re.UNICODE)
        elif field != 'disambiguation':
            _log.warning('Release '+relId+' is missing the '+field+' field')
        return set()

    @staticmethod
    def getReleaseWords(rel):
        words = set()
        relId = rel['id']

        for field in ['title', 'artist-credit-phrase', 'disambiguation']:
            words.update(mbcat.Catalog.processWords(field, rel))
        for credit in rel['artist-credit']:
            for field in ['sort-name', 'disambiguation', 'name']:
                if field in credit:
                    words.update(mbcat.Catalog.processWords(field, credit))

        return words

    @staticmethod
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
        """

        for track in mbcat.Catalog.getReleaseTracks(rel):
            if 'recording' in track and 'title' in track['recording']:
                # Add recording and reference the release
                self.curs.execute('insert into recordings '
                    '(id, title, length, release) values (?,?,?,?)', 
                    (track['recording']['id'], track['recording']['title'],
                    track['recording']['length'] \
                    if 'length' in track['recording'] else None, rel['id']))
                for word in mbcat.Catalog.processWords('title',
                    track['recording']):
                    # Reference each word to this recording
                    self.curs.execute('insert into trackwords '
                        '(trackword, recording) values (?,?)', 
                        (word, track['recording']['id']))

    def unDigestTrackWords(self, rel):
        """
        Undo what digestTrackWords() does.
        """
        self.curs.execute('select id from recordings where release=?', 
            (rel['id'],))
        for recordingId in self.curs:
            self.curs.execute('delete from trackwords where recording=?', 
                (recordingId[0],))
        # Should do this in its own function
        self.curs.execute('delete from recordings where release=?',
            (rel['id'],))

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
        for word in query_words:
            self.curs.execute('select releases from %s where %s = ?' % \
                    (table, keycolumn),
                    (word,))
            # get the record, there should be one or none
            fetched = self.curs.fetchone()
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
        self.curs.execute(
            'select releases from recordings where recording = ?',
            (recordingId,))
        # get the record, there should be one or none
        fetched = self.curs.fetchone()

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
        self.curs.execute('select title,length from recordings '
            'where recording=?', (recordingId,))
        recordingRow = self.curs.fetchall()[0]

        return '%s: %s (%s)' % (recordingId, recordingRow[0],
            mbcat.Catalog.formatRecordingLength(recordingRow[1]))

    def getRecordingTitle(self, recordingId):
        self.curs.execute('select title from recordings '
            'where recording=?', (recordingId,))
        return self.curs.fetchone()[0]

    def getRecordingLength(self, recordingId):
        self.curs.execute('select length from recordings '
            'where recording=?', (recordingId,))
        return self.curs.fetchone()[0]

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

        self.curs.execute('select sortstring from releases where id = ?',
                (releaseId,))
        sortstring = self.curs.fetchone()[0]

        # TODO isn't this done while digesting XML?
        if not sortstring:
            # cache it for next time
            sortstring = self.getSortStringFromRelease(
                    self.getRelease(releaseId))
            self.curs.execute('update releases set sortstring=? where id=?',
                    (sortstring, releaseId))
            self.curs.commit()

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
        try:
            self.curs.execute('select count(distinct word) from words')
            return self.curs.fetchone()[0]
        except sqlite3.OperationalError:
            return 0

    def getTrackWordCount(self):
        """Fetch the number of words in the track search word table."""
        try:
            self.curs.execute('select count(distinct trackword) from trackwords')
            return self.curs.fetchone()[0]
        except sqlite3.OperationalError:
            return 0

    def getComment(self, releaseId):
        """Get the comment for a release (if any)."""
        self.curs.execute('select comment from releases where id=?',
            (releaseId,))
        return self.curs.fetchone()[0]

    def setComment(self, releaseId, comment):
        """Set the comment for a release."""
        self.curs.execute('update releases set comment=? where id=?',
            (comment, releaseId))
        self.conn.commit()

    def getDigitalPaths(self, releaseId):
        self.curs.execute('select digital from releases where id=?',
                (releaseId,))
        return self.curs.fetchall()[0][0]

    def addDigitalPath(self, releaseId, format, path):
        existingPaths = self.getDigitalPaths(releaseId)
        self.curs.execute('insert into digital (release, format, path) '
                'values (?,?,?)', (releaseId, format, path))
        self.conn.commit()

    def getAddedDates(self, releaseId):
        self.curs.execute('select added from releases where id=?',
            (releaseId,))
        return self.curs.fetchall()[0][0]

    def addAddedDate(self, releaseId, date):
        # input error checking
        if (type(date) != float):
            try:
                date = float(date)
            except ValueError as e:
                raise ValueError('Date object must be a floating-point number')

        existingDates = self.getAddedDates(releaseId)
        self.curs.execute('update releases set added=? where id=?',
            (existingDates+[date],releaseId))
        self.conn.commit()

    def getCheckOutEvents(self, releaseId):
        # TODO should use sqlite3.Row as the conn.row_factory for these fetches
        self.curs.execute('select borrower,date from checkout_events where '
            'release=?', (releaseId,))
        return self.curs.fetchall()

    def getCheckInEvents(self, releaseId):
        # TODO should use sqlite3.Row as the conn.row_factory for these fetches
        self.curs.execute('select date from checkin_events where '
            'release=?', (releaseId,))
        return self.curs.fetchall()

    def addCheckOutEvent(self, releaseId, borrower, date):
        self.curs.execute('insert into checkout_events '
            '(borrower, date, release) values (?,?,?)',
            (borrower, date, releaseId))
        self.conn.commit()

    def addCheckInEvent(self, releaseId, date):
        self.curs.execute('insert into checkin_events (date,release) '
            'where release=?', (date, releaseId))
        self.conn.commit()

    def getRating(self, releaseId):
        self.curs.execute('select rating from releases where id=?',
            (releaseId,))
        result = self.curs.fetchall()
        return result[0][0] if result else None

    def setRating(self, releaseId, rating):
        self.curs.execute('update releases set rating=? where id=?',
                (rating, releaseId))
        self.conn.commit()

    def getPurchases(self, releaseId):
        self.curs.execute('select date,price,vendor from purchases '
            'where release=?', (releaseId,))
        return self.curs.fetchall()

    def addPurchase(self, releaseId, date, price, vendor):
        # Some error checking
        if not isinstance(date, str) and not isinstance(date, unicode):
            raise ValueError ('Wrong type for date')
        if not isinstance(price, str) and not isinstance(price, unicode):
            raise ValueError ('Wrong type for date')
        if not isinstance(vendor, str) and not isinstance(vendor, unicode):
            raise ValueError ('Wrong type for date')

        self.curs.execute('insert into purchases (date,price,vendor,release) '
            'values (?,?,?,?)', (date,price,vendor,releaseId))
        self.conn.commit()

    def getListenDates(self, releaseId):
        self.curs.execute('select listened_date from listened_dates '
            'where release=?', (releaseId,))
        # chain flattens whatever list of column lists that come back
        return itertools.chain.from_iterable(self.curs.fetchall())

    def addListenDate(self, releaseId, date):
        # Some precursory error checking
        if not isinstance(date, float):
            raise ValueError ('Wrong type for date argument')
        self.curs.execute('insert into listened_dates (listened_date, release) '
            'values (?,?)', (date,releaseId))
        self.conn.commit()

    @mbcat.utils.deprecated
    def getExtraData(self, releaseId):
        """Put together all of the metadata added by mbcat. This might be
        removed in a later release, only need it when upgrading from 0.1."""
        self.curs.execute('select purchases,added,lent,listened,digital,count,'
                'comment,rating from releases where id=?', (releaseId,))
        purchases,added,lent,listened,digital,count,comment,rating = \
                self.curs.fetchall()[0]

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
        self.curs.execute('update releases set '+\
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
        self.conn.commit()

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

    def digestReleaseXml(self, releaseId, metaXml, rebuild=False):
        """Update the appropriate data structes for a new release."""
        relDict = self.getReleaseDictFromXml(metaXml) # parse the XML

        exists = releaseId in self
        now = time.time()

        self.curs.execute('insert into added_dates '
            '(added_date, release) values (?, ?)',
            (now, releaseId))
        if not exists:
            # Update releases table
            newColumns = [
                'id',
                'meta',
                'metatime',
                ]

            try:
                self.curs.execute('insert into releases (' + \
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
            self.curs.execute('update releases set meta=?,sortstring=?,'
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
            ('format', mbcat.formats.getReleaseFormat(
                relDict['release']).name()),
            ]

        self.curs.execute('update releases set '+\
            ','.join([key+'=?' for key,val in metaColumns])+\
            ' where id=?',
            [val for key,val in metaColumns] + [releaseId]
            )

        # Update words table
        rel_words = self.getReleaseWords(relDict['release'])
        for word in rel_words:
            self.curs.execute('insert into words (word,release) values (?,?)',
                (word, releaseId))

        # Update words -> (word, recordings) and
        # recordings -> (recording, releases)
        self.digestTrackWords(relDict['release'])

        # Update discids -> (discid, releases)
        for medium in relDict['release']['medium-list']:
            for disc in medium['disc-list']:
                self.curs.execute('insert into discids '
                    '(discid, release) values (?,?)',
                    (disc['id'], releaseId))

    def unDigestRelease(self, releaseId, delete=True):
        """Remove all references to a release from the data structures.
        Optionally, leave the release in the releases table.
        This function does not commit its changes to the connection.
        See also: digestReleaseXml()"""
        relDict = self.getRelease(releaseId)

        if delete:
            # Update releases table
            self.curs.execute('delete from releases where id = ?',
                (releaseId,))

        # Update words table
        rel_words = self.getReleaseWords(relDict)
        for word in rel_words:
            self.curs.execute('delete from words where release=?',
                (releaseId,))

        # Update words -> (word, recordings) and
        # recordings -> (recording, releases)
        self.unDigestTrackWords(relDict)

        # Update discids -> (discid, releases)
        for medium in relDict['medium-list']:
            for disc in medium['disc-list']:
                self.curs.execute('delete from discids where discid=?',
                    (disc['id'],))

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
        self.curs.execute('select metatime from releases where id = ?',
            (releaseId,))
        r = self.curs.fetchone()
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
        self.conn.commit()

    def deleteRelease(self, releaseId):
        releaseId = mbcat.utils.getReleaseIdFromInput(releaseId)
        self.unDigestRelease(releaseId)
        self.conn.commit()

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
    @staticmethod
    def _getCoverArtPath(releaseId):
        return os.path.join(self.cachePath, releaseId[0], releaseId[0:2],
                releaseId, 'cover.jpg')

    def getCoverArt(self, releaseId, maxage=60*60):
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
        self.curs.execute('select '+','.join(self.basicColumns)+\
            ' from releases'+\
            ((' where '+','.join(
                key+'=?' for key in filt.keys()
                )) if filt else ''),
            filt.values())
        return self.curs

    def getReleaseTitle(self, releaseId):
        self.curs.execute('select title from releases where id=?',
            (releaseId,))
        return self.curs.fetchone()[0]

    def getReleaseArtist(self, releaseId):
        self.curs.execute('select artist from releases where id=?',
            (releaseId,))
        return self.curs.fetchone()[0]

    def getReleaseFormat(self, releaseId):
        self.curs.execute('select format from releases where id=?',
            (releaseId,))
        return self.curs.fetchone()[0]

    def getReleaseASIN(self, releaseId):
        self.curs.execute('select asin from releases where id=?',
            (releaseId,))
        cols = self.curs.fetchone()
        return cols[0] if cols else None

def recLengthAsString(recLength):
    if not recLength:
        return '?:??'
    # convert milli-seconds to seconds
    length = float(recLength)/1000
    return ('%d:%02d' % (length/60, length%60))

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

