from setuptools import setup


setup(
    name='pwcp',
    version='0.1',
    packages=['pwcp'],
    install_requires=['pcpp@git+https://github.com/Krutoy-4el/pcpp.git'],
    entry_points={
        'console_scripts': ['pwcp=pwcp:main']
    }
)
