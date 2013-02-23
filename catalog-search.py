#!/usr/bin/python

from catalog import *
from extradata import *

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
				print "Select a match: ",
				index = int(getInput())
				c.getSortNeighbors(matches[index])
			elif len(matches) == 1:
				c.getSortNeighbors(matches[0])
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
while (True):
	print "Enter command ('h' for help): ",
	input = getInput().lower()

	if not input:
		break

	if (input.startswith('h')):
		print "e : edit extra data"
		print "s : search for releases"
		print "h : this help"
	elif (input.startswith('s')):
		interactiveSort(c)
	elif (input.startswith('e')):
		print "Enter release ID: ",
		releaseId = getInput()
		if releaseId not in c.releaseIndex:
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

