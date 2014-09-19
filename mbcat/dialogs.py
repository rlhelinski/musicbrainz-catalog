import threading
import datetime
# only for examples
import random, time
import gobject
import gtk

def DummyTask():
    """
    This task does nothing, forever. It demonstrates how to create a generator
    for running tasks in a progress dialog with TaskHandler.
    """
    while True:
        time.sleep(0.1)
        yield random.random()

def ExampleTask1():
    """
    Count from 0 to 99.
    """
    N = 100
    for i in range(N):
        time.sleep(0.1)
        yield float(i)/N
    yield False

def ExampleTask2():
    """
    Pretend that we don't know how much work there is to do and just indicate
    that something is happening.
    """
    N = 100
    for i in range(N):
        time.sleep(0.1)
        yield True
    yield False

def ExampleTask3():
    """
    Indicate that there are 100 things to do and then count from 0 to 99.
    """
    N = 100
    yield N
    for i in range(N):
        time.sleep(0.1)
        yield float(i)/N
    yield False

class TaskHandler(threading.Thread):
    """This class sets the fraction of the progressbar"""
    
    #Thread event, stops the thread if it is set.
    stopthread = threading.Event()

    def __init__(self, parent, task_generator,
            initStatusLabel='Doing something...',
            processLabel='Processing'):
        super(TaskHandler, self).__init__()
        self.stopthread.clear()
        self.task_generator = task_generator

        gtk.gdk.threads_enter()
        # Create progressbar window
        self.window = gtk.Window(type=gtk.WINDOW_TOPLEVEL)
        self.window.set_transient_for(parent)
        self.window.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
        self.window.set_resizable(False)
        self.window.set_border_width(10)
        self.window.connect('destroy', self.on_destroy)
        self.window.connect('delete_event', self.on_delete)

        vbox = gtk.VBox(False, 10)
        self.status = gtk.Label(initStatusLabel)
        self.status.set_width_chars(60)
        vbox.pack_start(self.status)
        self.progressbar = gtk.ProgressBar()
        vbox.pack_start(self.progressbar)

        # Finished building the window
        self.window.add(vbox)
        self.window.set_title(processLabel)
        self.window.show_all()

        gtk.gdk.threads_leave()

        self.currval = 0
        self.maxval = None
        self.last_update_time = 0
        self.seconds_elapsed = 0
        self.start_time = time.time()
        self.update_interval = 0.1

    def run(self):
        """Run method, this is the code that runs while thread is alive."""

        #While the stopthread event isn't setted, the thread keeps going on
        while not self.stopthread.isSet():
            r = self.task_generator.next()
            if r is False:
                self.window.destroy()
                break
            self.update(r)

    def _need_update(self):
        """Returns whether the ProgressBar should be redrawn."""

        delta = time.time() - self.last_update_time
        return delta > self.update_interval

    def update(self, value):
        # The different types of values that can be yielded
        if isinstance(value, int) and value is not True:
            self.currval = 0
            self.maxval = value
            return
        elif isinstance(value, float):
            f = value
        elif value is True:
            self.currval += 1
            f = float(self.currval) / self.maxval
        elif isinstance(value, unicode) or isinstance(value, str):
            gtk.gdk.threads_enter()
            self.status.set_text(value)
            gtk.gdk.threads_leave()
            return

        # Decide if the GUI needs to be updated
        if not self._need_update():
            return

        now = time.time()
        self.seconds_elapsed = now - self.start_time

        # Acquire the gtk global mutex
        gtk.gdk.threads_enter()
        #Set a random value for the fraction
        if isinstance(value, float) or self.maxval:
            self.progressbar.set_fraction(f)
        else:
            self.progressbar.pulse()

        # Add text to progressbar
        if self.maxval:
                self.progressbar.set_text('%d / %d : %s' % (
                    self.currval,
                    self.maxval,
                    self.ETA(f)))
        elif isinstance(value, float):
            self.progressbar.set_text('%f %% : %s' % (
                value,
                self.ETA(value)))
        else:
            self.progressbar.set_text('%d' % self.currval)

        # Release the gtk global mutex
        gtk.gdk.threads_leave()

        self.last_update_time = now

    @staticmethod
    def format_time(seconds):
        """Formats time as the string "HH:MM:SS"."""

        return str(datetime.timedelta(seconds=int(seconds)))

    def ETA(self, fract):
        if fract == 0 or fract == 0.0:
            return 'ETA:  --:--:--'
        else:
            eta = self.seconds_elapsed / fract - self.seconds_elapsed
            return 'ETA:  %s' % self.format_time(eta)

    def stop(self):
        """Stop method, sets the event to terminate the thread's main loop"""
        self.stopthread.set()
        gtk.gdk.threads_enter()
        self.window.destroy()
        gtk.gdk.threads_leave()

    def on_delete(self, widget, event, data=None):
        # Change FALSE to TRUE and the main window will not be destroyed
        # with a "delete_event".
        return False

    def on_destroy(self, widget, data=None):
        self.stop()

