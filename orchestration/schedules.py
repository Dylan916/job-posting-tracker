"""Dagster Schedule definitions for automated recurring pipeline execution."""

from dagster import ScheduleDefinition
from orchestration.jobs import realtime_pipeline_job

every_15_minutes_schedule = ScheduleDefinition(
    job=realtime_pipeline_job,
    cron_schedule="*/15 * * * *",
    name="every_15_minutes_poller",
    description="Polls all ATS sources and GitHub repositories every 15 minutes for immediate alerts.",
)

hourly_schedule = ScheduleDefinition(
    job=realtime_pipeline_job,
    cron_schedule="0 * * * *",
    name="hourly_poller",
    description="Runs full pipeline ingestion once per hour.",
)
