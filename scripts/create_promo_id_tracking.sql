-- PAM.Promo_ID_Tracking — permanent ledger of all allocated promo codes and group IDs.
-- One row per promo, inserted at creation time, NEVER deleted (even if the promo is removed
-- from the live table). This ensures allocated IDs are never reused.
--
-- Run once to create. Backfill existing promos via scripts/backfill_promo_id_tracking.py.

IF NOT EXISTS (
    SELECT 1 FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_SCHEMA = 'PAM' AND TABLE_NAME = 'Promo_ID_Tracking'
)
BEGIN
    CREATE TABLE PAM.Promo_ID_Tracking (
        code                        VARCHAR(50)   NOT NULL PRIMARY KEY,
        orbit_id                    VARCHAR(50)   NULL,
        sku_group_id                VARCHAR(50)   NULL,
        trade_in_group_id           VARCHAR(50)   NULL,
        bolt_trade_in_grp_id        VARCHAR(50)   NULL,
        port_in_group_id            VARCHAR(50)   NULL,
        segment_group_id            VARCHAR(50)   NULL,
        device_status_group_id      VARCHAR(50)   NULL,
        mk_mdl_grp_tier_1           VARCHAR(50)   NULL,
        mk_mdl_grp_tier_2           VARCHAR(50)   NULL,
        mk_mdl_grp_tier_3           VARCHAR(50)   NULL,
        mk_mdl_grp_tier_4           VARCHAR(50)   NULL,
        tiered_grp_id               VARCHAR(50)   NULL,
        promo_tier_1_sku_group_id   VARCHAR(50)   NULL,
        promo_tier_2_sku_group_id   VARCHAR(50)   NULL,
        promo_tier_3_sku_group_id   VARCHAR(50)   NULL,
        created_at                  DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
        created_by                  VARCHAR(200)  NULL
    );

    CREATE NONCLUSTERED INDEX IX_Tracking_sku
        ON PAM.Promo_ID_Tracking (sku_group_id)
        WHERE sku_group_id IS NOT NULL;

    CREATE NONCLUSTERED INDEX IX_Tracking_trade_in
        ON PAM.Promo_ID_Tracking (trade_in_group_id)
        WHERE trade_in_group_id IS NOT NULL;
END;
