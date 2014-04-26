# Several classes which inherit the same base class and contain a reference to
# a release dictionary for making callbacks and resolving the symbolic names. 
from __future__ import print_function
from __future__ import unicode_literals
import mbcat
import re
import collections

class PathArtist(object):
    symbol = '{artist}'
    def eval(self, release):
        return mbcat.utils.formatSortCredit(release)

class PathTitle(object):
    symbol = '{title}'
    def eval(self, release):
        return release['title'] + \
                (' ('+release['disambiguation']+')'
                    if 'disambiguation' in release else '')

class PathYear(object):
    symbol = '{year}'
    def eval(self, release):
        return release['date'].split('-')[0] if 'date' in release else ''

class PathDate(object):
    symbol = '{date}'
    def eval(self, release):
        return release['date'] if 'date' in release else '', \

class DigitalPath(list):
    """A list of digital path parts that can be resolved to a specific path for
    a specific release"""
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

    def __init__(self, s):
        self.digestString(s)

    def digestString(self, s=''):
        while s:
            m = self.literalre.match(s)
            if m:
                print (m.group(0))
                self.append(m.group(0))
                s = s[m.end():]
                continue
            m = self.symbolre.match(s)
            if m:
                print (m.group(1))
                self.append(self.symbolMap[m.group(1).lower()]())
                s = s[m.end():]
                continue

    def toString(self, release):
        return ''.join([
                elem if isinstance(elem, unicode) or \
                isinstance(elem, str) else \
                elem.eval(release) for elem in self
            ])

