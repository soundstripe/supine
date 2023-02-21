import random
from unittest import mock

from supine.pagination import Pagination


def test_fetch_paginated_updates_total():
    """Given a pagination object, when .fetch_paginated is called, ensure .total is updated accordingly"""
    p = Pagination(start=0, count=5)
    with mock.patch.object(p, '_query_count', return_value=500):
        with mock.patch.object(p, '_query_results'):
            p.fetch_paginated(mock.Mock(), mock.Mock())

    assert p.total == 500


def test_fetch_paginated_updates_count():
    """Given a pagination object, when .fetch_paginated is called, ensure .count is updated accordingly"""
    mock_data = [random.randint(0, 10) for _ in range(200)]

    p = Pagination(start=0, count=5)
    with mock.patch.object(p, '_query_count', return_value=500):
        with mock.patch.object(p, '_query_results', return_value=mock_data):
            p.fetch_paginated(mock.Mock(), mock.Mock())

    assert p.total == 500
