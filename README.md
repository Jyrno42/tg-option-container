# tg-option-container

[![Build Status](https://travis-ci.org/thorgate/tg-option-container.svg)](https://travis-ci.org/thorgate/tg-option-container)
[![Coverage Status](https://codecov.io/gh/thorgate/tg-option-container/branch/master/graph/badge.svg)](https://codecov.io/gh/thorgate/tg-option-container)
[![PyPI Status](https://badge.fury.io/py/tg-option-container.png)](https://badge.fury.io/py/tg-option-container)

Container for dictionary-like validated data structures

Documentation is available on Read the Docs: [http://tg-option-container.readthedocs.io](http://tg-option-container.readthedocs.io)

## Getting started

Install tg-option-container:

```sh
pip install tg-option-container
```

Then use it in your project:

```python
from tg_option_container import Option, OptionContainer


class Character(OptionContainer):
    props = [
        Option.string('name', None),
        Option.string('gender', None, choices=('M', 'N')),
    ]


john = Character(name='John Smith', gender='M')

# This will raise: tg_option_container.types.InvalidOption: Invalid choice x for option `gender`, choices are ('M', 'N').
mary = Character(name='Mary Smith', gender='x')
```

## Development

You can run the tests by running `tox` in the top-level of the project.
