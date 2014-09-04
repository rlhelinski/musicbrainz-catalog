
class Html(object):
    def __init__(self, catalog):
        self.catalog = catalog

    def writeFile(fileName=None, pbar=None):
        _log.info('Writing HTML to \'%s\'' % fileName)
        with open(fileName, 'wt') as htf:
            self.render(htf, pbar)

    def render(self, htf=None, pbar=None):
        """
        Write HTML representing the catalog to a file
        """

        def fmt(s):
            return s.encode('ascii', 'xmlcharrefreplace').decode()

        if pbar:
            pbar.maxval=len(self)
            pbar.start()

        # TODO need a more extensible solution for replacing symbols in this
        # template file
        with open ('mbcat/catalog_html.template') as template_file:
            htf.write(template_file.read())

        formatsBySize = sorted(self.catalog.getFormats(),
                key=lambda s: mbcat.formats.getFormatObj(s))

        htf.write('<a name="top">\n')
        htf.write('<div id="toc">\n')
        htf.write('<div id="toctitle">\n')
        htf.write('<h2>Contents</h2>\n')
        htf.write('<span class="toctoggle">&nbsp;[<a href="#" class="internal"'
                ' id="togglelink">hide</a>]&nbsp;</span>\n</div>\n')
        htf.write('<ul>\n')
        for releaseType in formatsBySize:
            htf.write('\t<li><a href="#'+releaseType+'">'+\
                releaseType+'</a></li>\n')
        htf.write('</ul>\n')
        htf.write('</div>\n')

        for releaseType in formatsBySize:
            sortedList = self.catalog.getSortedList(
                    mbcat.formats.getFormatObj(releaseType).__class__)
            if len(sortedList) == 0:
                continue
            htf.write("<h2><a name=\""+str(releaseType)+"\">" + \
                    str(releaseType) + (" (%d Releases)" %
            len(sortedList)) + " <a href=\"#top\">top</a></h2>\n")

            htf.write("<table class=\"formattable\">\n")
            mainCols = ['Artist',
                'Release Title',
                'Date',
                'Country',
                'Label',
                'Catalog #',
                'Barcode',
                'ASIN',
                ]
            htf.write('<tr>\n' + \
                '\n'.join(['<th>'+name+'</th>' for name in mainCols]) +\
                '\n</tr>\n')

            for (releaseId, releaseSortStr) in sortedList:
                rel = self.catalog.getRelease(releaseId)

                if pbar:
                    pbar.update(pbar.currval + 1)

                #coverartUrl = mbcat.amazonservices.getAsinImageUrl(rel.asin,
                #        mbcat.amazonservices.AMAZON_SERVER["amazon.com"], 'S')
                # Refer to local copy instead
                imgPath = self.catalog._getCoverArtPath(releaseId)
                coverartUrl = imgPath if os.path.isfile(imgPath) else None

                htf.write("<tr class=\"releaserow\">\n")
                htf.write("<td>" + ''.join( [\
                    credit if type(credit)==str else \
                    "<a href=\""+self.catalog.artistUrl+credit['artist']['id']+"\">"+\
                    fmt(credit['artist']['name'])+\
                    "</a>" for credit in rel['artist-credit'] ] ) + "</td>\n")
                htf.write("<td><a href=\""+self.catalog.releaseUrl+rel['id']+"\"" + \
                    ">"+fmt(rel['title'])\
                    +(' (%s)' % fmt(rel['disambiguation']) \
                        if 'disambiguation' in rel and rel['disambiguation'] \
                        else '')\
                    + "</a></td>\n")
                htf.write("<td>"+(fmt(rel['date']) if 'date' in rel else '') +\
                        "</td>\n")
                htf.write("<td>"+(fmt(rel['country']) \
                    if 'country' in rel else '')+"</td>\n")
                htf.write("<td>"+', '.join([\
                    "<a href=\""+self.catalog.labelUrl+info['label']['id']+"\">"+\
                    fmt(info['label']['name'])+\
                    "</a>" if 'label' in info else '' \
                    for info in rel['label-info-list']])+"</td>\n")
                # TODO handle empty strings here (remove from this list before
                # joining)
                htf.write("<td>"+', '.join([\
                    fmt(info['catalog-number']) if \
                    'catalog-number' in info else '' \
                    for info in rel['label-info-list']])+"</td>\n")
                htf.write("<td>"+\
                    ('' if 'barcode' not in rel else \
                    rel['barcode'] if rel['barcode'] else
                    '[none]')+"</td>\n")
                htf.write("<td>"+("<a href=\"" + \
                    mbcat.amazonservices.getAsinProductUrl(rel['asin']) + \
                    "\">" + rel['asin'] + "</a>" if 'asin' in rel else '') + \
                    "</td>\n")
                htf.write("</tr>\n")
                htf.write("<tr class=\"detailrow\">\n")
                htf.write("<td colspan=\""+str(len(mainCols))+"\">\n")
                htf.write("<div class=\"togglediv\">\n")
                htf.write('<table class="releasedetail">\n')
                htf.write('<tr>\n')
                detailCols = [
                    'Cover Art',
                    'Track List',
                    'Digital Paths',
                    'Date Added',
                    'Format(s)',
                    ]
                for name in detailCols:
                    htf.write('<th>'+fmt(name)+'</th>\n')
                htf.write('</tr>\n<tr>\n')
                htf.write('<td>'+('<img class="coverart" src="'+ coverartUrl +\
                        '">' if coverartUrl else '')+'</td>\n')
                htf.write('<td>\n')
                htf.write('<table class="tracklist">\n')
                for medium in rel['medium-list']:
                    for track in medium['track-list']:
                        rec = track['recording']
                        length = mbcat.Catalog.formatRecordingLength(
                            rec['length'] if 'length' in rec else None)
                        htf.write('<tr><td class="time">'+
                            fmt(rec['title']) + '</td><td>' + length + \
                            '</td></tr>\n')
                htf.write('</table>\n</td>\n')
                htf.write('<td>\n<table class="pathlist">'+\
                    ''.join([\
                        ('<tr><td><a href="'+fmt(path)+'">'+fmt(path)+\
                            '</a></td></tr>\n')\
                        for path in self.catalog.getDigitalPaths(releaseId)])+\
                    '</table>\n</td>\n')
                htf.write(\
                    "<td>"+(datetime.fromtimestamp( \
                        self.catalog.getAddedDates(releaseId)[0] \
                        ).strftime('%Y-%m-%d') if \
                    len(self.catalog.getAddedDates(releaseId)) else '')+"</td>\n")
                htf.write("<td>"+' + '.join([(medium['format'] \
                        if 'format' in medium else '(unknown)') \
                        for medium in rel['medium-list']])+"</td>\n")

                htf.write('</tr>\n')
                htf.write("</table>\n</div>\n</td>\n</tr>\n")

            htf.write("</table>")

        htf.write("<p>%d releases</p>" % len(self))

        # TODO this will become part of the template
        htf.write("""</body>
</html>""")
        htf.close()

        if pbar:
            pbar.finish()

