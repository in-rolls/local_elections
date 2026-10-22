import io
import json
import logging

from local_elections.common import runlog


def reset_logger():
    logger = logging.getLogger(runlog.LOGGER_NAME)
    logger.handlers.clear()
    logger.propagate = True


def test_json_log_has_stable_event_and_context(monkeypatch):
    reset_logger()
    monkeypatch.setenv(runlog.LOG_FORMAT_ENV, "json")
    stream = io.StringIO()
    runlog.configure(stream)

    logger = logging.getLogger("local_elections.test")
    logger.info(
        "downloaded source",
        extra={"event": "source_fetched", "state": "Assam", "bytes": 42},
    )

    record = json.loads(stream.getvalue())
    assert record["event"] == "source_fetched"
    assert record["state"] == "Assam"
    assert record["bytes"] == 42
    assert record["message"] == "downloaded source"
    assert record["timestamp"].endswith("+00:00")
    reset_logger()


def test_command_decorator_logs_lifecycle(monkeypatch):
    reset_logger()
    monkeypatch.setenv(runlog.LOG_FORMAT_ENV, "json")
    stream = io.StringIO()
    runlog.configure(stream)

    @runlog.command("validate", state="Goa")
    def sample():
        return 0

    assert sample() == 0
    records = [json.loads(line) for line in stream.getvalue().splitlines()]
    assert [record["event"] for record in records] == [
        "command_started",
        "command_completed",
    ]
    assert all(record["phase"] == "validate" for record in records)
    assert all(record["state"] == "Goa" for record in records)
    reset_logger()


def test_nonzero_result_is_a_structured_failure(monkeypatch):
    reset_logger()
    monkeypatch.setenv(runlog.LOG_FORMAT_ENV, "json")
    stream = io.StringIO()
    runlog.configure(stream)

    @runlog.command("validate", state="Assam")
    def sample():
        return 1

    assert sample() == 1
    records = [json.loads(line) for line in stream.getvalue().splitlines()]
    assert records[-1]["event"] == "command_failed"
    assert records[-1]["exit_code"] == 1
    assert records[-1]["level"] == "error"
    reset_logger()
