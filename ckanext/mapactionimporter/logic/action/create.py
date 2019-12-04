import os
import cgi
import uuid

from ckan.common import _
import ckan.logic as logic
import ckan.plugins.toolkit as toolkit

from ckanext.mapactionimporter.lib import mappackage


def create_dataset_from_zip(context, data_dict):
    upload = data_dict.get('upload')
    if not _upload_attribute_is_valid(upload):
        msg = {'upload': [_('You must select a file to be imported')]}
        raise toolkit.ValidationError(msg)

    try:
        dataset_info = mappackage.to_dataset(upload.file)
    except (mappackage.MapPackageException) as e:
        msg = {'upload': [e.args[0]]}
        raise toolkit.ValidationError(msg)

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
