# Security Policy

## Version and Support

| Version | Status | Supported Until |
|---------|--------|-----------------|
| v1.0.x  | ✅ Active | 2026-12-31 |
| < v1.0  | ❌ EOL | 2026-03-31 |

---

## Reporting a Vulnerability

### Responsible Disclosure

If you discover a security vulnerability in DuckPools Coinflip, **please do NOT open a public issue or discussion**.

### How to Report

**Email:** security@duckpools.io

**Include in your report:**

1. **Description**
   - Clear summary of the vulnerability
   - Affected components (smart contract, backend, frontend, etc.)

2. **Impact**
   - Potential financial impact (if any)
   - Scope of affected users
   - Risk level (critical/high/medium/low)

3. **Proof of Concept**
   - Steps to reproduce (without exploiting on mainnet)
   - Code examples or screenshots
   - Test transactions (on testnet only, never mainnet)

4. **Proposed Fix**
   - Suggested remediation (if available)
   - Code patches (optional)

### Response Timeline

- **Acknowledgment:** Within 24 hours
- **Initial Assessment:** Within 48 hours
- **Fix Timeline:** Within 7-14 days (depending on severity)
- **Public Disclosure:** After fix is deployed and verified

### Communication

- We will keep you informed of progress
- You'll be credited in the security advisory (if desired)
- Bounty payment (if eligible) within 30 days of fix deployment

---

## Bug Bounty Program

### Rewards

We offer rewards for responsible disclosure of security vulnerabilities:

| Severity | Reward Range | Criteria |
|----------|--------------|----------|
| **Critical** | $2,000 - $5,000 | Direct financial loss possible, affects all users |
| **High** | $500 - $2,000 | Significant impact, affects many users |
| **Medium** | $100 - $500 | Limited impact, requires user interaction |
| **Low** | $50 - $100 | Minor issue, information disclosure |

### Bounty Eligibility

To be eligible for a bounty:

1. **First to Report**: First valid report receives bounty
2. **No Exploitation**: Vulnerability not exploited on mainnet
3. **Clear Impact**: Demonstration of potential harm
4. **Detailed Report**: Complete reproduction steps
5. **Responsible Disclosure**: Reported via proper channels

### Ineligible Issues

The following are NOT eligible for bounties:

- Issues already known to us (see advisories below)
- Physical attacks on infrastructure
- Social engineering attacks
- Third-party vulnerabilities (Ergo protocol, Nautilus, etc.)
- Theoretical vulnerabilities without proof of concept
- UI/UX issues without security impact
- Typos, grammatical errors, etc.

---

## Security Best Practices

### For Users

1. **Never Share Private Keys**
   - Your wallet private key controls your funds
   - Never give it to anyone, including support staff

2. **Verify Transactions**
   - Always check transaction details before signing
   - Verify addresses on Ergo Explorer
   - Double-check amounts (especially large bets)

3. **Keep Software Updated**
   - Use latest Nautilus wallet version
   - Keep browser updated
   - Only access via official URLs (duckpools.io)

4. **Use Hardware Wallets** (recommended for large amounts)
   - Ledger, Trezor, or other hardware wallets
   - Additional layer of security

5. **Enable 2FA** (where available)
   - On email accounts
   - On wallet software that supports it

### For Developers

1. **Code Review**
   - All code must be reviewed before merging
   - Security-sensitive changes require 2 reviewers
   - Smart contract changes require additional audit

2. **Testing**
   - Unit tests for all critical paths
   - Integration tests on testnet
   - Security testing for financial operations

3. **Secrets Management**
   - Never commit secrets to Git
   - Use environment variables for sensitive data
   - Rotate API keys regularly

4. **Dependencies**
   - Keep dependencies updated
   - Review security advisories weekly
   - Use Dependabot for automated alerts

5. **Access Control**
   - Principle of least privilege
   - Separate dev/staging/production environments
   - Audit access logs regularly

### For Operators

1. **Infrastructure Security**
   - Firewall rules (restrict ports)
   - Regular security updates
   - Intrusion detection system

2. **Monitoring**
   - Real-time alerting for anomalies
   - Log aggregation and analysis
   - Regular security audits

3. **Backup**
   - Daily database backups
   - Encrypted backup storage
   - Tested restore procedures

4. **Incident Response**
   - Documented response procedures
   - Team contact list
   - Escalation paths

---

## Security Architecture

### Threat Model

