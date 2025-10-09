# Simple import smoke test to execute module-level code in app/db.py
def test_db_module_imports():
    import importlib
    m = importlib.import_module("app.db")
    # just assert the module imported and has something (any attribute)
    assert hasattr(m, "__file__")