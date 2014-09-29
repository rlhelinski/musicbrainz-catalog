#!/usr/bin/env python
#
#

from __future__ import print_function
from __future__ import unicode_literals
import logging
logging.basicConfig(level=logging.INFO)
import threading
import gobject
import gtk
import pango
import mbcat
import mbcat.barcode # why does this not automatically import?
import mbcat.dialogs
import musicbrainzngs as mb
import argparse
import time
import webbrowser
import sqlite3

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

def DateEntry(parent, message, default=''):
    """
    Display a dialog with a text entry.
    Returns the text, or None if canceled.
    """
    d = gtk.MessageDialog(parent,
            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
            gtk.MESSAGE_QUESTION,
            gtk.BUTTONS_OK_CANCEL,
            message)
    entry = gtk.Calendar()
    #entry.set_text(default)
    #entry.connect('activate', lambda _: d.response(gtk.RESPONSE_OK))
    entry.show()
    d.vbox.pack_end(entry)
    d.set_default_response(gtk.RESPONSE_OK)

    r = d.run()
    # have to get the text before we destroy the gtk.Entry
    year, month, day = entry.get_date()
    # From http://www.pygtk.org/pygtk2reference/class-gtkcalendar.html#method-gtkcalendar--get-date
    # Note that month is zero-based (i.e it allowed values are 0-11) while
    # selected_day is one-based (i.e. allowed values are 1-31).
    date = '%d/%d/%d' % (month+1, day, year)
    d.destroy()
    if r == gtk.RESPONSE_OK:
        return date
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
    val = {'date': '%d/%d/%d' % (year, month+1, day),
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

class BarcodeSearchDialog:
    def __init__(self,
            parentWindow,
            app,
            message='Enter barcode (UPC):',
            default='',
            title='Barcode Entry'
            ):
        self.parentWindow = parentWindow
        self.app = app
        self.window = gtk.Window()
        self.window.set_transient_for(parentWindow)
        self.window.set_destroy_with_parent(True)
        self.window.set_border_width(10)
        self.window.connect('destroy', self.on_destroy)
        self.window.set_title(title)

        vbox = gtk.VBox(False, 10)

        prompt = gtk.Label(message)
        vbox.pack_start(prompt, expand=True, fill=True)

        entrybox = gtk.HBox(False, 10)
        self.entry = gtk.Entry(40)
        self.entry.connect('changed', self.on_change, self.entry)
        self.entry.connect('activate', self.on_submit)
        if default:
            self.entry.set_text(default)
        entrybox.pack_start(self.entry, expand=True, fill=True)
        self.checkIndicator = gtk.Image()
        self.checkIndicator.set_from_stock(
                gtk.STOCK_CANCEL, gtk.ICON_SIZE_BUTTON)
        entrybox.pack_start(self.checkIndicator, expand=False, fill=False)

        vbox.pack_start(entrybox, expand=False, fill=False)

        buttonbox = gtk.HBox(False, 10)

        btn = gtk.Button('Close', gtk.STOCK_CLOSE)
        btn.connect('clicked', self.on_close)
        buttonbox.pack_end(btn, expand=False, fill=False)

        btn = gtk.Button('Add', gtk.STOCK_OK)
        btn.connect('clicked', self.on_submit)
        buttonbox.pack_end(btn, expand=False, fill=False)

        vbox.pack_start(buttonbox, expand=False, fill=False)

        self.window.add(vbox)
        self.window.show_all()

    def on_change(self, widget, entry):
        entry_text = entry.get_text()
        self.checkIndicator.set_from_stock(
                gtk.STOCK_APPLY if \
                    mbcat.barcode.UPC.check_upc_a(entry_text) \
                    else gtk.STOCK_CANCEL,
                gtk.ICON_SIZE_BUTTON)

    def get_matches(self, entry):
        barCodes = mbcat.barcode.UPC(entry).variations()
        matches = set()
        for barCode in barCodes:
            try:
                for releaseId in self.app.catalog.barCodeLookup(barCode):
                    matches.add(releaseId)
            except KeyError as e:
                pass
            else:
                found = True
        matches = list(matches)

        if len(matches) > 1:
            # Have to ask the user which release they mean
            return ReleaseSelectDialog(self.parentWindow, self.app.catalog,
                    releaseIdList=matches)
        elif len(matches) == 1:
            return matches[0]
        else:
            ErrorDialog(self.window, 'No matches found for "%s"' % entry)

    def on_submit(self, widget):
        entry = self.entry.get_text()
        releaseId = self.get_matches(entry)

        if releaseId and releaseId in self.app.catalog:
            self.app.setSelectedRow(self.app.getReleaseRow(releaseId))
            self.on_destroy()

    def on_destroy(self, widget=None, data=None):
        self.window.destroy()

    def on_close(self, widget):
        self.on_destroy(widget)

class BarcodeQueryDialog(BarcodeSearchDialog):
    """
    A variation of BarcodeSearchDialog for webservice queries.
    """
    def on_submit(self, widget):
        entry = self.entry.get_text()
        if not entry:
            return
        mbcat.dialogs.PulseDialog(self.window,
            QueryTask(self.window, self.app, QueryResultsDialog,
                mb.search_releases,
                barcode=entry, limit=self.app.searchResultsLimit)).start()
        #self.on_destroy() # can't do this here

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

def buildRatingComboBox(default=None):
    combobox = gtk.combo_box_new_text()
    combobox.append_text('None')
    combobox.append_text('1')
    combobox.append_text('2')
    combobox.append_text('3')
    combobox.append_text('4')
    combobox.append_text('5')
    combobox.set_active(default if default is not None else 0)
    combobox.show()
    return combobox

def RatingDialog(parent,
    message='Enter rating',
    default=None):
    d = gtk.MessageDialog(parent,
            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
            gtk.MESSAGE_QUESTION,
            gtk.BUTTONS_OK_CANCEL,
            message
            )
    combobox = buildRatingComboBox(default)
    d.vbox.pack_end(combobox)
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

def makeTrackTreeStore(catalog, releaseId):
    trackTreeStore = gtk.TreeStore(str, str, str)
    # TODO this should be a Catalog method
    for mediumId,position,format in catalog.cm.executeAndFetch(
            'select id,position,format from media '
            'where release=? order by position',
            (releaseId,)):
        parent = trackTreeStore.append(None,
            ('',
            format+' '+str(position),
            mbcat.catalog.recLengthAsString(
                catalog.getMediumLen(mediumId)
                )))
        for recId,recLength,recPosition,title in catalog.cm.executeAndFetch(
                'select id,length,position,title from recordings '
                'where medium=? order by position',
                (mediumId,)):
            trackTreeStore.append(parent,
                (recId,
                title,
                mbcat.catalog.recLengthAsString(recLength)
                ))
    return trackTreeStore

class QueryTask(mbcat.dialogs.ThreadedCall):
    def __init__(self, window, app, result_viewer, fun, *args, **kwargs):
        mbcat.dialogs.ThreadedCall.__init__(self, fun, *args, **kwargs)
        self.window = window
        self.app = app
        self.result_viewer = result_viewer
    def run(self):
        mbcat.dialogs.ThreadedCall.run(self)
        if not self.result:
            ErrorDialog(self.window, 'No results found for "%s"' % str(kwargs))
        else:
            self.result_viewer(self.window, self.app, self.result)
            #if type(self.app) == BarcodeQueryDialog:
                #self.window.destroy()

class QueryResultsDialog:
    """
    Create a window with a list of releases from a WebService query.
    Allow the user to add any of these releases.
    """
    row_contains = 'Group'

    def __init__(self,
            parentWindow,
            app,
            queryResult,
            message='Release Results',
        ):
        self.window = gtk.Window()
        self.window.set_transient_for(parentWindow)
        self.window.set_destroy_with_parent(True)
        self.window.set_resizable(True)
        self.window.set_border_width(10)
        self.window.connect('destroy', self.on_destroy)
        self.window.set_title(message)
        self.window.set_size_request(400, 300)

        self.active_on_row_selected = []

        vbox = gtk.VBox(False, 10)
        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)

        # Keep reference to catalog for later
        self.app = app
        self.parentWindow = parentWindow

        self.buildTreeView()
        self.buildListStore(queryResult)

        self.tv.connect('row-activated', self.on_row_activate)
        self.tv.connect('cursor-changed', self.on_row_select)
        self.tv.connect('unselect-all', self.on_unselect_all)
        sw.add(self.tv)
        vbox.pack_start(sw, expand=True, fill=True)

        hbox = self.buildButtons()
        vbox.pack_end(hbox, expand=False, fill=False)

        self.buildRowInfoWidgets(vbox)

        self.window.add(vbox)
        self.window.show_all()

    def buildTreeView(self):
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
        self.tv.set_search_column(1) # search by Artist

    def buildListStore(self, queryResult):
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

    def buildButtons(self):
        # Buttons
        hbox = gtk.HBox(False, 10)
        btn = gtk.Button('Close', gtk.STOCK_CLOSE)
        btn.connect('clicked', self.on_close)
        hbox.pack_end(btn, expand=False, fill=False)

        btn = gtk.Button('Add', gtk.STOCK_ADD)
        btn.connect('clicked', self.add_release)
        hbox.pack_end(btn, expand=False, fill=False)
        self.active_on_row_selected.append(btn)

        btn = gtk.Button('Browse Release')
        btn.connect('clicked', self.browse_release)
        hbox.pack_end(btn, expand=False, fill=False)
        self.active_on_row_selected.append(btn)

        return hbox

    def buildRowInfoWidgets(self, vbox):
        # Info on the selected row
        self.selInfo = gtk.Label()
        vbox.pack_end(self.selInfo, expand=False)

    def get_selection(self):
        model, it = self.tv.get_selection().get_selected()
        return model.get_value(it, 0) if it else None

    def add_release(self, widget, data=None):
        self.app._addRelease(self.get_selection(), self.window)

    def on_row_activate(self, treeview, path, column):
        # TODO not sure what this should do
        relId = self.get_selection()
        webbrowser.open(mbcat.catalog.Catalog.releaseUrl + relId)

    def browse_release(self, button):
        relId = self.get_selection()
        webbrowser.open(mbcat.catalog.Catalog.releaseUrl + relId)

    def row_widgets_set_sensitive(self, sens=True):
        for widget in self.active_on_row_selected:
            widget.set_sensitive(sens)

    def on_row_select(self, treeview):
        relId = self.get_selection()
        if relId:
            self.selInfo.set_text(relId)
            _log.info(self.row_contains+' '+relId+' selected')
        self.row_widgets_set_sensitive(True)

    def on_unselect_all(self, treeview):
        self.selInfo.set_text('')
        self.row_widgets_set_sensitive(False)

    def on_destroy(self, widget, data=None):
        self.window.destroy()

    def on_close(self, widget):
        self.on_destroy(widget)

