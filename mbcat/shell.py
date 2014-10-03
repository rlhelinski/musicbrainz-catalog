from __future__ import unicode_literals
from mbcat.catalog import *
from mbcat.barcode import UPC
import mbcat
import os
import sys
from mbcat.inputsplitter import InputSplitter
import musicbrainzngs
import webbrowser
import itertools
_log = logging.getLogger("mbcat")
import tempfile
import traceback


class Shell:
    """An interactive shell that prompts the user for inputs and renders output for the catalog."""

    def __init__(self, stdin=sys.stdin, stdout=sys.stdout, catalog=None):
        self.c = catalog if catalog != None else Catalog()
        self.c.report()
        self.s = InputSplitter(stdin=stdin, stdout=stdout)

    def confirm(self, prompt, default=False):
        options = '[Y/n]' if default else '[y/N]'
        answer = self.s.nextLine(prompt+' '+options+' ')
        if default is True:
            return not answer or answer.lower().startswith('y')
        else:
            return answer and answer.lower().startswith('y')

    def printReleaseList(self, neighborhood, highlightId=None):
        for relId, sortStr in neighborhood:
            self.s.write(
                ('\033[92m' if relId == highlightId else "")+\
                relId+\
                sortStr+\
                ("[" + self.c.getReleaseFormat(relId) + "]")+\
                (' <<<\033[0m' if relId == highlightId else "")+\
                '\n')

    def SearchSort(self):
        """Search for a release and display its neighbors in the sorting scheme.
        Useful for sorting physical media."""
        releaseId = self.Search()
        (index, neighborhood) = self.c.getSortNeighbors(
            releaseId, matchFormat=True)
        self.printReleaseList(neighborhood, highlightId=releaseId)

    def Search(self, prompt="Enter search terms (or release ID): "):
        """Search for a release and return release ID."""
        while(True):
            input = self.s.nextLine(prompt)
            if input:
                if len(mbcat.utils.getReleaseIdFromInput(input)) == 36:
                    releaseId = mbcat.utils.getReleaseIdFromInput(input)
                    self.s.write("Release %s selected.\n" % \
                            self.formatReleaseInfo(releaseId))
                    return releaseId
                matches = list(self.c._search(input))
                if len(matches) > 1:
                    self.s.write("%d matches found:\n" % len(matches))
                    for i, match in enumerate(matches):
                        self.s.write(
                            str(i) + " " + self.formatReleaseInfo(match) + "\n")
                    while (True):
                        try:
                            index = int(self.s.nextWord("Select a match: "))
                            return matches[index]
                        except ValueError as e:
                            self.s.write(str(e) + " try again\n")
                        except IndexError as e:
                            self.s.write(str(e) + " try again\n")

                elif len(matches) == 1:
                    self.s.write("Release %s selected.\n" % \
                            self.formatReleaseInfo(matches[0]))
                    return matches[0]
                else:
                    raise ValueError("No matches for \"%s\"." % input)
            else:
                raise ValueError('No release specified.')

    def formatReleaseInfo(self, releaseId):
        return ' '.join( [
                releaseId, ':', \
                self.c.getReleaseArtist(releaseId), '-', \
                self.c.getReleaseDate(releaseId), '-', \
                self.c.getReleaseTitle(releaseId), \
                #'('+release['disambiguation']+')' if 'disambiguation' in \
                    #release else '', \
                '['+str(self.c.getReleaseFormat(releaseId))+']', \
            ] )

    def SearchTrack(self, prompt="Enter search terms (or recording ID): "):
        """Search for a recording and return recording ID."""
        while(True):
            input = self.s.nextLine(prompt)
            if input:
                if len(mbcat.utils.getReleaseIdFromInput(input)) == 36:
                    matches = [mbcat.utils.getReleaseIdFromInput(input)]
                else:
                    matches = list(self.c._search(input, table='trackwords',
                        keycolumn='trackword', outcolumn='recording'))

                self.s.write("%d %s found:\n" % (len(matches), 
                    'matches' if len(matches)>1 else 'match'))
                for i, match in enumerate(matches):
                    self.s.write(
                        str(i) + " " + \
                        self.c.formatRecordingInfo(match) + "\n")
                if len(matches) > 1:
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
                    raise ValueError("No matches for \"%s\"." % input)
            else:
                raise ValueError('No release specified.')

    def SearchTrackShowReleases(self, 
        prompt="Enter search terms (or recording ID): "):
        """Search for a track (recording) by words and show the releases on which it appears."""
        recordingId = self.SearchTrack(prompt)
        if not recordingId:
            return

        releases = self.c.recordingGetReleases(recordingId)
        if not releases:
            return

        self.s.write('\nAppears on:\n')
        for i, releaseId in enumerate(releases):
            self.s.write(
                str(i)+' '+self.formatReleaseInfo(releaseId)+'\n')

    def AddPurchaseEvent(self):
        """Add a purchase date."""
        releaseId = self.Search()

        purchases = self.c.getPurchases(releaseId)
        hdrFmtStr = '%-10s %-7s %-20s\n'
        rowFmtStr = '%-10s %7s %-20s\n'
        if purchases:
            self.s.write(''.join([
                    hdrFmtStr % ('Date', 'Price', 'Vendor')]))
            for date,price,vendor in purchases:
                self.s.write(rowFmtStr % (mbcat.decodeDate(date),price,vendor))
        dateStr = self.s.nextLine(
                'Enter purchase date ('+mbcat.dateFmtUsr+'): ')
        if not dateStr:
            raise ValueError('Empty date string.')
        vendorStr = self.s.nextLine('Vendor: ')
        if not vendorStr:
            raise ValueError('Empty vendor string.')
        priceStr = self.s.nextLine('Price: ')
        if not vendorStr:
            raise ValueError('Empty price string.')

        self.c.addPurchase(releaseId,
                float(mbcat.encodeDate(dateStr)),
                float(priceStr),
                vendorStr)

    def promptDate(self, prompt='Enter a date'):
        response = self.s.nextLine(
            prompt+' (' + mbcat.dateFmtUsr + \
            ') [blank for none, "now" for current time]: ')
        if response:
            return float(mbcat.encodeDate(response)) \
                if response.lower() != 'now' else time.time()
        else:
            return None

    def AddListenDate(self):
        """Add a listen date."""
        releaseId = self.Search()

        listenDates = self.c.getListenDates(releaseId)
        for listenDate in listenDates:
            self.s.write(str(mbcat.decodeDateTime(listenDate))+'\n')
        date = self.promptDate('Enter listen date')
        if date:
            self.c.addListenDate(releaseId, date)

    # TODO also need a delete comment function
    def AddComment(self):
        """Edit comments."""
        releaseId = self.Search()
        comment = self.c.getComment(releaseId)
        tfd, tfn = tempfile.mkstemp()
        tf = os.fdopen(tfd, 'w')
        if comment:
            tf.write(comment)
        tf.close()

        os.system('editor %s' % tfn)

        with open(tfn, 'r') as f:
            self.c.setComment(releaseId, f.read())

        os.unlink(tfn)

    def SetRating(self):
        """Add a rating."""
        releaseId = self.Search()
        currentRating = self.c.getRating(releaseId)
        if currentRating is not None and currentRating != 'None':
            self.s.write('Current rating: %d/5\n' % currentRating)
        else:
            self.s.write('No rating set\n')
        nr = self.s.nextLine('New rating [leave empty for no change]: ')
        if not nr:
            raise ValueError('Empty string.')
        if not nr.isdigit() or (int(nr) < 0) or (int(nr) > 5):
            raise ValueError('Rating must be an integer between 0 and 5')
        self.c.setRating(releaseId, nr)

    def Refresh(self):
        """Refresh XML metadata from MusicBrainz."""
        releaseId = self.Search(
            "Enter search terms or release ID [empty for all]: ")

        maxAge = self.s.nextLine(
            "Enter maximum cache age in minutes [leave empty for one minute]: ")
        maxAge = int(maxAge) * 60 if maxAge else 60

        if not releaseId:
            t = mbcat.dialogs.TextProgress(
                self.c.refreshAllMetaData(self.c, maxAge))
            t.start()
            t.join()
        elif releaseId not in self.c:
            self.s.write("Release not found\n")
            return
        else:
            self.c.addRelease(releaseId, olderThan=maxAge)

    def CoverArt(self):
        """Refresh cover art from coverart.org or Amazon.com."""
        try:
            releaseId = self.Search(
                "Enter search terms or release ID [empty for all]: ")
        except ValueError as e:
            # TODO this function needs to be rewritten like refreshAllMetaData
            self.c.refreshAllCoverArt()
        else:
            self.c.getCoverArt(releaseId)

    def Switch(self):
        """Substitute one release ID for another."""
        releaseId = self.Search()
        oldReleaseTitle = self.c.getReleaseTitle(releaseId)
        self.s.write("Enter new release ID: ")
        newReleaseId = self.s.nextWord()
        self.c.renameRelease(releaseId, newReleaseId)
        newReleaseTitle = self.c.getReleaseTitle(newReleaseId)
        if oldReleaseTitle != newReleaseTitle:
            self.s.write("Replaced '%s' with '%s'\n" %
                         (oldReleaseTitle, newReleaseTitle))
        else:
            self.s.write("Replaced '%s'\n" % (oldReleaseTitle))

    def Html(self):
        """Write HTML file."""
        fileName = self.s.nextLine(
            'Path for HTML file [empty for catalog.html]: ')
        if not fileName:
            fileName = 'catalog.html'
        widgets = ["Releases: ", progressbar.Bar(
            marker="=", left="[", right="]"), " ", progressbar.Percentage()]
        t = mbcat.dialogs.TextProgress(
            self.c.makeHtml(self.c, fileName=fileName))
        t.start()
        t.join()

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
            self.s.write("Release '%s' already exists.\n" %
                         self.c.getRelease(releaseId)['title'])
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
            self.s.write(self.formatReleaseInfo(releaseId) + '\n')

        if not found:
            raise KeyError('No variation of barcode %s found' % barCodeEntered)

    def Delete(self):
        """Delete a release."""
        releaseId = self.Search("Enter search terms or release ID to delete: ")
        if self.confirm('Delete release?', default=False):
            self.c.deleteRelease(releaseId)

    def Check(self):
        """Check releases for missing information."""
        self.s.write("Running checks...\n")
        self.c.checkReleases()
        self.s.write("DONE\n")

    def PrintCheckOutEvents(self, releaseId):
        """List the check out and in events."""
        for event in self.c.getCheckOutHistory(releaseId):
            if len(event) == 2:
                self.s.write('Checked out on: '+mbcat.decodeDate(event[0])+\
                        ' by: '+event[1]+'.\n')
            elif len(event) == 1:
                self.s.write('Checked in on: '+mbcat.decodeDate(event[0])+\
                        '.\n')

    def CheckOut(self):
        """Check out a release."""
        releaseId = self.Search()

        self.PrintCheckOutEvents(releaseId)

        if self.c.getCheckOutStatus(releaseId):
            raise ValueError('Release is already checked out. Check in first.')

        borrower = self.s.nextLine("Borrower (leave empty to return): ")
        if not borrower:
            raise ValueError('No borrower specified.')

        date = self.promptDate("Lend date")
        if date:
            self.c.addCheckOutEvent(releaseId, borrower, date)

    def CheckIn(self):
        """Check in a release."""
        releaseId = self.Search()

        self.PrintCheckOutEvents(releaseId)

        if not self.c.getCheckOutStatus(releaseId):
            raise ValueError('Release is not checked out. Check out first.')

        date = self.promptDate("Return date")
        if date:
            self.c.addCheckInEvent(releaseId, date)

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
            releaseId = self.Search(
                "Enter search terms or release ID [enter for all]: ")
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

        t = mbcat.dialogs.TextProgress(
            self.c.syncCollection(self.c, colId))
        t.start()
        t.join()

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
        number = 20
        t = mbcat.dialogs.TextProgress(
            self.c.checkLevenshteinDistances(self.c, limit=2))
        t.start()
        t.join()
        lds = t.task.result
        for i in range(number):
            self.s.write(str(lds[i][0]) + '\t' +
                         self.formatReleaseInfo(lds[i][1]) + ' <-> ' +
                         self.formatReleaseInfo(lds[i][2]) + '\n')

    def ZipExport(self):
        """Export the catalog to a zip file containing release XML files."""
        defaultPath = 'mbcat-catalog.zip'
        path = self.s.nextLine('Enter path for file [empty for \'%s\']: '
                               % defaultPath)
        if not path:
            path = defaultPath

        pbar = progressbar.ProgressBar(widgets=self.widgets)
        self.c.saveZip(path, pbar)

    def ZipImport(self):
        """Import a zip file containing XML files into the catalog."""
        defaultPath = 'mbcat-catalog.zip'
        path = self.s.nextLine('Enter path for file [empty for \'%s\']: '
                               % defaultPath)
        if not path:
            path = defaultPath

        pbar = progressbar.ProgressBar(widgets=self.widgets)
        self.c.loadZip(path, pbar)

    def printQueryResults(self, results):
        self.s.write('Release Results:\n')
        # TODO this is a mess and should be combined with other code
        for release in results['release-list']:
            self.s.write(release['id'] + ' ' +
                        # Artist(s)
                         ''.join([(('"' + cred['artist']['name'] + '"') \
                                    if isinstance(cred, dict) else cred)
                                    for cred in release['artist-credit']]) +
                         ' "' + release['title'] + '"' +
                         # Format(s)
                         (' (' + ' + '.join(mbcat.utils.mergeList(
                             [[medium['format']] if medium and 'format' in medium else []
                              for medium in release['medium-list']])) + ')') +
                         # Record Label(s) and Catalog Number(s)
                         ((' ' + ', '.join([('label: ' + info['label']['name'] if 'label' in info else '') +
                                           (' catno.: ' + info['catalog-number']
                                            if 'catalog-number' in info else '')
                                           for info in release['label-info-list']])) \
                                           if 'label-info-list' in release else '') +
                         # Country
                         ((' (' + ', '.join(mbcat.utils.mergeList(
                             [[code for code in release_event['area']['iso-3166-1-code-list']]
                              if release_event and 'area' in release_event
                              and 'iso-3166-1-code-list' in release_event['area'] else []
                              for release_event in release['release-event-list']])) + ')') \
                              if 'release-event-list' in release else '') +
                         # Barcode
                         (', barcode: ' + release['barcode'] if 'barcode' in release
                          else '') +
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
            self.s.write("Date    : %s\n" %
                         (rel['date'] if 'date' in rel else ''))
            self.s.write("Country    : %s\n" %
                         (rel['country'] if 'country' in rel else ''))
            if 'barcode' in rel:
                self.s.write("Barcode    : %s\n" % rel['barcode'])
            if 'label-info-list' in rel:
                for label_info in rel['label-info-list']:
                    for label, field in [
                            ("Label:", rel['label']['name']),
                            ("Catalog #:", rel['catalog-number']),
                            ("Barcode :", rel['barcode'])]:
                        if field:
                            self.s.write(label + ' ' + field + ',\t')
                        else:
                            self.s.write(label + '\t,\t')
            self.s.write('\n')
        return oneInCatalog

    def printGroupQueryResults(self, results):
        self.s.write('Release Group Results:\n')
        for group in results['release-group-list']:
            self.s.write(group['id'] + ' ' +
                ''.join([
                        (('"' + cred['artist']['name'] + '"') \
                        if type(cred) == dict else cred)
                        for cred in group['artist-credit']]) +
                ' "' + group['title'] + '" (%d releases)\n' % \
                    len(group['release-list']))

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
        if ' ' in catno:
            _log.warning('Removing whitespaces from string (workaround)')
            catno = catno.replace(' ', '')
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

    def MBReleaseGroup(self):
        """Search for releases on musicbrainz by group ID"""
        rgid = self.s.nextLine('Enter release group ID: ')
        results = musicbrainzngs.search_releases(rgid=rgid,
                limit=self.searchResultsLimit)

        if results:
            self.printQueryResults(results)

    def MBRelGroupTitle(self):
        """Search for release groups on musicbrainz by title"""

        title = self.s.nextLine('Enter title: ')
        results = musicbrainzngs.search_release_groups(
                releasegroup=title,
                limit=self.searchResultsLimit)

        if results:
            self.printGroupQueryResults(results)

    def CopyCount(self):
        """Check and set the on-hand copy count for a release"""

        releaseId = self.Search("Enter search terms or release ID: ")
        if not releaseId:
            raise ValueError('no release specified')
        self.s.write('Current copy count: %d\n' %
                     self.c.getCopyCount(releaseId))
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

        webbrowser.open(self.c.releaseUrl + releaseId)

    def Report(self):
        """Display high-level information about catalog"""
        self.c.report()

    def RebuildCache(self):
        """Rebuild cache database tables (used for searching)"""
        t = mbcat.dialogs.TextProgress(
            self.c.rebuildCacheTables(self.c))
        t.start()
        t.join()

    def ReadDiscTOC(self):
        """Read table of contents from a CD-ROM, search for a release, and add
to the catalog"""
        def askBrowseSubmission():
            if self.confirm('Open browser to Submission URL?', default=False):
                _log.info('Opening web browser.')
                webbrowser.open(disc.submission_url)

        try:
            import discid
        except ImportError as e:
            raise Exception('Could not import discid')
        default_device = discid.get_default_device()
        spec_device = self.s.nextLine('Device to read [empty for \'%s\']: ' %
                                      default_device)
        if not spec_device:
            spec_device = default_device

        try:
            disc = discid.read(spec_device)
        except discid.DiscError as e:
            raise Exception("DiscID calculation failed: " + str(e))
        self.s.write('DiscID: %s\n' % disc.id)
        self.s.write('Submisson URL: %s\n' % disc.submission_url)

        try:
            self.s.write("Querying MusicBrainz...")
            result = mb.get_releases_by_discid(disc.id,
                                               includes=["artists"])
            self.s.write('OK\n')
        except mb.ResponseError:
            _log.warning('Disc not found or bad MusicBrainz response.')
            askBrowseSubmission()

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
                        self.s.write('%10s: %s\n' %
                                     (label, result['cdstub'][key]))
                askBrowseSubmission()

                raise Exception('There was only a CD stub.')

        def addResultToCatalog(choice):
            if choice in self.c:
                if not self.confirm('Release already exists. Add again?',
                        default=False):
                    return
            else:
                if not self.confirm('Add release?', default=False):
                    return

            self.s.write("Adding '%s' to the catalog.\n" %
                         result['disc']['release-list'][choice]['title'])

            releaseId = mbcat.utils.extractUuid(
                result['disc']['release-list'][choice]['id'])

            self.c.addRelease(releaseId)

        if len(result['disc']['release-list']) == 0:
            raise Exception("There were no matches for disc ID: %s" % disc.id)
        elif len(result['disc']['release-list']) == 1:
            self.s.write("There was one match. " +
                         ('It is already in the catalog. ' if oneInCatalog else '') +
                         '\n')
            if not oneInCatalog:
                addResultToCatalog(0)
        else:
            self.s.write("There were %d matches.\n" %
                         len(result['disc']['release-list']))
            choice = self.s.nextLine(
                'Choose one result to add (empty for none): ')
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
        'q': Quit,
        'release' : {
            'add': Add,
            'switch': Switch,
            'delete': Delete,
            'refresh': Refresh,
            'checkout': CheckOut,
            'checkin': CheckIn,
            'count': CopyCount,
            'tracklist': TrackList,
            'coverart': CoverArt,
            'purchase': AddPurchaseEvent,
            'listen': AddListenDate,
            'comment': AddComment,
            'rate': SetRating,
            },
        'search': {
            'release' : SearchSort,
            'barcode': BarcodeSearch,
            'track': SearchTrackShowReleases,
            },
        'catalog' : {
            'html': Html,
            'similar': GetSimilar,
            'export': {
                'zip': ZipExport,
                },
            'import': {
                'zip': ZipImport,
                },
            'rebuild': RebuildCache,
            'report': Report,
            'check': Check,
            },
        'digital': {
            'path': DigitalPath,
            'search': DigitalSearch,
            #'list' : DigitalList,
        },
        'audacity': {
            'labeltrack': LabelTrack,
            'metatags': MetaTags,
        },
        'webservice': {
            'release': {
                'barcode': MBReleaseBarcode,
                'catno': MBReleaseCatno,
                'title': MBReleaseTitle,
                'group': MBReleaseGroup,
            },
            'group': {
                'title': MBRelGroupTitle,
            },
            'sync': SyncCollection,
        },
        'browser': OpenBrowser,
        'disc': ReadDiscTOC,
    }

    def cmdSummary(self, cmdStruct, level=0, parentLeader=''):
        """Print a summary of commands."""
        for i, cmdname in enumerate(sorted(cmdStruct.keys())):
            cmdfun = cmdStruct[cmdname]
            more = i < len(cmdStruct) - 1
            thisLeader = (
                ('\u251c' if more else '\u2514') + '\u2500' * 3 if level > 0 else '')
            if type(cmdfun) == dict:
                childLeader = (
                    ('\u2502' if more else ' ') + ' ' * 3 if level > 0 else '')
                self.s.write(parentLeader + thisLeader + cmdname + " :\n")
                self.cmdSummary(cmdfun, level + 1, parentLeader + childLeader)
            else:
                try:
                    self.s.write(parentLeader + thisLeader + cmdname + " : " +
                                 cmdStruct[cmdname].__doc__.strip() + "\n")
                except AttributeError as e:
                    raise Exception('No docstring for \'%s\'' % cmdname)

    def cmdParse(self, cmdStruct, input):
        try:
            if type(cmdStruct[input]) == dict:
                # Help the user along if they haven't completed a command
                if not self.s.hasMore():
                    self.s.write('Possible completions:\n')
                    self.cmdSummary(cmdStruct[input], parentLeader=' '*3)
                # Use the next input word and recur into the structure
                self.cmdParse(cmdStruct[input], self.s.nextWord().lower())
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
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    traceback.print_tb(exc_traceback)
                    self.s.write(str(e) + " Command failed.\n")
        except KeyError as e:
            self.s.write(str(e) + " Invalid command.\n")

    def main(self):
        while (True):
            input = self.s.nextWord("Enter command ('h' for help): ").lower()

            if not input or input.startswith('q'):
                break

            if (input == 'h' or input == 'help'):
                self.cmdSummary(self.shellCommands)

            elif input in self.shellCommands.keys():
                self.cmdParse(self.shellCommands, input)

            else:
                self.s.write("Invalid command\n")
