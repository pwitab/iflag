from setuptools import setup

with open('README.md') as readme_file:
    readme = readme_file.read()

with open('HISTORY.md') as history_file:
    history = history_file.read()

setup(
    name='iflag',
    version='0.1.0',
    description='A Python library for the Itron / Actaris IFLAG and Corus protocol',
    long_description=readme + '\n\n' + history,
    long_description_content_type="text/markdown",

    url='https://github.com/pwitab/iflag',
    author=('Henrik Palmlund Wahlgren '
            '@ Palmlund Wahlgren Innovative Technology AB'),
    author_email='henrik@pwit.se',
    license='BSD-3-Clause',
    packages=['iflag'],
    install_requires=['attr'],
    zip_safe=False,
    keywords=[],
    classifiers=[],

)
