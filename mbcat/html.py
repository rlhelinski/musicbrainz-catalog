from __future__ import unicode_literals
import logging
_log = logging.getLogger("mbcat")
import jinja2
import datetime
from . import dialogs
from . import formats
from . import catalog
from . import amazonservices

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

        self.numer = 0
        # There's no way to update the progress during Jinja2's template
        # rendering, so just set the denominator to zero to cause pulsing.
        self.denom = 0

        def fmt(s):
            return s.encode('ascii', 'xmlcharrefreplace').decode()

        templateLoader = jinja2.FileSystemLoader(searchpath='templates')
        templateEnv = jinja2.Environment(
                loader=templateLoader,
                trim_blocks=True, lstrip_blocks=True,
                extensions=['jinja2.ext.autoescape'],
                autoescape='html',
                )
        templateEnv.globals['catalog'] = self.catalog
        templateEnv.globals['incr'] = self.incr
        templateEnv.globals['recLengthAsString'] = \
                catalog.recLengthAsString
        templateEnv.globals['getAsinProductUrl'] = \
                amazonservices.getAsinProductUrl
        template = templateEnv.get_template('catalog.jinja')

        formatList = sorted(self.catalog.getFormats(),
                key=lambda s: formats.getFormatObj(s))

        templateVars = {
                'title' : 'MusicBrainz Catalog',
                'date' : str(datetime.datetime.now()),
                'releaseCnt' : len(self.catalog),
                'formatsBySize' : formatList,
                'formatCnts' : {k: self.catalog.getReleaseCountByFormat(k) \
                        for k in formatList},
                'formatIds' : {k: self.catalog.getReleaseIdsByFormat(k) \
                        for k in formatList},
                'includeDetails' : False,
                }

        outputText = template.render( templateVars )
        htf.write(outputText)
        return

