"""
Amazon file name convention:
<ASIN>.<ServerNumber>.[SML]ZZZZZZZ.jpg

Example:
http://www.amazon.com/gp/product/B000002M3I?tag=musicbrainz0d-20
http://ec1.images-amazon.com/images/P/B000002M3I.01.LZZZZZZZ.jpg

"""
from __future__ import print_function
import re
from musicbrainzngs.musicbrainz import _rate_limit
try:
    # For Python 3.0 and later
    from urllib.request import urlopen, HTTPError
except ImportError:
    # Fall back to Python 2's urllib2
    from urllib2 import urlopen, HTTPError

# data transliterated from the perl stuff used to find cover art for the
# musicbrainz server.
# See mb_server/cgi-bin/MusicBrainz/Server/CoverArt.pm
# hartzell --- Tue Apr 15 15:25:58 PDT 2008
COVERART_SITES = (
    # CD-Baby
    # tested with http://musicbrainz.org/release/1243cc17-b9f7-48bd-a536-b10d2013c938.html
    {
    'regexp': 'http://(www\.)?cdbaby.com/cd/(\w)(\w)(\w*)',
    'imguri': 'http://cdbaby.name/$2/$3/$2$3$4.jpg',
    },
    # Jamendo
    # tested with http://musicbrainz.org/release/2fe63977-bda9-45da-8184-25a4e7af8da7.html
    {
    'regexp': 'http:\/\/(?:www.)?jamendo.com\/(?:[a-z]+\/)?album\/([0-9]+)',
    'imguri': 'http://www.jamendo.com/get/album/id/album/artworkurl/redirect/$1/?artwork_size=0',
    },
    )

# amazon image file names are unique on all servers and constructed like
# <ASIN>.<ServerNumber>.[SML]ZZZZZZZ.jpg
# A release sold on amazon.de has always <ServerNumber> = 03, for example.
# Releases not sold on amazon.com, don't have a "01"-version of the image,
# so we need to make sure we grab an existing image.
AMAZON_SERVER = {
    "amazon.jp": {
                "server": "ec1.images-amazon.com",
                "id"    : "09",
        },
    "amazon.co.jp": {
                "server": "ec1.images-amazon.com",
                "id"    : "09",
        },
    "amazon.co.uk": {
                "server": "ec1.images-amazon.com",
                "id"    : "02",
        },
    "amazon.de": {
                "server": "ec2.images-amazon.com",
                "id"    : "03",
        },
    "amazon.com": {
                "server": "ec1.images-amazon.com",
                "id"    : "01",
        },
    "amazon.ca": {
                "server": "ec1.images-amazon.com",
                "id"    : "01",                   # .com and .ca are identical
        },
    "amazon.fr": {
                "server": "ec1.images-amazon.com",
                "id"    : "08"
        },
}

AMAZON_IMAGE_PATH = '/images/P/%s.%s.%sZZZZZZZ.jpg'
AMAZON_ASIN_URL_REGEX = re.compile(r'^http://(?:www.)?(.*?)(?:\:[0-9]+)?/.*/([0-9B][0-9A-Z]{9})(?:[^0-9A-Z]|$)')

# This should be parameterized for other locales
AMAZON_PRODUCT_URL = 'http://www.amazon.com/gp/product/%s?tag=musicbrainz0d-20'

def getAsinFromUrl(text):
    match = AMAZON_ASIN_URL_REGEX.match(text)
    if match != None:
        asinHost = match.group(1)
    asin = match.group(2);
    if AMAZON_SERVER.has_key(asinHost):
        serverInfo = AMAZON_SERVER[asinHost]
    else:
        serverInfo = AMAZON_SERVER['amazon.com']

def getAsinImageUrl(asin, serverInfo, size='L'):
    return "http://" + serverInfo['server'] + AMAZON_IMAGE_PATH % (asin, serverInfo['id'], size)

def getAsinProductUrl(asin):
    return AMAZON_PRODUCT_URL % (asin)

@_rate_limit
def saveImage(releaseAsin, server, imgPath):
    imgUrl = getAsinImageUrl(releaseAsin, server)
    print(imgUrl)
    try:
        response = urlopen( imgUrl )
    except HTTPError as e:
        print(e)
        return

    with open(imgPath, 'w') as imgf:
        imgf.write(response.read())
        print("Wrote %d bytes to %s" %(imgf.tell(), imgPath))

    response.close()

