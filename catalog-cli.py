#!/usr/bin/python

from __future__ import print_function
from mbcat.catalog import *
from mbcat.extradata import *
import os, shutil

class InputSplitter(object):
    def __init__(self):
        self.s = sys.stdin
        self.buffer = []

    def _readline(self):
        return self.s.readline().strip()

    def nextLine(self, prompt=""):
        if prompt:
            print(prompt, end="")
        if self.buffer:
            l = ' '.join(self.buffer)
            self.buffer = []
            return l
        else:
            return self._readline()

    def nextWord(self, prompt=""):
        if prompt:
            print(prompt, end="")
        if not self.buffer:
            self.buffer = self._readline().split()

        if self.buffer:
            return self.buffer.pop(0)
        else:
            return ''

class Shell:
    def __init__(self):
        self.c = Catalog()
        self.c.load()
        self.c.report()
        self.s = InputSplitter()

    def Search(self, prompt="Enter search terms (or release ID): "):
        while(True):
            input = self.s.nextLine(prompt)
            if input:
                if len(getReleaseId(input)) == 36:
                    releaseId = getReleaseId(input)
                    self.c.getSortNeighbors(releaseId, matchFormat=True)
                    return releaseId
                matches = list(self.c._search(input))
                if len(matches) > 1:
                    print(len(matches), "matches found:")
                    for i, match in enumerate(matches):
                        print(i, self.c.formatDiscInfo(match))
                    while (True):
                        try:
                            index = int(self.s.nextWord("Select a match: "))
                            self.c.getSortNeighbors(matches[index], matchFormat=True)
                            return matches[index]
                        except ValueError as e:
                            print(e, "try again")
                        except IndexError as e:
                            print(e, "try again")

                elif len(matches) == 1:
                    self.c.getSortNeighbors(matches[0], matchFormat=True)
                    return matches[0]
                else:
                    raise ValueError ("No matches.")
            else:
                raise ValueError ('No release specified.')


    def Reload(self):
        del self.c 
        self.c = Catalog()
        print("Reloading database...")
        self.c.load()
        print("DONE")

    def EditExtra(self):
        # TODO remove, extra should be transparaent to the user
        releaseId = self.Search()
        ed = self.c.extraIndex[releaseId] 
        print(str(ed))
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
            print("Release not found")
            return
        else:
            self.c.refreshMetaData(releaseId, olderThan=maxAge)

    def Switch(self):
        releaseId = self.Search()
        print("Enter new release ID: ")
        newReleaseId = self.s.nextWord()
        self.c.renameRelease(releaseId, newReleaseId)

    def Html(self):
        #self.c = Catalog()
        #self.c.load()
        self.c.makeHtml()

    def Add(self):
        print("Enter release ID: ")
        releaseId = getReleaseId(self.s.nextWord())
        if not releaseId:
            print("No input")
            return
        if releaseId in self.c:
            print("Release '%s' already exists" % self.c.getRelease(releaseId)['title'])
            return
        try:
            self.c.refreshMetaData(releaseId)
        except mb.ResponseError as e:
            print(e, "bad release ID?")
            return

        self.c.addExtraData(releaseId)

        print("Added", self.c.getRelease(releaseId)['title'])

    def BarcodeSearch(self):
        barCode = self.s.nextWord("Enter barcode: ")
        for releaseId in self.c.barCodeMap[barCode]:
            print(self.c.formatDiscInfo(releaseId))

    def Delete(self):
        releaseId = self.Search("Enter search terms or release ID to delete: ")
        self.c.deleteRelease(releaseId)

    def Check(self):
        print("Running checks...")
        self.c.checkReleases()
        print("DONE")

    def Lend(self):
        releaseId = self.Search()
        ed = self.c.extraIndex[releaseId]
        print(str(ed))

        borrower = self.s.nextLine("Borrower (leave empty to return): ")
        if not borrower:
            borrower = '[returned]'
        date = self.s.nextLine("Lend date (leave empty for today): ")
        ed.addLend(borrower, date)
        ed.save()
        
    def Path(self):
        releaseId = self.Search()
        ed = self.c.extraIndex[releaseId]
        print(str(ed))

        path = self.s.nextLine("Enter path to add: ")
        if path.startswith("'") and path.endswith("'"):
            path = path[1:-1]
        ed.addPath(path)
        ed.save()

    def DigitalSearch(self):
        releaseId = getReleaseId(self.s.nextLine("Enter release ID [enter for all]: "))
        if not releaseId:
            self.c.searchDigitalPaths()
        elif releaseId not in self.c:
            print("Release not found")
            return
        else:
            self.c.searchDigitalPaths(releaseId=releaseId)

    digitalCommands = {
            'search' : (DigitalSearch, 'search for digital paths'),
            }

    def Digital(self):
        # TODO this needs to be updated---the commands should all be captured in a tree structure
        print("Enter sub-command:")
        for cmd, (fun, desc) in self.digitalCommands.items():
            print(cmd + ' : ' + desc)
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
            print('%d: "%s" by %s (%s)' % (i, collection['name'], 
                collection['editor'], collection['id']))

        col_i = int(raw_input('Enter collection index: '))
        colId = result['collection-list'][col_i]['id']

        self.c.syncCollection(colId)

    shellCommands = {
        'h' : (None, 'this help'),
        'q' : (None, 'quit (or press enter)'),
        'extra' : (EditExtra, 'edit extra data'), # TODO replace this command
        'search' : (Search, 'search for releases'),
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
                print("\r", end="") # TODO this is a hack
                for letter in sorted(self.shellCommands.keys()):
                    print(letter + " : " + self.shellCommands[letter][1])

            elif input in self.shellCommands.keys():
                print(self.shellCommands[input][1])
                # Call the function
                try:
                    (self.shellCommands[input][0])(self)
                except ValueError as e:
                    print(e, "Command failed.")

            else:
                print("Invalid command")


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

