#!/usr/bin/env python
#
#

from __future__ import print_function
import logging
logging.basicConfig(level=logging.INFO)
import pygtk
pygtk.require('2.0')
import gtk
import pango
import mbcat
import mbcat.barcode # why does this not automatically import?
import musicbrainzngs as mb
import argparse
import time
import webbrowser

_log = logging.getLogger("mbcat")

# Thanks http://stackoverflow.com/a/8907574/3098007
def ReleaseIDEntry(parent, message, default='', textVisible=True):
    """
    Display a dialog with a text entry.
    Returns the text, or None if canceled.
    """
    d = gtk.MessageDialog(parent,
            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
            gtk.MESSAGE_QUESTION,
            gtk.BUTTONS_OK_CANCEL,
            message)
    entry = gtk.Entry()
    entry.set_visibility(textVisible)
    entry.set_text(default)
    entry.set_width_chars(36)
    entry.connect('activate', lambda _: d.response(gtk.RESPONSE_OK))
    entry.show()
    d.vbox.pack_end(entry)
    d.set_default_response(gtk.RESPONSE_OK)

    r = d.run()
    # have to get the text before we destroy the gtk.Entry
    text = entry.get_text().decode('utf8')
    d.destroy()
    if r == gtk.RESPONSE_OK:
        return text
    else:
        return None

def ErrorDialog(parent, message, type=gtk.MESSAGE_ERROR):
    _log.error(message)
    d = gtk.MessageDialog(parent,
        gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
        type,
        buttons=gtk.BUTTONS_OK)
    d.set_markup(message)
    d.run()
    d.destroy()

def ReleaseSelectDialog(parent,
        catalog,
        message='Choose a release',
        releaseIdList=[],
        releaseDictList=[]
        ):
    # TODO releaseDictList argument should support metadata returned from a
    # webservice query
    d = gtk.MessageDialog(parent,
            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
            gtk.MESSAGE_QUESTION,
            gtk.BUTTONS_OK_CANCEL,
            message)
    d.set_resizable(True)
    sw = gtk.ScrolledWindow()
    sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
    d.set_size_request(400, 300)
    tv = gtk.TreeView()
    artistCell = gtk.CellRendererText()
    artistCell.set_property('xalign', 0)
    artistCell.set_property('ellipsize', pango.ELLIPSIZE_END)
    artistCell.set_property('width-chars', 20)
    artistCol = gtk.TreeViewColumn('Artist', artistCell)
    artistCol.add_attribute(artistCell, 'text', 1)
    artistCol.set_resizable(True)
    tv.append_column(artistCol)

    titleCell = gtk.CellRendererText()
    titleCell.set_property('xalign', 0)
    titleCell.set_property('ellipsize', pango.ELLIPSIZE_END)
    titleCell.set_property('width-chars', 30)
    titleCol = gtk.TreeViewColumn('Title', titleCell)
    titleCol.add_attribute(titleCell, 'text', 2)
    tv.append_column(titleCol)

    formatCell = gtk.CellRendererText()
    formatCell.set_property('xalign', 0)
    formatCell.set_property('ellipsize', pango.ELLIPSIZE_END)
    formatCell.set_property('width-chars', -1)
    formatCol = gtk.TreeViewColumn('Format', formatCell)
    formatCol.add_attribute(formatCell, 'text', 3)
    tv.append_column(formatCol)

    # make the list store
    releaseListStore = gtk.ListStore(str, str, str, str)
    for releaseId in releaseIdList:
        releaseListStore.append((
            #release['id'],
            #mbcat.catalog.getArtistSortPhrase(release),
            #release['title']))
            releaseId,
            catalog.getReleaseArtist(releaseId),
            catalog.getReleaseTitle(releaseId),
            catalog.getReleaseFormat(releaseId)
            ))
    tv.set_model(releaseListStore)
    tv.expand_all()

    tv.show_all()
    sw.add(tv)
    sw.show()
    d.vbox.pack_end(sw)
    d.set_default_response(gtk.RESPONSE_OK)

    r = d.run()
    model, it = tv.get_selection().get_selected()
    if r == gtk.RESPONSE_OK and it:
        selection = model.get_value(it, 0)
    else:
        selection = None
    d.destroy()
    return selection

def TrackSelectDialog(parent,
        catalog,
        message='Choose a track',
        trackIdList=[],
        ):
    d = gtk.MessageDialog(parent,
            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
            gtk.MESSAGE_QUESTION,
            gtk.BUTTONS_OK_CANCEL,
            message)
    d.set_resizable(True)
    sw = gtk.ScrolledWindow()
    sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
    d.set_size_request(400, 300)
    tv = gtk.TreeView()
    titleCell = gtk.CellRendererText()
    titleCell.set_property('xalign', 0)
    titleCell.set_property('ellipsize', pango.ELLIPSIZE_END)
    titleCell.set_property('width-chars', 30)
    titleCol = gtk.TreeViewColumn('Title', titleCell)
    titleCol.add_attribute(titleCell, 'text', 1)
    titleCol.set_resizable(True)
    tv.append_column(titleCol)

    lengthCell = gtk.CellRendererText()
    lengthCell.set_property('xalign', 0)
    lengthCell.set_property('ellipsize', pango.ELLIPSIZE_END)
    lengthCell.set_property('width-chars', -1)
    lengthCol = gtk.TreeViewColumn('Length', lengthCell)
    lengthCol.add_attribute(lengthCell, 'text', 2)
    tv.append_column(lengthCol)

    releaseCell = gtk.CellRendererText()
    releaseCell.set_property('xalign', 0)
    releaseCell.set_property('ellipsize', pango.ELLIPSIZE_END)
    releaseCell.set_property('width-chars', 30)
    releaseCol = gtk.TreeViewColumn('Appears on', releaseCell)
    releaseCol.add_attribute(releaseCell, 'text', 3)
    tv.append_column(releaseCol)

    artistCell = gtk.CellRendererText()
    artistCell.set_property('xalign', 0)
    artistCell.set_property('ellipsize', pango.ELLIPSIZE_END)
    artistCell.set_property('width-chars', 20)
    artistCol = gtk.TreeViewColumn('Artist', artistCell)
    artistCol.add_attribute(artistCell, 'text', 4)
    tv.append_column(artistCol)

    # make the list store
    trackListStore = gtk.ListStore(str, str, str, str, str, str)
    for trackId in trackIdList:
        for releaseId in catalog.recordingGetReleases(trackId):
            trackListStore.append((
                trackId,
                catalog.getRecordingTitle(trackId),
                mbcat.catalog.recLengthAsString(
                    catalog.getRecordingLength(trackId)),
                catalog.getReleaseTitle(releaseId),
                # TODO this should be specific to the recording,
                # not the release
                catalog.getReleaseArtist(releaseId),
                releaseId
                ))
    tv.set_model(trackListStore)
    tv.expand_all()

    tv.show_all()
    sw.add(tv)
    sw.show()
    d.vbox.pack_end(sw)
    d.set_default_response(gtk.RESPONSE_OK)

    r = d.run()
    model, it = tv.get_selection().get_selected()
    if r == gtk.RESPONSE_OK and it:
        # use the releaseId in position 5
        selection = model.get_value(it, 5)
    else:
        selection = None
    d.destroy()
    return selection

