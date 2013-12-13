"""
An interface for the MusicBrainz Cover Art Archive
https://coverartarchive.org/
http://musicbrainz.org/doc/Cover_Art_Archive/API
"""

from musicbrainzngs import compat
from musicbrainzngs import util
import musicbrainzngs.musicbrainz as mb
import json
import logging
_log = logging.getLogger("mbcat")
try:
    # For Python 3.0 and later
    from urllib.request import urlopen, HTTPError
except ImportError:
    # Fall back to Python 2's urllib2
    from urllib2 import urlopen, HTTPError

@mb._rate_limit
def getCoverArtMeta(releaseId):
    method='GET'
    url='https://coverartarchive.org/release/' + releaseId
    data=''
    req = mb._MusicbrainzHttpRequest(method, url, data)

    handlers = [compat.HTTPHandler()]
    opener = compat.build_opener(*handlers)
    _log.info('Checking for coverart ' + url)
    resp = mb._safe_read(opener, req, '')

    return json.loads(resp)

def getCoverArtUrl(meta, size='large'):
    return meta['images'][0]['thumbnails'][size]

@mb._rate_limit
def saveCoverArt(meta, imgPath):
    imgUrl = getCoverArtUrl(meta)
    response = urlopen( imgUrl )
    with open(imgPath, 'w') as imgf:
        imgf.write(response.read())
        _log.info("Wrote %d bytes to %s" %(imgf.tell(), imgPath))
    response.close()

