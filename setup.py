import codecs
from setuptools import setup, find_packages

entry_points = {
}

TESTS_REQUIRE = [
	'fudge',
	'nose2[coverage_plugin]',
	'nti.testing',
	'pyhamcrest',
	'z3c.baseregistry',
	'zope.testrunner',
]

def _read(fname):
	with codecs.open(fname, encoding='utf-8') as f:
		return f.read()

setup(
	name='nti.containers',
	version=_read('version.txt').strip(),
	author='Jason Madden',
	author_email='jason@nextthought.com',
	description="NTI containers",
	long_description=_read('README.rst'),
	license='Apache',
	keywords='containers',
	classifiers=[
		'Intended Audience :: Developers',
		'Natural Language :: English',
		'Operating System :: OS Independent',
		'Programming Language :: Python :: 2',
		'Programming Language :: Python :: 2.7',
		'Programming Language :: Python :: 3',
		'Programming Language :: Python :: 3.4',
		'Programming Language :: Python :: 3.5',
		'Programming Language :: Python :: Implementation :: CPython',
		'Programming Language :: Python :: Implementation :: PyPy',
	],
	zip_safe=True,
	packages=find_packages('src'),
	package_dir={'': 'src'},
	include_package_data=True,
	namespace_packages=['nti'],
	tests_require=TESTS_REQUIRE,
	install_requires=[
		'setuptools',
		'nti.dublincore',
		'nti.ntiids',
		'nti.zodb',
		'repoze.lru',
		'slugify',
		'ZODB',
		'zope.annotation',
		'zope.component',
		'zope.container',
		'zope.dublincore',
		'zope.interface',
		'zope.location',
		'zope.lifecycleevent',
		'zope.site'
	],
	extras_require={
		'test': TESTS_REQUIRE,
	},
	entry_points=entry_points,
)
