import os
import extradata

for release_dir in os.listdir('release-id'):
    release_mtime = os.stat('release-id/'+release_dir).st_mtime
    ed = extradata.ExtraData(release_dir)
    try:
        ed.load()
    except IOError as e:
        "ignore"
        #print e
    except ValueError as e:
        print str(e) + ", while loading " + release_dir
        ed.addDate(float(release_mtime))
        ed.save()

    if not ed.addDates:
        print float(release_mtime)
        ed.addDate(float(release_mtime))
        ed.save()
