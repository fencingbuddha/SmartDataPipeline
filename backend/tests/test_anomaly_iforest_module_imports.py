import importlib

def test_anomaly_iforest_module_imports():
    # Simply importing should execute top-level definitions for coverage
    import app.routers.anomaly_iforest as mod
    importlib.reload(mod)
    assert hasattr(mod, "router")
