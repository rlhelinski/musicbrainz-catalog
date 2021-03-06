#!/usr/bin/env python

from __future__ import print_function
from __future__ import unicode_literals
import logging
logging.basicConfig(level=logging.INFO)
import threading
import gobject
import glib
import gtk
import pango
import mbcat
import mbcat.catalog
import mbcat.barcode
import mbcat.dialogs
import mbcat.digital
import mbcat.userprefs
import musicbrainzngs as mb
import argparse
import time
import datetime
import webbrowser
import sqlite3
import os

# Initialize GTK's threading engine
gobject.threads_init()

_log = logging.getLogger("mbcat")

default_dialog_size = (500, 300)

class PreferencesDialog(gtk.Window):
    def __init__(self, parentWindow, prefs, catalog):
        self.prefs = prefs
        self.catalog = catalog
        self.parentWindow = parentWindow
        self.checkDigitalPathRoots()

        gtk.Window.__init__(self)
        self.set_transient_for(parentWindow)
        self.set_destroy_with_parent(True)
        self.set_title('Preferences')
        self.buildWidgets()
        self.show()

    def buildWidgets(self):
        self.notebook = gtk.Notebook()
        self.add(self.notebook)

        ####
        tablbl = gtk.Label('Digital Paths')
        digvbox = gtk.VBox(False, 0)
        #digvbox.set_border_width(10)
        self.notebook.append_page(digvbox, tablbl)

        pathRootFrame = gtk.Frame('Path Roots')
        pathRootFrame.set_border_width(10)
        digvbox.pack_start(pathRootFrame, True, True)

        digRootFrameVBox = gtk.VBox(False, 10)
        digRootFrameVBox.set_border_width(10)
        pathRootFrame.add(digRootFrameVBox)

        digpathsw = gtk.ScrolledWindow()
        digpathsw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        digRootFrameVBox.pack_start(digpathsw, True, True)

        self.digpathtv = gtk.TreeView()
        self.digpathtv.set_headers_visible(False)
        self.digpathtv.set_size_request(500, 150)
        digpathsw.add(self.digpathtv)

        self.pathmodel = gtk.ListStore(str, str)

        for i, (label, textWidth) in enumerate(
            [('Root Path', 60),
            ]):
            cell = gtk.CellRendererText()
            cell.set_property('editable', True)
            cell.connect('edited', self.edited_path_cb, self.pathmodel)
            cell.set_property('xalign', 0)
            cell.set_property('ellipsize', pango.ELLIPSIZE_END)
            cell.set_property('width-chars', textWidth)
            col = gtk.TreeViewColumn(label, cell)
            col.add_attribute(cell, 'text', i+1)
            col.set_resizable(True)
            self.digpathtv.append_column(col)

        self.digpathtv.connect('cursor-changed', self.on_digpath_select)

        self.buildDigPathTV()

        digpathbtns = gtk.HBox()
        digRootFrameVBox.pack_start(digpathbtns, False, False)

        addbtn = gtk.Button(stock=gtk.STOCK_ADD)
        addbtn.connect('clicked', self.on_rootpath_add)
        digpathbtns.pack_start(addbtn, False, False)

        delbtn = gtk.Button(stock=gtk.STOCK_REMOVE)
        delbtn.connect('clicked', self.on_rootpath_del)
        digpathbtns.pack_start(delbtn, False, False)

        editbtn = gtk.Button(stock='mbcat-edit-path')
        editbtn.connect('clicked', self.on_rootpath_edit)
        digpathbtns.pack_start(editbtn, False, False)

        digspecframe = gtk.Frame('Release Path Spec.')
        #digspecframe.set_border_width(10)
        digRootFrameVBox.pack_start(digspecframe, False, False)
        digspecentryvbox = gtk.VBox(False, 10)
        digspecframe.add(digspecentryvbox)
        digspecentryvbox.set_border_width(10)
        self.digspecentry = gtk.Entry()
        self.digspecentry.set_sensitive(False)
        self.digspecentry.connect('activate', self.on_specentry_activate)
        digspecentryvbox.add(self.digspecentry)

        defPathSpecFrame = gtk.Frame('Default Path Spec.')
        defPathSpecFrame.set_border_width(10)
        digvbox.pack_start(defPathSpecFrame, False, False)

        defPathSpecFrameVBox = gtk.VBox(False, 10)
        defPathSpecFrameVBox.set_border_width(10)
        defPathSpecFrame.add(defPathSpecFrameVBox)
        entry = gtk.Entry()
        entry.set_text(self.prefs.defaultPathSpec)
        entry.connect('activate', self.on_defaultPathSpec_activate)
        defPathSpecFrameVBox.pack_start(entry, False, False)


        ####
        tablbl = gtk.Label('MusicBrainz.org')
        mbvbox = gtk.VBox(False, 10)
        self.notebook.append_page(mbvbox, tablbl)

        serverframe = gtk.Frame('Servers')
        serverframe.set_border_width(10)
        mbvbox.pack_start(serverframe, False, False)

        mbprefs = gtk.Table(2, 4, homogeneous=False)
        mbprefs.set_border_width(10)
        serverframe.add(mbprefs)

        r = 0
        lbl = gtk.Label('Host Name :')
        mbprefs.attach(lbl, 0, 1, r, r+1)
        entry = gtk.Entry()
        entry.set_text(self.prefs.getHostName())
        entry.connect('activate', self.on_hostname_activate)
        mbprefs.attach(entry, 1, 2, r, r+1)

        r += 1
        lbl = gtk.Label('Cover Art Archive :')
        mbprefs.attach(lbl, 0, 1, r, r+1)
        entry = gtk.Entry()
        entry.set_text(self.prefs.getCAAHostName())
        entry.connect('activate', self.on_caa_hostname_activate)
        mbprefs.attach(entry, 1, 2, r, r+1)

        acctframe = gtk.Frame('User Account')
        acctframe.set_border_width(10)
        mbvbox.pack_start(acctframe, False, False)

        mbprefs = gtk.Table(2, 4, homogeneous=False)
        mbprefs.set_border_width(10)
        acctframe.add(mbprefs)

        r = 0
        lbl = gtk.Label('Username :')
        mbprefs.attach(lbl, 0, 1, r, r+1)
        entry = gtk.Entry()
        entry.set_text(self.prefs.username)
        entry.connect('activate', self.on_username_activate)
        mbprefs.attach(entry, 1, 2, r, r+1)

        ####
        self.notebook.show_all()

    def buildDigPathTV(self):
        for path_id, path_dict in sorted(self.prefs.pathRoots.items(),
                    key=lambda x: x[1]):
            self.pathmodel.append((path_id, path_dict['path']))
        self.digpathtv.set_model(self.pathmodel)
        self.digpathtv.expand_all()

    def edited_path_cb(self, cell, path, new_text, user_data):
        path_id = self.pathmodel[path][0]
        old_text = self.pathmodel[path][1]
        if new_text == old_text:
            return
        self.prefs.editPathRoot(path_id, new_text)
        self.pathmodel[path][1] = new_text
        return

    def get_digpath_selected(self):
        model, it = self.digpathtv.get_selection().get_selected()
        if not it:
            return (None, None)
        return (model.get_value(it, 0), model.get_value(it, 1))

    def on_digpath_select(self, treeview):
        path_id, path = self.get_digpath_selected()
        if not path_id:
            return
        self.digspecentry.set_sensitive(True)
        pathspec = self.prefs.getPathRootSpec(path_id)
        self.digspecentry.set_text(pathspec)

    def on_specentry_activate(self, entry):
        newspec = entry.get_text()
        path_id, path = self.get_digpath_selected()
        self.prefs.setRootPathSpec(path_id, newspec)

    def on_defaultPathSpec_activate(self, entry):
        newspec = entry.get_text()
        self.prefs.setDefaultPathSpec(newspec)

    def choose_rootpath(self, parent=None):
        dialog = gtk.FileChooserDialog(
            title='Choose path to digital copy',
            parent=parent if parent else self,
            action=gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
            buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                gtk.STOCK_OPEN, gtk.RESPONSE_OK))
        dialog.set_default_response(gtk.RESPONSE_OK)
        # TODO use gtk.FileChooser.set_current_folder and add a named argument
        response = dialog.run()
        if response != gtk.RESPONSE_OK:
            dialog.destroy()
            return

        path = dialog.get_filename()
        dialog.destroy()
        return path

    def on_rootpath_add(self, button):
        path = self.choose_rootpath()
        path_id = self.prefs.addPathRoot(path)
        self.pathmodel.append((path_id,path))

    def on_rootpath_del(self, button):
        path_id, path = self.get_digpath_selected()
        if ConfirmDialog(self.parentWindow,
                'Are you sure you want to delete "%s"?' % path,
                buttons=gtk.BUTTONS_YES_NO, expect=gtk.RESPONSE_YES,
                default=gtk.RESPONSE_NO):
            self.prefs.delPathRoot(path_id)
            if ConfirmDialog(self.parentWindow,
                    'Also delete associations with "%s"?' % path,
                    buttons=gtk.BUTTONS_YES_NO, expect=gtk.RESPONSE_YES,
                    default=gtk.RESPONSE_YES):
                self.catalog.deleteDigitalPathRoot(path_id)
            model, it = self.digpathtv.get_selection().get_selected()
            self.pathmodel.remove(it)

    def on_rootpath_edit(self, button):
        path_id, old_text = self.get_digpath_selected()
        new_text = self.choose_rootpath()
        if new_text == old_text:
            return
        self.prefs.editPathRoot(path_id, new_text)
        self.pathmodel[path_id][1] = new_text

    def on_username_activate(self, entry):
        newusername = entry.get_text()
        self.prefs.setUserName(newusername)

    def on_hostname_activate(self, entry):
        newhostname = entry.get_text()
        self.prefs.setHostName(newhostname)

    def on_caa_hostname_activate(self, entry):
        newhostname = entry.get_text()
        self.prefs.setCAAHostName(newhostname)

    def checkDigitalPathRoots(self):
        for root_id, path_dict in self.prefs.pathRoots.items():
            if not os.path.isdir(path_dict['path']):
                msg = 'Path root %s : %s not found' % (root_id,
                        path_dict['path'])
                _log.error(msg)
                if ConfirmDialog(self.parentWindow,
                        msg+'\nWould you like to browse for a new path?',
                        buttons=gtk.BUTTONS_YES_NO, expect=gtk.RESPONSE_YES):
                    newpath = self.choose_rootpath(self.parentWindow)
                    if newpath and os.path.isdir(newpath):
                        self.prefs.editPathRoot(root_id, newpath)

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

