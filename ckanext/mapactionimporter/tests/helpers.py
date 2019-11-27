import nose.tools
import os

import ckan.tests.helpers as helpers
import ckan.plugins as plugins

from ckanext.mapactionimporter.plugin import create_product_themes

assert_equal = nose.tools.assert_equal
assert_false = nose.tools.assert_false
assert_raises = nose.tools.assert_raises
assert_regexp_matches = nose.tools.assert_regexp_matches
assert_true = nose.tools.assert_true


def get_test_xml():
    return get_test_file('MA001_Aptivate_Example.xml')


def get_test_zip():
    return get_test_file('MA001_Aptivate_Example.zip')


def get_update_zip():
    return get_test_file('MA001_Aptivate_Example_Update.zip')


def get_correction_zip():
    return get_test_file('MA001_Aptivate_Example_Correction.zip')


def get_not_zip():
    return get_test_file('MA001_Aptivate_Example.txt')


def get_zip_no_metadata():
    return get_test_file('MA001_Missing_Metadata.zip')


def get_zip_empty_metadata():
    return get_test_file('MA001_Empty_Metadata.zip')


def get_special_characters_zip():
    return get_test_file('MA001_Special_Characters.zip')


def get_missing_fields_zip():
    return get_test_file('MA001_Missing_Fields.zip')


def get_test_file(filename):
    return file(os.path.join(os.path.split(__file__)[0],
        './test-data/', filename))


class FunctionalTestBaseClass(helpers.FunctionalTestBase):
    @classmethod
    def setup_class(cls):
        super(FunctionalTestBaseClass, cls).setup_class()
        plugins.load('datasetversions')
        plugins.load('mapactionimporter')

    def setup(self):
        super(FunctionalTestBaseClass, self).setup()
        create_product_themes()

    @classmethod
    def teardown_class(cls):
        plugins.unload('datasetversions')
        plugins.unload('mapactionimporter')
        super(FunctionalTestBaseClass, cls).teardown_class()
