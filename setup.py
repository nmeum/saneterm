from setuptools import setup

setup(
    name='saneterm',
    version='0.0.1',
    packages=['saneterm'],
    install_requires=[
        'PyGObject',
    ],
    entry_points={
        'gui_scripts': [
            'saneterm = saneterm.__main__:main'
        ]
    },
)
