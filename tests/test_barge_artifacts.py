from __future__ import annotations

from pathlib import Path

import pytest

from voxwright.barge_artifacts import (
    BargeCheckpoint,
    barge_checkpoint_digest,
    checkpoint_from_dict,
    checkpoint_manager,
    checkpoint_to_dict,
    decode_barge_checkpoint,
    encode_barge_checkpoint,
    load_barge_checkpoint,
    resume_manager,
    write_barge_checkpoint,
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


def test_barge_decoder_rejects_envelope_operation_and_scalar_drift() -> None:
    value = checkpoint_to_dict(BargeCheckpoint(running_operation(), BargePolicy.QUEUE))
    value["extra"] = None
    with pytest.raises(ValueError, match="exact barge checkpoint fields"):
        checkpoint_from_dict(value)
    value = checkpoint_to_dict(BargeCheckpoint(running_operation(), BargePolicy.QUEUE))
    value["schema_version"] = True
    with pytest.raises(TypeError, match="schema_version: expected integer"):
        checkpoint_from_dict(value)
    value = checkpoint_to_dict(BargeCheckpoint(running_operation(), BargePolicy.QUEUE))
    value["operation"]["idempotent"] = 1  # type: ignore[index]
    with pytest.raises(TypeError, match="idempotent: expected boolean"):
        checkpoint_from_dict(value)
    value = checkpoint_to_dict(BargeCheckpoint(running_operation(), BargePolicy.QUEUE))
    value["policy"] = "invented"
    with pytest.raises(ValueError, match="unknown policy"):
        checkpoint_from_dict(value)


def test_barge_decoder_reapplies_active_queue_invariants() -> None:
    value = checkpoint_to_dict(BargeCheckpoint(running_operation(), BargePolicy.QUEUE))
    value["operation"]["state"] = "completed"  # type: ignore[index]
    with pytest.raises(ValueError, match="operation must be running"):
        checkpoint_from_dict(value)
    later = Interrupt(9, 0, Identifier("interrupt-2"), "later")
    earlier = Interrupt(3, 0, Identifier("interrupt-1"), "earlier")
    checkpoint = BargeCheckpoint(running_operation(), BargePolicy.QUEUE, (earlier, later))
    value = checkpoint_to_dict(checkpoint)
    value["queued"].reverse()  # type: ignore[union-attr]
    with pytest.raises(ValueError, match="deterministic order"):
        checkpoint_from_dict(value)
    with pytest.raises(ValueError, match="document is empty"):
        decode_barge_checkpoint("\n")


def test_barge_checkpoint_file_roundtrip_preserves_digest(tmp_path: Path) -> None:
    checkpoint = BargeCheckpoint(
        running_operation(),
        BargePolicy.QUEUE,
        (Interrupt(3, 0, Identifier("interrupt-1"), "pause"),),
    )
    path = tmp_path / "barge.json"
    write_barge_checkpoint(path, checkpoint)
    restored = load_barge_checkpoint(path)
    assert restored == checkpoint
    assert path.read_text(encoding="utf-8") == encode_barge_checkpoint(checkpoint)
    assert barge_checkpoint_digest(restored) == barge_checkpoint_digest(checkpoint)


def test_barge_checkpoint_files_never_clobber_or_accept_truncation(tmp_path: Path) -> None:
    checkpoint = BargeCheckpoint(running_operation(), BargePolicy.QUEUE)
    path = tmp_path / "barge.json"
    write_barge_checkpoint(path, checkpoint)
    with pytest.raises(FileExistsError, match="output already exists"):
        write_barge_checkpoint(path, checkpoint)
    path.write_text(encode_barge_checkpoint(checkpoint).rstrip("\n"), encoding="utf-8")
    with pytest.raises(ValueError, match="missing terminal newline"):
        load_barge_checkpoint(path)
