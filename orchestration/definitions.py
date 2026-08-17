"""Dagster unified Definitions root."""

from dagster import Definitions, load_assets_from_modules

from orchestration import assets
from orchestration.jobs import realtime_pipeline_job
from orchestration.schedules import every_15_minutes_schedule, hourly_schedule

all_assets = load_assets_from_modules([assets])

defs = Definitions(
    assets=all_assets,
    jobs=[realtime_pipeline_job],
    schedules=[every_15_minutes_schedule, hourly_schedule],
)
