"""Dagster Job definitions."""

from dagster import AssetSelection, define_asset_job

realtime_pipeline_job = define_asset_job(
    name="realtime_ingestion_job",
    selection=AssetSelection.all(),
    description="End-to-end ingestion from SimplifyJobs + Greenhouse, diffing in PostgreSQL, and Telegram alert dispatch.",
)
