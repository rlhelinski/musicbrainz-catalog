#!/usr/bin/python

from catalog import *

c = Catalog()
c.load()

if len(sys.argv) > 1:
	search_terms = sys.argv
	del search_terms[0]
	c.search(' '.join(search_terms))
else:
	c.report()

# Examples
def interactiveSort(c):
	while(True):
		print "Enter search terms: ",
		input = sys.stdin.readline().strip()
		if input:
			matches = list(c._search(input))
			if len(matches) > 1:
				print len(matches), "matches found:"
				for i, match in enumerate(matches):
					print i, c.formatDiscInfo(match)
				print "Select a match: ",
				index = int(sys.stdin.readline().strip())
				c.getSortNeighbors(matches[index])
			elif len(matches) == 1:
				c.getSortNeighbors(matches[0])
			else:
				print "No matches."
		else:
			break
interactiveSort(c)

