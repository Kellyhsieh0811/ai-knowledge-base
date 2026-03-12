# Security Policy

## Reporting a Vulnerability

We take the security of this project seriously. If you believe you have found a security vulnerability, please report it to us responsibly.

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, please send an email to the project maintainer. We will acknowledge your report and provide an estimated timeframe for a fix.

## Supported Versions

We currently only support the latest version of this project. Please ensure you are running the most recent code from the `main` branch.

## Security Practices

This project follows several security best practices:
- **Rate Limiting**: Protection against abuse and brute-force attacks.
- **Secure Headers**: Implementation of CSP and other security-related HTTP headers.
- **Environment Isolation**: Sensitive keys are kept in `.env` and never committed to version control.
- **CORS**: Controlled access for cross-origin requests.
