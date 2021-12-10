#!/bin/bash
set -e

echo "This is setup-ckan.bash..."

echo "Installing the packages that CKAN requires..."
sudo apt-get update -qq
sudo apt-get install xmlsec1 libxmlsec1-dev

echo "Installing CKAN and its Python dependencies..."
git clone https://github.com/ckan/ckan
cd ckan
git checkout 2.7
pip install setuptools==20.4
pip install psycopg2==2.7.3.2
pip install celery==3.1.23
python setup.py develop
pip install -r requirements.txt
pip install -r dev-requirements.txt
cd -

echo "Creating the PostgreSQL user and database..."
psql -h localhost -U postgres -c "CREATE USER ckan_default WITH PASSWORD 'pass';"
psql -h localhost -U postgres -c 'CREATE DATABASE ckan_test_27 WITH OWNER ckan_default;'

echo "Initialising the database..."
cd ckan
paster db init -c test-core.ini
cd -

echo "Installing ckanext-mapactionimporter dependencies..."
echo "Installing ckanext-scheming"
pip install -e git+https://github.com/ckan/ckanext-scheming.git@release-1.2.0#egg=ckanext-scheming
pip install -r https://raw.githubusercontent.com/ckan/ckanext-scheming/release-1.2.0/requirements.txt

echo "Configure storage_path"
sudo mkdir -p /var/lib/ckan_test
sudo chmod 777 /var/lib/ckan_test
cd ckan
paster config-tool -s app:main test-core.ini 'ckan.storage_path=/var/lib/ckan_test'
cd -

echo "Installing ckanext-mapactionimporter and its requirements..."
pip install -r requirements.txt
python setup.py develop
pip install -r dev-requirements.txt

echo "Moving test.ini into a subdir..."
mkdir subdir
mv test.ini subdir

echo "setup-ckan.bash is done."