# Security policy

## Supported versions

Security fixes are applied to the latest released patch line. This pre-1.0 project does not
promise compatibility fixes for older snapshots.

## Reporting a vulnerability

Open a private GitHub security advisory for vulnerabilities involving permission bypass,
tool-call injection, unsafe artifact parsing, privacy-filter leakage, or report escaping. Include
the affected version, a minimal offline reproduction, and the expected invariant. Do not include
real credentials, private audio, or personal data.

For non-sensitive hardening ideas, use the security issue form. Public issues should not contain
an exploit that could expose another user's data.

## Trust boundary

Voxwright simulates application mechanics locally. Tool schemas, permissions, grammar validation,
context redaction, and tamper-evident ledgers reduce risk but do not make an untrusted external
model or backend safe. Applications must authenticate real backends, enforce permissions at the
side-effect boundary, and review their own retention and privacy requirements.
