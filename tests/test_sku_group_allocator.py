import os
from data.sku_group_tracking import next_sku_group_id_progressive


def test_progressive_allocator_ignores_future_blocks(tmp_path, monkeypatch):
    # Simulate existing IDs: within A block up to AD4 plus an out-of-band UA1 artifact
    existing = {"AA1", "AA2", "AB1", "AD4", "UA1"}
    nxt = next_sku_group_id_progressive(existing)
    # Should advance to AD5, not respect the UA1 leap
    assert nxt == "AD5"


def test_progressive_allocator_rolls_second_letter():
    # Highest within block has digit 9 -> should advance second letter
    existing = {"AA1", "AA9"}
    assert next_sku_group_id_progressive(existing) == "AB1"


def test_progressive_allocator_block_exhaustion():
    # Exhaust A block fully => next start BA1
    # Simplify by including AZ9 explicitly
    existing = {"AZ9"}
    assert next_sku_group_id_progressive(existing) == "BA1"


def test_progressive_allocator_starts_at_A_when_none():
    assert next_sku_group_id_progressive(set()) == "AA1"