def DateEntry(parent, message, default=None):
    """
    Display a dialog with a text entry.
    Returns the text, or None if canceled.
    """
    if not default:
        default = datetime.datetime.now()
    d = gtk.MessageDialog(parent,
            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
            gtk.MESSAGE_QUESTION,
            gtk.BUTTONS_OK_CANCEL,
            message)
    entry = gtk.Calendar()
    entry.select_month(default.month-1, default.year)
    entry.select_day(default.day)
    d.vbox.pack_start(entry)

    # Hour, Minute, Second Spinners
    hbox = gtk.HBox(False, 0)

    vbox2 = gtk.VBox(False, 0)
    hbox.pack_start(vbox2, True, True, 5)

    label = gtk.Label("Hour :")
    label.set_alignment(0, 0.5)
    vbox2.pack_start(label, False, True, 0)

    adj = gtk.Adjustment(default.hour, 0, 23, 1, 12, 0)
    hour_spinner = gtk.SpinButton(adj, 0, 0)
    hour_spinner.set_wrap(True)
    vbox2.pack_start(hour_spinner, False, True, 0)

    vbox2 = gtk.VBox(False, 0)
    hbox.pack_start(vbox2, True, True, 5)

    label = gtk.Label("Minute :")
    label.set_alignment(0, 0.5)
    vbox2.pack_start(label, False, True, 0)

    adj = gtk.Adjustment(default.minute, 0, 59, 1, 15, 0)
    minute_spinner = gtk.SpinButton(adj, 0, 0)
    minute_spinner.set_wrap(True)
    vbox2.pack_start(minute_spinner, False, True, 0)

    vbox2 = gtk.VBox(False, 0)
    hbox.pack_start(vbox2, True, True, 5)

    label = gtk.Label("Second :")
    label.set_alignment(0, 0.5)
    vbox2.pack_start(label, False, True, 0)

    adj = gtk.Adjustment(default.second, 0, 59, 1, 15, 0)
    second_spinner = gtk.SpinButton(adj, 0, 0)
    second_spinner.set_wrap(True)
    vbox2.pack_start(second_spinner, False, True, 0)

    d.vbox.pack_start(hbox, True, True, 5)
    d.vbox.show_all()

    d.set_default_response(gtk.RESPONSE_OK)

    r = d.run()
    # have to get the text before we destroy the gtk.Entry
    year, month, day = entry.get_date()
    hour, minute, second = hour_spinner.get_value_as_int(), \
            minute_spinner.get_value_as_int(), \
            second_spinner.get_value_as_int()
    # From http://www.pygtk.org/pygtk2reference/class-gtkcalendar.html#method-gtkcalendar--get-date
    # Note that month is zero-based (i.e it allowed values are 0-11) while
    # selected_day is one-based (i.e. allowed values are 1-31).
    entered_datetime = datetime.datetime(
            year,
            month+1,
            day,
            hour,
            minute,
            second)
    d.destroy()
    if r == gtk.RESPONSE_OK:
        return entered_datetime
    else:
        return None

