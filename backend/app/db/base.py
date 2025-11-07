from sqlalchemy.orm import declarative_base
from importlib import import_module

Base = declarative_base()

# Import model modules so their tables register with Base.metadata.
# We try both singular and plural variants where naming may differ.
# These imports must come before any Base.metadata.create_all(...)
_model_modules = [
    "metric_daily",
    "forecast_results",
    "sources",   # try plural first
    "source",    # then singular
    "clean_events",
    "raw_events",
    "user",
]

for _mod in _model_modules:
    try:
        import_module(f"app.models.{_mod}")
    except ModuleNotFoundError:
        # It's okay if one variant doesn't exist (e.g., sources vs source)
        continue
