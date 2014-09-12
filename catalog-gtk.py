#!/usr/bin/env python
#
#

from __future__ import print_function
import logging
logging.basicConfig(level=logging.INFO)
import threading
import gobject
import gtk
import pango
import mbcat
import mbcat.barcode # why does this not automatically import?
import mbcat.gtkpbar
import musicbrainzngs as mb
import argparse
import time
import webbrowser

# Initialize GTK's threading engine
gobject.threads_init()

_log = logging.getLogger("mbcat")

# Thanks http://stackoverflow.com/a/8907574/3098007
def TextEntry(parent, message, default='', textVisible=True):
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

def PurchaseInfoEntry(parent,
        message='Enter purchase info:'):
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
    table = gtk.Table(3, 2)

    label = gtk.Label('Date:')
    label.set_alignment(xalign=0, yalign=0)
    table.attach(label, 0, 1, 0, 1)
    dateEntry = gtk.Calendar()
    table.attach(dateEntry, 1, 2, 0, 1)

    label = gtk.Label('Vendor:')
    label.set_alignment(xalign=0, yalign=0)
    table.attach(label, 0, 1, 1, 2)
    vendorEntry = gtk.Entry()
    vendorEntry.set_width_chars(20)
    vendorEntry.connect('activate', lambda _: d.response(gtk.RESPONSE_OK))
    table.attach(vendorEntry, 1, 2, 1, 2)

    label = gtk.Label('Price:')
    label.set_alignment(xalign=0, yalign=0)
    table.attach(label, 0, 1, 2, 3)
    adj = gtk.Adjustment(0.0, 0.0, 1000000.0, 0.01, 0.01, 0.0)
    priceEntry = gtk.SpinButton(adj, 1.0, 2)
    priceEntry.set_width_chars(20)
    priceEntry.connect('activate', lambda _: d.response(gtk.RESPONSE_OK))
    table.attach(priceEntry, 1, 2, 2, 3)

    table.show_all()
    d.vbox.pack_end(table)
    d.set_default_response(gtk.RESPONSE_OK)

    r = d.run()
    # have to get the text before we destroy the gtk.Entry
    year, month, day = dateEntry.get_date()
    val = {'date': '%d/%d/%d' % (year, month, day),
        'vendor' : vendorEntry.get_text().decode('utf8'),
        'price' : priceEntry.get_text().decode('utf8'),
        }

    d.destroy()
    if r == gtk.RESPONSE_OK:
        return val
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
    for i, (label, textWidth) in enumerate(
        [('Artist', 20),
        ('Title', 30),
        ('Format', -1),
        ]):
        cell = gtk.CellRendererText()
        cell.set_property('xalign', 0)
        cell.set_property('ellipsize', pango.ELLIPSIZE_END)
        cell.set_property('width-chars', textWidth)
        col = gtk.TreeViewColumn(label, cell)
        col.add_attribute(cell, 'text', i+1)
        col.set_resizable(True)
        tv.append_column(col)

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
    for i, (label, xalign, textWidth) in enumerate(
        [('Title', 0, 30),
        ('Length', 1.0, -1),
        ('Appears on', 0, 30),
        ('Artist', 0, 20),
        ]):
        cell = gtk.CellRendererText()
        cell.set_property('xalign', xalign)
        cell.set_property('ellipsize', pango.ELLIPSIZE_END)
        cell.set_property('width-chars', textWidth)
        col = gtk.TreeViewColumn(label, cell)
        col.add_attribute(cell, 'text', i+1)
        col.set_resizable(True)
        tv.append_column(col)

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
    entry = TextEntry(parent, message, default)
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
        _log.info('Only one release result found')
        return matches[0]
    else:
        ErrorDialog(parent, 'No matches found for "%s"' % entry)

