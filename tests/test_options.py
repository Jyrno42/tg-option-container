import datetime
import decimal

from gettext import gettext as _

import pytest
import pytz

from tg_option_container import InvalidOption, Option, OptionContainer
from tg_option_container.types import (ChoicesValidator, MaxValueValidator, MinValueValidator, TypeValidator, Undefined, clean_datetime,
                                       clean_option_container)

try:
    from unittest.mock import Mock, patch

except ImportError:
    from mock import Mock, patch


def assert_datetime_equal(a, b):
    aa = a.astimezone(pytz.utc)
    bb = b.astimezone(pytz.utc)

    assert aa == bb, 'Dates %s and %s are not equal (%s, %s)' % (a, b, aa, bb)

    return aa == bb


def test_fails_with_diamond_inheritance():
    class A(OptionContainer):
        pass

    class B(OptionContainer):
        pass

    with pytest.raises(AssertionError) as exc_info:
        class C(A, B):
            pass

    assert 'OptionContainers do not support diamond inheritance' == str(exc_info.value)


def test_fails_if_props_is_not_list():
    with pytest.raises(TypeError) as exc_info:
        class BadContainer1(OptionContainer):
            props = {}

    assert 'BadContainer1.props should be a list' == str(exc_info.value)

    class A(OptionContainer):
        pass

    with pytest.raises(TypeError) as exc_info:
        class BadContainer2(A):
            props = {}

    assert 'BadContainer2.props should be a list' == str(exc_info.value)


def test_to_str():
    class A(OptionContainer):
        props = [
            Option.string('host', None),
        ]

    class B(A):
        name = 'xyz'

    assert str(A) == 'A\n\t{0}'.format(A.props[0])
    assert str(A(host='hello')) == '<A>:\n\thost: hello'
    assert str(A) == A(host='hello').typedef()

    assert str(B) == 'B\n\t{0}'.format(B.props[0])
    assert str(B(host='hello')) == '<B xyz>:\n\thost: hello'


def test_identifier_is_set():
    class A(OptionContainer):
        pass

    class B(OptionContainer):
        name = 'luke'

    assert getattr(A(), 'identifier', None) == A.__name__
    assert getattr(B(), 'identifier', None) == 'luke'


def test_metaclass_works():
    class A(OptionContainer):
        props = [
            Option.string('host', None),
            Option.string('user', None),
            Option.string('password', None),
        ]

    assert hasattr(A, 'defs')
    assert not hasattr(A, 'definitions')

    assert A.defs == {
        'host': A.props[0],
        'user': A.props[1],
        'password': A.props[2],
    }

    a_inst = A(host='some.where', user='john', password='pass')
    assert getattr(a_inst, 'definitions', {}) == {
        'host': A.props[0],
        'user': A.props[1],
        'password': A.props[2],
    }

    class B(A):
        props = [
            Option.string('user', 'yolger'),
        ]

    assert hasattr(B, 'defs')
    assert not hasattr(B, 'definitions')

    assert B.defs == {
        'host': A.props[0],
        'user': B.props[0],
        'password': A.props[2],
    }

    b_inst = B(host='other.place', password='pass')
    assert getattr(b_inst, 'definitions', {}) == {
        'host': A.props[0],
        'user': B.props[0],
        'password': A.props[2],
    }

    class C(B):
        props = [
            Option.string('password', 'pass'),
            Option.integer('port', 8080),
        ]

    assert hasattr(C, 'defs')
    assert not hasattr(C, 'definitions')

    assert C.defs == {
        'host': A.props[0],
        'user': B.props[0],
        'password': C.props[0],
        'port': C.props[1],
    }

    c_inst = C(host='other.place')
    assert getattr(c_inst, 'definitions', {}) == {
        'host': A.props[0],
        'user': B.props[0],
        'password': C.props[0],
        'port': C.props[1],
    }

    assert c_inst.get('password') == 'pass'


