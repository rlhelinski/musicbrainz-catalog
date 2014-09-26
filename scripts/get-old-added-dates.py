from __future__ import unicode_literals

import sqlite3
try:
    import cPickle as pickle
except ImportError:
    import pickle
# Problem: pickle dumps takes unicode strings but returns binary strings
def listAdapter(l):
    return buffer(pickle.dumps(l))
def listConverter(s):
    return pickle.loads(s)
sqlite3.register_adapter(list, listAdapter)
sqlite3.register_converter(str("list"), listConverter)

import glob
#db_files = glob.glob('/home/ryan/Dropbox/mbcat/mbcat.db.*')
db_files = [
    #'/home/ryan/Dropbox/mbcat/mbcat.db.1401981167.bz2',
    #'/home/ryan/Dropbox/mbcat/mbcat.db.1402407797.bz2',
    #'/home/ryan/Dropbox/mbcat/mbcat.db.1404706835.bz2',
    #'/home/ryan/Dropbox/mbcat/mbcat.db.1404833080.bz2',
    #'/home/ryan/Dropbox/mbcat/mbcat.db.1405482875.bz2',
    #'/home/ryan/Dropbox/mbcat/mbcat.db.1409377728.bz2',
    #'/home/ryan/Dropbox/mbcat/mbcat.db.1410069776.bz2',
    #'/home/ryan/Dropbox/mbcat/mbcat.db.1410116048.bz2',
    #'/home/ryan/Dropbox/mbcat/mbcat.db.1410410368.bz2',
    #'/home/ryan/Dropbox/mbcat/mbcat.db.1411733272.bz2',
    "/home/ryan/Dropbox/mbcat/"
    "mbcat (revelator's conflicted copy 2014-08-23).db",
    "/home/ryan/Dropbox/mbcat/"
    "mbcat (Emory's conflicted copy 2014-09-22).db",
    "/home/ryan/Dropbox/mbcat/"
    "mbcat (Emory's conflicted copy 2014-09-26).db",
    ]

master_db = '/home/ryan/Dropbox/mbcat/mbcat.db'
master_conn = sqlite3.connect(master_db)
master_c = master_conn.cursor()

import bz2
    #db_file = bz2.BZ2File(db_bz2_file)
    #conn = sqlite3.connect(db_file)
#for db_file in db_files:
#db_file = '/home/ryan/Dropbox/mbcat/mbcat.db.1401167310'
#db_file = '/home/ryan/Dropbox/mbcat/mbcat.db.1401981167'

def import_added_dates(master_conn, master_c, db_file):
    conn = sqlite3.connect(db_file, detect_types=sqlite3.PARSE_DECLTYPES)
    c = conn.cursor()
    try:
        c.execute('select id,added from releases')
    except sqlite3.OperationalError as e:
        print (e, 'Trying new schema instead')
        new_schema = True
        try:
            c.execute('select release,date from added_dates')
        except sqlite3.OperationalError as e:
            print (e, 'New schema didn\'t work, giving up')
    else:
        new_schema = False

    added = 0; existing = 0
    for releaseId, added_list in c:
        if new_schema:
            added_list = [added_list]
        for added_date in added_list:
            master_c.execute('select count(*) from added_dates '
                'where date=? and release=?', (float(added_date),releaseId))
            exist_count = master_c.fetchone()[0]
            if exist_count == 0:
                print ("Add", releaseId, added_date)
                master_c.execute('insert or ignore into added_dates (date,release) '
                    'values (?,?)', (added_date, releaseId))
                added += 1
            else:
                #print ("Exists", releaseId, added_date)
                existing += 1

    master_conn.commit()
    print ("Added", added, "Existing", existing)

import sys
for db_bz2_file in db_files:
    print(db_bz2_file)
    if db_bz2_file.endswith('.bz2'):
        db_file = db_bz2_file.replace('.bz2', '')
        with bz2.BZ2File(db_bz2_file) as bz2_f:
            with open(db_file, 'w') as db_f:
                db_f.write(bz2_f.read())
    else:
        db_file = db_bz2_file
    import_added_dates(master_conn, master_c, db_file)
    # should unlink here, but too scared
    print ('Press enter to continue: '); sys.stdin.readline()
