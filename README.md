![Tests workflow](https://github.com/infraguys/gcl_sdk/actions/workflows/tests.yaml/badge.svg)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/gcl-sdk)
![PyPI - Downloads](https://img.shields.io/pypi/dm/gcl-sdk)

Welcome to the Genesis SDK!

The Genesis SDK is a set of tools for developing Genesis elements. Main information you can find in the [wiki](https://github.com/infraguys/gcl_sdk/wiki).


# 🚀 Development

Install required packages:

Ubuntu:
```bash
sudo apt-get install tox libev-dev
```

Fedora:
```bash
sudo dnf install python3-tox libev-devel
```

Initialize virtual environment:

```bash
tox -e develop
source .tox/develop/bin/activate
```

# ⚙️ Tests

**NOTE:** Python version 3.12 is supposed to be used, but you can use other versions

Unit tests:

```bash
tox -e py312
```

Functional tests:

```bash
tox -e py312-functional
```


# 🔗 Related projects

- Genesis Core is main project of the Genesis ecosystem. You can find it [here](https://github.com/infraguys/genesis_core).
- Genesis DevTools it's a set oftools to manager life cycle of genesis projects. You can find it [here](https://github.com/infraguys/genesis_devtools).



# 💡 Contributing

Contributing to the project is highly appreciated! However, some rules should be followed for successful inclusion of new changes in the project:
- All changes should be done in a separate branch.
- Changes should include not only new functionality or bug fixes, but also tests for the new code.
- After the changes are completed and **tested**, a Pull Request should be created with a clear description of the new functionality. And add one of the project maintainers as a reviewer.
- Changes can be merged only after receiving an approve from one of the project maintainers.
