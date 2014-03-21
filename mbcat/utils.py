"""Various utilities to simplify common tasks.

This module contains helper functions to make common tasks easier.

@author: Matthias Friedrich <matt@mafr.de>
"""
__revision__ = '$Id: utils.py 13322 2011-11-03 13:38:06Z luks $'

import warnings

def deprecated(func):
    """This is a decorator which can be used to mark functions
    as deprecated. It will result in a warning being emmitted
    when the function is used."""
    def newFunc(*args, **kwargs):
        warnings.warn("Call to deprecated function %s." % func.__name__,
                      category=DeprecationWarning)
        return func(*args, **kwargs)
    newFunc.__name__ = func.__name__
    newFunc.__doc__ = func.__doc__
    newFunc.__dict__.update(func.__dict__)
    return newFunc

import re
try:
    from urlparse import urlparse
except ImportError as e:
    from urllib.parse import urlparse

__all__ = [
	'extractUuid',
]


# A pattern to split the path part of an absolute MB URI.
PATH_PATTERN = '^/(artist|release|track|label|release-group)/([^/]*)$'


def extractUuid(uriStr, resType=None):
	"""Extract the UUID part from a MusicBrainz identifier.

	This function takes a MusicBrainz ID (an absolute URI) as the input
	and returns the UUID part of the URI, thus turning it into a relative
	URI. If C{uriStr} is None or a relative URI, then it is returned
	unchanged.

	The C{resType} parameter can be used for error checking. Set it to
	'artist', 'release', or 'track' to make sure C{uriStr} is a
	syntactically valid MusicBrainz identifier of the given resource
	type. If it isn't, a C{ValueError} exception is raised.
	This error checking only works if C{uriStr} is an absolute URI, of
	course.

	Example:

	>>> from musicbrainz2.utils import extractUuid
	>>>  extractUuid('http://musicbrainz.org/artist/c0b2500e-0cef-4130-869d-732b23ed9df5', 'artist')
	'c0b2500e-0cef-4130-869d-732b23ed9df5'
	>>>

	@param uriStr: a string containing a MusicBrainz ID (an URI), or None
	@param resType: a string containing a resource type

	@return: a string containing a relative URI, or None

	@raise ValueError: the given URI is no valid MusicBrainz ID
	"""
	if uriStr is None:
		return None

	(scheme, netloc, path) = urlparse(uriStr)[:3]

	if scheme == '':
		return uriStr	# no URI, probably already the UUID

	if scheme != 'http' or netloc != 'musicbrainz.org':
		raise ValueError('%s is no MB ID.' % uriStr)

	m = re.match(PATH_PATTERN, path)

	if m:
		if resType is None:
			return m.group(2)
		else:
			if m.group(1) == resType:
				return m.group(2)
			else:
				raise ValueError('expected "%s" Id' % resType)
	else:
		raise ValueError('%s is no valid MB ID.' % uriStr)

# This goes with getFormatFromUri(), but can we replace that with a library function?
try:
    import HTMLParser
    h = HTMLParser.HTMLParser()
except ImportError as e:
    import html.parser
    h = html.parser.HTMLParser()

@deprecated
def getFormatFromUri(uriStr, escape=True):
    # TODO deprecate
    #return uriStr.split("#")[1].decode('ascii')
    formatStr = uriStr.split("#", 1)[1]
    if escape:
        return h.unescape(formatStr)
    else:
        return formatStr

def getReleaseIdFromInput(releaseId):
    """Extracts a release ID from a string or a URL"""
    if releaseId.startswith('http'):
        return mbcat.utils.extractUuid(releaseId, 'release')
    else:
        return releaseId

def formatSortCredit(release):
    return ''.join([credit if type(credit)==str else credit['artist']['sort-name'] for credit in release['artist-credit'] ])

def releaseSortCmp(a, b):
    return unicode.lower(a[1]) < unicode.lower(b[1])

def chunks(l, n):
    """ Yield successive n-sized chunks from l. """
    for i in range(0, len(l), n):
        yield l[i:i+n]


# EOF
