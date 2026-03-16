import os
import sys
import struct
import logging
import pyodbc
import msal
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Logging — writes to console AND ssms_job.log in the same directory
# ---------------------------------------------------------------------------
log = logging.getLogger('ssms_job')
log.setLevel(logging.DEBUG)

_fmt = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')

_ch = logging.StreamHandler(sys.stdout)
_ch.setFormatter(_fmt)
log.addHandler(_ch)

_fh = logging.FileHandler(os.path.join(os.path.dirname(__file__), 'ssms_job.log'), encoding='utf-8')
_fh.setFormatter(_fmt)
log.addHandler(_fh)

# ---------------------------------------------------------------------------

SQLSERVER_CONN_STR = os.getenv("SQLSERVER_CONN_STR")

# Dataverse TDS connection parameters (service principal token auth)
DATAVERSE_SERVER   = os.getenv("DATAVERSE_SERVER", "org830c4186.crm.dynamics.com")
DATAVERSE_DATABASE = os.getenv("DATAVERSE_DATABASE", "org830c4186")
FABRIC_CLIENT_ID     = os.getenv("FABRIC_CLIENT_ID")
FABRIC_CLIENT_SECRET = os.getenv("FABRIC_CLIENT_SECRET")
FABRIC_TENANT_ID     = os.getenv("FABRIC_TENANT_ID")


def _get_dataverse_token() -> bytes:
    """Acquire an AAD access token for the Dataverse org and return it
    as the raw byte structure expected by SQL_COPT_SS_ACCESS_TOKEN."""
    resource = f"https://{DATAVERSE_SERVER}"
    authority = f"https://login.microsoftonline.com/{FABRIC_TENANT_ID}"
    app = msal.ConfidentialClientApplication(
        FABRIC_CLIENT_ID,
        authority=authority,
        client_credential=FABRIC_CLIENT_SECRET,
    )
    result = app.acquire_token_for_client(scopes=[f"{resource}/.default"])
    if "access_token" not in result:
        raise RuntimeError(f"Token acquisition failed: {result.get('error_description', result)}")
    token_bytes = result["access_token"].encode("utf-16-le")
    return struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)


def _dataverse_connect() -> pyodbc.Connection:
    """Open a pyodbc connection to Dataverse TDS using an injected AAD token."""
    SQL_COPT_SS_ACCESS_TOKEN = 1256
    conn_str = (
        f"DRIVER={{ODBC Driver 18 for SQL Server}};"
        f"SERVER={DATAVERSE_SERVER},5558;"
        f"DATABASE={DATAVERSE_DATABASE};"
        f"Encrypt=yes;TrustServerCertificate=no;"
    )
    token_struct = _get_dataverse_token()
    return pyodbc.connect(conn_str, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct})

QUERY = """
SELECT
    c.crffc_promocodeid as Code,
    b.cat_teammembername as Owner,
    a.cat_billname as bill_facing_name,
    c.crffc_clarityid as orbit_id,
    a.cat_initiativename as description,
    a.cat_productnotes as promo_notes,
    c.crffc_promopercentagediscount as discount,
    c.crffc_promoamt as amount,
    CASE WHEN a.cat_desiredexecutionname = 'RDC'
         THEN CONVERT(varchar(50), c.crffc_nseipdropdevice)
         ELSE CONVERT(varchar(50), c.crffc_nseipdrop)
    END AS nseip_drop,
    c.crffc_dcdwebcart as dcd_web_cart,
    CASE WHEN a.cat_desiredexecutionname = 'RDC'
         THEN CONVERT(varchar(50), c.crffc_producttypedevice)
         ELSE CONVERT(varchar(50), c.crffc_producttype)
    END AS product_type,
    c.crffc_bogo as bogo,
    CASE WHEN a.cat_desiredexecutionname = 'RDC'
         THEN CONVERT(varchar(50), c.crffc_fpddisplaypromodev)
         ELSE CONVERT(varchar(50), c.crffc_fpddisplaypromo)
    END AS fpd_display_promo,
    c.crffc_onmenu as on_menu,
    c.crffc_marketgroup as market_group,
    c.crffc_storegroup as store_group,
    c.crffc_promostartdate as promo_start_date,
    c.crffc_promoenddate as promo_end_date,
    NULL as comm_end_date,
    c.crffc_promoduration as promo_duration,
    c.crffc_delaytime as delay_time,
    c.crffc_applicationgraceperiod as application_grace_period,
    c.crffc_devicesalestypebutton as device_sales_type,
    a.cat_addalinetypesname as activation_type,
    a.cat_activeservicerequiredname as active_line_required,
    CASE WHEN a.cat_desiredexecutionname = 'RDC'
         THEN CONVERT(varchar(50), c.crffc_maintainsocdev)
         ELSE CONVERT(varchar(50), c.crffc_maintainsoc)
    END AS maintain_soc,
    CASE WHEN a.cat_desiredexecutionname = 'RDC'
         THEN CONVERT(varchar(50), c.crffc_maintainactivelinedev)
         ELSE CONVERT(varchar(50), c.crffc_maintainactiveline)
    END AS crffc_maintainactivelinedev,
    c.crffc_limitperban as limit_per_ban,
    CASE WHEN a.cat_desiredexecutionname = 'RDC'
         THEN CONVERT(varchar(50), c.crffc_socgroupdev)
         ELSE CONVERT(varchar(50), c.crffc_socgroup)
    END AS soc_grouping,
    CASE WHEN a.cat_desiredexecutionname = 'RDC'
         THEN CONVERT(varchar(50), c.crffc_accounttypedev)
         ELSE CONVERT(varchar(50), c.crffc_accounttype)
    END AS account_type,
    CASE WHEN a.cat_desiredexecutionname = 'RDC'
         THEN CONVERT(varchar(50), c.crffc_salesapplicationdev)
         ELSE CONVERT(varchar(50), c.crffc_salesapplications)
    END AS sales_application,
    RIGHT(CONVERT(varchar(50), c.crffc_userstory), 5) as operator_id,
    c.crffc_skugroupid as sku_group_id,
    c.crffc_devicestatusgrp as device_status_group_id,
    c.crffc_clawback as clawback_indicator,
    a.cat_acceptbrokendevicesname as Broken_Trade,
    a.cat_anticipatedvolumetakeratestotal as Anticipated_volume_take_rates_total,
    a.cat_desiredexecutionname as Desired_Execution,
    a.cat_phasename as Status,
    a.crffc_eligibletradeindevices,
    a.cat_lobchannelhorizontalname,
    a.cat_additionaleligibilityrequirementsname,
    a.cat_eligibledevices,
    a.cat_channelsname,
    a.cat_description,
	a.cat_initiativename
FROM dbo.cat_gtmentry a
INNER JOIN dbo.cat_projectteamroles b
    ON a.cat_gtmentryid = b.cat_gtmentry
   AND b.cat_roletypename = 'Product Lead'
LEFT JOIN dbo.crffc_promotions c
    ON a.cat_gtmentryid = c.crffc_gtmentryrecord
WHERE CAST(a.createdon as date) >= '2024-01-01'
  AND a.cat_desiredexecutionname IN ('RDC','Rebate','SPE')
  AND a.cat_lobchannelhorizontalname IN ('Consumer Markets Postpaid','Business');
"""

