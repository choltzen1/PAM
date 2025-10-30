import os, urllib.parse
from sqlalchemy import create_engine

_research_engine = None

def get_research_engine():
    global _research_engine
    if _research_engine is not None:
        return _research_engine
    raw = os.getenv('RESEARCH_DB_CONNECTION')
    if not raw:
        # fallback to PAM connection pieces if dedicated string absent
        driver = os.getenv('PAM_DB_DRIVER','ODBC Driver 17 for SQL Server')
        server = os.getenv('PAM_DB_SERVER','localhost')
        database = os.getenv('PAM_DB_DATABASE','PromoQuality')
        user = os.getenv('PAM_DB_USERNAME','')
        pwd = os.getenv('PAM_DB_PASSWORD','')
        encrypt = os.getenv('PAM_DB_ENCRYPT','no')
        trust = os.getenv('PAM_DB_TRUST_CERT','yes')
        timeout = os.getenv('PAM_DB_LOGIN_TIMEOUT','15')
        raw = f'DRIVER={{{driver}}};SERVER={server};DATABASE={database};UID={user};PWD={pwd};Encrypt={encrypt};TrustServerCertificate={trust};LoginTimeout={timeout}'
    params = urllib.parse.quote_plus(raw)
    pool_size = int(os.getenv('RESEARCH_DB_POOL_SIZE','8'))
    max_overflow = int(os.getenv('RESEARCH_DB_MAX_OVERFLOW','16'))
    pool_timeout = int(os.getenv('RESEARCH_DB_POOL_TIMEOUT','15'))
    _research_engine = create_engine(
        f'mssql+pyodbc:///?odbc_connect={params}',
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=pool_timeout,
        pool_pre_ping=True
    )
    return _research_engine
