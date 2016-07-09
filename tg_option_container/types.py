import datetime
import inspect

from gettext import gettext as _

import dateutil.parser


class InvalidOption(AttributeError):
    """Special exception used when option validation fails
    """

    def __init__(self, message, **kwargs):
        self.message = message
        self.format_params = kwargs

        super(InvalidOption, self).__init__(message)

    def add_params(self, **kwargs):
        self.format_params.update(kwargs)

    def __str__(self):
        msg = self.message

        if self.format_params:
            msg = msg.format(**self.format_params)

        return msg


class MinValueValidator(object):
    """Validate the value is greater or equal to I{min_value}
    """

    def __init__(self, min_value):
        self.min_value = min_value

    def __str__(self):
        return '<MinValueValidator min_value={0}>'.format(self.min_value)

    def __call__(self, value):
        if value < self.min_value:
            raise InvalidOption(_('Ensure value for option `{key}` is greater than or equal to {min_value}'), min_value=self.min_value)

        return True


class MaxValueValidator(object):
    """Validate the value is less or equal to I{max_value}
    """

    def __init__(self, max_value):
        self.max_value = max_value

    def __str__(self):
        return '<MaxValueValidator max_value={0}>'.format(self.max_value)

    def __call__(self, value):
        if value > self.max_value:
            raise InvalidOption(_('Ensure value for option `{key}` is less than or equal to {max_value}'), max_value=self.max_value)

        return True


class ChoicesValidator(object):
    """Validate the value is in I{choices}
    """

    def __init__(self, choices):
        if isinstance(choices, list):
            choices = tuple(choices)

        try:
            from model_utils import Choices

        except ImportError:
            pass

        else:
            if isinstance(choices, Choices):
                choices = tuple([db_value for db_value, code_identifier in choices])

        assert isinstance(choices, tuple)

        self.choices = choices

    def __str__(self):
        return '<ChoicesValidator choices={0}>'.format(self.choices)

    def __call__(self, value):
        if value not in self.choices:
            raise InvalidOption(_('Invalid choice {value} for option `{key}`, choices are {choices}.'), value=value, choices=self.choices)

        return True


class TypeValidator(object):
    """Validate the value is an instance of I{expected_type}
    """

    def __init__(self, expected_type, prepend='', append=''):
        self.append = append
        self.prepend = prepend
        self.expected_type = expected_type

        # If this is a callable, Option class will append it to cleaners automatically
        self.clean = None

    def __str__(self):
        return '<TypeValidator expected_type={0}{1}{2}>'.format(
            self.expected_type,
            ' prepend={0}'.format(self.prepend) if self.prepend else '',
            ' append={0}'.format(self.append) if self.append else '',
        )

    def __call__(self, value):
        if not isinstance(value, self.expected_type):
            raise InvalidOption(_('{prepend}Expected type {expected_type} for option `{key}`, provided type is {value_type}.{append}'),
                                value_type=type(value),
                                expected_type=self.expected_type,
                                prepend='{0} '.format(self.prepend) if self.prepend else '',
                                append=' {0}'.format(self.append) if self.append else '')

        return True


class ListValidator(TypeValidator):
    """Validate the value is an instance of list and all items of it are I{expected_type}
    """

    def __init__(self, expected_type, allow_empty=True):
        self.allow_empty = allow_empty

        super(ListValidator, self).__init__(expected_type=expected_type)

        self.clean = self._clean

    def __str__(self):
        return '<ListValidator expected_type={0} allow_empty={1}>'.format(
            self.expected_type,
            self.allow_empty,
        )

    def _clean(self, value):
        from .container import OptionContainer

        # This is just a sanity check
        if not isinstance(value, list):
            raise InvalidOption(_('Expected type {expected_type} for option `{key}`, provided type is {value_type}.'),
                                value_type=type(value),
                                expected_type=list)

        if self.expected_type is not None:
            if inspect.isclass(self.expected_type) and issubclass(self.expected_type, OptionContainer):
                # Expected type is an OptionContainer, lets try to construct it
                value = [self.expected_type(**params) if not isinstance(params, self.expected_type) else params for params in value]

            elif isinstance(self.expected_type, Option):
                # Expected type is an Option, lets use it to validate our value
                value = [self.expected_type.validate(inner) for inner in value]

        return value

    def __call__(self, value):
        if not isinstance(value, list):
            raise InvalidOption(_('Expected type {expected_type} for option `{key}`, provided type is {value_type}.'),
                                value_type=type(value),
                                expected_type=list)

        if self.expected_type is not None:
            if isinstance(self.expected_type, Option):
                if not all([self.expected_type.is_valid(x) for x in value]):
                    raise InvalidOption(_('Expected all items in list to be OPTION: {expected_type} for option `{key}`.'),
                                        expected_type=self.expected_type)

            else:
                if not all([isinstance(x, self.expected_type) for x in value]):
                    raise InvalidOption(_('Expected all items in list to be {expected_type} for option `{key}`.'),
                                        expected_type=self.expected_type)

        return True


