"""This is only a test"""

import musicbrainzngs.mbxml as mbxml
import musicbrainzngs.util as mbutil
import musicbrainzngs.musicbrainz as mb

# Have to give an identity for musicbrainzngs
mb.set_useragent(
    "python-musicbrainz-ngs-example",
    "0.1",
    "https://github.com/alastair/python-musicbrainz-ngs/",
)

# Test getting XML from webservice
#releaseId = '67b0b44d-fae2-45bf-9dce-d7ac88fa68c3'
#releaseId = 'f50a3fce-abf3-4903-a470-69d90de1ca55'
#releaseId = '932d0cc0-c005-41de-b579-5afd5cd49021'
releaseId = 'd4f67978-6a2b-45ba-a8ca-e949c127fcd0'
#xmlPath = 'release-id/%s/metadata.xml' % releaseId
xmlPath = 'test-ngs.xml'

metadata_xml = mb.get_release_by_id(releaseId, includes=['discids', 'media', 'labels', 'recordings'], raw=True)
with open(xmlPath, 'w') as xmlf:
    resp = xmlf.write(metadata_xml)

metadata_dict = mbxml.parse_message(metadata_xml)
rel = metadata_dict['release']

print releaseId, rel['title'] + (' ('+rel['disambiguation']+')' if 'disambiguation' in rel and rel['disambiguation'] else '')
print 'Barcode: ' + (rel['barcode'] if rel['barcode'] else '[none]'), 
for info in rel['label-info-list']:
    print 'cat. no.: ' + info.get('catalog-number')
print "tracklist:"
for medium in rel['medium-list']:
    for disc in medium['disc-list']:
        print 'discid: ' + disc['id']
    for recording in medium['track-list']:
        print recording['position'], recording['recording']['title']


# Test loading from file 
with open(xmlPath, 'r') as xmlf:
    resp = xmlf.read()

metadata_file = mbxml.parse_message(resp)
if metadata_dict != metadata_file:
    print "Data read back from disk does not match"
else:
    print "We were successful"

