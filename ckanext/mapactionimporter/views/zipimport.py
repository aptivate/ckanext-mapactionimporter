from logging import getLogger
from flask import Blueprint

import ckan.model as model
import ckan.logic as logic
import ckan.plugins.toolkit as toolkit

log = getLogger(__name__)
zipimport = Blueprint('zipimport', __name__)

def new(data=None, errors=None, error_summary=None):
    context = {
        'model': model,
        'session': model.Session,
        'user': toolkit.c.user,
        'auth_user_obj': toolkit.c.userobj,
    }

    _authorize_or_abort(context)

    errors = errors or {}
    error_summary = error_summary or {}

    data = data or {}
    extra_vars={
            'data': data,
            'errors': errors,
            'error_summary': error_summary,
            'pkg_dict': toolkit.c
        }
    
    return toolkit.render(
        'mapactionimporter/import_zip.html',
        extra_vars=extra_vars
    )

def import_dataset():

    context = {
        'model': model,
        'session': model.Session,
        'user': toolkit.c.user,
    }
    _authorize_or_abort(context)

    try:
        params = toolkit.request.files
        dataset = toolkit.get_action(
            'create_dataset_from_mapaction_zip')(
                context,
                params
            )
        return toolkit.redirect_to(controller='dataset',
                                   action='edit',
                                   id=dataset['name'])
    except toolkit.ValidationError as e:
        errors = e.error_dict
        error_summary = e.error_summary
        return new(data=params,
                        errors=errors,
                        error_summary=error_summary)

def _authorize_or_abort(context):
    try:
        toolkit.check_access('package_create', context)
    except toolkit.NotAuthorized:
        toolkit.abort(401,
            toolkit._('Unauthorized to create a dataset'))

zipimport.add_url_rule('/dataset/import_mapactionzip', view_func=new, methods=["GET"])

zipimport.add_url_rule('/dataset/import_mapactionzip', view_func=import_dataset, methods=["POST"])
