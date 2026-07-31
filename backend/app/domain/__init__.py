"""Pure domain logic.

**Layer rule (PLAN.md §7): nothing in this package may import FastAPI, sqlite3,
or anything from `app.repository`.** Give these functions plain data, get plain
data back.

That constraint is what makes `tests/test_delivery.py` and `tests/test_pricing.py`
need no fixtures, no test client and no database — and fast tests are the tests
that actually get written inside a 40-minute budget.
"""
