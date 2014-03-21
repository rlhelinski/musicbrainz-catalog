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

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # TODO expand this to full command-line argument parsing
        search_terms = sys.argv
        del search_terms[0]
        c = Catalog()
        c.load()
        c.search(' '.join(search_terms))

    else:
        s = Shell()
        s.main()

