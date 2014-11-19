
MusicBrainz Catalog
===================

`musicbrainz-catalog` is a Python application for cataloging your music
collection and cross-referencing with the
[MusicBrainz.org](http://musicbrainz.org) online database. Both
[GTK](http://www.gtk.org/) and text-mode interfaces are available. Using
MusicBrainz helps provide the information about the releases you own based on a
[CD TOC](http://musicbrainz.org/doc/Disc%20ID) or a
[barcode](http://en.wikipedia.org/wiki/Universal_Product_Code), for example.
The catch is that if the information about a release in the MusicBrainz.org
online database is missing or incorrect, that you fix it for everyone's benefit.
However, with over 1,293,000 releases (as of 2014-06-12), you should expect to
not have to enter this information about your release most of the time.

![Screenshot](doc/mbcat-screenshot.png "Screenshot of GTK interface on Mac OSX")

This application can help you perform the following tasks:

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

Installation
============

You'll need the following software to get started:

* [Python](https://www.python.org/),
* [musicbrainzngs](https://github.com/rlhelinski/python-musicbrainzngs),
* [python-discid](https://github.com/JonnyJD/python-discid) (optional; requires
[libdiscid](http://musicbrainz.org/doc/libdiscid)),
* and the `musicbrainz-catalog` source code.

On Ubuntu Linux, get the pre-requisites with the following command:
```bash
sudo apt-get install python python-musicbrainzngs libdiscid0 python-libdiscid
```

Once you have the pre-requisites, we recommend cloning the source code using
Git so that you can stay up to date with development. To copy the source code
with Git so that you can easily upgrade later, use the command:
```bash
git clone https://github.com/rlhelinski/musicbrainz-catalog.git
```
The "master" branch should always be the latest and greatest revision.

To get a ZIP file of the latest version instead of using Git, use the following
link:
https://github.com/rlhelinski/musicbrainz-catalog/archive/master.zip

The 'catalog-cli.py' script is the text-mode interface to the catalog. Start it
with
```bash
python catalog-cli.py
```

Example Workflow
================

This section will walk you though several of the common tasks with
musicbrainz-catalog using the text-mode shell. You can always get a list of the
shell commands and their descriptions by typing `h` or `help` at the shell
prompt.

Add a Release
-------------

Assume that you just bought a new release. We can check if MusicBrainz.org has
a release associated with the barcode on the label. Enter the command:

```
webservice release barcode 724596941621
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
release add 8e378c3e-0af4-373f-94fc-84c03e8b4374
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
Enter command ('h' for help): search release
Enter search terms (or release ID): me
```

You can also search for a release using a barcode (`search barcode`) or the
name of a track (`search track`) as we discuss below.
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

on ANSI terminals, the selected release (denoted by a trailing "<<<" here) is
highlighted.

Write an HTML File of the Catalog
---------------------------------

One of the main forms of output from the program is an
[en.wikipedia.org/wiki/HTML](HTML) file containing information about your
catalog. To write it out, use the command:

```
catalog html
```

The shell will prompt you for the path to write the HTML document. The path to
this file is stored as a user prefernce in the file `~/.mbcat/userprefs.xml`.
It will use the working directory by default.

```
Path for HTML file [empty for catalog.html]:
```

You will then be asked if you want to open the HTML file in a browser:

```
Open browser to view HTML? [y/N]
```

The default is not to open. 

Refresh Release Metadata
------------------------

The metadata about a release on MusicBrainz.org can change at any time. If
there has been a change to a release that you have already added, you may wish
to update the data about that release. Use the `release refresh` command:
```
Enter command ('h' for help): release refresh
```

The command will prompt you to enter search terms or a release ID. Enter
nothing here if you wish to refresh all of the metadata in the catalog.  Note
that musicbrainz-catalog [limits the rate at which queries are
made](https://musicbrainz.org/doc/XML_Web_Service/Rate_Limiting) to the
MusicBrainz.org web service to once per second and that a full refresh can take
a while.

```
Enter search terms or release ID [empty for all]: moby
2 matches found:
0 679841df-599d-402f-9f89-0d0bb6e94368 : Moby - 1999-06-01 - Play  [Compact Disc]
1 8e378c3e-0af4-373f-94fc-84c03e8b4374 : Moby - 2009-06-30 - Wait for Me  [Compact Disc]
Select a match: 1
Enter maximum cache age in minutes [leave empty for one minute]: 
INFO:mbcat:Release 8e378c3e-0af4-373f-94fc-84c03e8b4374 is already in catalog.
INFO:mbcat:Fetching metadata for 8e378c3e-0af4-373f-94fc-84c03e8b4374
```


Search Catalog by Barcode
-------------------------

If you are trying to put a release away and it has a
[barcode](http://en.wikipedia.org/wiki/Universal_Product_Code), you can search 
for it in your catalog using the command:

```
search barcode
```

You will be prompted for the barcode. Note that the program will try slight
variations on the barcode, such as adding or removing leading 0s, when doing
its search.

```
Enter barcode: 724596941621
```

In this case, one release was found, but it is possible that multiple releases
will be returned. 

```
Enter barcode: 8e378c3e-0af4-373f-94fc-84c03e8b4374 : Moby - 2009-06-30 - Wait for Me  [Compact Disc]
```

If the release is not in the catalog and you wish to add it, you can search for
it by barcode on the MusicBrainz.org web service. Use the command: 

```
Enter command ('h' for help): webservice release barcode
```

Again, you will be prompted for the barcode:

```
Enter barcode: 724596941621
```

A release was found.
```
Release Results:
8e378c3e-0af4-373f-94fc-84c03e8b4374 "Moby" "Wait for Me" (CD) label: Mute catno.: mut 9416-2 (US), barcode: 724596941621
```

To add this release, you would copy and paste the release UUID and use the
`release add` command as we did before. 

Search for a Track (Recording)
------------------------------

The musicbrainz-catalog application also stores information about what words
are in the title of a track (or recording) and about on which releases that
track appears. Use the `track search` command:

```
Enter command ('h' for help): search track
```

Enter your search terms
```
Enter search terms (or recording ID): back black
```

The catalog will come back and give you a list of track that were found 
matching the search terms.

```
1 match found:
0 ef71afb6-5e51-41df-999b-9e7c7306063a: Back in Black (4:15)
```

If more than one track is found, it will ask you to choose one so that it can
report the releases. In this case, only one track was found, so the shell shows the releases on which this track appears. 

```
Appears on:
0 83ff6988-2f79-40b9-82d5-437f2a5da5f3 : AC/DC - 2003-02-18 - Back in Black  [Compact Disc]
```

Delete and Switch Releases
--------------------------

If you wish to remove a release from the catalog, use the `release delete` command. 

You may have noticed that the release you added was wrong, for example, if you
added the wrong release from a release group or if you created a new release in
a release group since adding a release to the catalog. To accurately reflect the 
release that you have, you can use the `release switch` command. It will prompt
you for the release you wish to switch and then for the new release UUID to use
instead. Other information associated with this release, such as when it was
first added and your personal rating are retained. 

