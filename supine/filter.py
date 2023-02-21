import dataclasses
from abc import abstractmethod
from typing import Any

import sqlalchemy


def exclude_none(d: list[tuple[str, Any]]) -> dict:
    """
    for use as dict_factory argument to dataclasses.asdict()
    filters out "private" keys beginning with "_"
    filters out values equal to None
    """
    return {k: v for (k, v) in d if v is not None and k[0] != '_'}


class Filter:
    @abstractmethod
    def modify_query(self, query: sqlalchemy.Select) -> sqlalchemy.Select:
        return query

    @abstractmethod
    def modify_results(self, results: list) -> list:
        return results


class DataclassFilterMixin:
    def modify_query(self, query: sqlalchemy.Select) -> sqlalchemy.Select:
        """
        modifies a SQLAlchemy query using the properties of this dataclass

        by default, all properties are checked for equality with identically-named
        properties of the ORM class

        it is expected that most subclasses will need to override this method
        """
        # noinspection PyDataclass
        filter_by_args = dataclasses.asdict(self, dict_factory=exclude_none)
        return query.filter_by(**filter_by_args)

    # noinspection PyMethodMayBeStatic
    def modify_results(self, results: list) -> list:
        return results

    def __init__(self):
        if not getattr(self, '__fields__', None):
            raise ValueError('you should define dataclass fields when using this mixin')

    def __new__(cls, *args, **kwargs):
        """require subclasses to be dataclasses"""
        if not dataclasses.is_dataclass(cls):
            raise ValueError(f'{cls!r} must be marked as a @dataclass')
        if not kwargs:
            raise ValueError(f'No dataclass fields defined on {cls!r}')
        return super().__new__(cls)
