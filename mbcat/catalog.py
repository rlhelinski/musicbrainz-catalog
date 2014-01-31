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
import sqlite3
import cPickle as pickle
import zlib

# Problem: pickle dumps takes unicode strings but returns binary strings
def listAdapter(l):
    return buffer(pickle.dumps(l))

def listConverter(s):
    return pickle.loads(s)

sqlite3.register_adapter(list, listAdapter)
sqlite3.register_converter(str("list"), listConverter)

overWriteAll = False

import warnings

def deprecated(func):
    """This is a decorator which can be used to mark functions
    as deprecated. It will result in a warning being emmitted
    when the function is used."""
    def newFunc(*args, **kwargs):
        warnings.warn("Call to deprecated function %s." % func.__name__,
                      category=DeprecationWarning)
        return func(*args, **kwargs)
    newFunc.__name__ = func.__name__
    newFunc.__doc__ = func.__doc__
    newFunc.__dict__.update(func.__dict__)
    return newFunc


# Have to give an identity for musicbrainzngs
mb.set_useragent(
    "musicbrainz-catalog",
    "0.1",
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

def releaseSortCmp(a, b):
    return unicode.lower(a[1]) < unicode.lower(b[1])

def chunks(l, n):
    """ Yield successive n-sized chunks from l. """
    for i in range(0, len(l), n):
        yield l[i:i+n]

# This goes with getFormatFromUri(), but can we replace that with a library function?
try:
    import HTMLParser
    h = HTMLParser.HTMLParser()
except ImportError as e:
    import html.parser
    h = html.parser.HTMLParser()

def getFormatFromUri(uriStr, escape=True):
    # TODO deprecate
    #return uriStr.split("#")[1].decode('ascii')
    formatStr = uriStr.split("#", 1)[1]
    if escape:
        return h.unescape(formatStr)
    else:
        return formatStr

def getReleaseIdFromInput(releaseId):
    """Extracts a release ID from a string or a URL"""
    if releaseId.startswith('http'):
        return mbcat.utils.extractUuid(releaseId, 'release')
    else:
        return releaseId

def formatSortCredit(release):
    return ''.join([credit if type(credit)==str else credit['artist']['sort-name'] for credit in release['artist-credit'] ])



class Catalog(object):
    mbUrl = 'http://musicbrainz.org/'
    artistUrl = mbUrl+'artist/'
    labelUrl = mbUrl+'label/'
    releaseUrl = mbUrl+'release/'

    def __init__(self, dbPath='mbcat.db'):
        self.dbPath = dbPath

        self.prefs = mbcat.userprefs.PrefManager()

        # should we connect here, once and for all, or should we make temporary
        # connections to sqlite3? 

    def _connect(self):
        # Let's try here for now, just need to make sure we disconnect when this
        # object is deleted.
        self.conn = sqlite3.connect(self.dbPath)
        return sqlite3.connect(self.dbPath, detect_types=sqlite3.PARSE_DECLTYPES)

    def _resetMaps(self):
        """Drop the derived tables in the database and rebuild them"""
        with self._connect() as con:
            cur = con.cursor()
            for tab in ['words', 'discids', 'barcodes', 'formats']:
                cur.execute('delete * from ?', tab)
            
    def renameRelease(self, releaseId, newReleaseId):
        os.rename(os.path.join('release-id', releaseId),
                os.path.join('release-id', newReleaseId) )
        # TODO this is lazy, but it is the only way to correct all the tables created during load()
        self.load()
        self.refreshMetaData(newReleaseId, olderThan=60)

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
    
    def getRelease(self, releaseId):
        with self._connect() as con:
            cur = con.cursor()
            cur.execute('select meta from releases where id = ?', (releaseId,))
            releaseXml = zlib.decompress(cur.fetchone()[0])

            # maybe it would be better to store the release as a serialized dict in the table
            # then, we could skip this parsing step
            metadata = self.getReleaseDictFromXml(releaseXml)

        return metadata['release']

    def __len__(self):
        """Return the number of releases in the catalog."""
        with self._connect() as con:
            cur = con.cursor()
            cur.execute('select count(id) from releases')
            return cur.fetchone()[0]

    def __contains__(self, releaseId):
        return releaseId in self.metaIndex

    def loadReleaseIds(self):
        fileList = os.listdir(self.rootPath)

        # There's no Fraction() provided in progressbar-python3
        widgets = ["Releases: ", progressbar.Bar(marker="=", left="[", right="]"), " ", progressbar.Percentage() ]
        if len(fileList) > 0:
            pbar = progressbar.ProgressBar(widgets=widgets, maxval=len(fileList)).start()

            for releaseId in fileList:
                if len(releaseId) == 36:
                    #pbar.increment() # progressbar-python3 does not have increment()
                    pbar.update(pbar.currval + 1)
                    yield releaseId
            pbar.finish()

    def saveZip(self, zipName='catalog.zip'):
        """Exports the database as a ZIP archive"""
        import zipfile, StringIO

        with zipfile.ZipFile(zipName, 'w', zipfile.ZIP_DEFLATED) as zf:
            xml_writer = wsxml.MbXmlWriter()
            for releaseId in self.getReleaseIds():
                xmlPath = self._get_xml_path(releaseId)
                XmlParser = wsxml.MbXmlParser()
                with open(xmlPath, 'r') as xmlf:
                    metadata = XmlParser.parse(xmlf)

                memXmlF = StringIO.StringIO()
                xml_writer.write(memXmlF, metadata)
                memXmlF.seek(0)
                zf.writestr(xmlPath, memXmlF.read())

                # TODO write a function to produce these paths
                zf.writestr(self._get_xml_path('extra.xml'), \
                    self.extraIndex[releaseId].toString())

    def loadZip(self, zipName='catalog.zip'):
        import zipfile, StringIO

        zf = zipfile.ZipFile(zipName, 'r')
        XmlParser = wsxml.MbXmlParser()
        for fInfo in zf.infolist():
            if not fInfo.filename.startswith('release-id') or not fInfo.filename.endswith('metadata.xml'):
                continue

            rootPath, releaseId, fileName = fInfo.filename.split('/')
            memXmlF = StringIO.StringIO()
            memXmlF.write(zf.read(fInfo))
            memXmlF.seek(0)
            metadata = XmlParser.parse(memXmlF)
            self.metaIndex[releaseId] = metadata
        zf.close()

    @staticmethod
    def getReleaseWords(rel):
        words = []
        for field in ['title', 'artist-credit-phrase', 'disambiguation']:
            if field in rel:
                words.extend(re.findall(r"\w+", rel[field].lower(), re.UNICODE))
            elif field != 'disambiguation':
                _log.error('Missing field from release '+relId+': '+str(e))

        return words

    def mapWordsToRelease(self, words, releaseId):
        word_set = set(words)
        for word in word_set:
            if word in self.wordMap:
                self.wordMap[word].append(releaseId)
            else:
                self.wordMap[word] = [releaseId]

    def _search(self, query):
        query_words = query.lower().split(' ')
        matches = set()
        with self._connect() as con:
            cur = con.cursor()
            for word in query_words:
                cur.execute('select releases from words where word = ?', (word,))
                fetched = cur.fetchone()
                # if the word is in the table
                if fetched:
                    # for the first word
                    if word == query_words[0]:
                        # use the whole set of releases that have this word
                        matches = set(fetched[0])
                    else:
                        # intersect the releases that have this word with the current release set 
                        matches = matches & set(fetched[0])
                else:
                    # this word is not contained in any releases and therefore
                    # no releases match
                    matches = set()
                    break

        return matches

    def formatDiscInfo(self, releaseId):
        release = self.getRelease(releaseId)
        return ' '.join( [
                releaseId, ':', \
                formatSortCredit(release), '-', \
                (release['date'] if 'date' in release else ''), '-', \
                release['title'], \
                '('+release['disambiguation']+')' if 'disambiguation' in release else '', \
                '['+str(mbcat.formats.getReleaseFormat(release))+']', \
                ] )

    def formatDiscSortKey(self, releaseId):
        release = self.getRelease(releaseId)

        return ' - '.join ( [ \
                formatSortCredit(release), \
                release['date'] if 'date' in release else '', \
                release['title'] + \
                (' ('+release['disambiguation']+')' if 'disambiguation' in release else ''), \
                ] ) 

    def getSortedList(self, matchFmt=None):
        relIds = self.formatMap[matchFmt] if matchFmt else self.getReleaseIds()
            
        sortKeys = [(relId, self.formatDiscSortKey(relId)) for relId in relIds]

        return sorted(sortKeys, key=lambda sortKey: sortKey[1].lower())

    def getSortNeighbors(self, releaseId, neighborHood=5, matchFormat=False):
        """
        Print release with context (neighbors) to assist in sorting and storage of releases.
        """
        # This should be broken down since it writes to the console

        if matchFormat:
            try:
                sortedList = self.getSortedList(\
                    mbcat.formats.getReleaseFormat(\
                        self.getRelease(releaseId)).__class__)
            except KeyError as e:
                _log.warning("Sorting release " + releaseId + " with no format into a list of all releases.")
                sortedList = self.getSortedList()
        else:
            sortedList = self.getSortedList()

        index = sortedList.index((releaseId, self.formatDiscSortKey(releaseId)))
        for i in range(max(0,index-neighborHood), min(len(sortedList), index+neighborHood)):
            sortId, sortStr = sortedList[i]
            print( ('\033[92m' if i == index else "") + "%4d" % i, \
                    sortId, \
                    sortStr, \
                    ("[" + str(mbcat.formats.getReleaseFormat(self.getRelease(sortId))) + "]"), \
                    (" <<<" if i == index else "") + \
                    ('\033[0m' if i == index else "") )


    def search(self, query):
        """Print a list releases that match words in a query."""
        matches = self._search(query)
        for releaseId in matches:
            print(self.formatDiscInfo(releaseId))

    def getWordCount(self):
        """Fetch the number of words in the search word table."""
        with self._connect() as con:
            cur = con.cursor()
            cur.execute('select count(word) from words')
            return cur.fetchone()[0]

    def report(self):
        """Print some statistics about the catalog as a sanity check."""

        print("\n%d releases" % len(self))
        print("%d words in search table" % self.getWordCount())

    def makeHtml(self, fileName=None):
        """
        Write HTML representing the catalog to a file
        """

        if not fileName:
            fileName = os.path.join(self.prefs.htmlPubPath, "catalog.html")

        def fmt(s):
            return s.encode('ascii', 'xmlcharrefreplace').decode()


        htf = open(fileName, 'wt')

        htf.write("""<!DOCTYPE HTML>
<html>
<head>
<title>Music Catalog</title>
<script type="text/javascript" src="http://code.jquery.com/jquery-1.10.2.min.js"></script>
<script type="text/javascript">
$(document).ready(function(){
  $("#toc ul").show();
  $("#togglelink").click(function(e){
    $("#toc ul").slideToggle();
    var isShow = $(this).text() == 'Show';
    $(this).text(isShow ? 'Hide' : 'Show');
  });
  $(".releaserow").click(function(e){
    if(! $(e.target).is("a")) {
        $(this).toggleClass("active");
        $(this).next("tr").slideToggle();
        $(this).next("tr").children("td").children(".togglediv").stop('true','true').slideToggle();
    }
  });
  $(".detailrow").click(function(e){
    if(! $(e.target).is("a")) {
        $(this).prev("tr").toggleClass("active");
        $(this).slideToggle();
        $(this).children("td").children(".togglediv").slideToggle();
    }
  });
});
</script>
<style type="text/css">
.hasTooltip {
    position:relative;
}

.hasTooltip span {
    display:none;
}

.hasTooltip:hover span {
    display:block;
    position:absolute;
    z-index:15;
    background-color:black;
    border-radius:5px;
    color:white;
    box-shadow:1px 1px 3px gray;
    padding:5px;
    top:1.3em;
    left:0px;
    white-space: nowrap;
}

#toc, .toc {
    float: right;
    display: table;
    padding: 7px;
}

#toc, .toc, .mw-warning {
    border: 1px solid rgb(170, 170, 170);
    background-color: rgb(249, 249, 249);
    padding: 5px;
    font-size: 95%;
}

#toc h2, .toc h2 {
    display: inline;
    border: medium none;
    padding: 0px;
    font-size: 100%;
    font-weight: bold;
}

h2 {
    clear: both;
}

.toctoggle{
  display:inline-block;
}

#toc .toctitle, .toc .toctitle {
    text-align: center;
}

.formattable {
    width: 100%;
}

tr.releaserow:hover{
  background-color:beige;
}

.active{
  background-color:beige;
}

.detailrow {
  display:none;
}

.detailrow td{
  vertical-align:top;
  background-color:lightgray;
}

.togglediv {
  display:none;
  }

.time {
  align:right;
}

.coverart {
  max-width:320px; max-height:320px;
  border-radius:5px;
  background-color:black;
  padding:5px;
}

</style>
</head>
<body>""")

        formatsBySize = sorted(self.formatMap.keys(), key=lambda obj: obj())

        htf.write('<a name="top">\n')
        htf.write('<div id="toc">\n')
        htf.write('<div id="toctitle">\n')
        htf.write('<h2>Contents</h2>\n')
        htf.write('<span class="toctoggle">&nbsp;[<a href="#" class="internal" id="togglelink">hide</a>]&nbsp;</span>\n</div>\n')
        htf.write('<ul>\n')
        for releaseType in formatsBySize:
            htf.write('\t<li><a href="#'+str(releaseType())+'">'+\
                str(releaseType())+'</a></li>\n')
        htf.write('</ul>\n')
        htf.write('</div>\n')

        for releaseType in formatsBySize:
            sortedList = self.getSortedList(releaseType)
            if len(sortedList) == 0:
                continue
            htf.write("<h2><a name=\""+str(releaseType())+"\">" + str(releaseType()) + (" (%d Releases)" %
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

                #coverartUrl = mbcat.amazonservices.getAsinImageUrl(rel.asin, mbcat.amazonservices.AMAZON_SERVER["amazon.com"], 'S')
                # Refer to local copy instead
                imgPath = os.path.join(self.rootPath, releaseId, 'cover.jpg')
                coverartUrl = imgPath if os.path.isfile(imgPath) else None

                htf.write("<tr class=\"releaserow\">\n")
                htf.write("<td>" + ''.join( [\
                    credit if type(credit)==str else \
                    "<a href=\""+self.artistUrl+credit['artist']['id']+"\">"+\
                    fmt(credit['artist']['name'])+\
                    "</a>" for credit in rel['artist-credit'] ] ) + "</td>\n")
                htf.write("<td><a href=\""+self.releaseUrl+rel['id']+"\"" + \
                    ">"+fmt(rel['title'])\
                    +(' (%s)' % fmt(rel['disambiguation']) if 'disambiguation' in rel and rel['disambiguation'] else '')\
                    + "</a></td>\n")
                htf.write("<td>"+(fmt(rel['date']) if 'date' in rel else '')+"</td>\n")
                htf.write("<td>"+(fmt(rel['country']) \
                    if 'country' in rel else '')+"</td>\n")
                htf.write("<td>"+', '.join([\
                    "<a href=\""+self.labelUrl+info['label']['id']+"\">"+\
                    fmt(info['label']['name'])+\
                    "</a>" if 'label' in info else '' for info in rel['label-info-list']])+"</td>\n")
                # TODO handle empty strings here (remove from this list before joining)
                htf.write("<td>"+', '.join([\
                    fmt(info['catalog-number']) if \
                    'catalog-number' in info else '' for info in rel['label-info-list']])+"</td>\n")
                htf.write("<td>"+\
                    ('' if 'barcode' not in rel else \
                    rel['barcode'] if rel['barcode'] else
                    '[none]')+"</td>\n")
                htf.write("<td>"+("<a href=\"" + \
                    mbcat.amazonservices.getAsinProductUrl(rel['asin']) + \
                    "\">" + rel['asin'] + "</a>" if 'asin' in rel else '')+"</td>\n")
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
                htf.write('<td>'+('<img class="coverart" src="'+ coverartUrl +'">' if coverartUrl else '')+'</td>\n')
                htf.write('<td>\n')
                htf.write('<table class="tracklist">\n')
                for medium in rel['medium-list']:
                    for track in medium['track-list']:
                        rec = track['recording']
                        length = float(rec['length'])/1000 if 'length' in rec else None
                        htf.write('<tr><td class="time">'+
                            fmt(rec['title']) + '</td><td>' + 
                            (('%d:%02d' % (length/60, length%60)) if length else '?:??') + 
                            '</td></tr>\n')
                htf.write('</table>\n</td>\n')
                htf.write('<td>\n<table class="pathlist">'+\
                    ''.join([\
                        ('<tr><td><a href="'+fmt(path)+'">'+fmt(path)+'</a></td></tr>\n')\
                        for path in self.extraIndex[releaseId].digitalPaths])+\
                    '</table>\n</td>\n')
                htf.write(\
                    "<td>"+(datetime.fromtimestamp( \
                        self.extraIndex[releaseId].addDates[0] \
                        ).strftime('%Y-%m-%d') if \
                    len(self.extraIndex[releaseId].addDates) else '')+"</td>\n")
                htf.write("<td>"+' + '.join([(medium['format'] if 'format' in medium else '(unknown)') for medium in rel['medium-list']])+"</td>\n")

                htf.write('</tr>\n')
                htf.write("</table>\n</div>\n</td>\n</tr>\n")

            htf.write("</table>")

        htf.write("<p>%d releases</p>" % len(self))

        htf.write("""</body>
</html>""")
        htf.close()

    def fetchReleaseMetaXml(self, releaseId):
        """Fetch release metadata XML from musicbrainz"""
        # get_release_by_id() handles throttling on its own
        _log.info('Fetching metadata for ' + releaseId)
        mb.set_parser(mb.mb_parser_null)
        xml = mb.get_release_by_id(releaseId, includes=['artists', 'discids', 'media', 'labels', 'recordings'])
        mb.set_parser()
        return xml

    @deprecated
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

    @deprecated
    def fixMeta(self, discId, releaseId):
        results_meta = self.fetchReleaseMetaXml(releaseId)

        self.writeXml(discId, results_meta)

    def loadMetaData(self, releaseId):
        """Load metadata from disk"""
        xmlPath = self._get_xml_path(releaseId)
        if (not os.path.isfile(xmlPath)):
            _log.error("No XML metadata for %s", releaseId)
            return None
        with open(xmlPath, 'r') as xmlf:
            metaxml = xmlf.read()

        return self.getReleaseDictFromXml(metaxml)['release']

    def digestReleaseXml(self, releaseId, metaXml):
        relDict = self.getReleaseDictFromXml(metaXml)
        
        with self._connect() as con:
            cur = con.cursor()

            # Update releases table
            cur.execute('insert into releases(id, meta, metatime, purchases, added, lent, listened, digital, count, comment, rating) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                    (
                        releaseId, 
                        buffer(zlib.compress(metaXml)), 
                        time.time(),
                        [],
                        [time.time()],
                        [],
                        [],
                        [],
                        1, # set count to 1 for now 
                        '',
                        0
                    )
                )

            # Update words table
            rel_words = self.getReleaseWords(relDict)
            for word in rel_words:
                sql_list_append(cur, 'words', 'word', word, relId)

            # Update barcodes -> (barcode, releases)
            if 'barcode' in relDict and relDict['barcode']:
                sql_list_append(cur, 'barcodes', 'barcode', relDict['barcode'], relId)

            # Update discids -> (discid, releases)
            for medium in relDict['medium-list']:
                for disc in medium['disc-list']:
                    sql_list_append(cur, 'discids', 'discid', disc['id'], relId)

            # Update formats -> (format, releases)
            fmt = mbcat.formats.getReleaseFormat(relDict).__class__.__name__
            sql_list_append(cur, 'formats', 'format', fmt, relId)

            con.commit()

    def searchDigitalPaths(self, releaseId=''):
        releaseIdList = [releaseId] if releaseId else self.getReleaseIds() 

        # TODO could use progressbar here
        # TODO need to be more flexible in capitalization and re-order of words
        for relId in releaseIdList:
            #print relId
            for path in self.prefs.musicPaths:
                #print path
                rel = self.getRelease(relId)
                for artistName in [ rel['artist-credit-phrase'], rel['artist-credit'][0]['artist']['sort-name'] ]:
                    artistPath = os.path.join(path, artistName)
                    if os.path.isdir(artistPath):
                        #print 'Found ' + artistPath
                        for titleName in [rel['title']]:
                            titlePath = os.path.join(artistPath, titleName)
                            if os.path.isdir(titlePath):
                                _log.info('Found ' + relId + ' at ' + titlePath)
                                self.extraIndex[relId].addPath(titlePath)
            self.extraIndex[relId].save()

        if releaseId and not self.extraIndex[relId].digitalPaths:
            _log.warning('No digital paths found for '+releaseId)


    def addRelease(self, releaseId, olderThan=0):
        """Get metadata XML from MusicBrainz and add to catalog."""

        releaseId = getReleaseIdFromInput(releaseId)
        xmlPath = self._get_xml_path(releaseId)
        if (os.path.isfile(xmlPath) and (os.path.getmtime(xmlPath) > (time.time() - olderThan))):
            _log.info("Skipping fetch of metadata for %s because it is recent", releaseId)
            return 0

        metaXml = self.fetchReleaseMetaXml(releaseId)
        self.digestReleaseXml(releaseId, metaXml)

    def deleteRelease(self, releaseId):
        releaseId = getReleaseIdFromInput(releaseId)
        shutil.rmtree(os.path.join(self.rootPath, releaseId))
        # also drop from memory
        #del self.releaseIndex[releaseId] # TODO necessary?
        self.load()

    def refreshAllMetaData(self, olderThan=0):
        for releaseId in self.loadReleaseIds():
            _log.info("Refreshing %s", releaseId)
            self.refreshMetaData(releaseId, olderThan)

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

    def getCoverArt(self, releaseId, maxage=60*60):
        release = self.getRelease(releaseId)
        imgPath = os.path.join(self.rootPath, releaseId, 'cover.jpg')
        if os.path.isfile(imgPath) and os.path.getmtime(imgPath) > time.time() - maxage:
            _log.info("Already have cover art for " + releaseId + ", skipping")
            return

        try:
            meta = mbcat.coverart.getCoverArtMeta(releaseId)
            mbcat.coverart.saveCoverArt(meta, imgPath)

        except mb.ResponseError as e:
            _log.warning('No cover art for ' + releaseId + ' available from Cover Art Archive')
                
            if 'asin' in release:
                _log.info('Trying to fetch cover art from Amazon instead')
                mbcat.amazonservices.saveImage(release['asin'], mbcat.amazonservices.AMAZON_SERVER["amazon.com"], imgPath)
            else:
                _log.warning('No ASIN for ' + releaseId + ', cannot fetch from Amazon.')

    def refreshAllCoverArt(self, maxage=60*60*24):
        for releaseId in self.getReleaseIds():
            self.getCoverArt(releaseId, maxage=maxage)

    def checkLevenshteinDistances(self):
        import Levenshtein
        dists = []

        widgets = ["Releases: ", progressbar.Bar(marker="=", left="[", right="]"), " ", progressbar.Percentage() ]
        maxval = (float(len(self)**2) - float(len(self)))/2
        pbar = progressbar.ProgressBar(widgets=widgets, maxval=maxval).start()
        for leftIdx in range(len(self)):
            for rightIdx in range(leftIdx, len(self)):
                if  leftIdx == rightIdx :
                    continue
                leftId = self.getReleaseIds()[leftIdx]
                rightId = self.getReleaseIds()[rightIdx]
                dist = Levenshtein.distance(self.formatDiscSortKey(leftId),
                        self.formatDiscSortKey(rightId))

                dists.append((dist,leftId, rightId))
                pbar.update(pbar.currval + 1)
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
            result = mb.get_releases_in_collection(colId, limit=25, offset=count)
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
        for relIdChunk in chunks(relIdsToAdd, 100):
            mb.add_releases_to_collection(colId, relIdChunk)
        print('DONE')

    def makeLabelTrack(self, releaseId, outPath='Label Track.txt'):
        """Useful for importing into Audacity."""
        rel = self.getRelease(releaseId)
        with open(outPath, 'wt') as f:
            pos = 0.0
            for medium in rel['medium-list']:
                for track in medium['track-list']:
                    rec = track['recording']
                    if 'length' not in rec:
                        _log.warning('Track '+track['number']+' length is empty in '+releaseId)
                    length = float(rec['length'])/1000 if 'length' in rec else 2*60
                    f.write('%.6f\t%.6f\t%s\n' % (pos, pos+length, rec['title']))
                    pos += length
        _log.info('Wrote label track for '+releaseId+' to '+outPath)

    def writeMetaTags(self, releaseId, outPath='Tags.xml'):
        """Useful for importing metadata into Audacity."""
        myxml = etree.Element('tags')
        rel = self.getRelease(releaseId)

        for name, value in [
                ('ALBUM', rel['title'] + (' ('+rel['disambiguation']+')' if 'disambiguation' in rel else '')),
                ('YEAR', rel['date'] if 'date' in rel else ''),
                ('ARTIST', rel['artist-credit-phrase']),
                ('COMMENTS', self.releaseUrl+releaseId),
                ]:
            subTag = etree.SubElement(myxml, 'tag', attrib=\
                {'name': name, 'value':value})

        with open(outPath, 'wb') as xmlfile:
            xmlfile.write(etree.tostring(myxml))

        _log.info('Saved Audacity tags XML for '+releaseId+' to \'%s\'' % outPath)

    def writeTrackList(self, stream, releaseId):
        """Write ASCII tracklist for releaseId to 'stream'. """
        stream.write('\n')
        rel = self.getRelease(releaseId)
        for medium in rel['medium-list']:
            for track in medium['track-list']:
                rec = track['recording']
                length = float(rec['length'])/1000 if 'length' in rec else None
                stream.write(
                    rec['title'] + 
                    ' '*(60-len(rec['title'])) + 
                    (('%3d:%02d' % (length/60, length%60)) if length else '  ?:??') + 
                    '\n')


