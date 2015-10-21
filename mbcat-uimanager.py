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
        <menuitem action="Quit"/>
      </menu>
      <menu action="Sound">
        <menuitem action="Mute"/>
      </menu>
      <menu action="RadioBand">
        <menuitem action="AM"/>
        <menuitem action="FM"/>
        <menuitem action="SSB"/>
      </menu>
    </menubar>
    <toolbar name="Toolbar">
      <toolitem action="Quit"/>
      <separator/>
      <toolitem action="Mute"/>
      <separator/>
      <placeholder name="RadioBandItems">
        <toolitem action="AM"/>
        <toolitem action="FM"/>
        <toolitem action="SSB"/>
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
        actiongroup.add_toggle_actions([('Mute', None, '_Mute', '<Control>m',
                                         'Mute the volume', self.mute_cb)])

        # Create actions
        actiongroup.add_actions([
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
            ('RefreshMetadata', None, 'Refresh _Metadata'),
            ('IndexDigital', None, 'Index _Digital'),
            ('DatabaseVacuum', None, 'Vacuum Database'),
            ('DatabaseRebuild', None, 'Rebuild Derived Tables'),
            ('DatabaseFindSimilar', None, 'Find Similar Releases'),
            ('Catalog', None, '_Catalog'),
            ('Sound', None, '_Sound'),
            ('RadioBand', None, '_Radio Band')])
        actiongroup.get_action('Quit').set_property('short-label', '_Quit')

        # Create some RadioActions
        actiongroup.add_radio_actions([
            ('AM', None, '_AM', '<Control>a', 'AM Radio', 0),
            ('FM', None, '_FM', '<Control>f', 'FM Radio', 1),
            ('SSB', None, '_SSB', '<Control>s', 'SSB Radio', 2),
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
