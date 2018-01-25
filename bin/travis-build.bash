#!/bin/bash
set -e

echo "This is travis-build.bash..."

echo "Installing the packages that CKAN requires..."
sudo apt-get update -qq
sudo apt-get install postgresql-$PGVERSION solr-jetty

echo "Installing CKAN and its Python dependencies..."
git clone https://github.com/aptivate/ckan
cd ckan
export ckan_branch=mapaction-dev
echo "CKAN branch: $ckan_branch"
git checkout $ckan_branch
python setup.py develop
pip install -r requirements.txt --allow-all-external
pip install -r dev-requirements.txt --allow-all-external
cd -

echo "Creating the PostgreSQL user and database..."
sudo -u postgres psql -c "CREATE USER ckan_default WITH PASSWORD 'pass';"
sudo -u postgres psql -c 'CREATE DATABASE ckan_test WITH OWNER ckan_default;'

echo "Initialising the database..."
cd ckan
paster db init -c test-core.ini
cd -

echo "Configure storage_path"
sudo mkdir -p /var/lib/ckan_test
sudo chmod 777 /var/lib/ckan_test
cd ckan
paster config-tool -s app:main test-core.ini 'ckan.storage_path=/var/lib/ckan_test'
cd -

echo "Installing ckanext-mapactionimporter and its requirements..."
python setup.py develop
pip install -r requirements.txt
pip install -r dev-requirements.txt

echo "Moving test.ini into a subdir..."
mkdir subdir
mv test.ini subdir

echo "travis-build.bash is done."