def PurchaseInfoEntry(parent,
        message='Enter purchase info:'):
    """
    Display a dialog with a text entry.
    Returns the text, or None if canceled.
    """
    # TODO this should have hour, minute and second added to be consistent with
    # other date entries
    # ELSE could drop multiple purchases when deleting
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
    val = {'date': float(mbcat.encodeDateTime(
            datetime.datetime(year, month+1, day))),
        'vendor' : vendorEntry.get_text().decode('utf8'),
        'price' : priceEntry.get_value(),
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
    d.set_size_request(*default_dialog_size)

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
    d.set_size_request(*default_dialog_size)

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

        key, mod = gtk.accelerator_parse('Escape')
        accel = gtk.AccelGroup()
        accel.connect_group(key, mod, 0, lambda w,x,y,z: self.window.destroy())
        self.window.add_accel_group(accel)

        vbox = gtk.VBox(False, 10)

        prompt = gtk.Label(message)
        vbox.pack_start(prompt, expand=True, fill=True)

        self.hint = gtk.Label('')
        vbox.pack_start(self.hint, expand=True, fill=True)

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
        suggestion = ('UPC check digit: %d' % \
            mbcat.barcode.UPC.checksum_upc_a(entry_text)) \
            if len(entry_text) == 11 else \
            ('EAN check digit: %d' % \
            mbcat.barcode.EAN._checksum(entry_text)) \
            if len(entry_text) == 12 else ''
        self.hint.set_text(suggestion)
        self.checkIndicator.set_from_stock(
                gtk.STOCK_APPLY if \
                    mbcat.barcode.UPC.check_upc_a(entry_text) \
                    or
                    mbcat.barcode.EAN._checksum(entry_text) \
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
    combobox.set_active(int(default) if default and default != 'None' else 0)
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

def ConfirmDialog(parent, message, type=gtk.MESSAGE_QUESTION,
        buttons=gtk.BUTTONS_OK_CANCEL, expect=gtk.RESPONSE_OK,
        default=gtk.RESPONSE_OK):
    d = gtk.MessageDialog(parent,
            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
            gtk.MESSAGE_QUESTION,
            buttons,
            message)
    d.set_default_response(default)

    r = d.run()
    d.destroy()
    return (r == expect)

class QueryTask(mbcat.dialogs.ThreadedCall):
    def __init__(self, window, app, result_viewer, fun, *args, **kwargs):
        mbcat.dialogs.ThreadedCall.__init__(self, fun, *args, **kwargs)
        self.window = window
        self.app = app
        self.result_viewer = result_viewer
    def run(self):
        try:
            mbcat.dialogs.ThreadedCall.run(self)
        except mb.ResponseError as e:
            # TODO this manipulates GTK from another thread (BAD)
            ErrorDialog(self.window, 'MusicBrainz response error: '+str(e))
            # TODO in case of get_releases_by_discid, call askBrowseSubmission()

        if not self.result:
            # TODO this manipulates GTK from another thread (BAD)
            ErrorDialog(self.window, 'No results found for "%s"' % str(kwargs))
        else:
            gobject.idle_add(startResultViewer, self.result_viewer,
                    self.window, self.app, self.result)
            # TODO can implement this with a killParent flag to __init__
            #if type(self.app) == BarcodeQueryDialog:
                #self.window.destroy()

class DiscQueryTask(QueryTask):
    def __init__(self, window, app, result_viewer, submission_url,
            fun, *args, **kwargs):
        mbcat.dialogs.ThreadedCall.__init__(self, fun, *args, **kwargs)
        self.window = window
        self.app = app
        self.result_viewer = result_viewer
        self.submission_url = submission_url
    def run(self):
        try:
            mbcat.dialogs.ThreadedCall.run(self)
        except mb.ResponseError as e:
            self.result = e
        else:
            if self.result.get("disc"):
                _log.info('Showing query results for disc ID "%s"'\
                    %self.result['disc']['id'])
                self.result_viewer(self.window, self.app, self.submission_url,
                        self.result['disc'])
                # TODO can implement this with a killParent flag to __init__
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
        self.window.set_size_request(*default_dialog_size)

        key, mod = gtk.accelerator_parse('Escape')
        accel = gtk.AccelGroup()
        accel.connect_group(key, mod, 0, lambda w,x,y,z: self.window.destroy())
        self.window.add_accel_group(accel)

        self.active_on_row_selected = []

        vbox = gtk.VBox(False, 10)

        # Keep reference to catalog for later
        self.app = app
        self.parentWindow = parentWindow

        # Keep reference to queryResult
        self.queryResult = queryResult
        self.buildWidgets(vbox, self.queryResult)

        self.window.add(vbox)
        self.window.show_all()

    def buildWidgets(self, vbox, queryResult):
        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)

        self.buildTreeView()
        self.buildListStore(queryResult)

        self.tv.connect('row-activated', self.on_row_activate)
        self.tv.connect('cursor-changed', self.on_row_select)
        self.tv.connect('unselect-all', self.on_unselect_all)
        sw.add(self.tv)
        vbox.pack_start(sw, expand=True, fill=True)

        hbox = self.buildButtons()
        self.row_widgets_set_sensitive(False)
        vbox.pack_end(hbox, expand=False, fill=False)

        self.buildRowInfoWidgets(vbox)

    def buildTreeView(self):
        self.tv = gtk.TreeView()
        cell = gtk.CellRendererPixbuf()
        col = gtk.TreeViewColumn('Have', cell)
        col.add_attribute(cell, 'stock-id', 1)
        self.tv.append_column(col)
        for i, (label, textWidth) in enumerate([
            ('Artist', 20),
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
            col.add_attribute(cell, 'text', i+2)
            col.set_resizable(True)
            self.tv.append_column(col)
        self.tv.set_search_column(1) # search by Artist

    def buildListStore(self, queryResult):
        # make the list store
        resultListStore = gtk.ListStore(str, str, str, str, str, str, str, str, str)
        for release in queryResult['release-list']:
            resultListStore.append((
                release['id'],
                gtk.STOCK_APPLY if release['id'] in self.app.catalog else '',
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
        # function for use with idle_add() to mark this release as part of the
        # catalog
        def doneFun(ref):
            ref.buildListStore(ref.queryResult)
            return False

        self.app._addRelease(self.get_selection(), self.window, doneFun, self)
        # TODO error check necessary?

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

class DiscQueryResultsDialog(QueryResultsDialog):
    def __init__(self,
            parentWindow,
            app,
            submission_url,
            queryResult,
            message='Disc Results',
        ):
        self.submission_url = submission_url
        QueryResultsDialog.__init__(self, parentWindow, app, queryResult,
                message)

    def buildButtons(self):
        hbox = QueryResultsDialog.buildButtons(self)

        btn = gtk.Button('Submit Disc')
        btn.connect('clicked', self.submit_disc)
        hbox.pack_end(btn, expand=False, fill=False)

        return hbox

    def submit_disc(self, widget):
        webbrowser.open(self.submission_url)

class TrackListView(gtk.ScrolledWindow):
    titleColWidth = 32
    def __init__(self, catalog):
        self.catalog = catalog
        gtk.ScrolledWindow.__init__(self)
        self.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)

        self.buildTreeView()

        self.tv.connect('cursor-changed', self.on_row_select)
        self.tv.connect('row-activated', self.on_row_activate)
        self.tv.show()
        self.add(self.tv)

    def buildTreeView(self):
        self.tv = gtk.TreeView()
        for i, (label, xalign, textWidth) in enumerate(
            [('Title', 0, self.titleColWidth),
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

    def makeTreeStore(self, releaseId):
        trackTreeStore = gtk.TreeStore(str, str, str)
        # TODO this should be a Catalog method
        for mediumId,position,format in self.catalog.cm.executeAndFetch(
                'select id,position,format from media '
                'where release=? order by position',
                (releaseId,)):
            trackData = self.catalog.cm.executeAndFetch(
                    'select recordings.id, recordings.length, '
                    'medium_recordings.position, recordings.title '
                    'from recordings '
                    'inner join medium_recordings on '
                    'medium_recordings.recording=recordings.id '
                    'inner join media on medium_recordings.medium=media.id '
                    'where media.id=? order by medium_recordings.position',
                    (mediumId,))
            parent = trackTreeStore.append(None,
                ('',
                format+' '+str(position)+' ('+str(len(trackData))+')',
                mbcat.catalog.recLengthAsString(
                    self.catalog.getMediumLen(mediumId)
                    )))
            for recId,recLength,recPosition,title in trackData:
                trackTreeStore.append(parent,
                    (recId,
                    title,
                    mbcat.catalog.recLengthAsString(recLength)
                    ))
        return trackTreeStore

    def update(self, releaseId):
        trackTreeStore = self.makeTreeStore(releaseId)
        self.tv.set_model(trackTreeStore)
        self.tv.expand_all()

    def get_selection(self):
        model, it = self.tv.get_selection().get_selected()
        return model.get_value(it, 0) if it else None

    def on_row_select(self, treeview):
        """Override this method when you inherit this class."""
        pass

    def on_row_activate(self, treeview, path, column):
        # TODO not sure what this should do
        relId = self.get_selection()
        if relId:
            webbrowser.open(mbcat.catalog.Catalog.recordingUrl + relId)

class TrackListDialogView(TrackListView):
    titleColWidth = 50
    def __init__(self, catalog, dialog):
        TrackListView.__init__(self, catalog)
        self.dialog = dialog

    def on_row_select(self, treeview):
        self.dialog.on_row_select(treeview)

class TrackListDialog(QueryResultsDialog):
    """
    Display a dialog with a list of tracks for a release.
    Example:
    """
    def __init__(self,
            parentWindow,
            app,
            releaseId,
            message='Track List',
        ):
        QueryResultsDialog.__init__(self, parentWindow, app,
            releaseId, message)

    def buildWidgets(self, vbox, releaseId):
        self.trackListView = TrackListDialogView(self.app.catalog, self)
        self.trackListView.update(releaseId)
        self.trackListView.show()

        vbox.pack_start(self.trackListView, expand=True, fill=True)

        hbox = self.buildButtons()
        vbox.pack_end(hbox, expand=False, fill=False)

        self.buildRowInfoWidgets(vbox)

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

    def get_selection(self):
        return self.trackListView.get_selection()

    def on_row_select(self, treeview):
        model, iter = self.trackListView.tv.get_selection().get_selected()
        if iter and len(model.get_path(iter)) > 1:
            # if a recording is selected
            QueryResultsDialog.on_row_select(self, treeview)
            self.row_widgets_set_sensitive(True)
        else:
            # a medium is selected
            self.row_widgets_set_sensitive(False)

def startResultViewer(viewer, *args, **kwargs):
    """For use with gobject.idle_add"""
    viewer(*args, **kwargs)
    return False

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
        self.leftInfo.set_width_chars(36)
        hbox.pack_start(self.leftInfo, True, True)
        self.vsLbl = gtk.Label('<->')
        hbox.pack_start(self.vsLbl, False, False)
        self.rightInfo = gtk.Label()
        self.rightInfo.set_ellipsize(pango.ELLIPSIZE_END)
        self.rightInfo.set_width_chars(36)
        hbox.pack_start(self.rightInfo, True, True)
        vbox.pack_end(hbox, False, False)

    def on_row_select(self, treeview):
        model, it = self.tv.get_selection().get_selected()
        if not it:
            return
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
    d.set_size_request(*default_dialog_size)
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
            message='Checkout History',
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

class ListenHistoryDialog(QueryResultsDialog):
    """Manage listen history."""

    row_contains = 'Event'

    def __init__(self,
            parentWindow,
            app,
            releaseId,
            message='Listen History',
            ):
        self.releaseId = releaseId
        QueryResultsDialog.__init__(self, parentWindow, app, releaseId, message)
        self.selInfo.set_ellipsize(pango.ELLIPSIZE_END)
        self.selInfo.set_text('Release "%s" (%s)' %
                (self.app.catalog.getReleaseTitle(releaseId), releaseId))

    def on_row_select(self, treeview):
        # When a row is selected, sensitize the Delete button
        self.checkInBtn.set_sensitive(True)

    def update(self):
        self.buildListStore(self.releaseId)

    def buildTreeView(self):
        self.tv = gtk.TreeView()
        for i, (label, textWidth) in enumerate(
            [('Date', 20),
            ]):
            cell = gtk.CellRendererText()
            cell.set_property('xalign', 1.0)
            cell.set_property('width-chars', textWidth)
            col = gtk.TreeViewColumn(label, cell)
            col.add_attribute(cell, 'text', i+1)
            col.set_resizable(True)
            self.tv.append_column(col)

    def buildListStore(self, releaseId):
        resultListStore = gtk.ListStore(float, str)

        for event in self.app.catalog.getListenDates(self.releaseId):
            resultListStore.append((event, mbcat.decodeDateTime(event)))
        self.tv.set_model(resultListStore)

    def buildButtons(self):
        # Buttons
        hbox = gtk.HBox(False, 10)
        btn = gtk.Button('Close', gtk.STOCK_CLOSE)
        btn.connect('clicked', self.on_close)
        hbox.pack_end(btn, expand=False, fill=False)

        self.checkInBtn = gtk.Button('Delete Date')
        self.checkInBtn.connect('clicked', self.delete_date)
        self.checkInBtn.set_sensitive(False)
        hbox.pack_end(self.checkInBtn, expand=False, fill=False)

        self.checkOutBtn = gtk.Button('Add Date')
        self.checkOutBtn.connect('clicked', self.add_date)
        hbox.pack_end(self.checkOutBtn, expand=False, fill=False)

        return hbox

    def get_selection(self):
        """Return the unique date float for the selected row, if any."""
        model, it = self.tv.get_selection().get_selected()
        return model.get_value(it, 0) if it else None

    def add_date(self, button):
        dt = DateEntry(self.window,
            'Choose a listen date')
        if dt:
            date = float(mbcat.encodeDateTime(dt))
            self.app.catalog.addListenDate(releaseId=self.releaseId, date=date)
            self.update()
            self.app.updateDetailPane()

    def delete_date(self, button):
        selected_date = self.get_selection()
        if selected_date:
            self.app.catalog.deleteListenDate(releaseId=self.releaseId,
                    date=selected_date)
            self.update()
            self.app.updateDetailPane()
            self.checkInBtn.set_sensitive(False)

class DigitalPathListDialog(QueryResultsDialog):
    """Manage digital paths for a release."""

    row_contains = 'Digital Path'

    def __init__(self,
            parentWindow,
            app,
            releaseId,
            message='Digital Paths',
            ):
        self.releaseId = releaseId
        QueryResultsDialog.__init__(self, parentWindow, app, releaseId, message)
        self.selInfo.set_ellipsize(pango.ELLIPSIZE_END)
        self.selInfo.set_text('Release "%s" (%s)' %
                (self.app.catalog.getReleaseTitle(releaseId), releaseId))

    def on_row_select(self, treeview):
        # When a row is selected, sensitize the Delete button
        self.checkInBtn.set_sensitive(True)

    def update(self):
        self.buildListStore(self.releaseId)

    def buildTreeView(self):
        self.tv = gtk.TreeView()
        for i, (label, textWidth, xalign) in enumerate([
            ('Path', 52, 0),
            ('Format', 6, 1.0),
            ]):
            cell = gtk.CellRendererText()
            cell.set_property('xalign', xalign)
            cell.set_property('width-chars', textWidth)
            if i == 0:
                cell.set_property('ellipsize', pango.ELLIPSIZE_END)
            col = gtk.TreeViewColumn(label, cell)
            col.add_attribute(cell, 'text', i+2)
            col.set_resizable(True)
            self.tv.append_column(col)

    def buildListStore(self, releaseId):
        resultListStore = gtk.ListStore(str, str, str, str)

        for root_id,path,fmt in self.app.catalog.getDigitalPaths(
                self.releaseId):
            if not root_id or root_id not in self.app.prefs.pathRoots:
                _log.error('Bad or missing path root for release %s' % \
                        self.releaseId)
                root_path = '[unknown]'
            else:
                root_path = self.app.prefs.pathRoots[root_id]['path']
            resultListStore.append((
                    # For the program
                    root_id,
                    path,
                    # For the user
                    os.path.join(root_path, path),
                    fmt
                    ))
        self.tv.set_model(resultListStore)

    def buildButtons(self):
        # Buttons
        hbox = gtk.HBox(False, 10)
        btn = gtk.Button('Close', gtk.STOCK_CLOSE)
        btn.connect('clicked', self.on_close)
        hbox.pack_end(btn, expand=False, fill=False)

        self.checkInBtn = gtk.Button('Delete Path')
        self.checkInBtn.connect('clicked', self.delete_path)
        self.checkInBtn.set_sensitive(False)
        hbox.pack_end(self.checkInBtn, expand=False, fill=False)

        self.checkOutBtn = gtk.Button('Add Path')
        self.checkOutBtn.connect('clicked', self.add_path)
        hbox.pack_end(self.checkOutBtn, expand=False, fill=False)

        return hbox

    def get_selection(self):
        model, it = self.tv.get_selection().get_selected()
        return (model.get_value(it, 0), model.get_value(it, 1)) \
                if it else (None, None)

    def add_path(self, button):
        dialog = gtk.FileChooserDialog(
            title='Choose path to digital copy',
            action=gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
            buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                gtk.STOCK_OPEN, gtk.RESPONSE_OK))
        dialog.set_default_response(gtk.RESPONSE_OK)
        response = dialog.run()
        if response != gtk.RESPONSE_OK:
            dialog.destroy()
            return

        path = dialog.get_filename()
        dialog.destroy()

        if path:
            # Determine the root path of the path specified by the user
            root_id, rel_path = self.app.prefs.getRootIdForPath(path)
            if not root_id:
                ErrorDialog(self.parentWindow,
                    'The path "%s" was not found in any of the root paths in '
                    'the user preferences. Please add a root path first.' % \
                    path)
                return

            fmt = mbcat.digital.guessDigitalFormat(path)
            self.app.catalog.addDigitalPath(
                    self.releaseId, fmt, root_id, rel_path)
            self.app.catalog.cm.commit()
            self.update()
            self.app.updateDetailPane()

    def delete_path(self, button):
        selected_root_id, selected_path = self.get_selection()
        if selected_root_id:
            self.app.catalog.deleteDigitalPath(
                    releaseId=self.releaseId,
                    root_id=selected_root_id,
                    path=selected_path)
            self.app.catalog.cm.commit()
            self.update()
            self.app.updateDetailPane()
            self.checkInBtn.set_sensitive(False)


class PurchaseHistoryDialog(QueryResultsDialog):
    """Manage purchase dates."""

    row_contains = 'Event'

    def __init__(self,
            parentWindow,
            app,
            releaseId,
            message='Purchase History',
            ):
        self.releaseId = releaseId
        QueryResultsDialog.__init__(self, parentWindow, app, releaseId, message)
        self.selInfo.set_ellipsize(pango.ELLIPSIZE_END)
        self.selInfo.set_text('Release "%s" (%s)' %
                (self.app.catalog.getReleaseTitle(releaseId), releaseId))

    def on_row_select(self, treeview):
        # When a row is selected, sensitize the Delete button
        self.checkInBtn.set_sensitive(True)

    def update(self):
        self.buildListStore(self.releaseId)

    def buildTreeView(self):
        self.tv = gtk.TreeView()
        for i, (label, textWidth, xalign) in enumerate([
            ('Date', 20, 0),
            ('Price', 5, 1.0),
            ('Vendor', 20, 0),
            ]):
            cell = gtk.CellRendererText()
            cell.set_property('xalign', xalign)
            cell.set_property('width-chars', textWidth)
            col = gtk.TreeViewColumn(label, cell)
            col.add_attribute(cell, 'text', i+1)
            col.set_resizable(True)
            self.tv.append_column(col)

    def buildListStore(self, releaseId):
        resultListStore = gtk.ListStore(float, str, str, str)

        for date,price,vendor in self.app.catalog.getPurchases(
                self.releaseId):
            resultListStore.append((
                date,
                mbcat.decodeDate(date),
                price,
                vendor
                ))
        self.tv.set_model(resultListStore)

    def buildButtons(self):
        # Buttons
        hbox = gtk.HBox(False, 10)
        btn = gtk.Button('Close', gtk.STOCK_CLOSE)
        btn.connect('clicked', self.on_close)
        hbox.pack_end(btn, expand=False, fill=False)

        self.checkInBtn = gtk.Button('Delete Event')
        self.checkInBtn.connect('clicked', self.delete_event)
        self.checkInBtn.set_sensitive(False)
        hbox.pack_end(self.checkInBtn, expand=False, fill=False)

        self.checkOutBtn = gtk.Button('Add Event')
        self.checkOutBtn.connect('clicked', self.add_event)
        hbox.pack_end(self.checkOutBtn, expand=False, fill=False)

        return hbox

    def get_selection(self):
        """Return the unique date float for the selected row, if any."""
        model, it = self.tv.get_selection().get_selected()
        return model.get_value(it, 0) if it else None

    def add_event(self, button):
        info = PurchaseInfoEntry(self.window)
        if info:
            self.app.catalog.addPurchase(self.releaseId,
                    info['date'], info['price'], info['vendor'])
            self.update()
            self.app.updateDetailPane()

    def delete_event(self, button):
        selected_date = self.get_selection()
        if selected_date:
            self.app.catalog.deletePurchase(releaseId=self.releaseId,
                    date=selected_date)
            self.update()
            self.app.updateDetailPane()
            self.checkInBtn.set_sensitive(False)

def TextViewEntry(parent, message, default='', editable=True):
    """
    Display a dialog with a text entry.
    Returns the text, or None if canceled.
    """
    d = gtk.MessageDialog(parent,
            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
            gtk.MESSAGE_QUESTION,
            gtk.BUTTONS_OK_CANCEL if editable else gtk.BUTTONS_CLOSE,
            message)
    d.set_size_request(*default_dialog_size)
    d.set_resizable(True)
    sw = gtk.ScrolledWindow()
    sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
    textview = gtk.TextView()
    textview.set_editable(editable)
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

        self.trackList = TrackListView(self.catalog)
        self.trackList.show()
        self.pack_start(self.trackList)

        self.buildInfoTable()

        self.pack_start(self.lt, expand=False, fill=False)
        self.lt.show()

    def buildInfoTable(self):
        self.lt = gtk.Table(2, 4, homogeneous=False)
        self.lt.set_border_width(5)

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

        l = gtk.Label('Digital Formats:')
        l.set_alignment(0, 0.5)
        self.lt.attach(l, 0, 1, r, r+1)
        self.digFormatsLbl = gtk.Label()
        self.lt.attach(self.digFormatsLbl, 1, 2, r, r+1)
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
        self.checkOutLbl.set_ellipsize(pango.ELLIPSIZE_END)
        self.lt.attach(self.checkOutLbl, 1, 2, r, r+1)
        r += 1

        self.lt.set_row_spacings(5)
        self.lt.set_col_spacing(0, 5)
        self.lt.show_all()

    def on_track_row_activate(self, treeview, path, column):
        relId = self.get_selection()
        if relId:
            webbrowser.open(mbcat.catalog.Catalog.recordingUrl + relId)

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

        self.trackList.update(releaseId)

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

        digFormats = self.catalog.getDigitalFormats(releaseId)
        self.digFormatsLbl.set_text(', '.join(digFormats) \
                if digFormats else 'None')

        rating = self.catalog.getRating(releaseId)
        self.ratingLbl.set_active(int(rating) if rating and rating != 'None' else 0)

        count = self.catalog.getCopyCount(releaseId)
        self.countSpinButton.set_value(int(count) if count and count != 'None' else 0)

        checkedOut = self.catalog.getCheckOutStatus(releaseId)
        self.checkOutLbl.set_text(checkedOut[0] if checkedOut else 'No')

class MBCatGtk:
    """
    A GTK interface for managing a music collection using MusicBrainz.
    """
    __name__ = 'MusicBrainz Catalog GTK GUI'
    __version__ = mbcat.catalog.__version__
    __copyright__ = 'Ryan Helinski'
    __website__ = 'https://github.com/rlhelinski/musicbrainz-catalog'
    __icon_file__ = os.path.join(mbcat.__path__[0],
                                 'art',
                                 'MusicBrainzCatalogLogo-white.svg')
    __png_icon_file__ = os.path.join(mbcat.__path__[0],
                                 'art',
                                 'MusicBrainzCatalogLogo-white-256.png')

    columnNames = ['Artist', 'Release Title', 'Date', 'Country', 'Label',
        'Catalog #', 'Barcode', 'ASIN', 'Format', 'Sort Format', 'First Added']
    columnWidths = [30, 45, 16, 2, 37, 23, 16, 16, 16, 16, 16]
    numFields = ['Barcode', 'ASIN']

    formatNames = ['All', 'Digital', 'CD', '7" Vinyl', '12" Vinyl', 'Unknown']
    formatLabels = ['_All', '_Digital', '_CD', '_7" Vinyl', '_12" Vinyl',
        '_Unknown']

    searchResultsLimit = 100

    # Default extensions.
    filePatterns = [
        # These are essentially the same
        ('sqlite3 files', '*.sqlite3'), # unambiguous
        ('sqlite files', '*.sqlite'), # might tempt to open with sqlite < 3
        ('db files', '*.db'), # not specific
        ]

    zipFilePatterns = [('zip files', '*.zip')]

    htmlFilePatterns = [('html files', '*.html')]

    @staticmethod
    def getColumnWidth(i):
        sl = [self.releaseList[j][i] for j in xrange(len(self.releaseList))]
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

    def url_hook_func(self, ignore1, url, ignore2):
        webbrowser.open(url, new=2)

    def openAboutWindow(self, widget):
        about = gtk.AboutDialog()
        about.set_program_name(self.__name__)
        about.set_version(self.__version__)
        about.set_copyright(self.__copyright__)
        about.set_comments(self.__doc__)
        about.set_website(self.__website__)
        gtk.about_dialog_set_url_hook(self.url_hook_func, data=None)
        try:
            about.set_logo(gtk.gdk.pixbuf_new_from_file(self.__icon_file__))
        except glib.GError:
            about.set_logo(gtk.gdk.pixbuf_new_from_file(self.__png_icon_file__))
        about.run()
        about.destroy()
        return

    def openDatabase(self, filename=None):
        if filename:
            self.catalog.open(
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
        self.actiongroup.get_action('SaveAs').set_sensitive(True)
        self.updateStatusBar()

    def copyAndOpenDatabase(self, filename):
        import shutil
        # Copy the database to the new location
        shutil.copy(self.catalog.dbPath, filename)
        # Open the new copy
        self.openDatabase(filename)

    def addPatternsToDialog(self, dialog, patterns):
        for desc, pattern in patterns:
            filt = gtk.FileFilter()
            filt.set_name(desc)
            filt.add_pattern(pattern)
            dialog.add_filter(filt)

    def menuCatalogOpen(self, widget):
        # Ask the user where to store the new database
        dialog = gtk.FileChooserDialog(
            title='Open database file',
            action=gtk.FILE_CHOOSER_ACTION_OPEN,
            buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                gtk.STOCK_OPEN, gtk.RESPONSE_OK))

        dialog.set_default_response(gtk.RESPONSE_OK)

        self.addPatternsToDialog(dialog, self.filePatterns)

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
            title='Save database file as',
            action=gtk.FILE_CHOOSER_ACTION_SAVE,
            buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                gtk.STOCK_SAVE, gtk.RESPONSE_OK))

        dialog.set_default_response(gtk.RESPONSE_OK)

        self.addPatternsToDialog(dialog, self.filePatterns)

        response = dialog.run()
        if response != gtk.RESPONSE_OK:
            dialog.destroy()
            return

        filename = dialog.get_filename()
        dialog.destroy()

        self.copyAndOpenDatabase(filename)

    def menuCatalogImportZip(self, widget):
        dialog = gtk.FileChooserDialog(
            title='Import from zip file',
            action=gtk.FILE_CHOOSER_ACTION_SAVE,
            buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                gtk.STOCK_SAVE, gtk.RESPONSE_OK))

        dialog.set_default_response(gtk.RESPONSE_OK)

        self.addPatternsToDialog(dialog, self.zipFilePatterns)

        response = dialog.run()
        if response != gtk.RESPONSE_OK:
            dialog.destroy()
            return

        self.CatalogTask(self,
            mbcat.dialogs.ProgressDialog(self.window,
                self.catalog.loadZip(self.catalog,
                        dialog.get_filename()))).start()
        dialog.destroy()

    def menuCatalogExportZip(self, widget):
        dialog = gtk.FileChooserDialog(
            title='Export to zip file',
            action=gtk.FILE_CHOOSER_ACTION_SAVE,
            buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                gtk.STOCK_SAVE, gtk.RESPONSE_OK))

        dialog.set_default_response(gtk.RESPONSE_OK)

        self.addPatternsToDialog(dialog, self.zipFilePatterns)

        response = dialog.run()
        if response != gtk.RESPONSE_OK:
            dialog.destroy()
            return

        self.CatalogTask(self,
            mbcat.dialogs.ProgressDialog(self.window,
                self.catalog.saveZip(self.catalog,
                        dialog.get_filename()))).start()
        dialog.destroy()

    def menuCatalogImportDB(self, widget):
        dialog = gtk.FileChooserDialog(
            title='Import from sqlite3 database file',
            action=gtk.FILE_CHOOSER_ACTION_SAVE,
            buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                gtk.STOCK_SAVE, gtk.RESPONSE_OK))

        dialog.set_default_response(gtk.RESPONSE_OK)

        self.addPatternsToDialog(dialog, self.filePatterns)

        response = dialog.run()
        if response != gtk.RESPONSE_OK:
            dialog.destroy()
            return

        source = mbcat.catalog.Catalog(dbPath=dialog.get_filename())
        dialog.destroy()

        self.CatalogTask(self,
            mbcat.dialogs.PulseDialog(
                self.window,
                mbcat.dialogs.ThreadedCall(
                    self.catalog.merge,
                    source))).start()

    def menuCatalogExportHtml(self, widget):
        try:
            import mbcat.html
        except ImportError as e:
            ErrorDialog(self.window, 'Error importing: '+str(e))
            return

        dialog = gtk.FileChooserDialog(
            title='Export to HTML file',
            action=gtk.FILE_CHOOSER_ACTION_SAVE,
            buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                gtk.STOCK_SAVE, gtk.RESPONSE_OK))

        dialog.set_default_response(gtk.RESPONSE_OK)

        self.addPatternsToDialog(dialog, self.htmlFilePatterns)

        response = dialog.run()
        if response != gtk.RESPONSE_OK:
            dialog.destroy()
            return

        htmlfilename = dialog.get_filename()
        dialog.destroy()
        t = mbcat.dialogs.ProgressDialog(self.window,
            mbcat.html.HtmlWriter(self.catalog,
                    htmlfilename))
        t.start()
        t.join() # TODO this is blocking, but using it because the next
        # line manipulates GTK
        if ConfirmDialog(self.window,
                'Open HTML file in browser?',
                buttons=gtk.BUTTONS_YES_NO, expect=gtk.RESPONSE_YES,
                default=gtk.RESPONSE_NO):
            _log.info('Opening browser to "%s"' % htmlfilename)
            webbrowser.open(htmlfilename)

    def menuPreferences(self, widget):
        PreferencesDialog(self.window, self.prefs, self.catalog)

    def menuCatalogVacuum(self, widget):
        self.CatalogTask(self,
            mbcat.dialogs.PulseDialog(
                self.window,
                mbcat.dialogs.ThreadedCall(self.catalog.vacuum))).start()

    def menuCatalogRefresh(self, widget):
        self.CatalogTask(self,
            mbcat.dialogs.ProgressDialog(self.window,
                self.catalog.refreshAllMetaData(self.catalog, 60*60*24))).start()

    def menuCatalogIndexDigital(self, widget):
        self.CatalogTask(self,
            mbcat.dialogs.ProgressDialog(self.window,
                mbcat.digital.DigitalSearch(self.catalog))).start()

    def menuReleaseIndexDigital(self, widget):
        selRelId = self.getSelection()
        self.CatalogTask(self,
            mbcat.dialogs.ProgressDialog(self.window,
                mbcat.digital.DigitalSearch(self.catalog,
                    releaseId=selRelId))).start()

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
            self.task.start()
            self.task.join()
            gobject.idle_add(self.app.refreshView)

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
            gobject.idle_add(startResultViewer, self.result_viewer,
                    self.window, self.app, self.task.task.result)

    def menuCatalogRebuild(self, widget):
        self.CatalogTask(self,
            mbcat.dialogs.ProgressDialog(self.window,
                self.catalog.rebuildDerivedTables(self.catalog))).start()

    def menuCatalogGetSimilar(self, widget):
        # Check to make sure we can import Levenshtein module
        # TODO find a way to return an exception from the child thread
        try:
            import Levenshtein
        except ImportError as e:
            ErrorDialog(self.window, 'Error importing: '+str(e))
            return
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
        for item in self.menu_release_items:
            self.actiongroup.get_action(item).set_sensitive(sens)

    def toolbar_force_important(self):
        """Force labels to appear on toolbar buttons"""
        actions = ['ViewDetailPane',
                'FormatAll',
                'FormatDigital',
                'FormatCD',
                'Format7Inch',
                'Format12Inch',
                ]
        for action in actions:
            self.actiongroup.get_action(action).set_is_important(True)

    def on_row_activate(self, treeview, path, column):
        self.actiongroup.get_action('ViewDetailPane').set_sensitive(True)
        self.actiongroup.get_action('ViewDetailPane').set_active(True)
        # self.detailpane.show() # This is activated by set_active() above
        # self.updateDetailPane() # This is also activated

    def on_row_select(self, treeview):
        self.menu_release_items_set_sensitive(True)
        model, it = treeview.get_selection().get_selected()
        if it:
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
        if row is None:
            return
        # Limit the range of the row input
        actualRow = min(len(self.releaseList)-1, row)
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
        selRelId = self.getSelection()
        selRow = self.getSelectedRow()
        self.makeListStore()
        self.updateDetailPane()
        self.updateStatusBar()
        # if there was a selection
        if selRelId:
            newRow = self.getReleaseRow(selRelId)
            # if the release exists in the new ListStore
            if newRow:
                self.setSelectedRow(newRow)
            else:
                self.setSelectedRow(selRow)
        return False # for use with gobject.idle_add

    def viewXml(self, widget=None):
        import xml.dom.minidom
        selRelId = self.getSelection()
        xml = xml.dom.minidom.parseString(
                self.catalog.getReleaseXml(selRelId))
        TextViewEntry(self.window,
                message='Release XML for \'%s\'' % selRelId,
                default=xml.toprettyxml(),
                editable=False)

    def scrollToSelected(self, widget=None):
        row = self.getSelectedRow()
        self.treeview.scroll_to_cell(row, use_align=True, row_align=0.5)

    def toggleStatusBar(self, widget):
        if widget.get_active():
            self.statusbar.show()
        else:
            self.statusbar.hide()

    def toggleToolBar(self, widget):
        tb = self.uimanager.get_widget('/Toolbar')
        if widget.get_active():
            tb.show()
        else:
            tb.hide()

    def updateStatusBar(self):
        # TODO use this push/pop action better
        self.statusbar.pop(self.context_id)
        msg = ('Showing %d out of %d releases' % \
            (len(self.releaseList), len(self.catalog)))
        self.statusbar.push(self.context_id, msg)

    def toggleDetailPane(self, widget):
        if widget.get_active():
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
            self.filtFmt = 'sortformat="'+fmt+'"'
        else:
            self.filtFmt = ''
        self.makeListStore()
        self.updateStatusBar()

        row = self.getReleaseRow(sel)
        if row:
            self.setSelectedRow(row)

    def menuClearFilters(self, widget=None):
        self.filt = ''
        self.actiongroup.get_action('FormatAll').set_active(True)
        self.refreshView(widget)
        self.searchentry.set_text('')

    def menuClearSearch(self, widget=None):
        self.filt = ''
        self.searchentry.set_text('')
        self.refreshView(widget)

    def menuCatalogCheck(self, widget):
        self.filt = self.catalog.badReleaseFilter
        self.refreshView(widget)

    def _setFilterQuick(self, terms):
        self.filt = ' and '.join([
                ('sortstring like "%'+term+'%"') \
                for term in terms.split(' ')
                ])

    def menuFilterQuick(self, widget):
        terms = TextEntry(self.window,
            'Enter terms to search for, seperated by spaces.\n'\
            'Ex.: "john smith" would show any releases including "john"\n'\
            '\tand "smith" in the title or the artist.')
        if terms:
            self._setFilterQuick(terms)
            self.refreshView(widget)

    def search_callback(self, widget=None):
        terms = self.searchentry.get_text()
        if terms:
            self._setFilterQuick(terms)
            self.refreshView(widget)

    def menuFilterExpression(self, widget):
        expr = TextEntry(self.window,
            'Enter an SQL expression for "where"\n'\
            'Ex.: country="US" and date < 1970\n'
            'Ex.: artist like "%Smith%" or artist like "%John%"\n'
            'Useful columns:\n'\
            '\tartist, title, sortstring, date, county, label, catno,\n'\
            '\tbarcode, asin, format, metatime, count, comment, rating\n',
            default=self.filt)
        if expr:
            self.filt = expr
            self.refreshView(widget)

    def _addRelease(self, releaseId, parentWindow, doneFun=None,
            doneFunArg=None):
        class AddReleaseTask(mbcat.dialogs.ThreadedCall):
            def __init__(self, app, c, fun, doneFun, doneFunArg, *args):
                mbcat.dialogs.ThreadedCall.__init__(self, fun, *args)
                self.app = app
                self.c = c
                self.doneFun = doneFun
                self.doneFunArg = doneFunArg

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
                if self.doneFun:
                    self.doneFun(self.doneFunArg)

        if releaseId in self.catalog:
            ErrorDialog(parentWindow, 'Release already exists')
            return

        mbcat.dialogs.PulseDialog(parentWindow,
            AddReleaseTask(self,
                self.catalog,
                self.catalog.addRelease,
                doneFun,
                doneFunArg,
                releaseId)).start()

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
        if not ConfirmDialog(self.window,
            'Are you sure you wish to delete "%s"\nwith ID %s?' % \
                (relTitle, releaseId)):
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

        relTitle = self.catalog.getReleaseTitle(releaseId)
        # Ask the user to specify a release to which to switch
        newRelId = TextEntry(self.window,
            'Enter release ID to replace\n%s\n"%s"' % (releaseId, relTitle))
        if not newRelId:
            return
        if newRelId in self.catalog:
            ErrorDialog(self.window, 'New release ID already exists')
            return

        self.catalog.renameRelease(releaseId, newRelId)
        newRelTitle = self.catalog.getReleaseTitle(newRelId)

        if relTitle != newRelTitle:
            _log.info("Replaced '%s' with '%s'" % (relTitle, newRelTitle))
        else:
            _log.info("Replaced '%s'" % (relTitle))

        self.makeListStore()
        self.setSelectedRow(row)

    def getCoverArt(self, widget):
        releaseId = self.getSelection()
        self.catalog.getCoverArt(releaseId, maxage=0)
        # refresh the detail pane if it is active
        self.updateDetailPane()

    def refreshRelease(self, widget):
        row = self.getSelectedRow()
        releaseId = self.getSelection()
        try:
            self.catalog.addRelease(releaseId, olderThan=0)
        except mb.NetworkError as e:
            ErrorDialog(self.window, 'Network error, failed to refresh')
        else:
            self.makeListStore()
            self.setSelectedRow(row)

    def browseRelease(self, widget):
        releaseId = self.getSelection()
        # copied from QueryResultsDialog.browse_release
        webbrowser.open(mbcat.catalog.Catalog.releaseUrl + releaseId)

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

        date = DateEntry(self.window, "Choose a lend date")
        if date:
            self.catalog.addCheckOutEvent(releaseId, borrower,
                    mbcat.encodeDateTime(date))
            self.updateDetailPane()

    def checkIn(self, widget=None, releaseId=None):
        if not releaseId:
            releaseId = self.getSelection()

        if not self.catalog.getCheckOutStatus(releaseId):
            ErrorDialog(self.window, 'Release is not checked out.')
            return

        date = DateEntry(self.window, "Select return date")
        if date:
            self.catalog.addCheckInEvent(releaseId, mbcat.encodeDateTime(date))
            self.updateDetailPane()

    def editComment(self, widget):
        releaseId = self.getSelection()
        oldcomment = self.catalog.getComment(releaseId)
        newcomment = TextViewEntry(self.window, 'Edit Release Comments',
                oldcomment if oldcomment is not None else '')
        if newcomment is not None:
            self.catalog.setComment(releaseId, newcomment)

    def changeCount(self, widget):
        releaseId = self.getSelection()
        newcount = IntegerDialog(self.window, 'Enter new copy count',
            self.catalog.getCopyCount(releaseId))
        if newcount is not None:
            self.catalog.setCopyCount(releaseId, newcount)

    def listen(self, widget):
        ListenHistoryDialog(self.window, self, self.getSelection())

    def digitalPaths(self, widget):
        DigitalPathListDialog(self.window, self, self.getSelection())

    def purchaseInfo(self, widget):
        PurchaseHistoryDialog(self.window, self, self.getSelection())

    def submitReleaseGroupRating(self, releaseGroupId, rating):
        # TODO cache password and check for that here
        if not self.webserviceAuth():
            return

        print (str(rating))
        nr = 0 if rating == 'None' else (int(rating)*20)
        _log.info('Submitting release group %s rating %d' % (releaseGroupId,
                nr))
        mb.submit_ratings(release_group_ratings={releaseGroupId: nr})

    def rateRelease(self, widget):
        releaseId = self.getSelection()
        if not releaseId:
            return
        nr = RatingDialog(self.window,
            default=self.catalog.getRating(releaseId))
        if not nr:
            return
        self.catalog.setRating(releaseId, nr)
        # Also rate on musicbrainz.org if we are signed in
        self.submitReleaseGroupRating(
                self.catalog.getReleaseGroup(releaseId), nr)

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

    def searchReleaseID(self, widget):
        releaseId = TextEntry(self.window, 'Enter Release ID')
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

    def webserviceAuth(self):
        if not self.catalog.prefs.username:
            username = TextEntry(self.window, 'Enter username:')
            self.catalog.prefs.setUserName(username)
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
        return True

    def webserviceSyncCollection(self, widget):
        """Synchronize with a musicbrainz collection (currently only pushes releases)."""
        if not self.webserviceAuth():
            return

        result = mb.get_collections()
        collectionId = SelectCollectionDialog(self.window, result)

        self.CatalogTask(self,
            mbcat.dialogs.ProgressDialog(self.window,
                self.catalog.syncCollection(self.catalog,
                    collectionId))).start()

    def askBrowseSubmission(self, url, msg='Open browser to Submission URL?'):
        answer = ConfirmDialog(self.window, msg)
        if answer:
            _log.info('Opening web browser to submission URL.')
            webbrowser.open(url)

    def readDiscTOC(self, widget):
        try:
            import discid
        except ImportError as e:
            ErrorDialog(self.window, 'Error importing: '+str(e))
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
        _log.info("Disc submission URL: %s" % disc.submission_url)

        _log.info("Querying MusicBrainz for DiscID '%s'..." % disc.id)
        d = mbcat.dialogs.PulseDialog(self.window,
            DiscQueryTask(self.window, self,
                DiscQueryResultsDialog, disc.submission_url,
                mb.get_releases_by_discid,
                disc.id, includes=['artists']))
        d.start()
        d.join()

        print (d.task.result)
        if type(d.task.result) == mb.ResponseError:
            ErrorDialog(self.window, 'MusicBrainz response error: '+\
                    str(d.task.result))
            self.askBrowseSubmission(d.task.submission_url)
        elif d.task.result.get('cdstub'):
            # TODO this should be a dialog?
            for label, key in [
                    ('CD Stub', 'id'),
                    ('Artist', 'artist'),
                    ('Title', 'title'),
                    ('Barcode', 'barcode')]:
                if key in d.task.result['cdstub']:
                    _log.info('%10s: %s\n' %
                                 (label, d.task.result['cdstub'][key]))
            self.askBrowseSubmission(d.task.submission_url,
                    'There was only a CD stub. '
                    'Open browser to Submission URL?')

    def makeListStore(self, ):
        self.releaseList = gtk.ListStore(str, str, str, str, str, str, str, str,
            str, str, str, str, str)

        filtStr = ' and '.join(filter(None, [self.filtFmt, self.filt]))
        for row in self.catalog.getAdvTable(filtStr):
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
            self.tvcolumn[n] = gtk.TreeViewColumn(columnName, cell, text=n+2)
            self.tvcolumn[n].set_sort_column_id(n+2)
            self.tvcolumn[n].set_resizable(True)
            if (columnName == 'Sort Format'):
                self.tvcolumn[n].set_property('visible', False)
            self.treeview.append_column(self.tvcolumn[n])

        self.treeview.connect('row-activated', self.on_row_activate)
        self.treeview.connect('cursor-changed', self.on_row_select)
        self.treeview.connect('unselect-all', self.on_unselect_all)
        self.scrolledwindow = gtk.ScrolledWindow()
        self.scrolledwindow.add(self.treeview)

    ui_xml = '''<ui>
    <menubar name="MenuBar">
      <menu action="Catalog">
        <menuitem action="Open"/>
        <menuitem action="SaveAs"/>
        <separator />
        <menu action="Import">
            <menuitem action="ImportDatabase" />
            <menuitem action="ImportZip" />
        </menu>
        <menu action="Export">
            <menuitem action="ExportZip" />
            <menuitem action="ExportHTML" />
        </menu>
        <separator />
        <menuitem action="RefreshMetadata" />
        <menuitem action="IndexDigital" />
        <menuitem action="DatabaseVacuum" />
        <menuitem action="DatabaseRebuild" />
        <menuitem action="DatabaseFindSimilar" />
        <separator />
        <menuitem action="Preferences" />
        <separator />
        <menuitem action="Quit"/>
      </menu>
      <menu action="View">
        <menuitem action="ViewToolbar"/>
        <menuitem action="ViewDetailPane" />
        <menuitem action="ViewStatusBar" />
        <menuitem action="ViewRefresh" />
        <menuitem action="ViewScrollSelected" />
        <menuitem action="ViewXML" />
      </menu>
      <menu action="Release">
        <menuitem action="ReleaseAdd" />
        <menuitem action="ReleaseDelete" />
        <menuitem action="ReleaseSwitch" />
        <menuitem action="ReleaseCoverArt" />
        <menuitem action="ReleaseMetadata" />
        <menuitem action="ReleaseBrowse" />
        <menuitem action="ReleaseIndexDigital" />
        <menuitem action="ReleaseTracklist" />
        <separator />
        <menuitem action="ReleaseCheckOut" />
        <menuitem action="ReleaseComment" />
        <menuitem action="ReleaseCount" />
        <menuitem action="ReleaseListen" />
        <menuitem action="ReleaseDigital" />
        <menuitem action="ReleasePurchase" />
        <menuitem action="ReleaseRate" />
      </menu>
      <menu action="Search">
        <menuitem action="SearchBarcode" />
        <menuitem action="SearchArtistTitle" />
        <menuitem action="SearchTrack" />
        <menuitem action="SearchReleaseID" />
      </menu>
      <menu action="Filter">
        <menu action="FilterFormat">
          <menuitem action="FormatAll" />
          <menuitem action="FormatDigital" />
          <menuitem action="FormatCD" />
          <menuitem action="Format7Inch" />
          <menuitem action="Format12Inch" />
        </menu>
        <menuitem action="FilterQuick"/>
        <menuitem action="FilterExpression"/>
        <menuitem action="FilterIncomplete"/>
        <separator />
        <menuitem action="FilterClear"/>
      </menu>
      <menu action="Webservice">
        <menuitem action="WebDiscId"/>
        <separator />
        <menuitem action="WebReleaseGroup"/>
        <menuitem action="WebRelease"/>
        <menuitem action="WebBarcode"/>
        <menuitem action="WebCatNo"/>
        <separator />
        <menuitem action="WebSyncColl"/>
      </menu>
      <menu action="Help">
        <menuitem action="About"/>
      </menu>
    </menubar>
    <toolbar name="Toolbar">
      <separator/>
      <toolitem action="ViewDetailPane"/>
      <separator/>
      <placeholder name="FilterFormat">
        <toolitem action="FormatAll"/>
        <toolitem action="FormatDigital"/>
        <toolitem action="FormatCD"/>
        <toolitem action="Format7Inch"/>
        <toolitem action="Format12Inch"/>
      </placeholder>
      <separator/>
      <toolitem action="SearchClear"/>
    </toolbar>
    </ui>'''

    menu_release_items = [
            'ViewScrollSelected',
            'ReleaseRate',
            'ViewXML',
            'ReleaseDelete',
            'ReleaseSwitch',
            'ReleaseCoverArt',
            'ReleaseMetadata',
            'ReleaseBrowse',
            'ReleaseIndexDigital',
            'ReleaseTracklist',
            ]

    def __init__(self, dbPath, cachePath):
        self.prefs = mbcat.userprefs.PrefManager()
        self.catalog = mbcat.catalog.Catalog(dbPath, cachePath, self.prefs)
        self.filt = ''
        self.filtFmt = ''

        # Create the toplevel window
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.set_title(self.__name__)
        try:
            self.window.set_icon_from_file(self.__icon_file__)
        except glib.GError as e:
            print (e)
            try:
                self.window.set_icon_from_file(self.__png_icon_file__)
            except glib.GError:
                print (e)
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
        self.window.add(vbox)

        # Create a UIManager instance
        uimanager = gtk.UIManager()
        self.uimanager = uimanager

        # Add the accelerator group to the toplevel window
        accelgroup = uimanager.get_accel_group()
        self.window.add_accel_group(accelgroup)

        # Create an ActionGroup
        actiongroup = gtk.ActionGroup('UIManagerExample')
        self.actiongroup = actiongroup

        # Create a ToggleAction, etc.
        actiongroup.add_toggle_actions([
            ('ViewToolbar', None, 'Tool Bar',
                None, 'Show/hide tool bar', self.toggleToolBar, True),
            ('ViewDetailPane', None, 'Detail Pane',
                None, 'Show/hide release detail pane', self.toggleDetailPane),
            ('ViewStatusBar', None, 'Status Bar',
                None, 'Show/hide status bar', self.toggleStatusBar, True),
            ])

        # Create actions
        actiongroup.add_actions([
            ('Catalog', None, '_Catalog'),
            ('Quit', gtk.STOCK_QUIT, '_Quit', '<Control>q',
                'Quit the Program', self.destroy),
            ('Open', gtk.STOCK_OPEN, '_Open Database', None,
                'Open a different database file', self.menuCatalogOpen),
            ('SaveAs', gtk.STOCK_SAVE_AS, '_Save Database As', None,
                'Save database file to a new location', self.menuCatalogSaveAs),
            ('Import', None, '_Import'),
            ('ImportDatabase', None, '_Database', None,
                'Import database file', self.menuCatalogImportDB),
            ('ImportZip', None, '_Zip', None,
                'Import zip file', self.menuCatalogImportZip),
            ('Export', None, '_Export'),
            ('ExportZip', None, '_Zip', None,
                'Export to zip file', self.menuCatalogExportZip),
            ('ExportHTML', None, '_HTML', None,
                'Export HTML file', self.menuCatalogExportHtml),
            ('RefreshMetadata', gtk.STOCK_REFRESH, 'Refresh _Metadata',
                None, 'Refresh all release metadata', self.menuCatalogRefresh),
            ('IndexDigital', gtk.STOCK_HARDDISK, 'Index _Digital',
                None, 'Index digital copies of releases',
                self.menuCatalogIndexDigital),
            ('DatabaseVacuum', gtk.STOCK_CLEAR, 'Vacuum Database',
                None, 'Reduce space used by database file',
                self.menuCatalogVacuum),
            ('DatabaseRebuild', gtk.STOCK_EXECUTE, 'Rebuild Derived Tables',
                None, 'Rebuild derived tables in database',
                self.menuCatalogRebuild),
            ('DatabaseFindSimilar', gtk.STOCK_FIND, 'Find Similar Releases',
                None, 'Find similar releases in database',
                self.menuCatalogGetSimilar),
            ('Preferences', None, 'Preferences', '<Control>p',
                'Edit user preferences', self.menuPreferences),
            ('View', None, '_View'),
            ('ViewRefresh', gtk.STOCK_REFRESH, '_Refresh',
                None, 'Refresh view', self.refreshView),
            ('ViewScrollSelected', None, '_Scroll to Selected',
                None, 'Scroll to selected release', self.scrollToSelected),
            ('ViewXML', None, 'View _XML',
                None, 'View XML of release', self.viewXml),
            ('Release', None, '_Release'),
            ('ReleaseAdd', gtk.STOCK_ADD, '_Add Release', '<Control>a',
                'Add release', self.addRelease),
            ('ReleaseDelete', gtk.STOCK_DELETE, '_Delete Release',
                '<Control>Delete', 'Delete release', self.deleteRelease),
            ('ReleaseSwitch', gtk.STOCK_CONVERT, '_Switch',
                None, 'Switch a release with another', self.switchRelease),
            ('ReleaseCoverArt', gtk.STOCK_REFRESH, 'Fetch Co_ver Art',
                None, 'Fetch cover art', self.getCoverArt),
            ('ReleaseMetadata', gtk.STOCK_REFRESH, '_Refresh Metadata',
                None, 'Refresh metadata', self.refreshRelease),
            ('ReleaseBrowse', gtk.STOCK_REFRESH, '_Browse to Release',
                None, 'Open browser to release URL', self.browseRelease),
            ('ReleaseIndexDigital', gtk.STOCK_HARDDISK, '_Index Digital Copies',
                None, 'Index digital copies of selected release',
                self.menuReleaseIndexDigital),
            ('ReleaseTracklist', gtk.STOCK_INDEX, 'Track _List',
                None, 'Show release track listing', self.showTrackList),
            ('ReleaseCheckOut', None, '_Check Out/In',
                None, 'Check out history', self.checkOutDialog),
            ('ReleaseComment', gtk.STOCK_EDIT, 'Co_mment',
                None, 'Edit release comments', self.editComment),
            ('ReleaseCount', None, 'Cou_nt',
                None, 'Edit release count', self.changeCount),
            ('ReleaseListen', None, 'Listen Events',
                None, 'Edit listen events', self.listen),
            ('ReleaseDigital', gtk.STOCK_OPEN, 'Digital _Paths',
                None, 'Edit digital paths', self.digitalPaths),
            ('ReleasePurchase', None, 'Purchase History',
                None, 'Edit purchase history', self.purchaseInfo),
            ('ReleaseRate', None, '_Rate',
                None, 'Rate release', self.rateRelease),
            ('Search', None, '_Search'),
            ('SearchBarcode', None, 'Barcode (UPC)', None,
                'Search for release by barcode', self.searchBarcode),
            ('SearchArtistTitle', None, 'Artist/Title', None,
                'Search by keywords in artist or title',
                self.searchArtistTitle),
            ('SearchTrack', None, 'Track', None, 'Search for track by name',
                self.searchTrack),
            ('SearchReleaseID', None, 'Release ID', None,
                'Search for release by ID', self.searchReleaseID),
            ('Filter', None, '_Filter'),
            ('FilterFormat', None, '_Format'),
            ('FilterQuick', None, 'Quick Search', None,
                'Filter by keywords', self.menuFilterQuick),
            ('FilterExpression', None, 'SQL Expression', None,
                'Filter by SQL expression', self.menuFilterExpression),
            ('FilterIncomplete', None, 'Incomplete Data', None,
                'Filter releases except those with incomplete metadata',
                self.menuCatalogCheck),
            ('FilterClear', gtk.STOCK_CLEAR, 'Clear Filters', None, None,
                    self.menuClearFilters),
            ('SearchClear', gtk.STOCK_CLEAR, 'Clear Search', None, None,
                    self.menuClearSearch),
            ('Webservice', None, '_Webservice'),
            ('WebDiscId', gtk.STOCK_CDROM, '_Disc Lookup', None,
                'Read disc TOC and query by disc ID', self.readDiscTOC),
            ('WebReleaseGroup', None, 'Release Group', None,
                'Search for release group by keywords',
                self.webserviceReleaseGroup),
            ('WebRelease', None, 'Release', None,
                'Search for release by keywords', self.webserviceRelease),
            ('WebBarcode', None, 'Barcode (UPC)', None,
                'Search for release by barcode', self.webserviceBarcode),
            ('WebCatNo', None, 'Catalog Number', None,
                    'Search for release by catalog number',
                    self.webserviceCatNo),
            ('WebSyncColl', None, 'Sync Collection', None,
                    'Synchronize with a collection on musicbrainz.org',
                    self.webserviceSyncCollection),
            ('Help', None, '_Help'),
            ('About', None, '_About', None, None, self.openAboutWindow),
            ])
        actiongroup.get_action('Quit').set_property('short-label', '_Quit')

        # Create some RadioActions
        actiongroup.add_radio_actions([
            ('FormatAll', None, 'All', None, 'All Formats', 0),
            ('FormatDigital', None, 'Digital', None, 'Digital Releases', 1),
            ('FormatCD', None, 'CD', None, 'Compact Disc', 2),
            ('Format7Inch', None, '7" Vinyl', None, '7" Vinyl', 3),
            ('Format12Inch', None, '12" Vinyl', None, '12" Vinyl', 4),
            ], 0, self.selectFormat)

        # Add the actiongroup to the uimanager
        uimanager.insert_action_group(actiongroup, 0)

        # Add a UI description
        uimanager.add_ui_from_string(self.ui_xml)

        # Create a MenuBar
        menubar = uimanager.get_widget('/MenuBar')
        vbox.pack_start(menubar, False)

        # Create a Toolbar
        toolbar = uimanager.get_widget('/Toolbar')
        vbox.pack_start(toolbar, False)
        self.toolbar_force_important()

        # Add search bar to Toolbar
        self.searchentry = gtk.Entry()
        self.searchentry.connect('activate', self.search_callback)
        self.searchentry.show()
        searchitem = gtk.ToolItem()
        searchitem.show()
        #searchitem.set_tooltip(toolbar.tooltips, 'Search for release keywords')
        searchitem.add(self.searchentry)
        toolbar.insert(searchitem, 11)

        # Set sensitivities
        self.menu_release_items_set_sensitive(False)

        # Create tree view for releases
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

        # The final step is to display this newly created widget.
        # and the window
        vbox.show()
        self.window.show()

        self.openDatabase()

        return

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
