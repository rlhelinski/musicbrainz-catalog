from __future__ import unicode_literals
import logging
_log = logging.getLogger("mbcat")

class Format(object):
    def __eq__(self, other):
        return self.size == other.size

    def __lt__(self, other):
        return self.size < other.size

    def __str__(self):
        return self.__doc__

    def name(self):
        return self.__class__.__name__

class Vinyl12(Format):
    """12" Vinyl"""
    size = 30

class Vinyl10(Format):
    """10" Vinyl"""
    size = 25

class Vinyl7(Format):
    """7" Vinyl"""
    size = 17

class CD(Format):
    """Compact Disc"""
    size = 12

class MD(Format):
    """Mini Disc"""
    size = 8

class DVD(Format):
    """Digital Versatile Disc"""
    # We make this the same size as CDs because these DVDs are packed with music CDs
    # (not to be confused with video releases)
    size = 12 

class Unknown(Format):
    """(unknown)"""
    size = -1

class Cassette(Format):
    """Cassette"""
    # 64 mm x 100.5 mm
    size = 10

class Digital(Format):
    """Digital Media"""
    # Can we prove that digital releases have zero volume? :)
    size = 0

def getFormatObj(fmtStr):
    """Factory function that returns a medium format object given a format string."""
    if not fmtStr or 'Unknown' in fmtStr:
        return Unknown()
    if fmtStr.startswith('12"') or fmtStr == 'Vinyl' or fmtStr == 'Vinyl12':
        # If the format is just "Vinyl", assume it is 12"
        return Vinyl12()
    elif fmtStr.startswith('10"'):
        return Vinyl10()
    elif fmtStr.startswith('7"') or fmtStr == 'Vinyl7':
        return Vinyl7()
    elif 'CD' in fmtStr or fmtStr=='DualDisc' or 'DVD' in fmtStr:
        return CD()
    elif fmtStr.startswith('Digital'):
        return Digital()
    elif fmtStr == 'Cassette':
        return Cassette()
    else:
        raise ValueError('Format "'+fmtStr+'" not recognized.')
        
def getReleaseFormat(rel):
    """Useful for grouping releases by type or size."""
    # characterize the mediums and bin this release into a specific format type
    try:
        fmts = []
        for medium in rel['medium-list']:
            fmts.append(getFormatObj(medium['format']))

        # the largest format in the release dictates its category for sorting
        sortFormat = max(fmts)
    except KeyError:
        _log.warning('No format for ' + rel['id'])
        sortFormat = Unknown()

    return sortFormat

