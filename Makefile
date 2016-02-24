OS := $(shell uname)
PKGNAME = django-etl-sync
PYTHON ?= python
mkfile_path := $(abspath $(lastword $(MAKEFILE_LIST)))
current_dir := $(patsubst %/,%,$(dir $(mkfile_path)))
parent_dir := $(patsubst %/,%,$(dir $(current_dir)))
pysqlite ?= pysqlite-2.8.1

env: $(parent_dir)/env/bin/activate

$(parent_dir)/env/bin/activate: requirements.txt
	test -d env || virtualenv $(parent_dir)/env
	CFLAGS=-I/usr/include/gdal $(parent_dir)/env/bin/pip install -Ur requirements.txt
	touch $(parent_dir)/env/bin/acivate

spatialite: $(parent_dir)/env/bin/activate
	curl -o "$(parent_dir)/env/$(pysqlite).tar.gz" "https://pypi.python.org/packages/source/p/pysqlite/$(pysqlite).tar.gz"
	cd $(parent_dir)/env && tar xzf $(parent_dir)/env/$(pysqlite).tar.gz
	cd $(parent_dir)/env/$(pysqlite) && sed -i -e "/SQLITE_OMIT_LOAD_EXTENSION/d" setup.cfg
ifeq ($(OS), Darwin)
	# Run MacOS commands, assume sqlite was installed with brew install sqlite --universal
	# and libspatialite is installed as well
	echo "include_dirs=/usr/local/opt/sqlite/include\nlibrary_dirs=/usr/local/opt/sqlite/lib" >> $(parent_dir)/env/$(pysqlite)/setup.cfg
else
	echo "include_dirs=/usr/include"
endif
	cd $(parent_dir)/env/$(pysqlite) && $(parent_dir)/env/bin/python setup.py install

