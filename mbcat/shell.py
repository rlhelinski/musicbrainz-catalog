from __future__ import unicode_literals
from mbcat.catalog import *
from mbcat.extradata import *
from mbcat.barcode import UPC
import os
import sys
from mbcat.inputsplitter import InputSplitter
import musicbrainzngs
import webbrowser
import itertools
_log = logging.getLogger("mbcat")

class Shell:
    """An interactive shell that prompts the user for inputs and renders output for the catalog."""
    widgets = ["Releases: ", progressbar.Bar(
                marker="=", left="[", right="]"), 
            " ", progressbar.Percentage() ]

    def __init__(self, stdin=sys.stdin, stdout=sys.stdout, catalog=None):
        self.c = catalog if catalog!=None else Catalog()
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
                    releaseId = mbcat.utils.getReleaseIdFromInput(input)
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


    def AddPurchaseEvent(self):
        """Add a purchase date."""
        releaseId = self.Search()

        purchases = self.c.getPurchases(releaseId)
        for purchase in purchases:
            self.s.write(str(purchase)+'\n')
        dateStr = self.s.nextLine('Enter purchase date ('+dateFmtUsr+'): ')
        if not dateStr:
            raise ValueError('Empty date string.')
        vendorStr = self.s.nextLine('Vendor: ')
        if not vendorStr:
            raise ValueError('Empty vendor string.')
        priceStr = self.s.nextLine('Price: ')
        if not vendorStr:
            raise ValueError('Empty price string.')

        pe = PurchaseEvent(dateStr, priceStr, vendorStr)
        self.c.addPurchase(releaseId, pe)

    def AddListenDate(self):
        """Add a listen date."""
        releaseId = self.Search()

        listenDates = self.c.getListenDates(releaseId)
        for listenDate in listenDates:
            self.s.write(time.strftime(dateFmtStr, time.localtime(listenDate))+'\n')
        dateStr = self.s.nextLine('Enter listen date ('+dateFmtUsr+') [enter for now]: ')
        date = time.strptime(dateStr,dateFmtStr) if dateStr else time.time()

        self.c.addListenDate(releaseId, date)

    # TODO also need a delete comment function
    def AddComment(self):
        """Add a comment."""
        releaseId = self.Search()
        comment = self.c.getComment(releaseId)
        if comment:
            self.s.write('Comments: ' + comment + '\n')
        newComment = self.s.nextLine('Additional Comment: ')
        if not newComment:
            raise ValueError('Empty string.')

        if comment:
            newComment = comment+'\n'+newComment
        self.c.setComment(releaseId, newComment)

    def SetRating(self):
        """Add a rating."""
        releaseId = self.Search()
        currentRating = self.c.getRating(releaseId)
        if currentRating:
            self.s.write ('Current rating: %d/5\n' % currentRating)
        else:
            self.s.write ('No rating set\n')
        nr = self.s.nextLine('New rating [leave empty for no change]: ')
        if not nr:
            raise ValueError('Empty string.')
        if not nr.isdigit() or (int(nr) < 0) or (int(nr) > 5):
            raise ValueError('Rating must be an integer between 0 and 5')
        self.c.setRating(releaseId, nr)

    def Refresh(self):
        """Refresh XML metadata from MusicBrainz."""
        releaseId = self.Search("Enter search terms or release ID [empty for all]: ")

        maxAge = self.s.nextLine("Enter maximum cache age in minutes [leave empty for one minute]: ")
        maxAge = int(maxAge)*60 if maxAge else 60

        pbar = progressbar.ProgressBar(widgets=self.widgets)
        if not releaseId:
            self.c.refreshAllMetaData(maxAge, pbar)
        elif releaseId not in self.c:
            self.s.write("Release not found\n")
            return
        else:
            self.c.addRelease(releaseId, olderThan=maxAge)

    def CoverArt(self):
        """Refresh cover art from coverart.org or Amazon.com."""
        try:
            releaseId = self.Search("Enter search terms or release ID [empty for all]: ")
        except ValueError as e:
            self.c.refreshAllCoverArt()
        else:
            self.c.getCoverArt(releaseId)

    def Switch(self):
        """Substitute one release ID for another."""
        releaseId = self.Search()
        oldReleaseTitle = self.c.getRelease(releaseId)['title']
        self.s.write("Enter new release ID: ")
        newReleaseId = self.s.nextWord()
        self.c.renameRelease(releaseId, newReleaseId)
        newReleaseTitle = self.c.getRelease(newReleaseId)['title']
        if oldReleaseTitle != newReleaseTitle:
            self.s.write("Replaced '%s' with '%s'\n" % (oldReleaseTitle, newReleaseTitle))
        else:
            self.s.write("Replaced '%s'\n" % (oldReleaseTitle))

    def Html(self):
        """Write HTML file."""
        fileName = self.s.nextLine('Path for HTML file [empty for catalog.html]: ')
        if not fileName:
            fileName='catalog.html'
        widgets = ["Releases: ", progressbar.Bar(marker="=", left="[", right="]"), " ", progressbar.Percentage() ]
        pbar = progressbar.ProgressBar(widgets=self.widgets)
        self.c.makeHtml(fileName=fileName,pbar=pbar)

        answer = self.s.nextLine('Open browser to view HTML? [y/N]')
        if answer and answer.lower().startswith('y'):
            _log.info('Opening web browser.')
            webbrowser.open(fileName)

    def Add(self):
        """Add a release."""
        self.s.write("Enter release ID: ")
        releaseId = mbcat.utils.getReleaseIdFromInput(self.s.nextWord())
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

        self.c.getCoverArt(releaseId)

    def BarcodeSearch(self):
        """Search for a release by barcode."""
        barCodeEntered = self.s.nextWord("Enter barcode: ")
        barCodes = UPC(barCodeEntered).variations()
        found = False

        pairs = set()
        for barCode in barCodes:
            try:
                for releaseId in self.c.barCodeLookup(barCode):
                    pairs.add(releaseId)
            except KeyError as e:
                pass
            else:
                found = True

        for releaseId in pairs:
            self.s.write(self.c.formatDiscInfo(releaseId)+'\n')

        if not found:
            raise KeyError('No variation of barcode %s found' % barCodeEntered)

    def Delete(self):
        """Delete a release."""
        releaseId = self.Search("Enter search terms or release ID to delete: ")
        self.c.deleteRelease(releaseId)

    def Check(self):
        """Check releases for missing information."""
        self.s.write("Running checks...\n")
        self.c.checkReleases()
        self.s.write("DONE\n")

    def CheckOut(self):
        """Check out a release."""
        releaseId = self.Search()

        lendEvents = self.c.getLendEvents(releaseId)
        for event in lendEvents:
            self.s.write (str(event)+'\n')

        borrower = self.s.nextLine("Borrower (leave empty to return): ")
        if not borrower:
            raise ValueError ('No release specified.')

        date = self.s.nextLine("Lend date  ("+dateFmtUsr+") (leave empty for today): ")
        if not date:
            date = time.time()
        self.c.addLendEvent(releaseId, CheckOutEvent(borrower, date))

    def CheckIn(self):
        """Check in a release."""
        releaseId = self.Search()

        lendEvents = self.c.getLendEvents(releaseId)
        if not lendEvents or not isinstance(lendEvents[-1], CheckOutEvent):
            raise ValueError ('Release is not checked out.')

        date = self.s.nextLine("Return date ("+dateFmtUsr+") (leave empty for today): ")
        if not date:
            date = time.time()
        self.c.addLendEvent(releaseId, CheckInEvent(date))

    def DigitalPath(self):
        """Add a path to a digital copy of a release."""
        releaseId = self.Search()

        path = self.s.nextLine("Enter path to add: ")
        if path.startswith("'") and path.endswith("'"):
            path = path[1:-1]
        self.c.addDigitalPath(releaseId, path)

    def DigitalSearch(self):
        """Search for digital copies of releases."""
        pbar = progressbar.ProgressBar(widgets=self.widgets)
        try:
            releaseId = self.Search("Enter search terms or release ID [enter for all]: ")
        except ValueError as e:
            self.c.searchDigitalPaths(pbar=pbar)
        else:
            self.c.searchDigitalPaths(releaseId=releaseId, pbar=pbar)

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
        pbar = progressbar.ProgressBar(widgets=self.widgets)
        lds = self.c.checkLevenshteinDistances(pbar)
        for i in range (number):
            self.s.write(str(lds[i][0]) + '\t' + \
                self.c.formatDiscInfo(lds[i][1]) + ' <-> ' + \
                self.c.formatDiscInfo(lds[i][2]) + '\n')

    def ZipExport(self):
        """Export the catalog to a zip file containing release XML files."""
        defaultPath = 'mbcat-catalog.zip'
        path = self.s.nextLine('Enter path for file [empty for \'%s\']: '\
                %defaultPath)
        if not path:
            path = defaultPath

        pbar = progressbar.ProgressBar(widgets=self.widgets)
        self.c.saveZip(path, pbar)

    def ZipImport(self):
        """Import a zip file containing XML files into the catalog."""
        defaultPath = 'mbcat-catalog.zip'
        path = self.s.nextLine('Enter path for file [empty for \'%s\']: '\
                %defaultPath)
        if not path:
            path = defaultPath

        pbar = progressbar.ProgressBar(widgets=self.widgets)
        self.c.loadZip(path, pbar)

    @staticmethod
    def mergeList(l):
        return list(set(itertools.chain.from_iterable(l)))

    def printQueryResults(self, results):
        self.s.write('Release Results:\n')
        for release in results['release-list']:
            self.s.write(release['id']+' '+\
                    ', '.join(['"'+cred['artist']['name']+'"' \
                            for cred in release['artist-credit']])+\
                    ' "'+release['title']+'"'+\
                    (' ('+' + '.join(self.mergeList(
                            [[medium['format']] if medium and 'format' in medium else [] \
                            for medium in release['medium-list']]))+')')+\
                    (' ' +', '.join([('label: '+info['label']['name'] if 'label' in info else '') +\
                            (' catno.: '+info['catalog-number'] if 'catalog-number' in info else '') \
                            for info in release['label-info-list']]))+\
                    (' ('+', '.join(self.mergeList(
                            [[code for code in release_event['area']['iso-3166-1-code-list']]\
                            if release_event and 'area' in release_event \
                            and 'iso-3166-1-code-list' in release_event['area'] else [] \
                            for release_event in release['release-event-list']]))+')')+\
                    (', barcode: '+release['barcode'] if 'barcode' in release
else '')+\
                    '\n')

    def printDiscQueryResults(self, results):
        oneInCatalog = False
        for i, rel in enumerate(results['disc']['release-list']):
            self.s.write("\nResult : %d\n" % i)
            inCatalog = rel['id'] in self.c
            oneInCatalog |= inCatalog
            self.s.write("Release  : %s%s\n" % (rel['id'],
                    ' (in catalog)' if inCatalog else ''))
            self.s.write("Artist   : %s\n" % rel['artist-credit-phrase'])
            self.s.write("Title    : %s\n" % (rel['title']))
            self.s.write("Date    : %s\n" % (rel['date'] if 'date' in rel else ''))
            self.s.write("Country    : %s\n" % (rel['country'] if 'country' in rel else ''))
            if 'barcode' in rel:
                self.s.write("Barcode    : %s\n" % rel['barcode'])
            if 'label-info-list' in rel:
                for label_info in rel['label-info-list']:
                    for label, field in [ \
                                    ("Label:", rel['label']['name']), \
                                    ("Catalog #:", rel['catalog-number']), \
                                    ("Barcode :", rel['barcode']) ]:
                        if field:
                            self.s.write(label+' '+field+',\t')
                        else:
                            self.s.write(label+'\t,\t')
            self.s.write('\n')
        return oneInCatalog

    def printGroupQueryResults(self, results):
        self.s.write('Release Group Results:\n')
        for group in results['release-group-list']:
            self.s.write(group['id']+' '+\
                    ', '.join(['"'+cred['artist']['name']+'"' \
                            for cred in group['artist-credit']])+\
                    ' "'+group['title']+'" (%d releases)\n' % len(group['release-list']))

    searchResultsLimit = 20

    def MBReleaseBarcode(self):
        """Search for release on musicbrainz by barcode"""
        barcode = self.s.nextLine('Enter barcode: ')
        results = musicbrainzngs.search_releases(barcode=barcode,
                limit=self.searchResultsLimit)

        if results:
            self.printQueryResults(results)

    def MBReleaseCatno(self):
        """Search for release on musicbrainz by catalog number"""
        catno = self.s.nextLine('Enter catalog number: ')
        results = musicbrainzngs.search_releases(catno=catno,
                limit=self.searchResultsLimit)

        if results:
            self.printQueryResults(results)

    def MBReleaseTitle(self):
        """Search for release on musicbrainz by title"""
        title = self.s.nextLine('Enter title: ')
        results = musicbrainzngs.search_releases(release=title,
                limit=self.searchResultsLimit)

        if results:
            self.printQueryResults(results)

    def MBRelGroupTitle(self):
        """Search for release groups on musicbrainz by title"""

        title = self.s.nextLine('Enter title: ')
        results = musicbrainzngs.search_release_groups(releasegroup=title,
                limit=self.searchResultsLimit)

        if results:
            self.printGroupQueryResults(results)

    def CopyCount(self):
        """Check and set the on-hand copy count for a release"""

        releaseId = self.Search("Enter search terms or release ID: ")
        if not releaseId:
            raise ValueError('no release specified')
        self.s.write('Current copy count: %d\n' % self.c.getCopyCount(releaseId))
        newCount = self.s.nextLine('New copy count [empty for no change]: ')
        if newCount:
            try:
                self.c.setCopyCount(releaseId, int(newCount))
            except ValueError as e:
                raise ValueError('copy count must be an integer')

    def OpenBrowser(self):
        """Open a web browser for a musicbrainz release page"""
        releaseId = self.Search("Enter search terms or release ID: ")
        if not releaseId:
            raise ValueError('no release specified')

        webbrowser.open(self.c.releaseUrl+releaseId)

    def Report(self):
        """Display high-level information about catalog"""
        self.c.report()



    def ReadDiscTOC(self):
        """Read table of contents from a CD-ROM, search for a release, and add
to the catalog"""
        try:
            import discid
        except ImportError as e:
            raise Exception('Could not import discid')
        default_device = discid.get_default_device()
        spec_device = self.s.nextLine('Device to read [empty for \'%s\']: ' %\
                default_device)
        if not spec_device:
            spec_device = default_device

        try:
            disc = discid.read(spec_device)
        except discid.DiscError as e:
            raise Exception ("DiscID calculation failed: " + str(e))
        self.s.write ('DiscID: %s\n' % disc.id)
        self.s.write ('Submisson URL: %s\n' % disc.submission_url)

        try:
            self.s.write ("Querying MusicBrainz...")
            result = mb.get_releases_by_discid(disc.id,
                    includes=["artists"])
            self.s.write ('OK\n')
        except mb.ResponseError:
            raise Exception("Disc not found or bad MusicBrainz response.")
        else:
            if result.get("disc"):
                oneInCatalog = self.printDiscQueryResults(result)
            elif result.get("cdstub"):
                for label, key in [
                    ('CD Stub', 'id'),
                    ('Artist', 'artist'),
                    ('Title', 'title'),
                    ('Barcode', 'barcode')]:
                    if key in result['cdstub']:
                        self.s.write('%10s: %s\n' % (label, result['cdstub'][key]))
                answer = self.s.nextLine('Open browser to Submission URL? [y/N]')
                if answer and answer.lower().startswith('y'):
                    _log.info('Opening web browser.')
                    webbrowser.open(disc.submission_url)

                raise Exception('There was only a CD stub.')

        def addResultToCatalog(choice):
            self.s.write("Adding '%s' to the catalog.\n" % result['disc']['release-list'][choice]['title'])

            releaseId = mbcat.utils.extractUuid(result['disc']['release-list'][choice]['id'])

            self.c.addRelease(releaseId)


        if len(result['disc']['release-list']) == 0:
            raise Exception("There were no matches for disc ID: %s" % disc.id)
        elif len(result['disc']['release-list']) == 1:
            self.s.write("There was one match. " + \
                ('It is already in the catalog. ' if oneInCatalog else '') + \
                '\n')
            if not oneInCatalog:
                addResultToCatalog(0)
        else:
            self.s.write("There were %d matches.\n" % len(result['disc']['release-list']))
            choice = self.s.nextLine('Choose one result to add (empty for none): ')
            if not choice.isdigit():
                raise Exception('Input was not a number')
            choice = int(choice)
            if choice < 0 or choice >= len(result['disc']['release-list']):
                raise Exception('Input was out of range')
            addResultToCatalog(choice)


    def Quit(self):
        """quit (or press enter)"""
        sys.exit(0)

    # The master list of shell commands
    shellCommands = {
        'q' : Quit,
        'search' : SearchSort,
        'refresh' : Refresh,
        'html' : Html,
        'switch' : Switch,
        'add' : Add,
        'barcode' : BarcodeSearch,
        'delete' : Delete,
        'check' : Check,
        'checkout' : CheckOut,
        'checkin' : CheckIn,
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
        'listen' : AddListenDate,
        'comment' : AddComment,
        'rate' : SetRating,
        'similar' : GetSimilar,
        'export' : {
            'zip' : ZipExport,
            },
        'import' : {
            'zip' : ZipImport,
            },
        'mb' : {
            'release' : {
                'barcode' : MBReleaseBarcode,
                'catno' : MBReleaseCatno,
                'title' : MBReleaseTitle,
                },
            'group' : {
                'title' : MBRelGroupTitle,
                },
            },
        'count' : CopyCount,
        'browser' : OpenBrowser,
        'report' : Report,
        'disc' : ReadDiscTOC,
        }

    def main(self):
        def cmdSummary(cmdStruct, level=0, parentLeader=''):
            """Print a summary of commands."""
            #import pdb; pdb.set_trace()
            for i, cmdname in enumerate(sorted(cmdStruct.keys())):
                cmdfun = cmdStruct[cmdname]
                more = i < len(cmdStruct)-1
                thisLeader = (('\u251c' if more else '\u2514')+'\u2500'*3 if level>0 else '')
                if type(cmdfun) == dict:
                    childLeader = (('\u2502' if more else ' ')+' '*3 if level>0 else '')
                    self.s.write(parentLeader + thisLeader + cmdname + " :\n")
                    cmdSummary (cmdfun, level+1, parentLeader+childLeader)
                else:
                    try:
                        self.s.write(parentLeader + thisLeader + cmdname + " : " +
                                cmdStruct[cmdname].__doc__.strip() + "\n")
                    except AttributeError as e:
                        raise Exception('No docstring for \'%s\'' % cmdname)

        def cmdParse(cmdStruct, input):
            try:
                if type(cmdStruct[input]) == dict:
                    # Use the next input word and recur into the structure
                    cmdParse(cmdStruct[input], self.s.nextWord().lower())
                else:
                    # Remind the user what this command does
                    try:
                        self.s.write(cmdStruct[input].__doc__.strip() + '\n')
                    except AttributeError as e:
                        raise Exception('No docstring for \'%s\'' % input)
                    # Call the function
                    try:
                        (cmdStruct[input])(self)
                    except ValueError as e:
                        self.s.write(str(e) + " Command failed.\n")
                    except KeyError as e:
                        self.s.write(str(e) + " Command failed.\n")
                    except Exception as e:
                        self.s.write(str(e) + " Command failed.\n")
            except KeyError as e:
                self.s.write(str(e) + " Invalid command.\n")

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

