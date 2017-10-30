import codecs
from setuptools import setup, find_packages

entry_points = {
}

TESTS_REQUIRE = [
    'ExtensionClass',
    'fudge',
    'nti.testing',
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
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
    ],
    url="https://github.com/NextThought/nti.containers",
    zip_safe=True,
    packages=find_packages('src'),
    package_dir={'': 'src'},
    include_package_data=True,
    namespace_packages=['nti'],
    tests_require=TESTS_REQUIRE,
    install_requires=[
        'setuptools',
        'Acquisition',
        'awesome-slugify',
        'BTrees',
        'nti.base',
        'nti.dublincore',
        'nti.externalization',
        'nti.ntiids',
        'nti.zodb',
        'persistent',
        'repoze.lru',
        'zc.queue',
        'ZODB',
        'zope.annotation',
        'zope.cachedescriptors',
        'zope.component',
        'zope.container',
        'zope.deferredimport',
        'zope.dublincore',
        'zope.interface',
        'zope.intid',
        'zope.location',
        'zope.lifecycleevent',
        'zope.site',
    ],
    extras_require={
        'test': TESTS_REQUIRE,
        'docs': [
            'Sphinx',
            'repoze.sphinx.autointerface',
            'sphinx_rtd_theme',
        ],
    },
    entry_points=entry_points,
)