def test_generic_works():
    class A(OptionContainer):
        props = [
            Option.string('host', 'some.where'),
        ]

    first = A()
    second = A(host='other.place')

    # Defaults are set properly & __getitem__ works
    assert first['host'] == 'some.where'

    # can be overwritten & .get works
    assert second.get('host') == 'other.place'

    # Set works
    second.set('host', 'last.place')
    assert second.get('host') == 'last.place'

    # Set triggers option.validator
    with patch('tg_option_container.types.Option.validate') as fn_mock:
        fn_mock.return_value = 12345

        second.set('host', 'invisible.place')

        fn_mock.assert_called_once_with('invisible.place')
        assert second.get('host') == 12345

    # Set with bad key fails
    with pytest.raises(InvalidOption) as exc_info:
        second.set('nanny', 12345)

    assert str(exc_info.value) == str(_('Invalid key {key} for {identifier}')).format(key='nanny', identifier=first.identifier)

    # Fails with correct error
    with pytest.raises(InvalidOption) as exc_info:
        second.set('host', 12345)

    expected_format_params = {
        'value_type': int,
        'expected_type': str,
        'prepend': '',
        'append': '',
        'key': 'host',
    }

    assert str(exc_info.value) == str(_('{prepend}Expected type {expected_type} for option `{key}`, '
                                        'provided type is {value_type}.{append}')).format(**expected_format_params)
    assert exc_info.value.format_params == expected_format_params


def test_invalid_option_exception():
    # Ensure correct base exception is used, we need this since some code
    # might depend on this in the future.
    assert issubclass(InvalidOption, AttributeError)

    # No format params should result in a raw string
    assert str(InvalidOption('Foo {some_value} {other_param}')) == 'Foo {some_value} {other_param}'

    # Providing format params make __str__ format the error
    assert str(InvalidOption('Foo {some_value}', some_value='bar')) == 'Foo bar'

    # It should also be possible to add format params after creating the exception
    e = InvalidOption('Foo {some_value} {other_value}', some_value='bar')

    # Calling __str__ before all parameter are added should raise a KeyError
    with pytest.raises(KeyError):
        str(e)

    # add `other_value` parameter
    e.add_params(other_value='baz')
    assert str(e) == 'Foo bar baz'


def test_min_value_validator():
    validator = MinValueValidator(0)

    assert callable(validator)
    assert validator(2) is True
    assert validator(0) is True

    with pytest.raises(InvalidOption) as exc_info:
        validator(-1)

    assert exc_info.value.format_params['min_value'] == 0
    assert str(validator) == '<MinValueValidator min_value=0>'


def test_max_value_validator():
    validator = MaxValueValidator(0)

    assert callable(validator)
    assert validator(-2) is True
    assert validator(0) is True

    with pytest.raises(InvalidOption) as exc_info:
        validator(1)

    assert exc_info.value.format_params['max_value'] == 0
    assert str(validator) == '<MaxValueValidator max_value=0>'


def test_choices_validator():
    validator = ChoicesValidator(('a', 'b'))

    assert callable(validator)
    assert validator('a') is True
    assert validator('b') is True

    with pytest.raises(InvalidOption) as exc_info:
        validator('c')

    assert exc_info.value.format_params['choices'] == ('a', 'b')
    assert str(validator) == '<ChoicesValidator choices={0}>'.format(('a', 'b'))

    # Should also accept a list (but convert it to a tuple)
    assert ChoicesValidator(['a', 'b']).choices == ('a', 'b')

    # Should raise AssertionError if choices is of invalid type
    with pytest.raises(AssertionError):
        ChoicesValidator({'a', 'b'})


def test_type_validator():
    validator = TypeValidator(int)

    assert callable(validator)
    assert validator(1) is True

    with pytest.raises(InvalidOption) as exc_info:
        validator('c')

    assert exc_info.value.format_params['expected_type'] == int
    assert exc_info.value.format_params['value_type'] == str
    assert str(validator) == '<TypeValidator expected_type={0}>'.format(int)

    # Should also support tuple of types
    validator2 = TypeValidator((int, float, decimal.Decimal))

    assert callable(validator2)
    assert validator2(1) is True
    assert validator2(1.0) is True
    assert validator2(decimal.Decimal(1.0)) is True

    with pytest.raises(InvalidOption) as exc_info:
        validator2('c')

    assert exc_info.value.format_params['expected_type'] == (int, float, decimal.Decimal)
    assert exc_info.value.format_params['value_type'] == str
    assert str(validator2) == '<TypeValidator expected_type={0}>'.format((int, float, decimal.Decimal))

    # Should also support append & prepend
    validator = TypeValidator(int, append='dorian', prepend='john')

    assert callable(validator)
    assert validator(1) is True

    with pytest.raises(InvalidOption) as exc_info:
        validator('c')

    assert exc_info.value.format_params['prepend'] == 'john '
    assert exc_info.value.format_params['append'] == ' dorian'
    assert exc_info.value.format_params['expected_type'] == int
    assert exc_info.value.format_params['value_type'] == str
    assert str(validator) == '<TypeValidator expected_type={0} prepend=john append=dorian>'.format(int)


