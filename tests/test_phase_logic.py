import datetime
from data.storage import PromoDataManager

class PhaseTestHarness:
    def __init__(self):
        self.extras_store = {}
    def get_promo_extras(self, code):
        return self.extras_store.get(code, {})
    def upsert_promo_extras(self, code, extras, user):
        cur = self.extras_store.get(code, {})
        cur.update(extras)
        self.extras_store[code] = cur

def build_manager(monkeypatch):
    mgr = PromoDataManager()
    harness = PhaseTestHarness()
    monkeypatch.setattr(mgr.db_manager, 'get_promo_extras', harness.get_promo_extras)
    monkeypatch.setattr(mgr.db_manager, 'upsert_promo_extras', harness.upsert_promo_extras)
    return mgr

def test_phase_build_before_start(monkeypatch):
    mgr = build_manager(monkeypatch)
    today = datetime.datetime(2025,1,10)
    phase = mgr._compute_phase('2025-01-12','2025-01-20', today)
    assert phase == 'Build'

def test_phase_launched_on_start_day(monkeypatch):
    mgr = build_manager(monkeypatch)
    today = datetime.datetime(2025,1,10)
    phase = mgr._compute_phase('2025-01-10','2025-01-20', today)
    assert phase == 'Launched'

def test_phase_launched_on_end_day(monkeypatch):
    mgr = build_manager(monkeypatch)
    today = datetime.datetime(2025,1,20)
    phase = mgr._compute_phase('2025-01-10','2025-01-20', today)
    assert phase == 'Launched'

def test_phase_expired_after_end(monkeypatch):
    mgr = build_manager(monkeypatch)
    today = datetime.datetime(2025,1,21)
    phase = mgr._compute_phase('2025-01-10','2025-01-20', today)
    assert phase == 'Expired'

def test_phase_missing_start_future_end(monkeypatch):
    mgr = build_manager(monkeypatch)
    today = datetime.datetime(2025,1,10)
    phase = mgr._compute_phase(None,'2025-01-20', today)
    assert phase == 'Build'

def test_phase_missing_start_past_end(monkeypatch):
    mgr = build_manager(monkeypatch)
    today = datetime.datetime(2025,1,25)
    phase = mgr._compute_phase(None,'2025-01-20', today)
    assert phase == 'Expired'
