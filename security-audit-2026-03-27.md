# DuckPools Security Audit Report

**Date**: 2026-03-27
**Auditor**: Penetration Tester Jr (c55137b5-99e2-45f1-8efe-ac289b61ef18)
**Team**: Security & Compliance
**Scope**: DuckPools Coinflip Web Application and API

---

## Executive Summary

A security assessment was performed on the DuckPools Coinflip protocol web application and backend API. The audit focused on OWASP Top 10 vulnerabilities, API security, and input validation.

**Key Findings:**
- 1 HIGH severity issue
- 3 MEDIUM severity issues
- 2 LOW severity issues

The most critical finding is that sensitive API keys can be passed via query parameters, which exposes them to logging and history. Immediate remediation is recommended.

---

## Detailed Findings

### 1. HIGH: API Key Exposed in Query Parameters

**Severity**: HIGH
**CVSS**: 7.5 (High)
**Location**: `backend/bet_routes.py` lines 496, 531

**Description**:
The `/resolve-bet` and `/reveal-bet` endpoints check for API key authentication in both the `X-Api-Key` header AND query parameter `api_key`. This allows sensitive API keys to be transmitted via URL query parameters.

**Code**:
```python
# Line 496 in bet_routes.py
api_key = request.headers.get("X-Api-Key") or request.query_params.get("api_key")
if api_key != API_KEY:
    raise HTTPException(status_code=403, detail="Invalid API key")
```

**Risk**:
- Query parameters are logged in:
  - Web server access logs (nginx, Apache)
  - Proxy server logs
  - CDN logs (Cloudflare, etc.)
  - Browser history
  - Referrer headers (if URL is shared)
- API key exposure allows unauthorized access to bot-only endpoints
- An attacker who gains access to logs can escalate privileges

**Evidence**:
```bash
# API key works in query params (confirmed via testing)
curl -X POST "http://localhost:8000/resolve-bet?api_key=hello" \
  -H "Content-Type: application/json" \
  -d '{"bet_id":"test",...}'
```

**Recommendation**:
```python
# Remove query parameter check, only accept header
api_key = request.headers.get("X-Api-Key")
if not api_key or api_key != API_KEY:
    raise HTTPException(status_code=403, detail="Invalid API key")
```

**Impact**: Unauthorized access to bet resolution and revelation endpoints could allow manipulation of game outcomes.

---

### 2. MEDIUM: Single API Key for Multiple Purposes

**Severity**: MEDIUM
**CVSS**: 6.5 (Medium)
**Location**: `backend/bet_routes.py` line 38, `backend/api_server.py` line 46

**Description**:
The same `API_KEY` environment variable is used for:
1. Ergo node REST API authentication
2. Internal bot endpoint authentication (`/resolve-bet`, `/reveal-bet`)

This violates the principle of least privilege - if the node API key is compromised, bot endpoints are also exposed, and vice versa.

**Code**:
```python
# Line 38 in bet_routes.py
API_KEY = os.getenv("API_KEY", "hello")

# Used for node authentication
headers = {"api_key": API_KEY, ...}

# Used for bot endpoint authentication
api_key = request.headers.get("X-Api-Key")
if api_key != API_KEY:
    raise HTTPException(status_code=403, detail="Invalid API key")
```

**Risk**:
- Increased attack surface: compromise of one system exposes the other
- No way to revoke bot access without affecting node access
- Cannot implement different rotation policies for different systems
- Node API key (potentially shared with infrastructure team) gives access to bot operations

**Recommendation**:
```python
# backend/.env
NODE_API_KEY=hello               # For Ergo node
BOT_API_KEY=<strong-random-key>  # For bot endpoints

# bet_routes.py
NODE_API_KEY = os.getenv("NODE_API_KEY", "hello")
BOT_API_KEY = os.getenv("BOT_API_KEY")

# For node requests
headers = {"api_key": NODE_API_KEY, ...}

# For bot endpoints
api_key = request.headers.get("X-Api-Key")
if not api_key or api_key != BOT_API_KEY:
    raise HTTPException(status_code=403, detail="Invalid API key")
```

**Impact**: Compromise of one authentication system doesn't cascade to the other.

---

### 3. MEDIUM: CORS allow_credentials Enabled Without Clear Justification

**Severity**: MEDIUM
**CVSS**: 5.9 (Medium)
**Location**: `backend/api_server.py` line 181

