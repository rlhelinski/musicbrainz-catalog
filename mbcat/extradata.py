from __future__ import print_function
from collections import defaultdict
import os, time, sys
import xml.etree.ElementTree as ET
import mbcat.utils
import logging
_log = logging.getLogger("mbcat")
try:
    from StringIO import StringIO
except ImportError as e:
    from io import StringIO

dateFmtStr = '%m/%d/%Y'
dateFmtUsr = 'MM/DD/YYYY'

class PurchaseEvent:

    def __init__(self, date, price, vendor):
        # Do these calls use the implicit property calls?
        self.date = date
        self.price = price
        self.vendor = vendor

    def getDate(self):
        try:
            return time.strftime(dateFmtStr, time.localtime(self._date))
        except TypeError:
            return ''
        except AttributeError:
            return ''

    def setDate(self, date):
        try:
            self._date = time.strptime(date, dateFmtStr)
        except ValueError as e:
            _log.warning(e)

    date = property(getDate, setDate, doc='purchase date')

    def getPrice(self):
        try:
            return "%.2f" % (self._price / 100)
        except AttributeError:
            return ''

    def setPrice(self, price):
        try:
            self._price = int(float(price) * 100)
        except ValueError as e:
            _log.warning(e)

    price = property(getPrice, setPrice, doc='purchase price')

    def __str__(self):
        return "Purchased on "+self.date+" from "+self.vendor+" for "+self.price

class CheckOutEvent:
    def __init__(self, borrower, date):
        self._date = date
        self.borrower = borrower 

    def getDate(self):
        return time.strftime(dateFmtStr, time.localtime(self._date))

    def setDate(self, date):
        self._date = time.strptime(date, dateFmtStr)

    date = property(getDate, setDate, doc='purchase date')

    def __str__(self):
        return "Lent on: " + self.date + " to: " + self.borrower

class CheckInEvent:
    def __init__(self, date):
        self._date = date

    def getDate(self):
        return time.strftime(dateFmtStr, time.localtime(self._date))

    def setDate(self, date):
        self._date = time.strptime(date, dateFmtStr)

    date = property(getDate, setDate, doc='purchase date')

    def __str__(self):
        return "Returned on: " + self.date

class LendEvent:
    def __init__(self, borrower, date):
        self._date = date
        self.borrower = borrower 

    def getDate(self):
        return time.strftime(dateFmtStr, time.localtime(self._date))

    def setDate(self, date):
        self._date = time.strptime(date, dateFmtStr)

    date = property(getDate, setDate, doc='purchase date')

    def __str__(self):
        return "Lent on: " + self.date + " to: " + self.borrower

class DigitalPath:
    def __init__(self, path, digiFormat):
        self.path=path
        self.digiFormat=digiFormat

# TODO add list of listening events
# TODO add path to audio files on system
class ExtraData:
    def __init__(self, releaseId, path='release-id'):
        if releaseId.startswith('http'):
            releaseId = utils.extractUuid(releaseId, 'release')
        self.path = os.path.join(path, releaseId, 'extra.xml')
        self.purchases = []
        self.addDates = []
        self.lendEvents = []
        self.listenEvents = []
        self.digitalPaths = [] 
        self.comment = ""
        self.rating = 0

    def load(self):
        tree = ET.parse(self.path)
        root = tree.getroot()
        for purchase in root.findall('./purchase'):
            self.purchases.append(PurchaseEvent( \
                    purchase.attrib['date'], \
                    purchase.attrib['price'], \
                    purchase.attrib['vendor'] ) )
        for added in root.findall('./added'):
            self.addDates.append(float(added.attrib['date']))
        for comment in root.findall('./comment'):
            self.comment = comment.text
        for rating in root.findall('./rating'):
            self.rating = int(rating.text)
        for lendList in root.findall('./lendlist'):
            for lend in lendList:
                if lend.tag != 'lent':
                    continue
                self.lendEvents.append(LendEvent(lend.attrib['who'], \
                    int(lend.attrib['date'])))
        for pathList in root.findall('./digital'):
            for path in pathList:
                if path.tag != 'path':
                    continue
                if path.text:
                    self.addPath(path.text)
        
        return root

    def toElement(self):
        root = ET.Element('extra')
        root.text="\n"
        for purchase in self.purchases:
            pe = ET.SubElement(root, 'purchase', attrib={ \
                    'date':purchase.date, \
                    'price':purchase.price, \
                    'vendor':purchase.vendor})
            pe.tail="\n"
        for addDate in self.addDates:
            pe = ET.SubElement(root, 'added', attrib={ \
                    'date':"%d" % addDate})
            pe.tail="\n"
        c = ET.SubElement(root, 'comment')
        c.text=self.comment
        c.tail="\n"
        r = ET.SubElement(root, 'rating')
        r.text=str(self.rating)
        r.tail="\n"
        ll = ET.SubElement(root, 'lendlist')
        ll.tail="\n"
        for lendEvent in self.lendEvents:
            le = ET.SubElement(ll, 'lent', \
                    attrib={
                        'date':'%d' % lendEvent._date,
                        'who':lendEvent.borrower})
            le.tail="\n"
        dl = ET.SubElement(root, 'digital')
        dl.tail="\n"
        for path in self.digitalPaths:
            de = ET.SubElement(dl, 'path') # TODO could add format as attrib
            de.text=path
            de.tail="\n"
        return root

    def save(self):
        et = ET.ElementTree(self.toElement())
        et.write(self.path)

    def toString(self):
        memF = StringIO()
        et = ET.ElementTree(self.toElement())
        et.write(memF)
        memF.seek(0)
        return memF.read()


    def __str__(self):
        return "Extra Data:\n" + \
                "\n".join([str(purchase) for purchase in self.purchases]) + \
                ("\nComment: " + self.comment if self.comment else "") + \
                ("\nRating: %d / 5" % self.rating) + \
                (("\n".join([str(lend) for lend in self.lendEvents])) if self.lendEvents else "") + \
                "\n"

    def addDate(self, date=time.time()):
        self.addDates.append(date)

    def addLend(self, borrower, date):
        if not date:
            #date = time.strftime(dateFmtStr)
            date = time.time()
        self.lendEvents.append(LendEvent(borrower, date))

    def setRating(self, rating=0):
        self.rating = int(rating)

    def addPath(self, path):
        if path not in self.digitalPaths:
            self.digitalPaths.append(path)

    def addPurchase(self, purch):
        self.purchases.append(purch)

