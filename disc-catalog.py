#!/opt/local/bin/python2.7
# 
# Read a CD in the disc drive and calculate a MusicBrainz DiscID.
#
# Usage:
#	python discid.py
#
# $Id$
#
import sys, os
from musicbrainz2.disc import readDisc, getSubmissionUrl, DiscError
import musicbrainz2.webservice as ws
import musicbrainz2.wsxml as wsxml
import musicbrainz2.utils as mbutils

try:
	# Read the disc in the default disc drive. If necessary, you can pass
	# the 'deviceName' parameter to select a different drive.
	#
	if len(sys.argv) > 1:
		disc = readDisc(deviceName=sys.argv[1])
	else:
		disc = readDisc()
except DiscError, e:
	print "DiscID calculation failed:", str(e)
	sys.exit(1)

if (not os.path.isdir('disc-id')):
	os.mkdir('disc-id')
if (not os.path.isdir(os.path.join('disc-id', disc.id))):
	os.mkdir(os.path.join('disc-id', disc.id))

tocf = open(os.path.join('disc-id', disc.id, 'toc.txt'), 'a')
print >> tocf, 'DiscID      :', disc.id
print 'DiscID      :', disc.id
print >> tocf, 'First Track :', disc.firstTrackNum
print >> tocf, 'Last Track  :', disc.lastTrackNum
print >> tocf, 'Length      :', disc.sectors, 'sectors'

i = disc.firstTrackNum
for (offset, length) in disc.tracks:
	print >> tocf, "Track %-2d    : %8d %8d" % (i, offset, length)
	i += 1

print >> tocf, 'Submit via  :', getSubmissionUrl(disc)
print 'Submit via  :', getSubmissionUrl(disc)

#tocf.write(getSubmissionUrl(disc))
tocf.close()

def getXML(query, filter, entity=None, include=None): 
	if filter is None:
	    filterParams = [ ]
	else:
	    filterParams = filter.createParameters()
	
	if include is None:
	    includeParams = [ ]
	else:
	    includeParams = include.createIncludeTags()
	
	stream = query._ws.get('release', '', includeParams, filterParams)
	return stream

#xml = getXML(q, filter)
#for line in xml:
#	print line

#xmlf.write(xml.read())

print "Querying MusicBrainz..."
#print "For more info: http://musicbrainz.org/cdtoc/"+disc.id
q = ws.Query()
filter = ws.ReleaseFilter(discId=disc.id)
#results = q.getReleases(filter=filter)
results_meta = q._getFromWebService('release', '', filter=filter,
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
results = results_meta.getReleaseResults()

for i, result in enumerate(results):
	print "\nResult	: %d" % i,
	if result.score:
		print "	Score	: %d" % result.score
	print "Release	:", result.release._id
	print "Artist	:", result.release.artist.getName()
	print "Title	:", result.release.title
	for releaseEvent in result.release.releaseEvents:
		for label, field in [("Released	:", releaseEvent.date), \
				("Country	:", releaseEvent.country), \
				("Label	:", (releaseEvent.label.name if releaseEvent.label else None)), \
				("Catalog #:", releaseEvent.catalogNumber), \
				("Barcode :", releaseEvent.barcode) ]:
			if field:
				print label, field, ",\t",
			else:
				print label, "\t,\t", 
	print 
	if len(result.release.releaseEvents):
		print "Date	:", result.release.releaseEvents[0].getDate()

if len(results) == 0:
	print "There were no matches!"
	print "Enter a note to yourself: " 
	note = sys.stdin.readline()
	tocf = open(os.path.join('disc-id', disc.id, 'toc.txt'), 'a')
	tocf.write(note)
	tocf.close()
	sys.exit(1)
elif len(results) == 1:
	print "There was one match."
	choice = 0
else:
	print "There were %d matches." % len(results),
	print "Choose one making you better feeling: "
	choice = int(sys.stdin.readline().strip())
	#print "You chose: %d" % choice
	if choice < 0 or choice >= len(results):
		print "You failed"
		sys.exit(1)


print "Querying MusicBrainz for that release metadata..."

#uuid = mbutils.extractUuid(results[choice].release.getId(), 'release')
#results_meta = q._getFromWebService('release', uuid)
#results_meta = q._getFromWebService('release', '', filter=filter)
#results_meta = q.getReleaseById(results[choice].release.getId())
# This query seemed to only give me the release title!
# Instead, replace the list of results with the release chosen
#results_meta._releaseResults = [ results_meta.releaseResults[choice] ] 

releaseId = mbutils.extractUuid(results_meta.releaseResults[choice].release._id)
#print "Fetching metadata for", releaseId

if not releaseId:
	print "It looks like MusicBrainz only has a CD stub for this TOC."
	sys.exit(1)

from catalog import *

c = Catalog()
c.writeXml(releaseId, c.getReleaseMeta(releaseId))


#xmlPath = os.path.join('release-id', disc.id, 'metadata.xml')
#if (os.path.isfile(xmlPath)):
	#print xmlPath, "exists. Overwrite? [y/N]"
	#response = sys.stdin.readline().strip()
	#if (response != 'y'):
		#sys.exit(1)
#
#print "Writing metadata to", xmlPath
#xmlf = open(xmlPath, 'w')
#xml_writer = wsxml.MbXmlWriter()
#xml_writer.write(xmlf, results_meta)
#
#xmlf.close()

# EOF
