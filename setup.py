#!/usr/bin/env python
import os
import shutil
import sys
import re

from setuptools import setup

try:
    from pypandoc import convert

    def read_md(f):
        return convert(f, 'rst')
except ImportError:
    print("warning: pypandoc module not found, could not convert Markdown to RST")

    def read_md(f):
        return open(f, 'r', encoding='utf-8').read()


NAME = 'tg-option-container'
PACKAGE = 'tg_option_container'


def get_tag_from_package(package, tag):
    init_py = open(os.path.join(package, '__init__.py')).read()
    return re.search("__{0}__ = ['\"]([^'\"]+)['\"]".format(tag), init_py).group(1)


def get_packages(package):
    return [dirpath
            for dirpath, dirnames, filenames in os.walk(package)
            if os.path.exists(os.path.join(dirpath, '__init__.py'))]


def get_package_data(package):
    walk = [(dirpath.replace(package + os.sep, '', 1), filenames)
            for dirpath, dirnames, filenames in os.walk(package)
            if not os.path.exists(os.path.join(dirpath, '__init__.py'))]

    filepaths = []
    for base, filenames in walk:
        filepaths.extend([os.path.join(base, filename) for filename in filenames])
    return {package: filepaths}


if sys.argv[-1] == 'publish':
    try:
        import pypandoc
    except ImportError:
        print("pypandoc not installed.\nUse `pip install pypandoc`.\nExiting.")

    if os.system("pip freeze | grep wheel"):
        print("wheel not installed.\nUse `pip install wheel`.\nExiting.")
        sys.exit()

    if os.system("pip freeze | grep twine"):
        print("twine not installed.\nUse `pip install twine`.\nExiting.")
        sys.exit()

    os.system("python setup.py sdist bdist_wheel")
    os.system("twine upload dist/*")

    print("You probably want to also tag the version now:")
    print("  git tag -a {0} -m 'version {0}'".format(get_tag_from_package(PACKAGE, 'version')))
    print("  git push --tags")

    shutil.rmtree('dist')
    shutil.rmtree('build')
    shutil.rmtree('tg_option_container.egg-info')
    sys.exit()


setup(
    name=NAME,
    version=get_tag_from_package(PACKAGE, 'version'),
    url=get_tag_from_package(PACKAGE, 'url'),
    license=get_tag_from_package(PACKAGE, 'license'),
    description=get_tag_from_package(PACKAGE, 'description'),
    long_description=read_md('README.md'),
    author=get_tag_from_package(PACKAGE, 'author'),
    author_email=get_tag_from_package(PACKAGE, 'email'),
    packages=get_packages(PACKAGE),
    package_data=get_package_data(PACKAGE),
    install_requires=[
        'six',
        'python-dateutil'
    ],
    zip_safe=False,
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 3',
    ]
)
