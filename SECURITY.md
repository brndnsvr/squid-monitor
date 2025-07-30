# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability in Squid Monitor, please report it by:

1. **Do not** create a public GitHub issue
2. Email security concerns to: maintainer@example.com
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

We will acknowledge receipt within 48 hours and provide updates on the resolution.

## Security Considerations

This monitoring tool is designed with security in mind:

- Runs as non-root user
- Extensive systemd hardening
- Input validation for all user inputs
- No hardcoded credentials
- Support for encrypted SMTP (STARTTLS)
- Minimal attack surface in container

## Best Practices

1. Always use TLS for SMTP when possible
2. Restrict file permissions on configuration files
3. Use environment variables for sensitive data
4. Regularly update dependencies
5. Monitor logs for suspicious activity
6. Use network segmentation for monitoring infrastructure