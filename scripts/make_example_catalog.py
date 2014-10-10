import mbcat.catalog
c = mbcat.catalog.Catalog(dbPath='test.sqlite3')

import logging
logging.basicConfig(level=logging.DEBUG)
_log = logging.getLogger("mbcat")

from tests import test_releases

for releaseId in test_releases:
    c.addRelease(releaseId)

c.report()
