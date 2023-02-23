import abc
import dataclasses
from typing import Any

import sqlalchemy


def exclude_none(d: list[tuple[str, Any]]) -> dict:
    """
    for use as dict_factory argument to dataclasses.asdict()
    filters out "private" keys beginning with "_"
    filters out values equal to None
    """
    return {k: v for (k, v) in d if v is not None and k[0] != "_"}


class Filter(metaclass=abc.ABCMeta):
    def __init__(self, /, **kwargs):
        """
        The Filter is where you can add query params for filtering lists of Resources. You should
        subclass the Filter class and implement the modify_query function to suit your needs.

        Mixins and dataclasses can make this a lot easier on you!

        To prevent having to write your own __init__ function boilerplate, use the DataclassFilterMixin as follows:

        >>> @dataclasses.dataclass
        ... class UserFilter(DataclassFilterMixin, Filter):
        ...     first_name: str = Query(None)  # api users will be able to filter the user list by first name

        SupineRouter uses the Filter.__init__ function as a sub-dependency, so your type hints on that function are
        passed through to FastAPI as Dependencies

        SupineRouter calls modify_query before executing the query. The incoming query selects all results,
        so modify_query should modify and return it with filters reflecting the various attributes set on the Filter
        during __init__
        """

    @abc.abstractmethod
    def modify_query(self, query: sqlalchemy.Select) -> sqlalchemy.Select:
        return query


class DataclassFilterMixin:
    """
    This mixin makes filtering your API queries very simple. Specify this Mixin BEFORE the Filter class in your
    class's inheritance.

    example for a 'user' Resource:

    >>> @dataclasses.dataclass
    ... class UserFilter(DataclassFilterMixin, Filter):  # Mixin BEFORE Filter
    ...     first_name: str = Query(None)  # api users will be able to filter the user list by first name

    By default, this mixin checks every attribute for equality to the orm instances. If you need to implement,
    for example, range or wildcard checks, you will need to override modify_query.

    modify_query() will be called by SupineRouter prior to executing the select()
    """

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

    def __init__(self):
        if not getattr(self, "__fields__", None):
            raise ValueError("you should define dataclass fields when using this mixin")

    def __new__(cls, *args, **kwargs):
        """require subclasses to be dataclasses"""
        if not dataclasses.is_dataclass(cls):
            raise ValueError(f"{cls!r} must be marked as a @dataclass")
        # noinspection PyUnresolvedReferences,PyProtectedMember
        if not getattr(cls, dataclasses._FIELDS):
            raise ValueError(f"No dataclass fields defined on {cls!r}")
        return super().__new__(cls, *args)
