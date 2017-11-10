import ckan.tests.factories as factories
import ckan.tests.helpers as helpers
import ckan.plugins.toolkit as toolkit
from ckanext.mapactionimporter.tests.helpers import (
    FunctionalTestBaseClass,
    get_test_zip,
    get_test_schema_zip,
    assert_equal,
    assert_true,
    assert_regexp_matches)


class TestDataPackageController(FunctionalTestBaseClass):
    def setup_member(self):
        user = factories.User()
        organization = factories.Organization(user=user)
        group_189 = factories.Group(name='00189', user=user)
        helpers.call_action(
            'group_member_create',
            id=group_189['id'],
            username=user['name'],
            role='editor')

        env = {'REMOTE_USER': user['name'].encode('ascii')}
        return (env, organization)

    def get_import_zip_response(self, env, params, upload_files):
        url = toolkit.url_for('import_mapactionzip')
        response = self._get_test_app().post(
            url,
            params,
            extra_environ=env,
            upload_files=upload_files
        )

        return response

    def test_import_zipfile(self):
        env, organization = self.setup_member()
        params = {
            'owner_org': organization['id'],
        }
        upload_files = [('upload', get_test_schema_zip().name)]
        response = self.get_import_zip_response(env, params, upload_files)

        # Should redirect to dataset's page
        assert_equal(response.status_int, 302)

        slug = '189-ma099-v1'
        assert_regexp_matches(
            response.headers['Location'],
            '/dataset/edit/%s' % slug)

        # Should create the dataset
        dataset = helpers.call_action('package_show', id=slug)
        assert_equal(dataset['title'],
                     'Central African Republic: Example Map- Reference (as of 3 Feb 2099)')
        assert_equal(dataset['product_themes'], ["Orientation and Reference"])
        assert_equal(dataset['private'], True)


    def test_import_with_schema(self):
        """ Test import with a MapAction export product-type field
            validated against the schema defined by CKAN package_type
        """
        env, organization = self.setup_member()
        params = {
            'owner_org': organization['id'],
        }
        upload_files = [('upload', get_test_schema_zip().name)]
        response = self.get_import_zip_response(env, params, upload_files)
        assert_equal(response.status_int, 302)

        slug = '189-ma099-v1'
        assert_regexp_matches(
            response.headers['Location'],
            '/dataset/edit/%s' % slug)

        # Should create the dataset
        dataset = helpers.call_action('package_show', id=slug)
        assert_equal(dataset['type'], 'mapsheet')
        assert_equal(dataset['title'],
                     'Central African Republic: Example Map- Reference (as of 3 Feb 2099)')
        assert_equal(dataset['product_themes'], ["Orientation and Reference"])
        assert_equal(dataset['private'], True)


    @helpers.change_config('ckan.auth.create_unowned_dataset', False)
    def test_cannot_display_form_without_access(self):
        user = factories.User()
        env = {'REMOTE_USER': user['name'].encode('ascii')}
        url = toolkit.url_for('import_mapactionzip')
        response = self._get_test_app().get(url, extra_environ=env, status=[401])
        assert_true('Unauthorized to create a dataset' in response.body)

    @helpers.change_config('ckan.auth.create_unowned_dataset', False)
    def test_cannot_create_dataset_without_access(self):
        user = factories.User()
        env = {'REMOTE_USER': user['name'].encode('ascii')}
        url = toolkit.url_for('import_mapactionzip')
        response = self._get_test_app().post(url, extra_environ=env, status=[401])
        assert_true('Unauthorized to create a dataset' in response.body)
