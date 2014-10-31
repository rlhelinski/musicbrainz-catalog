import cProfile, pstats, StringIO, random, os
import logging
logging.basicConfig(level=logging.INFO)

pr = cProfile.Profile()
pr.enable()

from mbcat.catalog import Catalog

os.system('rm -rf release-id/')
assert not os.path.isdir('release-id')

c = Catalog()

assert len(c) == 0

from . import test_releases

for relId in test_releases: 
    # Would like to add some random user nuances
    # (mbcat.catalog.Catalog.releaseUrl if random.random() < 0.3 else '') + relId
    c.addRelease(relId)

assert len(c) == len(test_releases)

c.load()
c.makeHtml()
#c.saveZip()
#c.loadZip()


for relId in test_releases:
    if random.random() < 0.3:
        c.deleteRelease(relId)

c.makeHtml()

pr.disable() # stop profiling 
s = StringIO.StringIO()
sortby = 'cumulative'
ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
ps.print_stats()
print s.getvalue()