def test_option_logic():
    validator = lambda x: True
    cleaner = lambda x: x

    opt_a = Option('some_value', 'bar', validators=validator, clean=cleaner)
    opt_b = Option('some_value', 'bar', validators=[validator, ], clean=[cleaner, ])

    # Option must accept both a list and a single callable for `clean` and `validators`
    assert opt_a.clean == [cleaner, ] and opt_a.validators == [validator, ]
    assert opt_b.clean == [cleaner, ] and opt_b.validators == [validator, ]

    # If any items in cleaners are not callable, an AssertionError must be raised
    with pytest.raises(AssertionError):
        Option('some_option', 'bar', clean=[cleaner, 'xxx'])

    # If items in validators are not callable, an AssertionError must be raised
    with pytest.raises(AssertionError):
        Option('some_option', 'bar', validators=[validator, 'xxx'])

    # If value is set to Undefined() the end value must be the default
    assert Option('some_value', 'bar').validate(Undefined()) == 'bar'

    # If `none_to_default` is True, None must also act the same way
    assert Option('some_value', 'bar', none_to_default=True).validate(None) == 'bar'

    # If `choices` kwarg is provided, an instance of `ChoicesValidator` must be added to I{validators}
    opt = Option('coord', 'y', choices=('y', 'z'))

    assert opt.validators
    assert isinstance(opt.validators[0], ChoicesValidator)
    assert opt.validators[0].choices == ('y', 'z')

    # If `expected_type` kwarg is provided, an instance of `TypeValidator` must be added to I{validators}
    opt = Option('coord', 'y', expected_type=float)

    assert opt.validators
    assert isinstance(opt.validators[0], TypeValidator)
    assert opt.validators[0].expected_type == float

    # If `min_value` kwarg is provided, an instance of `MinValueValidator` must be added to I{validators}
    opt = Option('coord', 'y', min_value=0)

    assert opt.validators
    assert isinstance(opt.validators[0], MinValueValidator)
    assert opt.validators[0].min_value == 0

    # If `max_value` kwarg is provided, an instance of `MaxValueValidator` must be added to I{validators}
    opt = Option('coord', 'y', max_value=0)

    assert opt.validators
    assert isinstance(opt.validators[0], MaxValueValidator)
    assert opt.validators[0].max_value == 0

    # Ensure cleaners and validators are executed when I{validate} is called
    clean_mock = Mock(return_value='xyz')
    validate_mock = Mock(return_value=True)

    opt = Option('some_value', 'bar', validators=validate_mock, clean=clean_mock)

    # Ensure our mocks are used
    assert opt.clean == [clean_mock, ]
    assert opt.validators == [validate_mock, ]

    # Clean should turn our value to xyz
    assert opt.validate('foo') == 'xyz'

    # Both clean and validator mock should have been called
    clean_mock.assert_called_once_with('foo')
    validate_mock.assert_called_once_with('xyz')

    # Reset validator mock
    validate_mock.reset_mock()
    validate_mock.return_value = False

    # Validate should raise InvalidOption since our validator is marked to return False now
    with pytest.raises(InvalidOption):
        opt.validate('foo')


def test_clean_datetime():
    expected_utc = datetime.datetime(2016, 5, 9, 16, 0, 0, tzinfo=pytz.UTC)

    assert_datetime_equal(clean_datetime('2016-05-09 16:00:00 +00:00'), expected_utc)
    assert_datetime_equal(clean_datetime('2016-05-09 16:00:00+00:00'), expected_utc)
    assert_datetime_equal(clean_datetime('2016-05-09T16:00:00+00:00'), expected_utc)
    assert_datetime_equal(clean_datetime('2016-05-09T16:00:00 +00:00'), expected_utc)
    assert_datetime_equal(clean_datetime('2016-05-09T16:00:00 +0000'), expected_utc)
    assert_datetime_equal(clean_datetime('2016-05-09T16:00:00 Z'), expected_utc)
    assert_datetime_equal(clean_datetime('2016-05-09T16:00:00Z'), expected_utc)

    expected_tln = pytz.timezone('Europe/Tallinn').localize(datetime.datetime(2016, 5, 9, 16, 0, 0))

    assert_datetime_equal(clean_datetime('2016-05-09 16:00:00 +03:00'), expected_tln)
    assert_datetime_equal(clean_datetime('2016-05-09 16:00:00+03:00'), expected_tln)
    assert_datetime_equal(clean_datetime('2016-05-09T16:00:00+03:00'), expected_tln)
    assert_datetime_equal(clean_datetime('2016-05-09T16:00:00 +03:00'), expected_tln)

    assert clean_datetime(None) is None

    # Should return the same datetime if provided with a datetime
    assert clean_datetime(expected_utc) == expected_utc


