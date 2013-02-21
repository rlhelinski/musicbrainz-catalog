import xml.etree.ElementTree as ET
import os, time

class PurchaseEvent:
	def __init__(self, date, price, vendor):
		self.date = time.strptime(date, '%m/%d/%Y')
		self.price = float(price)
		self.vendor = vendor

class ExtraData:
	def __init__(self, releaseId, path='release-id'):
		self.path = os.path.join(path, releaseId, 'extra.xml')
		#self.root = ET.Element('extra')
		self.purchases = []

	def load(self):
		tree = ET.parse(self.path)
		root = tree.getroot()
		for purchase in root.findall('./purchase'):
			self.purchases.append(PurchaseEvent( \
				purchase.attrib['date'], \
				purchase.attrib['price'], \
				purchase.attrib['vendor'] ) )
		for comment in root.findall('./comment'):
			self.comment = comment.text
		for rating in root.findall('./rating'):
			self.rating = int(rating.text)
		return root

	def save(self):
		# <?xml version="1.0" encoding="UTF-8"?>

		ET.dump(self.tree)

	def __setitem__(self, name, value):
		print name, value
		#ET.SubElement(self.root, 