def BarcodeSearchDialog(parent,
        catalog,
        message='Enter barcode (UPC):',
        default=''):
    entry = TextEntry(parent, message, default)
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
    entry = TextEntry(parent, message, default)
    if not entry:
        return
    if len(entry) == 36:
        matches = [mbcat.utils.getReleaseIdFromInput(input)]
    else: # assume that a search query was entered
        matches = list(catalog._search(entry, table='trackwords',
            keycolumn='trackword', outcolumn='recording'))
    if len(matches) > 1:
        # Have to ask the user which release they mean
        return TrackSelectDialog(parent, catalog, trackIdList=matches)
    elif len(matches) == 1:
        _log.info('Only one track result found')
        releases = list(catalog.recordingGetReleases(matches[0]))
        if len(releases) > 1:
            return TrackSelectDialog(parent, catalog, trackIdList=matches)
        else:
            return releases[0]
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

def TrackListDialog(parent, catalog, releaseId):
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
    for i, (label, xalign, textWidth) in enumerate(
        [('Title', 0, 40),
        ('Length', 1.0, 2),
        ]):
        cell = gtk.CellRendererText()
        cell.set_property('xalign', xalign)
        cell.set_property('ellipsize', pango.ELLIPSIZE_END)
        cell.set_property('width-chars', textWidth)
        col = gtk.TreeViewColumn(label, cell)
        col.add_attribute(cell, 'text', i+1)
        col.set_resizable(True)
        tv.append_column(col)

    # make the list store
    trackTreeStore = gtk.TreeStore(str, str, str)
    for mediumId,position,format in catalog.curs.execute(
            'select id,position,format from media '
            'where release=? order by position',
            (releaseId,)).fetchall():
        parent = trackTreeStore.append(None,
            ('',
            format+' '+str(position),
            mbcat.catalog.recLengthAsString(
                catalog.getMediumLen(mediumId)
                )))
        for recId,recLength,recPosition,title in catalog.curs.execute(
                'select id,length,position,title from recordings '
                'where medium=? order by position',
                (mediumId,)).fetchall():
            trackTreeStore.append(parent,
                (recId,
                title,
                mbcat.catalog.recLengthAsString(recLength)
                ))
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
    Display a dialog with a list of release groups for a query result.
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

    for i, (label, textWidth, xalign) in enumerate([
            ('Artist', 20, 0),
            ('Title', 27, 0),
            ('Releases', 3, 1.0),
        ]):
        cell = gtk.CellRendererText()
        cell.set_property('xalign', xalign)
        cell.set_property('ellipsize', pango.ELLIPSIZE_END)
        cell.set_property('width-chars', textWidth)
        col = gtk.TreeViewColumn(label, cell)
        col.add_attribute(cell, 'text', i+1)
        col.set_resizable(True)
        tv.append_column(col)

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
    model, it = tv.get_selection().get_selected()
    id = model.get_value(it, 0) if r == gtk.RESPONSE_OK and it \
        else None
    d.destroy()
    return id