**Description**:
CORS is configured with `allow_credentials=True`, which allows browsers to send cookies and authorization headers in cross-origin requests. This increases the risk of CSRF attacks.

**Code**:
```python
# Line 181 in api_server.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,  # ← Enables cookies/auth headers
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Risk**:
- Enables CSRF attacks if any state-changing operation can be triggered via cross-origin requests
- Combined with weak same-site cookie policies, this could allow unauthorized actions
- The frontend uses EIP-12 wallet signatures, not cookies, so credentials=True may be unnecessary

**Analysis**:
- DuckPools uses Nautilus wallet (EIP-12) for authentication, not session cookies
- User actions require wallet signatures, which CSRF cannot forge
- However, any future cookie-based auth would be vulnerable

**Recommendation**:
1. Confirm if `allow_credentials=True` is actually needed
2. If not, set to `False`
3. If needed, implement CSRF protection:
   - Use SameSite=Strict/Lax cookies
   - Add CSRF tokens for state-changing endpoints
   - Validate Origin/Referer headers

```python
# If cookies are not used:
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,  # Disable unless absolutely necessary
    allow_methods=["GET", "POST"],  # Restrict to needed methods
    allow_headers=["Content-Type"],  # Restrict to needed headers
)
```

**Impact**: Reduced CSRF attack surface for any future cookie-based authentication.

---

### 4. MEDIUM: Security Headers Not Applied to Running Instance

**Severity**: MEDIUM
**CVSS**: 5.3 (Medium)
**Location**: `backend/api_server.py` lines 150-174 (SecurityHeadersMiddleware)

**Description**:
Although the codebase includes a `SecurityHeadersMiddleware` that injects standard security headers, the running backend instance (v0.1.0) does not return these headers. This suggests a version mismatch or middleware not being applied in production.

**Expected Headers** (from code):
```python
response.headers["X-Content-Type-Options"] = "nosniff"
response.headers["X-Frame-Options"] = "DENY"
response.headers["X-XSS-Protection"] = "1; mode=block"
response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"
```

**Actual Headers** (from testing):
```
server: uvicorn
(No X-Content-Type-Options, X-Frame-Options, etc.)
```

**Risk**:
- **X-Frame-Options missing**: Page can be embedded in iframes (clickjacking risk)
- **X-Content-Type-Options missing**: Browser may sniff MIME types (MIME-sniffing attacks)
- **X-XSS-Protection missing**: Legacy XSS protection disabled
- **Referrer-Policy missing**: Sensitive URLs leaked via Referer header
- **Permissions-Policy missing**: Browser can request camera/mic/geolocation without restriction

**Evidence**:
```bash
curl -I http://localhost:8000/health
# Returns only: server: uvicorn
# Missing: X-Frame-Options, X-Content-Type-Options, etc.
```

**Recommendation**:
1. Verify the running backend version matches the codebase
2. Ensure SecurityHeadersMiddleware is registered before the app starts
3. Add health check for security headers in CI/CD:
```python
# tests/test_security_headers.py
async def test_security_headers_applied():
    async with httpx.AsyncClient() as client:
        resp = await client.get("http://localhost:8000/health")
        assert "X-Frame-Options" in resp.headers
        assert resp.headers["X-Frame-Options"] == "DENY"
        assert "X-Content-Type-Options" in resp.headers
```

**Impact**: Clickjacking, MIME-sniffing, and information leakage vulnerabilities.

---

### 5. LOW: Rate Limiting Too Permissive on Bot Endpoints

**Severity**: LOW
**CVSS**: 3.5 (Low)
**Location**: `backend/bet_routes.py` lines 488, 528

**Description**:
Bot-only endpoints `/resolve-bet` and `/reveal-bet` have a rate limit of 30 requests per minute, which is quite high for sensitive operations that should be rate-limited more aggressively.

**Code**:
```python
@router.post("/resolve-bet")
@limiter.limit("30/minute")  # ← 30 req/min for bot-only endpoint
async def resolve_bet(request: Request, body: ResolveBetRequest):
```

**Risk**:
- Even with API key auth, an attacker with leaked key can perform 30 actions per minute
- Bot endpoints are called programmatically, so bursty traffic is expected
- High rate limit amplifies the impact of API key exposure

**Recommendation**:
1. Reduce rate limit to 10 req/min for bot endpoints
2. Implement per-API-key rate limiting (not just per-IP)
3. Add separate buckets for different bot operations:
```python
@router.post("/resolve-bet")
@limiter.limit("10/minute")  # Stricter for resolve
async def resolve_bet(...)

