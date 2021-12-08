# -*- coding: utf-8 -*-

import nose.tools

import ckan.model

import ckan.tests.factories as factories
import ckan.tests.helpers as helpers
import ckan.plugins.toolkit as toolkit

import ckanext.mapactionimporter.tests.factories as custom_factories
import ckanext.mapactionimporter.tests.helpers as custom_helpers

assert_equals = nose.tools.assert_equals
assert_true = nose.tools.assert_true
assert_regexp_matches = nose.tools.assert_regexp_matches


class TestThemeVocab(custom_helpers.FunctionalTestBaseClass):

    def test_set_multiple_themes_on_dataset(self):

        app = self._get_test_app()
        user = factories.User()
        organization = factories.Organization(user=user)
        group_189 = factories.Group(name='00189', user=user)
        helpers.call_action(
            'group_member_create',
            id=group_189['id'],
            username=user['name'],
            role='editor')

        env = {'REMOTE_USER': user['name'].encode('ascii')}
        dataset = custom_factories.Dataset(package_type='test_schema')

        response = app.get(
            url=toolkit.url_for(
                controller='package',
                action='edit',
                id=dataset.get('id'),
            ),
            extra_environ=env,
        )

        # organization dropdown available in create page.
        form = response.forms['dataset-edit']
        form['name'] = u'my-dataset'
        form['owner_org'] = organization['id']
        form['product_themes'] = [
            'Affected Population',
            'Agriculture',
        ]
        response = helpers.submit_and_follow(app, form, env, 'save')

        context = {'user': user['name']}
        dataset_dict = toolkit.get_action('package_show')(context, {'id': dataset['id']})
        assert_equals(dataset_dict['product_themes'], ['Agriculture', 'Affected Population'])
