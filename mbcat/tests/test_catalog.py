"""Unit test for the mbcat catalog class"""
# Python 2/3 compatibility
from __future__ import print_function
from __future__ import unicode_literals

import unittest
import random

# set up logging
import logging
logging.basicConfig(level=logging.INFO)

import musicbrainzngs
import mbcat.catalog
from mbcat.tests.utils import *

import tempfile
import os

class CatalogTest(unittest.TestCase):
    def setUp(self):
        self.dbfile = tempfile.mktemp()
        self.catalog = mbcat.catalog.Catalog(self.dbfile)

    def tearDown(self):
        os.unlink(self.dbfile)

    def test_catalog(self):
        self.assertEqual(len(self.catalog), 0, 
                'Catalog should be empty after being created')

        for releaseId in test_releases:
            try:
                self.catalog.addRelease(releaseId)
            except musicbrainzngs.musicbrainz.ResponseError as e:
                print (releaseId+': '+str(e))

        self.assertEqual(len(self.catalog), len(test_releases),
                'Failed to add all of the test releases')

        # make a few deletions
        random.seed(42)
        victims = random.sample(test_releases, int(len(test_releases)*0.25))
        print ('Deleting %d releases' % len(victims))
        for victim in victims:
            print ('Deleting '+self.catalog.formatDiscSortKey(victim))
            self.catalog.deleteRelease(victim)

        self.assertEqual(len(self.catalog), len(test_releases)-len(victims))
        # TODO check that other structures have changed, such as the word maps

        for releaseId in victims:
            try:
                self.catalog.addRelease(releaseId)
            except musicbrainzngs.musicbrainz.ResponseError as e:
                print (releaseId+': '+str(e))

        self.assertEqual(len(self.catalog), len(test_releases),
                'Failed to add all of the test releases')

    def test_word_search(self):
        # test word search
        for query in ['pink moon',
                'jackson abc',
                'there', ]:
            result = self.catalog._search(query)
            print (result)
            assert len(result) == 1
            self.assertEqual(len(result), 1,
                'Could not find test release by word search')

    def test_shell(self):
        import mbcat.shell
        try:
            import StringIO
        except ImportError:
            import io as StringIO

        userin = StringIO.StringIO()
        shellout = StringIO.StringIO()
        shell = mbcat.shell.Shell(stdin=userin, stdout=shellout, catalog=self.catalog)

        def enterCmd(shell, cmd):
            userin.write(cmd+'\n')
            userin.seek(0) # don't forget to rewind the memory file
            shell.main()

        def printOutput(stdout):
            stdout.seek(0)
            print (stdout.read())
            stdout.seek(0)
            stdout.truncate()

        if False:
            enterCmd(shell, 'h')
            printOutput(shellout)

            enterCmd(shell, 'search collins')
            printOutput(shellout)
            #enterCmd(shell, '0')
            #printOutput(shellout)

            enterCmd(shell, 'barcode 78221869928')
            # Should return 8765eec6-c74e-420e-b1c8-4415eb284158
            printOutput(shellout)

            enterCmd(shell, 'comment collins')
            printOutput(shellout)
            enterCmd(shell, 'it is very great!')
            printOutput(shellout)

            enterCmd(shell, 'coverart collins')
            printOutput(shellout)

            enterCmd(shell, 'digital search\n')
            printOutput(shellout)

            enterCmd(shell, 'audacity metatags collins')
            printOutput(shellout)
            enterCmd(shell, 'audacity labeltrack collins')
            printOutput(shellout)

            enterCmd(shell, 'check')
            printOutput(shellout)

            enterCmd(shell, 'similar')
            printOutput(shellout)

            enterCmd(shell, 'tracklist collins')
            printOutput(shellout)

            enterCmd(shell, 'switch collins\n9c0801b6-79ab-3ba9-93c0-64f8438debc3')
            printOutput(shellout)
            enterCmd(shell, 'switch collins\nf7373a05-cbd2-3385-a67f-35d10e06ac4f')
            printOutput(shellout)

            enterCmd(shell, 'refresh fleetwood')
            enterCmd(shell, '0')
            printOutput(shellout)


def suite():
    suite = unittest.TestSuite()
    suite.addTest(CatalogTest('test_catalog'))
    #suite.addTest(...)
    return suite

