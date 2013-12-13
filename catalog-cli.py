#!/usr/bin/python

from __future__ import print_function
from mbcat.catalog import *
from mbcat.extradata import *
from mbcat.barcode import UPC
import os
import shutil
import sys
from inputsplitter import InputSplitter

class Shell:
    def __init__(self, s=sys.stdin):
        self.c = Catalog()
        self.c.load()
        self.c.report()
        self.s = InputSplitter()

    def SearchSort(self):
        """Search for a release; useful for sorting physical media."""
        releaseId = self.Search()
        self.c.getSortNeighbors(releaseId, matchFormat=True)

    def Search(self, prompt="Enter search terms (or release ID): "):
        """Search for a release and return release ID."""
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
        """Reload database from disk"""
        del self.c 
        self.c = Catalog()
        self.s.write("Reloading database...")
        self.c.load()
        self.s.write("DONE\n")

    def EditExtra(self):
        """edit extra data"""
        # TODO remove, extra should be transparaent to the user
        releaseId = self.Search()
        ed = self.c.extraIndex[releaseId] 
        self.s.write(str(ed))
        modify = self.s.nextWord("Modify? [y/N]")
        if modify.lower().startswith('y'):
            ed.interactiveEntry()
            ed.save()

    def Refresh(self):
        """Refresh XML metadata from MusicBrainz."""
        releaseId = self.Search("Enter search terms or release ID [empty for all]: ")

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
        """Substitute one release ID for another."""
        releaseId = self.Search()
        self.s.write("Enter new release ID: ")
        newReleaseId = self.s.nextWord()
        self.c.renameRelease(releaseId, newReleaseId)

    def Html(self):
        """Write HTML file."""
        #self.c = Catalog()
        #self.c.load()
        self.c.makeHtml()

    def Add(self):
        """Add a release."""
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
        """Search for a release by barcode."""
        barCodes = UPC(self.s.nextWord("Enter barcode: ")).variations()

        for barCode in barCodes:
            for releaseId in self.c.barCodeMap[barCode]:
                self.s.write(self.c.formatDiscInfo(releaseId)+'\n')

    def Delete(self):
        """Delete a release."""
        releaseId = self.Search("Enter search terms or release ID to delete: ")
        self.c.deleteRelease(releaseId)

    def Check(self):
        """Check releases for missing information."""
        self.s.write("Running checks...\n")
        self.c.checkReleases()
        self.s.write("DONE\n")

    def Lend(self):
        """Check out a release."""
        releaseId = self.Search()
        ed = self.c.extraIndex[releaseId]
        self.s.write(str(ed))

        borrower = self.s.nextLine("Borrower (leave empty to return): ")
        if not borrower:
            borrower = '[returned]'
        date = self.s.nextLine("Lend date (leave empty for today): ")
        ed.addLend(borrower, date)
        ed.save()
        
    def DigitalPath(self):
        """Add a path to a digital copy of a release."""
        releaseId = self.Search()
        ed = self.c.extraIndex[releaseId]
        self.s.write(str(ed))

        path = self.s.nextLine("Enter path to add: ")
        if path.startswith("'") and path.endswith("'"):
            path = path[1:-1]
        ed.addPath(path)
        ed.save()

    def DigitalSearch(self):
        """Search for digital copies of releases."""
        try:
            releaseId = self.Search("Enter search terms or release ID [enter for all]: ")
        except ValueError as e:
            self.c.searchDigitalPaths()
        else:
            self.c.searchDigitalPaths(releaseId=releaseId)

    def SyncCollection(self):
        """Synchronize with a musicbrainz collection (currently only pushes releases)."""
        if not self.c.prefs.username:
            username = self.s.nextLine('Enter username: ')
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

        col_i = int(self.s.nextLine('Enter collection index: '))
        colId = result['collection-list'][col_i]['id']

        self.c.syncCollection(colId)

    def LabelTrack(self):
        """Create label track file for Audacity; useful when transferring vinyl."""
        self.c.makeLabelTrack(self.Search())

    def MetaTags(self):
        """Create metadata tags for Audacity."""
        self.c.writeMetaTags(self.Search())

    def TrackList(self):
        """Print a list of track titles and times."""
        self.c.writeTrackList(self.s, self.Search())

    def Quit(self):
        """quit (or press enter)"""
        sys.exit(0)

    shellCommands = {
        'q' : Quit,
        'extra' : EditExtra, # TODO replace this command
        'search' : SearchSort, 
        'refresh' : Refresh, 
        'html' : Html, 
        'switch' : Switch, 
        'add' : Add, 
        'reload' : Reload, 
        'barcode' : BarcodeSearch, 
        'delete' : Delete, 
        'check' : Check, 
        'lend' : Lend, 
        'digital' : {
            'path' : DigitalPath, 
            'search' : DigitalSearch, 
            #'list' : DigitalList,
            },
        'sync' : SyncCollection, 
        'labeltrack' : LabelTrack, 
        'tracklist' : TrackList, 
        'metatags' : MetaTags,
        }

    def main(self):
        def cmdSummary(cmdStruct, level=0):
            """Print a summary of commands."""
            for cmdname in sorted(cmdStruct.keys()):
                cmdfun = cmdStruct[cmdname]
                if type(cmdfun) == dict:
                    self.s.write(('\t'*level) + cmdname + " :\n")
                    cmdSummary (cmdfun, level+1)
                else:
                    self.s.write(('\t'*level) + cmdname + " : " + 
                            cmdStruct[cmdname].__doc__.strip() + "\n")
        
        def cmdParse(cmdStruct, input):
            if type(cmdStruct[input]) == dict:
                # Use the next input word and recur into the structure
                cmdParse(cmdStruct[input], self.s.nextWord().lower())
            else: 
                # Remind the user what this command does
                self.s.write(cmdStruct[input].__doc__.strip() + '\n')
                # Call the function
                try:
                    (cmdStruct[input])(self)
                except ValueError as e:
                    self.s.write(str(e) + " Command failed.\n")

        while (True):
            input = self.s.nextWord("Enter command ('h' for help): ").lower()

            if not input or input.startswith('q'):
                break

            if (input == 'h' or input == 'help'):
                cmdSummary(self.shellCommands)

            elif input in self.shellCommands.keys():
                cmdParse(self.shellCommands, input)

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

