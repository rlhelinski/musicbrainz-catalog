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
import uuid

class PrefManager:
    def __init__(self):
        self.prefFile = os.path.expanduser(os.path.join('~', '.mbcat', 'userprefs.xml'))
        self.pathRoots = dict()
        self.username = ''
        self.htmlPubPath = ''
        self.defaultPathSpec = defaultPathSpec

        if (os.path.isfile(self.prefFile)):
            self.load()
        else:
            self._addPathRoot(os.path.expanduser(os.path.join('~', 'Music')))
            self.htmlPubPath = '.'
            try:
                self.save()
            except:
                _log.error('Failed to create preferences file')

    def load(self):
        mytree = etree.parse(self.prefFile)
        myroot = mytree.getroot()

        for child in myroot:
            if (child.tag == 'pathroots'):
                for root in child:
                    if root.tag != 'root':
                        raise Exception('Tags under pathroots must be <root> tags.')
                    self._addPathRoot(
                            path_id=root.attrib['id'],
                            new_path=root.attrib['path'],
                            path_spec=root.attrib['pathspec'])
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
        for id, path_dict in self.pathRoots.items():
            pathTag = etree.SubElement(pathsTag, 'root')
            pathTag.attrib['id'] = id
            pathTag.attrib['path'] = path_dict['path']
            pathTag.attrib['pathspec'] = path_dict['pathspec']
        defaultPathSpec = etree.SubElement(myxml, 'default',
                attrib={'pathspec':self.defaultPathSpec})
        accountTag = etree.SubElement(myxml, 'account',
                attrib={'username':self.username})
        # could also load password
        htmlPathTag = etree.SubElement(myxml, 'htmlpub',
                attrib={'path':self.htmlPubPath})
        # TODO only write these tags if the settings are not the defaults
        hostnameTag = etree.SubElement(myxml, 'musicbrainz',
                attrib={'hostname':musicbrainzngs.musicbrainz.hostname,
                        'caa_hostname':musicbrainzngs.caa.hostname})

        if (not os.path.isdir(os.path.dirname(self.prefFile))):
            os.mkdir(os.path.dirname(self.prefFile))

        with open(self.prefFile, 'wb') as xmlfile:
            xmlfile.write(xml.dom.minidom.parseString(
                    etree.tostring(myxml)).toprettyxml())

        _log.info("Preferences saved to '%s'" % self.prefFile)

    def setRootPathSpec(self, path_id, path_spec):
        self.pathRoots[path_id]['pathspec'] = path_spec
        self.save()

    def setDefaultPathSpec(self, path_spec):
        self.defaultPathSpec = path_spec
        self.save()

    def _addPathRoot(self, new_path, path_id=None, path_spec=None):
        if not path_id:
            path_id = str(uuid.uuid4())
        if not path_spec:
            path_spec = self.defaultPathSpec

        self.pathRoots[path_id] = dict(
                path= new_path,
                pathspec= path_spec)
        return path_id

    def addPathRoot(self, new_path, path_id=None, path_spec=None):
        path_id = self._addPathRoot(new_path, path_id, path_spec)
        self.save()
        return path_id

    def getRootPath(self, root_id):
        if root_id not in self.pathRoots:
            _log.error('Root ID %s not in user preferences file' % root_id)
            return None
        return self.pathRoots[root_id]['path']

    def getRootIdForPath(self, abs_path):
        for root_id, path_dict in self.pathRoots.items():
            if abs_path.startswith(path_dict['path']):
                found_root_id = root_id
                found_rel_path = os.path.relpath(abs_path, path_dict['path'])
                return found_root_id, found_rel_path
        return (None, None)

    def delPathRoot(self, path_id):
        del self.pathRoots[path_id]
        self.save()

    def editPathRoot(self, path_id, new_path):
        self.pathRoots[path_id]['path'] = new_path
        self.save()

    def getPathRootSpec(self, path_id):
        return self.pathRoots[path_id]['pathspec']

    def setUserName(self, username):
        self.username = username
        self.save()

    def getHostName(self):
        return musicbrainzngs.musicbrainz.hostname

    def setHostName(self, hostname):
        musicbrainzngs.set_hostname = hostname
        self.save()

    def getCAAHostName(self):
        return musicbrainzngs.caa.hostname

    def setCAAHostName(self, hostname):
        musicbrainzngs.set_caa_hostname = hostname
        self.save()
