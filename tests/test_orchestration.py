"""Tests for Dagster orchestration asset definitions and pipeline DAG."""

from orchestration.definitions import defs


def test_dagster_definitions_compilation():
    """Test that all Dagster Software-Defined Assets, jobs, and schedules compile without errors."""
    assert defs is not None

    # Verify assets loaded
    asset_keys = {str(k.path[-1]) for k in defs.resolve_asset_graph().get_all_asset_keys()}
    expected_assets = {
        "raw_simplify_postings",
        "raw_custom_ats_postings",
        "upserted_postings_db",
        "telegram_alerts_dispatched",
    }
    assert expected_assets.issubset(asset_keys)

    # Verify schedules exist
    assert len(defs.schedules) >= 1
