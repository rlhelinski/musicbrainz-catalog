import mbcat
c = mbcat.catalog.Catalog()

for releaseId in c.getReleaseIds():
    firstAdded = c.getFirstAdded(releaseId)
    if not firstAdded:
        metatime = c.getMetaTime(releaseId)
        print (releaseId, metatime)
        c.addAddedDate(releaseId, metatime)
