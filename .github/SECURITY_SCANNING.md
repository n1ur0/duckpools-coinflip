# Security Scanning CI/CD

This document describes the security scanning pipeline implemented for DuckPools.

## Overview

The security scanning pipeline runs automatically on:
- Every push to `main`, `dev`, `feature/*`, and `fix/*` branches
- Every pull request targeting `main` or `dev` branches
- Daily at 2:00 AM UTC (scheduled run)

## Security Checks

### 1. Dependency Audit
- **npm audit**: Scans frontend dependencies for known vulnerabilities
- **pip safety**: Scans Python backend dependencies for known vulnerabilities

### 2. Secret Detection
- **Gitleaks**: Scans for hardcoded secrets, API keys, and sensitive information
- **TruffleHog**: Advanced secret detection with verified secrets feature

### 3. Static Analysis
- **Semgrep**: Semantic code analysis for security vulnerabilities
- **CodeQL**: GitHub's advanced static analysis engine
- **Bandit**: Python-specific security linter for the backend

### 4. Container Security
- **Trivy**: Vulnerability scanner for Docker containers (runs only when Docker-related changes are detected)

## Configuration Files

### `.gitleaks.toml`
Custom Gitleaks configuration with rules specific to DuckPools:
- AWS credentials detection
- Ergo blockchain secrets (addresses, mnemonics, token IDs)
- Generic API keys and secrets
- Database URLs and webhook URLs
- JWT tokens

### Security Workflow
Located in `.github/workflows/security-scan.yml` and includes:
- Matrix strategy for parallel execution
- Artifact upload for reports
- Security summary generation
- Continue-on-error for non-blocking security checks

## Interpreting Results

### Dependency Audit Results
- **npm audit**: Check job logs for vulnerability details
- **pip safety**: Download `safety-report` artifact for detailed report

### Secret Detection Results
- Check job logs for any detected secrets
- All detected secrets should be immediately rotated and removed from code
- Update `.gitleaks.toml` if legitimate false positives are found

### Static Analysis Results
- **Semgrep**: Check job logs or Semgrep dashboard
- **CodeQL**: Check GitHub Security tab
- **Bandit**: Download `bandit-report` artifact for Python security issues

### Container Security Results
- Check GitHub Security tab for Trivy scan results
- Review both OS package and application dependencies

## Security Response Process

### Critical/High Severity Findings
1. Immediately stop any deployment if affected code is in production
2. Create a security issue with `priority:critical` label
3. Fix the vulnerability in a dedicated branch
4. Run security scan to verify fix
5. Deploy fix with appropriate testing

### Medium/Low Severity Findings
1. Create a security issue with appropriate priority label
2. Schedule fix for next sprint
3. Track in security backlog

### False Positives
1. Update appropriate configuration file (`.gitleaks.toml`, etc.)
2. Add specific allowlist entries with comments
3. Ensure allowlist is as specific as possible

## Required Secrets

The following repository secrets should be configured:

- `SEMGREP_APP_TOKEN`: For Semgrep publishing (optional, but recommended)

## Best Practices

1. **Never commit secrets** to the repository
2. **Review security scan reports** regularly
3. **Update dependencies** frequently to minimize vulnerabilities
4. **Add security scanning** to your pull request checklist
5. **Use environment variables** for sensitive configuration
6. **Implement proper secret rotation** procedures

## Troubleshooting

### High False Positive Rate
1. Review `.gitleaks.toml` configuration
2. Add specific allowlist entries
3. Consider if pattern is too broad

### Slow Pipeline Performance
1. Security scans run in parallel where possible
2. Scheduled daily scans run when CI/CD is typically less busy
3. Consider splitting very large repositories

### Missing Security Context in PRs
1. Ensure `security` label is applied to security-related PRs
2. Add security team as CODEOWNERS for security files
3. Require security scan passing before merging

## Continuous Improvement

The security scanning pipeline should be regularly reviewed and improved:

1. Add new security tools as needed
2. Update rule configurations for new threats
3. Monitor for new vulnerability patterns
4. Adjust based on team feedback

For questions or improvements to this security pipeline, please contact the Security & Compliance team.