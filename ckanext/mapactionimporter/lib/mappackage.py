import os

import logging
import shutil
import tempfile
import zipfile

from ckan.common import _

from defusedxml.ElementTree import parse, ParseError
from slugify import slugify

log = logging.getLogger(__name__)

# Valid CKAN tags must only contain alphanumeric characters or symbols: -_.
PRODUCT_THEMES = (
    "Affected Population",
    "Agriculture",
    "Appeals",
    "Camp Coordination or Management",
    "Early Recovery",
    "Education",
    "Emergency Shelter",
    "Emergency Telecommunications",
    "Environmental Aspects",
    "Health",
    "Logistics",
    "Nutrition",
    "P-codes",
    "Population Baseline",
    "Orientation and Reference",
    "Search and Rescue or Evacuation Planning",
    "Search and Rescue Sectors",
    "Security and Safety and Protection",
    "Situation and Damage",
    "Water Sanitation and Hygiene",
    "Who-What-Where",
)


EXCLUDE_TAGS = (
    'operationID',
    'status',
    'theme',
    'themes',
    'title',
    'versionNumber',
)


class MapPackageException(Exception):
    pass


def map_metadata_to_ckan_extras(et):
    map_metadata = {}
    for e in et.findall('./mapdata/*'):
        tag_name = e.tag

        if tag_name in EXCLUDE_TAGS:
            continue

        tag_value = e.text

        if tag_name == 'countries-iso3':
            tag_name = 'country-iso3'
            tag_value = get_countries_iso3(e)

        map_metadata[tag_name] = tag_value
    return map_metadata


def get_countries_iso3(countries_iso3_element):
    countries = []

    for country in countries_iso3_element.findall('country-iso3'):
        countries.append(country.text)

    return countries


def join_lines(text):
    """ Return input text without newlines """
    if text is None:
        return ''

    return ' '.join(text.splitlines())


def extract_zip(map_package):
    # Extract the map package
    tempdir = tempfile.mkdtemp('-mapactionzip')

    metadata_paths = []
    file_paths = []
    try:
        with zipfile.ZipFile(map_package, 'r') as z:
            for i in z.infolist():
                filename = i.filename.encode('cp437')
                full_path = os.path.join(tempdir, filename)

                with open(full_path, 'wb') as outputfile:
                    shutil.copyfileobj(z.open(i.filename), outputfile)

                if filename.endswith('.xml'):
                    metadata_paths.append(full_path)
                else:
                    file_paths.append(full_path)
    except zipfile.BadZipfile:
        raise MapPackageException(_('File is not a zip file'))

    # Expect a single metadata file
    if len(metadata_paths) == 0:
        raise MapPackageException(_('Could not find metadata XML in zip file'))
    metadata_file = metadata_paths[0]

    try:
        et = parse(metadata_file)
    except ParseError as e:
        raise MapPackageException(_("Error parsing XML: '{0}'".format(
            e.msg.args[0])))

    return (et, file_paths)


def to_dataset(context, map_package):
    et, file_paths = extract_zip(map_package)
    dataset_dict = populate_dataset_dict_from_xml(et)
    # Not currently in the metadata
    dataset_dict['license_id'] = 'notspecified'
    dataset_info = {
        'status': get_mandatory_text_node(et, 'status'),
        'dataset_dict': dataset_dict,
        'file_paths': file_paths,
        'name': dataset_dict['name'],
        'operation_id': get_mandatory_text_node(et, 'operationID'),
    }

    return dataset_info


def populate_dataset_dict_from_xml(et):
    # Extract key metadata
    dataset_dict = {}
    dataset_dict['title'] = join_lines(get_text_node(et, 'title'))
    product_type = get_text_node(et, 'productType')
    operation_id = get_mandatory_text_node(et, 'operationID')
    map_number = get_mandatory_text_node(et, 'mapNumber')
    version_text = get_mandatory_text_node(et, 'versionNumber')

    try:
        version_number = int(version_text)
    except ValueError:
        raise MapPackageException(_("Version number '{version_number}' must be an integer".format(
            version_number=version_text)))

    dataset_dict['name'] = slugify('%s %s v%s' % (operation_id,
                                                  map_number,
                                                  version_number))
    dataset_dict['version'] = version_number
    dataset_dict['type'] = product_type

    for theme in et.findall('.//mapdata//theme'):
        if theme.text in PRODUCT_THEMES:
            dataset_dict.setdefault('product_themes', []).append(theme.text)
        else:
            log.error(
                "Product theme '{0}' not defined in PRODUCT_THEMES".format(
                    theme.text))

    summary = get_text_node(et, 'summary')
    dataset_dict['notes'] = join_lines(summary)

    dataset_dict['extras'] = [
        {'key': k, 'value': v} for (k, v)
        in map_metadata_to_ckan_extras(et).items()
    ]

    return dataset_dict


def get_mandatory_text_node(et, name):
    text = get_text_node(et, name)

    if text is None:
        raise MapPackageException(_("Unable to find mandatory field '{name}' in metadata".format(name=name)))

    return text


def get_text_node(et, name):
    element = et.find('.//mapdata/{0}'.format(name))
    if element is not None:
        return element.text

    return None