class QueryResultsDialog:
    """
    Create a window with a list of releases from a WebService query.
    Allow the user to add any of these releases.
    """
    def __init__(self,
        parent,
        catalog,
        queryResult,
        message='Release results',
        ):
        # TODO releaseDictList argument should support metadata returned from a
        # webservice query
        self.window = gtk.Window()
        self.window.set_transient_for(parent.window)
        self.window.set_destroy_with_parent(True)
        self.window.set_resizable(True)
        self.window.set_border_width(10)
        self.window.connect('destroy', self.on_destroy)
        vbox = gtk.VBox(False, 10)
        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.window.set_size_request(400, 300)

        # Keep reference to catalog for later
        self.catalog = catalog
        self.parent = parent

        self.tv = gtk.TreeView()
        for i, (label, textWidth) in enumerate(
            [('Artist', 20),
            ('Title', 30),
            ('Format', 10),
            ('Label', 20),
            ('Country', 4),
            ('Catalog #', 20),
            ('Barcode', 25),
            ]):
            cell = gtk.CellRendererText()
            cell.set_property('xalign', 0)
            cell.set_property('ellipsize', pango.ELLIPSIZE_END)
            cell.set_property('width-chars', textWidth)
            col = gtk.TreeViewColumn(label, cell)
            col.add_attribute(cell, 'text', i+1)
            col.set_resizable(True)
            self.tv.append_column(col)
        self.tv.connect('row-activated', self.on_row_activate)
        self.tv.connect('cursor-changed', self.on_row_select)
        self.tv.connect('unselect-all', self.on_unselect_all)

        # make the list store
        resultListStore = gtk.ListStore(str, str, str, str, str, str, str, str)
        for release in queryResult['release-list']:
            resultListStore.append((
                release['id'],
                mbcat.catalog.formatQueryArtist(release),
                release['title'],
                mbcat.catalog.formatQueryMedia(release),
                mbcat.catalog.formatQueryRecordLabel(release),
                release['country'] if 'country' in release else '',
                mbcat.catalog.formatQueryCatNo(release),
                release['barcode'] if 'barcode' in release else '',
                ))
        self.tv.set_model(resultListStore)

        sw.add(self.tv)
        vbox.pack_start(sw, expand=True, fill=True)

        # Buttons
        hbox = gtk.HBox(False, 10)
        btn = gtk.Button('Close', gtk.STOCK_CLOSE)
        btn.connect('clicked', self.on_close)
        hbox.pack_end(btn, expand=False, fill=False)
        btn = gtk.Button('Add', gtk.STOCK_ADD)
        btn.connect('clicked', self.add_release)
        hbox.pack_end(btn, expand=False, fill=False)
        vbox.pack_end(hbox, expand=False, fill=False)

        # Info on the selected row
        self.selInfo = gtk.Label()
        vbox.pack_end(self.selInfo, expand=False)

        self.window.add(vbox)
        self.window.set_title(message)
        self.window.show_all()

    def get_selection(self):
        model, it = self.tv.get_selection().get_selected()
        return model.get_value(it, 0) if it else None

    def add_release(self, widget, data=None):
        entry = self.get_selection()
        # TODO this procedure needs to be part of the Catalog class?
        if entry in self.catalog:
            ErrorDialog(self.window, 'Release "%s" already exists' % entry)
            return
        try:
            self.catalog.addRelease(entry)
        except mb.ResponseError as e:
            ErrorDialog(self.window, str(e) + ". Bad release ID?")
            return

        _log.info("Added '%s'" % self.catalog.getRelease(entry)['title'])

        # TODO clean this up, too many references to parent, need a method
        self.catalog.getCoverArt(entry)
        self.parent.makeListStore()
        self.parent.setSelectedRow(self.parent.getReleaseRow(entry))

    def on_row_activate(self, treeview, path, column):
        model, it = treeview.get_selection().get_selected()
        relId = model.get_value(it, 0)
        webbrowser.open(self.catalog.releaseUrl + relId)

    def on_row_select(self, treeview):
        model, it = treeview.get_selection().get_selected()
        relId = model.get_value(it, 0)
        self.selInfo.set_text(relId)
        _log.info('Release '+relId+' selected')

    def on_unselect_all(self, treeview):
        self.selInfo.set_text('')

    def on_destroy(self, widget, data=None):
        self.window.destroy()

    def on_close(self, widget):
        self.on_destroy(widget)