def ReleaseSearchDialog(parent,
        catalog,
        message='Enter search terms or release ID',
        default=''):
    entry = ReleaseIDEntry(parent, message, default)
    if not entry:
        return
    if len(entry) == 36:
        releaseId = mbcat.utils.getReleaseIdFromInput(input)
        return releaseId
    # else, assume that a search query was entered
    matches = list(catalog._search(entry))
    if len(matches) > 1:
        # Have to ask the user which release they mean
        return ReleaseSelectDialog(parent, catalog, releaseIdList=matches)
    elif len(matches) == 1:
        return matches[0]
    else:
        ErrorDialog(parent, 'No matches found for "%s"' % entry)

def BarcodeSearchDialog(parent,
        catalog,
        message='Enter barcode (UPC):',
        default=''):
    entry = ReleaseIDEntry(parent, message, default)
    if not entry:
        return

    barCodes = mbcat.barcode.UPC(entry).variations()
    matches = set()
    for barCode in barCodes:
        try:
            for releaseId in catalog.barCodeLookup(barCode):
                matches.add(releaseId)
        except KeyError as e:
            pass
        else:
            found = True
    matches = list(matches)

    if len(matches) > 1:
        # Have to ask the user which release they mean
        return ReleaseSelectDialog(parent, catalog, releaseIdList=matches)
    elif len(matches) == 1:
        return matches[0]
    else:
        ErrorDialog(parent, 'No matches found for "%s"' % entry)

def TrackSearchDialog(parent,
        catalog,
        message='Enter search terms',
        default=''):
    entry = ReleaseIDEntry(parent, message, default)
    if not entry:
        return
    if len(entry) == 36:
        matches = [mbcat.utils.getReleaseIdFromInput(input)]
    else: # assume that a search query was entered
        matches = list(catalog._search(entry, table='trackwords',
            keycolumn='trackword'))
    if len(matches) > 1:
        # Have to ask the user which release they mean
        return TrackSelectDialog(parent, catalog, trackIdList=matches)
    elif len(matches) == 1:
        return matches[0]
    else:
        ErrorDialog(parent, 'No matches found for "%s"' % entry)

def RatingDialog(parent,
    message='Enter rating',
    default=None):
    d = gtk.MessageDialog(parent,
            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
            gtk.MESSAGE_QUESTION,
            gtk.BUTTONS_OK_CANCEL,
            message
            )
    combobox = gtk.combo_box_new_text()
    d.vbox.pack_end(combobox)
    combobox.append_text('None')
    combobox.append_text('1')
    combobox.append_text('2')
    combobox.append_text('3')
    combobox.append_text('4')
    combobox.append_text('5')
    combobox.set_active(default if default is not None else 0)
    combobox.show()
    d.set_default_response(gtk.RESPONSE_OK)

    r = d.run()
    model = combobox.get_model()
    index = combobox.get_active()
    text = model[index][0]
    d.destroy()
    if r == gtk.RESPONSE_OK and text != 'None':
        return text
    else:
        return None

def IntegerDialog(parent,
        message='Enter a number',
        default=0,
        lower=0,
        upper=1000):
    d = gtk.MessageDialog(parent,
            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
            gtk.MESSAGE_QUESTION,
            gtk.BUTTONS_OK_CANCEL,
            message)
    adjustment = gtk.Adjustment(
        value=1,
        lower=lower,
        upper=upper,
        step_incr=1)
    spinbutton = gtk.SpinButton(adjustment)
    spinbutton.set_value(default)
    spinbutton.show()
    d.vbox.pack_end(spinbutton)
    spinbutton.connect('activate', lambda _: d.response(gtk.RESPONSE_OK))
    d.set_default_response(gtk.RESPONSE_OK)

    r = d.run()
    val = spinbutton.get_value_as_int()
    d.destroy()
    if r == gtk.RESPONSE_OK:
        return val
    else:
        return None

def ConfirmDialog(parent, message, type=gtk.MESSAGE_QUESTION):
    d = gtk.MessageDialog(parent,
            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
            gtk.MESSAGE_QUESTION,
            gtk.BUTTONS_OK_CANCEL,
            message)
    d.set_default_response(gtk.RESPONSE_OK)

    r = d.run()
    d.destroy()
    return (r == gtk.RESPONSE_OK)