@router.post("/reveal-bet")
@limiter.limit("15/minute")  # Slightly higher for reveal
async def reveal_bet(...)
```

**Impact**: Reduces the impact of API key exposure and limits brute force attempts.

---

### 6. LOW: Potential XSS in Error Display

**Severity**: LOW
**CVSS**: 3.1 (Low)
**Location**: `frontend/src/components/BetForm.tsx` lines 136-138

**Description**:
Error messages from the backend are displayed in the frontend without HTML escaping. While React's default escaping mitigates this, there's no explicit sanitization of user-generated content that may be reflected in error messages.

**Code**:
```typescript
// Line 136-138 in BetForm.tsx
const message = err instanceof Error ? err.message : 'Failed to place bet';
setError(message);
```

**Frontend display (not shown but inferred)**:
```tsx
{error && <div className="bf-error">{error}</div>}
```

**Risk**:
- If backend includes user input in error messages, it could be reflected without sanitization
- React's auto-escaping prevents most XSS, but edge cases exist (dangerouslySetInnerHTML, etc.)
- Error messages may be logged client-side, exposing sensitive data

**Evidence (backend validation)**:
```python
# Line 84 in bet_routes.py
raise ValueError(f"Address too short: {len(v)} chars")
# If v is user-controlled, this reflects user input in error
```

**Recommendation**:
1. Sanitize all error messages in backend before sending
2. Use a library like `bleach` or DOMPurify in frontend
3. Avoid including user input in error messages:
```python
# Backend
if len(v) < 30:
    raise ValueError("Address too short")  # Don't include len(v)

# Frontend
import DOMPurify from 'dompurify';
const sanitizedError = DOMPurify.sanitize(message);
setError(sanitizedError);
```

**Impact**: Reduced XSS attack surface through error handling.

---

## Additional Observations

### Positive Security Controls
1. **Rate limiting implemented** via `slowapi` (issue 705ddf7c)
2. **Input validation** using Pydantic models
3. **Security headers middleware** defined (though not active in running instance)
4. **CORS origins restricted** to configured list
5. **API key authentication** on bot endpoints
6. **Address validation** for Ergo addresses
7. **Bet amount bounds checking** (min/max limits)

### Areas for Future Review
1. **WebSocket security**: Review WS endpoint authentication (`/ws/bets?address={addr}`)
2. **Smart contract security**: Audit ErgoScript contracts using MCP tools
3. **Wallet signature verification**: Ensure EIP-12 signatures are validated correctly
4. **Secret generation**: Verify cryptographic randomness for bet secrets
5. **Transaction replay protection**: Ensure transactions cannot be replayed
6. **Logging and monitoring**: Implement security event logging

---

## Testing Methodology

1. **Static Code Analysis**: Manual review of Python and TypeScript code
2. **API Testing**: `curl` tests against running backend (localhost:8000)
3. **Header Analysis**: Inspected HTTP response headers
4. **OWASP Top 10**: Checked against OWASP guidance

---

## Remediation Priority

| Priority | Issue | Estimated Effort |
|----------|-------|------------------|
| P0 | API Key in Query Parameters | 30 min |
| P1 | Single API Key for Multiple Purposes | 2 hours |
| P1 | Security Headers Not Applied | 1 hour (debug + restart) |
| P2 | CORS allow_credentials=True | 4 hours (analysis + fix) |
| P3 | Rate Limiting Too Permissive | 30 min |
| P3 | Potential XSS in Error Display | 2 hours |

---

## Conclusion

The DuckPools application demonstrates good security awareness with input validation, rate limiting, and authentication controls in place. However, critical vulnerabilities around API key handling and security header configuration require immediate attention.

The most urgent fix is removing the ability to pass API keys via query parameters (Issue #1). This should be deployed immediately as it exposes secrets to logging infrastructure.

Overall security posture: **MODERATE** - Good foundation, but critical areas need remediation before mainnet deployment.

---

## References

- OWASP Top 10: https://owasp.org/www-project-top-ten/
- CWE-598: Use of GET Request Method With Sensitive Query Strings
- CWE-532: Insertion of Sensitive Information into Log File
- FastAPI Security Best Practices: https://fastapi.tiangolo.com/tutorial/security/
