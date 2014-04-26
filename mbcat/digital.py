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

defaultFmt = '{Artist}/{Title}'

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

