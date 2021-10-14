import setuptools

with open('readme.md', 'r', encoding='utf-8') as fh:
    long_description = fh.read()

setuptools.setup(
    name='nsmbpy',
    version='1.0.0',
    author='RoadrunnerWMC',
    author_email='roadrunnerwmc@gmail.com',
    description='Python library that can help you read, modify and create file types used in New Super Mario Bros.',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/RoadrunnerWMC/nsmbpy',
    packages=setuptools.find_packages(),
    python_requires='>=3.6',
    install_requires=[
        'ndspy',
    ],
    classifiers=[
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
        'Operating System :: OS Independent',
    ],
)
