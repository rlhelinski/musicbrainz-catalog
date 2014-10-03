import logging
_log = logging.getLogger("mbcat")
import jinja2
import datetime
from . import dialogs
from . import formats

class HtmlWriter(dialogs.ThreadedTask):
    def __init__(self, catalog, htmlFileName='catalog.html'):
        dialogs.ThreadedTask.__init__(self, 0)
        self.catalog = catalog
        self.htmlFileName = htmlFileName

    def run(self):
        self.writeFile(self.htmlFileName)

    def writeFile(self, fileName=None):
        _log.info('Writing HTML to \'%s\'' % fileName)
        with open(fileName, 'wt') as htf:
            self.render(htf)

    def render(self, htf=None):
        """
        Write HTML representing the catalog to a file
        """

        self.numer = 0; self.denom=len(self.catalog)

        def fmt(s):
            return s.encode('ascii', 'xmlcharrefreplace').decode()

        templateLoader = jinja2.FileSystemLoader(searchpath='templates')
        templateEnv = jinja2.Environment(
                loader=templateLoader,
                autoescape='html',
                extensions=['jinja2.ext.autoescape'])
        templateEnv.globals['catalog'] = self.catalog
        template = templateEnv.get_template('catalog.jinja')

        formatList = sorted(self.catalog.getFormats(),
                key=lambda s: formats.getFormatObj(s))

        templateVars = {
                'title' : 'MusicBrainz Catalog',
                'date' : str(datetime.datetime.now()),
                'releaseIds' : self.catalog.getReleaseIds(),
                'formatsBySize' : formatList,
                'formatCnts' : {k: self.catalog.getReleaseCountByFormat(k) \
                        for k in formatList},
                'formatIds' : {k: self.catalog.getReleaseIdsByFormat(k) \
                        for k in formatList},
                }

        outputText = template.render( templateVars )
        htf.write(outputText)
        return
################################################################################


        for releaseType in formatsBySize:
            sortedList = self.catalog.getSortedList(
                    formats.getFormatObj(releaseType).__class__)
            if len(sortedList) == 0:
                continue

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

                #coverartUrl = amazonservices.getAsinImageUrl(rel.asin,
                #        amazonservices.AMAZON_SERVER["amazon.com"], 'S')
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
                    amazonservices.getAsinProductUrl(rel['asin']) + \
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
                        length = formatRecordingLength(
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