```
┌─────────────────────────────────────────────────────────────┐
│                     Threat Vectors                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐ │
│  │   Smart      │    │   Backend    │    │   Frontend   │ │
│  │  Contracts   │───▶│     API      │───▶│     UI       │ │
│  │              │    │              │    │              │ │
│  │ - RNG exploit│    │ - Injection  │    │ - XSS        │ │
│  │ - Logic bug  │    │ - Auth bypass│    │ - Phishing   │ │
│  │ - Reentrancy │    │ - DoS        │    │ - CSRF       │ │
│  └──────────────┘    └──────────────┘    └──────────────┘ │
│         │                    │                    │        │
│         └────────────────────┼────────────────────┘        │
│                              │                              │
│  ┌───────────────────────────▼─────────────────────────┐   │
│  │                   Blockchain Layer                  │   │
│  │  - 51% attack (unlikely)                            │   │
│  │  - Double-spend                                    │   │
│  │  - Chain reorg                                     │   │
│  └───────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Mitigation Strategies

#### Smart Contract Security

1. **Commit-Reveal RNG**
   - Prevents front-running
   - Uses block hash for randomness
   - Verified on-chain

2. **Payout Limits**
   - Maximum bet size enforced
   - House bankroll checks
   - Prevents draining attacks

3. **Timeout Protection**
   - Bets expire after timeout
   - Refund mechanism
   - Prevents stuck funds

4. **Reentrancy Protection**
   - Non-recursive design
   - State updates before transfers
   - Verified by audit

#### Backend Security

1. **API Authentication**
   - API key required for sensitive operations
   - Rate limiting
   - IP whitelist (optional)

2. **Input Validation**
   - Pydantic schemas for all inputs
   - Type checking
   - Range validation

3. **SQL Injection Prevention**
   - Parameterized queries
   - ORM usage
   - Input sanitization

4. **CORS Protection**
   - Whitelisted origins only
   - Proper credentials handling
   - Preflight validation

#### Frontend Security

1. **XSS Prevention**
   - React auto-escaping
   - Content Security Policy (CSP)
   - DOMPurify for HTML

2. **CSRF Protection**
   - SameSite cookies
   - Anti-CSRF tokens
   - Referrer checking

3. **Secure Communication**
   - HTTPS only in production
   - HSTS headers
   - Certificate pinning (future)

4. **Wallet Security**
   - EIP-12 protocol (secure signing)
   - Transaction preview
   - Address verification

---

## Known Security Issues

### Addressed Issues

| ID | Date | Severity | Description | Status |
|----|------|----------|-------------|--------|
| N/A | - | - | No known issues at this time | - |

### Past Advisories

No security advisories published yet (v1.0 is in development).

---

## Compliance and Legal

### Regulatory Considerations

**Jurisdiction:** We operate in crypto-friendly jurisdictions. Geo-blocking is implemented for restricted regions.

**KYC/AML:**
- Player pseudonymity (no KYC required for betting)
- LP providers may require KYC (future)
- Transaction monitoring for suspicious patterns

**Licensing:**
- Operating under relevant gambling licenses
- Compliance with local regulations
- Regular audits and reporting

### Data Privacy

**Data Collected:**
- Wallet addresses (public blockchain data)
- IP addresses (for rate limiting, logs)
- Browser/user agent (for analytics)

**Data Retention:**
- Transaction logs: Permanent (on-chain)
- API logs: 30 days
- Analytics data: 90 days

**Data Access:**
- Only authorized personnel can access logs
- GDPR/CCPA compliant where applicable
- Users can request data deletion (except on-chain data)

---

## Security Audits

### Completed Audits

| Date | Auditor | Scope | Report |
|------|---------|-------|--------|
| TBD | TBD | Smart contracts, backend, frontend | TBD |

### Audit Checklist

Our security audit covers:

- [ ] Smart contract logic verification
- [ ] Reentrancy attack analysis
- [ ] RNG security assessment
- [ ] Backend API security
- [ ] Frontend XSS/CSRF testing
- [ ] Infrastructure review
- [ ] Dependency vulnerability scan
- [ ] Penetration testing
- [ ] Compliance review

---

## Incident Response

### Incident Categories

| Severity | Description | Response Time |
|----------|-------------|---------------|
| P0 | Critical: Active exploit, funds at risk | Immediate (< 1 hour) |
| P1 | High: Security bug, no known exploit | 24 hours |
| P2 | Medium: Security issue, low impact | 72 hours |
| P3 | Low: Minor security concern | 1 week |

### Response Team

| Role | Contact |
|------|---------|
| Security Lead | security@duckpools.io |
| CTO | cto@duckpools.io |
| DevOps Lead | devops@duckpools.io |
| Smart Contract Lead | contracts@duckpools.io |

### Response Procedure

1. **Triage (0-1 hour)**
   - Confirm incident
   - Assess severity
   - Assemble response team

2. **Containment (0-24 hours)**
   - Mitigate active threat
   - Stop vulnerable services if needed
   - Preserve evidence

3. **Investigation (24-72 hours)**
   - Root cause analysis
   - Impact assessment
   - Determine exploit scope

4. **Remediation (24 hours-14 days)**
   - Develop fix
   - Test thoroughly
   - Deploy to testnet first

5. **Recovery**
   - Deploy fix to production
   - Monitor for issues
   - Update users

6. **Post-Mortem (within 1 week)**
   - Document incident
   - Identify lessons learned
   - Update procedures

---

## Additional Resources

### Tools

- [Slither](https://github.com/crytic/slither) - Smart contract static analysis
- [PyCharm Security](https://www.jetbrains.com/pycharm/) - Python security analysis
- [ESLint Security Plugin](https://github.com/nodesecurity/eslint-plugin-security) - JS security linting
- [OWASP ZAP](https://www.zaproxy.org/) - Web app penetration testing

### Learning

- [Ergo Security Best Practices](https://ergoplatform.org/en/developers/security/)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Smart Contract Security](https://consensys.github.io/smart-contract-best-practices/)

### Community

- [Ergo Forum](https://www.ergoforum.org/)
- [DuckPools Discord](https://discord.gg/duckpools)
- [Security Research](https://github.com/ducks/duckpools-coinflip/security)

---

## Questions?

For security-related questions:

- **General security:** security@duckpools.io
- **Bug bounty:** security@duckpools.io
- **Partnership:** partnerships@duckpools.io
- **Media:** press@duckpools.io

---

**Document Version:** 1.0
**Last Updated:** 2026-03-27
**Next Review:** 2026-06-27
**Maintained by:** Security Team