def SelectCollectionDialog(parent, result):
    """
    Display a dialog with a list of collections from a query.
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
    id = model.get_value(it, 0) if r == gtk.RESPONSE_OK and it \
        else None
    d.destroy()
    return id

def TextViewEntry(parent, message, default=''):
    """
    Display a dialog with a text entry.
    Returns the text, or None if canceled.
    """
    d = gtk.MessageDialog(parent,
            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
            gtk.MESSAGE_QUESTION,
            gtk.BUTTONS_OK_CANCEL,
            message)
    d.set_size_request(400,300)
    d.set_resizable(True)
    sw = gtk.ScrolledWindow()
    sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
    textview = gtk.TextView()
    textbuffer = textview.get_buffer()
    sw.add(textview)
    textbuffer.set_text(default)
    textview.set_wrap_mode(gtk.WRAP_WORD)
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

class DetailPane(gtk.HBox):
    imgpx = 258
    def __init__(self, catalog):
        gtk.HBox.__init__(self, False, 0)
        self.catalog = catalog

        self.coverart = gtk.Image()
        self.coverart.set_size_request(self.imgpx, self.imgpx)
        self.pack_start(self.coverart, expand=False, fill=False)

        self.sw = gtk.ScrolledWindow()
        #self.sw.set_size_request(self.imgpx, self.imgpx)
        self.sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)

        self.tv = gtk.TreeView()
        for i, (label, xalign, textWidth) in enumerate(
            [('Title', 0, 40),
            ('Length', 1.0, 2),
            ]):
            cell = gtk.CellRendererText()
            cell.set_property('xalign', xalign)
            cell.set_property('ellipsize', pango.ELLIPSIZE_END)
            cell.set_property('width-chars', textWidth)
            col = gtk.TreeViewColumn(label, cell)
            col.add_attribute(cell, 'text', i+1)
            col.set_resizable(True)
            self.tv.append_column(col)

        self.tv.show()
        self.sw.add(self.tv)
        self.sw.show()
        self.pack_start(self.sw)

    def update(self, releaseId):
        self.coverart.hide()
        self.coverart.set_from_file(self.catalog._getCoverArtPath(releaseId))
        try:
            self.pixbuf = self.coverart.get_pixbuf()
            resized = self.pixbuf.scale_simple(self.imgpx,self.imgpx,
                gtk.gdk.INTERP_BILINEAR)
            self.coverart.set_from_pixbuf(resized)
        except ValueError:
            pass
        self.coverart.show()

        releaseDict = self.catalog.getRelease(releaseId)
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
        self.tv.set_model(trackTreeStore)
        self.tv.expand_all()

class MBCatGtk:
    """
    A GTK interface for managing a MusicBrainz Catalog.
    """
    __name__ = 'MusicBrainz Catalog GTK Gui'
    __version__ = '0.1'
    __copyright__ = 'Ryan Helinski'
    __website__ = 'https://github.com/rlhelinski/musicbrainz-catalog'

    columnNames = ['Artist', 'Release Title', 'Date', 'Country', 'Label',
        'Catalog #', 'Barcode', 'ASIN', 'Format']
    columnWidths = [30, 45, 16, 2, 37, 23, 16, 16, 16]
    numFields = ['Barcode', 'ASIN']

    formatNames = ['All', 'Digital', 'CD', '7" Vinyl', '12" Vinyl', 'Unknown']
    formatLabels = ['_All', '_Digital', '_CD', '_7" Vinyl', '_12" Vinyl',
        '_Unknown']

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

    def menuCatalogVacuum(self, widget):
        # Need a new Catalog object for this new thread
        c = mbcat.catalog.Catalog(self.catalog.dbPath, self.catalog.cachePath)
        th = mbcat.gtkpbar.TaskHandler(self.window,
            c.vacuum())
        th.start()

    def menuCatalogRebuild(self, widget):
        # Need a new Catalog object for this new thread
        c = mbcat.catalog.Catalog(self.catalog.dbPath, self.catalog.cachePath)
        th = mbcat.gtkpbar.TaskHandler(self.window,
            c.rebuildCacheTables())
        th.start()
        # TODO figure out how to cause a refresh here

    def menuCatalogGetSimilar(self, widget):
        th = TaskHandler()
        pd = ProgressDialog(parent=self.window, taskHandler=th)
        #   initStatusLabel='Computing similar releases')
        self.catalog.checkLevenshteinDistances(pbar=pd)
        # Need to write a dialog to show this result
        for i in range(100):
            print(str(lds[i][0]) + '\t' +
                         self.c.formatDiscInfo(lds[i][1]) + ' <-> ' +
                         self.c.formatDiscInfo(lds[i][2]) + '\n')

    def format_comment(self, column, cell, model, it, field):
        row = model.get_value(it, 0)
        cell.set_property('text', 'OK')

    def menu_release_items_set_sensitive(self, sens=True):
        """Make menu items specific to releases active."""
        for menuitem in self.menu_release_items:
            menuitem.set_sensitive(sens)

    def on_row_activate(self, treeview, path, column):
        model, it = treeview.get_selection().get_selected()
        relId = model.get_value(it, 0)
        webbrowser.open(self.catalog.releaseUrl + relId)

    def on_row_select(self, treeview):
        self.menu_release_items_set_sensitive(True)
        model, it = treeview.get_selection().get_selected()
        relId = model.get_value(it, 0)
        if self.detailpane.get_visible():
            self.detailpane.update(relId)
        _log.info('Release '+relId+' selected')

    def on_unselect_all(self, treeview):
        self.menu_release_items_set_sensitive(False)

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
        # Limit the range of the row input
        actualRow = min(len(self.releaseList), row)
        self.treeview.get_selection().select_path(actualRow)
        self.treeview.scroll_to_cell(actualRow, use_align=True, row_align=0.5)
        self.on_row_select(self.treeview)

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
        if not result_iter:
            return None
        return self.releaseList.get_path(result_iter)[0]

    def refreshView(self, widget):
        self.makeListStore()
        self.updateStatusBar()

    def scrollToSelected(self, widget):
        row = self.getSelectedRow()
        self.treeview.scroll_to_cell(row, use_align=True, row_align=0.5)

    def toggleStatusBar(self, widget):
        if widget.active:
            self.statusbar.show()
        else:
            self.statusbar.hide()

    def updateStatusBar(self):
        # TODO use this push/pop action better
        self.statusbar.pop(self.context_id)
        msg = ('%d total releases, %d release words, %d track words, '+\
            'showing %d releases') % \
            (len(self.catalog), self.catalog.getWordCount(),
                self.catalog.getTrackWordCount(),
                len(self.releaseList))
        self.statusbar.push(self.context_id, msg)

    def toggleDetailPane(self, widget):
        if widget.active:
            self.detailpane.show()
            self.updateDetailPane()
        else:
            self.detailpane.hide()

    def updateDetailPane(self):
        self.detailpane.update(self.getSelection())

    def selectFormat(self, action, current):
        text = self.formatNames[action.get_current_value()]
        sel = self.getSelection()
        if text != 'All':
            fmt = mbcat.formats.getFormatObj(text).name()
            #print ('Filtering formats: '+text+', '+fmt)
            self.filt = {'sortformat': fmt}
        else:
            self.filt = {}
        self.makeListStore()
        self.updateStatusBar()

        row = self.getReleaseRow(sel)
        if row:
            self.setSelectedRow(row)

    def addRelease(self, widget):
        entry = TextEntry(self.window, 'Enter Release ID')
        if not entry:
            return
        # TODO this procedure needs to be part of the Catalog class?
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

        if not releaseId:
            # Should never get here
            ErrorDialog(parent, 'Select a release first')
            return

        relTitle = self.catalog.getRelease(releaseId)['title']
        # Ask the user to specify a release to which to switch
        newRelId = TextEntry(self.window,
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
        # refresh the detail pane if it is active
        self.updateDetailPane()

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
        TrackListDialog(self.window, self.catalog, releaseId)

    def checkOut(self, widget):
        releaseId = self.getSelection()

        checkOutEvents = self.catalog.getCheckOutEvents(releaseId)
        checkInEvents = self.catalog.getCheckInEvents(releaseId)
        for event in checkOutEvents:
            _log.info(str(event) + '\n')
        for event in checkInEvents:
            _log.info(str(event) + '\n')

        borrower = TextEntry(self.window, "Borrower: ")
        if not borrower:
            return

        date = TextEntry(self.window,
            "Lend date  (" + mbcat.dateFmtUsr + "): ",
            default=time.strftime(mbcat.dateFmtStr))
        self.catalog.addCheckOutEvent(releaseId, borrower,
            time.strftime('%s', time.strptime(date, mbcat.dateFmtStr)))

    def checkIn(self, widget):
        releaseId = self.getSelection()

        lendEvents = self.catalog.getLendEvents(releaseId)
        if not lendEvents or not isinstance(lendEvents[-1],
            mbcat.extradata.CheckOutEvent):
            ErrorDialog(self.window, 'Release is not checked out.')
            return

        date = TextEntry(self.window,
            "Return date (" + mbcat.dateFmtUsr +
            ") (leave empty for today): ")
        if not date:
            date = time.time()
        self.catalog.addLendEvent(releaseId,
            mbcat.extradata.CheckInEvent(date))

    def editComment(self, widget):
        releaseId = self.getSelection()
        oldcomment = self.catalog.getComment(releaseId)
        newcomment = TextViewEntry(self.window, 'Edit Release Comments', oldcomment if oldcomment is not None else '')
        if newcomment is not None:
            self.catalog.setComment(releaseId, newcomment)

    def changeCount(self, widget):
        releaseId = self.getSelection()
        newcount = IntegerDialog(self.window, 'Enter new copy count',
            self.catalog.getCopyCount(releaseId))
        if newcount is not None:
            self.catalog.setCopyCount(releaseId, newcount)

    def listen(self, widget):
        # TODO this needs its own dialog that displays the current listening dates
        releaseId = self.getSelection()
        dateStr = TextEntry(self.window,
            'Enter listen date (' + mbcat.dateFmtUsr + ')',
            time.strftime(mbcat.dateFmtStr))
        if dateStr:
            date = float(time.strftime('%s',
                time.strptime(dateStr, mbcat.dateFmtStr)))
            self.catalog.addListenDate(releaseId, date)

    def purchaseInfo(self, widget):
        """Add a purchase date."""
        releaseId = self.getSelection()

        purchases = self.catalog.getPurchases(releaseId)
        for purchase in purchases:
            print(str(purchase))
        info = PurchaseInfoEntry(self.window)
        if not info:
            return

        self.catalog.addPurchase(releaseId, info['date'], info['price'], info['vendor'])

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
        entry = TextEntry(self.window, 'Enter release group search terms')
        if not entry:
            return
        th = mbcat.gtkpbar.TaskHandler(self.window, mbcat.gtkpbar.DummyTask())
        th.start()
        results = mb.search_release_groups(releasegroup=entry,
             limit=self.searchResultsLimit)
        th.stop()
        if not results:
            ErrorDialog(self.window, 'No results found for "%s"' % entry)
        release_group_selected = GroupQueryResultsDialog(self.window,
            self.catalog, results)
        if release_group_selected:
            results = mb.search_releases(rgid=release_group_selected)
            QueryResultsDialog(self, self.catalog, results)

    def webserviceRelease(self, widget):
        entry = TextEntry(self.window, 'Enter release search terms')
        if not entry:
            return
        results = mb.search_releases(release=entry,
             limit=self.searchResultsLimit)
        if not results:
            ErrorDialog(self.window, 'No results found for "%s"' % entry)
        QueryResultsDialog(self, self.catalog, results)

    def webserviceBarcode(self, widget):
        entry = TextEntry(self.window, 'Enter search barcode (UPC):')
        if not entry:
            return
        results = mb.search_releases(barcode=entry,
             limit=self.searchResultsLimit)
        if not results:
            ErrorDialog(self.window, 'No results found for "%s"' % entry)
            return
        QueryResultsDialog(self, self.catalog, results)

    def webserviceCatNo(self, widget):
        entry = TextEntry(self.window, 'Enter search catalog number:')
        if not entry:
            return
        results = mb.search_releases(catno=entry,
             limit=self.searchResultsLimit)
        if not results:
            ErrorDialog(self.window, 'No results found for "%s"' % entry)
            return
        QueryResultsDialog(self, self.catalog, results)

    def webserviceSyncCollection(self, widget):
        """Synchronize with a musicbrainz collection (currently only pushes releases)."""
        if not self.catalog.prefs.username:
            username = TextEntry('Enter username:')
            self.catalog.prefs.username = username
            self.catalog.prefs.save()
        else:
            username = self.catalog.prefs.username

        # Input the password.
        password = TextEntry(self.window,
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

    def readDiscTOC(self, widget):
        def askBrowseSubmission():
            answer = ConfirmDialog(self.window,
                'Open browser to Submission URL? [y/N]')
            if answer:
                _log.info('Opening web browser.')
                webbrowser.open(disc.submission_url)

        try:
            import discid
        except ImportError as e:
            ErrorDialog(self.window, 'Could not import discid')
            return
        default_device = discid.get_default_device()
        # bring up a dialog to allow the user to specify a device
        spec_device = TextEntry(self.window, 'Select a device to read:',
            default_device)
        try:
            disc = discid.read(spec_device)
        except discid.DiscError as e:
            ErrorDialog(self.window, "DiscID calculation failed: " + str(e))
            return

        try:
            _log.info("Querying MusicBrainz...")
            result = mb.get_releases_by_discid(disc.id,
                                               includes=["artists"])
            _log.info('OK\n')
        except mb.ResponseError:
            _log.warning('Disc not found or bad MusicBrainz response.')
            askBrowseSubmission()
        else:
            if result.get("disc"):
                _log.info('Showing query results for disc ID "%s"'\
                    %result['disc']['id'])
                # TODO pass in submission URL in disc.submission_url here
                # and add button to dialog to bring up that URL
                QueryResultsDialog(self, self.catalog, result['disc'])
            elif result.get("cdstub"):
                for label, key in [
                        ('CD Stub', 'id'),
                        ('Artist', 'artist'),
                        ('Title', 'title'),
                        ('Barcode', 'barcode')]:
                    if key in result['cdstub']:
                        _log.info('%10s: %s\n' %
                                     (label, result['cdstub'][key]))
                askBrowseSubmission()

                ErrorDialog(self.window, 'There was only a CD stub.')
                return

    def createMenuBar(self, widget):
        # Menu bar
        mb = gtk.MenuBar()
        self.menu_release_items = []

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
        submenuitem.connect('activate', self.menuCatalogSaveAs)
        menu.append(submenuitem)

        # Separator
        sep = gtk.SeparatorMenuItem()
        menu.append(sep)

        # Check
        submenuitem = gtk.MenuItem('Check')
        menu.append(submenuitem)

        # Vacuum
        submenuitem = gtk.ImageMenuItem(gtk.STOCK_CLEAR)
        submenuitem.get_child().set_label('Vacuum')
        submenuitem.connect('activate', self.menuCatalogVacuum)
        menu.append(submenuitem)

        # Rebuild
        submenuitem = gtk.ImageMenuItem(gtk.STOCK_EXECUTE)
        submenuitem.get_child().set_label('Rebuild Indexes')
        submenuitem.connect('activate', self.menuCatalogRebuild)
        menu.append(submenuitem)

        # Similar
        submenuitem = gtk.MenuItem('Similar')
        submenuitem.connect('activate', self.menuCatalogGetSimilar)
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

        ## Show Release Detail Pane
        submenuitem = gtk.CheckMenuItem('Show Detail Pane')
        submenuitem.set_active(False)
        self.menu_release_items.append(submenuitem)
        submenuitem.connect('activate', self.toggleDetailPane)
        menu.append(submenuitem)

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

        ## Refresh
        submenuitem = gtk.MenuItem('Refresh')
        submenuitem.connect('activate', self.refreshView)
        menu.append(submenuitem)

        ## Refresh
        submenuitem = gtk.MenuItem('Scroll to Selected')
        submenuitem.connect('activate', self.scrollToSelected)
        self.menu_release_items.append(submenuitem)
        menu.append(submenuitem)

        mb.append(menuitem)

        # Release menu
        menu = gtk.Menu()
        menuitem = gtk.MenuItem("_Release")
        menuitem.set_submenu(menu)

        ## Add
        submenuitem = gtk.ImageMenuItem(gtk.STOCK_ADD)
        submenuitem.get_child().set_label('_Add')
        key, mod = gtk.accelerator_parse('<Control>a')
        submenuitem.add_accelerator('activate', self.agr, key, mod,
            gtk.ACCEL_VISIBLE)
        submenuitem.connect('activate', self.addRelease)
        menu.append(submenuitem)

        ## Delete
        submenuitem = gtk.ImageMenuItem(gtk.STOCK_REMOVE)
        submenuitem.get_child().set_label('_Delete')
        key, mod = gtk.accelerator_parse('<Control>Delete')
        submenuitem.add_accelerator('activate', self.agr, key, mod,
            gtk.ACCEL_VISIBLE)
        submenuitem.connect('activate', self.deleteRelease)
        menu.append(submenuitem)
        self.menu_release_items.append(submenuitem)

        ## Switch
        submenuitem = gtk.ImageMenuItem(gtk.STOCK_CONVERT)
        submenuitem.get_child().set_label('_Switch')
        submenuitem.connect('activate', self.switchRelease)
        menu.append(submenuitem)
        self.menu_release_items.append(submenuitem)

        ## Cover Art
        submenuitem = gtk.ImageMenuItem(gtk.STOCK_REFRESH)
        submenuitem.get_child().set_label('Get Cover Art')
        submenuitem.connect('activate', self.getCoverArt)
        menu.append(submenuitem)
        self.menu_release_items.append(submenuitem)

        ## Refresh
        submenuitem = gtk.ImageMenuItem(gtk.STOCK_REFRESH)
        submenuitem.get_child().set_label('_Refresh')
        submenuitem.connect('activate', self.refreshRelease)
        menu.append(submenuitem)
        self.menu_release_items.append(submenuitem)

        ## Track List
        submenuitem = gtk.ImageMenuItem(gtk.STOCK_INDEX)
        submenuitem.get_child().set_label('Track List')
        submenuitem.connect('activate', self.showTrackList)
        menu.append(submenuitem)
        self.menu_release_items.append(submenuitem)

        ## Separator
        sep = gtk.SeparatorMenuItem()
        menu.append(sep)

        ## Check Out
        submenuitem = gtk.MenuItem('Check Out')
        submenuitem.connect('activate', self.checkOut)
        menu.append(submenuitem)
        self.menu_release_items.append(submenuitem)

        ## Check In
        submenuitem = gtk.MenuItem('Check In')
        submenuitem.connect('activate', self.checkIn)
        menu.append(submenuitem)
        self.menu_release_items.append(submenuitem)

        ## Comment
        submenuitem = gtk.ImageMenuItem(gtk.STOCK_EDIT)
        submenuitem.get_child().set_label('Comment')
        submenuitem.connect('activate', self.editComment)
        menu.append(submenuitem)
        self.menu_release_items.append(submenuitem)

        ## Count
        submenuitem = gtk.MenuItem('Count')
        submenuitem.connect('activate', self.changeCount)
        menu.append(submenuitem)
        self.menu_release_items.append(submenuitem)

        ## Listen
        submenuitem = gtk.MenuItem('Listen')
        submenuitem.connect('activate', self.listen)
        menu.append(submenuitem)
        self.menu_release_items.append(submenuitem)

        ## Purchase Info
        submenuitem = gtk.MenuItem('Purchase Info')
        submenuitem.connect('activate', self.purchaseInfo)
        menu.append(submenuitem)
        self.menu_release_items.append(submenuitem)

        ## Rate
        submenuitem = gtk.MenuItem('_Rate')
        submenuitem.connect('activate', self.rateRelease)
        menu.append(submenuitem)
        self.menu_release_items.append(submenuitem)

        mb.append(menuitem)
        self.menu_release_items_set_sensitive(False)

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

        ## Disc lookup
        submenuitem = gtk.ImageMenuItem(gtk.STOCK_CDROM)
        submenuitem.get_child().set_label('Disc lookup')
        submenuitem.connect('activate', self.readDiscTOC)
        menu.append(submenuitem)

        ## Separator
        sep = gtk.SeparatorMenuItem()
        menu.append(sep)

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

        ## Catalog # Search
        submenuitem = gtk.MenuItem('Catalog Number')
        submenuitem.connect('activate', self.webserviceCatNo)
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

        mb.show_all()
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
        self.treeview.connect('unselect-all', self.on_unselect_all)
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
        self.treeview.show()
        self.scrolledwindow.show()
        vbox.pack_start(self.scrolledwindow, True, True, 0)

        self.statusbar = gtk.Statusbar()
        self.context_id = self.statusbar.get_context_id('PyGTK')
        self.statusbar.show()

        # This packs the button into the window (a GTK container).
        vbox.pack_end(self.statusbar, False, False, 0)

        # Release detail pane
        self.detailpane = DetailPane(self.catalog)
        vbox.pack_end(self.detailpane, False, False, 0)

        self.window.add(vbox)

        # The final step is to display this newly created widget.
        # and the window
        vbox.show()
        self.window.show()

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
