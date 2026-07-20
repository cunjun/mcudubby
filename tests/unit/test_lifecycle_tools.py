from McuBuddy.session import SessionState
from McuBuddy.tools.lifecycle import disconnect_all
from McuBuddy.tools.logs import disconnect_log
from McuBuddy.tools.probe import disconnect_probe


class _FakeDisconnectable:
    def __init__(self, summary: str) -> None:
        self.summary = summary
        self.called = False

    def disconnect(self) -> dict:
        self.called = True
        return {"status": "ok", "summary": self.summary}


def test_probe_disconnect_calls_backend() -> None:
    session = SessionState()
    session.probe = _FakeDisconnectable("probe disconnected")

    result = disconnect_probe(session)

    assert result["status"] == "ok"
    assert session.probe.called is True


def test_log_disconnect_calls_backend() -> None:
    session = SessionState()
    session.log = _FakeDisconnectable("log disconnected")

    result = disconnect_log(session)

    assert result["status"] == "ok"
    assert session.log.called is True


def test_disconnect_all_disconnects_probe_and_log() -> None:
    session = SessionState()
    session.probe = _FakeDisconnectable("probe disconnected")
    session.log = _FakeDisconnectable("log disconnected")

    result = disconnect_all(session)

    assert result["status"] == "ok"
    assert session.probe.called is True
    assert session.log.called is True
    assert "probe" in result["results"]
    assert "log" in result["results"]
