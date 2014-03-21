#!/usr/bin/python

from __future__ import print_function
import logging
logging.basicConfig(level=logging.INFO)
from mbcat.catalog import *
from mbcat.extradata import *
from mbcat.barcode import UPC
import os
import sys
from mbcat.shell import *
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Runs the MusicBrainz-Catalog shell')
    parser.add_argument('--database', help='Specify the path to the catalog database')
    parser.add_argument('--cache', help='Specify the path to the file cache')
    args = parser.parse_args()

    c = Catalog(dbPath=args.database, cachePath=args.cache)
    s = Shell(catalog=c)
    s.main()

