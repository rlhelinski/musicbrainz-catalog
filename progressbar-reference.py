import threading
import random, time
import gobject
import gtk
#Initializing the gtk's thread engine
gobject.threads_init()

def DummyTask():
    """
    This task does nothing at all. It demonstrates how to create a generator
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

class TaskHandler(threading.Thread):
    """This class sets the fraction of the progressbar"""
    
    #Thread event, stops the thread if it is set.
    stopthread = threading.Event()

    def __init__(self, task_generator):
        super(TaskHandler, self).__init__()
        self.task_generator = task_generator

        #Gui bootstrap: window and progressbar
        self.window = gtk.Window()
        self.progressbar = gtk.ProgressBar()
        self.window.add(self.progressbar)
        self.window.show_all()
        #Connecting the 'destroy' event to the main_quit function
        self.window.connect('destroy', main_quit)

    def run(self):
        """Run method, this is the code that runs while thread is alive."""

        #While the stopthread event isn't setted, the thread keeps going on
        while not self.stopthread.isSet():
            r = self.task_generator.next()
            if isinstance(r, bool) and not r:
                self.window.destroy()
                break
            # Acquiring the gtk global mutex
            gtk.threads_enter()
            #Setting a random value for the fraction
            if isinstance(r, float):
                self.progressbar.set_fraction(r)
            elif isinstance(r, bool):
                self.progressbar.pulse()
            else:
                gtk.threads_leave()
                raise ValueError('Unsupported type yielded by generator')
            # Releasing the gtk global mutex
            gtk.threads_leave()

    def stop(self):
        """Stop method, sets the event to terminate the thread's main loop"""
        self.stopthread.set()
        self.window.destroy()

def main_quit(obj):
    """main_quit function, it stops the thread and the gtk's main loop"""
    #Importing the fs object from the global scope
    global th
    #Stopping the thread and the gtk's main loop
    th.stop()
    gtk.main_quit()


#Creating and starting the thread
#th = TaskHandler(DummyTask())
#th = TaskHandler(ExampleTask1())
th = TaskHandler(ExampleTask2())
th.start()

print threading.enumerate()

try:
    gtk.main()
except KeyboardInterrupt:
    # Kill the thread
    th.stop()
