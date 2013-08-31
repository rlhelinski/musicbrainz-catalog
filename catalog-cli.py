#!/usr/bin/python

from mbcatalog.catalog import *
from mbcatalog.extradata import *
import os, shutil

c = Catalog()
c.load()

def getInput():
    return sys.stdin.readline().strip()

def shellSearch():
    global c
    while(True):
        print "Enter search terms (or release ID): ",
        input = getInput()
        if input:
            if len(getReleaseId(input)) == 36:
                releaseId = getReleaseId(input)
                c.getSortNeighbors(releaseId, matchFormat=True)
                return releaseId
            matches = list(c._search(input))
            if len(matches) > 1:
                print len(matches), "matches found:"
                for i, match in enumerate(matches):
                    print i, c.formatDiscInfo(match)
                while (True):
                    try:
                        print "Select a match: ",
                        index = int(getInput())
                        c.getSortNeighbors(matches[index], matchFormat=True)
                        return matches[index]
                    except ValueError as e:
                        print e, "try again"
                    except IndexError as e:
                        print e, "try again"

            elif len(matches) == 1:
                c.getSortNeighbors(matches[0], matchFormat=True)
                return matches[0]
            else:
                print "No matches."
        else:
            break


def shellReload():
    global c # should rap into a class?
    del c 
    c = Catalog()
    print "Reloading database...",
    c.load()
    print "DONE"

def shellEditExtra():
    global c
    releaseId = shellSearch()
    if not releaseId:
        return
    ed = ExtraData(releaseId)
    try:
        ed.load()
        print str(ed)
        print "Modify? [y/N]",
    except IOError as e:
        print "Add? [y/N]",
    modify = getInput()
    if modify.lower().startswith('y'):
        ed.interactiveEntry()
        ed.save()

def shellRefresh():
    global c
    print "Enter release ID [a for all]: ",
    releaseId = getReleaseId(getInput())
    if releaseId == "a":
        c.refreshAllMetaData(60*60)
    elif releaseId not in c:
        print "Release not found"
        return
    else:
        c.refreshMetaData(releaseId, olderThan=60)

def shellChange():
    global c
    print "Enter release ID: ",
    releaseId = getReleaseId(getInput())
    if releaseId not in c:
        print "Release not found"
        return
    print "Enter new release ID: ",
    newReleaseId = getInput()
    c.renameRelease(releaseId, newReleaseId)

def shellHtml():
    global c
    c = Catalog()
    c.load()
    c.makeHtml()

def shellAdd():
    global c
    print "Enter release ID: ",
    releaseId = getReleaseId(getInput())
    if not releaseId:
        print "No input"
        return
    if releaseId in c:
        print "Release already exists"
        return
    try:
        c.refreshMetaData(releaseId)
    except ws.ResourceNotFoundError as e:
        print "Release not found"
        return

    ed = ExtraData(releaseId)
    try:
        ed.load()
    except IOError as e:
        "Doesn't matter"
    ed.addDate()
    ed.save()

def shellBarcodeSearch():
    global c
    print "Enter barcode: ",
    barCode = getInput()
    for releaseId in c.barCodeMap[barCode]:
        print c.formatDiscInfo(releaseId)

def shellDelete():
    global c
    print "Enter release ID to delete: ",
    releaseId = getReleaseId(getInput())
    c.deleteRelease(releaseId)

def shellCheck():
    global c
    print "Running checks..."
    c.checkReleases()
    print "DONE"

def shellLend():
    global c
    releaseId = shellSearch()
    if not releaseId:
        return
    ed = ExtraData(releaseId)
    try:
        ed.load()
        print str(ed)
    except IOError as e:
        pass

    print "Borrower (leave empty to return): ",
    borrower = getInput()
    if not borrower:
        borrower = '[returned]'
    print "Lend date (leave empty for today): ",
    date = getInput()
    ed.addLend(borrower, date)
    ed.save()
    

shellCommands = {
    'h' : (None, 'this help'),
    'q' : (None, 'quit'),
    'e' : (shellEditExtra, 'edit extra data'),
    's' : (shellSearch, 'search for releases'),
    'r' : (shellRefresh, 'refresh XML metadata from musicbrainz'),
    't' : (shellHtml, 'write hTml'),
    'c' : (shellChange, 'change release'),
    'a' : (shellAdd, 'add release'),
    'l' : (shellReload, 'reLoad database from disk'),
    'b' : (shellBarcodeSearch, 'barcode search'),
    'd' : (shellDelete, 'delete release'),
    'k' : (shellCheck, 'check releases'),
    'n' : (shellLend, 'leNd (checkout) release'),
    }



def commandShell():
    global c
    while (True):
        print "Enter command ('h' for help): ",
        input = getInput().lower()

        if not input or input.startswith('q'):
            break

        if (input.startswith('h')):
            print "\r",
            #for letter, descr in shellCommands.items():
            for letter in sorted(shellCommands.keys()):
                print letter + " : " + shellCommands[letter][1]

        elif input[0] in shellCommands.keys():
            print shellCommands[input[0]][1]
            # Call the function
            (shellCommands[input[0]][0])()

        else:
            print "Invalid command"


if __name__ == "__main__":
    if len(sys.argv) > 1:
        search_terms = sys.argv
        del search_terms[0]
        c.search(' '.join(search_terms))
    else:
        c.report()

    commandShell()
