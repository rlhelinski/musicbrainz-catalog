#!/usr/bin/env python

from distutils.core import setup

# TODO move this __version__ variable to mbcat/__init__.py
from mbcat.catalog import __version__
setup(name='mbcat',
      version=__version__,
      description='MusicBrainz Catalog',
      author='Ryan Helinski',
      # author_email='',
      url='https://www.github.com/rlhelinski/musicbrainz-catalog',
      packages=['mbcat', 'progressbar'],
      package_data={'mbcat': ['art/*.png', 'art/*.svg']},
      scripts=['mbcat-cmd.py', 'mbcat-gtk.py',
          'scripts/mbcat-add-disc', 'scripts/mbcat-disc-get-release'],
      )