class GroupQueryResultsDialog(QueryResultsDialog):
    """
    Display a dialog with a list of release groups for a query result.
    """
    row_contains = 'Group'
    def __init__(self,
            parentWindow,
            app,
            queryResult,
            message='Release Group Results',
            ):
        QueryResultsDialog.__init__(self, parentWindow, app,
            queryResult, message)

    def buildTreeView(self):
        self.tv = gtk.TreeView()
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
            self.tv.append_column(col)
        self.tv.set_search_column(1) # search by Artist

    def buildListStore(self, queryResult):
        # make the list store
        resultListStore = gtk.ListStore(str, str, str, str)
        for group in queryResult['release-group-list']:
            resultListStore.append((
                group['id'],
                mbcat.catalog.formatQueryArtist(group),
                group['title'],
                '%d' % len(group['release-list'])
                ))
        self.tv.set_model(resultListStore)

    def buildButtons(self):
        # Buttons
        hbox = gtk.HBox(False, 10)
        btn = gtk.Button('Close', gtk.STOCK_CLOSE)
        btn.connect('clicked', self.on_close)
        hbox.pack_end(btn, expand=False, fill=False)

        # TODO could use gtk.STOCK_CONNECT here
        btn = gtk.Button('Get Releases')
        btn.connect('clicked', self.get_releases)
        hbox.pack_end(btn, expand=False, fill=False)
        self.active_on_row_selected.append(btn)

        btn = gtk.Button('Browse Group')
        btn.connect('clicked', self.browse_group)
        hbox.pack_end(btn, expand=False, fill=False)
        self.active_on_row_selected.append(btn)

        return hbox

    def get_releases(self, widget, data=None):
        release_group_selected = self.get_selection()

        mbcat.dialogs.PulseDialog(self.window,
            QueryTask(self.window, self.app, QueryResultsDialog,
                mb.search_releases,
                rgid=release_group_selected)).start()

    def browse_group(self, button):
        relId = self.get_selection()
        webbrowser.open(mbcat.catalog.Catalog.groupUrl + relId)

