from ckan.common import config
import ckan.tests.helpers as helpers
import ckan.tests.factories as factories
import ckan.plugins.toolkit as toolkit
import ckan.lib.uploader as uploader

from ckanext.mapactionimporter.tests.helpers import (
    FunctionalTestBaseClass,
    assert_equal,
    assert_false,
    assert_is_not_none,
    assert_raises,
    assert_true,
    get_correction_zip,
    get_country_group_zip,
    get_missing_fields_zip,
    get_not_zip,
    get_special_characters_zip,
    get_test_zip,
    get_update_zip,
    get_zip_empty_metadata,
    get_zip_no_metadata,
)


class TestCreateDatasetFromZip(FunctionalTestBaseClass):
    def setup(self):
        storage_path = config.get('ckan.storage_path')
        if not storage_path:
            assert_is_not_none(
                storage_path,
                msg="You must define ckan.storage.path in ckan/test-core.ini"
            )

        super(TestCreateDatasetFromZip, self).setup()
        self.user = factories.User()


class TestDatasetForEvent(TestCreateDatasetFromZip):
    def setup(self):
        super(TestDatasetForEvent, self).setup()
        self.group_189 = factories.Group(name='189', user=self.user, type='event')

        helpers.call_action(
            'group_member_create',
            id=self.group_189['id'],
            username=self.user['name'],
            role='editor')


