from functools import lru_cache
from typing import Callable

import sqlalchemy
from fastapi import Depends, params
from sqlalchemy.orm import Session, sessionmaker


@lru_cache
def get_engine():
    return sqlalchemy.create_engine("sqlite://")


@lru_cache()
def get_sessionmaker():
    return sessionmaker(get_engine())


def get_session():
    return get_sessionmaker()()
