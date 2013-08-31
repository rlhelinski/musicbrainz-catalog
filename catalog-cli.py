#!/usr/bin/python

from mbcatalog.catalog import *
from mbcatalog.extradata import *
import os, shutil

class Shell:
    def __init__(self):
        self.c = Catalog()
        self.c.load()
        self.c.report()

    @staticmethod
    def getInput():
        return sys.stdin.readline().strip()

    def Search(self):
        while(True):
            print "Enter search terms (or release ID): ",
            input = getInput()
            if input:
                if len(getReleaseId(input)) == 36:
                    releaseId = getReleaseId(input)
                    self.c.getSortNeighbors(releaseId, matchFormat=True)
                    return releaseId
                matches = list(self.c._search(input))
                if len(matches) > 1:
                    print len(matches), "matches found:"
                    for i, match in enumerate(matches):
                        print i, self.c.formatDiscInfo(match)
                    while (True):
                        try:
                            print "Select a match: ",
                            index = int(getInput())
                            self.c.getSortNeighbors(matches[index], matchFormat=True)
                            return matches[index]
                        except ValueError as e:
                            print e, "try again"
                        except IndexError as e:
                            print e, "try again"

                elif len(matches) == 1:
                    self.c.getSortNeighbors(matches[0], matchFormat=True)
                    return matches[0]
                else:
                    raise ValueError ("No matches")
            else:
                raise ValueError ('No release specified')


    def Reload(self):
        del self.c 
        self.c = Catalog()
        print "Reloading database...",
        self.c.load()
        print "DONE"

    def EditExtra(self):
        releaseId = self.Search()
        ed = ExtraData(releaseId)
        try:
            ed.load()
            print str(ed)
            print "Modify? [y/N]",
        except IOError as e:
            print "Add? [y/N]",
        modify = getInput()
        if modify.lower().startswith('y'):
            ed.interactiveEntry()
            ed.save()

    def Refresh(self):
        print "Enter release ID [a for all]: ",
        releaseId = getReleaseId(getInput())
        if releaseId == "a":
            self.c.refreshAllMetaData(60*60)
        elif releaseId not in self.c:
            print "Release not found"
            return
        else:
            self.c.refreshMetaData(releaseId, olderThan=60)

    def Change(self):
        releaseId = self.Search()
        print "Enter new release ID: ",
        newReleaseId = getInput()
        self.c.renameRelease(releaseId, newReleaseId)

    def Html(self):
        self.c = Catalog()
        self.c.load()
        self.c.makeHtml()

    def Add(self):
        print "Enter release ID: ",
        releaseId = getReleaseId(getInput())
        if not releaseId:
            print "No input"
            return
        if releaseId in self.c:
            print "Release already exists"
            return
        try:
            self.c.refreshMetaData(releaseId)
        except ws.ResourceNotFoundError as e:
            print "Release not found"
            return
        except ws.RequestError as e:
            print e
            return

        ed = ExtraData(releaseId)
        try:
            ed.load()
        except IOError as e:
            "Doesn't matter"
        ed.addDate()
        ed.save()

    def BarcodeSearch(self):
        print "Enter barcode: ",
        barCode = getInput()
        for releaseId in self.c.barCodeMap[barCode]:
            print self.c.formatDiscInfo(releaseId)

    def Delete(self):
        print "Enter release ID to delete: ",
        releaseId = self.Search()
        self.c.deleteRelease(releaseId)

    def Check(self):
        print "Running checks..."
        self.c.checkReleases()
        print "DONE"

    def Lend(self):
        releaseId = self.Search()
        ed = ExtraData(releaseId)
        try:
            ed.load()
            print str(ed)
        except IOError as e:
            pass

        print "Borrower (leave empty to return): ",
        borrower = getInput()
        if not borrower:
            borrower = '[returned]'
        print "Lend date (leave empty for today): ",
        date = getInput()
        ed.addLend(borrower, date)
        ed.save()
        
    def Path(self):
        releaseId = self.Search()
        ed = ExtraData(releaseId)
        try:
            ed.load()
            print str(ed)
        except IOError as e:
            pass

        print "Enter path: ",
        path = getInput()
        if path.startswith("'") and path.endswith("'"):
            path = path[1:-1]
        ed.addPath(path)
        ed.save()


    shellCommands = {
        'h' : (None, 'this help'),
        'q' : (None, 'quit'),
        'extra' : (EditExtra, 'edit extra data'), # TODO replace this command
        'search' : (Search, 'search for releases'),
        'refresh' : (Refresh, 'refresh XML metadata from musicbrainz'),
        'html' : (Html, 'write HTML'),
        'change' : (Change, 'change release ID'),
        'add' : (Add, 'add release'),
        'reload' : (Reload, 'reload database from disk'),
        'barcode' : (BarcodeSearch, 'barcode search'),
        'delete' : (Delete, 'delete release'),
        'check' : (Check, 'check releases'),
        'lend' : (Lend, 'lend (checkout) release'),
        'path' : (Path, 'add Path to release'),
        }

    def main(self):
        while (True):
            print "Enter command ('h' for help): ",
            input = getInput().lower()

            if not input or input.startswith('q'):
                break

            if (input == 'h' or input == 'help'):
                print "\r",
                for letter in sorted(self.shellCommands.keys()):
                    print letter + " : " + self.shellCommands[letter][1]

            elif input in self.shellCommands.keys():
                print self.shellCommands[input][1]
                # Call the function
                try:
                    (self.shellCommands[input][0])(self)
                except ValueError as e:
                    print e

            else:
                print "Invalid command"


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

