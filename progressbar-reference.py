import threading
import random, time
import gobject
import gtk
#Initializing the gtk's thread engine
gobject.threads_init()

window = None

# 0.04 = 25fps
# 0.041 = 24fps
# 0.055 = 18fps
# 0.083 = 12fps
# 0.125 = 8fps
# 0.166 = 6fps


def much_fun(arg):
    t0 = time.time()
    time.sleep(arg)
    return time.time() - t0

class ProgressDialog(threading.Thread):
    """This does something that takes a while and keeps track of its own
    progress"""

    def __init__(self, task):
        super(ProgressDialog, self).__init__()
        self.task = task

        self.pbarwindow = gtk.Window()
        self.pbarwindow.set_transient_for(window)
        self.progressbar = gtk.ProgressBar()
        self.pbarwindow.add(self.progressbar)
        self.pbarwindow.show_all()

    def run(self):
        """Run method, this is the code that runs while thread is alive."""
        self.task.start()

        tstart = time.time()
        while not self.task.stopthread.isSet():
            fract = float(self.task.numer)/self.task.denom
            seconds_elapsed = time.time() - tstart

            text = '%0.3f Remaining' % (
                seconds_elapsed / fract - seconds_elapsed
                ) if fract != 0 else '?.?? Remaining'
            gobject.idle_add(self.progressbar.set_fraction, fract)
            gobject.idle_add(self.progressbar.set_text, text)
            time.sleep(0.1)

        self.quit()

    def quit(self):
        self.pbarwindow.destroy()

    def stop(self):
        """Stop method, sets the event to terminate the thread's main loop"""
        self.task.stop()
        self.quit()

class PulseDialog(ProgressDialog):
    def run(self):
        """Start the sub-thread; pulse the progress bar until it finishes"""
        self.task.start()

        tstart = time.time()
        while self.task.isAlive():
            gobject.idle_add(self.progressbar.pulse)
            gobject.idle_add(self.progressbar.set_text,
                '%0.3f Elapsed' % (time.time() - tstart))
            time.sleep(0.1)
        self.quit()

class ThreadedCall(threading.Thread):
    """
    This simply runs a function in a new thread.
    This thread class is for inheriting to implement a thread which runs a task
    and does something with the return value.
    """

    def __init__(self, fun, *args):
        super(ThreadedCall, self).__init__()
        self.fun = fun
        self.args = args

    def run(self):
        """Run method, this is the code that runs while thread is alive.
        This is just an example. You can make your own by creating a class
        that inherits this class and defining your own run() method."""
        self.result = self.fun(*self.args)

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
    # TODO keep a list of references to the threads and tell them all to stop here
    gtk.main_quit()

def main_delete(widget, event, data=None):
    # If you return FALSE in the "delete_event" signal handler,
    # GTK will emit the "destroy" signal. Returning TRUE means
    # you don't want the window to be destroyed.
    # This is useful for popping up 'are you sure you want to quit?'
    # type dialogs.
    print ("delete event occurred")

    # Change FALSE to TRUE and the main window will not be destroyed
    # with a "delete_event".
    return False

def run_long_task(widget):
    t = ProgressDialog(ThreadedTask(10)).start()

def run_mutex_task(widget):
    t = ProgressDialog(MutexTask(10)).start()

class pulse_task(ThreadedCall):
    def run(self):
        ThreadedCall.run(self)
        # This is the thing we want to do after the thread is done
        print ('Result: '+str(self.result))

def run_pulse_task(widget):
    t = PulseDialog(pulse_task(much_fun, 10)).start()

window = gtk.Window()
window.set_has_frame(True)
window.set_frame_dimensions(10, 10, 10, 10)
vbox = gtk.VBox(False, 10)
label = gtk.Label('Hello, world!')
vbox.pack_start(label)
button = gtk.Button('Come on, do it!')
button.connect('clicked', run_long_task)
vbox.pack_start(button)
button = gtk.Button('Easy with this one')
button.connect('clicked', run_mutex_task)
vbox.pack_start(button)
button = gtk.Button('This one is touchy!')
button.connect('clicked', run_pulse_task)
vbox.pack_start(button)
window.add(vbox)
window.connect('destroy', main_quit)
window.connect('delete_event', main_delete)
window.show_all()

# TODO show this result in a Label
#print threading.enumerate()

try:
    gtk.main()
except KeyboardInterrupt:
    pass
    # Kill the thread
    #th.stop()
