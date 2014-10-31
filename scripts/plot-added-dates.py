import matplotlib.pyplot as plt
from matplotlib import dates

import sqlite3
conn = sqlite3.connect('/home/ryan/Dropbox/mbcat/mbcat.db')
c = conn.cursor()
import itertools
c.execute('select date from added_dates')
added_dates = list(itertools.chain.from_iterable(c))
print(len(added_dates))

import datetime
dts = map(datetime.datetime.fromtimestamp, added_dates)
fds = dates.date2num(dts) # converted
# matplotlib date format object
hfmt = dates.DateFormatter('%m/%d/%Y %H:%M')

fig = plt.figure()
ax = fig.add_subplot(111)
#ax.vlines(fds, y2, y1)
plt.hist(fds, bins=32)

ax.xaxis.set_major_locator(dates.MonthLocator())
ax.xaxis.set_major_formatter(hfmt)
ax.set_ylim(bottom = 0)
plt.xticks(rotation='vertical')
plt.subplots_adjust(bottom=.3)
plt.show()
