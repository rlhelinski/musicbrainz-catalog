import threading
import datetime
# only for examples
import random, time
import gobject
import gtk

class ProgressDialog(threading.Thread):
    """This does something that takes a while and keeps track of its own
    progress"""

    def __init__(self, parentWindow, task, initStatusLabel='Please Wait...'):
        super(ProgressDialog, self).__init__()
        # not sure if we need this if this window is destroyed with its parent
        self.setDaemon(True)
        self.task = task
        self.parentWindow = parentWindow

        self.pbarwindow = gtk.Window(type=gtk.WINDOW_TOPLEVEL)
        self.pbarwindow.set_transient_for(parentWindow)
        self.pbarwindow.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
        self.pbarwindow.set_resizable(False)
        self.pbarwindow.set_border_width(10)
        self.pbarwindow.connect('destroy', self.on_destroy)
        self.pbarwindow.connect('delete_event', self.on_delete)

        vbox = gtk.VBox(False, 10)
        self.status = gtk.Label(initStatusLabel)
        self.status.set_width_chars(60)
        vbox.pack_start(self.status)

        self.progressbar = gtk.ProgressBar()
        vbox.pack_start(self.progressbar)
        self.pbarwindow.add(vbox)
        self.pbarwindow.show_all()

    def on_delete(self, widget, event, data=None):
        # Change FALSE to TRUE and the main window will not be destroyed
        # with a "delete_event".
        return False

    def on_destroy(self, widget, data=None):
        self.task.stop()

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
        self.setDaemon(True)
        self.fun = fun
        self.args = args

    def run(self):
        """Run method, this is the code that runs while thread is alive.
        This is just an example. You can make your own by creating a class
        that inherits this class and defining your own run() method."""
        self.result = self.fun(*self.args)

    def stop(self):
        """We can't actually interrupt the call because of Python's threading
        limitations, but we provide this function to keep API consistent."""
        pass

class ThreadedTask(threading.Thread):
    """This does something that takes a while and keeps track of its own
    progress"""
    
    def __init__(self, denom):
        super(ThreadedTask, self).__init__()
        self.setDaemon(True)
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

# Some examples
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

