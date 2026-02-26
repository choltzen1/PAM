import os
from typing import Dict

try:
    import oracledb
except Exception:  # pragma: no cover - handled at runtime
    oracledb = None


def _required_env(name: str) -> str:
    value = os.getenv(name, '').strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _build_dsn() -> str:
    explicit = os.getenv('ORACLE_DSN', '').strip()
    if explicit:
        return explicit

    host = _required_env('ORACLE_HOST')
    service = _required_env('ORACLE_SERVICE')
    port = int(os.getenv('ORACLE_PORT', '1521'))
    return oracledb.makedsn(host, port, service_name=service)


def _init_oracle_client_if_configured() -> None:
    if oracledb is None:
        return

    lib_dir = os.getenv('ORACLE_CLIENT_LIB_DIR', '').strip()
    wallet_dir = os.getenv('ORACLE_WALLET_DIR', '').strip()
    thick_required = os.getenv('ORACLE_THICK_MODE', '').strip().lower() in ('1', 'true', 'yes')

    if not lib_dir:
        if thick_required:
            raise RuntimeError("ORACLE_THICK_MODE is enabled but ORACLE_CLIENT_LIB_DIR is not set.")
        return

    if not oracledb.is_thin_mode():
        return

    kwargs = {'lib_dir': lib_dir}
    if wallet_dir:
        kwargs['config_dir'] = wallet_dir
    oracledb.init_oracle_client(**kwargs)


def execute_oracle_block(sql_text: str) -> Dict[str, str]:
    if oracledb is None:
        raise RuntimeError("oracledb is not installed. Add it to requirements and install dependencies.")

    _init_oracle_client_if_configured()

    user = _required_env('ORACLE_USER')
    password = _required_env('ORACLE_PASSWORD')
    dsn = _build_dsn()

    conn = oracledb.connect(user=user, password=password, dsn=dsn)
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql_text)
        conn.commit()
        return {'status': 'success'}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
