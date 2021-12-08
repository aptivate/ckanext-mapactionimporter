import unittest

from lxml.etree import fromstring, Element
from ckanext.mapactionimporter.lib import mappackage


class TestXmlParse(unittest.TestCase):
    template_xml = """Must be overridden in the subclass"""

    def parse_xml(self, **kwargs):
        defaults = {
            'mapnumber': 'default-map-no',
            'operationid': 'default-op-id',
            'ref': 'default-ref',
            'status': 'default-status',
            'summary': 'default-summary',
            'theme': 'default-theme',
            'title': 'default-title',
            'versionnumber': '987',
        }

        values = {}

        for tag, default in defaults.iteritems():
            values[tag] = kwargs.get(tag, default)

        xml = self.template_xml.format(**values)

        return fromstring(xml)


class TestMapMetadataToCkanExtras(TestXmlParse):
    template_xml = """<?xml version="1.0" encoding="utf-8"?>
<mapdoc>
  <mapdata>
    <operationID>{operationid}</operationID>
    <title>{title}</title>
    <status>{status}</status>
    <summary>{summary}</summary>
    <themes>
      <theme>{theme}</theme>
    </themes>
    <mapNumber>{mapnumber}</mapNumber>
    <versionNumber>{versionnumber}</versionNumber>
    <principal-country-iso3>NPL</principal-country-iso3>
    <countries-iso3>
      <country-iso3>NPL</country-iso3>
      <country-iso3>CHN</country-iso3>
      <country-iso3>IND</country-iso3>
    </countries-iso3>
  </mapdata>
</mapdoc>
    """

    def setUp(self):
        et = self.parse_xml()
        self.extras_dict = mappackage.map_metadata_to_ckan_extras(et)
        self.assertTrue(len(self.extras_dict) > 0)

    def test_status_excluded(self):
        self.assertNotIn('status', self.extras_dict)

    def test_title_excluded(self):
        self.assertNotIn('title', self.extras_dict)

    def test_operationID_excluded(self):
        self.assertNotIn('operationID', self.extras_dict)

    def test_versionNumber_excluded(self):
        self.assertNotIn('versionNumber', self.extras_dict)

    def test_themes_excluded(self):
        self.assertNotIn('themes', self.extras_dict)

    def test_countries_included(self):
        self.assertIn('country-iso3', self.extras_dict)

        countries = self.extras_dict['country-iso3']

        self.assertIn('NPL', countries)
        self.assertIn('CHN', countries)
        self.assertIn('IND', countries)

        self.assertEquals(len(countries), 3)


class TestPopulateDatasetDictFromXml(TestXmlParse):
    template_xml = """<?xml version="1.0" encoding="utf-8"?>
<mapdoc>
  <mapdata>
    <operationID>{operationid}</operationID>
    <title>{title}</title>
    <ref>{ref}</ref>
    <summary>{summary}</summary>
    <themes>
      <theme>{theme}</theme>
    </themes>
    <mapNumber>{mapnumber}</mapNumber>
    <versionNumber>{versionnumber}</versionNumber>
  </mapdata>
</mapdoc>
    """

    def test_empty_summary_copied_to_notes(self):
        et = self.parse_xml(summary='')
        dataset_dict = mappackage.populate_dataset_dict_from_xml(et)

        self.assertEqual(dataset_dict['notes'], '')

    def test_missing_summary_copied_to_notes(self):
        et = self.parse_xml()
        self._remove_from_etree(et, './/mapdata', 'summary')

        dataset_dict = mappackage.populate_dataset_dict_from_xml(et)

        self.assertEqual(dataset_dict['notes'], '')

    def test_summary_newlines_replaced_with_spaces(self):
        et = self.parse_xml(summary='one\ntwo\r\nthree\rfour\n\nfive\r\n\r\nsix\r\rseven')

        dataset_dict = mappackage.populate_dataset_dict_from_xml(et)

        self.assertEqual(dataset_dict['notes'], 'one two three four  five  six  seven')

    def test_missing_title_copied_to_title(self):
        et = self.parse_xml()
        self._remove_from_etree(et, './/mapdata', 'title')

        dataset_dict = mappackage.populate_dataset_dict_from_xml(et)

        self.assertEqual(dataset_dict['title'], '')

    def test_no_themes_when_missing(self):
        et = self.parse_xml()

        dataset_dict = mappackage.populate_dataset_dict_from_xml(et)

        self.assertTrue('product_themes' not in dataset_dict)

    def test_theme_stored_in_product_themes(self):
        et = self.parse_xml(theme='Orientation and Reference')

        dataset_dict = mappackage.populate_dataset_dict_from_xml(et)

        self.assertTrue('Orientation and Reference' in
                        dataset_dict['product_themes'])

    def test_multiple_themes_stored_in_product_themes(self):
        et = self.parse_xml(theme='Orientation and Reference')
        self._add_to_etree(et, './/mapdata/themes', 'theme',
                           'Affected Population')

        dataset_dict = mappackage.populate_dataset_dict_from_xml(et)

        self.assertTrue('Orientation and Reference' in
                        dataset_dict['product_themes'])
        self.assertTrue('Affected Population' in
                        dataset_dict['product_themes'])

    def test_it_raises_when_mandatory_field_missing(self):
        mandatory_fields = ('operationID',
                            'mapNumber',
                            'versionNumber')

        for f in mandatory_fields:
            et = self.parse_xml()

            self._remove_from_etree(et, './/mapdata', f)

            with self.assertRaises(mappackage.MapPackageException):
                mappackage.populate_dataset_dict_from_xml(et)

    def test_it_raises_when_version_number_non_numeric(self):
        et = self.parse_xml(versionnumber='v1')

        with self.assertRaises(mappackage.MapPackageException) as e:
            mappackage.populate_dataset_dict_from_xml(et)

        self.assertEquals(e.exception.args[0],
                          "Version number 'v1' must be an integer")

    def test_name_includes_operation_id_map_number_and_version(self):
        et = self.parse_xml(operationid='00123', mapnumber='MA001',
                            versionnumber='02')
        dataset_dict = mappackage.populate_dataset_dict_from_xml(et)

        self.assertEqual(dataset_dict['name'], '00123-ma001-v2')

    def test_version_number_stored_in_ckan_version(self):
        et = self.parse_xml(versionnumber='2')
        dataset_dict = mappackage.populate_dataset_dict_from_xml(et)

        self.assertEqual(dataset_dict['version'], 2)

    def _remove_from_etree(self, et, parent_xpath, child_xpath):
        for parent in et.findall(parent_xpath):
            for child in parent.findall(child_xpath):
                parent.remove(child)

    def _add_to_etree(self, et, parent_xpath, name, text):
        for parent in et.findall(parent_xpath):
            child = Element(name)
            child.text = text
            parent.append(child)
