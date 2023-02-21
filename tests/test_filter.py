import dataclasses

import pytest

from supine.filter import DataclassFilterMixin, Filter


class BadSubclass(DataclassFilterMixin, Filter):
    pass


class NoFieldsDefined(DataclassFilterMixin, Filter):
    pass


@dataclasses.dataclass
class DataclassFilter(DataclassFilterMixin, Filter):
    named_attr: str = None


def test_dataclass_mixin_requires_dataclass_subclass():
    with pytest.raises(ValueError):
        BadSubclass()


def test_dataclass_mixin_requires_fields():
    with pytest.raises(ValueError):
        NoFieldsDefined()


def test_dataclass_has_filter_functions():
    instance = DataclassFilter()
    assert callable(instance.modify_query)
    assert callable(instance.modify_results)
