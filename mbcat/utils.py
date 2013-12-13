"""Various utilities to simplify common tasks.

This module contains helper functions to make common tasks easier.

@author: Matthias Friedrich <matt@mafr.de>
"""
__revision__ = '$Id: utils.py 13322 2011-11-03 13:38:06Z luks $'

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




# EOF