def test_iso8601():
    def foobar(value):
        return value

    class A(OptionContainer):
        props = [
            Option.iso8601('foo', None),
        ]

    class B(OptionContainer):
        props = [
            Option.iso8601('foo', None, clean=[foobar, ]),
        ]

    class C(OptionContainer):
        props = [
            Option.iso8601('foo', None, clean=foobar),
        ]

    assert tuple(A.defs['foo'].clean) == tuple([clean_datetime, ])
    assert tuple(B.defs['foo'].clean) == tuple([foobar, clean_datetime, ])
    assert tuple(C.defs['foo'].clean) == tuple([foobar, clean_datetime, ])

    assert any([isinstance(x, TypeValidator) for x in A.defs['foo'].validators])

    validator = list(filter(lambda x: isinstance(x, TypeValidator), A.defs['foo'].validators))[0]

    assert validator.append == _('Please use ISO_8601.')
    assert validator.expected_type == datetime.datetime


def test_clean_option_container():
    class A(OptionContainer):
        props = [
            Option.string('host', 'some.where'),
        ]

    class B(OptionContainer):
        pass

    # Works properly
    first = clean_option_container(A)(None)
    second = clean_option_container(A)({'host': 'other.place'})

    # Defaults are set properly & __getitem__ works
    assert first['host'] == 'some.where'

    # can be overwritten & .get works
    assert second.get('host') == 'other.place'

    # Set works
    second.set('host', 'last.place')
    assert second.get('host') == 'last.place'

    # Fails with correct error
    with pytest.raises(InvalidOption) as exc_info:
        clean_option_container(A)({'host': 12345})

    # Add key param (option containers do it automatically when nested)
    exc_info.value.add_params(key='some_key')

    base_msg = _('{prepend}Expected type {expected_type} for option `{key}`, provided type is {value_type}.{append}').format(**{
        'value_type': int,
        'expected_type': str,
        'prepend': '',
        'append': '',
        'key': 'host',
    })

    assert str(exc_info.value) == '{key}:{inner}'.format(**{
        'key': 'some_key',
        'inner': base_msg,
    })
    assert exc_info.value.format_params == {
        'key': 'some_key',
        'inner': base_msg,
    }

    # returns value if provided with OptionContainer instance
    inst = A()
    assert clean_option_container(A)(inst) == inst

    # validates that value is instance of container_cls if provided with OptionContainer instance
    with pytest.raises(InvalidOption) as exc_info:
        assert clean_option_container(B)(inst)

    # Add key param (option containers do it automatically when nested)
    exc_info.value.add_params(key='some_key')

    base_msg = _('Provided OptionContainer instance {value} is not a subclass {container_cls}').format(**{
        'value': inst,
        'container_cls': B,
    })

    expected_format_params = {
        'key': 'some_key',
        'inner': base_msg,
    }

    assert str(exc_info.value) == '{key}:{inner}'.format(**expected_format_params)
    assert exc_info.value.format_params == expected_format_params


