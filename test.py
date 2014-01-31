from __future__ import print_function
from __future__ import unicode_literals

import mbcat.catalog

c = mbcat.catalog.Catalog()

c.report()

c.search('genesis live')

assert len(c.getReleaseIds()) == len(c)

