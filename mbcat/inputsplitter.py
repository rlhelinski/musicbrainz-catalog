import sys

# Work-around for Python 2.6
try:
    sys.stdout.write(u'\xa6\n')
except UnicodeEncodeError:
    reload(sys).setdefaultencoding('utf8')

class InputSplitter(object):
    def __init__(self, stdin=sys.stdin, stdout=sys.stdout):
        self.stdin = stdin
        self.stdout = stdout
        self.buffer = []

    def write(self, string):
        self.stdout.write(string)
        self.stdout.flush()

    def _readline(self):
        return self.stdin.readline().strip()

    def nextLine(self, prompt=""):
        if prompt:
            self.write(prompt)
        if self.buffer:
            l = ' '.join(self.buffer)
            self.buffer = []
            return l
        else:
            return self._readline()

    def nextWord(self, prompt=""):
        if prompt:
            self.write(prompt)
        if not self.buffer:
            self.buffer = self._readline().split()

        if self.buffer:
            return self.buffer.pop(0)
        else:
            return ''
