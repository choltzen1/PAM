import data.version_history as vh


class DummyResult:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class DummyConn:
    def __init__(self, recorder, row):
        self.recorder = recorder
        self.row = row

    def execute(self, clause, params=None):
        self.recorder.append({
            'sql': getattr(clause, 'text', str(clause)),
            'params': params or {}
        })
        return DummyResult(self.row)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class DummyEngine:
    def __init__(self, recorder, row=(0,)):
        self.recorder = recorder
        self.row = row

    def connect(self):
        return DummyConn(self.recorder, self.row)

    def begin(self):
        return DummyConn(self.recorder, self.row)


class DummyDB:
    def __init__(self, engine):
        self._engine = engine

    def get_engine(self):
        return self._engine


def test_log_version_event_uses_insert_sql(monkeypatch):
    calls = []
    engine = DummyEngine(calls)
    monkeypatch.setattr(vh, 'DatabaseManager', lambda: DummyDB(engine))

    ok = vh.log_version_event(
        promo_code='UT_ZLAB_0001',
        promo_id='UT_ZLAB_0001',
        event_type='zlab_inserted',
        actor='pytest',
        source='unit_test'
    )

    assert ok is True
    assert calls, 'Expected SQL execute call'
    assert 'INSERT INTO PAM.Version_History' in calls[0]['sql']
    assert calls[0]['params']['promo_code'] == 'UT_ZLAB_0001'
    assert calls[0]['params']['event_type'] == 'zlab_inserted'


def test_get_next_zlab_gen_count_increments_from_count(monkeypatch):
    calls = []
    engine = DummyEngine(calls, row=(2,))
    monkeypatch.setattr(vh, 'DatabaseManager', lambda: DummyDB(engine))

    next_count = vh.get_next_zlab_gen_count('UT_ZLAB_0002')

    assert next_count == 3
    assert calls, 'Expected SQL execute call'
    assert 'SELECT COUNT(1) AS cnt FROM PAM.Version_History' in calls[0]['sql']
    assert calls[0]['params']['promo_code'] == 'UT_ZLAB_0002'
