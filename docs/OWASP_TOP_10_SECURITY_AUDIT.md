# OWASP Top 10 Security Audit - DuckPools API

**Issue ID**: befd4bd3-b8c0-46a2-99cc-b0b765c83b94
**Issue Title**: Run OWASP top 10 checklist against the API and document findings
**Performed by**: Penetration Tester Jr
**Date**: 2026-03-28
**Scope**: Backend API (FastAPI), WebSocket endpoints, LP pool routes, Oracle routes
**OWASP Top 10 Version**: 2021

---

## Executive Summary

This security audit evaluates the DuckPools Coinflip API against the OWASP Top 10 (2021) vulnerabilities. The audit covers:

- **Backend API**: FastAPI server (`backend/api_server.py`)
- **LP Pool Routes**: Liquidity pool endpoints (`backend/lp_routes.py`)
- **WebSocket Routes**: Real-time bet updates (`backend/ws_routes.py`)
- **Oracle Service**: RNG oracle endpoints (`backend/oracle_routes.py`, `backend/oracle_service.py`)
- **Configuration**: CORS, middleware, dependencies

### Overall Risk Assessment: **MEDIUM**

The API has several security gaps that should be addressed before production deployment, particularly around rate limiting, authentication, input validation, and security headers.

---

## OWASP Top 10 (2021) Checklist

### A01:2021 - Broken Access Control

| Check | Status | Findings | Severity |
|-------|--------|----------|----------|
| **A01.1**: Verify all API endpoints have proper authentication | ⚠️ PARTIAL | Only POST endpoints have `api_key` header verification; GET endpoints are open | **HIGH** |
| **A01.2**: Verify that users cannot access other users' data | ⚠️ PARTIAL | `/lp/balance/{address}` allows querying any address without authentication | **MEDIUM** |
| **A01.3**: Verify that sensitive operations require additional authorization | ✅ PASS | Withdrawal request execution uses blockchain contract logic | **LOW** |

#### Detailed Findings:

**1. GET Endpoints Lack Authentication (HIGH)**
- **Affected endpoints**:
  - `GET /lp/pool` - Pool state and TVL
  - `GET /lp/price` - LP token price
  - `GET /lp/balance/{address}` - User's LP balance
  - `GET /lp/apy` - Pool APY calculations
  - `GET /lp/estimate/deposit` - Deposit estimates
  - `GET /lp/estimate/withdraw` - Withdrawal estimates
  - `GET /ws/stats` - WebSocket connection statistics
  - `GET /api/oracle/health` - Oracle health status
  - `GET /api/oracle/status` - Oracle service status
  - `GET /api/oracle/endpoints` - Oracle endpoint list

- **Risk**: While some data (pool state) is public, other endpoints like `/lp/balance/{address}` expose user-specific data without authentication. An attacker can enumerate addresses and track user balances.

- **Recommendation**:
  - Add `api_key` authentication to GET endpoints that expose user-specific data
  - Implement rate limiting to prevent enumeration attacks
  - Consider adding address ownership verification (signature-based)

**2. No Authorization Checks on Address-Based Queries (MEDIUM)**
- **Affected endpoint**: `GET /lp/balance/{address}` (lp_routes.py:145)
- **Risk**: Any client can query LP balances for any Ergo address, enabling surveillance and targeted attacks
- **Recommendation**:
  - Require authentication (JWT or api_key) to query balances
  - Add address signature verification: client must sign a challenge to prove ownership

---

### A02:2021 - Cryptographic Failures

| Check | Status | Findings | Severity |
|-------|--------|----------|----------|
| **A02.1**: Verify all sensitive data is encrypted in transit | ✅ PASS | API uses HTTPS in production (CORS config expects HTTPS origins) | **LOW** |
| **A02.2**: Verify no hardcoded secrets in code | ⚠️ PARTIAL | API key hash used in env, but some values appear hardcoded in places | **MEDIUM** |
| **A02.3**: Verify strong cryptographic algorithms | ✅ PASS | Uses Ergo's built-in cryptography (SigmaProp, SHA-256) | **LOW** |

#### Detailed Findings:

