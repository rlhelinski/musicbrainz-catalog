#!/usr/bin/python

from __future__ import print_function
from __future__ import unicode_literals
import logging
logging.basicConfig(level=logging.DEBUG)
import mbcat.catalog
import mbcat.digital
import os
import sys
_log = logging.getLogger("mbcat")

c = mbcat.catalog.Catalog(dbPath='test.db')

ds = mbcat.digital.DigitalSearch(c)
