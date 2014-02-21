# Python 2/3 compatibility
from __future__ import print_function
from __future__ import unicode_literals

import random

import logging
# set up logging
logging.basicConfig(level=logging.INFO)

import mbcat.catalog

test_releases = [
    'ca519b2d-5fd3-4d7b-a537-2d39da5d5018',
    '3355c565-c28f-45b7-bae3-96435978509f',
    'e0778052-5b59-39f2-a0b0-48515b64a94d',
    '6d9db0cb-c7e5-31d0-ac93-0db4d4b6d829',
    '662058eb-1edf-376f-bc84-638048cc9d1f',
    'a192f44f-e51c-4ab4-a229-8810f581cc47',
    '25a313f9-041a-4e46-9020-3240203abaf7',
    '449bb11b-a9d7-4b02-90eb-b44183806117',
    '21519f98-d1a5-4108-b565-3a2d9b9f776a',
    '33bd2678-ad42-4cb9-9e9b-b7ea8934fa1d',
    # best-selling albums
    '196971df-a7b6-3cdb-8e59-f43967cd29bf',
    'b84ee12a-09ef-421b-82de-0441a926375b',
    'd0cce31b-58be-3e6d-aa06-798ef0345ab3',
    'f7c680af-5b09-3fea-be84-5e00a7da56a0',
    '317df471-8569-4a09-968d-1c1f2810ff32',
    '081ea37e-db59-4332-8cd2-ad020cb93af6',
    '8765eec6-c74e-420e-b1c8-4415eb284158',
    # 7"
    '3f423bcc-f834-41fd-b35e-c9ed9036b2d7',
    # Unknown format
    #'be3cc3e7-bdb0-3c13-a60b-a985b30eb603', # this disappeared as of 2014/02/06
    # Digital
    '14a12f84-c5f3-473b-87f5-9340174ecbc4',
    ]

# test the catalog class
c = mbcat.catalog.Catalog('testcat.db')

c.report()
assert len(c) == 0

for releaseId in test_releases:
    c.addRelease(releaseId)

c.report()

# test word search
for query in ['pink moon',
        'jackson abc',
        'there', ]:
    result = c._search(query)
    print (result)
    assert len(result) == 1

assert len(c.getReleaseIds()) == len(c)

# make a few deletions
random.seed(42)
victims = random.sample(test_releases, int(len(test_releases)*0.25))
print ('Deleting %d releases' % len(victims))
for victim in victims:
    print ('Deleting '+c.formatDiscSortKey(victim))
    c.deleteRelease(victim)

c.report()

import mbcat.shell
import StringIO

userin = StringIO.StringIO()
shellout = StringIO.StringIO()
shell = mbcat.shell.Shell(stdin=userin, stdout=shellout, catalog=c)

def enterCmd(shell, cmd):
    userin.write(cmd+'\n')
    userin.seek(0) # don't forget to rewind the memory file
    shell.main()

def printOutput(stdout):
    stdout.seek(0)
    print (stdout.read())

enterCmd(shell, 'h')
printOutput(shellout)

