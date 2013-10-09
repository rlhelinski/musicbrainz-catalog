# defaults
# TODO scratch that, they should be loaded independently since they are 
# platform-specific. 
import os
import xml.etree.ElementTree as etree

# http://stackoverflow.com/questions/749796/pretty-printing-xml-in-python/4590052#4590052
def xml_indent(elem, level=0):
    """Add white space to XML DOM so that when it is converted to a string, it is pretty."""

    i = "\n" + level*"  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for elem in elem:
            xml_indent(elem, level+1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i

    return elem

class PrefManager:
    def __init__(self):
        self.prefFile = os.path.expanduser(os.path.join('~', '.mbcat', 'userprefs.xml'))
        self.musicPaths = []
        self.username = ''

        if (os.path.isfile(self.prefFile)):
            self.load()
        else:
            self.musicPaths = [os.path.expanduser(os.path.join('~', 'Music'))]
            self.save()

    def load(self):
        mytree = etree.parse(self.prefFile)
        myroot = mytree.getroot()

        for child in myroot:
            if (child.tag == 'musicpaths'):
                for path in child:
                    #print "User Preferences: " + child.attrib['name'] + " = " + child.attrib['value']
                    self.musicPaths.append(path.text)
                    print 'Music path: ' + path.text
            elif (child.tag == 'account'):
                if 'username' in child.attrib:
                    self.username = child.attrib['username']
                    # could also store password

        print "Loaded preferences from '%s'" % self.prefFile

    def save(self):
        myxml = etree.Element('xml', attrib={'version':'1.0', 'encoding':'UTF-8'})

        pathsTag = etree.SubElement(myxml, 'musicpaths')
        for path in self.musicPaths:
            pathTag = etree.SubElement(pathsTag, 'pref')
            pathTag.text = path
        accountTag = etree.SubElement(myxml, 'account', attrib={'username':self.username})
        # could also load password

        if (not os.path.isdir(os.path.dirname(self.prefFile))):
            os.mkdir(os.path.dirname(self.prefFile))

        xml_indent(myxml)
        with open(self.prefFile, 'w') as xmlfile:
            xmlfile.write(etree.tostring(myxml))

        print "Preferences saved to '%s'" % self.prefFile
    
