# Several classes which inherit the same base class and contain a reference to
# a release dictionary for making callbacks and resolving the symbolic names.
from __future__ import print_function
from __future__ import unicode_literals
import mbcat
import re
import collections

class DigitalPathSymbol(object):
    def __init__(self):
        self.subset = list()
    def eval(self, release):
        val = self._eval(release)
        if not self.subset:
            return val
        elif len(self.subset)==1:
            return val.lower()[self.subset[0]]
        else:
            return val.lower()[self.subset[0]:self.subset[1]]

class PathArtist(DigitalPathSymbol):
    symbol = '{artist}'
    def _eval(self, release):
        return mbcat.utils.formatSortCredit(release)

class PathTitle(DigitalPathSymbol):
    symbol = '{title}'
    def _eval(self, release):
        return release['title'] + \
                (' ('+release['disambiguation']+')'
                    if 'disambiguation' in release else '')

class PathYear(DigitalPathSymbol):
    symbol = '{year}'
    def _eval(self, release):
        return release['date'].split('-')[0] if 'date' in release else ''

class PathDate(DigitalPathSymbol):
    symbol = '{date}'
    def _eval(self, release):
        return release['date'] if 'date' in release else '', \

defaultPathSpec = '{Artist}/{Title}'

class DigitalPath(list):
    """A list of digital path parts that can be resolved to a specific path for
    a specific release.

    Examples:
    >>> import mbcat.digital
    >>> rel = s.c.getRelease('4867ceba-ffe7-40c0-a093-45be6c03c655')

    >>> dp = mbcat.digital.DigitalPath('{Artist}/{Year} - {Title}')
    >>> dp.toString(rel)
    u'Daft Punk/2013 - Random Access Memories'

    >>> dp = mbcat.digital.DigitalPath('{Artist}[0]/{Artist}/{Year} - {Title}')
    >>> dp.toString(rel)
    u'd/Daft Punk/2013 - Random Access Memories'

    """
    patterns = [
            PathArtist,
            PathTitle,
            PathYear,
            PathDate
        ]
    symbolMap = {
        'artist' : PathArtist,
        'title' : PathTitle,
        'year' : PathYear,
        'date' : PathDate,
        }
    symbolre = re.compile('\{([^\}]+)\}')
    literalre = re.compile('[^\{\[]+')
    subsetre = re.compile('\[([^\]]+)\]')

    def __init__(self, s):
        self.digestString(s)

    def digestString(self, s=''):
        while s:
            m = self.literalre.match(s)
            if m:
                print ('literal '+m.group(0))
                self.append(m.group(0))
                s = s[m.end():]
                continue
            m = self.symbolre.match(s)
            if m:
                print ('symbol '+m.group(1))
                self.append(self.symbolMap[m.group(1).lower()]())
                s = s[m.end():]
                continue
            m = self.subsetre.match(s)
            if m:
                print ('subset '+m.group(1))
                # check that the subset was applied to a symbol that has been
                # processed
                if len(self) < 1 or (not isinstance(self[-1], PathArtist)):
                    raise Exception('subset "%s" not applied to a symbol' % \
                            m.group(0))
                self[-1].subset = [int(m.group(1))]
                s = s[m.end():]
                continue
            raise Exception('Expression not supported "%s"' % s)

    def toString(self, release):
        return ''.join([
                elem if isinstance(elem, unicode) or \
                isinstance(elem, str) else \
                elem.eval(release) for elem in self
            ])

class DigitalSearch(object):
    def __init__(self, catalog, prefs=None):
        self.catalog = catalog
        self.prefs = catalog.prefs if not prefs else prefs

    @staticmethod
    def getArtistPathVariations(release):
        return set([
                # the non-sorting-friendly string
                release['artist-credit-phrase'],
                # if just the first artist is used
                release['artist-credit'][0]['artist']['sort-name'],
                # if just the first artist is used, sort-friendly
                release['artist-credit'][0]['artist']['name'],
                # the sort-friendly string with all artists credited
                mbcat.catalog.getArtistSortPhrase(release)
                ])

    @staticmethod
    def getTitlePathVariations(release):
        s = set()
        s.add(release['title'])
        if 'disambiguation' in release:
            s.add(release['disambiguation'])
            s.add(release['title']+' ('+release['disambiguation']+')')
        return s

    @staticmethod
    def getPathAlNumPrefixes(path):
        """Returns a set of prefixes used for directory balancing"""
        return set([
                '', # in case nothing is used
                path[0].lower(), # most basic implementation
                path[0:1].lower(), # have never seen this
                (path[0]+'/'+path[0:2]).lower(), # used by Wikimedia
                ])

    def getDigitalPathVariations(self, root, release):
        for artistName in self.getArtistPathVariations(release):
            for prefix in self.getPathAlNumPrefixes(artistName):
                artistPath = os.path.join(root, prefix, artistName)
                if os.path.isdir(artistPath):
                    for titleName in self.getTitlePathVariations(release):
                        yield os.path.join(artistPath, titleName)
                else:
                    _log.debug(artistPath+' does not exist')

    def searchDigitalPaths(self, releaseId='', pbar=None):
        """Search for files for a release in all locations and with variations
        """
        releaseIdList = [releaseId] if releaseId else \
                self.catalog.getReleaseIds()

        if pbar:
            pbar.maxval = len(self.catalog)*len(self.prefs.pathRoots)
            pbar.start()
        # TODO need to be more flexible in capitalization and re-order of words
        for path in self.prefs.pathRoots:
            _log.info("Searching '%s'"%path)
            for relId in releaseIdList:
                rel = self.catalog.getRelease(relId)
                if pbar:
                    pbar.update(pbar.currval + 1)

                # Try to guess the sub-directory path
                for titlePath in self.getDigitalPathVariations(path, rel):
                    if os.path.isdir(titlePath):
                        _log.info('Found '+relId+' at '+titlePath)
                        self.catalog.addDigitalPath(relId, titlePath)
                    else:
                        _log.debug('Did not find '+relId+' at '+titlePath)
        if pbar:
            pbar.finish()

        if releaseId and not self.catalog.getDigitalPaths(releaseId):
            _log.warning('No digital paths found for '+releaseId)

    def getDigitalPath(self, releaseId, pathSpec=None):
        """
        Returns the expectedfile path for a release given a specific release ID
        and a path specification string (mbcat.digital).
        """
        if not pathSpec:
            pathSpec = self.prefs.defaultPathSpec
        return DigitalPath(pathSpec).toString(
                self.catalog.getRelease(releaseId))

    def fixDigitalPath(self, releaseId, digitalPathRoot=None):
        """This function moves a digital path to the correct location, which is
        specified by a path root string"""
        pathSpec = self.prefs.pathFmts[digitalPathRoot] \
            if digitalPathRoot else self.prefs.defaultPathSpec
        if not digitalPathRoot:
            raise NotImplemented('You need to specify a digital path root')

        assert digitalPathRoot in self.prefs.pathRoots
        pathFmt = self.prefs.pathFmts[digitalPathRoot]
        correctPath = self.getDigitalPath(releaseId, pathFmt)
        for path in self.getDigitalPaths(releaseId):
            path = os.path.join(digitalPathRoot, DigitalPath(pathFmt))
            if path != correctPath:
                _log.info('Moving "%s" to "%s"' % (path, correctPath))
                shutil.move(path, correctPath)

