# Contributing

Voxwright accepts focused fixes and extensions to its offline voice-application mechanics. New
behavior should remain deterministic, require no network service by default, and distinguish
synthetic evaluation from evaluation of a real spoken model.

## Development setup

Use Python 3.11 or newer. Create `.venv`, install `.[dev]`, then run:

```bash
make format
make build
make test
make format-check
make typecheck
```

Install `.[dev,torch]` from the PyTorch CPU wheel index only when working on the optional model
adapter. `make test-all` includes tests marked `slow` and `model`.

## Change expectations

- Add boundary and inverse-direction tests with behavior changes.
- Preserve byte determinism for versioned JSON, JSONL, SVG, and report artifacts.
- Use seeded synthetic fixtures and label their planted ground truth clearly.
- Add changelog notes for user-visible changes and keep public API/schema goldens deliberate.
- Never add API keys, real personal data, downloaded weights, or network-dependent default tests.

Commit subjects follow the Conventional Commits form, such as `feat: add ...` or `fix: reject ...`.
