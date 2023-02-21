from functools import lru_cache

import sqlalchemy
from sqlalchemy.orm import Session, sessionmaker


@lru_cache
def get_engine():
    return sqlalchemy.create_engine("sqlite://")


@lru_cache()
def get_sessionmaker():
    return sessionmaker(get_engine())


def get_session():
    return get_sessionmaker()()


def make_session_factory(sessionmaker):
    """
    returns a session factory function suitable as a parameter for Depends()

    rolls back any transaction not committed during your path operation
    """

    def inner() -> Session:
        session = sessionmaker()
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    return inner
