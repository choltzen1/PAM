def fetch_promo_line(promo_id: str) -> dict:
    # TODO: replace with real DB query when creds arrive
    return {
        "trade_in_grp_id": promo_id,
        "loan_sku_grp": "LSG_TEST",
        "mk_mdl_grp_id": "MMG_TEST",
        "operator_id": 0,
        "application_id": "APP_TEST",
        "dl_service_code": "CPO",
        "tradein_amount": 100,
        "description": f"MOCK PROMO {promo_id}"
    }