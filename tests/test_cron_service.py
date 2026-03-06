import pytest

from nanobot.cron.service import CronService
from nanobot.cron.types import CronSchedule


def test_add_job_rejects_unknown_timezone(tmp_path) -> None:
    service = CronService(tmp_path / "cron" / "jobs.json")

    with pytest.raises(ValueError, match="unknown timezone 'America/Vancovuer'"):
        service.add_job(
            name="tz typo",
            schedule=CronSchedule(kind="cron", expr="0 9 * * *", tz="America/Vancovuer"),
            message="hello",
        )

    assert service.list_jobs(include_disabled=True) == []


def test_add_job_accepts_valid_timezone(tmp_path) -> None:
    service = CronService(tmp_path / "cron" / "jobs.json")

    job = service.add_job(
        name="tz ok",
        schedule=CronSchedule(kind="cron", expr="0 9 * * *", tz="America/Vancouver"),
        message="hello",
    )

    assert job.schedule.tz == "America/Vancouver"
    assert job.state.next_run_at_ms is not None


def test_add_job_default_kind_is_agent_turn(tmp_path) -> None:
    """Test that default kind is 'agent_turn'."""
    service = CronService(tmp_path / "cron" / "jobs.json")

    job = service.add_job(
        name="default kind",
        schedule=CronSchedule(kind="every", every_ms=60000),
        message="hello",
    )

    assert job.payload.kind == "agent_turn"


def test_add_job_with_kind_system_event(tmp_path) -> None:
    """Test that kind='system_event' creates a reminder job."""
    service = CronService(tmp_path / "cron" / "jobs.json")

    job = service.add_job(
        name="reminder",
        schedule=CronSchedule(kind="every", every_ms=60000),
        message="drink water",
        kind="system_event",
    )

    assert job.payload.kind == "system_event"
    assert job.payload.message == "drink water"


def test_add_job_with_kind_agent_turn(tmp_path) -> None:
    """Test that kind='agent_turn' creates a task job."""
    service = CronService(tmp_path / "cron" / "jobs.json")

    job = service.add_job(
        name="task",
        schedule=CronSchedule(kind="every", every_ms=60000),
        message="check email",
        kind="agent_turn",
    )

    assert job.payload.kind == "agent_turn"
    assert job.payload.message == "check email"


def test_job_persistence_with_kind(tmp_path) -> None:
    """Test that kind is persisted and loaded correctly."""
    store_path = tmp_path / "cron" / "jobs.json"

    # Create service and add job
    service1 = CronService(store_path)
    job1 = service1.add_job(
        name="persistent reminder",
        schedule=CronSchedule(kind="at", at_ms=1893456000000),
        message="meeting",
        kind="system_event",
        delete_after_run=True,
    )
    assert job1.payload.kind == "system_event"

    # Create new service instance and load jobs
    service2 = CronService(store_path)
    jobs = service2.list_jobs(include_disabled=True)

    assert len(jobs) == 1
    assert jobs[0].payload.kind == "system_event"
    assert jobs[0].payload.message == "meeting"
