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

class UIManagerExample:
    ui = '''<ui>
    <menubar name="MenuBar">
      <menu action="Catalog">
        <menuitem action="Open"/>
        <menuitem action="Save As"/>
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
      <toolitem action="Quit"/>
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
    </toolbar>
    </ui>'''

    def __init__(self):
        # Create the toplevel window
        window = gtk.Window()
        window.connect('destroy', lambda w: gtk.main_quit())
        window.set_size_request(300, -1)
        vbox = gtk.VBox()
        window.add(vbox)

        # Create a UIManager instance
        uimanager = gtk.UIManager()

        # Add the accelerator group to the toplevel window
        accelgroup = uimanager.get_accel_group()
        window.add_accel_group(accelgroup)

        # Create an ActionGroup
        actiongroup = gtk.ActionGroup('UIManagerExample')
        self.actiongroup = actiongroup

        # Create a ToggleAction, etc.
        actiongroup.add_toggle_actions([
            ('ViewToolbar', None, 'Show Tool Bar'),
            ('ViewDetailPane', None, 'Show Detail Pane'),
            ('ViewStatusBar', None, 'Show Status Bar'),
            ])

        # Create actions
        actiongroup.add_actions([
            ('Catalog', None, '_Catalog'),
            ('Quit', gtk.STOCK_QUIT, '_Quit me!', None,
                'Quit the Program', self.quit_cb),
            ('Open', gtk.STOCK_OPEN, '_Open Database', None,
                'Open a different database file', self.load_cb),
            ('Save As', gtk.STOCK_SAVE_AS, '_Save Database As', None,
                'Save database file to a new location', self.save_as_cb),
            ('Import', None, '_Import'),
            ('ImportDatabase', None, '_Database'),
            ('ImportZip', None, '_Zip'),
            ('Export', None, '_Export'),
            ('ExportZip', None, '_Zip'),
            ('ExportHTML', None, '_HTML'),
            ('RefreshMetadata', gtk.STOCK_REFRESH, 'Refresh _Metadata'),
            ('IndexDigital', gtk.STOCK_HARDDISK, 'Index _Digital'),
            ('DatabaseVacuum', gtk.STOCK_CLEAR, 'Vacuum Database'),
            ('DatabaseRebuild', gtk.STOCK_EXECUTE, 'Rebuild Derived Tables'),
            ('DatabaseFindSimilar', gtk.STOCK_FIND, 'Find Similar Releases'),
            ('Preferences', None, 'Preferences', '<Control>p'),
            ('View', None, '_View'),
            ('ViewRefresh', gtk.STOCK_REFRESH, '_Refresh'),
            ('ViewScrollSelected', None, '_Scroll to Selected'),
            ('ViewXML', None, 'View _XML'),
            ('Release', None, '_Release'),
            ('ReleaseAdd', gtk.STOCK_ADD, '_Add Release', '<Control>a'),
            ('ReleaseDelete', gtk.STOCK_DELETE, '_Delete Release', '<Control>Delete'),
            ('ReleaseSwitch', gtk.STOCK_CONVERT, '_Switch'),
            ('ReleaseCoverArt', gtk.STOCK_REFRESH, 'Fetch Co_ver Art'),
            ('ReleaseMetadata', gtk.STOCK_REFRESH, '_Refresh Metadata'),
            ('ReleaseBrowse', gtk.STOCK_REFRESH, '_Browse to Release'),
            ('ReleaseIndexDigital', gtk.STOCK_HARDDISK, '_Index Digital Copies'),
            ('ReleaseTracklist', gtk.STOCK_INDEX, 'Track _List'),
            ('ReleaseCheckOut', None, '_Check Out/In'),
            ('ReleaseComment', gtk.STOCK_EDIT, 'Co_mment'),
            ('ReleaseCount', None, 'Cou_nt'),
            ('ReleaseListen', None, 'Listen Events'),
            ('ReleaseDigital', None, 'Digital _Paths'),
            ('ReleasePurchase', None, 'Purchase History'),
            ('ReleaseRate', None, '_Rate'),
            ('Search', None, '_Search'),
            ('SearchBarcode', None, 'Barcode (UPC)'),
            ('SearchArtistTitle', None, 'Artist/Title'),
            ('SearchTrack', None, 'Track'),
            ('SearchReleaseID', None, 'Release ID'),
            ('Filter', None, '_Filter'),
            ('FilterFormat', None, '_Format'),
            ('FilterQuick', None, 'Quick Search'),
            ('FilterExpression', None, 'SQL Expression'),
            ('FilterIncomplete', None, 'Incomplete Data'),
            ('FilterClear', None, 'Clear Filters'),
            ('Webservice', None, '_Webservice'),
            ('WebDiscId', gtk.STOCK_CDROM, '_Disc Lookup'),
            ('WebReleaseGroup', None, 'Release Group'),
            ('WebRelease', None, 'Release'),
            ('WebBarcode', None, 'Barcode (UPC)'),
            ('WebCatNo', None, 'Catalog Number'),
            ('WebSyncColl', None, 'Sync Collection'),
            ('Help', None, '_Help'),
            ('About', None, '_About'),
            ])
        actiongroup.get_action('Quit').set_property('short-label', '_Quit')

        # Create some RadioActions
        actiongroup.add_radio_actions([
            ('FormatAll', None, 'All', None, 'All Formats', 0),
            ('FormatDigital', None, 'Digital', None, 'Digital Releases', 1),
            ('FormatCD', None, 'CD', None, 'Compact Disc', 2),
            ('Format7Inch', None, '7" Vinyl', None, '7" Vinyl', 3),
            ('Format12Inch', None, '12" Vinyl', None, '12" Vinyl', 4),
            ], 0, self.radioband_cb)

        # Add the actiongroup to the uimanager
        uimanager.insert_action_group(actiongroup, 0)

        # Add a UI description
        uimanager.add_ui_from_string(self.ui)

        # Create a MenuBar
        menubar = uimanager.get_widget('/MenuBar')
        vbox.pack_start(menubar, False)

        # Create a Toolbar
        toolbar = uimanager.get_widget('/Toolbar')
        vbox.pack_start(toolbar, False)

        # Create and pack two Labels
        label = gtk.Label('Sound is not muted')
        vbox.pack_start(label)
        self.mutelabel = label
        label = gtk.Label('Radio band is AM')
        vbox.pack_start(label)
        self.bandlabel = label

        # Create buttons to control visibility and sensitivity of actions
        buttonbox = gtk.HButtonBox()
        sensitivebutton = gtk.CheckButton('Sensitive')
        sensitivebutton.set_active(True)
        sensitivebutton.connect('toggled', self.toggle_sensitivity)
        visiblebutton = gtk.CheckButton('Visible')
        visiblebutton.set_active(True)
        visiblebutton.connect('toggled', self.toggle_visibility)
        # add them to buttonbox
        buttonbox.pack_start(sensitivebutton, False)
        buttonbox.pack_start(visiblebutton, False)
        vbox.pack_start(buttonbox)

        window.show_all()
        return

    def mute_cb(self, action):
        # action has not toggled yet
        text = ('muted', 'not muted')[action.get_active()==False]
        self.mutelabel.set_text('Sound is %s' % text)
        return

    def radioband_cb(self, action, current):
        text = ('AM', 'FM', 'SSB')[action.get_current_value()]
        self.bandlabel.set_text('Radio band is %s' % text)
        return

    def load_cb(self, b):
        pass

    def save_as_cb(self, b):
        pass

    def quit_cb(self, b):
        print ('Quitting program')
        gtk.main_quit()

    def toggle_sensitivity(self, b):
        self.actiongroup.set_sensitive(b.get_active())
        return

    def toggle_visibility(self, b):
        self.actiongroup.set_visible(b.get_active())
        return

if __name__ == '__main__':
    ba = UIManagerExample()
    gtk.main()
