# CSP Production Hardening Playbook

## Overview
This playbook documents the Content Security Policy (CSP) hardening procedures for DuckPools CoinFlip production deployment. The current implementation uses relaxed CSP settings for development purposes, but these must be tightened for production to prevent XSS attacks and other security vulnerabilities.

## Current State (PoC)
The current CSP in `backend/api_server.py` is configured for development with the following characteristics:
- `script-src 'self'` (no unsafe-inline/unsafe-eval)
- `style-src 'self'` (no unsafe-inline)
- `connect-src 'self' ws://localhost:8000 http://localhost:3000` (restricted to development origins)

## Production Hardening Requirements

### 1. Remove `unsafe-eval` from CSP
**Current Issue**: While not currently present, ensure `unsafe-eval` is removed from production CSP
**Risk**: Allows dynamic code execution via `eval()` and similar functions
**Production Solution**: Remove `unsafe-eval` entirely from CSP

### 2. Use nonces instead of `unsafe-inline` for scripts
**Current Issue**: Development mode uses `unsafe-inline` for Vite HMR
**Risk**: Bypasses CSP nonce-based protection
**Production Solution**: 
- Remove `unsafe-inline` from script-src
- Implement nonce-based CSP with proper server-side nonce generation
- Example: `script-src 'self' 'nonce-<random-value>'`

### 3. Remove debug header `X-Security-Middleware`
**Current Issue**: Debug header exposes middleware implementation details
**Risk**: Information leakage to potential attackers
**Production Solution**: Remove the debug header entirely

### 4. Update `connect-src` to include production WebSocket and API origins
**Current Issue**: Development mode restricts to localhost ports
**Risk**: Blocks legitimate production connections
**Production Solution**: Update connect-src to include:
- Production API domain (e.g., `https://api.duckpools.com`)
- Production WebSocket domain (e.g., `wss://api.duckpools.com`)
- Any other required production origins

## Implementation Steps

### Step 1: Update SecurityHeadersMiddleware
Modify `backend/api_server.py` to:
1. Remove any debug headers (X-Security-Middleware)
2. Implement nonce-based CSP for production
3. Update connect-src to include production origins

### Step 2: Environment Configuration
Add production-specific CSP settings to environment variables:
```bash
# Production CSP settings
CSP_SCRIPT_NONCE_HEADER="X-CSP-Nonce"
CSP_ALLOWED_ORIGINS="https://api.duckpools.com,wss://api.duckpools.com"
```

### Step 3: Testing Procedures
1. **Local Testing**: Verify CSP headers are properly set in production mode
2. **Browser Testing**: Use browser dev tools to inspect CSP headers
3. **Security Scan**: Run security scans to verify CSP effectiveness
4. **Penetration Testing**: Include CSP testing in penetration test scope

### Step 4: Verification Checklist
- [ ] CSP headers present on all responses
- [ ] No `unsafe-eval` in CSP
- [ ] No `unsafe-inline` in script-src
- [ ] No debug headers (X-Security-Middleware)
- [ ] connect-src includes all required production origins
- [ ] CSP enforces proper origin restrictions
- [ ] Nonce-based CSP implemented correctly

## Rollout Plan

### Phase 1: Development Testing
- Implement nonce-based CSP in development environment
- Test with production-like CSP settings
- Validate all functionality still works

### Phase 2: Staging Environment
- Deploy to staging with production CSP
- Conduct thorough testing
- Address any compatibility issues

### Phase 3: Production Deployment
- Deploy to production with hardened CSP
- Monitor for any issues
- Document any exceptions or workarounds

## Monitoring and Maintenance

### CSP Violation Monitoring
- Set up alerts for CSP violation reports
- Regularly review violation reports
- Address legitimate violations promptly

### Regular Audits
- Quarterly CSP security audits
- Update CSP as new threats emerge
- Review allowed origins and scripts

## References
- [Content Security Policy Documentation](https://developer.mozilla.org/en-US/docs/Web/HTTP/CSP)
- [CSP Best Practices](https://web.dev/csp/)
- [CSP Nonce Implementation](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Security-Policy/script-src#nonces_and_hashes)

## Acceptance Criteria
- [x] Remove X-Security-Middleware header
- [x] Document CSP production hardening in playbook
- [ ] Implement nonce-based CSP for production
- [ ] Update connect-src for production origins
- [ ] Test CSP in staging environment
- [ ] Deploy hardened CSP to production

*Note: This playbook should be updated as the deployment environment and requirements evolve.*