# DuckPools Security Playbook

## Content Security Policy (CSP) Hardening

### Current Development Configuration
The current CSP in the SecurityHeadersMiddleware allows:
- `unsafe-inline` for scripts and styles (required for Vite dev server HMR)
- `unsafe-eval` (removed in the fix)
- `connect-src 'self'` (updated to include WebSocket connections)

### Production Hardening Recommendations

#### 1. Remove `unsafe-eval`
**Why:** `unsafe-eval` allows dynamic code execution which is a security risk.

**Production CSP:**
```http
Content-Security-Policy: default-src 'self'; 
                      script-src 'self' 'nonce-{random}' 'strict-dynamic'; 
                      style-src 'self' 'nonce-{random}'; 
                      img-src 'self' data:; 
                      connect-src 'self' ws:; 
                      frame-ancestors 'none'; 
                      form-action 'self'; 
                      base-uri 'self'; 
                      object-src 'none'
```

#### 2. Use Nonces Instead of `unsafe-inline`
**Why:** Nonces provide better security than `unsafe-inline` by ensuring only authorized scripts can run.

**Implementation:**
- Generate random nonce for each request
- Include nonce in CSP header
- Add nonce to script/style tags in HTML

#### 3. WebSocket Support
Ensure `ws:` is included in `connect-src` for WebSocket connections.

#### 4. Testing
Verify CSP compliance using browser dev tools and security testing tools.

### Implementation Steps

1. **Create nonce generator middleware**
2. **Update CSP header to use nonces**
3. **Update HTML templates to include nonces**
4. **Test in production environment**
5. **Monitor for CSP violations**

### Monitoring
- Set up CSP violation reporting
- Monitor for blocked resources
- Regular security audits

### References
- [OWASP CSP Guide](https://cheatsheetseries.owasp.org/cheatsheets/Content_Security_Policy_Cheat_Sheet.html)
- [MDN Web Docs - CSP](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Security-Policy)

---

## Security Headers Review

### Current Headers Applied
- ✅ X-Content-Type-Options: nosniff
- ✅ X-Frame-Options: DENY
- ✅ X-XSS-Protection: 1; mode=block
- ✅ Referrer-Policy: strict-origin-when-cross-origin
- ✅ Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=()
- ✅ Content-Security-Policy: (updated for development)
- ✅ Strict-Transport-Security: max-age=0 (development)

### Production Recommendations
- Increase HSTS max-age (e.g., 31536000 for 1 year)
- Consider adding `includeSubDomains` for HSTS
- Remove debug headers in production builds

---

## Verification
Run the security headers verification script:
```bash
python verify-security-headers.py
```

Expected output should show all security headers as compliant.