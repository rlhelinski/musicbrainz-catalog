#!/usr/bin/python

from __future__ import print_function
from mbcat.catalog import *
from mbcat.extradata import *
from mbcat.barcode import UPC
import os
import shutil
import sys

class InputSplitter(object):
    def __init__(self, stdin=sys.stdin, stdout=sys.stdout):
        self.stdin = stdin
        self.stdout = stdout
        self.buffer = []

    def write(self, string):
        self.stdout.write(string)
        self.stdout.flush()

    def _readline(self):
        return self.stdin.readline().strip()

    def nextLine(self, prompt=""):
        if prompt:
            self.write(prompt)
        if self.buffer:
            l = ' '.join(self.buffer)
            self.buffer = []
            return l
        else:
            return self._readline()

    def nextWord(self, prompt=""):
        if prompt:
            self.write(prompt)
        if not self.buffer:
            self.buffer = self._readline().split()

        if self.buffer:
            return self.buffer.pop(0)
        else:
            return ''

class Shell:
    def __init__(self, s=sys.stdin):
        self.c = Catalog()
        self.c.load()
        self.c.report()
        self.s = InputSplitter()

    def SearchSort(self):
        releaseId = self.Search()
        self.c.getSortNeighbors(releaseId, matchFormat=True)

    def Search(self, prompt="Enter search terms (or release ID): "):
        while(True):
            input = self.s.nextLine(prompt)
            if input:
                if len(getReleaseId(input)) == 36:
                    releaseId = getReleaseId(input)
                    return releaseId
                matches = list(self.c._search(input))
                if len(matches) > 1:
                    self.s.write("%d matches found:\n" % len(matches))
                    for i, match in enumerate(matches):
                        self.s.write(str(i) + " " + self.c.formatDiscInfo(match) + "\n")
                    while (True):
                        try:
                            index = int(self.s.nextWord("Select a match: "))
                            return matches[index]
                        except ValueError as e:
                            self.s.write(str(e) + " try again\n")
                        except IndexError as e:
                            self.s.write(str(e) + " try again\n")

                elif len(matches) == 1:
                    return matches[0]
                else:
                    raise ValueError ("No matches.")
            else:
                raise ValueError ('No release specified.')


    def Reload(self):
        del self.c 
        self.c = Catalog()
        self.s.write("Reloading database...")
        self.c.load()
        self.s.write("DONE\n")

    def EditExtra(self):
        # TODO remove, extra should be transparaent to the user
        releaseId = self.Search()
        ed = self.c.extraIndex[releaseId] 
        self.s.write(str(ed))
        modify = self.s.nextWord("Modify? [y/N]")
        if modify.lower().startswith('y'):
            ed.interactiveEntry()
            ed.save()

    def Refresh(self):
        releaseId = getReleaseId(self.s.nextLine("Enter release ID [empty for all]: "))

        maxAge = self.s.nextLine("Enter maximum cache age in minutes [leave empty for one minute]: ")
        maxAge = int(maxAge)*60 if maxAge else 60

        if not releaseId:
            self.c.refreshAllMetaData(maxAge)
        elif releaseId not in self.c:
            self.s.write("Release not found\n")
            return
        else:
            self.c.refreshMetaData(releaseId, olderThan=maxAge)

    def Switch(self):
        releaseId = self.Search()
        self.s.write("Enter new release ID: ")
        newReleaseId = self.s.nextWord()
        self.c.renameRelease(releaseId, newReleaseId)

    def Html(self):
        #self.c = Catalog()
        #self.c.load()
        self.c.makeHtml()

    def Add(self):
        self.s.write("Enter release ID: ")
        releaseId = getReleaseId(self.s.nextWord())
        if not releaseId:
            self.s.write("No input")
            return
        if releaseId in self.c:
            self.s.write("Release '%s' already exists.\n" % self.c.getRelease(releaseId)['title'])
            return
        try:
            self.c.refreshMetaData(releaseId)
        except mb.ResponseError as e:
            self.s.write(str(e) + " bad release ID?\n")
            return

        self.c.addExtraData(releaseId)

        self.s.write("Added '%s'.\n" % self.c.getRelease(releaseId)['title'])

    def BarcodeSearch(self):
        barCodes = UPC(self.s.nextWord("Enter barcode: ")).variations()

        for barCode in barCodes:
            for releaseId in self.c.barCodeMap[barCode]:
                self.s.write(self.c.formatDiscInfo(releaseId)+'\n')

    def Delete(self):
        releaseId = self.Search("Enter search terms or release ID to delete: ")
        self.c.deleteRelease(releaseId)

    def Check(self):
        self.s.write("Running checks...")
        self.c.checkReleases()
        self.s.write("DONE\n")

    def Lend(self):
        releaseId = self.Search()
        ed = self.c.extraIndex[releaseId]
        self.s.write(str(ed))

        borrower = self.s.nextLine("Borrower (leave empty to return): ")
        if not borrower:
            borrower = '[returned]'
        date = self.s.nextLine("Lend date (leave empty for today): ")
        ed.addLend(borrower, date)
        ed.save()
        
    def Path(self):
        releaseId = self.Search()
        ed = self.c.extraIndex[releaseId]
        self.s.write(str(ed))

        path = self.s.nextLine("Enter path to add: ")
        if path.startswith("'") and path.endswith("'"):
            path = path[1:-1]
        ed.addPath(path)
        ed.save()

    def DigitalSearch(self):
        # TODO this should search
        try:
            releaseId = self.Search("Enter search terms or release ID [enter for all]: ")
        except ValueError as e:
            self.c.searchDigitalPaths()
        else:
            self.c.searchDigitalPaths(releaseId=releaseId)

    digitalCommands = {
            'search' : (DigitalSearch, 'search for digital paths'),
            }

    def Digital(self):
        # TODO this needs to be updated---the commands should all be captured in a tree structure
        self.s.write("Enter sub-command:")
        for cmd, (fun, desc) in self.digitalCommands.items():
            self.s.write(cmd + ' : ' + desc + '\n')
        input = self.s.nextWord()
        (self.digitalCommands[input][0])(self)

    def SyncCollection(self):
        if not self.c.prefs.username:
            username = raw_input('Enter username: ')
            self.c.prefs.username = username
            self.c.prefs.save()
        else:
            username = self.c.prefs.username

        # Input the password.
        import getpass
        password = getpass.getpass("Password for '%s': " % username)

        # Call musicbrainzngs.auth() before making any API calls that
        # require authentication.
        mb.auth(username, password)

        result = mb.get_collections()
        for i, collection in enumerate(result['collection-list']):
            self.s.write('%d: "%s" by %s (%s)\n' % (i, collection['name'], 
                collection['editor'], collection['id']))

        col_i = int(raw_input('Enter collection index: '))
        colId = result['collection-list'][col_i]['id']

        self.c.syncCollection(colId)

    shellCommands = {
        'h' : (None, 'this help'),
        'q' : (None, 'quit (or press enter)'),
        'extra' : (EditExtra, 'edit extra data'), # TODO replace this command
        'search' : (SearchSort, 'search for releases; useful for sorting'),
        'refresh' : (Refresh, 'refresh XML metadata from musicbrainz'),
        'html' : (Html, 'write HTML'),
        'switch' : (Switch, 'substitute one release ID for another'),
        'add' : (Add, 'add release'),
        'reload' : (Reload, 'reload database from disk'),
        'barcode' : (BarcodeSearch, 'barcode search'),
        'delete' : (Delete, 'delete release'),
        'check' : (Check, 'check releases'),
        'lend' : (Lend, 'lend (checkout) release'),
        'path' : (Path, 'add path to digital copy of release'),
        'digital' : (Digital, 'manage links to digital copies'),
        'sync' : (SyncCollection, 'sync with a musicbrainz collection'),
        }

    def main(self):
        while (True):
            input = self.s.nextWord("Enter command ('h' for help): ").lower()

            if not input or input.startswith('q'):
                break

            if (input == 'h' or input == 'help'):
                for letter in sorted(self.shellCommands.keys()):
                    self.s.write(letter + " : " + self.shellCommands[letter][1] + "\n")

            elif input in self.shellCommands.keys():
                self.s.write(self.shellCommands[input][1] + '\n')
                # Call the function
                try:
                    (self.shellCommands[input][0])(self)
                except ValueError as e:
                    self.s.write(str(e) + " Command failed.\n")

            else:
                self.s.write("Invalid command\n")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        search_terms = sys.argv
        del search_terms[0]
        c = Catalog()
        c.load()
        c.search(' '.join(search_terms))

    else:
        s = Shell()
        s.main()

