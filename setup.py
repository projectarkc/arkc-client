import codecs
import sys
from setuptools import setup


with codecs.open('README.rst', encoding='utf-8') as f:
    long_description = f.read()

if str(sys.version_info.major) == '2':
    print("WARNING! ArkC Client is recommended to be installed with Python3.")
    quit()
else:
    pkg_name = 'arkcclient'
    pkg = ['arkcclient', 'arkcclient.pyotp']
    pkg_data = {
        'arkcserver': ['README.md', 'LICENSE'],
	'arkcclient.pyotp': ['LICENSE']
    }
    required = ['pycrypto','dnslib', 'requests', 'miniupnpc']
    entry = """
    [console_scripts]
    arkcclient = arkcclient.main:main
    """
    categories = [
        'License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: Implementation :: CPython',
        'Topic :: Internet :: Proxy Servers',
    ]

setup(
    name=pkg_name,
    version="0.2.1",
    license='https://www.gnu.org/licenses/old-licenses/gpl-2.0.txt',
    description="A lightweight proxy designed to be proof to IP blocking measures",
    author='Noah, Teba',
    author_email='noah@arkc.org',
    url='https://arkc.org',
    packages=pkg,
    package_data=pkg_data,
    install_requires=required,
    entry_points=entry,
    classifiers=categories,
    long_description=long_description,
)

