import os
import cgi
import uuid

from ckan.common import _
import ckan.logic as logic
import ckan.plugins.toolkit as toolkit

import ckan.lib.plugins as lib_plugins
import ckanext.scheming.helpers as scheming_helpers

from ckanext.mapactionimporter.lib import mappackage


## MapAction Zipfile importer
#
# Goal is to transform the MapAction Zip file into a CKAN Record.
#
# Achieve this in a multiple step process:
#
# 1. Zip file extraction and validation.
#
#   Implementated by:
#   - map_package.extract_zip()
#
#   Validates:
#   - The zipfile contain a well formed metadata XML.
#
# 2. Transform metadata XML into Python datastrutures / values.
#
#   Implementated by:
#   - map_package.to_dataset()
#   - Calls:
#   -- map_package.extract_zip()
#   -- map_package.populate_dataset_dict_from_xml()
#
# 3. Transform Python representation into CKAN compatable dataset.
#
#   - requires knowledge of CKAN schemas
#   - transform python repr of MA metadata into dataset, using schema def.
#   - validate schema
#
# CKAN Actions:
#
#  - ckanext.mapactionimporter.logic.action.create.create_dataset_from_zip
#  -- calls map_package.to_dataset(upload : FileUpload) -> dataset_info dict
#
#  - justification for this design is keeping the CKAN stuff out of the zipfile
#  handling.
#
###

def transform_for_schema(context, dataset_info):
    """
        Transforms dataset_info structure for the given schema:
            extras in schema should become first class values
    """
    data_dict = dataset_info['dataset_dict']
    schema = None

    # Schema lookup from ckan.logic.action.create:package_create()
    if 'type' not in data_dict:
        package_plugin = lib_plugins.lookup_package_plugin()
        try:
            # use first type as default if user didn't provide type
            package_type = package_plugin.package_types()[0]
        except (AttributeError, IndexError):
            package_type = 'dataset'
            # in case a 'dataset' plugin was registered w/o fallback
            package_plugin = lib_plugins.lookup_package_plugin(package_type)
        data_dict['type'] = package_type
    else:
        package_plugin = lib_plugins.lookup_package_plugin(data_dict['type'])

    if 'schema' in context:
        schema = context['schema']
    else:
        schema = package_plugin.create_package_schema()

    # The scheming extension doesn't implement the internal CKAN's
    # create_package_schema methods, it only builds the scheming schema at
    # validation time.
    #
    # create_package_schema doesn't get us a full scheming schema, so we get the
    # schema manually and promote fields from exists if they are defined:
    scheming_schema = scheming_helpers.scheming_get_dataset_schema(data_dict['type'])
    if scheming_schema:
        schema_dataset_fields = set(f['field_name'] for f in scheming_schema['dataset_fields'])

        new_extras = []
        # promote extras defined in the schema to dataset fields
        for i, extra in enumerate(data_dict['extras']):
            key, value = (extra['key'], extra['value'])

            if key in schema_dataset_fields:
                if key not in data_dict:
                    data_dict[key] = value
                else:
                    raise Exception("key %s already exists, %s -> %s" % (
                        key, data_dict[key], value))
            else:
                new_extras.append({"key": key, "value": value})

        data_dict['extras'] = new_extras

    data, errors = lib_plugins.plugin_validate(
            package_plugin, context, data_dict, schema, 'package_create')

    # Replace data_dict with new version
    dataset_info.update(dataset_dict=data_dict)

    return dataset_info



def create_dataset_from_zip(context, data_dict):
    upload = data_dict.get('upload')
    if not _upload_attribute_is_valid(upload):
        msg = {'upload': [_('You must select a file to be imported')]}
        raise toolkit.ValidationError(msg)

    # Build and validate dataset from upload
    try:
        dataset_info = mappackage.to_dataset(context, upload.file)
        # transform dataset_info for schema.
        dataset_info = transform_for_schema(context, dataset_info)
    except (mappackage.MapPackageException) as e:
        msg = {'upload': [e.args[0]]}
        raise toolkit.ValidationError(msg)

    # Update or Create dataset
    try:
        old_dataset = toolkit.get_action('package_show')(
            _get_context(context), {'id': dataset_info['name']})

        if dataset_info['status'] in ('New', 'Update'):
            msg = {'upload': [_("Status is '{status}' but dataset '{name}' already exists").format(
                status=dataset_info['status'], name=dataset_info['name'])]}
            raise toolkit.ValidationError(msg)

        return _update_dataset(context, old_dataset, dataset_info)
    except logic.NotFound:
        if dataset_info['status'] == 'Correction':
            msg = {'upload': [_("Status is '{status}' but dataset '{name}' does not exist").format(
                status=dataset_info['status'], name=dataset_info['name'])]}
            raise toolkit.ValidationError(msg)

        return _create_dataset(context, data_dict, dataset_info)


