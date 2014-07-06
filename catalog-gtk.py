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
import argparse

class MBCatGtk:
    """A GTK interface for managing a MusicBrainz Catalog"""
    __name__ = 'MusicBrainz Catalog GTK Gui'
    __version__ = '0.1'
    __copyright__ = 'Ryan Helinski'
    __website__ = 'https://github.com/rlhelinski/musicbrainz-catalog'

    columnNames = ['Artist', 'Release Title', 'Date', 'Country', 'Label',
        'Catalog #', 'Barcode', 'ASIN']
    columnWidths = [30, 45, 16, 2, 37, 23, 16, 16]
    numFields = ['Barcode', 'ASIN']

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

    def format_comment(self, column, cell, model, it, field):
        row = model.get_value(it, 0)
        cell.set_property('text', 'OK')

    def on_row_activate(self, tree, path, column):
        pass

    def on_row_select(self, treeview):
        model, it = treeview.get_selection().get_selected()
        relId = model.get_value(it, 0)
        self.statusbar.pop(self.context_id)
        self.statusbar.push(self.context_id, relId)


    def createMenuBar(self, widget):
        # Menu bar
        mb = gtk.MenuBar()
        # File menu
        filemenu = gtk.Menu()
        filem = gtk.MenuItem("_File")
        filem.set_submenu(filemenu)

        mb.append(filem)

        # ...
        # Help menu
        helpmenu = gtk.Menu()
        help = gtk.MenuItem("Help")
        help.set_submenu(helpmenu)

        aboutm = gtk.MenuItem("About")
        aboutm.connect("activate", self.openAboutWindow)
        helpmenu.append(aboutm)

        mb.append(help)

        widget.pack_start(mb, False, False, 0)

    def fmtArtist(self, release):
        return ''.join([(cred['artist']['name'] \
            if isinstance(cred, dict) else cred)
            for cred in release['artist-credit']])

    def fmtLabel(self, rel):
        if 'label-info-list' not in rel:
            return ''
        return ', '.join([
            (info['label']['name'] if 'label' in info else '')
            for info in rel['label-info-list']])

    def fmtCatNo(self, rel):
        if 'label-info-list' not in rel:
            return ''
        return ', '.join([
            (info['catalog-number'] if 'catalog-number' in info else '')
            for info in rel['label-info-list']])


    def cellArtist(self, column, cell, model, it, field):
        row = model.get_value(it, 0)
        release = self.catalog.getRelease(model[0])
        cell.set_property('text', self.fmtArtist(release))

    def sortReleaseFunc(self, model, row1, row2, data):
        #sort_column, _ = model.get_sort_column_id()
        sort_column = 0
        value1 = self.catalog.getReleaseSortStr(
            model.get_value(row1, sort_column))
        value2 = self.catalog.getReleaseSortStr(
            model.get_value(row2, sort_column))
        if value1 < value2:
            return -1
        elif value1 == value2:
            return 0
        else:
            return 1

    def makeListStore(self):
        self.releaseList = gtk.ListStore(str, str, str, str, str, str, str, str, str)

        for i, relId in enumerate(self.catalog.getReleaseIds()):
            rel = self.catalog.getRelease(relId)
            self.releaseList.append([relId,
                self.catalog.getArtistSortPhrase(rel),
                rel['title'],
                (rel['date'] if 'date' in rel else ''),
                (rel['country'] if 'country' in rel else ''),
                self.fmtLabel(rel),
                self.fmtCatNo(rel),
                (rel['barcode'] if 'barcode' in rel else ''),
                (rel['asin'] if 'asin' in rel else '')
                ])
        self.releaseList.set_sort_func(0, self.sortReleaseFunc, None)
        self.releaseList.set_sort_column_id(0, gtk.SORT_ASCENDING)

        self.treeview.set_model(self.releaseList)

        return self.releaseList

    def createTreeView(self):
        # create the TreeView
        self.treeview = gtk.TreeView()
        # TODO add ability to sort by headers
        self.treeview.set_headers_clickable(True)
        # rules-hint
        self.treeview.set_rules_hint(True)
        # search by release title; have to add 1 because of UUID at beginning
        self.treeview.set_search_column(self.columnNames.index('Artist')+1)

        # create the TreeViewColumns to display the data
        self.tvcolumn = [None] * len(self.columnNames)
        for n, columnName in enumerate(self.columnNames):
            cell = gtk.CellRendererText()
            cell.set_property('ellipsize', pango.ELLIPSIZE_END)
            cell.set_property('width-chars', self.columnWidths[n])
            if (columnName in self.numFields):
                cell.set_property('xalign', 1.0)
            self.tvcolumn[n] = gtk.TreeViewColumn(columnName, cell)
            self.tvcolumn[n].add_attribute(cell, 'text', n+1)
            self.tvcolumn[n].set_resizable(True)
            self.treeview.append_column(self.tvcolumn[n])

        self.treeview.connect('row-activated', self.on_row_activate)
        self.treeview.connect('cursor-changed', self.on_row_select)
        self.scrolledwindow = gtk.ScrolledWindow()
        self.scrolledwindow.add(self.treeview)

    def __init__(self, catalog):
        self.catalog = catalog

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

        vbox = gtk.VBox(False, 2)

        self.createMenuBar(vbox)
        self.createTreeView()
        self.makeListStore()
        vbox.pack_start(self.scrolledwindow, True, True, 0)

        self.statusbar = gtk.Statusbar()
        self.context_id = self.statusbar.get_context_id('PyGTK')

        # This packs the button into the window (a GTK container).
        vbox.pack_start(self.statusbar, False, False, 0)

        self.window.add(vbox)
    
        # The final step is to display this newly created widget.
        # and the window
        self.window.show_all()

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

    c = mbcat.catalog.Catalog(dbPath=args.database, cachePath=args.cache)
    gui = MBCatGtk(catalog=c)
    gui.main()
