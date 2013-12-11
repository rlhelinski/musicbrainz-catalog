#!/opt/local/bin/python2.7
"""
Read a CD in the disc drive, compute the MusicBrainz DiscID,
find a MusicBrainz release, and add that to your catalog. 
This is offered as a separate script in case libdiscid is
not available.

Usage:
    python disc-catalog.py [/path/to/cdrom]
"""

from __future__ import print_function
import sys, os
import discid
import musicbrainzngs as mb
from mbcat.catalog import *
from mbcat.extradata import *
from mbcat.utils import *
from inputsplitter import InputSplitter

mb.set_useragent(
    "python-musicbrainz-ngs-catalog",
    "0.1",
    "https://github.com/rlhelinski/musicbrainz-catalog/",
)

c = Catalog()
c.load()

io = InputSplitter()

while not io.nextLine('Press enter to read the disc or \'q\' to quit... ').startswith('q'):

    try:
        # Read the disc in the default disc drive. If necessary, you can pass
        # the 'deviceName' parameter to select a different drive.
        #
        dev = sys.argv[1] if len(sys.argv) > 1 else discid.get_default_device()
        io.write ('Reading from %s\n' % dev)
        disc = discid.read(dev)
    except discid.DiscError as e:
        print ("DiscID calculation failed: " + str(e))
        continue

    # This should be replaced with a log output 
    if (not os.path.isdir('disc-id')):
        os.mkdir('disc-id')
    if (not os.path.isdir(os.path.join('disc-id', disc.id))):
        os.mkdir(os.path.join('disc-id', disc.id))

    with open(os.path.join('disc-id', disc.id, 'toc.txt'), 'a') as tocf:
        print ('DiscID      :', disc.id, file=tocf)
        print ('First Track :', disc.first_track_num, file=tocf)
        print ('Last Track  :', disc.last_track_num, file=tocf)
        print ('Length      :', disc.sectors, 'sectors', file=tocf)

        i = disc.first_track_num
        for track in disc.tracks:
            print ("Track %-2d    : %8d %8d" % (i, track.offset, track.length), file=tocf)
            i += 1

        # TODO fix this
        print ('Submit via:', disc.submission_url, file=tocf)
        print ('Submit via:', disc.submission_url)

    print ('DiscID:', disc.id)
    
    try:
        io.write ("Querying MusicBrainz...")
        result = mb.get_releases_by_discid(disc.id,
                includes=["artists"])
        io.write ('OK\n')
    except mb.ResponseError:
        print("disc not found or bad response")
        continue
    else:
        if result.get("disc"):
            for i, rel in enumerate(result['disc']['release-list']):
                print ("\nResult : %d" % i)
                #if rel.score:
                    #print " Score   : %d" % rel.score
                print ("Release  :", rel['id'])
                print ("Artist   :", rel['artist-credit-phrase'])
                print ("Title    :", rel['title'])
                print ("Date    :", rel['date'] if 'date' in rel else '')
                print ("Country    :", rel['country'])
                if 'barcode' in rel:
                    print ("Barcode    :", rel['barcode'])
                if 'label-info-list' in rel:
                    for label_info in rel['label-info-list']:
                        for label, field in [ \
                                        ("Label:", rel['label']['name']), \
                                        ("Catalog #:", rel['catalog-number']), \
                                        ("Barcode :", releaseEvent.barcode) ]:
                            if field:
                                print (label, field, ",\t")
                            else:
                                print (label, "\t,\t")
                print ()

        elif result.get("cdstub"):
            print ('We found only a stub')
            print("artist:\t" % result["cdstub"]["artist"])
            print("title:\t" % result["cdstub"]["title"])
            raise

    if len(result['disc']['release-list']) == 0:
        print ("There were no matches!")
        print ("Enter a note to yourself: ")
        note = user_input()
        tocf = open(os.path.join('disc-id', disc.id, 'toc.txt'), 'a')
        tocf.write(note)
        tocf.close()
        sys.exit(1)
    elif len(result['disc']['release-list']) == 1:
        print ("There was one match.")
        choice = 0
    else:
        print ("There were %d matches." % len(result['disc']['release-list']))
        print ("Choose one making you better feeling: ")
        choice = io.nextLine()
        if not choice.isdigit():
            continue
        choice = int(choice)
        if choice < 0 or choice >= len(result['disc']['release-list']):
            print ("You failed!")
            continue


    print ("Adding '%s' to the catalog..." % result['disc']['release-list'][choice]['title'])

    releaseId = extractUuid(result['disc']['release-list'][choice]['id'])

    if not releaseId:
        print ("It looks like MusicBrainz only has a CD stub for this TOC.")
        sys.exit(1)

    c.refreshMetaData(releaseId)

    ed = ExtraData(releaseId)
    try:
        ed.load()
    except IOError as e:
        pass
    ed.addDate()
    ed.save()

# EOF
