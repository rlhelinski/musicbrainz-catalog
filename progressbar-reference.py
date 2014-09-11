import threading
import random, time
import gobject
import gtk
#Initializing the gtk's thread engine
gobject.threads_init()

window = None

class ProgressDialog(threading.Thread):
    """This does something that takes a while and keeps track of its own
    progress"""
    
    def __init__(self, task):
        super(ProgressDialog, self).__init__()
        self.task = task

        gtk.gdk.threads_enter()
        self.pbarwindow = gtk.Window()
        self.pbarwindow.set_transient_for(window)
        self.progressbar = gtk.ProgressBar()
        self.pbarwindow.add(self.progressbar)
        self.pbarwindow.show_all()
        gtk.gdk.threads_leave()

    def run(self):
        """Run method, this is the code that runs while thread is alive."""
        self.task.start()

        while not self.task.stopthread.isSet():
            gtk.gdk.threads_enter()
            self.progressbar.set_fraction(
                float(self.task.numer)/self.task.denom)
            self.progressbar.set_text(str(time.time()))
            gtk.gdk.threads_leave()
            time.sleep(0.1)
        self.quit()

    def quit(self):
        self.pbarwindow.destroy()

    def stop(self):
        """Stop method, sets the event to terminate the thread's main loop"""
        self.task.stop()
        self.quit()

class ThreadedTask(threading.Thread):
    """This does something that takes a while and keeps track of its own
    progress"""
    
    def __init__(self, denom):
        super(ThreadedTask, self).__init__()
        self.denom = denom
        self.numer = 0

        #Thread event, stops the thread if it is set.
        self.stopthread = threading.Event()

    def run(self):
        """Run method, this is the code that runs while thread is alive.
        This is just an example. You can make your own by creating a class
        that inherits this class and defining your own run() method."""

        while not self.stopthread.isSet():
            if self.numer > self.denom:
                self.stopthread.set()
                break
            time.sleep(1)
            self.numer += 1

        self.stop()

    def stop(self):
        """Stop method, sets the event to terminate the thread's main loop"""
        self.stopthread.set()

class MutexTask(ThreadedTask):
    """This does something that takes a while and keeps track of its own
    progress.
    This version is mutually exclusive---only one can run at a time."""
    one_running = threading.Event()

    def __init__(self, *args):
        super(MutexTask, self).__init__(*args)

        if self.one_running.isSet():
            raise Exception('one at a time, please')
        self.one_running.set()

    def stop(self):
        """Stop method, sets the event to terminate the thread's main loop"""
        super(MutexTask, self).stop()
        self.one_running.clear()

def main_quit(obj):
    """main_quit function, it stops the thread and the gtk's main loop"""
    #Importing the fs object from the global scope
    global th
    #Stopping the thread and the gtk's main loop
    #th.stop()
    gtk.main_quit()

def run_long_task(widget):
    t = ProgressDialog(ThreadedTask(10)).start()

def run_mutex_task(widget):
    t = ProgressDialog(MutexTask(10)).start()

window = gtk.Window()
vbox = gtk.VBox()
label = gtk.Label('Hello, world!')
vbox.pack_start(label)
button = gtk.Button('Come on, do it!')
button.connect('clicked', run_long_task)
vbox.pack_start(button)
button = gtk.Button('Easy with this one')
button.connect('clicked', run_mutex_task)
vbox.pack_start(button)
window.add(vbox)
window.connect('destroy', main_quit)
window.show_all()

# TODO show this result in a Label
#print threading.enumerate()

try:
    gtk.main()
except KeyboardInterrupt:
    pass
    # Kill the thread
    #th.stop()
