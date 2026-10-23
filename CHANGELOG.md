# Changelog

All notable changes are documented here.

## [0.1.2] - 2026-10-30

### Added

- Strict frame-stack and replay-trace restoration with schema and CLI validation.
- Resumable barge-in checkpoints preserving deterministic interrupt ordering.
- Self-verifying report bundles bound to campaign, coverage, charts, and rendered bytes.

### Fixed

- Reject malformed nested artifact metadata with precise typed paths.
- Keep report and bundle output targets non-clobbering across CLI workflows.

## [0.1.1] - 2026-10-30

### Added

- Strict workflow, checkpoint, sandbox-audit, context, runtime, and campaign artifact codecs.
- CLI validation for the new versioned artifacts and deterministic workflow SVG export.
- Session-visible context updates and permission prompts with checksummed replay coverage.

### Fixed

- Preserve denied and confirmation-blocked tool attempts in tamper-evident audit evidence.
- Use explicit cross-version type narrowing at JSON decoder boundaries.

## [0.1.0] - 2026-10-30

### Added

- Typed, versioned session events with checksummed JSONL recording, replay, and diffing.
- Seeded synthetic scenarios with planted goals, slots, mishearings, and adversarial transcripts.
- Scripted, recorded, rule-based, local loopback, and optional CPU PyTorch adapters.
- Strict tool-call parsing, typed argument validation, and permissioned simulated tools.
- Frame grounding, repair policies, workflow recovery, barge-in handling, and context filtering.
- Logical-clock runtime, planted-ground-truth evaluation, and deterministic HTML/Markdown reports.
- Offline CLI commands and four end-to-end examples using synthetic fixtures.
