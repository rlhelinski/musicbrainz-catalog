This is the "master" branch, which should always be the latest and greatest
revision. 

What is it?
===================

musicbrainz-catalog is a Python application for cataloging your music
collection and cross-referencing with the
[MusicBrainz.org](http://musicbrainz.org) online database. This approach helps
provide the information about the releases you own given just a [CD
TOC](http://musicbrainz.org/doc/Disc%20ID) or a
[barcode](http://en.wikipedia.org/wiki/Universal_Product_Code), for example.
The caveat is that if the information about a release in the MusicBrainz.org
online database is missing or incorrect, that you fix it for everyone's
benefit. However, with over 1,293,000 releases (as of 2014-06-12), you should
expect to not have to enter this information about your release 90% of the
time. Life is good.

This application will help you perform the following tasks:

* Check if you have a particular [release](https://musicbrainz.org/doc/Release)
  or [track](https://musicbrainz.org/doc/Recording) in your collection
* Sort your collection alphabetically, e.g., find where a release should be put
  away
* Create an [HTML](http://en.wikipedia.org/wiki/Html) file representing the
  catalog for archiving, sharing, printing, etc.
* Track which releases you have checked out (e.g., in the car) or lent out
  (e.g., to Sam)
* Search for releases in the MusicBrainz.org online database
    * Using the [CD TOC](http://musicbrainz.org/doc/Disc%20ID) (with
      [python-discid](https://github.com/JonnyJD/python-discid)) 
    * Searching by title, barcode or catalog number
* Synchronize your catalog with a 
  [MusicBrainz.org collection](https://musicbrainz.org/doc/Collections)
* Output metatags and a label track to help with converting vinyl to digital 
  in [Audacity](http://audacity.sourceforge.net/)
* Track other information like:
    * When, where and the cost when you purchased a release
    * When you listened to a release
    * A personal rating
    * Comments
    * Count (how many you have on-hand)

Getting Started
===============

You'll need [Python](https://www.python.org/),
[python-discid](https://github.com/JonnyJD/python-discid) (which requires
[libdiscid](http://musicbrainz.org/doc/libdiscid)) and the musicbrainz-catalog
source code. 

To copy the source code with Git so that you can easily upgrade later, use the
command:
```
git clone https://github.com/rlhelinski/musicbrainz-catalog.git
```

To get a ZIP file instead, use the following link:
https://github.com/rlhelinski/musicbrainz-catalog/archive/master.zip

The 'catalog-cli.py' script is the text-mode interface to the catalog. Start it
with 
```
python catalog-cli.py
```

Example Workflow
===============

You just got a new release. We can check if MusicBrainz.org has a release
associated with the barcode on the label. Enter the command:
```
mb release barcode 724596941621
```
The shell comes back with the output:
```
Release Results:
8e378c3e-0af4-373f-94fc-84c03e8b4374 "Moby" "Wait for Me" (CD) label: Mute catno.: mut 9416-2 (US), barcode: 724596941621
```
We recognize the artist and title of the single release that was found, which
is identified by its UUID at the beginning of the line. We can add this release
to the catalog with the `add` command and copy & paste the release UUID: 
```
add 8e378c3e-0af4-373f-94fc-84c03e8b4374
```

