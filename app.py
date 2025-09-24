from factory import create_app, data_manager as factory_data_manager  # import alias

app = create_app()
# After factory create_app, re-import the factory module variable to ensure it's initialized
from factory import data_manager as _dm  # type: ignore
data_manager = _dm  # expose for tests
if data_manager is None:  # defensive assertion during test/dev
    try:
        # Attempt lazy init if somehow missed
        from data.hybrid_storage import HybridPromoDataManager as PromoDataManager
        data_manager = PromoDataManager()
    except Exception:
        pass

"""Entrypoint module.
The root route now lives in the core blueprint (`core.home`).
"""

if __name__ == "__main__":
    import argparse
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Run the PAM application')
    parser.add_argument('--port', type=int, default=5006, help='Port to run the application on')
    args = parser.parse_args()
    
    # Run the app on the specified port
    app.run(debug=True, port=args.port)
