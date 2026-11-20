from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.api import reanalyze
from app.models import Job


@pytest.mark.parametrize("status", ["ANALYZED", "PARTIAL"])
def test_reanalysis_queues_both_completed_statuses(status):
    message = SimpleNamespace(status=status)
    session = Mock()
    session.get.return_value = message
    assert reanalyze("message-id", SimpleNamespace(id="analyst-id"), session) == {"queued": True}
    assert message.status == "PENDING"
    jobs = [call.args[0] for call in session.add.call_args_list if isinstance(call.args[0], Job)]
    assert len(jobs) == 1
    assert jobs[0].payload == {"message_id": "message-id"}
    session.commit.assert_called_once()