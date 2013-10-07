#!/usr/bin/python

from mbcatalog.catalog import *
from mbcatalog.extradata import *
import os, shutil

class InputSplitter(object):
    def __init__(self):
        self.s = sys.stdin
        self.buffer = []

    def _readline(self):
        return self.s.readline().strip()

    def nextLine(self):
        if self.buffer:
            l = ' '.join(self.buffer)
            self.buffer = []
            return l
        else:
            return self._readline()

    def nextWord(self):
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

    def Search(self):
        while(True):
            print "Enter search terms (or release ID): ",
            input = self.s.nextLine()
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
                            index = int(self.s.nextWord())
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
        # TODO remove, extra should be transparaent to the user
        releaseId = self.Search()
        ed = self.c.extraIndex[releaseId] 
        print str(ed)
        print "Modify? [y/N]",
        modify = self.s.nextWord()
        if modify.lower().startswith('y'):
            ed.interactiveEntry()
            ed.save()

    def Refresh(self):
        print "Enter release ID [a for all]: ",
        releaseId = getReleaseId(self.s.nextLine())
        if releaseId == "a":
            self.c.refreshAllMetaData(60*60)
        elif releaseId not in self.c:
            print "Release not found"
            return
        else:
            self.c.refreshMetaData(releaseId, olderThan=60)

    def Switch(self):
        releaseId = self.Search()
        print "Enter new release ID: "
        newReleaseId = self.s.nextWord()
        self.c.renameRelease(releaseId, newReleaseId)

    def Html(self):
        #self.c = Catalog()
        #self.c.load()
        self.c.makeHtml()

    def Add(self):
        print "Enter release ID: ",
        releaseId = getReleaseId(self.s.nextWord())
        if not releaseId:
            print "No input"
            return
        if releaseId in self.c:
            print "Release '%s' already exists" % self.c.getRelease(releaseId)['title']
            return
        try:
            self.c.refreshMetaData(releaseId)
        except mb.ResponseError as e:
            print e, "bad release ID?"
            return

        self.c.addExtraData(releaseId)

        print "Added '%s'" % self.c.getRelease(releaseId)['title']

    def BarcodeSearch(self):
        print "Enter barcode: ",
        barCode = self.s.nextWord()
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
        self.c.extraIndex[releaseId]
        print str(ed)

        print "Borrower (leave empty to return): ",
        borrower = self.s.nextLine()
        if not borrower:
            borrower = '[returned]'
        print "Lend date (leave empty for today): ",
        date = self.s.nextLine()
        ed.addLend(borrower, date)
        ed.save()
        
    def Path(self):
        releaseId = self.Search()
        ed = self.c.extraIndex[releaseId]
        print str(ed)

        print "Enter path: ",
        path = self.s.nextLine()
        if path.startswith("'") and path.endswith("'"):
            path = path[1:-1]
        ed.addPath(path)
        ed.save()

    def DigitalSearch(self):
        print "Enter release ID [enter for all]: ",
        releaseId = getReleaseId(self.s.nextLine())
        if not releaseId:
            self.c.searchDigitalPaths()
        elif releaseId not in self.c:
            print "Release not found"
            return
        else:
            self.c.searchDigitalPaths(releaseId=releaseId)

    digitalCommands = {
            'search' : (DigitalSearch, 'search for digital paths'),
            }

    def Digital(self):
        print "Enter sub-command:"
        for cmd, (fun, desc) in self.digitalCommands.items():
            print cmd + ' : ' + desc
        input = self.s.nextWord()
        (self.digitalCommands[input][0])(self)


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
        }

    def main(self):
        while (True):
            print "Enter command ('h' for help): ",
            input = self.s.nextWord().lower()

            if not input or input.startswith('q'):
                break

            if (input == 'h' or input == 'help'):
                print "\r",
                for letter in sorted(self.shellCommands.keys()):
                    print letter + " : " + self.shellCommands[letter][1]

            elif input in self.shellCommands.keys():
                print self.shellCommands[input][1]
                # Call the function
                #try:
                (self.shellCommands[input][0])(self)
                #except ValueError as e:
                    #print e, "command failed"

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

