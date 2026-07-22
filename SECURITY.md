# Security Policy

## Public Repository Boundary

This repository is public. Do not commit:

- API keys, tokens, passwords, private keys, cookies, or credentials
- Internal-only URLs, hostnames, network details, or private configuration
- Customer, employee, or other sensitive personal data
- Production data, logs, dumps, or generated secret material

Use runtime secret storage and injection. Capability packages may declare required secret names or purposes, but never secret values.

## Safety Metadata

CLI Harness commands must classify side effects and identify when explicit approval is required. Trusting a package does not authorize every invocation.

## Reporting a Vulnerability

Do not open a public issue for a suspected vulnerability or exposed secret. Contact the Wondermove-Inc repository administrators through a private organizational channel. Include the affected path, impact, and safe reproduction details.
