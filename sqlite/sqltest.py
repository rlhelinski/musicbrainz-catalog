import sqlite3

print sqlite3.version
print sqlite3.sqlite_version

# Create a new database

# Connect to our database
con = None

with sqlite3.connect('test.db') as con:

    cur = con.cursor()
    cur.execute('SELECT SQLITE_VERSION()')

    data = cur.fetchone()

    print "SQLite version: %s" % data

with sqlite3.connect('test.db') as con:
    cur = con.cursor()
    cur.execute("CREATE TABLE Catalog(Id TEXT, Meta TEXT)")
    
