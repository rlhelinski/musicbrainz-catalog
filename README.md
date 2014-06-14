This is the "master" branch, which should always be the latest and greatest
revision. 

What is it?
===================

musicbrainz-catalog is a Python application for cataloging your music
collection and cross-referencing with the
[MusicBrainz.org](http://musicbrainz.org) online database. This approach helps
provide the information about the releases you own given just a 
[CD TOC](http://musicbrainz.org/doc/Disc%20ID) or a
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
      [python-discid](https://github.com/JonnyJD/python-discid)) (optional)
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
[python-discid](https://github.com/JonnyJD/python-discid) (optional; requires
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
================

This section will walk you though several of the common tasks with
musicbrainz-catalog using the text-mode shell. You can always get a list of the
shell command and their descriptions by typing `h` or `help` at the shell
prompt.

Add a Release
-------------

Assume that you just bought a new release. We can check if MusicBrainz.org has
a release associated with the barcode on the label. Enter the command:

```
mb release barcode 724596941621
```

We're in luck. The shell comes back with the output:

```
Release Results:
8e378c3e-0af4-373f-94fc-84c03e8b4374 "Moby" "Wait for Me" (CD) label: Mute catno.: mut 9416-2 (US), barcode: 724596941621
```

We recognize the artist and title of the one release that was found, which is
identified by its [UUID](http://en.wikipedia.org/wiki/Uuid) at the beginning of
the line. We can add this release to the catalog with the `add` command and
copy & paste the release UUID: 

```
add 8e378c3e-0af4-373f-94fc-84c03e8b4374
```

The shell fetches the information about this release from MusicBrainz.org, adds
it to the catalog, and also fetches cover art. It tries coverartarchive.org
first and then tries amazon.com.  

```
Add a release.
Enter release ID: INFO:mbcat:Fetching metadata for 8e378c3e-0af4-373f-94fc-84c03e8b4374
Added 'Wait for Me'.
INFO:mbcat:Checking for coverart https://coverartarchive.org/release/8e378c3e-0af4-373f-94fc-84c03e8b4374
WARNING:mbcat:No cover art for 8e378c3e-0af4-373f-94fc-84c03e8b4374 available from Cover Art Archive
INFO:mbcat:Trying to fetch cover art from Amazon instead
INFO:mbcat:Fetching 'http://ec1.images-amazon.com/images/P/B0027G783W.01.LZZZZZZZ.jpg'
INFO:mbcat:Wrote 12859 bytes to /Users/ryan/.mbcat/cache/8/8e/8e378c3e-0af4-373f-94fc-84c03e8b4374/cover.jpg
```

By default, musicbrainz-catalog stores all of its information in a hidden
directory in your home directory `~/.mbcat`. Inside this directory, the SQLite3
database is at `mbcat.db` and the cover art is stored under a directory called
`cache`. The actual cover art files are organized into sub-directories in the
same way as [Mediawiki](http://www.mediawiki.org/) to avoid directories with
too many files in them. 

Sort a Release Away
-------------------

Assuming that we have a few releases in our catalog, and we've organized them
on our shelf. To figure out where the new release belongs, you may use the
`search` command. This command will let you search for a release using search
terms, including words that appear in the artist name or release title, or
using the release ID directly. Once a unique release is selected, it prints the
neighborhood of releases so you can find its place easily. Releases of
different types are shown in separate neighborhoods. For example, CDs will be
organized separately from 12" vinyl records. 

To try it out, enter the `search` command. Then enter your search terms:

```
Enter command ('h' for help): search
Enter search terms (or release ID): me
```

If there is more than one release found, you will be asked to choose one.

```
3 matches found:
0 d4e57d35-d8f8-4302-bca4-534b6227e284 : National, The - 2013-05-20 - Trouble Will Find Me  [Compact Disc]
1 e68b0dbf-ac3f-4dcc-9894-b5532904ab4a : 2Pac - 2001 - All Eyez on Me  [Compact Disc]
2 8e378c3e-0af4-373f-94fc-84c03e8b4374 : Moby - 2009-06-30 - Wait for Me  [Compact Disc]
```

Choose the release we're after using the index on the far left-hand side:

```
Select a match: 2
```

Finally, the neighborhood is printed out as follows:

```
 ...
 321 7ace18b7-e82f-3de4-b6c1-42912e9a8f0b Miller, Steve, Band - 1989 - Abracadabra [Compact Disc] 
 322 30ec81bf-05fd-49e2-bfe3-1c386899ac0d Minogue, Kylie - 2002-02-26 - Fever [Compact Disc] 
 323 8e378c3e-0af4-373f-94fc-84c03e8b4374 Moby - 2009-06-30 - Wait for Me [Compact Disc]  <<<
 324 0838ba20-a571-4b3c-8c0c-a31436d373b3 Morissette, Alanis - 1995-06-13 - Jagged Little Pill [Compact Disc] 
 325 4b811465-bef3-3321-8a6f-25dd7f17a166 Morricone, Ennio - 1986 - The Mission [Compact Disc] 
 ...
```

on ANSI terminals, the selected release is highlighted.

Write an HTML File of the Catalog
---------------------------------

Refresh Release Metadata
------------------------

Search Catalog by Barcode
-------------------------

Search for a Track (Recording)
------------------------------

Delete and Switch Releases
--------------------------