def TrackListDialog(parent, releaseDict):
    """
    Display a dialog with a list of tracks for a release.
    Example:
    TrackListDialog(gui.window,
        gui.catalog.getTrackList('1cd1d24c-1705-485c-ae6f-c53e7831b1e4'))
    """
    d = gtk.MessageDialog(parent,
            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
            gtk.MESSAGE_QUESTION,
            gtk.BUTTONS_OK_CANCEL,
            'Track List')
    d.set_resizable(True)
    sw = gtk.ScrolledWindow()
    sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
    d.set_size_request(400, 300)
    tv = gtk.TreeView()
    titleCell = gtk.CellRendererText()
    titleCell.set_property('xalign', 0)
    titleCell.set_property('ellipsize', pango.ELLIPSIZE_END)
    titleCell.set_property('width-chars', 40)
    titleCol = gtk.TreeViewColumn('Title', titleCell)
    titleCol.add_attribute(titleCell, 'text', 1)
    titleCol.set_resizable(True)
    tv.append_column(titleCol)
    lenCell = gtk.CellRendererText()
    lenCell.set_property('xalign', 1.0)
    lenCol = gtk.TreeViewColumn('Length', lenCell)
    lenCol.add_attribute(lenCell, 'text', 2)
    tv.append_column(lenCol)

    # make the list store
    trackTreeStore = gtk.TreeStore(str, str, str)
    for medium in releaseDict['medium-list']:
        parent = trackTreeStore.append(None, 
            ('',
            medium['format']+' '+medium['position'], 
            mbcat.catalog.recLengthAsString(
                mbcat.catalog.getMediumLen(medium)
                )))
        for track in medium['track-list']:
            trackTreeStore.append(parent,
                (track['recording']['id'],
                track['recording']['title'],
                mbcat.catalog.recLengthAsString(
                    track['recording']['length'] \
                    if 'length' in track['recording'] else None)))
    tv.set_model(trackTreeStore)
    tv.expand_all()

    tv.show_all()
    sw.add(tv)
    sw.show()
    d.vbox.pack_end(sw)
    d.set_default_response(gtk.RESPONSE_OK)

    r = d.run()
    d.destroy()

def GroupQueryResultsDialog(parent, catalog, queryResult):
    """
    Display a dialog with a list of tracks for a release.
    Example:
    TrackListDialog(gui.window,
        gui.catalog.getTrackList('1cd1d24c-1705-485c-ae6f-c53e7831b1e4'))
    """
    d = gtk.MessageDialog(parent,
            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
            gtk.MESSAGE_QUESTION,
            gtk.BUTTONS_OK_CANCEL,
            'Track List')
    d.set_resizable(True)
    sw = gtk.ScrolledWindow()
    sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
    d.set_size_request(400, 300)
    tv = gtk.TreeView()

    authorCell = gtk.CellRendererText()
    authorCell.set_property('xalign', 0)
    authorCell.set_property('ellipsize', pango.ELLIPSIZE_END)
    authorCell.set_property('width-chars', 20)
    authorCol = gtk.TreeViewColumn('Title', authorCell)
    authorCol.add_attribute(authorCell, 'text', 1)
    authorCol.set_resizable(True)
    tv.append_column(authorCol)

    titleCell = gtk.CellRendererText()
    titleCell.set_property('xalign', 0)
    titleCell.set_property('ellipsize', pango.ELLIPSIZE_END)
    titleCell.set_property('width-chars', 30)
    titleCol = gtk.TreeViewColumn('Title', titleCell)
    titleCol.add_attribute(titleCell, 'text', 2)
    titleCol.set_resizable(True)
    tv.append_column(titleCol)

    lenCell = gtk.CellRendererText()
    lenCell.set_property('xalign', 1.0)
    lenCol = gtk.TreeViewColumn('Releases', lenCell)
    lenCol.add_attribute(lenCell, 'text', 3)
    tv.append_column(lenCol)

    # make the list store
    resultListStore = gtk.ListStore(str, str, str, str)
    for group in queryResult['release-group-list']:
        resultListStore.append((
            group['id'],
            mbcat.catalog.formatQueryArtist(group),
            group['title'],
            '%d' % len(group['release-list'])
            ))
    tv.set_model(resultListStore)
    tv.expand_all()

    tv.show_all()
    sw.add(tv)
    sw.show()
    d.vbox.pack_end(sw)
    d.set_default_response(gtk.RESPONSE_OK)

    r = d.run()
    d.destroy()

def QueryResultsDialog(parent, catalog, queryResult):
    """
    Display a dialog with a list of tracks for a release.
    Example:
    TrackListDialog(gui.window,
        gui.catalog.getTrackList('1cd1d24c-1705-485c-ae6f-c53e7831b1e4'))
    """
    d = gtk.MessageDialog(parent,
            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
            gtk.MESSAGE_QUESTION,
            gtk.BUTTONS_OK_CANCEL,
            'Track List')
    d.set_resizable(True)
    sw = gtk.ScrolledWindow()
    sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
    d.set_size_request(400, 300)
    tv = gtk.TreeView()

    authorCell = gtk.CellRendererText()
    authorCell.set_property('xalign', 0)
    authorCell.set_property('ellipsize', pango.ELLIPSIZE_END)
    authorCell.set_property('width-chars', 20)
    authorCol = gtk.TreeViewColumn('Title', authorCell)
    authorCol.add_attribute(authorCell, 'text', 1)
    authorCol.set_resizable(True)
    tv.append_column(authorCol)

    titleCell = gtk.CellRendererText()
    titleCell.set_property('xalign', 0)
    titleCell.set_property('ellipsize', pango.ELLIPSIZE_END)
    titleCell.set_property('width-chars', 30)
    titleCol = gtk.TreeViewColumn('Title', titleCell)
    titleCol.add_attribute(titleCell, 'text', 2)
    titleCol.set_resizable(True)
    tv.append_column(titleCol)

    formatCell = gtk.CellRendererText()
    formatCell.set_property('xalign', 0)
    formatCell.set_property('ellipsize', pango.ELLIPSIZE_END)
    formatCell.set_property('width-chars', 30)
    formatCol = gtk.TreeViewColumn('Format', formatCell)
    formatCol.add_attribute(formatCell, 'text', 3)
    formatCol.set_resizable(True)
    tv.append_column(formatCol)

    formatCell = gtk.CellRendererText()
    formatCell.set_property('xalign', 0)
    formatCell.set_property('ellipsize', pango.ELLIPSIZE_END)
    formatCell.set_property('width-chars', 20)
    formatCol = gtk.TreeViewColumn('Label', formatCell)
    formatCol.add_attribute(formatCell, 'text', 4)
    formatCol.set_resizable(True)
    tv.append_column(formatCol)

    formatCell = gtk.CellRendererText()
    formatCell.set_property('xalign', 0)
    formatCell.set_property('ellipsize', pango.ELLIPSIZE_END)
    formatCell.set_property('width-chars', 20)
    formatCol = gtk.TreeViewColumn('Catalog #', formatCell)
    formatCol.add_attribute(formatCell, 'text', 5)
    formatCol.set_resizable(True)
    tv.append_column(formatCol)

    # make the list store
    resultListStore = gtk.ListStore(str, str, str, str, str, str)
    for release in queryResult['release-list']:
        resultListStore.append((
            release['id'],
            mbcat.catalog.formatQueryArtist(release),
            release['title'],
            mbcat.catalog.formatQueryMedia(release),
            mbcat.catalog.formatQueryRecordLabel(release),
            mbcat.catalog.formatQueryCatNo(release),
            ))
    tv.set_model(resultListStore)
    tv.expand_all()

    tv.show_all()
    sw.add(tv)
    sw.show()
    d.vbox.pack_end(sw)
    d.set_default_response(gtk.RESPONSE_OK)

    r = d.run()
    d.destroy()

