from tg_option_container.container import OptionContainer
from tg_option_container.types import InvalidOption, Option, Undefined


__name__ = 'tg-option-container'
__title__ = 'TG Option Container'
__description__ = 'Container for dictionary-like validated data structures'
__version__ = '0.4.0'
__author__ = 'Thorgate'
__url__ = 'https://github.com/thorgate/tg-option-container'
__email__ = 'code@thorgate.eu'
__license__ = 'BSD 3-Clause'
__copyright__ = 'Copyright 2015-present Thorgate<code@thorgate.eu>'

NAME = __name__
VERSION = __version__

__all__ = [
    'InvalidOption',
    'Option',
    'OptionContainer',
    'Undefined',
]
