import cProfile, pstats, StringIO

pr = cProfile.Profile()
pr.enable()

from mbcatalog.catalog import Catalog

c = Catalog()
c.load()
c.makeHtml()
c.saveZip()
c.loadZip()

pr.disable()
s = StringIO.StringIO()
sortby = 'cumulative'
ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
ps.print_stats()
print s.getvalue()
