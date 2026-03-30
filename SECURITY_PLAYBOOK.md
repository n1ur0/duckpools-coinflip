# DuckPools Security Playbook

## Content Security Policy (CSP) Hardening

### Current Development Configuration

The current CSP in `backend/api_server.py` is configured for development with the following settings:

```python
response.headers["Content-Security-Policy"] = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self'; "
    "img-src 'self' data:; "
    "connect-src 'self' ws://localhost:8000 http://localhost:3000; "
    "frame-ancestors 'none'; "
    "form-action 'self'; "
    "base-uri 'self'; "
    "object-src 'none'"
)
```

### Production Hardening Requirements

For production deployment, the following changes must be made:

#### 1. Remove `unsafe-eval`
- **Current**: Not present in development config (good)
- **Production**: Ensure `unsafe-eval` is never included in CSP
- **Reason**: Prevents `eval()` and dynamic code execution vulnerabilities

#### 2. Replace `unsafe-inline` with Nonces
- **Current**: Not present in development config (good) 
- **Production**: Use CSP nonces for inline scripts and styles
- **Implementation**: 
  ```python
  # Example nonce generation and usage
  import secrets
  nonce = secrets.token_urlsafe(16)
  
  # Add nonce to CSP header
  response.headers["Content-Security-Policy"] = (
      "default-src 'self'; "
      f"script-src 'self' 'nonce-{nonce}'; "
      f"style-src 'self' 'nonce-{nonce}'; "
      # ... other directives
  )
  ```

#### 3. Update `connect-src` for Production
- **Current**: `connect-src 'self' ws://localhost:8000 http://localhost:3000;`
- **Production**: Update to include actual production domains
- **Example**: 
  ```python
  response.headers["Content-Security-Policy"] = (
      # ... other directives
      "connect-src 'self' wss://duckpools.com https://duckpools.com; "
      # ... other directives
  )
  ```

#### 4. Remove Debug Headers
- **Current**: X-Security-Middleware header is not set in production
- **Production**: Ensure no debug headers are exposed
- **Verification**: Audit all middleware and ensure no headers like `X-Security-Middleware` are set

### Implementation Checklist

- [ ] Remove any `unsafe-eval` from CSP
- [ ] Implement CSP nonces for inline scripts/styles
- [ ] Update `connect-src` to production domains
- [ ] Remove all debug headers
- [ ] Add CSP reporting endpoint for violation monitoring
- [ ] Test CSP in production environment

### Testing

Before deployment:
1. Run CSP violation tests
2. Verify no `unsafe-eval` or `unsafe-inline` in headers
3. Check that nonces are properly implemented
4. Test connectivity to production domains

### Monitoring

Implement CSP violation reporting:
```python
response.headers["Content-Security-Policy-Report-Only"] = (
    "default-src 'self'; report-uri /csp-report"
)
```

### References

- [OWASP CSP Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Content_Security_Policy_Cheat_Sheet.html)
- [MDN Web Docs - CSP](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Security-Policy)
- [CSP Generator](https://cspisawesome.com/)