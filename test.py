from __future__ import print_function
from __future__ import unicode_literals

import mbcat.catalog

c = mbcat.catalog.Catalog()
c.report()
c.search('genesis live')
print (len(c.getReleaseIds()))