class TestCreateDatasetForEvent(TestDatasetForEvent):
    def setup(self):
        super(TestCreateDatasetForEvent, self).setup()

    def test_it_allows_uploading_a_zipfile(self):
        dataset = helpers.call_action(
            'create_dataset_from_mapaction_zip',
            upload=_UploadFile(get_test_zip()))

        assert_equal(
            dataset['title'],
            'Central African Republic: Example Map- Reference (as of 3 Feb 2099)')

        assert_equal(
            dataset['name'],
            '189-ma001-v1')

        # Expect the JPEG And PDF referenced in the XML Metadata
        dataset = helpers.call_action('ckan_package_show', id=dataset['id'])
        resources = dataset['resources']
        extras = dataset['extras']

        assert_equal(len(resources), 2)
        assert_true(len(extras) > 0)

        sorted_resources = sorted(resources, key=lambda k: k['format'])

        self._check_uploaded_resource(sorted_resources[0],
                                      'JPEG',
                                      'MA001_Aptivate_Example-300dpi.jpeg',
                                      'ma001_aptivate_example-300dpi.jpeg')
        self._check_uploaded_resource(sorted_resources[1],
                                      'PDF',
                                      'MA001_Aptivate_Example-300dpi.pdf',
                                      'ma001_aptivate_example-300dpi.pdf')

    def test_dataset_private_when_organization_specified(self):
        organization = factories.Organization(user=self.user)
        dataset = helpers.call_action(
            'create_dataset_from_mapaction_zip',
            context={'user': self.user['id']},
            upload=_UploadFile(get_test_zip()),
            owner_org=organization['id'])
        assert_true(dataset['private'])

    def test_dataset_public_when_no_organization_specified(self):
        dataset = helpers.call_action(
            'create_dataset_from_mapaction_zip',
            upload=_UploadFile(get_test_zip()))
        assert_false(dataset['private'])

    def test_dataset_notes_set_to_xml_summary(self):
        dataset = helpers.call_action(
            'create_dataset_from_mapaction_zip',
            upload=_UploadFile(get_test_zip()))

        summary = ("Example reference map of the Central African Republic.  This "
                   "is an example map only and for testing use only")
        assert_equal(dataset['notes'], summary)

    def test_dataset_license_defaults_to_not_specified(self):
        dataset = helpers.call_action(
            'create_dataset_from_mapaction_zip',
            upload=_UploadFile(get_test_zip()))
        assert_equal(dataset['license_id'], 'notspecified')

    def _check_uploaded_resource(self, resource, expected_format,
                                 expected_name,
                                 expected_basename):
        assert_equal(resource['url_type'], 'upload')
        assert_equal(resource['format'], expected_format)
        assert_equal(resource['name'], expected_name)

        basename = resource['url'].split('/')[-1]
        assert_equal(basename, expected_basename)

    def test_it_raises_if_no_zip_file(self):
        with assert_raises(toolkit.ValidationError) as cm:
            helpers.call_action(
                'create_dataset_from_mapaction_zip',
                upload=u''
            )

        assert_equal(cm.exception.error_summary,
                     {'Upload':
                      'You must select a file to be imported'})

    def test_it_raises_if_not_a_zip_file(self):
        with assert_raises(toolkit.ValidationError) as cm:
            helpers.call_action(
                'create_dataset_from_mapaction_zip',
                upload=_UploadFile(get_not_zip()))

        assert_equal(cm.exception.error_summary,
                     {'Upload':
                      'File is not a zip file'})

    def test_it_raises_if_no_metadata(self):
        with assert_raises(toolkit.ValidationError) as cm:
            helpers.call_action(
                'create_dataset_from_mapaction_zip',
                upload=_UploadFile(get_zip_no_metadata()))

        assert_equal(cm.exception.error_summary,
                     {'Upload':
                      'Could not find metadata XML in zip file'})

    def test_it_raises_if_empty_metadata(self):
        with assert_raises(toolkit.ValidationError) as cm:
            helpers.call_action(
                'create_dataset_from_mapaction_zip',
                upload=_UploadFile(get_zip_empty_metadata()))

        assert_equal(cm.exception.error_summary,
                     {'Upload':
                      "Error parsing XML: 'no element found: line 1, column 0'"})

    def test_it_tidies_up_if_resource_creation_fails(self):
        old_max_resource_size = uploader._max_resource_size
        uploader._max_resource_size = 1

        with assert_raises(toolkit.ValidationError) as cm:
            helpers.call_action(
                'create_dataset_from_mapaction_zip',
                upload=_UploadFile(get_test_zip()))

        assert_equal(cm.exception.error_summary,
                     {'Upload':
                      'File upload too large'})

        datasets = helpers.call_action(
            'package_list',
            context={'user': self.user['name']})

        # The dataset will be in the trash so won't appear here
        assert_equal(len(datasets), 0)

        uploader._max_resource_size = old_max_resource_size

        dataset = helpers.call_action(
            'create_dataset_from_mapaction_zip',
            upload=_UploadFile(get_test_zip()))

        assert_equal(
            dataset['name'],
            '189-ma001-v1')

    def test_it_raises_if_file_has_special_characters(self):
        with assert_raises(toolkit.ValidationError) as cm:
            helpers.call_action(
                'create_dataset_from_mapaction_zip',
                upload=_UploadFile(get_special_characters_zip()))

        assert_equal(cm.exception.error_summary, {
            'Upload':
            "Error parsing XML: 'not well-formed (invalid token): line 22, column 47'",
        })

    def test_it_raises_if_mandatory_fields_missing(self):
        with assert_raises(toolkit.ValidationError) as cm:
            helpers.call_action(
                'create_dataset_from_mapaction_zip',
                upload=_UploadFile(get_missing_fields_zip()))

        assert_equal(cm.exception.error_summary, {
            'Upload':
            "Unable to find mandatory field 'operationID' in metadata",
        })

    def test_it_attaches_to_event_with_operation_id_from_metadata(self):
        dataset = helpers.call_action(
            'create_dataset_from_mapaction_zip',
            context={'user': self.user['name']},
            upload=_UploadFile(get_test_zip()),
        )

        dataset = helpers.call_action(
            'ckan_package_show',
            context={'user': self.user['name']},
            id=dataset['id'])
        events = dataset['groups']

        assert_equal(len(events), 1)
        assert_equal(events[0]['name'], '189')

    def test_new_version_associated_with_existing(self):
        organization = factories.Organization(user=self.user)
        version_1 = helpers.call_action(
            'create_dataset_from_mapaction_zip',
            context={'user': self.user['name']},
            upload=_UploadFile(get_test_zip()),
            owner_org=organization['id']
        )

        assert_equal(version_1['name'], '189-ma001-v1')

        version_2 = helpers.call_action(
            'create_dataset_from_mapaction_zip',
            upload=_UploadFile(get_update_zip()))

        assert_equal(version_2['name'], '189-ma001-v2')

        [rel_1] = helpers.call_action(
            'package_relationships_list',
            id=version_1['id'],
            rel='child_of')

        [rel_2] = helpers.call_action(
            'package_relationships_list',
            id=version_2['id'],
            rel='child_of')

        assert_equal(rel_1['subject'], '189-ma001-v1')
        assert_equal(rel_1['type'], 'child_of')
        assert_equal(rel_1['object'], '189-ma001')

        assert_equal(rel_2['subject'], '189-ma001-v2')
        assert_equal(rel_2['type'], 'child_of')
        assert_equal(rel_2['object'], '189-ma001')

        parent_dataset = helpers.call_action(
            'ckan_package_show',
            context={'user': self.user['name']},
            id='189-ma001')

        assert_equal(parent_dataset['owner_org'],
                     organization['id'])

    def test_error_when_status_is_correction(self):
        with assert_raises(toolkit.ValidationError) as cm:
            helpers.call_action(
                'create_dataset_from_mapaction_zip',
                context={'user': self.user['name']},
                upload=_UploadFile(
                    get_correction_zip())
            )

        assert_equal(
            cm.exception.error_summary,
            {
                'Upload':
                "Status is 'Correction' but dataset '189-ma001-v1' does not exist"
            })

    def test_error_when_status_is_update_and_dataset_exists(self):
        helpers.call_action(
            'create_dataset_from_mapaction_zip',
            context={'user': self.user['name']},
            upload=_UploadFile(get_update_zip()),
        )

        with assert_raises(toolkit.ValidationError) as cm:
            helpers.call_action(
                'create_dataset_from_mapaction_zip',
                context={'user': self.user['name']},
                upload=_UploadFile(get_update_zip())
            )

        assert_equal(
            cm.exception.error_summary,
            {
                'Upload':
                "Status is 'Update' but dataset '189-ma001-v2' already exists"
            })

    def test_it_raises_if_country_does_not_exist(self):
        with assert_raises(toolkit.ValidationError) as cm:
            helpers.call_action(
                'create_dataset_from_mapaction_zip',
                upload=_UploadFile(get_country_group_zip()))

        assert_equal(cm.exception.error_summary, {
            'Upload':
            "Event or country code 'bol' does not exist",
        })