INSERT_SQL = """
INSERT INTO PAM.OrbitPromoExtract_STG
(
    Code, Owner, bill_facing_name, orbit_id, description, promo_notes, discount, amount,
    nseip_drop, dcd_web_cart, product_type, bogo, fpd_display_promo, on_menu,
    market_group, store_group, promo_start_date, promo_end_date, comm_end_date,
    promo_duration, delay_time, application_grace_period, device_sales_type,
    activation_type, active_line_required, maintain_soc, crffc_maintainactivelinedev,
    limit_per_ban, soc_grouping, account_type, sales_application, operator_id,
    sku_group_id, device_status_group_id, clawback_indicator, Broken_Trade,
    Anticipated_volume_take_rates_total, Desired_Execution, Status,
    crffc_eligibletradeindevices, cat_lobchannelhorizontalname,
    cat_additionaleligibilityrequirementsname, cat_eligibledevices,
    cat_channelsname, cat_description
)
VALUES
(
    ?, ?, ?, ?, ?, ?, ?, ?,
    ?, ?, ?, ?, ?, ?,
    ?, ?, ?, ?, ?,
    ?, ?, ?, ?,
    ?, ?, ?, ?,
    ?, ?, ?, ?, ?,
    ?, ?, ?, ?,
    ?, ?, ?,
    ?, ?, ?, ?,
    ?, ?
)
"""


def fetch_dataverse_rows():
    log.info("Connecting to Dataverse TDS (%s)...", DATAVERSE_SERVER)
    try:
        with _dataverse_connect() as conn:
            log.info("Connected. Executing query...")
            cur = conn.cursor()
            cur.execute(QUERY)
            columns = [col[0] for col in cur.description]
            rows = cur.fetchall()
            log.info("Retrieved %d rows from Dataverse", len(rows))
            return columns, rows
    except pyodbc.Error as e:
        log.error("Dataverse connection failed: %s", e)
        raise


def load_sql(rows):
    log.info("Connecting to target SQL Server...")
    log.debug("SQLSERVER: %s", SQLSERVER_CONN_STR.split(';')[1] if SQLSERVER_CONN_STR else 'NOT SET')
    try:
        with pyodbc.connect(SQLSERVER_CONN_STR) as conn:
            cur = conn.cursor()

            log.info("Truncating staging table...")
            cur.execute("TRUNCATE TABLE PAM.OrbitPromoExtract_STG;")
            conn.commit()

            if rows:
                log.info("Inserting %d rows into staging...", len(rows))
                cur.fast_executemany = True
                cur.executemany(INSERT_SQL, rows)
                conn.commit()
                log.info("Insert complete.")

            log.info("Running MERGE proc...")
            cur.execute("EXEC dbo.usp_Merge_OrbitPromoExtract;")
            conn.commit()
            log.info("Load complete.")
    except pyodbc.Error as e:
        log.error("SQL Server operation failed: %s", e)
        raise


def main():
    if not all([FABRIC_CLIENT_ID, FABRIC_CLIENT_SECRET, FABRIC_TENANT_ID]):
        raise RuntimeError("Missing one or more env vars: FABRIC_CLIENT_ID, FABRIC_CLIENT_SECRET, FABRIC_TENANT_ID")
    if not SQLSERVER_CONN_STR:
        raise RuntimeError("Missing environment variable: SQLSERVER_CONN_STR")

    _, rows = fetch_dataverse_rows()
    load_sql(rows)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        log.exception("Job failed: %s", exc)
        sys.exit(1)
