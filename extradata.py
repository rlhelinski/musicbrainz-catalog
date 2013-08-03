import xml.etree.ElementTree as ET
import os, time, datetime

import sys
def getInput():
	return sys.stdin.readline().strip()

class PurchaseEvent:
	dateFmtStr = '%m/%d/%Y'
	dateFmtUsr = 'MM/DD/YYYY'

	def __init__(self, date, price, vendor):
		self.date = date
		self.price = price
		self.vendor = vendor

	def getDate(self):
		return time.strftime(self.dateFmtStr, self._date)

	def setDate(self, date):
		self._date = time.strptime(date, self.dateFmtStr)
	
	date = property(getDate, setDate, doc='purchase date')

	def getPrice(self):
		return "%.2f" % (self._price / 100)

	def setPrice(self, price):
		self._price = int(price * 100)

	price = property(getPrice, setPrice, doc='purchase price')

class ExtraData:
	def __init__(self, releaseId, path='release-id'):
		self.path = os.path.join(path, releaseId, 'extra.xml')
		#self.root = ET.Element('extra')
		self.purchases = []
		self.addDates = []
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
		return root

	def save(self):
		# <?xml version="1.0" encoding="UTF-8"?>

		#ET.dump(self.tree)
		et = ET.ElementTree(self.toElement())
		et.write(self.path)
		
	def __str__(self):
		return "Extra Data:\n" + \
			"\n".join([("Purchased on "+purchase.date+" from "+purchase.vendor+" for "+purchase.price) for purchase in self.purchases]) + \
			"\nComment: " + self.comment + \
			"\nRating: %d / 5" % self.rating

	def addDate(self, date=time.time()):
		self.addDates.append(date)

	def interactiveEntry(self):
		print "Welcome!"
		print "Purchase date ("+PurchaseEvent.dateFmtUsr+"): ",
		dateStr = getInput()
		print "Vendor: ",
		vendorStr = getInput()
		print "Price: ",
		priceStr = getInput()
		pe = PurchaseEvent( dateStr, priceStr, vendorStr )
		if len(self.purchases):
			self.purchases[0] = pe
		else:
			self.purchases.append(pe)
			
		print "Comment: ",
		self.comment = getInput()
		print "Rating (x/5): ",
		self.rating = int(getInput())


