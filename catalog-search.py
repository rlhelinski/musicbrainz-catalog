#!/usr/bin/python

from catalog import *
from extradata import *
import os, shutil

c = Catalog()
c.load()

def getInput():
	return sys.stdin.readline().strip()

# Examples
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

if len(sys.argv) > 1:
	search_terms = sys.argv
	del search_terms[0]
	c.search(' '.join(search_terms))
else:
	c.report()

# Command Shell
def commandShell():
	while (True):
		print "Enter command ('h' for help): ",
		input = getInput().lower()

		if not input:
			break

		if (input.startswith('h')):
			print "e : edit extra data"
			print "s : search for releases"
			print "h : this help"
			print "r : refresh"
			print "t : hTml"
			print "c : change release"
			print "a : add release"
			print "l : reLoad"
			print "b : Barcode search"
		elif (input.startswith('s')):
			interactiveSort(c)
		elif (input.startswith('l')):
			print "Reloading database...", 
			c.load()
			print "DONE"
		elif (input.startswith('e')):
			print "Edit extra data"
			print "Enter release ID: ",
			releaseId = getInput()
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
			releaseId = getInput()
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
			releaseId = getInput()
			if releaseId not in c.releaseIndex:
				print "Release not found"
				continue
			print "Enter new release ID: ",
			newReleaseId = getInput()
			os.rename(os.path.join('release-id', releaseId),
				os.path.join('release-id', newReleaseId) )
			c.load()
				
			c.refreshMetaData(newReleaseId, olderThan=60)
		elif (input.startswith('t')):
			print "Make HTML"
			os.system("python makeHtml.py")
			shutil.copy('catalog.html', '../Public/catalog.html')
		elif (input.startswith('a')):
			print "Enter release ID: ",
			releaseId = getInput()
			#if releaseId.startswith("http://musicbrainz.org/release/"):
				# TODO this should be on in refreshMetaData()
				#releaseId = releaseId.replace("http://musicbrainz.org/release/", "")
			if releaseId in c.releaseIndex:
				print "Release already exists"
				continue
			c.refreshMetaData(releaseId)
			
		elif (input.startswith('b')):
			print "Enter barcode: ",
			barCode = getInput()
			for releaseId in c.barCodeMap[barCode]:
				print c.formatDiscInfo(releaseId)
		elif (input.startswith('d')):
			print "Enter release ID to delete: ",
			releaseId = getInput()
			
commandShell()
