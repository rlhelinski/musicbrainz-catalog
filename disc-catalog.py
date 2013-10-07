#!/opt/local/bin/python2.7
#
# Read a CD in the disc drive and calculate a MusicBrainz DiscID.
#
# Usage:
#       python discid.py
#
# $Id$
#
import sys, os
from musicbrainz2.disc import readDisc, getSubmissionUrl, DiscError
import musicbrainz2.webservice as ws
import musicbrainz2.wsxml as wsxml
import musicbrainz2.utils as mbutils
from mbcatalog.catalog import *
from mbcatalog.extradata import *

c = Catalog()
c.load()

input = ''
while not input.startswith('q'):
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

    tocf.close()

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
        print "\nResult : %d" % i,
        if result.score:
            print " Score   : %d" % result.score
        print "Release  :", result.release._id
        print "Artist   :", result.release.artist.getName()
        print "Title    :", result.release.title
        for releaseEvent in result.release.releaseEvents:
            for label, field in [("Released :", releaseEvent.date), \
                            ("Country       :", releaseEvent.country), \
                            ("Label :", (releaseEvent.label.name if releaseEvent.label else None)), \
                            ("Catalog #:", releaseEvent.catalogNumber), \
                            ("Barcode :", releaseEvent.barcode) ]:
                if field:
                    print label, field, ",\t",
                else:
                    print label, "\t,\t",
        print
        if len(result.release.releaseEvents):
            print "Date     :", result.release.releaseEvents[0].getDate()

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
        if choice < 0 or choice >= len(results):
            print "You failed"
            sys.exit(1)


    print "Querying MusicBrainz for that release metadata..."

    releaseId = mbutils.extractUuid(results_meta.releaseResults[choice].release._id)

    if not releaseId:
        print "It looks like MusicBrainz only has a CD stub for this TOC."
        sys.exit(1)

    c.refreshMetaData(releaseId)

    ed = ExtraData(releaseId)
    try:
        ed.load()
    except IOError as e:
        "Doesn't matter"
    ed.addDate()
    ed.save()

    input = raw_input('Press enter to read another disc or \'q\' to quit...')

# EOF
