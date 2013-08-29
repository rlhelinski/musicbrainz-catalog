from mbcatalog.catalog import Catalog
import timeit

c = Catalog()

print timeit.repeat(c.load, repeat=3, number=10)

print timeit.repeat(c.loadZip, repeat=3, number=10)

