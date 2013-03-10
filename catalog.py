
import os, sys, time, re
import musicbrainz2.wsxml as wsxml
import musicbrainz2.utils as mbutils
import musicbrainz2.webservice as ws

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
		return h.unescape(uriStr)
	else:
		return formatStr


class Catalog(object):
	def __init__(self, rootPath='release-id'):
		self.rootPath = rootPath
		self.releaseIndex = dict()
		self.wordmap = dict()
		self.discIdMap = dict()

	def load(self):
		self.releaseIndex = dict()
		self.wordmap = dict()
		self.discIdMap = dict()
		for releaseId in os.listdir(self.rootPath):
			if releaseId.startswith('.') or len(releaseId) != 36:
				continue
			xmlPath = os.path.join(self.rootPath, releaseId, 'metadata.xml')
			if (not os.path.isfile(xmlPath)):
				print "No metadata for", releaseId
				#tocf = open(os.path.join(self.rootPath, discid, 'toc.txt'))
				#lines = tocf.readlines()
				#print lines[-2:-1]
				#print tocf.read()
				#tocf.close()
				continue
			xmlf = open(xmlPath, 'r')
			XmlParser = wsxml.MbXmlParser()
			metadata = XmlParser.parse(xmlf)
			if (len(metadata.getReleaseResults())):
				print "Old format", type(metadata)
				release = metadata.getReleaseResults()[0].release
			else:
				release = metadata.getRelease()
			self.releaseIndex[releaseId] = release
		
			if False:
				releaseDir = os.path.join('release-id',releaseId)
				if not os.path.isdir(releaseDir):
					os.mkdir(releaseDir)
				releaseXmlPath = os.path.join('release-id',releaseId,'metadata.xml')
				import shutil
				shutil.copyfile(xmlPath, releaseXmlPath)
			
			for disc in release.discs:
				if disc.id in self.discIdMap:
					self.discIdMap[disc.id].append(releaseId)
				else:
					self.discIdMap[disc.id] = [releaseId]

			# 
			# Should be a function
			words = []
			for field in [
				release.title, \
				release.artist.getName() ] + \
				[track.title for track in release.tracks] \
				:
				#words.extend(field.lower().split(' '))
				words.extend(re.findall(r"\w+", field.lower(), re.UNICODE))
			# Another function 
			word_set = set(words)
			for word in word_set:
				if word in self.wordmap:
					self.wordmap[word].append(releaseId)
				else:
					self.wordmap[word] = [releaseId]

	def _search(self, query):
		query_words = query.lower().split(' ')
		matches = []
		for word in query_words:
			if word in self.wordmap:
				if len(matches) > 0:
					matches = set(matches) & set(self.wordmap[word])
				else:
					matches = set(self.wordmap[word])
			
		return matches

	def formatDiscInfo(self, releaseId):
		release = self.releaseIndex[releaseId]
		return ' '.join( [
			releaseId, ':', \
			(release.releaseEvents[0].getDate() if len(release.releaseEvents) else ''), '-', \
			release.artist.getName(), '-', \
			release.title ] )

	def formatDiscSortKey(self, releaseId):
		release = self.releaseIndex[releaseId]
		return ' - '.join ( [
			release.artist.getSortName(), \
			release.title, \
			] ) #.encode('ascii', 'xmlcharrefreplace')
			
	def getSortedList(self):
		sortKeys = [(releaseId, self.formatDiscSortKey(releaseId)) for releaseId in self.releaseIndex.keys()]
		self.sortedList = sorted(sortKeys, key=lambda sortKey: unicode.lower(sortKey[1]))
		return self.sortedList

	def getSortNeighbors(self, releaseId, neighborHood=5):
		""">>> c.getSortNeighbors('oGahy0j6T2gXkGBLqSfaXqL.kMo-')
		"""
		if 'sortedList' not in self.__dict__:
			self.getSortedList()

		index = self.sortedList.index((releaseId, self.formatDiscSortKey(releaseId)))
		for i in range(max(0,index-neighborHood), min(len(self.sortedList), index+neighborHood)):
			# TODO make a function to get the format type from a format URI
			print ('\033[92m' if i == index else "") + "%4d" % i, \
				self.sortedList[i][0], \
				self.sortedList[i][1], \
				"[" + getFormatFromUri(self.releaseIndex[self.sortedList[i][0]].releaseEvents[0].format) + "]", \
				(" <<<" if i == index else "") + \
				('\033[0m' if i == index else "")


	def search(self, query):
		matches = self._search(query)
		for releaseId in matches:
			print self.formatDiscInfo(releaseId)

	def report(self):
		#for releaseId in self.releaseIndex.keys():
			#print self.formatDiscInfo(releaseId)
		print
		print "%d release-id records" % len(self.releaseIndex)
		print "%d words in search table" % len(self.wordmap)

	def makeHtml(self, fileName="catalog.html"):
		htf = open(fileName, 'w')

		print >> htf, """<!DOCTYPE HTML>
<html>
<head>
<title>Music Catalog</title>
</head>
<body>"""

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
<th>Format</th>
</tr>
"""
		for sortIndex, (releaseId, releaseSortStr) in enumerate(self.getSortedList()):
			release = self.releaseIndex[releaseId]
			print >> htf, "<tr>"
			print >> htf, "<!-- <td>"+("%04d" % sortIndex)+"</td> -->"
			print >> htf, "<td><a href=\""+release.artist.id+"\">"+self.releaseIndex[releaseId].artist.name.encode('ascii', 'xmlcharrefreplace')+"</a></td>"
			print >> htf, "<td><a href=\""+release.id+"\">"+release.title.encode('ascii', 'xmlcharrefreplace')+"</a></td>"
			print >> htf, "<td>"+(release.releaseEvents[0].date if len(release.releaseEvents) else '')+"</td>"
			print >> htf, "<td>"+(release.releaseEvents[0].country.encode('ascii', 'xmlcharrefreplace') if len(release.releaseEvents) and release.releaseEvents[0].country else '')+"</td>"
			print >> htf, "<td>"+("<a href=\""+release.releaseEvents[0].label.id+"\">"+release.releaseEvents[0].label.name.encode('ascii', 'xmlcharrefreplace')+"</a>" if len(release.releaseEvents) and release.releaseEvents[0].label else '')+"</td>"
			print >> htf, "<td>"+(release.releaseEvents[0].catalogNumber if len(release.releaseEvents) and release.releaseEvents[0].catalogNumber else '')+"</td>"
			print >> htf, "<td>"+(release.releaseEvents[0].barcode if len(release.releaseEvents) and release.releaseEvents[0].barcode else '')+"</td>"
			print >> htf, "<td>"+("<a href=\""+release.releaseEvents[0].format+"\">"+getFormatFromUri(release.releaseEvents[0].format, escape=False)+"</a>" if len(release.releaseEvents) else '')+"</td>"
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
		#filter = ws.ReleaseFilter()
		#results_meta = q.getReleases()
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

	def checkDiscIds(self):
		count = 0
		for discId in os.listdir('disc-id'):
			if discId.startswith('.') or len(discId) != 28: 
				continue
			if discId not in self.discIdMap:
				count += 1
				tocPath = os.path.join('disc-id', discId, 'toc.txt')
				print "No release for", discId
				tocf = open(tocPath, 'r')
				print tocf.read()
				tocf.close()
		return count