class TrackListDialog(QueryResultsDialog):
    """
    Display a dialog with a list of tracks for a release.
    Example:
    """
    def __init__(self, parentWindow, app, releaseId, message='Track List'):
        QueryResultsDialog.__init__(self, parentWindow, app,
            releaseId, message)

    def buildTreeView(self):
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

    def buildListStore(self, queryResult):
        trackTreeStore = makeTrackTreeStore(self.app.catalog, queryResult)
        self.tv.set_model(trackTreeStore)
        self.tv.expand_all()

    def buildButtons(self):
        # Buttons
        hbox = gtk.HBox(False, 10)
        btn = gtk.Button('Close', gtk.STOCK_CLOSE)
        btn.connect('clicked', self.on_close)
        hbox.pack_end(btn, expand=False, fill=False)

        btn = gtk.Button('Browse Recording')
        btn.connect('clicked', self.browse_recording)
        hbox.pack_end(btn, expand=False, fill=False)
        self.active_on_row_selected.append(btn)

        return hbox

    def browse_recording(self, button):
        recordingId = self.get_selection()
        webbrowser.open(mbcat.catalog.Catalog.recordingUrl + recordingId)

    def on_row_select(self, treeview):
        model, iter = self.tv.get_selection().get_selected()
        if len(model.get_path(iter)) > 1:
            # if a recording is selected
            QueryResultsDialog.on_row_select(self, treeview)
            self.row_widgets_set_sensitive(True)
        else:
            # a medium is selected
            self.row_widgets_set_sensitive(False)