class TestCorrectExistingDataset(TestDatasetForEvent):
    def setup(self):
        super(TestCorrectExistingDataset, self).setup()
        self.organization = factories.Organization(user=self.user)
        self.dataset = helpers.call_action(
            'create_dataset_from_mapaction_zip',
            context={'user': self.user['name']},
            upload=_UploadFile(get_test_zip()),
            owner_org=self.organization['id']
        )

    def test_updated_version_replaces_existing(self):
        assert_true(self.dataset['private'])

        another_user = factories.User()

        helpers.call_action(
            'member_create',
            id=self.organization['id'],
            object=another_user['id'],
            object_type='user',
            capacity='editor')

        original_resources = sorted(self.dataset['resources'],
                                    key=lambda k: k['format'])
        assert_equal(len(original_resources), 2)

        updated_dataset = helpers.call_action(
            'create_dataset_from_mapaction_zip',
            context={'user': another_user['name']},
            upload=_UploadFile(
                get_correction_zip()),
            owner_org=self.organization['id']
        )

        assert_equal(updated_dataset['name'], '189-ma001-v1')
        assert_equal(updated_dataset['notes'],
                     'Updated summary')
        assert_true(updated_dataset['private'])

        updated_resources = sorted(updated_dataset['resources'],
                                   key=lambda k: k['format'])
        assert_equal(len(updated_resources), 2)

        assert_true(
            original_resources[0]['id'] != updated_resources[0]['id'])
        assert_true(
            original_resources[1]['id'] != updated_resources[1]['id'])

    def test_nothing_changed_if_resource_update_fails(self):
        old_max_resource_size = uploader._max_resource_size
        uploader._max_resource_size = 1

        original_resources = sorted(self.dataset['resources'],
                                    key=lambda k: k['format'])
        assert_equal(len(original_resources), 2)

        with assert_raises(toolkit.ValidationError) as cm:
            helpers.call_action(
                'create_dataset_from_mapaction_zip',
                context={'user': self.user['name']},
                upload=_UploadFile(
                    get_correction_zip()),
                owner_org=self.organization['id']
            )

        uploader._max_resource_size = old_max_resource_size

        assert_equal(cm.exception.error_summary,
                     {'Upload':
                      'File upload too large'})
        dataset = helpers.call_action(
            'package_show',
            id='189-ma001-v1')

        assert_equal(
            dataset['notes'],
            ("Example reference map of the Central African Republic.  This "
             "is an example map only and for testing use only"))

        resources = sorted(dataset['resources'],
                           key=lambda k: k['format'])
        assert_equal(len(resources), 2)
        assert_equal(original_resources, resources)

    def test_updated_dataset_public_if_original_public(self):
        self.dataset['private'] = False

        helpers.call_action(
            'package_update',
            context={'user': self.user['name']},
            **self.dataset)

        updated_dataset = helpers.call_action(
            'create_dataset_from_mapaction_zip',
            context={'user': self.user['name']},
            upload=_UploadFile(
                get_correction_zip()),
            owner_org=self.organization['id']
        )

        assert_false(updated_dataset['private'])

    def test_error_when_status_not_correction(self):
        with assert_raises(toolkit.ValidationError) as cm:
            helpers.call_action(
                'create_dataset_from_mapaction_zip',
                context={'user': self.user['name']},
                upload=_UploadFile(
                    get_test_zip()),
                owner_org=self.organization['id']
            )

        assert_equal(
            cm.exception.error_summary,
            {
                'Upload':
                "Status is 'New' but dataset '189-ma001-v1' already exists"
            })


