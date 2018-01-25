from setuptools import setup

setup(
    name='fediplay',
    version='0.1',
    install_requires=[
        'Mastodon.py',
        'cssselect',
        'lxml',
        'youtube-dl',
        'python-mpd2'
    ],
    entry_points={
        'console_scripts': [
            'fediplay = fediplay:main'
        ]
    }
)

