import pytest
import sqlalchemy as sa

@pytest.fixture
def seeded_metric_daily(db):
    """
    Seed 30 days of historical daily metrics for source 'demo-source' and metric 'value',
    ending on 2025-09-30 so that forecasts begin on 2025-10-01 (as asserted by tests).
    """
    # Ensure the source exists (id 301 is used by other tests as well).
    db.execute(sa.text("INSERT INTO sources (id, name) VALUES (301, 'demo-source') ON CONFLICT DO NOTHING"))

    # Seed a simple pattern of values for September 2025.
    db.execute(sa.text("""
        INSERT INTO metric_daily (metric_date, source_id, metric, value, value_count, value_sum, value_avg) VALUES
            ('2025-09-01', 301, 'value', 5, 1, 5, 5),
            ('2025-09-02', 301, 'value', 6, 1, 6, 6),
            ('2025-09-03', 301, 'value', 7, 1, 7, 7),
            ('2025-09-04', 301, 'value', 8, 1, 8, 8),
            ('2025-09-05', 301, 'value', 9, 1, 9, 9),
            ('2025-09-06', 301, 'value', 5, 1, 5, 5),
            ('2025-09-07', 301, 'value', 6, 1, 6, 6),
            ('2025-09-08', 301, 'value', 7, 1, 7, 7),
            ('2025-09-09', 301, 'value', 8, 1, 8, 8),
            ('2025-09-10', 301, 'value', 9, 1, 9, 9),
            ('2025-09-11', 301, 'value', 5, 1, 5, 5),
            ('2025-09-12', 301, 'value', 6, 1, 6, 6),
            ('2025-09-13', 301, 'value', 7, 1, 7, 7),
            ('2025-09-14', 301, 'value', 8, 1, 8, 8),
            ('2025-09-15', 301, 'value', 9, 1, 9, 9),
            ('2025-09-16', 301, 'value', 5, 1, 5, 5),
            ('2025-09-17', 301, 'value', 6, 1, 6, 6),
            ('2025-09-18', 301, 'value', 7, 1, 7, 7),
            ('2025-09-19', 301, 'value', 8, 1, 8, 8),
            ('2025-09-20', 301, 'value', 9, 1, 9, 9),
            ('2025-09-21', 301, 'value', 5, 1, 5, 5),
            ('2025-09-22', 301, 'value', 6, 1, 6, 6),
            ('2025-09-23', 301, 'value', 7, 1, 7, 7),
            ('2025-09-24', 301, 'value', 8, 1, 8, 8),
            ('2025-09-25', 301, 'value', 9, 1, 9, 9),
            ('2025-09-26', 301, 'value', 5, 1, 5, 5),
            ('2025-09-27', 301, 'value', 6, 1, 6, 6),
            ('2025-09-28', 301, 'value', 7, 1, 7, 7),
            ('2025-09-29', 301, 'value', 8, 1, 8, 8),
            ('2025-09-30', 301, 'value', 9, 1, 9, 9)
    """))
    db.commit()
    yield
