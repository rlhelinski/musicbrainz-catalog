"""
An interface for the MusicBrainz Cover Art Archive
https://coverartarchive.org/
http://musicbrainz.org/doc/Cover_Art_Archive/API
"""

from musicbrainzngs import compat
from musicbrainzngs import util
import musicbrainzngs.musicbrainz as mb
import json
import urllib2

@mb._rate_limit
def getCoverArtMeta(releaseId):
    method='GET'
    url='https://coverartarchive.org/release/' + releaseId
    data=''
    req = mb._MusicbrainzHttpRequest(method, url, data)

    handlers = [compat.HTTPHandler()]
    opener = compat.build_opener(*handlers)
    print 'Checking for coverart ' + url
    resp = mb._safe_read(opener, req, '')

    return json.loads(resp)

def getCoverArtUrl(meta, size='large'):
    return meta['images'][0]['thumbnails'][size]

@mb._rate_limit
def saveCoverArt(meta, imgPath):
    imgUrl = getCoverArtUrl(meta)
    response = urllib2.urlopen( imgUrl )
    with open(imgPath, 'w') as imgf:
        imgf.write(response.read())
        print "Wrote %d bytes to %s" %(imgf.tell(), imgPath)
    response.close()

