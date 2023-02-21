from pydantic import conint
from sqlalchemy import Select, func


class Pagination:
    def __init__(self, start: conint(ge=0) = 0, count: conint(ge=1) = 200) -> None:
        self.start = start
        self.requested_count = count
        self._count = None
        self._total_count = None

    def paginate_query(self, query: Select):
        self._total_count = query.count()
        return query.offset(self.start).limit(self.count)

    def fetch_paginated(self, session, query: Select):
        self._total_count = session.scalar(
            query.with_only_columns(func.count(), maintain_column_froms=True)
        )
        results = session.scalars(query).fetchall()
        self._count = len(results)
        return results

    @property
    def count(self):
        return self._count

    @property
    def total(self):
        return self._total_count