def test_nested_containers():
    def foobar(value):
        return value

    class Child(OptionContainer):
        props = [
            Option.string('host', 'some.where'),
        ]

    class ParentA(OptionContainer):
        props = [
            Option.nested('child', Child),
        ]

    class ParentB(OptionContainer):
        props = [
            Option.nested('child', Child, clean=[foobar, ]),
        ]

    class ParentC(OptionContainer):
        props = [
            Option.nested('child', Child, clean=foobar),
        ]

    # Validate validators & cleaners are added properly
    assert len(ParentA.defs['child'].clean) == 1
    assert getattr(ParentA.defs['child'].clean[0], 'container_cls', Child)

    assert len(ParentB.defs['child'].clean) == 2
    assert getattr(ParentB.defs['child'].clean[1], 'container_cls', Child)

    assert len(ParentC.defs['child'].clean) == 2
    assert getattr(ParentC.defs['child'].clean[1], 'container_cls', Child)

    validator = list(filter(lambda x: isinstance(x, TypeValidator), ParentA.defs['child'].validators))[0]
    assert validator.expected_type == Child

    # Validate nested defaults work
    inst = ParentA()
    assert inst['child']['host'] == 'some.where'

    # Validate can set child
    inst.set('child', Child(host='magic.avenue'))
    assert inst['child']['host'] == 'magic.avenue'

    # Validate can set child keys
    inst.set(('child', 'host'), 'other.place')
    assert inst['child']['host'] == 'other.place'

    # Validate that setting child keys directly is not allowed
    with pytest.raises(NotImplementedError) as exc_info:
        inst['child'].set('host', 'other.place')

    assert 'Calling set on nested option containers is not allowed, please use set method of root container' in str(exc_info.value)

    # Validate key path is added to error
    with pytest.raises(InvalidOption) as exc_info:
        inst.set(('child', 'host'), 12345)

    assert 'child:' in str(exc_info.value)

    # Validate InvalidOption is raised if bad parent key path is provided
    with pytest.raises(InvalidOption) as exc_info:
        inst.set(('nanny', 'host'), 'xxx')

    assert str(exc_info.value) == str(_('Invalid key {key} for {identifier}')).format(key='nanny', identifier=inst.identifier)

    # Validate InvalidOption is raised if bad child key path is provided
    with pytest.raises(InvalidOption) as exc_info:
        inst.set(('child', 'nanny'), 'xxx')

    assert str(exc_info.value) == '{key}:{inner}'.format(
        inner=str(_('Invalid key {key} for {identifier}')).format(key='nanny', identifier=inst['child'].identifier),
        key='child',
    )

    # Validate grandchildren work
    class GrandParent(OptionContainer):
        props = [
            Option.nested('dad', ParentB),
            Option.string('name', 'Bobby'),
        ]

    # Validate nested defaults work for grandchildren
    inst = GrandParent()
    assert inst['dad']['child']['host'] == 'some.where'

    # Validate can set grandchild
    inst.set(('dad', 'child'), Child(host='magic.avenue'))
    assert inst['dad']['child']['host'] == 'magic.avenue'

    # Validate can set grandchild keys
    inst.set(('dad', 'child', 'host'), 'other.place')
    assert inst['dad']['child']['host'] == 'other.place'

    # Validate that setting child keys directly is not allowed
    with pytest.raises(NotImplementedError) as exc_info:
        inst['dad']['child'].set('host', 'other.place')

    assert 'Calling set on nested option containers is not allowed, please use set method of root container' in str(exc_info.value)

    # Validate InvalidOption is raised if bad parent key path is provided
    with pytest.raises(InvalidOption) as exc_info:
        inst.set(('nanny', 'host'), 'xxx')

    assert str(exc_info.value) == str(_('Invalid key {key} for {identifier}')).format(key='nanny', identifier=inst.identifier)

    # Validate InvalidOption is raised if bad child key path is provided
    with pytest.raises(InvalidOption) as exc_info:
        inst.set(('dad', 'nanny'), 'xxx')

    assert str(exc_info.value) == '{key}:{inner}'.format(
        inner=str(_('Invalid key {key} for {identifier}')).format(key='nanny', identifier=inst['dad'].identifier),
        key='dad',
    )

    # Validate InvalidOption is raised if bad grandchild key path is provided
    with pytest.raises(InvalidOption) as exc_info:
        inst.set(('dad', 'child', 'nanny'), 'xxx')

    assert str(exc_info.value) == '{key}:{inner}'.format(
        inner=str(_('Invalid key {key} for {identifier}')).format(key='nanny', identifier=inst['dad']['child'].identifier),
        key='dad:child',
    )

    # Validate InvalidOption is raised if attempts to set nested value for non-nested field
    with pytest.raises(InvalidOption) as exc_info:
        inst.set(('name', 'foo'), 'yolo')

    assert str(exc_info.value) == _('Key {key} for {identifier} is not a nested container').format(key='name', identifier=inst.identifier)
