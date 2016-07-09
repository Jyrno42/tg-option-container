from gettext import gettext as _

import six

from tg_option_container.types import InvalidOption, Undefined


class PropsMetaClass(type):
    """Props metaclass

    Special meta-class for `OptionContainer` objects which collects all props
    from the inheritance chain and sets cls.defs to their reduced form.

    Reduced form is achieved by combining all props while iterating over
    the inheritance chain in reverse. This provides the possibility of overwriting
    the parent definitions for the child classes.
    """
    def __new__(cls, name, bases, attrs):
        super_new = super(PropsMetaClass, cls).__new__

        parents = [b for b in bases if isinstance(b, PropsMetaClass)]

        # If more than 1 parent, then it is a diamond shaped inheritance, lets bail out
        assert len(parents) < 2, 'OptionContainers do not support diamond inheritance'

        klass = super_new(cls, name, bases, attrs)
        setattr(klass, 'defs', {})

        # Assign defs attribute
        klass = cls.reduce_props(klass, *parents)

        # Assign nested_keys value
        klass = cls.assign_nested_keys(klass)

        return klass

    def __str__(self):
        return '{name}\n{defs}'.format(
            name=self.__name__,
            defs='\n'.join(['\t{0}'.format(definition) for key, definition in self.defs.items()])
        )

    @staticmethod
    def assign_nested_keys(klass):
        nested_keys = set()

        for name, definition in klass.defs.items():
            if getattr(definition, '_is_nested', False):
                nested_keys.add(name)

        setattr(klass, 'nested_keys', nested_keys)

        return klass

    @staticmethod
    def reduce_props(klass, *parents):
        props = {}

        parents = list(parents)

        parents.append(klass)

        # Collect all prop definitions from parents
        for parent in parents:
            # Collect parent `defs` (This allows more than two levels of extending)
            for prop_name, value in parent.defs.items():
                props[prop_name] = value

            # Collect props
            parent_props = getattr(parent, 'props', [])

            if not isinstance(parent_props, list):
                raise TypeError('{0}.props should be a list'.format(parent.__name__))

            for prop in parent_props:
                props[prop.name] = prop

        setattr(klass, 'defs', props)

        return klass


