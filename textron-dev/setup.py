import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="textron",
    version="1.1.4b-1",
    author="Lev Grin",
    author_email="grin@monolithus.ru",
    description="Textron app for RFC-20 measurements analysis",
    long_description=long_description,
    packages=setuptools.find_packages(),
    install_requires=['bokeh', 'numpy', 'scipy', 'pandas'],
    classifiers=[
            'Development Status :: 2 - Beta',
            'Programming Language :: Python',
            'Programming Language :: Python :: 3',
            ],)
