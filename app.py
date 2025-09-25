from factory import create_app, data_manager as factory_data_manager  # import alias

app = create_app()
# After factory create_app, re-import the factory module variable to ensure it's initialized
from factory import data_manager as _dm  # type: ignore
data_manager = _dm  # expose for tests
if data_manager is None:  # defensive assertion during test/dev
    try:
        from data.storage import PromoDataManager
        data_manager = PromoDataManager()
    except Exception:
        pass

"""Entrypoint module.
The root route now lives in the core blueprint (`core.home`).
"""

if __name__ == "__main__":
    app.run(debug=True)
