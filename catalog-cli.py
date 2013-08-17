#!/usr/bin/python

from mbcatalog.catalog import *
from mbcatalog.extradata import *
import os, shutil

c = Catalog()
c.load()

def getInput():
    return sys.stdin.readline().strip()

def interactiveSort(c):
    while(True):
        print "Enter search terms: ",
        input = getInput()
        if input:
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
                        break
                    except ValueError as e:
                        print e, "try again"
                    except IndexError as e:
                        print e, "try again"

            elif len(matches) == 1:
                c.getSortNeighbors(matches[0], matchFormat=True)
            else:
                print "No matches."
        else:
            break

def commandShell():
    global c
    while (True):
        print "Enter command ('h' for help): ",
        input = getInput().lower()

        if not input or input.startswith('q'):
            break

        if (input.startswith('h')):
            print "\re : edit extra data"
            print "s : search for releases"
            print "h : this help"
            print "r : refresh"
            print "t : hTml"
            print "c : change release"
            print "a : add release"
            print "l : reLoad"
            print "b : Barcode search"
            print "d : Delete release"
            print "k : Check releases"
            print "q : quit"

        elif (input.startswith('s')):
            interactiveSort(c)

        elif (input.startswith('l')):
            print "Reloading database...",
            c.load()
            print "DONE"

        elif (input.startswith('e')):
            print "Edit extra data"
            print "Enter release ID: ",
            releaseId = getReleaseId(getInput())
            if releaseId not in c.releaseIndex:
                print "Release not found"
                continue
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

        elif (input.startswith('r')):
            print "Refresh Release"
            print "Enter release ID [a for all]: ",
            releaseId = getReleaseId(getInput())
            if releaseId == "a":
                c.refreshAllMetaData(60*60)
            elif releaseId not in c.releaseIndex:
                print "Release not found"
                continue
            else:
                c.refreshMetaData(releaseId, olderThan=60)

        elif (input.startswith('c')):
            print "Change Release"
            print "Enter release ID: ",
            releaseId = getReleaseId(getInput())
            if releaseId not in c.releaseIndex:
                print "Release not found"
                continue
            print "Enter new release ID: ",
            newReleaseId = getInput()
            c.renameRelease(releaseId, newReleaseId)

        elif (input.startswith('t')):
            print "Make HTML"
            c = Catalog()
            c.load()
            c.makeHtml()
            shutil.copy('catalog.html', '../Public/catalog.html')

        elif (input.startswith('a')):
            print "Enter release ID: ",
            releaseId = getReleaseId(getInput())
            if not releaseId:
                print "No input"
                continue
            if releaseId in c.releaseIndex:
                print "Release already exists"
                continue
            try:
                c.refreshMetaData(releaseId)
            except ws.ResourceNotFoundError as e:
                print "Release not found"
                continue

            ed = ExtraData(releaseId)
            try:
                ed.load()
            except IOError as e:
                "Doesn't matter"
            ed.addDate()
            ed.save()

        elif (input.startswith('b')):
            print "Enter barcode: ",
            barCode = getInput()
            for releaseId in c.barCodeMap[barCode]:
                print c.formatDiscInfo(releaseId)

        elif (input.startswith('d')):
            print "Enter release ID to delete: ",
            releaseId = getReleaseId(getInput())
            c.deleteRelease(releaseId)

        elif (input.startswith('k')):
            print "Running checks..."
            c.checkReleases()
            print "DONE"

if __name__ == "__main__":
    if len(sys.argv) > 1:
        search_terms = sys.argv
        del search_terms[0]
        c.search(' '.join(search_terms))
    else:
        c.report()

    commandShell()
