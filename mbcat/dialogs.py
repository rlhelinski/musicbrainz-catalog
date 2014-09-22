import threading
import datetime
# only for examples
import random, time
import gobject
import gtk

class ProgressDialog(threading.Thread):
    """This does something that takes a while and keeps track of its own
    progress"""

    def __init__(self, parentWindow, task):
        super(ProgressDialog, self).__init__()
        self.task = task
        self.parentWindow = parentWindow

        self.pbarwindow = gtk.Window()
        self.pbarwindow.set_transient_for(parentWindow)
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

