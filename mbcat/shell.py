from __future__ import print_function
from mbcat.catalog import *
from mbcat.extradata import *
from mbcat.barcode import UPC
import os
import sys
from mbcat.inputsplitter import InputSplitter

class Shell:
    def __init__(self, stdin=sys.stdin, stdout=sys.stdout, catalog=None):
        self.c = catalog if catalog else Catalog()
        self.c.report()
        self.s = InputSplitter(stdin=stdin, stdout=stdout)

    def SearchSort(self):
        """Search for a release and display its neighbors in the sorting scheme.
        Useful for sorting physical media."""
        releaseId = self.Search()
        (index, neighborhood) = self.c.getSortNeighbors(releaseId, matchFormat=True)

        for i, (sortId, sortStr) in neighborhood:
            self.s.write( ' '.join([
                    ('\033[92m' if i == index else "") + "%4d" % i, \
                    sortId, \
                    sortStr, \
                    ("[" + str(mbcat.formats.getReleaseFormat(self.c.getRelease(sortId))) + "]"), \
                    (" <<<" if i == index else "") + ('\033[0m' if i == index else "") \
                    ])+'\n' )

    def Search(self, prompt="Enter search terms (or release ID): "):
        """Search for a release and return release ID."""
        while(True):
            input = self.s.nextLine(prompt)
            if input:
                if len(mbcat.utils.getReleaseIdFromInput(input)) == 36:
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
                    raise ValueError ("No matches for \"%s\"." % input)
            else:
                raise ValueError ('No release specified.')


    def Reload(self):
        """Reload the database from disk."""
        del self.c 
        self.c = Catalog()
        self.s.write("Reloading database...")
        self.c.load()
        self.s.write("DONE\n")

    def AddPurchaseEvent(self):
        """Add a purchase date."""
        releaseId = self.Search()
        ed = self.c.extraIndex[releaseId] 
        for purchase in ed.purchases:
            self.s.write(str(purchase)+'\n')
        dateStr = self.s.nextLine('Purchase date ('+dateFmtUsr+'): ')
        if not dateStr:
            raise ValueError('Empty string.')
        vendorStr = self.s.nextLine('Vendor: ')
        if not vendorStr:
            raise ValueError('Empty string.')
        priceStr = self.s.nextLine('Price: ')
        if not vendorStr:
            raise ValueError('Empty string.')

        pe = PurchaseEvent(dateStr, priceStr, vendorStr)
        ed.addPurchase(pe)
        ed.save()

    # TODO also need a delete comment function
    def AddComment(self):
        """Add a comment."""
        releaseId = self.Search()
        ed = self.c.extraIndex[releaseId]
        if ed.comment:
            self.s.write('Comments: ' + ed.comment + '\n')
        cmt = self.s.nextLine('Additional Comment: ')
        if not cmt:
            raise ValueError('Empty string.')

        if ed.comment:
            ed.comment += '\n'+cmt
        else:
            ed.comment = cmt
        ed.save()


    def SetRating(self):
        """Add a rating."""
        releaseId = self.Search()
        ed = self.c.extraIndex[releaseId]
        if ed.rating:
            self.s.write ('Current rating: %d/5\n' % ed.rating)
        nr = self.s.nextLine('New rating: ')
        if not nr:
            raise ValueError('Empty string.')
        ed.setRating(nr)
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

    def CoverArt(self):
        """Refresh coverart from coverart.org or Amazon.com."""
        releaseId = self.Search("Enter search terms or release ID [empty for all]: ")
        if not releaseId:
            self.c.refreshAllCoverArt()
        else:
            self.c.getCoverArt(releaseId)

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
            self.c.addRelease(releaseId)
        except mb.ResponseError as e:
            self.s.write(str(e) + " bad release ID?\n")
            return

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

    def GetSimilar(self):
        """Helps the user identify similar, possibly duplicate, releases."""
        number=20
        lds = self.c.checkLevenshteinDistances()
        for i in range (number):
            self.s.write(str(lds[i][0]) + '\t' + \
                self.c.formatDiscInfo(lds[i][1]) + ' <-> ' + \
                self.c.formatDiscInfo(lds[i][2]) + '\n')


    def Quit(self):
        """quit (or press enter)"""
        sys.exit(0)

    shellCommands = {
        'q' : Quit,
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
        'tracklist' : TrackList, 
        'audacity' : {
            'labeltrack' : LabelTrack, 
            'metatags' : MetaTags,
            },
        'coverart' : CoverArt,
        'purchase' : AddPurchaseEvent,
        'comment' : AddComment,
        'rate' : SetRating,
        'similar' : GetSimilar,
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
    # Self-test code for the shell class
    import logging
    logging.basicConfig(level=logging.INFO)
    import StringIO

    s = Shell()