def SelectCollectionDialog(parent, result):
    """
    Display a dialog with a list of tracks for a release.
    Example:
    TrackListDialog(gui.window,
        gui.catalog.getTrackList('1cd1d24c-1705-485c-ae6f-c53e7831b1e4'))
    """
    d = gtk.MessageDialog(parent,
            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
            gtk.MESSAGE_QUESTION,
            gtk.BUTTONS_OK_CANCEL,
            'Track List')
    d.set_resizable(True)
    sw = gtk.ScrolledWindow()
    sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
    d.set_size_request(400, 300)
    tv = gtk.TreeView()

    authorCell = gtk.CellRendererText()
    authorCell.set_property('xalign', 0)
    authorCell.set_property('ellipsize', pango.ELLIPSIZE_END)
    authorCell.set_property('width-chars', 30)
    authorCol = gtk.TreeViewColumn('Name', authorCell)
    authorCol.add_attribute(authorCell, 'text', 1)
    authorCol.set_resizable(True)
    tv.append_column(authorCol)

    titleCell = gtk.CellRendererText()
    titleCell.set_property('xalign', 0)
    titleCell.set_property('ellipsize', pango.ELLIPSIZE_END)
    titleCell.set_property('width-chars', 20)
    titleCol = gtk.TreeViewColumn('Editor', titleCell)
    titleCol.add_attribute(titleCell, 'text', 2)
    titleCol.set_resizable(True)
    tv.append_column(titleCol)

    # make the list store
    resultListStore = gtk.ListStore(str, str, str)
    for i, collection in enumerate(result['collection-list']):
        resultListStore.append((
            collection['id'],
            collection['name'],
            collection['editor']
            ))
    tv.set_model(resultListStore)
    tv.expand_all()

    tv.show_all()
    sw.add(tv)
    sw.show()
    d.vbox.pack_end(sw)
    d.set_default_response(gtk.RESPONSE_OK)

    r = d.run()
    model, it = tv.get_selection().get_selected()
    d.destroy()
    if r == gtk.RESPONSE_OK and it:
        return model.get_value(it, 0)
    else:
        return None

def TextEntry(parent, message, default=''):
    """
    Display a dialog with a text entry.
    Returns the text, or None if canceled.
    """
    d = gtk.MessageDialog(parent,
            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
            gtk.MESSAGE_QUESTION,
            gtk.BUTTONS_OK_CANCEL,
            message)
    d.set_resizable(True)
    sw = gtk.ScrolledWindow()
    sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
    textview = gtk.TextView()
    textbuffer = textview.get_buffer()
    sw.add(textview)
    textbuffer.set_text(default)
    textview.set_wrap_mode(gtk.WRAP_WORD)
    #entry.set_width_chars(80)
    sw.show()
    textview.show()
    d.vbox.pack_end(sw)
    d.set_default_response(gtk.RESPONSE_OK)

    r = d.run()
    # TODO is there any easier way to get the whole buffer?
    text = textbuffer.get_text(
        textbuffer.get_start_iter(), 
        textbuffer.get_end_iter()).decode('utf8')
    d.destroy()
    if r == gtk.RESPONSE_OK:
        return text
    else:
        return None

