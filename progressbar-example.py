import mbcat.gtkpbar
import threading
import gobject
import gtk
#Initializing the gtk's thread engine
gobject.threads_init()

def main_quit(obj):
    """main_quit function, it stops the thread and the gtk's main loop"""
    #Importing the fs object from the global scope
    global th
    #Stopping the thread and the gtk's main loop
    th.stop()
    gtk.main_quit()

#Gui bootstrap: window and progressbar
window = gtk.Window()
label = gtk.Label('Main window')
window.add(label)
window.show_all()
#Connecting the 'destroy' event to the main_quit function
window.connect('destroy', main_quit)

#Creating and starting the thread
#th = TaskHandler(DummyTask())
#th = TaskHandler(ExampleTask1())
th = mbcat.gtkpbar.TaskHandler(window, mbcat.gtkpbar.ExampleTask3())
th.start()

print threading.enumerate()

try:
    gtk.main()
except KeyboardInterrupt:
    # Kill the thread
    th.stop()
