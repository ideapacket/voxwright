from __future__ import annotations

import pytest

from voxwright.barge_artifacts import (
    BargeCheckpoint,
    checkpoint_from_dict,
    checkpoint_manager,
    checkpoint_to_dict,
    decode_barge_checkpoint,
    encode_barge_checkpoint,
    resume_manager,
)
from voxwright.barge_in import (
    BargePolicy,
    InFlightOperation,
    Interrupt,
    InterruptManager,
    OperationState,
)
from voxwright.identifiers import Identifier


def running_operation() -> InFlightOperation:
    return InFlightOperation(
        Identifier("send-1"),
        Identifier("messages.send"),
        {"text": "synthetic hello"},
        False,
    ).start()


def test_active_interrupt_manager_checkpoints_and_resumes_without_aliasing() -> None:
    manager = InterruptManager(running_operation(), BargePolicy.QUEUE)
    first = Interrupt(4, 0, Identifier("interrupt-1"), "stop")
    manager.interrupt(first)
    checkpoint = checkpoint_manager(manager)
    manager.queued.clear()
    restored = resume_manager(checkpoint)
    assert restored.operation == checkpoint.operation
    assert restored.queued == [first]
    assert restored.finish_and_drain() == (first,)
    assert restored.operation.state is OperationState.COMPLETED


def test_checkpoint_requires_a_live_operation_and_compatible_queue() -> None:
    with pytest.raises(ValueError, match="must be running"):
        BargeCheckpoint(running_operation().complete(), BargePolicy.QUEUE)
    item = Interrupt(1, 0, Identifier("interrupt-1"), "new request")
    with pytest.raises(ValueError, match="only queue policy"):
        BargeCheckpoint(running_operation(), BargePolicy.CANCEL, (item,))


def test_checkpoint_rejects_nondeterministic_interrupt_order() -> None:
    later = Interrupt(9, 0, Identifier("interrupt-2"), "later")
    earlier = Interrupt(3, 0, Identifier("interrupt-1"), "earlier")
    with pytest.raises(ValueError, match="deterministic order"):
        BargeCheckpoint(running_operation(), BargePolicy.QUEUE, (later, earlier))


def test_barge_checkpoint_codec_restores_operation_policy_and_queue() -> None:
    manager = InterruptManager(running_operation(), BargePolicy.QUEUE)
    manager.interrupt(Interrupt(2, 0, Identifier("interrupt-1"), "pause"))
    checkpoint = checkpoint_manager(manager)
    restored = checkpoint_from_dict(checkpoint_to_dict(checkpoint))
    assert restored == checkpoint
    encoded = encode_barge_checkpoint(checkpoint)
    assert decode_barge_checkpoint(encoded) == checkpoint
    assert encode_barge_checkpoint(decode_barge_checkpoint(encoded)) == encoded


def test_nonqueue_active_checkpoint_roundtrips_with_an_empty_queue() -> None:
    checkpoint = BargeCheckpoint(running_operation(), BargePolicy.FINISH_IF_IDEMPOTENT)
    assert decode_barge_checkpoint(encode_barge_checkpoint(checkpoint)) == checkpoint