class MBCatGtk:
    """A GTK interface for managing a MusicBrainz Catalog"""
    __name__ = 'MusicBrainz Catalog GTK Gui'
    __version__ = '0.1'
    __copyright__ = 'Ryan Helinski'
    __website__ = 'https://github.com/rlhelinski/musicbrainz-catalog'

    columnNames = ['Artist', 'Release Title', 'Date', 'Country', 'Label',
        'Catalog #', 'Barcode', 'ASIN', 'Format']
    columnWidths = [30, 45, 16, 2, 37, 23, 16, 16, 16]
    numFields = ['Barcode', 'ASIN']

    formatNames = ['All', 'Digital', 'CD', '7" Vinyl', '12" Vinyl']
    formatLabels = ['_All', '_Digital', '_CD', '_7" Vinyl', '_12" Vinyl']

    maxAge = 60
    searchResultsLimit = 100

    # Default extensions.
    filePatterns = [
        # These are essentially the same
        ('sqlite3 files', '*.sqlite3'), # unambiguous
        ('sqlite files', '*.sqlite'), # might tempt to open with sqlite < 3
        ('db files', '*.db'), # not specific
        ]

    @staticmethod
    def getColumnWidth(i):
        sl = [self.releaseList[j][i] for j in range(len(self.releaseList))]
        sl = filter(None, sl)
        ll = [len(s) for s in sl]
        return int(numpy.mean(ll) + 3*numpy.std(ll))

    # This is a callback function. The data arguments are ignored
    # in this example. More on callbacks below.
    def hello(self, widget, data=None):
        print ("Hello World")

    def delete_event(self, widget, event, data=None):
        # If you return FALSE in the "delete_event" signal handler,
        # GTK will emit the "destroy" signal. Returning TRUE means
        # you don't want the window to be destroyed.
        # This is useful for popping up 'are you sure you want to quit?'
        # type dialogs.
        print ("delete event occurred")

        # Change FALSE to TRUE and the main window will not be destroyed
        # with a "delete_event".
        return False

    def destroy(self, widget, data=None):
        print ("destroy signal occurred")
        gtk.main_quit()

    def openAboutWindow(self, widget):
        about = gtk.AboutDialog()
        about.set_program_name(self.__name__)
        about.set_version(self.__version__)
        about.set_copyright(self.__copyright__)
        about.set_comments(self.__doc__)
        about.set_website(self.__website__)
        #about.set_logo(...)
        about.run()
        about.destroy()
        return

    def openDatabase(self, filename=None):
        if filename:
            self.catalog = mbcat.catalog.Catalog(
                dbPath=filename,
                cachePath=self.catalog.cachePath)
        try:
            self.makeListStore()
        except OperationalError as e:
            # This can happen if the database is using an old schema
            _log.error(e)
            _log.info('Trying to rebuild cache tables...')
            self.catalog.rebuildCacheTables()
            self.makeListStore()

        # Housekeeping
        self.menuCatalogSaveAsItem.set_sensitive(True)
        self.updateStatusBar()

    def copyAndOpenDatabase(self, filename):
        # Copy the database to the new location
        shutil.copy(self.catalog.dbPath, filename)
        # Open the new copy
        self.openDatabase(filename)

    def menuCatalogOpen(self, widget):
        # Ask the user where to store the new database
        dialog = gtk.FileChooserDialog(
            title='Choose file',
            action=gtk.FILE_CHOOSER_ACTION_OPEN,
            buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                gtk.STOCK_OPEN, gtk.RESPONSE_OK))

        dialog.set_default_response(gtk.RESPONSE_OK)

        for desc, pattern in self.filePatterns:
            filt = gtk.FileFilter()
            filt.set_name(desc)
            filt.add_pattern(pattern)
            dialog.add_filter(filt)

        response = dialog.run()
        if response != gtk.RESPONSE_OK:
            dialog.destroy()
            return

        filename = dialog.get_filename()
        dialog.destroy()

        self.openDatabase(filename)

    def menuCatalogSaveAs(self, widget):
        # Ask the user where to store the new database
        dialog = gtk.FileChooserDialog(
            title='Choose file',
            action=gtk.FILE_CHOOSER_ACTION_SAVE,
            buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                gtk.STOCK_SAVE, gtk.RESPONSE_OK))

        dialog.set_default_response(gtk.RESPONSE_OK)

        for desc, pattern in self.filePatterns:
            filt = gtk.FileFilter()
            filt.set_name(desc)
            filt.add_pattern(pattern)
            dialog.add_filter(filt)

        response = dialog.run()
        if response != gtk.RESPONSE_OK:
            dialog.destroy()
            return

        filename = dialog.get_filename()
        dialog.destroy()

        self.openDatabase(filename)

    def format_comment(self, column, cell, model, it, field):
        row = model.get_value(it, 0)
        cell.set_property('text', 'OK')

    def on_row_activate(self, treeview, path, column):
        model, it = treeview.get_selection().get_selected()
        relId = model.get_value(it, 0)
        webbrowser.open(self.catalog.releaseUrl + relId)

    def on_row_select(self, treeview):
        model, it = treeview.get_selection().get_selected()
        relId = model.get_value(it, 0)
        print (relId+' selected')

    def getSelection(self):
        """Returns the selected release ID or None"""
        model, it = self.treeview.get_selection().get_selected()
        if it:
            return model.get_value(it, 0)
        else:
            return None

    def getSelectedRow(self):
        """Returns the selected row index"""
        model, rows = self.treeview.get_selection().get_selected_rows()
        if rows:
            return rows[0][0]
        else:
            return None

    def setSelectedRow(self, row):
        """Selects and scrolls to a row in the TreeView"""
        actualRow = min(len(self.releaseList), row)
        self.treeview.get_selection().select_path(actualRow)
        self.treeview.scroll_to_cell(actualRow, use_align=True, row_align=0.5)

    def getReleaseRow(self, releaseID):
        def match_func(model, iter, data):
            column, key = data # data is a tuple containing column number, key
            value = model.get_value(iter, column)
            return value == key
        def search(model, iter, func, data):
            while iter:
                if func(model, iter, data):
                    return iter
                result = search(model, model.iter_children(iter), func, data)
                if result: return result
                iter = model.iter_next(iter)
            return None

        result_iter = search(self.releaseList,
                self.releaseList.iter_children(None),
                match_func, (0, releaseID))
        return self.releaseList.get_path(result_iter)[0]

    def toggleStatusBar(self, widget):
        if widget.active:
            self.statusbar.show()
        else:
            self.statusbar.hide()

    def updateStatusBar(self):
        self.statusbar.pop(self.context_id)
        msg = ('%d total releases, %d release words, %d track words, '+\
            'showing %d releases') % \
            (len(self.catalog), self.catalog.getWordCount(),
                self.catalog.getTrackWordCount(),
                len(self.releaseList))
        self.statusbar.push(self.context_id, msg)

    def selectFormat(self, action, current):
        text = self.formatNames[action.get_current_value()]
        if text != 'All':
            fmt = mbcat.formats.getFormatObj(text).name()
            #print ('Filtering formats: '+text+', '+fmt)
            self.filt = {'format': fmt}
        else:
            self.filt = {}
        self.makeListStore()
        self.updateStatusBar()

    def addRelease(self, widget):
        entry = ReleaseIDEntry(self.window, 'Enter Release ID')
        if not entry:
            return
        if entry in self.catalog:
            ErrorDialog(self.window, 'Release already exists')
            return
        try:
            self.catalog.addRelease(entry)
        except mb.ResponseError as e:
            ErrorDialog(self.window, str(e) + ". Bad release ID?")
            return

        _log.info("Added '%s'" % self.catalog.getRelease(entry)['title'])

        self.catalog.getCoverArt(entry)
        self.makeListStore()
        self.setSelectedRow(self.getReleaseRow(entry))

    def deleteRelease(self, widget):
        releaseId = self.getSelection()
        row = self.getSelectedRow()

        # TODO keep this? or just make the Delete menu item not sensitive
        # when there is no selection?
        if not releaseId:
            releaseId = ReleaseSearchDialog(self.window, self.catalog)
        if not releaseId or releaseId not in self.catalog:
            return

        relTitle = self.catalog.getRelease(releaseId)['title']
        response = ConfirmDialog(self.window,
            'Are you sure you wish to delete "%s"\nwith ID %s?' % \
                (relTitle, releaseId))
        if not response:
            return

        self.catalog.deleteRelease(releaseId)
        _log.info("Deleted '%s'" % relTitle)
        self.makeListStore()
        self.setSelectedRow(row)

    def switchRelease(self, widget):
        releaseId = self.getSelection()
        row = self.getSelectedRow()

        # Ask the user to specify a release
        if not releaseId:
            releaseId = ReleaseSearchDialog(self.window, self.catalog)
        if not releaseId or releaseId not in self.catalog:
            return

        relTitle = self.catalog.getRelease(releaseId)['title']
        newRelId = ReleaseIDEntry(self.window,
            'Enter release ID to replace %s\n"%s"' % (releaseId, relTitle))
        if newRelId in self.catalog:
            ErrorDialog(self.window, 'New release ID already exists')
            return

        self.catalog.renameRelease(releaseId, newRelId)
        newRelTitle = self.catalog.getRelease(newRelId)['title']

        if relTitle != newRelTitle:
            _log.info("Replaced '%s' with '%s'" % (relTitle, newRelTitle))
        else:
            _log.info("Replaced '%s'" % (relTitle))

        self.makeListStore()
        self.setSelectedRow(row)

    def getCoverArt(self, widget):
        releaseId = self.getSelection()
        self.catalog.getCoverArt(releaseId)

    def refreshRelease(self, widget):
        row = self.getSelectedRow()
        releaseId = self.getSelection()
        try:
            self.catalog.addRelease(releaseId, olderThan=self.maxAge)
        except mb.NetworkError as e:
            ErrorDialog(self.window, 'Network error, failed to refresh')
        else:
            self.makeListStore()
            self.setSelectedRow(row)

    def showTrackList(self, widget):
        releaseId = self.getSelection()
        TrackListDialog(self.window, self.catalog.getRelease(releaseId))

    def checkOut(self, widget):
        releaseId = self.getSelection()

        lendEvents = self.catalog.getLendEvents(releaseId)
        for event in lendEvents:
            _log.info(str(event) + '\n')

        borrower = ReleaseIDEntry(self.window, "Borrower (leave empty to return): ")
        if not borrower:
            return

        date = ReleaseIDEntry(self.window,
            "Lend date  (" + mbcat.dateFmtUsr + ") (leave empty for today): ")
        if not date:
            date = time.time()
        self.catalog.addLendEvent(releaseId,
            mbcat.extradata.CheckOutEvent(borrower, date))

    def checkIn(self, widget):
        releaseId = self.getSelection()

        lendEvents = self.catalog.getLendEvents(releaseId)
        if not lendEvents or not isinstance(lendEvents[-1],
            mbcat.extradata.CheckOutEvent):
            ErrorDialog(self.window, 'Release is not checked out.')
            return

        date = ReleaseIDEntry(self.window,
            "Return date (" + mbcat.dateFmtUsr +
            ") (leave empty for today): ")
        if not date:
            date = time.time()
        self.catalog.addLendEvent(releaseId,
            mbcat.extradata.CheckInEvent(date))

    def editComment(self, widget):
        releaseId = self.getSelection()
        oldcomment = self.catalog.getComment(releaseId)
        newcomment = TextEntry(self.window, 'Edit Release Comments', oldcomment if oldcomment is not None else '')
        if newcomment is not None:
            self.catalog.setComment(releaseId, newcomment)

    def changeCount(self, widget):
        releaseId = self.getSelection()
        newcount = IntegerDialog(self.window, 'Enter new copy count',
            self.catalog.getCopyCount(releaseId))
        if newcount is not None:
            self.catalog.setCopyCount(releaseId, newcount)

    def listen(self, widget):
        releaseId = self.getSelection()
        dateStr = TextEntry(self.window,
            'Enter listen date (' + mbcat.dateFmtUsr + ')',
            time.strftime(mbcat.dateFmtStr))
        if dateStr:
            date = float(time.strftime('%s',
                time.strptime(dateStr, mbcat.dateFmtStr)))
            self.catalog.addListenDate(releaseId, date)

    def rateRelease(self, widget):
        releaseId = self.getSelection()
        if not releaseId:
            return
        nr = RatingDialog(self.window, 
            default=self.catalog.getRating(releaseId))
        if not nr:
            return
        self.catalog.setRating(releaseId, nr)

    def searchBarcode(self, widget):
        releaseId = BarcodeSearchDialog(self.window, self.catalog)
        if not releaseId or releaseId not in self.catalog:
            return
        self.setSelectedRow(self.getReleaseRow(releaseId))

    def searchArtistTitle(self, widget):
        releaseId = ReleaseSearchDialog(self.window, self.catalog)
        if not releaseId or releaseId not in self.catalog:
            return
        self.setSelectedRow(self.getReleaseRow(releaseId))

    def searchTrack(self, widget):
        releaseId = TrackSearchDialog(self.window, self.catalog)
        if not releaseId or releaseId not in self.catalog:
            return
        self.setSelectedRow(self.getReleaseRow(releaseId))

    def webserviceReleaseGroup(self, widget):
        entry = ReleaseIDEntry(self.window, 'Enter release group search terms')
        if not entry:
            return
        results = mb.search_release_groups(releasegroup=entry,
             limit=self.searchResultsLimit)
        if not results:
            ErrorDialog(self.window, 'No results found for "%s"' % entry)
        GroupQueryResultsDialog(self.window, self.catalog, results)

    def webserviceRelease(self, widget):
        entry = ReleaseIDEntry(self.window, 'Enter release search terms')
        if not entry:
            return
        results = mb.search_releases(release=entry,
             limit=self.searchResultsLimit)
        if not results:
            ErrorDialog(self.window, 'No results found for "%s"' % entry)
        QueryResultsDialog(self.window, self.catalog, results)

    def webserviceBarcode(self, widget):
        entry = ReleaseIDEntry(self.window, 'Enter search barcode (UPC):')
        if not entry:
            return
        results = mb.search_releases(barcode=entry,
             limit=self.searchResultsLimit)
        if not results:
            ErrorDialog(self.window, 'No results found for "%s"' % entry)
        QueryResultsDialog(self.window, self.catalog, results)

    def webserviceSyncCollection(self, widget):
        """Synchronize with a musicbrainz collection (currently only pushes releases)."""
        if not self.catalog.prefs.username:
            username = ReleaseIDEntry('Enter username:')
            self.catalog.prefs.username = username
            self.catalog.prefs.save()
        else:
            username = self.catalog.prefs.username

        # Input the password.
        password = ReleaseIDEntry(self.window,
            "Password for '%s': " % username,
            textVisible=False)
        if not password:
            return

        # Call musicbrainzngs.auth() before making any API calls that
        # require authentication.
        mb.auth(username, password)

        result = mb.get_collections()
        collectionId = SelectCollectionDialog(self.window, result)

        self.catalog.syncCollection(collectionId)

    def createMenuBar(self, widget):
        # Menu bar
        mb = gtk.MenuBar()
        # Catalog (File) menu
        menu = gtk.Menu()
        menuitem = gtk.MenuItem("_Catalog")
        menuitem.set_submenu(menu)

        # Open
        submenuitem = gtk.ImageMenuItem(gtk.STOCK_OPEN, self.agr)
        # Note that this inherits the <Control>o accelerator
        submenuitem.connect('activate', self.menuCatalogOpen)
        menu.append(submenuitem)

        # Save As...
        submenuitem = gtk.ImageMenuItem(gtk.STOCK_SAVE_AS, self.agr)
        submenuitem.set_sensitive(False) # should be enabled when opened
        self.menuCatalogSaveAsItem = submenuitem
        key, mod = gtk.accelerator_parse('<Control>s')
        submenuitem.add_accelerator('activate', self.agr, key, mod,
            gtk.ACCEL_VISIBLE)
        submenuitem.connect('activate', self.menuCatalogSaveAs)
        menu.append(submenuitem)

        # Separator
        sep = gtk.SeparatorMenuItem()
        menu.append(sep)

        # Check
        submenuitem = gtk.MenuItem('Check')
        menu.append(submenuitem)

        # Rebuild
        submenuitem = gtk.MenuItem('Rebuild')
        menu.append(submenuitem)

        # Similar
        submenuitem = gtk.MenuItem('Similar')
        menu.append(submenuitem)

        # Separator
        sep = gtk.SeparatorMenuItem()
        menu.append(sep)

        # Quit
        submenuitem = gtk.ImageMenuItem(gtk.STOCK_QUIT, self.agr)
        key, mod = gtk.accelerator_parse('Q')
        submenuitem.add_accelerator('activate', self.agr, key, mod, 
            gtk.ACCEL_VISIBLE)
        submenuitem.connect('activate', self.destroy)
        menu.append(submenuitem)

        mb.append(menuitem)

        # View menu
        menu = gtk.Menu()
        menuitem = gtk.MenuItem("_View")
        menuitem.set_submenu(menu)

        ## Show Statusbar
        submenuitem = gtk.CheckMenuItem('Show Statusbar')
        submenuitem.set_active(True)
        submenuitem.connect('activate', self.toggleStatusBar)
        menu.append(submenuitem)

        ## Formats
        # TODO this should be dynamically generated after loading or changing
        # the database
        self.actiongroup = gtk.ActionGroup('FormatsGroup')

        self.actiongroup.add_actions([('Formats', None, '_Formats')])

        self.actiongroup.add_radio_actions([
            (name, None, label, None, None, i) \
            for i, [name, label] in enumerate(zip(self.formatNames, \
                self.formatLabels))
            ], 0, self.selectFormat)

        submenuitem = self.actiongroup.get_action('Formats').create_menu_item()
        menu.append(submenuitem)
        subsubmenu = gtk.Menu()
        submenuitem.set_submenu(subsubmenu)

        for name in self.formatNames:
            action = self.actiongroup.get_action(name)
            subsubmenu.append(action.create_menu_item())

        mb.append(menuitem)

        # Release menu
        menu = gtk.Menu()
        menuitem = gtk.MenuItem("_Release")
        menuitem.set_submenu(menu)

        ## Add
        submenuitem = gtk.ImageMenuItem(gtk.STOCK_ADD)
        submenuitem.get_children()[0].set_label('_Add')
        submenuitem.connect('activate', self.addRelease)
        menu.append(submenuitem)

        ## Delete
        submenuitem = gtk.ImageMenuItem(gtk.STOCK_REMOVE)
        submenuitem.get_children()[0].set_label('_Delete')
        submenuitem.connect('activate', self.deleteRelease)
        menu.append(submenuitem)

        ## Switch
        submenuitem = gtk.MenuItem('_Switch')
        submenuitem.connect('activate', self.switchRelease)
        menu.append(submenuitem)

        ## Cover Art
        submenuitem = gtk.MenuItem('Get Cover Art')
        submenuitem.connect('activate', self.getCoverArt)
        menu.append(submenuitem)

        ## Refresh
        submenuitem = gtk.MenuItem('_Refresh')
        submenuitem.connect('activate', self.refreshRelease)
        menu.append(submenuitem)

        ## Track List
        submenuitem = gtk.MenuItem('Track List')
        submenuitem.connect('activate', self.showTrackList)
        menu.append(submenuitem)

        ## Separator
        sep = gtk.SeparatorMenuItem()
        menu.append(sep)

        ## Check Out
        submenuitem = gtk.MenuItem('Check Out')
        submenuitem.connect('activate', self.checkOut)
        menu.append(submenuitem)

        ## Check In
        submenuitem = gtk.MenuItem('Check In')
        submenuitem.connect('activate', self.checkIn)
        menu.append(submenuitem)

        ## Comment
        submenuitem = gtk.MenuItem('Comment')
        submenuitem.connect('activate', self.editComment)
        menu.append(submenuitem)

        ## Count
        submenuitem = gtk.MenuItem('Count')
        submenuitem.connect('activate', self.changeCount)
        menu.append(submenuitem)

        ## Listen
        submenuitem = gtk.MenuItem('Listen')
        submenuitem.connect('activate', self.listen)
        menu.append(submenuitem)

        ## Purchase Info
        submenuitem = gtk.MenuItem('Purchase Info')
        menu.append(submenuitem)

        ## Rate
        submenuitem = gtk.MenuItem('_Rate')
        submenuitem.connect('activate', self.rateRelease)
        menu.append(submenuitem)

        mb.append(menuitem)

        # Search menu
        menu = gtk.Menu()
        menuitem = gtk.MenuItem("_Search")
        menuitem.set_submenu(menu)
        mb.append(menuitem)

        ## Barcode (UPC)
        submenuitem = gtk.MenuItem('Barcode (UPC)')
        submenuitem.connect('activate', self.searchBarcode)
        menu.append(submenuitem)

        ## Artist/Title
        submenuitem = gtk.MenuItem('Artist/Title')
        submenuitem.connect('activate', self.searchArtistTitle)
        menu.append(submenuitem)

        ## Track
        submenuitem = gtk.MenuItem('Track')
        submenuitem.connect('activate', self.searchTrack)
        menu.append(submenuitem)

        # Webservice menu
        menu = gtk.Menu()
        menuitem = gtk.MenuItem("Webservice")
        menuitem.set_submenu(menu)
        mb.append(menuitem)

        ## Release Group Search
        submenuitem = gtk.MenuItem('Release Group')
        submenuitem.connect('activate', self.webserviceReleaseGroup)
        menu.append(submenuitem)

        ## Release Search
        submenuitem = gtk.MenuItem('Release')
        submenuitem.connect('activate', self.webserviceRelease)
        menu.append(submenuitem)

        ## Barcode Search
        submenuitem = gtk.MenuItem('Barcode (UPC)')
        submenuitem.connect('activate', self.webserviceBarcode)
        menu.append(submenuitem)

        ## Separator
        sep = gtk.SeparatorMenuItem()
        menu.append(sep)

        ## Sync Collection
        submenuitem = gtk.MenuItem('Sync Collection')
        submenuitem.connect('activate', self.webserviceSyncCollection)
        menu.append(submenuitem)

        # Help menu
        helpmenu = gtk.Menu()
        help = gtk.MenuItem("Help")
        help.set_submenu(helpmenu)

        aboutm = gtk.MenuItem("About")
        aboutm.connect("activate", self.openAboutWindow)
        helpmenu.append(aboutm)

        mb.append(help)

        widget.pack_start(mb, False, False, 0)

    def cellArtist(self, column, cell, model, it, field):
        row = model.get_value(it, 0)
        release = self.catalog.getRelease(model[0])
        cell.set_property('text', self.fmtArtist(release))

    def makeListStore(self):
        self.releaseList = gtk.ListStore(str, str, str, str, str, str, str, str, str, str, str)

        for row in self.catalog.getBasicTable(self.filt):
            self.releaseList.append(row)
        # Need to add 1 here to get to sort string because of UUID at beginning
        self.releaseList.set_sort_column_id(1, gtk.SORT_ASCENDING)

        self.treeview.set_model(self.releaseList)
        # search by release title; have to add 2 because of UUID and sort
        # string at beginning
        self.treeview.set_search_column(self.columnNames.index('Artist')+2)

        return self.releaseList

    def createTreeView(self):
        # create the TreeView
        self.treeview = gtk.TreeView()
        # TODO add ability to sort by headers
        self.treeview.set_headers_clickable(True)
        # rules-hint
        self.treeview.set_rules_hint(True)

        # create the TreeViewColumns to display the data
        self.tvcolumn = [None] * len(self.columnNames)
        for n, columnName in enumerate(self.columnNames):
            cell = gtk.CellRendererText()
            cell.set_property('ellipsize', pango.ELLIPSIZE_END)
            cell.set_property('width-chars', self.columnWidths[n])
            if (columnName in self.numFields):
                cell.set_property('xalign', 1.0)
            self.tvcolumn[n] = gtk.TreeViewColumn(columnName, cell)
            self.tvcolumn[n].add_attribute(cell, 'text', n+2)
            self.tvcolumn[n].set_resizable(True)
            self.treeview.append_column(self.tvcolumn[n])

        self.treeview.connect('row-activated', self.on_row_activate)
        self.treeview.connect('cursor-changed', self.on_row_select)
        self.scrolledwindow = gtk.ScrolledWindow()
        self.scrolledwindow.add(self.treeview)

    def __init__(self, dbPath, cachePath):
        self.catalog = mbcat.catalog.Catalog(dbPath, cachePath)
        self.filt = {}

        # create a new window
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.set_title('mbcat')
        self.window.set_size_request(800, 600)
        self.window.set_position(gtk.WIN_POS_CENTER)

        # When the window is given the "delete_event" signal (this is given
        # by the window manager, usually by the "close" option, or on the
        # titlebar), we ask it to call the delete_event () function
        # as defined above. The data passed to the callback
        # function is NULL and is ignored in the callback function.
        self.window.connect("delete_event", self.delete_event)

        # Here we connect the "destroy" event to a signal handler.
        # This event occurs when we call gtk_widget_destroy() on the window,
        # or if we return FALSE in the "delete_event" callback.
        self.window.connect("destroy", self.destroy)

        self.agr = gtk.AccelGroup()
        self.window.add_accel_group(self.agr)

        vbox = gtk.VBox(False, 2)

        self.createMenuBar(vbox)
        self.createTreeView()
        vbox.pack_start(self.scrolledwindow, True, True, 0)

        self.statusbar = gtk.Statusbar()
        self.context_id = self.statusbar.get_context_id('PyGTK')

        # This packs the button into the window (a GTK container).
        vbox.pack_end(self.statusbar, False, False, 0)

        self.window.add(vbox)
    
        # The final step is to display this newly created widget.
        # and the window
        self.window.show_all()

        self.openDatabase()

    def main(self):
        # All PyGTK applications must have a gtk.main(). Control ends here
        # and waits for an event to occur (like a key press or mouse event).
        gtk.main()

# If the program is run directly or passed as an argument to the python
# interpreter then create a GtkGui instance and show it
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=
        'Runs the MusicBrainz-Catalog GTK interface')
    parser.add_argument('--database', 
        help='Specify the path to the catalog database')
    parser.add_argument('--cache', 
        help='Specify the path to the file cache')
    args = parser.parse_args()

    gui = MBCatGtk(dbPath=args.database, cachePath=args.cache)
    gui.main()
