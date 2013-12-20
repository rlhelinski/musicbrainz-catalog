import logging
_log = logging.getLogger("mbcat")

class Format(object):
    def __eq__(self, other):
        return self.size == other.size

    def __lt__(self, other):
        return self.size < other.size

    def __str__(self):
        return self.__doc__
    
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
    size = 12

class Unknown(Format):
    """(unknown)"""
    size = None

class Digital(Format):
    """Digital Media"""
    # Can we prove that digital releases have zero volume? :)
    size = 0

def getFormatObj(fmtStr):
    """Factory function that returns a medium format object given a format string."""
    if not fmtStr:
        return Unknown
    if fmtStr.startswith('12"') or fmtStr == 'Vinyl':
        # If the format is just "Vinyl", assume it is 12"
        return Vinyl12
    elif fmtStr.startswith('10"'):
        return Vinyl10
    elif fmtStr.startswith('7"'):
        return Vinyl7
    elif 'CD' in fmtStr or fmtStr=='DualDisc' or 'DVD' in fmtStr:
        return CD
    elif fmtStr == 'Digital Media':
        return Digital
    else:
        raise ValueError('Format "'+fmtStr+'" not recognized.')
        
def getReleaseFormat(rel):
    """Useful for grouping releases by type or size."""
    # characterize the mediums and bin this release into a specific format type
    try:
        fmts = []
        for medium in rel['medium-list']:
            fmts.append(getFormatObj(medium['format']))

        sortFormat = max(fmts)
    except KeyError:
        _log.warning('No format for ' + rel['id'])
        sortFormat = Unknown

    return sortFormat