class OptionContainer(six.with_metaclass(PropsMetaClass)):
    """Container for dictionary-like validated data structures

    Provides a common base logic for building validated dictionaries. Rules
    are defined by a props attribute on the class. These is mainly used for
    validating various JSON based configuration data which MUST
    conform to a specific structure. OptionContainers support single-inheritance
    based extending (diamond-inheritance does not work). Child classes can also
    overwrite parent declarations by redefining them in their props.

    Examples:
        >>> from tg_option_container import Option, OptionContainer

        >>> class SampleOptions(OptionContainer):
        >>>     props = [
        >>>         Option.integer('verbosity', default=0, choices=[1, 2, 3]),
        >>>     ]

        >>> class ExtendedSampleOptions(SampleOptions):
        >>>     props = [
        >>>         Option.integer('timeout', default=30),
        >>>     ]

        Note: `ExtendedSampleOptions` accepts both `timeout` and `verbosity` props.
    """

    def __init__(self, **kwargs):
        self.identifier = getattr(self, 'name', self.__class__.__name__)
        self.definitions = {}
        self.values = {}

        for name, definition in self.defs.items():
            assert name == definition.name
            self.definitions[definition.name] = definition

        # populate all key
        values = dict([(x, Undefined()) for x in self.defs.keys()])

        # Update the ones that were provided
        values.update(kwargs)

        # First set all user defined stuff. This is needed since we want
        # to be sure we catch invalid keys before invalid values
        for key in kwargs.keys():
            self.set(key, values[key])

            del values[key]

        # Set all the default
        for key, value in values.items():
            self.set(key, value)

    def __str__(self):
        return self.representation()

    def representation(self, level=0):
        name = self.__class__.__name__

        if self.identifier and self.identifier != name:
            name = '{0} {1}'.format(name, self.identifier)

        definitions = []

        for key, value in self.values.items():
            if isinstance(value, OptionContainer):
                value = value.representation(level + 1)

            elif getattr(self.definitions[key], '_list_of_containers', None):
                glue = '\n{0}'.format('\t' * (level + 2))
                value = '{0}{1}'.format(
                    glue,
                    glue.join(['{0}: {1}'.format(i, x.representation(level + 2)) for i, x in enumerate(value)])
                )

            definitions.append('{0}{1}: {2}'.format('\t' * (level + 1), key, value))

        return '<{name}>:\n{defs}'.format(
            name=name,

            defs='\n'.join(definitions),
        )

    def typedef(self):
        return str(self.__class__)

    def __getitem__(self, item):
        return self.get(item)

    def __len__(self):
        return len(self.values)

    def __iter__(self):
        return iter(self.values.items())

    def as_dict(self):
        """Get a dictionary representation of this OptionContainer
        Returns:
            dict
        """

        result = {}

        for key, value in self.values.items():
            if key in self.nested_keys:
                result[key] = value.as_dict()

            elif getattr(self.definitions[key], '_list_of_containers', None):
                result[key] = [inner.as_dict() for inner in value]

            else:
                result[key] = value

        return result

    def get(self, key):
        """Get value of `key`

        Raises:
            KeyError: If key does not exist
        """
        return self.values[key]

    def set(self, key, value):
        """Set `key` to `value`

        Validate the `value` based on props definition for `key`.

        Args:
            key (Union[str, tuple]): Key to set for this option container, if the provided value is a tuple, it's expected to be a
                point to the nested container key.
            value (*): value to set for key

        Raises:
            InvalidOption: If validation fails
            AssertionError: If the `key` is not valid for this container
            NotImplementedError: If the current option container instance is nested
        """

        return self._set(key, value)

    def _set(self, key, value, allow_nested_set=False):
        if not allow_nested_set:
            if hasattr(self, '_parent'):
                raise NotImplementedError(_('Calling set on nested option containers is not allowed, '
                                            'please use set method of root container'))

        if isinstance(key, tuple):
            assert len(key) > 0, 'Nested keys must contain items'

            self._set_nested(key, value, root=True)

        else:
            if key not in self.definitions:
                raise InvalidOption(_('Invalid key {key} for {identifier}'), key=key, identifier=self.identifier)

            try:
                value = self.definitions[key].validate(value)

            except InvalidOption as e:
                # Add key param here, since Options don't know their key
                e.add_params(key=key)

                # Re-raise
                raise e

            # Set `_parent` attribute for child container instance
            if key in self.nested_keys:
                setattr(value, '_parent', True)

            self.values[key] = value

    def _set_nested(self, key_path, value, root=False):
        keys = list(key_path)

        key = keys.pop(0)
        children_count = len(keys)
        was_single_set_error = False

        try:
            if key not in self.definitions:
                was_single_set_error = True
                raise InvalidOption(_('Invalid key {key} for {identifier}'), key=key, identifier=self.identifier)

            if children_count and key not in self.nested_keys:
                was_single_set_error = True
                raise InvalidOption(_('Key {key} for {identifier} is not a nested container'), key=key, identifier=self.identifier)

            if children_count:
                # Has child, use it's _set directly (so we can set allow_nested_set to True)
                self.values[key]._set(tuple(keys), value, allow_nested_set=True)

            else:
                try:
                    # We have reached the end of the chain, use self.set
                    self._set(key, value, allow_nested_set=True)

                except InvalidOption:
                    was_single_set_error = True

                    raise

        except InvalidOption as e:
            if not children_count or (root and was_single_set_error):
                raise e

            else:
                raise InvalidOption('{key}{inner}', inner=str(e), key='{0}:'.format(key))
