import urllib2
import xml.parsers.expat

from datetime import datetime

from django.template.loader import render_to_string

from crits.core.data_tools import create_zip
from crits.services.core import Service, ServiceConfigError

from . import forms

class OPSWATService(Service):
    """
    Pushes a sample to your local OPSWAT appliance and scans the sample with different custom engines.
    Specify the URL for the REST API. Also include any API option in the URL.

    ie:http://example.org:8008/metascan_rest/scanner?method=scan&archive_pwd=infected'
    """

    name = "OPSWAT"
    version = "1.0.0"
    type_ = Service.TYPE_AV
    supported_types = ['Sample']
    description = "Send a sample to OPSWAT appliance."

    @staticmethod
    def get_config(existing_config):
        if existing_config:
            return existing_config

        config = {}
        fields = forms.OPSWATConfigForm().fields
        for name, field in fields.iteritems():
            config[name] = field.initial
        return config

    @classmethod
    def generate_config_form(self, config):
        html = render_to_string('services_config_form.html',
                                {'name': self.name,
                                 'form': forms.OPSWATConfigForm(initial=config),
                                 'config_error': None})
        form = forms.OPSWATConfigForm
        return form, html

    @staticmethod
    def valid_for(obj):
        if obj.filedata.grid_id == None:
            raise ServiceConfigError("Missing filedata.")

    def scan(self, obj, config):
        data = obj.filedata.read()
        zipdata = create_zip([("samples", data)])
        url = self.config.get('OPSWAT_url', '')

        req = urllib2.Request(url)
        req.add_header("Content-Type", "application/zip")
        req.add_data(bytearray(zipdata))
        out = urllib2.urlopen(req)
        text_out = out.read()

        # Parse XML output
        handler = XMLTagHandler()
        parser = xml.parsers.expat.ParserCreate()
        parser.StartElementHandler = handler.StartElement
        parser.EndElementHandler = handler.EndElement
        parser.CharacterDataHandler = handler.CharData
        parser.Parse(text_out)

        for threat in handler.threatList:
            self._add_result('av_result', threat["threat_name"], {"engine":threat["engine_name"], "date":datetime.now().isoformat()})

class XMLTagHandler(object):
    def __init__(self):
        self.ResetFlags()
        self.threatList = []

    def ResetFlags(self):
        self.isEngineNameElement = 0
        self.isScanResultElement = 0
        self.isThreatNameElement = 0

        self.engineName = ""
        self.scanResult = ""
        self.threatName = ""

    def StartElement(self, name, attr):
        if name == "engine_result":
            self.ResetFlags()
        elif name == "engine_name":
            self.isEngineNameElement = 1
        elif name == "scan_result":
            self.isScanResultElement = 1
        elif name == "threat_name":
            self.isThreatNameElement = 1


    def EndElement(self, name):
        if name == "engine_result":
            if self.scanResult >= 1:
                self.threatList.append({"engine_name": self.engineName, "threat_name": self.threatName})
            else:
                self.threatList.append({"engine_name": self.engineName, "threat_name": ""})
        elif name == "engine_name":
            self.isEngineNameElement = 0
        elif name == "scan_result":
            self.isScanResultElement = 0
        elif name == "threat_name":
            self.isThreatNameElement = 0

    def CharData(self, data):
        if self.isEngineNameElement:
            self.engineName = data
        elif self.isScanResultElement:
            self.scanResult = int(data)
        elif self.isThreatNameElement:
            self.threatName = data
