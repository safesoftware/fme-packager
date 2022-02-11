from setuptools import setup, find_packages


with open("README.md") as readme_file:
    readme = readme_file.read()


with open("fme_packager/__init__.py") as f:
    start = '__version__ = "'
    body = f.read()
    start_index = body.find(start) + len(start)
    version = body[start_index : body.find('"', start_index)]

setup(
    name="fme_packager",
    packages=find_packages(),
    version=version,
    description="Tool for creating FME Packages",
    long_description=readme,
    long_description_content_type="text/markdown",
    author="Carson Lam",
    author_email="carson.lam@safe.com",
    url="https://github.com/safesoftware/fme-packager",
    python_requires=">=3.6",
    install_requires=[
        "click~=8.0.0",
        "cookiecutter~=1.7.2",
        "defusedxml~=0.6.0",
        "jsonschema~=3.2.0",
        "pypng~=0.0.20",
        "ruamel.yaml~=0.16.10",
        "wheel~=0.35.1",
        "xmltodict~=0.12.0",
        "packaging~=21.0",
    ],
    extras_require={
        "dev": [
            "pytest",
            "black~=22.1.0",
        ],
    },
    entry_points={
        "console_scripts": ["fme_packager = fme_packager.cli:cli"],
    },
    keywords="fme fmepy package",
    classifiers=[
        "DO NOT UPLOAD TO PYPI",
        "Framework :: FME",
        "Development Status :: 4 - Pre-Alpha",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
    include_package_data=True,
    zip_safe=False,
)
