from setuptools import setup, find_packages


with open("README.md") as readme_file:
    readme = readme_file.read()


with open("fpkgr/__init__.py") as f:
    start = "__version__ = '"
    body = f.read()
    start_index = body.find(start) + len(start)
    version = body[start_index:body.find("'", start_index)]

setup(
    name="fpkgr",
    packages=find_packages(),
    version=version,
    description="Tool for creating FME Packages",
    long_description=readme,
    author="Carson Lam",
    author_email="carson.lam@safe.com",
    url="https://gtb-1.safe.internal/clam/fpkgr",
    install_requires=[
        "click",
        "ruamel.yaml",
        "cookiecutter",
        "wheel",
        "jsonschema",
        "pypng",
    ],
    entry_points={
        "console_scripts": ["fpkgr = fpkgr.cli:cli"],
    },
    keywords="fme fmepy package",
    classifiers=[
        "DO NOT UPLOAD TO PYPI",
        "Framework :: FME",
        "Development Status :: 4 - Pre-Alpha",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
    ],
    zip_safe=False,
)
