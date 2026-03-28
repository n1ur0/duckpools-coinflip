# CSP Production Hardening Guide

## Overview

This document provides guidance for hardening the Content Security Policy (CSP) for production deployment of DuckPools CoinFlip.

## Current Development CSP

The current CSP in `backend/api_server.py` is configured for development:

```python
response.headers["Content-Security-Policy"] = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "connect-src 'self' ws://localhost:3000 wss://localhost:3000; "
    "frame-ancestors 'none'; "
    "form-action 'self'; "
    "base-uri 'self'; "
    "object-src 'none'"
)
```

## Production Recommendations

### 1. Remove `unsafe-inline`

`unsafe-inline` bypasses CSP protection and should be replaced with nonces or hashes:

```python
# Generate a nonce for each request
import secrets

csp_nonce = secrets.token_hex(16)

# Use in CSP
"script-src 'self' 'nonce-{csp_nonce}'; "
"style-src 'self' 'nonce-{csp_nonce}'; "

# Pass nonce to template
return templates.TemplateResponse("index.html", {"nonce": csp_nonce})
```

In HTML templates:
```html
<script nonce="{{ nonce }}">
    // Your code here
</script>

<style nonce="{{ nonce }}">
    /* Your styles here */
</style>
```

### 2. Lock Down WebSocket Origins

Replace `localhost` with your production WebSocket domain:

```python
# Production CSP
"connect-src 'self' wss://api.duckpools.com; "
```

### 3. Add Report-Only Mode (Optional)

For testing, implement CSP report-only mode:

```python
# Add to security headers
response.headers["Content-Security-Policy-Report-Only"] = (
    # Your production CSP here
)
```

### 4. Consider Additional Directives

```python
# Prevent mixed content
"block-all-mixed-content; "

# Require HTTPS in production
"upgrade-insecure-requests; "

# Control plugin types
"plugin-types 'none'; "
```

## Final Production CSP Example

```python
response.headers["Content-Security-Policy"] = (
    "default-src 'self'; "
    "script-src 'self' 'nonce-{csp_nonce}'; "
    "style-src 'self' 'nonce-{csp_nonce}'; "
    "img-src 'self' data: https://api.duckpools.com; "
    "connect-src 'self' wss://api.duckpools.com; "
    "font-src 'self'; "
    "frame-ancestors 'none'; "
    "form-action 'self'; "
    "base-uri 'self'; "
    "object-src 'none'; "
    "block-all-mixed-content; "
    "upgrade-insecure-requests; "
    "plugin-types 'none'; "
    "report-uri /csp-violation-report"
)
```

## Implementation Steps

1. **Generate nonces dynamically** for each request
2. **Update HTML templates** to use nonces for inline scripts/styles
3. **Update frontend build process** to generate content hashes for static files
4. **Test in report-only mode** before enforcing
5. **Gradually enforce** the policy
6. **Monitor CSP violation reports** and adjust as needed

## Security Benefits

- **Prevents XSS attacks** by restricting script sources
- **Prevents data injection** by controlling content sources
- **Blocks mixed content** to maintain HTTPS security
- **Prevents clickjacking** with frame restrictions
- **Prevents plugin-based attacks**

## References

- [MDN CSP Documentation](https://developer.mozilla.org/en-US/docs/Web/HTTP/CSP)
- [CSP Evaluator](https://csp-evaluator.withgoogle.com/)
- [OWASP CSP Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Content_Security_Policy_Cheat_Sheet.html)