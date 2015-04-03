from __future__ import unicode_literals
from mbcat.catalog import *
from mbcat.barcode import UPC
import mbcat
import mbcat.digital
import os
# TODO should not need this after fixing Catalog.writeTrackList()
import sys
import musicbrainzngs
import webbrowser
_log = logging.getLogger("mbcat")
import tempfile

import readline  # should be imported before 'cmd'
import cmd

class MBCatCmd(cmd.Cmd):
    """An interactive shell for MBCat"""

    prompt = 'mbcat: '

    searchResultsLimit = 20

    def __init__(self, catalog):
        cmd.Cmd.__init__(self)
        self.c = catalog
        self.history_file_path = os.path.expanduser('~/.mbcat/history')
        if (os.path.isfile(self.history_file_path)):
            readline.read_history_file(self.history_file_path)

    def confirm(self, prompt, default=False):
        options = '[Y/n]' if default else '[y/N]'
        answer = raw_input(prompt+' '+options+' ')
        if default is True:
            return not answer or answer.lower().startswith('y')
        else:
            return answer and answer.lower().startswith('y')

    def prompt_date(self, prompt='Enter a date'):
        response = raw_input(
            prompt + ' (' + mbcat.dateFmtUsr +
            ') ["now" for current time, empty to cancel]: ')
        if response:
            return float(mbcat.encodeDate(response)) \
                if response.lower() != 'now' else time.time()
        else:
            return None

    def emptyline(self):
        """Do nothing on an empty line"""
        pass

    def cmd_do(self, cmd, cmd_d, line_parts):
        if not line_parts or line_parts[0] not in cmd_d:
            self.show_subcmds(cmd)
            return
        if len(line_parts) == 1 and callable(cmd_d[line_parts[0]]):
            try:
                cmd_d[line_parts[0]](self)
            except ValueError as e:
                print ('Command failed: '+str(e))
            except EOFError as e:
                print ('Command failed: '+str(e))
        else:
            self.cmd_do(line_parts[0], cmd_d[line_parts[0]], line_parts[1:])

    def cmd_complete(self, cmd_d, text, line_parts, begidx, endidx):
        if len(line_parts) > 1:
            if line_parts[0] not in cmd_d:
                return
            return self.cmd_complete(cmd_d[line_parts[0]], text,
                                      line_parts[1:], begidx, endidx)
        else:
            if not text:
                completions = [name for name, func in cmd_d.items()]
            else:
                completions = [ name
                        for name, func in cmd_d.items()
                        if name.startswith(text)
                        ]
            return completions

    def do_catalog(self, line):
        """Catalog commands"""
        self.cmd_do('catalog', self.cmds['catalog'], line.split(' '))

    def complete_catalog(self, text, line, begidx, endidx):
        return self.cmd_complete(self.cmds['catalog'], text,
                                 line.split(' ')[1:], begidx, endidx)

    def help_catalog(self):
        self.show_subcmds('catalog')

    def do_search(self, line):
        """Search commands"""
        self.cmd_do('search', self.cmds['search'], line.split(' '))

    def complete_search(self, text, line, begidx, endidx):
        return self.cmd_complete(self.cmds['search'], text,
                                 line.split(' ')[1:], begidx, endidx)

    def help_search(self):
        self.show_subcmds('search')

    def catalog_report(self):
        """Display high-level information about catalog"""
        self.c.report()

    def catalog_rebuild(self):
        """Rebuild cache database tables (used for searching)"""
        t = mbcat.dialogs.TextProgress(
            self.c.rebuildDerivedTables(self.c))
        t.start()
        t.join()

    def catalog_check(self):
        """Check releases for missing information"""
        print("Running checks...\n")
        self.printReleaseList(self.c.checkReleases())

    def formatReleaseInfo(self, releaseId):
        return ' '.join([
                releaseId, ':', \
                self.c.getReleaseArtist(releaseId), '-', \
                self.c.getReleaseDate(releaseId), '-', \
                self.c.getReleaseTitle(releaseId), \
                #'('+release['disambiguation']+')' if 'disambiguation' in \
                    #release else '', \
                '['+str(self.c.getReleaseFormat(releaseId))+']', \
            ])

    def _search_release(self, prompt="Enter search terms (or release ID): "):
        """Search for a release and return release ID."""
        # TODO could use readline.get_completer() and
        # readline.set_completer(fun) here in order to temporarily substitute a
        # custom completer for releases
        while(True):
            input = raw_input(prompt)
            if input:
                if len(mbcat.utils.getReleaseIdFromInput(input)) == 36:
                    releaseId = mbcat.utils.getReleaseIdFromInput(input)
                    print("Release %s selected.\n" % \
                            self.formatReleaseInfo(releaseId))
                    return releaseId
                matches = list(self.c._search(input))
                if len(matches) > 1:
                    print("%d matches found:\n" % len(matches))
                    for i, match in enumerate(matches):
                        print(str(i) + " " + self.formatReleaseInfo(match))
                    while (True):
                        try:
                            index = int(raw_input("Select a match: "))
                            return matches[index]
                        except ValueError as e:
                            print(str(e) + " try again\n")
                        except IndexError as e:
                            print(str(e) + " try again\n")

                elif len(matches) == 1:
                    print("Release %s selected.\n" % \
                            self.formatReleaseInfo(matches[0]))
                    return matches[0]
                else:
                    raise ValueError("No matches for \"%s\"." % input)
            else:
                raise ValueError('No release specified.')

    def search_release(self):
        """Search for a release and display its neighbors in the sorting scheme.
        Useful for sorting physical media."""
        releaseId = self._search_release()
        (index, neighborhood) = self.c.getSortNeighbors(
            releaseId, matchFormat=True)
        self.printReleaseList(neighborhood, highlightId=releaseId)

    def search_barcode(self):
        """Search for a release by barcode"""
        barCodeEntered = raw_input("Enter barcode: ")
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
            print(self.formatReleaseInfo(releaseId) + '\n')

        if not found:
            raise KeyError('No variation of barcode %s found' % barCodeEntered)

    def do_release(self, line):
        """Release commands"""
        self.cmd_do('release', self.cmds['release'], line.split(' '))

    def complete_release(self, text, line, begidx, endidx):
        return self.cmd_complete(self.cmds['release'], text,
                                 line.split(' ')[1:], begidx, endidx)

    def help_release(self):
        self.show_subcmds('release')

    def release_add(self):
        """Add a release."""
        usr_input = raw_input("Enter release ID: ")
        releaseId = mbcat.utils.getReleaseIdFromInput(usr_input)
        if not releaseId:
            print("No input")
            return
        if releaseId in self.c:
            print("Release '%s' already exists.\n" %
                         self.c.getRelease(releaseId)['title'])
            return
        try:
            self.c.addRelease(releaseId)
        except mb.ResponseError as e:
            print(str(e) + " bad release ID?\n")
            return

        print("Added '%s'.\n" % self.c.getRelease(releaseId)['title'])

        self.c.getCoverArt(releaseId)

    def release_switch(self):
        """Substitute one release ID for another."""
        releaseId = self._search_release()
        oldReleaseTitle = self.c.getReleaseTitle(releaseId)
        # TODO make more consistent use of getReleaseIdFromInput()
        newReleaseId = mbcat.utils.getReleaseIdFromInput(
                raw_input("Enter new release ID: "))
        self.c.renameRelease(releaseId, newReleaseId)
        newReleaseTitle = self.c.getReleaseTitle(newReleaseId)
        if oldReleaseTitle != newReleaseTitle:
            print("Replaced '%s' with '%s'\n" %
                         (oldReleaseTitle, newReleaseTitle))
        else:
            print("Replaced '%s'\n" % (oldReleaseTitle))

    def release_delete(self):
        """Delete a release."""
        releaseId = self._search_release(
                "Enter search terms or release ID to delete: ")
        if self.confirm('Delete release?', default=False):
            self.c.deleteRelease(releaseId)

    def release_refresh(self):
        """Refresh XML metadata from MusicBrainz."""
        releaseId = self._search_release(
            "Enter search terms or release ID [empty for all]: ")

        maxAge = raw_input(
            "Enter maximum cache age in minutes "
            "[leave empty for one minute]: ")
        maxAge = int(maxAge) * 60 if maxAge else 60

        if not releaseId:
            t = mbcat.dialogs.TextProgress(
                self.c.refreshAllMetaData(self.c, maxAge))
            t.start()
            t.join()
        elif releaseId not in self.c:
            print("Release not found\n")
            return
        else:
            self.c.addRelease(releaseId, olderThan=maxAge)

    def PrintCheckOutEvents(self, releaseId):
        """List the check out and in events."""
        history = self.c.getCheckOutHistory(releaseId)
        if not history:
            print('No checkout events for %s' % (releaseId,))
        for event in history:
            if len(event) == 2:
                print('Checked out on: '+mbcat.decodeDate(event[0])+\
                        ' by: '+event[1]+'.\n')
            elif len(event) == 1:
                print('Checked in on: '+mbcat.decodeDate(event[0])+\
                        '.\n')

    def release_check_out(self):
        """Check out a release."""
        releaseId = self._search_release()

        self.PrintCheckOutEvents(releaseId)

        if self.c.getCheckOutStatus(releaseId):
            raise ValueError('Release is already checked out. Check in first.')

        borrower = raw_input("Borrower (leave empty to return): ")
        if not borrower:
            raise ValueError('No borrower specified.')

        date = self.prompt_date("Lend date")
        if date:
            self.c.addCheckOutEvent(releaseId, borrower, date)

    def release_check_in(self):
        """Check in a release."""
        releaseId = self._search_release()

        self.PrintCheckOutEvents(releaseId)

        if not self.c.getCheckOutStatus(releaseId):
            raise ValueError('Release is not checked out. Check out first.')

        date = self.prompt_date("Return date")
        if date:
            self.c.addCheckInEvent(releaseId, date)

    def release_copycount(self):
        """Check and set the on-hand copy count for a release"""

        releaseId = self._search_release("Enter search terms or release ID: ")
        if not releaseId:
            raise ValueError('no release specified')
        print('Current copy count: %d\n' %
                     self.c.getCopyCount(releaseId))
        newCount = raw_input('New copy count [empty for no change]: ')
        if newCount:
            try:
                self.c.setCopyCount(releaseId, int(newCount))
            except ValueError as e:
                raise ValueError('copy count must be an integer')

    def release_tracklist(self):
        """Print a list of track titles and times."""
        # TODO function below should be part of this class, not Catalog
        self.c.writeTrackList(sys.stdout, self._search_release())

    def release_coverart(self):
        """Refresh cover art from coverart.org or Amazon.com."""
        try:
            releaseId = self._search_release(
                "Enter search terms or release ID [empty for all]: ")
        except ValueError as e:
            # TODO this function needs to be rewritten like refreshAllMetaData
            self.c.refreshAllCoverArt()
        else:
            self.c.getCoverArt(releaseId)

    def release_add_purchase(self):
        """Add a purchase date."""
        releaseId = self._search_release()

        purchases = self.c.getPurchases(releaseId)
        hdrFmtStr = '%-10s %-7s %-20s\n'
        rowFmtStr = '%-10s %7s %-20s\n'
        if purchases:
            print(''.join([
                    hdrFmtStr % ('Date', 'Price', 'Vendor')]))
            for date,price,vendor in purchases:
                print(rowFmtStr % (mbcat.decodeDate(date),price,vendor))
        dateStr = raw_input(
                'Enter purchase date ('+mbcat.dateFmtUsr+'): ')
        if not dateStr:
            raise ValueError('Empty date string.')
        vendorStr = raw_input('Vendor: ')
        if not vendorStr:
            raise ValueError('Empty vendor string.')
        priceStr = raw_input('Price: ')
        if not vendorStr:
            raise ValueError('Empty price string.')

        self.c.addPurchase(releaseId,
                float(mbcat.encodeDate(dateStr)),
                float(priceStr),
                vendorStr)

    def release_add_listen(self):
        """Add a listen date."""
        releaseId = self._search_release()

        listenDates = self.c.getListenDates(releaseId)
        for listenDate in listenDates:
            print(str(mbcat.decodeDateTime(listenDate))+'\n')
        date = self.promptDate('Enter listen date')
        if date:
            self.c.addListenDate(releaseId, date)

    # TODO also need a delete comment function
    def release_add_comment(self):
        """Edit comments."""
        releaseId = self._search_release()
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

    def release_set_rating(self):
        """Add a rating."""
        releaseId = self._search_release()
        currentRating = self.c.getRating(releaseId)
        if currentRating is not None and currentRating != 'None':
            print('Current rating: %d/5\n' % currentRating)
        else:
            print('No rating set\n')
        nr = raw_input('New rating [leave empty for no change]: ')
        if not nr:
            raise ValueError('Empty string.')
        if not nr.isdigit() or (int(nr) < 0) or (int(nr) > 5):
            raise ValueError('Rating must be an integer between 0 and 5')
        self.c.setRating(releaseId, nr)

    def release_browse(self):
        """Open a web browser for a musicbrainz release page"""
        releaseId = self._search_release("Enter search terms or release ID: ")
        if not releaseId:
            raise ValueError('no release specified')

        webbrowser.open(self.c.releaseUrl + releaseId)

    def do_audacity(self, line):
        """Audacity commands"""
        self.cmd_do('audacity', self.cmds['audacity'], line.split(' '))

    def complete_audacity(self, text, line, begidx, endidx):
        return self.cmd_complete(self.cmds['audacity'], text,
                                 line.split(' ')[1:], begidx, endidx)

    def help_audacity(self):
        self.show_subcmds('audacity')

    def audacity_labeltrack(self):
        """Create label track file for Audacity; useful when transferring vinyl."""
        self.c.makeLabelTrack(self._search_release())

    def audacity_metatags(self):
        """Create metadata tags for Audacity."""
        self.c.writeMetaTags(self._search_release())

    def do_digital(self, line):
        """Digital path commands"""
        self.cmd_do('digital', self.cmds['digital'], line.split(' '))

    def complete_digital(self, text, line, begidx, endidx):
        return self.cmd_complete(self.cmds['digital'], text,
                                 line.split(' ')[1:], begidx, endidx)

    def help_digital(self):
        self.show_subcmds('digital')

    def digital_path_add(self):
        """Add a path to a digital copy of a release."""
        releaseId = self._search_release()

        path = raw_input("Enter path to add: ")
        if path.startswith("'") and path.endswith("'"):
            path = path[1:-1]
        if not os.path.isdir(path):
            raise ValueError('Path is not an existing directory')
        fmt = mbcat.digital.guessDigitalFormat(path)
        self.c.addDigitalPath(releaseId, fmt, path)

    def digital_search(self):
        """Search for digital copies of releases."""
        try:
            releaseId = self._search_release(
                "Enter search terms or release ID [enter for all]: ")
        except ValueError as e:
            releaseId = ''

        t = mbcat.dialogs.TextProgress(
                mbcat.digital.DigitalSearch(
                    self.c, releaseId=releaseId))
        t.start()
        t.join()

    def do_webservice(self, line):
        """Web service commands"""
        self.cmd_do('webservice', self.cmds['webservice'], line.split(' '))

    def complete_webservice(self, text, line, begidx, endidx):
        return self.cmd_complete(self.cmds['webservice'], text,
                                 line.split(' ')[1:], begidx, endidx)

    def help_webservice(self):
        self.show_subcmds('webservice')

    def printQueryResults(self, results):
        print('Release Results:\n')
        # TODO this is a mess and should be combined with other code
        for release in results['release-list']:
            print(release['id'] + ' ' +
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
        oneInCatalog = []
        for i, rel in enumerate(results['disc']['release-list']):
            print("\nResult : %d\n" % i)
            inCatalog = rel['id'] in self.c
            if inCatalog:
                oneInCatalog.append(rel['id'])
            print("Release  : %s%s\n" % (rel['id'],
                                                ' (in catalog)' if inCatalog else ''))
            print("Artist   : %s\n" % rel['artist-credit-phrase'])
            print("Title    : %s\n" % (rel['title']))
            print("Date    : %s\n" %
                         (rel['date'] if 'date' in rel else ''))
            print("Country    : %s\n" %
                         (rel['country'] if 'country' in rel else ''))
            if 'barcode' in rel:
                print("Barcode    : %s\n" % rel['barcode'])
            if 'label-info-list' in rel:
                for label_info in rel['label-info-list']:
                    for label, field in [
                            ("Label:", rel['label']['name']),
                            ("Catalog #:", rel['catalog-number']),
                            ("Barcode :", rel['barcode'])]:
                        if field:
                            print(label + ' ' + field + ',\t')
                        else:
                            print(label + '\t,\t')
            print('\n')
        return oneInCatalog

    def printGroupQueryResults(self, results):
        print('Release Group Results:\n')
        for group in results['release-group-list']:
            print(group['id'] + ' ' +
                ''.join([
                        (('"' + cred['artist']['name'] + '"') \
                        if type(cred) == dict else cred)
                        for cred in group['artist-credit']]) +
                ' "' + group['title'] + '" (%d releases)\n' % \
                    len(group['release-list']))

    searchResultsLimit = 20

    def MBReleaseBarcode(self):
        """Search for release on musicbrainz by barcode"""
        barcode = raw_input('Enter barcode: ')
        results = musicbrainzngs.search_releases(barcode=barcode,
                                                 limit=self.searchResultsLimit)

        if results:
            self.printQueryResults(results)

    def MBReleaseCatno(self):
        """Search for release on musicbrainz by catalog number"""
        catno = raw_input('Enter catalog number: ')
        if ' ' in catno:
            _log.warning('Removing whitespaces from string (workaround)')
            catno = catno.replace(' ', '')
        results = musicbrainzngs.search_releases(catno=catno,
                limit=self.searchResultsLimit)

        if results:
            self.printQueryResults(results)

    def MBReleaseTitle(self):
        """Search for release on musicbrainz by title"""
        title = raw_input('Enter title: ')
        results = musicbrainzngs.search_releases(release=title,
                                                 limit=self.searchResultsLimit)

        if results:
            self.printQueryResults(results)

    def MBReleaseGroup(self):
        """Search for releases on musicbrainz by group ID"""
        rgid = raw_input('Enter release group ID: ')
        results = musicbrainzngs.search_releases(rgid=rgid,
                limit=self.searchResultsLimit)

        if results:
            self.printQueryResults(results)

    def MBRelGroupTitle(self):
        """Search for release groups on musicbrainz by title"""

        title = raw_input('Enter title: ')
        results = musicbrainzngs.search_release_groups(
                releasegroup=title,
                limit=self.searchResultsLimit)

        if results:
            self.printGroupQueryResults(results)

    def SyncCollection(self):
        """Synchronize with a musicbrainz collection (currently only pushes releases)."""
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
            print('%d: "%s" by %s (%s)\n' % (i, collection['name'],
                        collection['editor'], collection['id']))

        col_i = int(raw_input('Enter collection index: '))
        colId = result['collection-list'][col_i]['id']

        t = mbcat.dialogs.TextProgress(
            self.c.syncCollection(self.c, colId))
        t.start()
        t.join()

    @staticmethod
    def askBrowseSubmission():
        if self.confirm('Open browser to Submission URL?', default=False):
            _log.info('Opening web browser.')
            webbrowser.open(disc.submission_url)

    def addResultToCatalog(self, result, choice):
        if choice in self.c:
            if not self.confirm('Release already exists. Add again?',
                    default=False):
                return
        else:
            if not self.confirm('Add release?', default=False):
                return

        print("Adding '%s' to the catalog.\n" %
                     result['disc']['release-list'][choice]['title'])

        releaseId = mbcat.utils.extractUuid(
            result['disc']['release-list'][choice]['id'])

        self.c.addRelease(releaseId)
        return releaseId

    def printDiscQueryResults(self, results):
        oneInCatalog = []
        for i, rel in enumerate(results['disc']['release-list']):
            print("Result : %d" % i)
            inCatalog = rel['id'] in self.c
            if inCatalog:
                oneInCatalog.append(rel['id'])
            print("Release  : %s%s" % (rel['id'],
                                                ' (in catalog)' if inCatalog else ''))
            print("Artist   : %s" % rel['artist-credit-phrase'])
            print("Title    : %s" % (rel['title']))
            print("Date    : %s" %
                         (rel['date'] if 'date' in rel else ''))
            print("Country    : %s" %
                         (rel['country'] if 'country' in rel else ''))
            if 'barcode' in rel:
                print("Barcode    : %s" % rel['barcode'])
            if 'label-info-list' in rel:
                for label_info in rel['label-info-list']:
                    for label, field in [
                            ("Label:", rel['label']['name']),
                            ("Catalog #:", rel['catalog-number']),
                            ("Barcode :", rel['barcode'])]:
                        if field:
                            print(label + ' ' + field + ',\t')
                        else:
                            print(label + '\t,\t')
            print('')
        return oneInCatalog

    def _do_disc(self, spec_device=None):
        """Read table of contents from a CD-ROM, search for a release, and
        optionally add to the catalog"""

        try:
            import discid
        except ImportError as e:
            raise Exception('Could not import discid')
        default_device = discid.get_default_device()
        if not spec_device:
            spec_device = raw_input('Device to read [empty for \'%s\']: ' %
                                          default_device)
        if not spec_device:
            spec_device = default_device

        try:
            disc = discid.read(spec_device)
        except discid.DiscError as e:
            raise Exception("DiscID calculation failed: " + str(e))
        print('DiscID: %s' % disc.id)
        print('Submisson URL: %s' % disc.submission_url)

        try:
            print("Querying MusicBrainz...")
            result = mb.get_releases_by_discid(disc.id,
                                               includes=["artists"])
            print('OK')
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
                        print('%10s: %s' %
                                     (label, result['cdstub'][key]))
                askBrowseSubmission()

                raise Exception('There was only a CD stub.')

        if len(result['disc']['release-list']) == 0:
            raise Exception("There were no matches for disc ID: %s" % disc.id)
        elif len(result['disc']['release-list']) == 1:
            print("There was one match. " +
                         ('It is already in the catalog. ' if oneInCatalog else ''))
            if not oneInCatalog:
                return addResultToCatalog(0)
            else:
                return oneInCatalog[0]
        else:
            print("There were %d matches." %
                         len(result['disc']['release-list']))
            choice = raw_input(
                'Choose one result to add (empty for none): ')
            if not choice.isdigit():
                raise Exception('Input was not a number')
            choice = int(choice)
            if choice < 0 or choice >= len(result['disc']['release-list']):
                raise Exception('Input was out of range')
            return self.addResultToCatalog(result, choice)

    def do_disc(self, line):
        """Read table of contents from a CD-ROM, search for a release, and
        optionally add to the catalog"""
        try:
            self._do_disc()
        except Exception as e:
            print (e)

    def do_EOF(self, line):
        # readline.set_history_length(length)
        readline.write_history_file(self.history_file_path)
        print ('')
        return True

    cmds = {
            'catalog': {
                'report': catalog_report,
                'rebuild': catalog_rebuild,
                'check': catalog_check,
                },
            'search': {
                'release': search_release,
                'barcode': search_barcode,
                },
            'release' : {
                'add': release_add,
                'switch': release_switch,
                'delete': release_delete,
                'refresh': release_refresh,
                'checkout': release_check_out,
                'checkin': release_check_in,
                'count': release_copycount,
                'tracklist': release_tracklist,
                'coverart': release_coverart,
                'purchase': release_add_purchase,
                'listen': release_add_listen,
                'comment': release_add_comment,
                'rate': release_set_rating,
                'browse': release_browse,
                },
            'audacity' : {
                'labeltrack': audacity_labeltrack,
                'metatags': audacity_metatags,
                },
            'digital' : {
                'path': digital_path_add,
                'search': digital_search,
                #'list' : digital_list,
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
            }

    def _show_subcmds(self, cmd, cmd_d, depth=0):
        print ('    '*depth + '%s sub-commands:' % cmd)
        for subcmd, subcmd_d in cmd_d.items():
            if (type(subcmd_d) == dict):
                self._show_subcmds(subcmd, subcmd_d, depth+1)
            elif callable(subcmd_d):
                print ('    '*(depth+1) + '%s: %s' % (subcmd, subcmd_d.__doc__))

    def show_subcmds(self, cmd):
        self._show_subcmds(cmd, self.cmds[cmd])

    def printReleaseList(self, neighborhood, highlightId=None):
        for relId, sortStr in neighborhood:
            print(
                ('\033[92m' if relId == highlightId else "")+\
                relId+\
                ' '+\
                sortStr+\
                ' '+\
                ("[" + self.c.getReleaseFormat(relId) + "]")+\
                (' <<<\033[0m' if relId == highlightId else "")
                )