class ReleaseDistanceDialog(QueryResultsDialog):
    row_contains = 'Comparison'
    def __init__(self, parentWindow, app, queryResult,
            message='Release Comparison Results'):
        self.parentWindow = parentWindow
        self.app = app

        QueryResultsDialog.__init__(self, parentWindow, app,
            queryResult, message)

    def buildTreeView(self):
        self.tv = gtk.TreeView()
        for i, (label, textWidth, xalign) in enumerate([
                ('Distance', 4, 1.0),
                ('Left', 32, 0),
                ('Right', 32, 0),
            ]):
            cell = gtk.CellRendererText()
            cell.set_property('xalign', xalign)
            cell.set_property('ellipsize', pango.ELLIPSIZE_END)
            cell.set_property('width-chars', textWidth)
            col = gtk.TreeViewColumn(label, cell)
            col.add_attribute(cell, 'text', i+2)
            col.set_resizable(True)
            self.tv.append_column(col)
        self.tv.set_search_column(1) # search by left

    def buildListStore(self, queryResult):
        # make the list store
        resultListStore = gtk.ListStore(str, str, str, str, str)
        for distance, left, right in queryResult[:200]:
            resultListStore.append((
                left,
                right,
                distance,
                self.app.catalog.getReleaseSortStr(left),
                self.app.catalog.getReleaseSortStr(right)))
        self.tv.set_model(resultListStore)

    def buildButtons(self):
        # Buttons
        hbox = gtk.HBox(False, 10)
        btn = gtk.Button('Close', gtk.STOCK_CLOSE)
        btn.connect('clicked', self.on_close)
        hbox.pack_end(btn, expand=False, fill=False)

        # TODO could use gtk.STOCK_CONNECT here
        btn = gtk.Button('Select Right')
        btn.connect('clicked', self.select_release, 1)
        hbox.pack_end(btn, expand=False, fill=False)
        self.active_on_row_selected.append(btn)

        btn = gtk.Button('Select Left')
        btn.connect('clicked', self.select_release, 0)
        hbox.pack_end(btn, expand=False, fill=False)
        self.active_on_row_selected.append(btn)

        return hbox

    def buildRowInfoWidgets(self, vbox):
        # Info on the selected row
        hbox = gtk.HBox(10, False)
        self.leftInfo = gtk.Label()
        self.leftInfo.set_ellipsize(pango.ELLIPSIZE_END)
        hbox.pack_start(self.leftInfo, expand=True, fill=True)
        self.vsLbl = gtk.Label(' <-> ')
        hbox.pack_start(self.vsLbl, expand=False, fill=False)
        self.rightInfo = gtk.Label()
        self.rightInfo.set_ellipsize(pango.ELLIPSIZE_END)
        hbox.pack_start(self.rightInfo, expand=True, fill=True)
        vbox.pack_end(hbox, expand=False)

    def on_row_select(self, treeview):
        model, it = self.tv.get_selection().get_selected()
        leftId = model.get_value(it, 0)
        rightId = model.get_value(it, 1)

        if leftId and rightId:
            self.leftInfo.set_text(leftId)
            self.rightInfo.set_text(rightId)
            _log.info(self.row_contains+' '+leftId+' <-> '+rightId+' selected')
        self.row_widgets_set_sensitive(True)

    def select_release(self, button, right):
        """
        right: 0 for left, 1 for right
        """
        model, it = self.tv.get_selection().get_selected()

        releaseId = model.get_value(it, right) if it else None
        self.app.setSelectedRow(self.app.getReleaseRow(releaseId))

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