**1. Hardcoded Values in Code (MEDIUM)**
- **Location**: `backend/lp_routes.py`
- **Code**: 
  ```python
  "fee": str(1_000_000),  # Line 309, 384, 467, 523 (hardcoded 0.001 ERG fee)
  ```
- **Risk**: While not a secret, hardcoded values reduce flexibility and may need adjustment based on network conditions
- **Recommendation**: Move fee to environment variable (`TX_FEE_NANOERG`)

**2. API Key Storage (GOOD)**
- **Current**: API key stored in environment variable (`API_KEY=hello`)
- **Used**: Node API authentication via `blake2b256("hello")` hash
- **Note**: The default API key "hello" should be changed for production
- **Recommendation**: Generate strong random API key for production

---

### A03:2021 - Injection

| Check | Status | Findings | Severity |
|-------|--------|----------|----------|
| **A03.1**: Verify user input is validated before use | ⚠️ PARTIAL | Pydantic models used for JSON bodies, but query parameters have basic validation | **MEDIUM** |
| **A03.2**: Verify no SQL injection vulnerabilities | N/A | No SQL database used (blockchain-only) | **N/A** |
| **A03.3**: Verify no command injection vulnerabilities | ✅ PASS | No shell commands executed with user input | **LOW** |
| **A03.4**: Verify no path traversal vulnerabilities | ⚠️ PARTIAL | Address parameter in `/lp/balance/{address:path}` accepts any string | **MEDIUM** |

#### Detailed Findings:

**1. Address Parameter Validation Weak (MEDIUM)**
- **Affected endpoint**: `GET /lp/balance/{address:path}` (lp_routes.py:145)
- **Code**:
  ```python
  @router.get("/balance/{address:path}", response_model=LPBalanceResponse)
  async def get_lp_balance(address: str, request: Request):
  ```
- **Risk**: While FastAPI's `{address:path}` captures the full path, there's no validation that it's a valid Ergo address format. This could lead to invalid ErgoTree bytes conversion or potential injection via malformed addresses passed to Ergo node

- **Recommendation**: Add Ergo address format validation:
  ```python
  from pydantic import constr, validator
  
  ErgoAddress = constr(strip_whitespace=True, min_length=1, max_length=100)
  
  class AddressParam(str):
      @classmethod
      def __get_validators__(cls):
          yield cls.validate
          
      @classmethod
      def validate(cls, v):
          if not v or not (v.startswith('3') or v.startswith('9')):
              raise ValueError('Invalid Ergo address prefix')
          if len(v) < 20:
              raise ValueError('Address too short')
          return v
  ```

**2. Query Parameter Bounds Missing (MEDIUM)**
- **Affected endpoints**:
  - `GET /lp/apy` - Query params: `avg_bet_size` (string), `bets_per_block` (float)
  - `GET /lp/estimate/deposit` - Query param: `amount` (int)
  - `GET /lp/estimate/withdraw` - Query param: `shares` (int)

- **Risk**: No maximum value validation could lead to integer overflow or DoS

- **Recommendation**: Add maximum bounds to all numeric parameters
  ```python
  amount: int = Query(..., gt=0, le=1_000_000_000_000_000_000)  # Max 1 million ERG
  shares: int = Query(..., gt=0, le=1_000_000_000_000_000_000)  # Reasonable max
  ```

**3. Pydantic Models for JSON Bodies (GOOD)**
- **Affected endpoints**: All POST endpoints
- **Current**: Pydantic models with Field validation (`gt=0`, `min_length=1`)
- **Status**: ✅ Proper validation implemented

**4. WebSocket Address Validation (PARTIAL)**
- **Location**: `backend/ws_routes.py:58`
- **Code**:
  ```python
  if len(address) < 20:
      await websocket.close(code=4001, reason="Invalid address: too short")
  ```
- **Risk**: Only checks length, not format. Could allow invalid addresses to be subscribed.
- **Recommendation**: Add full Ergo address validation (prefix check, checksum if applicable)

---

### A04:2021 - Insecure Design

| Check | Status | Findings | Severity |
|-------|--------|----------|----------|
| **A04.4**: Verify rate limiting is implemented | ❌ FAIL | No rate limiting found | **HIGH** |

#### Detailed Findings:

**1. No Rate Limiting (HIGH)**
- **Affected**: All API endpoints
- **Risk**: 
  - DoS attack: Attacker can spam requests, degrading service for legitimate users
  - Brute force: Enumerate all addresses via `/lp/balance/{address}`
  - Resource exhaustion: WebSocket connections (`ws/bets/{address}`) can be abused

- **Recommendation**: Implement rate limiting middleware using `slowapi`:
  ```python
  from slowapi import Limiter
  from slowapi.util import get_remote_address
  
  limiter = Limiter(key_func=get_remote_address)
  app.state.limiter = limiter
  
  # Apply limits
  @router.get("/lp/pool")
  @limiter.limit("100/minute")
  async def get_pool_state(request: Request):
  ```
  
  Suggested limits:
  - Public endpoints: 100 requests/minute
  - Authenticated endpoints: 1000 requests/minute
  - WebSocket connections: 5 concurrent per IP

---

### A05:2021 - Security Misconfiguration

| Check | Status | Findings | Severity |
|-------|--------|----------|----------|
| **A05.1**: Verify all default credentials are changed | ⚠️ PARTIAL | API key `hello` is default | **MEDIUM** |
| **A05.2**: Verify CORS is properly configured | ⚠️ PARTIAL | CORS allows `*` methods and headers | **MEDIUM** |
| **A05.3**: Verify security headers are present | ❌ FAIL | No security headers middleware | **HIGH** |
| **A05.4**: Verify error messages don't leak sensitive info | ⚠️ PARTIAL | Generic HTTPException used, but stack traces may leak | **MEDIUM** |
| **A05.5**: Verify server version is hidden | ❌ FAIL | FastAPI returns version in OpenAPI spec | **LOW** |

#### Detailed Findings:

