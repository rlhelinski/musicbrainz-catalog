#!/usr/bin/env python

from distutils.core import setup

setup(name='mbcat',
      version='0.3',
      description='MusicBrainz Catalog',
      author='Ryan Helinski',
      # author_email='',
      url='https://www.github.com/rlhelinski/musicbrainz-catalog',
      packages=['mbcat'],
      package_data={'mbcat': ['art/*.png', 'art/*.svg']},
      scripts=['mbcat-cmd.py', 'mbcat-gtk.py',
          'scripts/mbcat-add-disc', 'scripts/mbcat-disc-get-release'],
      install_requires=[
          'pygtk==2.24',
          'musicbrainzngs==0.6',
          'discid==1.1.1',
          'py3-progressbar', #'progressbar==2.3',
          ],
      )
