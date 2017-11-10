import ckan.tests.factories as factories


class Dataset(factories.Dataset):
    type = 'mapsheet'