class CheckOutHistoryDialog(QueryResultsDialog):
    row_contains = 'Event'

    def __init__(self,
            parentWindow,
            app,
            releaseId,
            message='Release Results',
            ):
        self.releaseId = releaseId
        QueryResultsDialog.__init__(self, parentWindow, app, releaseId, message)
        self.updateButtons()

    def on_row_select(self, treeview):
        pass

    def buildTreeView(self):
        self.tv = gtk.TreeView()
        for i, (label, textWidth) in enumerate(
            [('Check Out', 20),
            ('Check In', 20),
            ('Borrower', 10),
            ]):
            cell = gtk.CellRendererText()
            cell.set_property('xalign', 0)
            cell.set_property('ellipsize', pango.ELLIPSIZE_END)
            cell.set_property('width-chars', textWidth)
            col = gtk.TreeViewColumn(label, cell)
            col.add_attribute(cell, 'text', i)
            col.set_resizable(True)
            self.tv.append_column(col)

    def buildListStore(self, releaseId):
        # make the list store
        resultListStore = gtk.ListStore(str, str, str)

        for event in self.app.catalog.getCheckOutHistory(self.releaseId):
            if len(event) == 2:
                resultListStore.append((
                    mbcat.decodeDate(event[0]),
                    '',
                    event[1],
                    ))
            elif len(event) == 1:
                resultListStore.append((
                    '',
                    mbcat.decodeDate(event[0]),
                    '',
                    ))
        self.tv.set_model(resultListStore)

    def update(self):
        self.buildListStore(self.releaseId)
        self.updateButtons()

    def check_out(self, button):
        self.app.checkOut(releaseId=self.releaseId)
        self.update()

    def check_in(self, button):
        self.app.checkIn(releaseId=self.releaseId)
        self.update()

    def buildButtons(self):
        # Buttons
        hbox = gtk.HBox(False, 10)
        btn = gtk.Button('Close', gtk.STOCK_CLOSE)
        btn.connect('clicked', self.on_close)
        hbox.pack_end(btn, expand=False, fill=False)

        self.checkInBtn = gtk.Button('Check In')
        self.checkInBtn.connect('clicked', self.check_in)
        hbox.pack_end(self.checkInBtn, expand=False, fill=False)

        self.checkOutBtn = gtk.Button('Check Out')
        self.checkOutBtn.connect('clicked', self.check_out)
        hbox.pack_end(self.checkOutBtn, expand=False, fill=False)

        return hbox

    def updateButtons(self):
        if self.app.catalog.getCheckOutStatus(self.releaseId):
            self.checkInBtn.set_sensitive(True)
            self.checkOutBtn.set_sensitive(False)
        else:
            self.checkInBtn.set_sensitive(False)
            self.checkOutBtn.set_sensitive(True)

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
        self.sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)

        self.tv = gtk.TreeView()
        for i, (label, xalign, textWidth) in enumerate(
            [('Title', 0, 32),
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

        self.lt = gtk.Table(2, 4, homogeneous=False)

        r = 0
        self.releaseIdLbl = gtk.Label()
        self.releaseIdLbl.set_ellipsize(pango.ELLIPSIZE_END)
        self.lt.attach(self.releaseIdLbl, 0, 2, r, r+1) # span two columns
        r += 1

        l = gtk.Label('Release ID:')
        l.set_alignment(0, 0.5)
        self.lt.attach(l, 0, 1, r, r+1)
        hbox = gtk.HBox()
        self.clipboard = gtk.clipboard_get(gtk.gdk.SELECTION_CLIPBOARD)
        self.releaseIdCopyBtn = gtk.Button(stock=gtk.STOCK_COPY)
        self.releaseIdCopyBtn.connect('clicked', self.copyReleaseId)
        #self.releaseIdBtn.show()
        #self.vb.pack_start(self.releaseIdBtn, expand=False, fill=False)
        hbox.pack_start(self.releaseIdCopyBtn)
        self.releaseIdBrowseBtn = gtk.Button('Browse')
        self.releaseIdBrowseBtn.connect('clicked', self.browse_release)
        hbox.pack_start(self.releaseIdBrowseBtn)
        self.lt.attach(hbox, 1, 2, r, r+1)
        r += 1

        l = gtk.Label('Last Refresh:')
        l.set_alignment(0, 0.5)
        self.lt.attach(l, 0, 1, r, r+1)
        self.lastRefreshLbl = gtk.Label()
        self.lt.attach(self.lastRefreshLbl, 1, 2, r, r+1)
        r += 1

        l = gtk.Label('First Added:')
        l.set_alignment(0, 0.5)
        self.lt.attach(l, 0, 1, r, r+1)
        self.firstAddedLbl = gtk.Label()
        self.lt.attach(self.firstAddedLbl, 1, 2, r, r+1)
        r += 1

        l = gtk.Label('Last Listened:')
        l.set_alignment(0, 0.5)
        self.lt.attach(l, 0, 1, r, r+1)
        self.lastListenedLbl = gtk.Label()
        self.lt.attach(self.lastListenedLbl, 1, 2, r, r+1)
        r += 1

        l = gtk.Label('Rating:')
        l.set_alignment(0, 0.5)
        self.lt.attach(l, 0, 1, r, r+1)
        self.ratingLbl = buildRatingComboBox()
        self.ratingLbl.connect('changed', self.setRating)
        self.lt.attach(self.ratingLbl, 1, 2, r, r+1)
        r += 1

        l = gtk.Label('On-hand Count:')
        l.set_alignment(0, 0.5)
        self.lt.attach(l, 0, 1, r, r+1)
        adjustment = gtk.Adjustment(
            value=1,
            lower=0,
            upper=1000,
            step_incr=1)
        self.countSpinButton = gtk.SpinButton(adjustment)
        adjustment.connect('value_changed', self.setCount)
        self.lt.attach(self.countSpinButton, 1, 2, r, r+1)
        r += 1

        l = gtk.Label('Checked Out?')
        l.set_alignment(0, 0.5)
        self.lt.attach(l, 0, 1, r, r+1)
        self.checkOutLbl = gtk.Label()
        self.lt.attach(self.checkOutLbl, 1, 2, r, r+1)
        r += 1

        self.lt.set_row_spacings(10)
        self.lt.set_col_spacing(0, 10)
        self.lt.show_all()

        self.pack_start(self.lt, expand=False, fill=False)
        self.lt.show()

    def copyReleaseId(self, button):
        self.clipboard.set_text(self.releaseId)

    def browse_release(self, button):
        webbrowser.open(mbcat.catalog.Catalog.releaseUrl + self.releaseId)

    def setRating(self, combobox):
        model = combobox.get_model()
        index = combobox.get_active()
        text = model[index][0]
        self.catalog.setRating(self.releaseId, text)

    def setCount(self, spinbutton):
        self.catalog.setCopyCount(self.releaseId,
            self.countSpinButton.get_value_as_int())

    def update(self, releaseId):
        if self.get_visible():
            self._update(releaseId)

    def _update(self, releaseId):
        if not releaseId:
            return
        self.releaseId = releaseId # for the UUID copy button
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

        trackTreeStore = makeTrackTreeStore(self.catalog, releaseId)
        self.tv.set_model(trackTreeStore)
        self.tv.expand_all()

        self.releaseIdLbl.set_label(releaseId)

        lastRefresh = self.catalog.getMetaTime(releaseId)
        lastRefresh = mbcat.decodeDate(lastRefresh) if lastRefresh else '-'
        self.lastRefreshLbl.set_text(lastRefresh)

        firstAdded = self.catalog.getFirstAdded(releaseId)
        firstAdded = mbcat.decodeDate(firstAdded) if firstAdded else '-'
        self.firstAddedLbl.set_text(firstAdded)

        lastListened = self.catalog.getLastListened(releaseId)
        lastListened = mbcat.decodeDate(lastListened) if lastListened else '-'
        self.lastListenedLbl.set_text(lastListened)

        rating = self.catalog.getRating(releaseId)
        self.ratingLbl.set_active(int(rating) if rating and rating != 'None' else 0)

        count = self.catalog.getCopyCount(releaseId)
        self.countSpinButton.set_value(int(count) if count and count != 'None' else 0)

        checkedOut = self.catalog.getCheckOutStatus(releaseId)
        self.checkOutLbl.set_text(checkedOut[1] if checkedOut else 'No')

class MBCatGtk:
    """
    A GTK interface for managing a music collection using MusicBrainz.
    """
    __name__ = 'MusicBrainz Catalog GTK Gui'
    __version__ = mbcat.catalog.__version__
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
        except sqlite3.OperationalError as e:
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
        self.CatalogTask(self,
            mbcat.dialogs.PulseDialog(
                self.window,
                mbcat.dialogs.ThreadedCall(self.catalog.vacuum))).start()

    class CatalogTask(threading.Thread):
        """
        This is a thread that runs a specified task and then refreshes the
        window.
        """
        def __init__(self, app, task):
            threading.Thread.__init__(self)
            self.app = app
            self.task = task

        def run(self):
            row = self.app.getSelectedRow()
            self.task.start()
            self.task.join()
            self.app.refreshView()
            if row:
                self.app.setSelectedRow(row)

    class CheckTask(threading.Thread):
        def __init__(self, window, app, result_viewer, task):
            threading.Thread.__init__(self)
            self.window = window
            self.app = app
            self.result_viewer = result_viewer
            self.task = task
        def run(self):
            self.task.start()
            self.task.join()
            self.result_viewer(self.window, self.app, self.task.task.result)

    def menuCatalogRebuild(self, widget):
        self.CatalogTask(self,
            mbcat.dialogs.ProgressDialog(self.window,
                self.catalog.rebuildCacheTables(self.catalog))).start()

    def menuCatalogGetSimilar(self, widget):
        # TODO could implement a simple dialog here that asks for the limit on
        # the distance of neighbors to compare and the number of results to keep
        self.CheckTask(self.window, self, ReleaseDistanceDialog,
            mbcat.dialogs.ProgressDialog(self.window,
                self.catalog.checkLevenshteinDistances(self.catalog, 2))).start()

    def format_comment(self, column, cell, model, it, field):
        row = model.get_value(it, 0)
        cell.set_property('text', 'OK')

    def menu_release_items_set_sensitive(self, sens=True):
        """Make menu items specific to releases active."""
        for menuitem in self.menu_release_items:
            menuitem.set_sensitive(sens)

    def on_row_activate(self, treeview, path, column):
        self.detailpane.show()
        self.updateDetailPane()
        self.detailPaneCheckItem.set_active(True)

    def on_row_select(self, treeview):
        self.menu_release_items_set_sensitive(True)
        model, it = treeview.get_selection().get_selected()
        relId = model.get_value(it, 0)
        self.updateDetailPane()
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

    def refreshView(self, widget=None):
        self.makeListStore()
        self.updateDetailPane()
        self.updateStatusBar()

    def scrollToSelected(self, widget=None):
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
        msg = ('Showing %d out of %d releases' % \
            (len(self.releaseList), len(self.catalog)))
        self.statusbar.push(self.context_id, msg)

    def toggleDetailPane(self, widget):
        if widget.active:
            if not self.getSelection():
                self.setSelectedRow(0)
            self.detailpane.show()
            self.updateDetailPane()
            self.scrollToSelected() # TODO this doesn't work
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

    def _addRelease(self, releaseId, parentWindow):
        class AddReleaseTask(mbcat.dialogs.ThreadedCall):
            def __init__(self, app, c, fun, *args):
                mbcat.dialogs.ThreadedCall.__init__(self, fun, *args)
                self.app = app
                self.c = c

            def run(self):
                try:
                    mbcat.dialogs.ThreadedCall.run(self)
                except mb.ResponseError as e:
                    ErrorDialog(self.app.window, str(e) + ". Bad release ID?")
                    return
                except mb.NetworkError as e:
                    ErrorDialog(self.app.window, "Unable to connection.")
                    return
                self.app.makeListStore()
                self.app.setSelectedRow(self.app.getReleaseRow(releaseId))

        if releaseId in self.catalog:
            ErrorDialog(parentWindow, 'Release already exists')
            return

        mbcat.dialogs.PulseDialog(parentWindow,
            AddReleaseTask(self, self.catalog,
                self.catalog.addRelease, releaseId)).start()

    def addRelease(self, widget):
        entry = TextEntry(self.window, 'Enter Release ID')
        if entry:
            self._addRelease(entry, self.window)

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
        _log.info("Deleted %s '%s'" % (releaseId, relTitle))
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
        TrackListDialog(self.window, self, releaseId)

    def checkOutDialog(self, widget=None):
        CheckOutHistoryDialog(self.window, self, self.getSelection())

    def checkOut(self, widget=None, releaseId=None):
        if not releaseId:
            releaseId = self.getSelection()

        checkOutEvents = self.catalog.getCheckOutEvents(releaseId)
        checkInEvents = self.catalog.getCheckInEvents(releaseId)

        borrower = TextEntry(self.window, "Borrower: ")
        if not borrower:
            return

        date = TextEntry(self.window,
            "Lend date  (" + mbcat.dateFmtUsr + "): ",
            default=time.strftime(mbcat.dateFmtStr))
        self.catalog.addCheckOutEvent(releaseId, borrower, mbcat.encodeDate(date))
        self.updateDetailPane()

    def checkIn(self, widget=None, releaseId=None):
        if not releaseId:
            releaseId = self.getSelection()

        if not self.catalog.getCheckOutStatus(releaseId):
            ErrorDialog(self.window, 'Release is not checked out.')
            return

        date = TextEntry(self.window,
            "Return date (" + mbcat.dateFmtUsr + "): ",
            default=time.strftime(mbcat.dateFmtStr))
        if not date:
            date = time.time()
        self.catalog.addCheckInEvent(releaseId,
            mbcat.encodeDate(date))
        self.updateDetailPane()

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
        dateStr = DateEntry(self.window,
            'Choose a listen date',
            time.strftime(mbcat.dateFmtStr))
        if dateStr:
            date = float(mbcat.encodeDate(dateStr))
            self.catalog.addListenDate(releaseId, date)
            self.updateDetailPane()

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
        BarcodeSearchDialog(self.window, self)

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
        entry = TextEntry(self.window, 'Enter release group search terms:')
        if not entry:
            return

        mbcat.dialogs.PulseDialog(self.window,
            QueryTask(self.window, self, GroupQueryResultsDialog,
                mb.search_release_groups,
                releasegroup=entry)).start()

    def webserviceRelease(self, widget):
        entry = TextEntry(self.window, 'Enter release search terms')
        if not entry:
            return
        mbcat.dialogs.PulseDialog(self.window,
            QueryTask(self.window, self, QueryResultsDialog,
                mb.search_releases,
                release=entry, limit=self.searchResultsLimit)).start()

    def webserviceBarcode(self, widget):
        BarcodeQueryDialog(self.window, self)

    def webserviceCatNo(self, widget):
        entry = TextEntry(self.window, 'Enter search catalog number:')
        if not entry:
            return
        mbcat.dialogs.PulseDialog(self.window,
            QueryTask(self.window, self, QueryResultsDialog,
                mb.search_releases,
                catno=entry, limit=self.searchResultsLimit)).start()

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
                QueryResultsDialog(self.window, self, result['disc'])
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
        submenuitem.connect('activate', self.toggleDetailPane)
        menu.append(submenuitem)
        self.detailPaneCheckItem = submenuitem # save a reference

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

        ## Check Out/In
        submenuitem = gtk.MenuItem('Check Out/In')
        submenuitem.connect('activate', self.checkOutDialog)
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

    def makeListStore(self, ):
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
