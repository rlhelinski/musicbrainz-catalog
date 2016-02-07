# Several classes which inherit the same base class and contain a reference to
# a release dictionary for making callbacks and resolving the symbolic names.
from __future__ import print_function
from __future__ import unicode_literals
from . import catalog
from . import dialogs
from . import utils
import os
import re
import collections
import logging
_log = logging.getLogger("mbcat")

extre = re.compile('^.*\.([^.]*)$')

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
        return utils.formatSortCredit(release)

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

def getArtistPathVariations(release):
    return set([
            # the non-sorting-friendly string
            release['artist-credit-phrase'],
            # if just the first artist is used
            release['artist-credit'][0]['artist']['sort-name'],
            # if just the first artist is used, sort-friendly
            release['artist-credit'][0]['artist']['name'],
            # the sort-friendly string with all artists credited
            catalog.getArtistSortPhrase(release)
            ])

punctuation = { 0x2018:0x27, 0x2019:0x27, 0x201C:0x22, 0x201D:0x22 }

def getTitlePathVariations(release):
    s = set()
    prefixes = ['']
    if 'date' in release:
        prefixes.append('%s - ' % (release['date']))
        prefixes.append('%s - ' % (release['date'].split('-')[0]))
    for prefix in prefixes:
        s.add(prefix+release['title'])
        if 'disambiguation' in release:
            s.add(prefix+release['disambiguation'])
            s.add(prefix+release['title']+' ('+release['disambiguation']+')')
    for i in list(s):
        s.add(i.translate(punctuation).encode('ascii', 'ignore'))
    return s

def getPathAlNumPrefixes(path):
    """Returns a set of prefixes used for directory balancing"""
    return set([
            '', # in case nothing is used
            '0-9' if path[0].isdigit() else '',
            path[0].lower(), # most basic implementation
            path[0:1].lower(), # have never seen this
            (path[0]+'/'+path[0:2]).lower(), # used by Wikimedia
            ])

def guessDigitalFormat(fileNameList):
    if type(fileNameList) != list:
        fileNameList = os.listdir(fileNameList)
    # TODO also use file magic here
    extension_counter = collections.Counter(
        [m.group(1) if m else None for m in
            [extre.match(fileName) \
                    for fileName in fileNameList]])
    if len(extension_counter):
        return extension_counter.most_common(1)[0][0]
    else:
        _log.warning('Could not determine type for path %s' % path)
        return '[unknown]'

class DigitalSearch(dialogs.ThreadedTask):
    """
    A threaded task that searches for digital copies of one or all releases.
    """

    def __init__(self, catalog, prefs=None, releaseId=''):
        dialogs.ThreadedTask.__init__(self, 0)
        self.catalog = catalog
        self.prefs = catalog.prefs if not prefs else prefs
        self.releaseId = releaseId

    def run(self):
        self.checkExistingPaths(self.releaseId)
        if not self.stopthread.isSet():
            self.searchDigitalPaths(self.releaseId)

    def checkExistingPaths(self, releaseId=''):
        releaseIdList = [releaseId] if releaseId else \
                self.catalog.getReleaseIds()

        self.status = 'Checking existing path references...'
        self.numer = 0
        self.denom = len(releaseIdList)
        for relId in releaseIdList:
            for root_id,path,fmt in self.catalog.getDigitalPaths(relId):
                root = self.prefs.getRootPath(root_id)
                if root and not os.path.isdir(os.path.join(root, path)):
                    _log.info('Deleting release %s path "%s"' % (relId,
                            os.path.join(root, path)))
                    # TODO add query dialog here?
                    self.catalog.deleteDigitalPath(relId, root_id, path)
                self.numer += 1
                if self.stopthread.isSet():
                    return
        self.status = 'Committing changes...'
        self.numer = 0; self.denom = 0
        self.catalog.cm.commit()

    def searchDigitalPaths(self, releaseId=''):
        """
        Search for files for a release in all locations and with variations. If
        no release is specified, search for all releases in the catalog.
        """
        releaseIdList = [releaseId] if releaseId else \
                self.catalog.getReleaseIds()

        self.status = 'Searching for digital copy paths...'
        self.numer = 0
        self.denom = len(releaseIdList)*len(self.prefs.pathRoots)
        # TODO need to be more flexible in capitalization and re-order of words
        for root_id, root_dict in self.prefs.pathRoots.items():
            path = root_dict['path']
            self.catalog.addDigitalPathRoot(root_id, path)
            _log.info("Searching '%s'"%path)
            for relId in releaseIdList:
                self.searchForRelease(relId, root_id, path)
                if self.stopthread.isSet():
                    return

        self.status = 'Committing changes...'
        self.numer = 0; self.denom = 0
        self.catalog.cm.commit()

        if releaseId and not self.catalog.getDigitalPaths(releaseId):
            _log.warning('No digital paths found for '+releaseId)

    def searchForRelease(self, relId, rootPathId, rootPath):
        def sepFilesDirs(root, l):
            files = list(); dirs = list()
            for name in l:
                if os.path.isfile(os.path.join(root, name)):
                    files.append(name)
                elif os.path.isdir(os.path.join(root, name)):
                    dirs.append(name)
            return dirs, files

        rel = self.catalog.getRelease(relId)

        # Try to guess the sub-directory path
        for titlePath in self.getDigitalPathVariations(rootPath, rel):
            absTitlePath = os.path.join(rootPath, titlePath)
            if os.path.isdir(absTitlePath):
                fileList = os.listdir(absTitlePath)
                dirs, files = sepFilesDirs(absTitlePath, fileList)
                if len(files) >= min([trackCount for trackCount in \
                        self.catalog.getTrackCounts(relId)]):
                    fmt = guessDigitalFormat(fileList)
                elif dirs:
                    for d in dirs:
                        subDirFileList = os.listdir(os.path.join(
                                absTitlePath, d))
                        files.extend(subDirFileList)
                    fmt = guessDigitalFormat(files)
                else:
                    continue
                _log.info(
                        'Found release %s in "%s" under "%s" in %s format'\
                        %(relId, rootPath, titlePath, fmt)
                        )
                if len(files) < self.catalog.getTrackCount(relId):
                    _log.warning('Some tracks missing for "%s" (%d / %d)' % \
                            (relId, len(files), \
                            self.catalog.getTrackCount(relId)))
                self.catalog.addDigitalPath(relId,
                        fmt,
                        rootPathId,
                        titlePath)
            else:
                _log.debug('Did not find '+relId+' at '+titlePath)
        self.numer += 1

    def getDigitalPathVariations(self, root, release):
        for artistName in getArtistPathVariations(release):
            titlePathVars = getTitlePathVariations(release)
            # the release might be under just {Title}
            for titlePath in titlePathVars:
                if os.path.isdir(os.path.join(root, titlePath)):
                    yield titlePath
            for prefix in getPathAlNumPrefixes(artistName):
                artistPath = os.path.join(prefix, artistName)
                if os.path.isdir(os.path.join(root, artistPath)):
                    for titleName in titlePathVars:
                        yield os.path.join(artistPath, titleName)
                else:
                    _log.debug(artistPath+' does not exist')

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

