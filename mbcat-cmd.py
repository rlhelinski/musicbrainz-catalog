#!/usr/bin/python

from __future__ import print_function
from __future__ import unicode_literals
import logging
logging.basicConfig(level=logging.INFO)
import mbcat
import mbcat.catalog
import mbcat.userprefs
import mbcat.shell
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Runs the MusicBrainz-Catalog shell')
    parser.add_argument('--database', help='Specify the path to the catalog database')
    parser.add_argument('--cache', help='Specify the path to the file cache')
    args = parser.parse_args()

    prefs = mbcat.userprefs.PrefManager()
    c = mbcat.catalog.Catalog(dbPath=args.database, cachePath=args.cache, prefs=prefs)
    s = mbcat.shell.MBCatCmd(catalog=c)
    s.cmdloop()