def clean_datetime(value):
    if value is not None:
        # Also support some more human readable variants of iso8601
        if isinstance(value, str):
            value = value.replace(' +', '+')
            value = value.replace(' Z', 'Z')

            value = dateutil.parser.parse(value)

    return value


def clean_option_container(container_cls):
    from .container import OptionContainer

    def _clean_option_container(value):
        try:
            if isinstance(value, dict):
                return container_cls(**value)

            elif isinstance(value, OptionContainer):
                if not isinstance(value, container_cls):
                    raise InvalidOption(_('Provided OptionContainer instance {value} is not a subclass {container_cls}'),
                                        value=value,
                                        container_cls=container_cls)

                return value

            else:
                return container_cls()

        except InvalidOption as e:
            raise InvalidOption('{key}:{inner}', inner=str(e))

    setattr(_clean_option_container, 'container_cls', container_cls)

    return _clean_option_container


class Undefined(object):  # pragma: no cover
    """
    This class is used to represent no data being provided for a given option value.

    It is required because `None` may be a valid value in some cases.
    """
    def __str__(self):
        return 'undefined'

    def __repr__(self):
        return self.__str__()


class Option(object):
    """Single option definition for option containers

    Attributes:
        name (str): The option name
        default (any): The default value
        validators (callable): Callable with signature `fn(value) -> bool` used to validate the input value (can also raise InvalidOption)
        clean (callable): Callable with signature `fn(value) -> any` used to clean
            the value before running I{validators} (can also be a list of callables).

        choices: If provided adds ChoicesValidator to I{validators}
        expected_type: If provided adds TypeValidator to I{validators}. This can also be an instance of TypeValidator (or a
            subclass instance).
        min_value: If provided adds MinValueValidator to I{validators}
        max_value: If provided adds MaxValueValidator to I{validators}
        none_to_default: If provided `None` will be treated as `Undefined` (cleaned to default)
        resolve_default: If provided default will be treated as a callable
    """

    def __init__(self, name, default, validators=None, clean=None, **kwargs):
        assert isinstance(name, str), \
            'Name should be a string'

        self.name = name
        self.default = default
        self.validators = []
        self.clean = []

        if clean is not None:
            if not isinstance(clean, list):
                clean = [clean, ]

            assert all([callable(x) for x in clean])

            self.clean = clean

        if validators is not None:
            if not isinstance(validators, list):
                validators = [validators, ]

            assert all([callable(x) for x in validators])

            self.validators = validators

        # Handle expected_type kwarg
        expected_type = kwargs.get('expected_type', None)
        expected_type__prepend = kwargs.get('expected_type__prepend', '')
        expected_type__append = kwargs.get('expected_type__append', '')

        if expected_type is not None:
            if not isinstance(expected_type, TypeValidator):
                expected_type = TypeValidator(
                    expected_type=expected_type, prepend=expected_type__prepend, append=expected_type__append
                )

            self.validators.insert(0, expected_type)

            validator_clean = getattr(expected_type, 'clean', None)

            if validator_clean is not None:
                self.clean.insert(0, validator_clean)

        # Handle choices kwarg
        choices = kwargs.get('choices', None)
        if choices is not None:
            self.validators.insert(0, ChoicesValidator(choices=choices))

        # Handle min_value kwarg
        min_value = kwargs.get('min_value', None)
        if min_value is not None:
            self.validators.append(
                MinValueValidator(min_value=min_value)
            )

        # Handle max_value kwarg
        max_value = kwargs.get('max_value', None)
        if max_value is not None:
            self.validators.append(
                MaxValueValidator(max_value=max_value)
            )

        # Handle none_to_default kwarg
        self.none_to_default = kwargs.get('none_to_default', False)

    def __str__(self):
        return "<{cls} {name}: default={default}, {typedef}>".format(
            cls=self.__class__.__name__,
            name=self.name,
            default=self.default,
            typedef=self.typedef,
        )

    def __repr__(self):  # pragma: no cover
        return self.__str__()

    @property
    def typedef(self):
        return "validators={validators} clean={clean}".format(
            clean=self.clean,
            validators=[str(x) for x in self.validators],
        )

    def _nvl(self, value=Undefined()):
        """Convert values to I{default} when value is Undefined"""

        # If self.none_to_default is True, we convert None to Undefined()
        if self.none_to_default and value is None:
            value = Undefined()

        # If value is not defined, return the default, else the value
        if isinstance(value, Undefined):
            return self.default

        else:
            return value

    def _run_clean(self, value):
        """Run all I{clean} on the value"""

        for clean in self.clean:
            value = clean(value)

        return value

    def is_valid(self, value):
        try:
            self._run_validators(value)

        except InvalidOption:
            return False

        else:
            return True

    def _run_validators(self, value):
        for validator in self.validators:
            if not validator(value):
                raise InvalidOption('Invalid value `{value}` for option `{key}`', value=value)

    def validate(self, value):
        """Clean and validate the provided value against I{validators}

        Args:
            value: Value to validate
        """
        value = self._nvl(value)
        value = self._run_clean(value)

        # Run validators on the cleaned value
        self._run_validators(value)

        # Return the cleaned value
        return value

    @classmethod
    def integer(cls, name, default, validators=None, clean=None, **kwargs):
        """Option of integer type

        Note:
            This is a shorthand for: Option(..., expected_type=int)

        Args:
            name: see Option.__init__
            default: see Option.__init__
            validators: see Option.__init__
            clean: see Option.__init__
            **kwargs: see Option.__init__
        """
        kwargs.setdefault('expected_type', int)

        return Option(name, default, validators=validators, clean=clean, **kwargs)

    @classmethod
    def boolean(cls, name, default, validators=None, clean=None, **kwargs):
        """Option of boolean type

        Note:
            This is a shorthand for: Option(..., expected_type=bool)

        Args:
            name: see Option.__init__
            default: see Option.__init__
            validators: see Option.__init__
            clean: see Option.__init__
            **kwargs: see Option.__init__
        """
        kwargs.setdefault('expected_type', bool)

        return Option(name, default, validators=validators, clean=clean, **kwargs)

    @classmethod
    def string(cls, name, default, validators=None, clean=None, **kwargs):
        """Option of string type

        Note:
            This is a shorthand for: Option(..., expected_type=str)

        Args:
            name: see Option.__init__
            default: see Option.__init__
            validators: see Option.__init__
            clean: see Option.__init__
            **kwargs: see Option.__init__
        """
        kwargs.setdefault('expected_type', str)

        return Option(name, default, validators=validators, clean=clean, **kwargs)

    @classmethod
    def iso8601(cls, name, default, validators=None, clean=None, **kwargs):
        """Option of iso8601 type

        Note:
            This is a shorthand for:
                Option(..., expected_type=datetime.datetime, expected_type__append=_('Please use ISO_8601.'), clean=clean_datetime)

        Accepts the following formats:
            - ISO_8601
            - ISO_8601 with spaces: 2016-05-09 16:00:00 +02:00

            Note:
                For both variants the timezone part is optional and defaults to UTC

        Args:
            name: see Option.__init__
            default: see Option.__init__
            validators: see Option.__init__
            clean: see Option.__init__
            **kwargs: see Option.__init__
        """
        kwargs.setdefault('expected_type', datetime.datetime)
        kwargs.setdefault('expected_type__append', _('Please use ISO_8601.'))

        if not clean:
            clean = []

        if not isinstance(clean, list):
            clean = [clean, ]

        clean.append(clean_datetime)

        return Option(name, default, validators=validators, clean=clean, **kwargs)

    @classmethod
    def list(cls, name, default, validators=None, clean=None, inner_type=None, allow_empty=True, **kwargs):
        """Option of list type

        Note:
            This is a shorthand for: Option(..., expected_type=ListValidator(inner_type, autoclean, allow_empty))

        Args:
            inner_type (any): Can be used to construct a typed list
            allow_empty (Optional[bool]): If False ListValidator will also check that the list is not empty. Defaults to **True**

            name: see Option.__init__
            default: see Option.__init__
            validators: see Option.__init__
            clean: see Option.__init__
            **kwargs: see Option.__init__
        """
        from .container import OptionContainer

        # Construct a list if list is provided
        if callable(default):
            kwargs.setdefault('resolve_default', True)

        kwargs.setdefault('expected_type', ListValidator(inner_type, allow_empty))

        res = Option(name, default, validators=validators, clean=clean, **kwargs)

        if inspect.isclass(inner_type) and issubclass(inner_type, OptionContainer):
            # This is for pretty printing and as_dict
            setattr(res, '_list_of_containers', True)

        return res

    @classmethod
    def nested(cls, name, container_cls, validators=None, clean=None, **kwargs):
        """Option of string type

        Note:
            This is a shorthand for:
                Option(..., expected_type=container_cls, clean=clean_option_container(container_cls))

        Args:
            container_cls: The option container to nest

            name: see Option.__init__
            validators: see Option.__init__
            clean: see Option.__init__
            **kwargs: see Option.__init__
        """
        kwargs['expected_type'] = container_cls

        if not clean:
            clean = []

        if not isinstance(clean, list):
            clean = [clean, ]

        clean.append(clean_option_container(container_cls))

        opt = Option(name, {}, validators=validators, clean=clean, **kwargs)

        setattr(opt, '_is_nested', True)

        return opt
