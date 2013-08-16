import os, sys, time, re
import musicbrainz2.wsxml as wsxml
import musicbrainz2.utils as mbutils
import musicbrainz2.webservice as ws
import amazonservices
import urllib2
import extradata
from datetime import datetime

overWriteAll = False
lastQueryTime = 0

def releaseSortCmp(a, b):
    return unicode.lower(a[1]) < unicode.lower(b[1])

import HTMLParser
h = HTMLParser.HTMLParser()

def getFormatFromUri(uriStr, escape=True):
    #return uriStr.split("#")[1].decode('ascii')
    formatStr = uriStr.split("#", 1)[1]
    if escape:
        return h.unescape(formatStr)
    else:
        return formatStr

class ReleaseFormat(object):
    def __init__(self, fmtStr=""):
        self.fmtStr = fmtStr

    def isVinyl(self):
        return (self.fmtStr in ["Vinyl", "7\"", "10\"", "12\""])

    def isCD(self):
        return not self.isVinyl() and self.fmtStr != ""

    def isAny(self):
        return self.fmtStr == ""

    def __eq__(self, other):
        return (self.isVinyl() and other.isVinyl()) or \
                (self.isCD() and other.isCD()) or \
                (self.isAny() and other.isAny())

class Catalog(object):
    def __init__(self, rootPath='release-id'):
        self.rootPath = rootPath
        self.releaseIndex = dict()
        self.wordMap = dict()
        self.discIdMap = dict()
        self.barCodeMap = dict()

    def load(self):
        self.releaseIndex = dict()
        # To map ReleaseId -> Format
        #self.formatMap = dict()
        # It would enhance performance but is redundant. Not implemented because
        # performance is tolerable.
        self.wordMap = dict()
        self.discIdMap = dict()
        self.barCodeMap = dict()
        for releaseId in os.listdir(self.rootPath):
            if releaseId.startswith('.') or len(releaseId) != 36:
                continue
            xmlPath = os.path.join(self.rootPath, releaseId, 'metadata.xml')
            if (not os.path.isfile(xmlPath)):
                print "No metadata for", releaseId
                continue
            xmlf = open(xmlPath, 'r')
            XmlParser = wsxml.MbXmlParser()
            metadata = XmlParser.parse(xmlf)
            xmlf.close()
            release = metadata.getRelease()
            self.releaseIndex[releaseId] = release

            for disc in release.discs:
                if disc.id in self.discIdMap:
                    self.discIdMap[disc.id].append(releaseId)
                else:
                    self.discIdMap[disc.id] = [releaseId]

            for releaseEvent in release.releaseEvents:
                if releaseEvent.barcode:
                    if releaseEvent.barcode in self.barCodeMap:
                        self.barCodeMap[releaseEvent.barcode].append(releaseId)
                    else:
                        self.barCodeMap[releaseEvent.barcode] = [releaseId]
            # for searching later
            words = self.getReleaseWords(release)
            self.mapWordsToRelease(words, releaseId)

    def getReleaseWords(self, release):
        words = []
        for field in [
                release.title, \
                release.artist.getName() ] + \
                [track.title for track in release.tracks] \
                :
            words.extend(re.findall(r"\w+", field.lower(), re.UNICODE))
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
        for word in query_words:
            if word in self.wordMap:
                if len(matches) > 0:
                    matches = matches & set(self.wordMap[word])
                else:
                    matches = set(self.wordMap[word])
            else:
                matches = set()

        return matches

    def formatDiscInfo(self, releaseId):
        release = self.releaseIndex[releaseId]
        return ' '.join( [
                releaseId, ':', \
                (release.releaseEvents[0].getDate() if len(release.releaseEvents) else ''), '-', \
                release.artist.getName(), '-', \
                release.title, \
                ('['+getFormatFromUri(release.releaseEvents[0].format)+']' if len(release.releaseEvents) else ''), \
                ] )

    def formatDiscSortKey(self, releaseId):
        release = self.releaseIndex[releaseId]

        try:
            return ' - '.join ( [
                    release.artist.getSortName(), \
                    release.releaseEvents[0].date, \
                    release.title, \
                    ] ) 
        except IndexError as e:
            print "No releases or date for: ", releaseId

        return ' - '.join ( [
                release.artist.getSortName(), \
                "0", \
                release.title, \
                ] ) 

    def getSortedList(self, matchFormat=ReleaseFormat()):
        sortKeys = [(releaseId, self.formatDiscSortKey(releaseId)) for releaseId in self.releaseIndex.keys()]

        # TODO this could be sped up using a map from ReleaseId -> Format populated at loading time
        if not matchFormat.isAny():
            filteredSortKeys = []
            for sortId, sortStr in sortKeys:
                if len(self.releaseIndex[sortId].releaseEvents):
                    releaseFmt = getFormatFromUri(self.releaseIndex[sortId].releaseEvents[0].format)
                    if ReleaseFormat(releaseFmt) == matchFormat:
                        filteredSortKeys.append((sortId, sortStr))
                else:
                    print "No release events for " + sortId + ", " + sortStr
        else:
            filteredSortKeys = sortKeys

        self.sortedList = sorted(filteredSortKeys, key=lambda sortKey: unicode.lower(sortKey[1]))
        return self.sortedList

    def getSortNeighbors(self, releaseId, neighborHood=5, matchFormat=False):
        """>>> c.getSortNeighbors('oGahy0j6T2gXkGBLqSfaXqL.kMo-')
        """

        if matchFormat:
            try:
                self.getSortedList(
                        ReleaseFormat(
                                getFormatFromUri(
                                        self.releaseIndex[releaseId].releaseEvents[0].format)))
            except IndexError as e:
                print "No format for release"
                self.getSortedList()
        else:
            self.getSortedList()

        index = self.sortedList.index((releaseId, self.formatDiscSortKey(releaseId)))
        for i in range(max(0,index-neighborHood), min(len(self.sortedList), index+neighborHood)):
            sortId, sortStr = self.sortedList[i]
            print ('\033[92m' if i == index else "") + "%4d" % i, \
                    sortId, \
                    sortStr, \
                    ("[" + getFormatFromUri(self.releaseIndex[sortId].releaseEvents[0].format) + "]" if len(self.releaseIndex[sortId].releaseEvents) else ""), \
                    (" <<<" if i == index else "") + \
                    ('\033[0m' if i == index else "")


    def search(self, query):
        matches = self._search(query)
        for releaseId in matches:
            print self.formatDiscInfo(releaseId)

    def report(self):
        print
        print "%d release-id records" % len(self.releaseIndex)
        print "%d words in search table" % len(self.wordMap)

    def makeHtml(self, fileName="catalog.html"):
        import amazonservices
        htf = open(fileName, 'w')

        print >> htf, """<!DOCTYPE HTML>
<html>
<head>
<title>Music Catalog</title>
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

</style>
</head>
<body>"""

        for releaseType in [ReleaseFormat("CD"), ReleaseFormat("Vinyl")]:
            sortedList = self.getSortedList(releaseType)
            print >> htf, "<h2>" + releaseType.fmtStr + (" (%d Releases)" % len(sortedList)) + "</h2>"
            print >> htf, "<table>"
            print >> htf, """<tr>
<!-- <th>Sort Index</th> -->
<th>Artist</th>
<th>Release Title</th>
<th>Date</th>
<th>Country</th>
<th>Label</th>
<th>Catalog #</th>
<th>Barcode</th>
<th>ASIN</th>
<th>Format</th>
<th>Date Added</th>
</tr>
"""
            for sortIndex, (releaseId, releaseSortStr) in enumerate(sortedList):
                release = self.releaseIndex[releaseId]
                ed = extradata.ExtraData(releaseId)
                try: 
                    ed.load()
                except IOError as e:
                    print "No extradata for " + releaseId

                if release.asin:
                    coverartUrl = amazonservices.getAsinImageUrl(release.asin, amazonservices.AMAZON_SERVER["amazon.com"], 'S')
                else:
                    coverartUrl = None

                print >> htf, "<tr>"
                print >> htf, "<!-- <td>"+("%04d" % sortIndex)+"</td> -->"
                print >> htf, "<td><a href=\""+release.artist.id+"\">"+self.releaseIndex[releaseId].artist.name.encode('ascii', 'xmlcharrefreplace')+"</a></td>"
                print >> htf, "<td><a href=\""+release.id+"\"" + (" class=\"hasTooltip\"" if coverartUrl else "") + ">"+release.title.encode('ascii', 'xmlcharrefreplace')+("<span><img src=\""+ coverartUrl +"\"></span>" if coverartUrl else "") + "</a></td>"
                print >> htf, "<td>"+(release.releaseEvents[0].date if len(release.releaseEvents) else '')+"</td>"
                print >> htf, "<td>"+(release.releaseEvents[0].country.encode('ascii', 'xmlcharrefreplace') if len(release.releaseEvents) and release.releaseEvents[0].country else '')+"</td>"
                print >> htf, "<td>"+("<a href=\""+release.releaseEvents[0].label.id+"\">"+release.releaseEvents[0].label.name.encode('ascii', 'xmlcharrefreplace')+"</a>" if len(release.releaseEvents) and release.releaseEvents[0].label else '')+"</td>"
                print >> htf, "<td>"+(release.releaseEvents[0].catalogNumber if len(release.releaseEvents) and release.releaseEvents[0].catalogNumber else '')+"</td>"
                print >> htf, "<td>"+(release.releaseEvents[0].barcode if len(release.releaseEvents) and release.releaseEvents[0].barcode else '')+"</td>"
                print >> htf, "<td>"+("<a href=\"" + amazonservices.getAsinProductUrl(release.asin) + "\">" + release.asin + "</a>" if release.asin else '')+"</td>"
                print >> htf, "<td>"+("<a href=\""+release.releaseEvents[0].format+"\">"+getFormatFromUri(release.releaseEvents[0].format, escape=False)+"</a>" if len(release.releaseEvents) else '')+"</td>"
                print >> htf, "<td>"+(datetime.fromtimestamp(ed.addDates[0]).strftime('%Y-%m-%d') if len(ed.addDates) else '')+"</td>"
                print >> htf, "</tr>"
            print >> htf, "</table>"

        print >> htf, "<p>%d release records</p>" % len(self.releaseIndex)

        print >> htf, """</body>
</html>"""
        htf.close()

    def getReleaseMeta(self, releaseId):
        global lastQueryTime

        if lastQueryTime > (time.time() - 1):
            print "Waiting...",
            time.sleep(1.0)
        lastQueryTime = time.time()

        q = ws.Query()
        results_meta = q._getFromWebService('release', releaseId,
                include=ws.ReleaseIncludes(
                        artist=True,
                        counts=True,
                        releaseEvents=True,
                        discs=True,
                        labels=True,
                        tracks=True,
                        tags=True,
                        #ratings=True,
                        #isrcs=True
                        ))
        return results_meta

    def writeXml(self, releaseId, metaData):
        global overWriteAll

        xmlPath = os.path.join(self.rootPath, releaseId, 'metadata.xml')
        if not os.path.isdir(os.path.dirname(xmlPath)):
            os.mkdir(os.path.dirname(xmlPath))

        if (os.path.isfile(xmlPath) and not overWriteAll):
            print xmlPath, "already exists. Continue? [y/a/N] ",
            response = sys.stdin.readline().strip()
            if (not response or response[0] not in ['y', 'a']):
                return 1
            elif (response[0] == 'a'):
                overWriteAll = True

        print "Writing metadata to", xmlPath
        xmlf = open(xmlPath, 'w')
        xml_writer = wsxml.MbXmlWriter()
        xml_writer.write(xmlf, metaData)
        xmlf.close()

        return 0

    def fixMeta(self, discId, releaseId):
        results_meta =self.getReleaseMeta(releaseId)

        self.writeXml(discId, results_meta)

    def getMetaData(self, releaseId):
        xmlPath = os.path.join(self.rootPath, releaseId, 'metadata.xml')
        if (not os.path.isfile(xmlPath)):
            print "No metadata for", releaseId
            return None
        xmlf = open(xmlPath, 'r')
        XmlParser = wsxml.MbXmlParser()
        metadata = XmlParser.parse(xmlf)
        if (len(metadata.getReleaseResults())):
            print "Old format"
            release = metadata.getReleaseResults()[0].release
        else:
            release = metadata.getRelease()
        return release



    def refreshMetaData(self, releaseId, olderThan=0):
        """Should be renamed to "add release" or something"""

        if releaseId.startswith('http'):
            releaseId = mbutils.extractUuid(releaseId, 'release')
        xmlPath = os.path.join(self.rootPath, releaseId, 'metadata.xml')
        if (os.path.isfile(xmlPath) and (os.path.getmtime(xmlPath) > (time.time() - olderThan))):
            print "Skipping", releaseId, "because it is new"
            return 0

        results_meta = self.getReleaseMeta(releaseId)
        self.writeXml(releaseId, results_meta)
        self.load()
        self.getSortedList()

    def refreshAllMetaData(self, olderThan=0):
        for releaseId in self.releaseIndex.keys():
            print "Refreshing", releaseId,
            self.refreshMetaData(releaseId, olderThan)

    def checkReleases(self):

        for releaseId in self.releaseIndex:
            if self.releaseIndex[releaseId].releaseEvents:
                if not self.releaseIndex[releaseId].releaseEvents[0].barcode:
                    print "No barcode for " + releaseId + " " + self.formatDiscSortKey(releaseId) + " (" + getFormatFromUri(self.releaseIndex[releaseId].releaseEvents[0].format) + ")"
                if not self.releaseIndex[releaseId].releaseEvents[0].format:
                    print "No format for " + releaseId + " " + self.formatDiscSortKey(releaseId)

            else:
                print "No release events for", releaseId + " " + self.formatDiscSortKey(releaseId)

    def getCoverArt(self, releaseId):
        global lastQueryTime
        release = self.releaseIndex[releaseId]
        if release.asin:
            imgPath = os.path.join(self.rootPath, releaseId, 'cover.jpg')
            if os.path.isfile(imgPath):
                print "Already have it"
            else:
                # Don't hammer the server
                if lastQueryTime > (time.time() - 0.1):
                    print "Waiting...",
                    time.sleep(0.1)
                lastQueryTime = time.time()
                response = urllib2.urlopen(
                        amazonservices.getAsinImageUrl(release.asin,
                                amazonservices.AMAZON_SERVER["amazon.com"]))
                imgf = open(imgPath, 'w')
                print "Wrote %d bytes to %s" %(os.path.getsize(imgPath), imgPath)
                imgf.write(response.read())
                imgf.close()
                response.close()
        else:
            print "No ASIN for", releaseId

    def refreshCoverArt(self):
        for releaseId in self.releaseIndex.keys():
            self.getCoverArt(releaseId)

    def checkLevenshteinDistances(self):
        import Levenshtein
        dists = []
        for leftIdx in range(len(self.releaseIndex)):
            for rightIdx in range(leftIdx, len(self.releaseIndex)):
                if  leftIdx == rightIdx :
                    continue
                leftId = self.releaseIndex.keys()[leftIdx]
                rightId = self.releaseIndex.keys()[rightIdx]
                dist = Levenshtein.distance(self.formatDiscSortKey(leftId),
                        self.formatDiscSortKey(rightId))

                dists.append((dist,leftId, rightId))

        return sorted(dists, key=lambda sortKey: sortKey[0])

    def getTopSimilarities(self, number=100):
        lds = self.checkLevenshteinDistances()
        for i in range (number):
            print str(lds[i][0]) + "\t" + self.formatDiscInfo(lds[i][1]) + " <-> " + self.formatDiscInfo(lds[i][2])
