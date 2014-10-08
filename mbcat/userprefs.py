# defaults
# TODO scratch that, they should be loaded independently since they are 
# platform-specific. 
import logging
_log = logging.getLogger("mbcat")
import os
import xml.etree.ElementTree as etree
import xml.dom.minidom
from . import defaultPathSpec
import musicbrainzngs

class PrefManager:
    def __init__(self):
        self.prefFile = os.path.expanduser(os.path.join('~', '.mbcat', 'userprefs.xml'))
        self.pathRoots = []
        self.username = ''
        self.htmlPubPath = ''
        self.pathFmts = dict()
        self.defaultPathSpec = defaultPathSpec

        if (os.path.isfile(self.prefFile)):
            self.load()
        else:
            self.pathRoots = [os.path.expanduser(os.path.join('~', 'Music'))]
            self.htmlPubPath = '.'
            self.save()

    def load(self):
        mytree = etree.parse(self.prefFile)
        myroot = mytree.getroot()

        for child in myroot:
            if (child.tag == 'pathroots'):
                for path in child:
                    if path.tag != 'path':
                        raise Exception('Tags under pathroots must be <path> tags.')
                    self.pathRoots.append(path.text)
                    self.pathFmts[path.text] = path.attrib['pathspec'] \
                            if 'pathspec' in path.attrib else \
                                defaultPathSpec
            elif (child.tag == 'default'):
                if 'pathspec' in child.attrib:
                    self.defaultPathSpec = child.attrib['pathspec']
                # can add other generic defaults here
            elif (child.tag == 'account'):
                if 'username' in child.attrib:
                    self.username = child.attrib['username']
                    # could also store password
            elif (child.tag == 'htmlpub'):
                if 'path' in child.attrib:
                    self.htmlPubPath = child.attrib['path']
            elif (child.tag == 'musicbrainz'):
                if 'hostname' in child.attrib:
                    musicbrainzngs.set_hostname = child.attrib['hostname']
                if 'caa_hostname' in child.attrib:
                    musicbrainzngs.set_caa_hostname = \
                            child.attrib['caa_hostname']

        _log.info("Loaded preferences from '%s'" % self.prefFile)

    def save(self):
        myxml = etree.Element('xml', attrib={'version':'1.0', 'encoding':'UTF-8'})

        pathsTag = etree.SubElement(myxml, 'pathroots')
        for path in self.pathRoots:
            pathTag = etree.SubElement(pathsTag, 'path')
            pathTag.text = path
            pathTag.attrib['pathspec'] = self.pathFmts[path]
        defaultPathSpec = etree.SubElement(myxml, 'default', 
                attrib={'pathspec':self.defaultPathSpec})
        accountTag = etree.SubElement(myxml, 'account',
                attrib={'username':self.username})
        # could also load password
        htmlPathTag = etree.SubElement(myxml, 'htmlpub',
                attrib={'path':self.htmlPubPath})
        hostnameTag = etree.SubElement(myxml, 'musicbrainz',
                # TODO the hostname variable in the root namespace is being
                # cascaded by the caa namespace?
                attrib={'hostname':musicbrainzngs.hostname,
                        'caa_hostname':musicbrainzngs.caa.hostname})

        if (not os.path.isdir(os.path.dirname(self.prefFile))):
            os.mkdir(os.path.dirname(self.prefFile))

        with open(self.prefFile, 'wb') as xmlfile:
            xmlfile.write(xml.dom.minidom.parseString(
                    etree.tostring(myxml)).toprettyxml())

        _log.info("Preferences saved to '%s'" % self.prefFile)
    
    def editPathRoot(self, old_path, new_path):
        self.pathRoots[self.pathRoots.index(old_path)] = new_path
        self.pathFmts[new_path] = self.pathFmts[old_path]
        del self.pathFmts[old_path]
        self.save()

    def setPathSpec(self, dig_path, path_spec):
        self.pathFmts[dig_path] = path_spec
        self.save()

    def setDefaultPathSpec(self, path_spec):
        self.defaultPathSpec = path_spec
        self.save()

    def addPathRoot(self, new_path, new_fmt=None):
        if not new_fmt:
            new_fmt = self.defaultPathSpec
        self.pathRoots.append(new_path)
        self.pathFmts[new_path] = new_fmt
        self.save()

    def delPathRoot(self, path):
        del self.pathRoots[self.pathRoots.index(path)]
        del self.pathFmts[path]
        self.save()

    def setUserName(self, username):
        self.username = username
        self.save()

    def setHostName(self, hostname):
        musicbrainzngs.set_hostname = hostname
        self.save()

    def setCAAHostName(self, hostname):
        musicbrainzngs.set_caa_hostname = hostname
        self.save()
