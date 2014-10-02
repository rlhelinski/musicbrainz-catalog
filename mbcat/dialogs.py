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
        while self.task.isAlive():
            if self.task.status:
                gobject.idle_add(self.status.set_text, self.task.status)
            seconds_elapsed = time.time() - tstart
            if self.task.denom == 0:
                text = '{} - '.format(self.task.numer)+\
                    self.format_time(seconds_elapsed)+' Elapsed'
                gobject.idle_add(self.progressbar.pulse)
            else:
                fract = float(self.task.numer)/self.task.denom
                text = '{} / {} - '.format(self.task.numer, self.task.denom)+\
                    self.ETA(fract, seconds_elapsed)+' Remaining'
                gobject.idle_add(self.progressbar.set_fraction, fract)

            gobject.idle_add(self.progressbar.set_text, text)
            time.sleep(0.1)

        self.quit()

    @staticmethod
    def format_time(seconds):
        """Formats time as the string "MM:SS.mm"."""
        td = datetime.timedelta(seconds=round(seconds,2))
        return '{:02}:{:02}.{:02}'.format(
                td.seconds % 3600 // 60,
                td.seconds % 60,
                td.microseconds // 10000)

    def ETA(self, fract, seconds_elapsed):
        if fract == 0 or fract == 0.0:
            return '--:--.--'
        else:
            eta = seconds_elapsed / fract - seconds_elapsed
            return self.format_time(eta)

    def quit(self):
        gobject.idle_add(self.pbarwindow.destroy)

    def stop(self):
        """Stop method, sets the event to terminate the thread's main loop"""
        self.task.stop()
        self.quit()

import progressbar
class TextProgress(ProgressDialog):
    """Text-mode version of ProgressDialog"""
    detWidgets = [
            progressbar.Bar(marker="=", left="[", right="]"),
            " ",
            progressbar.Percentage()
            ]

    undetWidgets = [
            progressbar.Counter(),
            " ",
            progressbar.AnimatedMarker()
            ]

    def __init__(self, task):
        super(ProgressDialog, self).__init__()
        # not sure if we need this if this window is destroyed with its parent
        self.setDaemon(True)
        self.task = task


    def run(self):
        """Run method, this is the code that runs while thread is alive."""
        self.task.start()
        self.method = None

        tstart = time.time()
        while self.task.isAlive():
            seconds_elapsed = time.time() - tstart
            if self.task.denom != 0:
                if not self.method or self.method != 'det':
                    self.method = 'det'
                    self.pbar = progressbar.ProgressBar(
                            widgets=[self.task.status]+self.detWidgets)
                    self.pbar.start()
                self.pbar.maxval=self.task.denom
            else:
                if not self.method or self.method != 'undet':
                    self.method = 'undet'
                    self.pbar = progressbar.ProgressBar(
                            widgets=[self.task.status]+self.undetWidgets)
                    self.pbar.start()
                self.pbar.maxval = progressbar.progressbar.UnknownLength
            self.pbar.update(self.task.numer)
            time.sleep(0.1)

        self.quit()

    def quit(self):
        self.pbar.finish()


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

    def __init__(self, fun, *args, **kwargs):
        super(ThreadedCall, self).__init__()
        self.setDaemon(True)
        self.fun = fun
        self.args = args
        self.kwargs = kwargs

    def run(self):
        """Run method, this is the code that runs while thread is alive.
        This is just an example. You can make your own by creating a class
        that inherits this class and defining your own run() method."""
        self.result = self.fun(*self.args, **self.kwargs)

    def stop(self):
        """We can't actually interrupt the call because of Python's threading
        limitations, but we provide this function to keep API consistent."""
        pass

# TODO move this to another module so that importing gtk is not necessary for
# the catalog
class ThreadedTask(threading.Thread):
    """This does something that takes a while and keeps track of its own
    progress"""

    def __init__(self, denom):
        super(ThreadedTask, self).__init__()
        self.setDaemon(True)
        self.denom = denom
        self.numer = 0
        self.status = ''

        #Thread event, stops the thread if it is set.
        self.stopthread = threading.Event()

    def run(self):
        """Run method, this is the code that runs while thread is alive.
        This is just an example. You can make your own by creating a class
        that inherits this class and defining your own run() method."""

        while not self.stopthread.isSet():
            if self.numer > self.denom:
                break
            time.sleep(1)
            self.numer += 1

    def incr(self):
        self.numer += 1

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
def run_long_task(window):
    t = ProgressDialog(window, ThreadedTask(10)).start()

def run_mutex_task(window):
    t = ProgressDialog(window, MutexTask(10)).start()

class pulse_task(ThreadedCall):
    def run(self):
        ThreadedCall.run(self)
        # This is the thing we want to do after the thread is done
        print ('Result: '+str(self.result))

def run_pulse_task(window):
    t = PulseDialog(window, pulse_task(much_fun, 10)).start()