def _update_dataset(context, dataset_dict, dataset_info):
    old_resource_ids = [r['id'] for r in dataset_dict.pop('resources')]

    try:
        _create_resources(context, dataset_dict, dataset_info['file_paths'])
    except Exception as e:
        # Resource creation failed, rollback
        dataset_dict = toolkit.get_action('package_show')(
            _get_context(context), {'id': dataset_dict['id']})
        for resource in dataset_dict['resources']:
            if resource['id'] not in old_resource_ids:
                toolkit.get_action('resource_delete')(
                    _get_context(context), {'id': resource['id']})
        raise e

    for resource_id in old_resource_ids:
        toolkit.get_action('resource_delete')(
            _get_context(context), {'id': resource_id})

    dataset_dict = toolkit.get_action('package_show')(
        _get_context(context), {'id': dataset_dict['id']})

    dataset_dict.update(dataset_info['dataset_dict'])

    return toolkit.get_action('package_update')(
        _get_context(context), dataset_dict)


def _create_dataset(context, data_dict, dataset_info):
    private = data_dict.get('private', True)

    owner_org = data_dict.get('owner_org')

    update_dict = dataset_info['dataset_dict']

    if owner_org:
        update_dict['owner_org'] = owner_org
    else:
        private = False

    update_dict['private'] = private

    operation_id = dataset_info['operation_id']

    try:
        toolkit.get_action('group_show')(
            _get_context(context),
            data_dict={'id': operation_id})
    except (logic.NotFound) as e:
        msg = {'upload': [
            _("Event or country code '{}' does not exist").format(
                operation_id)]}
        raise toolkit.ValidationError(msg)

    # TODO:
    # If we do this, we get an error "User foo not authorized to edit these groups
    # update_dict['groups'] = [{'name': operation_id]

    final_name = update_dict['name']
    update_dict['name'] = '{0}-{1}'.format(final_name, uuid.uuid4())
    dataset = toolkit.get_action('package_create')(
        _get_context(context), update_dict)

    try:
        _create_resources(context, dataset, dataset_info['file_paths'])
    except:
        toolkit.get_action('package_delete')(_get_context(context),
                                             {'id': dataset['id']})
        raise

    toolkit.get_action('member_create')(_get_context(context), {
        'id': operation_id,
        'object': dataset['id'],
        'object_type': 'package',
        'capacity': 'member',  # TODO: What does capacity mean in this context?
    })

    update_dict = toolkit.get_action('package_show')(
        context, {'id': dataset['id']})
    update_dict['name'] = final_name

    try:
        dataset = toolkit.get_action('package_update')(
            _get_context(context), update_dict)
    except toolkit.ValidationError as e:
        if _('That URL is already in use.') in e.error_dict.get('name', []):
            e.error_dict['name'] = [_('"%s" already exists.' % final_name)]
        raise e

    # TODO: Is there a neater way so we don't have to reverse engineer the
    # base name?
    base_name = '-'.join(final_name.split('-')[0:-1])

    toolkit.get_action('dataset_version_create')(
        _get_context(context), {
            'id': dataset['id'],
            'base_name': base_name,
            'owner_org': owner_org
        }
    )

    return dataset


def _create_resources(context, dataset, file_paths):
    for resource_file in file_paths:
        resource = {
            'package_id': dataset['id'],
            'path': resource_file,
        }
        _create_and_upload_local_resource(
            _get_context(context), resource)


def _get_context(context):
    return {
        'model': context['model'],
        'session': context['session'],
        'user': context['user'],
        'ignore_auth': context.get('ignore_auth', False)
    }


def _upload_attribute_is_valid(upload):
    return hasattr(upload, 'file') and hasattr(upload.file, 'read')


def _create_and_upload_local_resource(context, resource):
    path = resource['path']
    del resource['path']
    with open(path, 'r') as the_file:
        _create_and_upload_resource(context, resource, the_file)


def _create_and_upload_resource(context, resource, the_file):
    resource['url'] = 'url'
    resource['url_type'] = 'upload'
    resource['upload'] = _UploadLocalFileStorage(the_file)
    resource['name'] = os.path.basename(the_file.name)
    toolkit.get_action('resource_create')(context, resource)


class _UploadLocalFileStorage(cgi.FieldStorage):
    def __init__(self, fp, *args, **kwargs):
        self.name = fp.name
        self.filename = fp.name
        self.file = fp
