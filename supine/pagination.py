from pydantic import conint
from sqlalchemy.sql import func, Select


class Pagination:
    def __init__(self, start: conint(ge=0) = 0, count: conint(ge=1) = 200) -> None:
        self.start = start
        self.requested_count = count
        self._count = None
        self._total_count = None

    def fetch_paginated(self, session, query: Select):
        self._total_count = self._query_count(query, session)
        results = self._query_results(query, session)
        self._count = len(results)
        return results

    @staticmethod
    def _query_results(query, session):
        return session.scalars(query).fetchall()

    @staticmethod
    def _query_count(query, session):
        return session.scalar(
            query.with_only_columns(func.count(), maintain_column_froms=True)
        )

    @property
    def count(self):
        return self._count

    @property
    def total(self):
        return self._total_count
