# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- GitHub repository setup documentation (GITHUB_SETUP.md)
- Comprehensive deployment guide (DEPLOYMENT.md)
- Security policy and bug bounty program (SECURITY.md)
- Enhanced .gitignore for production environments

### Changed
- Improved documentation structure
- Better organization of technical guides

### Fixed
- N/A

### Security
- N/A

---

## [1.0.0] - 2026-03-27

### Added
- Initial MVP release of DuckPools Coinflip protocol
- Smart Contracts:
  - PendingBet contract with commit-reveal scheme
  - GameState contract for RNG state management
  - LP pool contract for liquidity providers
- Backend API:
  - FastAPI server with 24 endpoints
  - Bet placement, revelation, and resolution
  - Pool state management and LP pool operations
  - Player statistics and leaderboard
  - WebSocket support for real-time bet updates
- Frontend:
  - React 18 + TypeScript + Vite 5
  - Nautilus wallet integration (EIP-12)
  - Bet form with commit-reveal flow
  - Game history with statistics
  - Leaderboard and player stats dashboard
  - LP pool deposit/withdraw interface
  - Compensation points display
- Off-chain Bot:
  - Automatic bet monitoring and resolution
  - RNG calculation using block hashes
  - House edge application (3%)
  - Expired bet refund mechanism
- Infrastructure:
  - Docker support via docker-compose.yml
  - PM2 process management
  - Nginx configuration for production
  - Comprehensive documentation
- Documentation:
  - README with quick start guide
  - Architecture overview
  - Ergo concepts guide
  - Getting started guide
  - Contributing guidelines

### Changed
- N/A (initial release)

### Fixed
- N/A (initial release)

### Security
- Commit-reveal RNG prevents front-running
- Input validation on all API endpoints
- CORS protection for cross-origin requests
- Proper environment variable handling for secrets

---

## [0.9.0] - 2026-03-20 (Development Only)

### Added
- Initial smart contract development
- Basic bet flow implementation
- Nautilus wallet prototype
- Ergo node integration

### Changed
- N/A

### Fixed
- N/A

---

## Version Format

**Format:** `MAJOR.MINOR.PATCH`

- **MAJOR**: Incompatible API changes, protocol-breaking changes
- **MINOR**: Backwards-compatible functionality additions
- **PATCH**: Backwards-compatible bug fixes

---

## Release Process

1. **Create release branch**: `git checkout -b release/vX.Y.Z`
2. **Update version**: Update version in package.json and backend config
3. **Update CHANGELOG**: Add release notes under new version
4. **Create PR**: Submit PR to `main` branch
5. **Review & Merge**: Get approval and merge
6. **Tag release**: `git tag -a vX.Y.Z -m "Release vX.Y.Z"`
7. **Push tag**: `git push origin vX.Y.Z`
8. **Deploy**: Deploy to production
9. **Announce**: Update users via Discord and social media

---

## Deprecation Policy

We will maintain backwards compatibility for at least **one major version**.

When deprecating features:
1. Mark as deprecated in documentation
2. Add deprecation warnings in code
3. Provide migration guide
4. Remove in next major version

---

## Migration Guides

### Upgrading from v0.9.0 to v1.0.0

No migration needed - v1.0.0 is the first production release.

---

## Contributors

- **DuckPools Team** - Core development
- **Community contributors** - Bug reports, feature requests, documentation

---

## Questions?

For questions about releases:
- Check [GitHub Issues](https://github.com/ducks/duckpools-coinflip/issues)
- Join [DuckPools Discord](https://discord.gg/duckpools)
- Contact: team@duckpools.io

---

**Last Updated:** 2026-03-27
**Maintained by:** DuckPools Team
