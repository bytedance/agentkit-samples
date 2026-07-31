# Security Policy

## Supported versions

Security fixes are provided for the latest released version of Situla.

## Reporting a vulnerability

Please do not report security vulnerabilities in a public issue. Use the
repository's private security advisory feature and include:

- the affected Situla version and platform;
- reproduction steps or a minimal proof of concept;
- the expected and observed behavior;
- any known impact on credentials, sandbox sessions, or local files.

Please avoid including live OAuth codes, STS tokens, Endpoint query strings,
or other credentials. The maintainers will acknowledge the report, investigate
it, and coordinate disclosure and a release when appropriate.

## Security boundaries

Situla is a loopback-only client for Volcengine AgentKit sandboxes. Reports
involving Host or Origin checks, capability cookies, URL redaction, sandbox
session isolation, or approval handling are treated as security-sensitive.