**1. Missing Security Headers (HIGH)**
- **Current**: No security headers middleware in `api_server.py`
- **Missing headers**:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY` or `SAMEORIGIN`
  - `Content-Security-Policy` (if serving HTML)
  - `Strict-Transport-Security: max-age=31536000; includeSubDomains`
  - `X-XSS-Protection: 1; mode=block`
  - `Referrer-Policy: strict-origin-when-cross-origin`
  - `Permissions-Policy`

- **Recommendation**: Add Starlette middleware to inject security headers on all responses (see issue #4d098eb3 for full implementation)

**2. CORS Too Permissive (MEDIUM)**
- **Location**: `backend/api_server.py:102-108`
- **Code**:
  ```python
  app.add_middleware(
      CORSMiddleware,
      allow_origins=cors_origins,
      allow_credentials=True,
      allow_methods=["*"],  # ← All methods
      allow_headers=["*"],  # ← All headers
  )
  ```
- **Risk**:
  - `allow_methods=["*"]` allows unsafe methods (PUT, DELETE, PATCH) even if not used
  - `allow_headers=["*"]` allows any header, potentially bypassing security controls

- **Recommendation**:
  ```python
  app.add_middleware(
      CORSMiddleware,
      allow_origins=cors_origins,
      allow_credentials=True,
      allow_methods=["GET", "POST", "OPTIONS"],  # Only allowed methods
      allow_headers=[
          "Content-Type",
          "Authorization",
          "X-API-Key",  # Specific headers only
      ],
  )
  ```

**3. Default API Key (MEDIUM)**
- **Current**: `API_KEY=hello` in .env
- **Risk**: Default credentials are often targeted by attackers
- **Recommendation**: Generate strong random API key for production: `openssl rand -hex 32`

**4. Server Version Disclosure (LOW)**
- **Current**: FastAPI returns `"version": "0.2.0"` in root endpoint and OpenAPI spec
- **Risk**: Helps attackers know which vulnerabilities to exploit
- **Recommendation**: Remove version from public API responses

---

### A06:2021 - Vulnerable and Outdated Components

| Check | Status | Findings | Severity |
|-------|--------|----------|----------|
| **A06.2**: Verify no known vulnerable dependencies | ❓ UNKNOWN | No SBOM or vulnerability scan | **MEDIUM** |
| **A06.3**: Verify Python version is supported | ✅ PASS | Requires Python 3.9+ (supported) | **LOW** |
| **A06.4**: Verify FastAPI version is current | ✅ PASS | FastAPI >=0.104.0 (recent) | **LOW** |

#### Detailed Findings:

**1. No Dependency Scanning (MEDIUM)**
- **Current**: No evidence of automated dependency vulnerability scanning
- **Recommendation**: Implement dependency scanning:
  ```bash
  # pip-audit for Python
  pip install pip-audit
  pip-audit
  
  # Or use safety
  pip install safety
  safety check
  
  # Add to CI/CD pipeline
  ```

**2. Dependencies List** (from requirements.txt):
```
fastapi>=0.104.0        # ✅ Recent
uvicorn[standard]>=0.24.0
httpx>=0.25.0
pydantic>=2.0.0
pydantic-settings>=2.0.0
websockets>=12.0
```

- **Recommendation**: Pin specific versions for production and scan regularly

---

### A07:2021 - Identification and Authentication Failures

| Check | Status | Findings | Severity |
|-------|--------|----------|----------|
| **A07.1**: Verify authentication is required for sensitive operations | ⚠️ PARTIAL | Only POST endpoints have api_key | **MEDIUM** |
| **A07.4**: Verify authentication is not vulnerable to brute force | ❌ FAIL | No rate limiting on auth endpoints | **MEDIUM** |

#### Detailed Findings:

**1. Weak Authentication Model (MEDIUM)**
- **Current**: Single shared API key (`X-API-Key` or `api_key` header)
- **Risk**:
  - All clients share the same key (no per-client authentication)
  - If key leaks, all clients are compromised
  - No way to revoke individual clients

- **Recommendation**: Implement per-client API keys:
  ```python
  # Store API keys in database or config
  API_KEYS = {
      "client1_key": {"name": "Client 1", "rate_limit": 1000},
      "client2_key": {"name": "Client 2", "rate_limit": 500},
  }
  ```

**2. WebSocket Authentication (MEDIUM)**
- **Location**: `backend/ws_routes.py:29`
- **Risk**: WebSocket connections have no authentication, only basic address length check
- **Recommendation**: Add API key verification in WebSocket handshake

---

### A08:2021 - Software and Data Integrity Failures

| Check | Status | Findings | Severity |
|-------|--------|----------|----------|
| **A08.3**: Verify data integrity is protected | ✅ PASS | Blockchain ensures immutability | **LOW** |
| **A08.4**: Verify updates come from trusted sources | ✅ PASS | Uses pip from PyPI | **LOW** |

#### Detailed Findings:

**1. Data Integrity via Blockchain (GOOD)**
- **Current**: All critical data (bets, LP tokens, withdrawals) is on-chain
- **Status**: ✅ Immutable and verifiable

---

### A09:2021 - Security Logging and Monitoring Failures

| Check | Status | Findings | Severity |
|-------|--------|----------|----------|
| **A09.1**: Verify security events are logged | ⚠️ PARTIAL | Basic logging in ws_routes.py and oracle_service.py | **MEDIUM** |
| **A09.2**: Verify logs include sufficient detail | ⚠️ PARTIAL | Logs miss context (IP, user agent) | **MEDIUM** |
| **A09.4**: Verify alerting is configured | ❌ FAIL | No alerting found | **HIGH** |

#### Detailed Findings:

**1. Limited Security Logging (MEDIUM)**
- **Current**: Only WebSocket and Oracle routes have logging
- **Missing**:
  - API access logs (who accessed what endpoint, when, from where)
  - Authentication failures
  - Rate limit violations
  - Suspicious patterns (rapid address enumeration)

- **Recommendation**: Implement comprehensive logging middleware

**2. No Alerting (HIGH)**
- **Risk**: Security incidents may go undetected
- **Recommendation**: Set up alerts for:
  - High rate of authentication failures
  - Unusual transaction patterns
  - WebSocket connection anomalies
  - API errors (500 status codes)
  - Node connectivity failures

---

### A10:2021 - Server-Side Request Forgery (SSRF)

| Check | Status | Findings | Severity |
|-------|--------|----------|----------|
| **A10.1**: Verify user input is not used in HTTP requests | ✅ PASS | No user-controlled URLs in outbound requests | **LOW** |
| **A10.2**: Verify internal services are protected | ✅ PASS | Internal Ergo node requires API key | **LOW** |

#### Detailed Findings:

**1. No SSRF Risk (GOOD)**
- **Current**: All HTTP requests go to hardcoded URLs (`NODE_URL`, `ORACLE_PRIMARY_URL`)
- **Status**: ✅ No user input influences request destinations

---

## Summary by Severity

### High (4)
1. **A01.1**: GET endpoints lack authentication
2. **A04.4**: No rate limiting implemented
3. **A05.3**: Missing security headers middleware
4. **A09.4**: No alerting configured

### Medium (13)
1. **A01.2**: No authorization checks on address queries
2. **A02.2**: Hardcoded values (transaction fee)
3. **A03.1**: Address validation weak
4. **A03.2**: Query parameter bounds missing
5. **A05.2**: CORS too permissive
6. **A05.4**: Error messages may leak sensitive info
7. **A05.1**: Default API key not changed
8. **A06.2**: No dependency vulnerability scanning
9. **A07.1**: Weak authentication model (shared API key)
10. **A07.4**: No rate limiting on auth
11. **A09.1**: Limited security logging
12. **A09.2**: Logs lack context (IP, user agent)

### Low (7)
1. **A02.3**: Cryptographic algorithms (OK)
2. **A03.3**: No command injection (OK)
3. **A05.5**: Server version disclosure
4. **A06.3**: Python version supported
5. **A06.4**: FastAPI version current
6. **A08.1**: No code signing (info)
7. **A10.1**: SSRF (no issue)

---

## Priority Recommendations (Ordered by Impact)

### Phase 1: Critical Security Hardening (Deploy Before Production)

1. **Implement Rate Limiting** (HIGH, A04.4, A07.4)
   - Use `slowapi` middleware
   - Limits: 100 req/min (public), 1000 req/min (auth)
   - Prevent DoS and enumeration attacks

2. **Add Security Headers Middleware** (HIGH, A05.3)
   - X-Content-Type-Options, X-Frame-Options, HSTS
   - Protect against XSS, clickjacking, MITM

3. **Add API Key Authentication to GET Endpoints** (MEDIUM, A01.1)
   - At minimum: `/lp/balance/{address}` to prevent enumeration
   - Add request signing for address ownership verification

4. **Strengthen Input Validation** (MEDIUM, A03.1, A03.2)
   - Add Ergo address format validation
   - Add maximum bounds on numeric parameters
   - Add request size limits

### Phase 2: Security Operations (Deploy with Monitoring)

5. **Implement Comprehensive Logging** (HIGH, A09.1, A09.2)
   - Log all API access with IP, user agent, timestamp
   - Log authentication failures
   - Log rate limit violations

6. **Set Up Alerting** (HIGH, A09.4)
   - Alert on auth failures, errors, anomalies
   - Integrate with monitoring platform (Prometheus, Grafana)

7. **Tighten CORS Configuration** (MEDIUM, A05.2)
   - Restrict methods to GET/POST/OPTIONS
   - Restrict headers to Content-Type, Authorization, X-API-Key

8. **Change Default API Key** (MEDIUM, A05.1)
   - Generate strong random API key for production
   - Document rotation procedure

### Phase 3: Ongoing Security Maintenance

9. **Implement Dependency Scanning** (MEDIUM, A06.2)
   - Add `pip-audit` or `safety` to CI/CD
   - Create SBOM for each release

10. **Implement Per-Client API Keys** (MEDIUM, A07.1)
    - Allow granular access control
    - Enable individual client revocation

---

## Conclusion

The DuckPools API has a solid foundation with proper use of Pydantic validation, FastAPI best practices, and blockchain immutability for critical data. However, several security gaps must be addressed before production deployment.

**Must Fix Before Production**:
- Rate limiting
- Security headers
- Authentication on user data endpoints
- Input validation strengthening

**Should Fix Soon**:
- Comprehensive logging
- Alerting
- CORS hardening
- API key rotation

---

**Auditor**: Penetration Tester Jr (17fe45e7-3b47-48b5-897a-59d6f7e9ba97)
**Reviewer**: Security Senior (EM - Security & Compliance)
**Status**: Ready for review
**Related Issues**: 
- #4d098eb3-808e-4caf-85af-af9d9e46eb21 (Security headers verification)