class TestCreateDatasetForNoEvent(TestCreateDatasetFromZip):
    def test_it_raises_if_event_does_not_exist(self):
        with assert_raises(toolkit.ValidationError) as cm:
            helpers.call_action(
                'create_dataset_from_mapaction_zip',
                upload=_UploadFile(get_test_zip()))

        assert_equal(cm.exception.error_summary, {
            'Upload':
            "Event or country code '189' does not exist",
        })


class TestCreateDatasetForCountry(TestCreateDatasetFromZip):
    def setup(self):
        super(TestCreateDatasetForCountry, self).setup()
        self.bol = factories.Group(name='bol', user=self.user, type='location')

        helpers.call_action(
            'group_member_create',
            id=self.bol['id'],
            username=self.user['name'],
            role='editor')

    def test_it_attaches_to_country_with_operation_id_from_metadata(self):
        dataset = helpers.call_action(
            'create_dataset_from_mapaction_zip',
            context={'user': self.user['name']},
            upload=_UploadFile(get_country_group_zip()),
        )

        dataset = helpers.call_action(
            'ckan_package_show',
            context={'user': self.user['name']},
            id=dataset['id'])
        countries = dataset['groups']

        assert_equal(len(countries), 1)
        assert_equal(countries[0]['name'], 'bol')

    def test_it_raises_if_country_does_not_exist(self):
        with assert_raises(toolkit.ValidationError) as cm:
            helpers.call_action(
                'create_dataset_from_mapaction_zip',
                upload=_UploadFile(get_test_zip()))

        assert_equal(cm.exception.error_summary, {
            'Upload':
            "Event or country code '189' does not exist",
        })


class _UploadFile(object):
    '''Mock the parts from cgi.FileStorage we use.'''
    def __init__(self, fp):
        self.file = fp
