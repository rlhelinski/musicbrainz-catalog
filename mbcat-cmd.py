#!/usr/bin/python

from __future__ import print_function
from __future__ import unicode_literals
import logging
logging.basicConfig(level=logging.INFO)
import mbcat
from mbcat.catalog import *
from mbcat.shell import *
import argparse

import readline # should be imported before 'cmd'
import cmd
import sys

class MBCatCmd(cmd.Cmd):
    """An interactive shell for MBCat"""

    prompt = 'mbcat: '

    def __init__(self, catalog):
        cmd.Cmd.__init__(self)
        self.c = catalog

    def confirm(self, prompt, default=False):
        options = '[Y/n]' if default else '[y/N]'
        answer = raw_input(prompt+' '+options+' ')
        if default is True:
            return not answer or answer.lower().startswith('y')
        else:
            return answer and answer.lower().startswith('y')

    def emptyline(self):
        """Do nothing on an empty line"""
        pass

    def cmd_do(self, cmd, subcmd):
        if not subcmd or subcmd not in self.cmds[cmd]:
            self.show_subcmds(cmd)
            return
        print ('Got subcmd: ' + subcmd)
        try:
            self.cmds[cmd][subcmd](self)
        except ValueError as e:
            print ('Command failed: '+str(e))

    def cmd_complete(self, cmd, text, line, begidx, endidx):
        if not text:
            completions = [name for name, func in self.cmds[cmd].items()]
        else:
            completions = [ name
                    for name, func in self.cmds[cmd].items()
                    if name.startswith(text)
                    ]
        return completions

    def do_catalog(self, subcmd):
        """Catalog commands"""
        self.cmd_do('catalog', subcmd)

    def complete_catalog(self, text, line, begidx, endidx):
        return self.cmd_complete('catalog', text, line, begidx, endidx)

    def help_catalog(self):
        self.show_subcmds('catalog')

    def do_search(self, subcmd):
        """Search commands"""
        self.cmd_do('search', subcmd)

    def complete_search(self, text, line, begidx, endidx):
        return self.cmd_complete('search', text, line, begidx, endidx)

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
        return ' '.join( [
                releaseId, ':', \
                self.c.getReleaseArtist(releaseId), '-', \
                self.c.getReleaseDate(releaseId), '-', \
                self.c.getReleaseTitle(releaseId), \
                #'('+release['disambiguation']+')' if 'disambiguation' in \
                    #release else '', \
                '['+str(self.c.getReleaseFormat(releaseId))+']', \
            ] )

    def _search_release(self, prompt="Enter search terms (or release ID): "):
        """Search for a release and return release ID."""
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

    def do_release(self, subcmd):
        """Release commands"""
        self.cmd_do('release', subcmd)

    def complete_release(self, text, line, begidx, endidx):
        return self.cmd_complete('release', text, line, begidx, endidx)

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

    def do_EOF(self, line):
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
                #'refresh': release_refresh,
                #'checkout': release_check_out,
                #'checkin': release_check_in,
                #'count': release_copycount,
                #'tracklist': release_tracklist,
                #'coverart': release_coverart,
                #'purchase': release_add_purchase,
                #'listen': release_add_listen,
                #'comment': release_add_comment,
                #'rate': release_set_rating,
                },
            }

    def show_subcmds(self, cmd):
        print ('Subcommands:')
        for subcmd, func in self.cmds[cmd].items():
            print ('\t%s: %s' % (subcmd, func.__doc__))

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

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Runs the MusicBrainz-Catalog shell')
    parser.add_argument('--database', help='Specify the path to the catalog database')
    parser.add_argument('--cache', help='Specify the path to the file cache')
    args = parser.parse_args()

    prefs = mbcat.userprefs.PrefManager()
    c = Catalog(dbPath=args.database, cachePath=args.cache, prefs=prefs)
    s = MBCatCmd(catalog=c)
    s.cmdloop()

