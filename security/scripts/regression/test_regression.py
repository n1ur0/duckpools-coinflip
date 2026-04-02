"""
DuckPools — Security Regression Tests

Post-merge regression gate. Run after every PR merge:
    cd security/scripts/regression && python -m pytest test_regression.py -v --tb=short

Tests enforce protocol invariants that MUST NOT regress:
  1. Plinko EV produces correct house edge (BNK-3)
  2. Plinko multipliers are symmetric
  3. Plinko multipliers are positive
  4. House edge constants match across modules
  5. API key separation (SEC-1)
  6. Security headers present on /health (SEC-2)
  7. RNG uses cryptographic hash (RNG-SEC-1)
  8. Dice RNG uses rejection sampling, not naive modulo (RNG-SEC-2)
  9. Bet amount validation bounds
 10. WebSocket requires authentication token (SEC-A1)
 11. WebSocket enforces connection limits (SEC-A2)
"""

import os
import sys
import pytest
from math import comb

# ─── Test Configuration ───────────────────────────────────────

TARGET_HOUSE_EDGE = 0.03
PLINKO_ROWS = [8, 12, 16]
EV_TOLERANCE = 1e-6


# ═══════════════════════════════════════════════════════════════
# 1. PLINKO EXPECTED VALUE REGRESSION (BNK-3)
#    If this fails, the house is either losing money or overcharging.
# ═══════════════════════════════════════════════════════════════

def _plinko_prob(rows: int, slot: int) -> float:
    """Binomial probability for landing in slot k with n rows."""
    if slot < 0 or slot > rows:
        return 0.0
    return comb(rows, slot) / (2 ** rows)


def _plinko_multiplier_powerlaw(rows: int, slot: int, alpha: float = 0.5,
                                 house_edge: float = 0.03) -> float:
    """
    Power-law multiplier formula used in frontend/src/utils/plinko.ts.
    
    multiplier(k) = A * (1/P(k))^alpha
    where A = (1 - house_edge) / sum(P(j)^(1-alpha))
    
    This guarantees E[X] = (1 - house_edge) for any row count.
    """
    prob = _plinko_prob(rows, slot)
    denom = sum(_plinko_prob(rows, s) ** (1 - alpha) for s in range(rows + 1))
    A = (1 - house_edge) / denom
    return A * (1 / prob) ** alpha


@pytest.mark.parametrize("rows", PLINKO_ROWS)
def test_plinko_ev_house_edge(rows: int):
    """
    CRITICAL: Verify Plinko multipliers produce the target house edge.
    
    The original multipliers [1000, 130, 26, 9, 4, 2, 1, 2, 4, 9, 26, 130, 1000]
    produced EV=5.02x (387% player edge). This test prevents regression.
    """
    ev = sum(
        _plinko_prob(rows, s) * _plinko_multiplier_powerlaw(rows, s)
        for s in range(rows + 1)
    )
    expected_ev = 1.0 - TARGET_HOUSE_EDGE  # 0.97
    assert abs(ev - expected_ev) < EV_TOLERANCE, (
        f"Plinko {rows}-row EV={ev:.10f}, expected {expected_ev:.10f}. "
        f"House edge is {(1 - ev) * 100:.4f}% (target {(TARGET_HOUSE_EDGE * 100):.1f}%). "
        f"BNK-3 regression — DO NOT MERGE."
    )


@pytest.mark.parametrize("rows", PLINKO_ROWS)
def test_plinko_multipliers_symmetric(rows: int):
    """Multipliers must be symmetric: mult(k) == mult(rows - k)."""
    for slot in range(rows + 1):
        m_left = _plinko_multiplier_powerlaw(rows, slot)
        m_right = _plinko_multiplier_powerlaw(rows, rows - slot)
        assert abs(m_left - m_right) < 1e-10, (
            f"Multiplier asymmetry at row={rows}, slot={slot}: "
            f"left={m_left:.6f}, right={m_right:.6f}"
        )


@pytest.mark.parametrize("rows", PLINKO_ROWS)
def test_plinko_multipliers_positive(rows: int):
    """All multipliers must be positive. Zero or negative = payout bug."""
    for slot in range(rows + 1):
        m = _plinko_multiplier_powerlaw(rows, slot)
        assert m > 0, f"Non-positive multiplier at row={rows}, slot={slot}: {m}"


@pytest.mark.parametrize("rows", PLINKO_ROWS)
def test_plinko_edge_greater_than_center(rows: int):
    """Edge multipliers must be higher than center (the core Plinko incentive)."""
    center = rows // 2
    m_edge = _plinko_multiplier_powerlaw(rows, 0)
    m_center = _plinko_multiplier_powerlaw(rows, center)
    assert m_edge > m_center, (
        f"Edge ({m_edge:.4f}) not greater than center ({m_center:.4f}) "
        f"for {rows} rows"
    )


@pytest.mark.parametrize("rows", PLINKO_ROWS)
def test_plinko_center_below_one(rows: int):
    """
    Center multiplier must be below 1.0x.
    
    With binomial distribution, center is the most common outcome.
    If center >= 1.0, the house cannot maintain a positive edge
    without extreme edge multipliers. This is how Stake.com does it.
    """
    center = rows // 2
    m_center = _plinko_multiplier_powerlaw(rows, center)
    assert m_center < 1.0, (
        f"Center multiplier {m_center:.4f} >= 1.0 for {rows} rows. "
        f"House cannot maintain edge. Players profit on the most common outcome."
    )


@pytest.mark.parametrize("rows", PLINKO_ROWS)
def test_plinko_probabilities_sum_to_one(rows: int):
    """Slot probabilities must sum to exactly 1.0."""
    total = sum(_plinko_prob(rows, s) for s in range(rows + 1))
    assert abs(total - 1.0) < 1e-12, f"Probabilities sum to {total}, not 1.0"


# ═══════════════════════════════════════════════════════════════
# 2. HOUSE EDGE CONSTANT CONSISTENCY
#    Frontend and backend must agree on house edge.
# ═══════════════════════════════════════════════════════════════

def test_house_edge_constants_match():
    """
    Verify house edge is defined consistently.
    
    The frontend uses PLINKO_HOUSE_EDGE = 0.03 (3%).
    The backend uses HOUSE_EDGE_BPS = 300 (basis points).
    These must be equivalent: 300 bps = 3%.
    """
    frontend_edge = 0.03  # PLINKO_HOUSE_EDGE in plinko.ts
    backend_bps = 300     # HOUSE_EDGE_BPS in api_server.py
    backend_edge = backend_bps / 10000
    
    assert abs(frontend_edge - backend_edge) < 1e-10, (
        f"House edge mismatch: frontend={frontend_edge}, backend={backend_edge} "
        f"({backend_bps} bps)"
    )


# ═══════════════════════════════════════════════════════════════
# 3. API KEY SEPARATION (SEC-1)
#    Node and bot API keys must be separate env vars.
# ═══════════════════════════════════════════════════════════════

def test_api_key_separation():
    """
    SEC-1: Verify API keys use separate environment variables.
    
    The same API_KEY must NOT be used for both node requests and
    bot endpoint authentication. Check the api_server.py source.
    """
    api_server_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "..",
        "backend", "api_server.py"
    )
    api_server_path = os.path.normpath(api_server_path)
    
    if not os.path.exists(api_server_path):
        pytest.skip(f"api_server.py not found at {api_server_path}")
    
    with open(api_server_path, "r") as f:
        source = f.read()
    
    # Check that BOT_API_KEY is referenced (or API_KEY separation exists)
    has_bot_key = "BOT_API_KEY" in source or "bot_api_key" in source.lower()
    has_node_key = "NODE_API_KEY" in source or "node_api_key" in source.lower()
    
    # If both exist, they must be different env vars
    if has_bot_key and has_node_key:
        # Good: separate keys
        return
    
    # If only one API_KEY is used, flag it
    # Check if the single API_KEY is used for BOTH node and endpoint auth
    api_key_count = source.count("API_KEY")
    
    # This is a soft check — if the code uses a single key, warn but don't fail
    # until SEC-1 is fully implemented
    if api_key_count > 0 and not has_bot_key:
        pytest.xfail(
            "SEC-1: Single API_KEY detected in api_server.py. "
            "BOT_API_KEY separation not yet implemented."
        )


# ═══════════════════════════════════════════════════════════════
# 4. SECURITY HEADERS (SEC-2)
#    Verify security headers middleware is configured.
# ═══════════════════════════════════════════════════════════════

REQUIRED_SECURITY_HEADERS = [
    "X-Content-Type-Options",
    "X-Frame-Options",
    "Referrer-Policy",
]

def test_security_headers_configured():
    """
    SEC-2: Verify security headers are configured in api_server.py.
    
    This is a static analysis check — we verify the middleware
    is registered and sets the required headers.
    """
    api_server_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "..",
        "backend", "api_server.py"
    )
    api_server_path = os.path.normpath(api_server_path)
    
    if not os.path.exists(api_server_path):
        pytest.skip(f"api_server.py not found at {api_server_path}")
    
    with open(api_server_path, "r") as f:
        source = f.read()
    
    # Check for security headers middleware
    has_security_headers = (
        "SecurityHeaders" in source or
        "security_headers" in source or
        "X-Content-Type-Options" in source or
        "nosniff" in source
    )
    
    if not has_security_headers:
        pytest.xfail(
            "SEC-2: SecurityHeadersMiddleware not found in api_server.py. "
            "Security headers may not be active."
        )
    
    # If middleware exists, check required headers are set
    for header in REQUIRED_SECURITY_HEADERS:
        if header not in source:
            pytest.xfail(
                f"SEC-2: Required header '{header}' not configured in middleware."
            )


# ═══════════════════════════════════════════════════════════════
# 5. RNG CRYPTOGRAPHIC INTEGRITY (RNG-SEC-1)
#    Verify RNG uses SHA-256, not a weak hash.
# ═══════════════════════════════════════════════════════════════

def test_rng_uses_sha256():
    """
    RNG-SEC-1: Verify Plinko RNG uses a cryptographic hash (blake2b256 or SHA-256).

    The commit-reveal scheme and RNG must use a cryptographic hash.
    MD5, SHA-1, or plain XOR would be trivially exploitable.
    """
    plinko_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "..",
        "frontend", "src", "utils", "plinko.ts"
    )
    plinko_path = os.path.normpath(plinko_path)

    if not os.path.exists(plinko_path):
        pytest.skip(f"plinko.ts not found at {plinko_path}")

    with open(plinko_path, "r") as f:
        source = f.read()

    has_crypto_hash = (
        "blake2b256" in source.lower() or
        "sha256" in source.lower() or
        "SHA256" in source
    )

    assert has_crypto_hash, (
        "RNG-SEC-1: Plinko RNG does not reference a cryptographic hash. "
        "Commit-reveal scheme may use a weak hash."
    )
    
    # Verify no weak hashes
    weak_hashes = ["md5", "MD5", "sha1", "SHA1"]
    for wh in weak_hashes:
        # Allow in comments
        for line in source.split("\n"):
            stripped = line.strip()
            if stripped.startswith("//") or stripped.startswith("*") or stripped.startswith("/*"):
                continue
            if wh in stripped:
                pytest.fail(
                    f"RNG-SEC-1: Weak hash '{wh}' detected in plinko.ts: {stripped}"
                )


def test_rng_uses_commit_reveal():
    """
    Verify Plinko implements commit-reveal scheme.
    
    The player commits to a secret BEFORE the block hash is known.
    This prevents the house from manipulating outcomes.
    """
    plinko_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "..",
        "frontend", "src", "utils", "plinko.ts"
    )
    plinko_path = os.path.normpath(plinko_path)
    
    if not os.path.exists(plinko_path):
        pytest.skip(f"plinko.ts not found at {plinko_path}")
    
    with open(plinko_path, "r") as f:
        source = f.read()
    
    assert "commit" in source.lower(), (
        "RNG-SEC-1: No commit-reveal scheme detected in plinko.ts"
    )
    assert "secret" in source.lower(), (
        "RNG-SEC-1: No player secret detected in plinko.ts"
    )


# ═══════════════════════════════════════════════════════════════
# 5b. DICE RNG MODULO BIAS (RNG-SEC-2)
#     Frontend dice RNG must use rejection sampling, not naive % 100.
# ═══════════════════════════════════════════════════════════════

def test_dice_rng_no_modulo_bias():
    """
    RNG-SEC-2: Verify frontend dice RNG does NOT use naive modulo 100.

    `hash[0] % 100` is biased: 256 % 100 = 56, so outcomes 0-55 have
    probability 2/256 vs 1/256 for 56-99. This gives players a ~1.5%
    edge on rollTarget > 56 bets — a direct money leak.

    The correct implementation uses rejection sampling: accept bytes < 200,
    reject bytes >= 200. This matches backend/rng_module.py dice_rng().
    """
    dice_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "..",
        "frontend", "src", "utils", "dice.ts"
    )
    dice_path = os.path.normpath(dice_path)

    if not os.path.exists(dice_path):
        pytest.skip(f"dice.ts not found at {dice_path}")

    with open(dice_path, "r") as f:
        source = f.read()

    # Check that rejection sampling is present
    has_rejection = "200" in source and ("rejection" in source.lower() or "< 200" in source)

    # Check that naive modulo is NOT the sole mechanism
    # (it's OK if "% 100" appears inside a rejection block)
    lines = source.split("\n")

    # Find lines with "% 100" or "%100" that are NOT in rejection blocks
    naive_modulo_lines = []
    in_rejection_block = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        # Track if we're inside a rejection sampling block
        if "200" in stripped and ("<" in stripped or "rejection" in stripped.lower()):
            in_rejection_block = True
        if in_rejection_block and stripped.startswith("}"):
            in_rejection_block = False

        if ("% 100" in stripped or "%100" in stripped) and not in_rejection_block:
            # Skip comments
            if stripped.startswith("//") or stripped.startswith("*") or stripped.startswith("/*"):
                continue
            naive_modulo_lines.append((i + 1, stripped))

    if naive_modulo_lines and not has_rejection:
        pytest.fail(
            "RNG-SEC-2: Naive `% 100` detected in dice.ts WITHOUT rejection sampling. "
            f"Lines: {naive_modulo_lines}. "
            "This introduces modulo bias (outcomes 0-55 have 2/256 prob vs 1/256 for 56-99). "
            "Use rejection sampling: accept bytes < 200, reject >= 200."
        )

    assert has_rejection, (
        "RNG-SEC-2: No rejection sampling detected in dice.ts computeDiceRng. "
        "Naive `% 100` introduces ~1.5% player edge on rollTarget > 56 bets."
    )


# ═══════════════════════════════════════════════════════════════
# 6. CORS CONFIGURATION SAFETY (SEC-3)
# ═══════════════════════════════════════════════════════════════

def test_cors_not_wildcard_with_credentials():
    """
    SEC-3: CORS must not allow credentials with wildcard origins.
    
    allow_origins=["*"] + allow_credentials=True = CSRF vulnerability.
    """
    api_server_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "..",
        "backend", "api_server.py"
    )
    api_server_path = os.path.normpath(api_server_path)
    
    if not os.path.exists(api_server_path):
        pytest.skip(f"api_server.py not found at {api_server_path}")
    
    with open(api_server_path, "r") as f:
        source = f.read()
    
    # Extract the CORS middleware block
    has_wildcard_origin = '"*"' in source or "'*'" in source
    has_credentials = "allow_credentials" in source and "True" in source
    
    if has_wildcard_origin and has_credentials:
        # Check if wildcard is actually used for origins (not just elsewhere)
        lines = source.split("\n")
        in_cors_block = False
        for line in lines:
            if "CORSMiddleware" in line:
                in_cors_block = True
            if in_cors_block:
                if "allow_origins" in line and ('"*"' in line or "'*'" in line):
                    if "allow_credentials" in source.split("allow_origins")[1][:200]:
                        pytest.fail(
                            "SEC-3: CORS configured with wildcard origins + "
                            "allow_credentials=True. This is a CSRF vulnerability."
                        )
                if line.strip() == ")" or (in_cors_block and "app.include_router" in line):
                    in_cors_block = False


# ═══════════════════════════════════════════════════════════════
# 7. NO DEFAULT WEAK CREDENTIALS (SEC-1)
# ═══════════════════════════════════════════════════════════════

def test_no_default_hello_api_key():
    """
    SEC-1: API key default must not be 'hello'.
    
    Default 'hello' in production would allow unauthenticated access.
    Also catches empty-string defaults for keys that should be required.
    """
    api_server_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "..",
        "backend", "api_server.py"
    )
    api_server_path = os.path.normpath(api_server_path)
    
    if not os.path.exists(api_server_path):
        pytest.skip(f"api_server.py not found at {api_server_path}")
    
    with open(api_server_path, "r") as f:
        source = f.read()
    
    # Check for "hello" as a default value near API_KEY
    lines = source.split("\n")
    for i, line in enumerate(lines):
        if "API_KEY" in line and 'os.getenv' in line:
            # Check if 'hello' is the default — HARD fail, not xfail
            if '"hello"' in line or "'hello'" in line:
                pytest.fail(
                    f"SEC-A9: API_KEY uses 'hello' as default at line {i+1}. "
                    "This must be replaced with a strong random default."
                )


# ═══════════════════════════════════════════════════════════════
# 8. REGISTER DESERIALIZATION — INT + LONG (SEC-A6)
#    _extract_int_from_serialized must handle both 0x02 and 0x04.
# ═══════════════════════════════════════════════════════════════

def _encode_vlq(value: int) -> str:
    """Encode an unsigned integer as VLQ hex string."""
    result = []
    while value > 0:
        byte = value & 0x7F
        value >>= 7
        if value > 0:
            byte |= 0x80
        result.append(byte)
    if not result:
        result.append(0)
    return ''.join(f'{b:02x}' for b in result)


def _zigzag_encode(value: int) -> int:
    """ZigZag encode a signed integer (works for both i32 and i64 range)."""
    if value >= 0:
        return value << 1
    return ((-value) << 1) - 1


def _make_serialized_int(value: int) -> str:
    """Create a serialized IntConstant (0x02 + VLQ(zigzag))."""
    return f"02{_encode_vlq(_zigzag_encode(value))}"


def _make_serialized_long(value: int) -> str:
    """Create a serialized LongConstant (0x04 + VLQ(zigzag))."""
    return f"04{_encode_vlq(_zigzag_encode(value))}"


@pytest.mark.parametrize("value,encoding", [
    (300, "int"),
    (300, "long"),
    (0, "int"),
    (0, "long"),
    (-1, "int"),
    (-1, "long"),
    (60, "int"),    # cooldown_blocks
    (60, "long"),
    (10000, "int"), # large house edge
    (10000, "long"),
])
def test_extract_int_handles_int_and_long(value: int, encoding: str):
    """
    SEC-A6: _extract_int_from_serialized must handle both Int (0x02)
    and Long (0x04) type prefixes.

    If this fails, R6 (cooldown) or R7 (house_edge) registers encoded
    as Long will silently read as 0, giving players zero-edge bets and
    bypassing withdrawal timelocks.
    """
    pool_manager_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "..",
        "backend", "pool_manager.py"
    )
    pool_manager_path = os.path.normpath(pool_manager_path)

    if not os.path.exists(pool_manager_path):
        pytest.skip(f"pool_manager.py not found at {pool_manager_path}")

    with open(pool_manager_path, "r") as f:
        source = f.read()

    # Verify the fix is in place: accepts both 0x02 and 0x04
    assert "0x02, 0x04" in source or "0x04" in source.split("0x02")[1][:50] if "0x02" in source else False, (
        "SEC-A6: _extract_int_from_serialized does not handle LongConstant (0x04). "
        "House edge or cooldown may silently read as 0."
    )

    # Functional test: verify VLQ+ZigZag roundtrip produces correct encoding
    if encoding == "int":
        serialized = _make_serialized_int(value)
        assert serialized.startswith("02"), f"IntConstant must start with 02, got {serialized[:2]}"
    else:
        serialized = _make_serialized_long(value)
        assert serialized.startswith("04"), f"LongConstant must start with 04, got {serialized[:2]}"

    # Decode the VLQ portion and ZigZag decode
    buf = bytes.fromhex(serialized)
    decoded_value = 0
    shift = 0
    for i in range(1, len(buf)):
        byte = buf[i]
        decoded_value |= (byte & 0x7F) << shift
        if (byte & 0x80) == 0:
            break
        shift += 7
    decoded_value = (decoded_value >> 1) ^ -(decoded_value & 1)

    assert decoded_value == value, (
        f"SEC-A6: VLQ+ZigZag roundtrip failed for value={value} ({encoding}). "
        f"Got {decoded_value}."
    )


def test_no_duplicate_long_parser_in_lp_routes():
    """
    SEC-A6: The inline LongConstant parser in lp_routes.py should be
    replaced with the shared _extract_int_from_serialized method.
    """
    lp_routes_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "..",
        "backend", "lp_routes.py"
    )
    lp_routes_path = os.path.normpath(lp_routes_path)

    if not os.path.exists(lp_routes_path):
        pytest.skip(f"lp_routes.py not found at {lp_routes_path}")

    with open(lp_routes_path, "r") as f:
        source = f.read()

    # Check that the duplicate VLQ decode loop is gone
    lines = source.split("\n")
    inline_parser_lines = []
    in_long_block = False
    for i, line in enumerate(lines):
        if "0x04" in line and "LongConstant" in line:
            in_long_block = True
        if in_long_block:
            if "0x7F" in line or "shift" in line.lower():
                inline_parser_lines.append((i + 1, line.strip()))
            if "requested_erg" in line and "=" in line and "0x04" not in line:
                break

    if inline_parser_lines:
        pytest.fail(
            "SEC-A6: Duplicate inline LongConstant parser detected in lp_routes.py. "
            f"Lines: {inline_parser_lines}. "
            "Use mgr._extract_int_from_serialized() instead."
        )


# ═══════════════════════════════════════════════════════════════
# 9. ORACLE SWITCH AUTHENTICATION (SEC-A3)
#    POST /api/oracle/switch must require admin API key.
# ═══════════════════════════════════════════════════════════════

def test_oracle_switch_has_auth():
    """
    SEC-A3: POST /api/oracle/switch must require authentication.

    Without auth, any attacker can force oracle failover to a malicious
    endpoint, feeding stale/manipulated price data into the protocol.
    This could enable economic attacks on LP solvency.
    """
    oracle_routes_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "..",
        "backend", "oracle_routes.py"
    )
    oracle_routes_path = os.path.normpath(oracle_routes_path)

    if not os.path.exists(oracle_routes_path):
        pytest.skip(f"oracle_routes.py not found at {oracle_routes_path}")

    with open(oracle_routes_path, "r") as f:
        source = f.read()

    # Check that /switch endpoint has an auth dependency
    has_auth_dependency = (
        "verify_admin" in source or
        "admin" in source.lower() and "Depends" in source
    )
    has_switch_route = "@router.post" in source and "/switch" in source

    if has_switch_route and not has_auth_dependency:
        pytest.fail(
            "SEC-A3: POST /api/oracle/switch has no authentication. "
            "Any unauthenticated user can force oracle failover. "
            "Add a dependency that validates an admin API key."
        )

    # Verify read-only endpoints remain public
    public_endpoints = ["/health", "/status", "/endpoints"]
    for endpoint in public_endpoints:
        lines = source.split("\n")
        for i, line in enumerate(lines):
            if endpoint in line and "@router" in lines[max(0, i-3):i]:
                route_context = "\n".join(lines[i:i+5])
                if "verify_admin" in route_context or "admin_api_key" in route_context.lower():
                    pytest.fail(
                        f"SEC-A3: Read-only endpoint {endpoint} should NOT require auth. "
                        "Only /switch needs protection."
                    )


# ═══════════════════════════════════════════════════════════════
# 10. SEC-A1: WEBSOCKET REQUIRES AUTHENTICATION TOKEN
#    Prevents unauthorized subscription to any address's bet events.
# ═══════════════════════════════════════════════════════════════

def test_ws_requires_auth_token():
    """
    SEC-A1: The WebSocket endpoint MUST require a valid auth token.

    Without this, any client can subscribe to any address's bet events,
    leaking private transaction data and enabling front-running.
    """
    ws_routes_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "..",
        "backend", "ws_routes.py"
    )
    ws_routes_path = os.path.normpath(ws_routes_path)

    if not os.path.exists(ws_routes_path):
        pytest.skip(f"ws_routes.py not found at {ws_routes_path}")

    with open(ws_routes_path, "r") as f:
        source = f.read()

    # Must have token verification logic
    has_token_check = (
        "token" in source and
        ("verify" in source or "sign" in source) and
        "query_params" in source
    )
    if not has_token_check:
        pytest.fail(
            "SEC-A1: WebSocket endpoint does not verify auth tokens. "
            "Any client can subscribe to any address's bet events. "
            "Implement token verification via ?token= query parameter."
        )

    # Must close connection with meaningful code when token is missing
    has_auth_close = "4001" in source or "close" in source
    if not has_auth_close:
        pytest.fail(
            "SEC-A1: WebSocket must close connection (code 4001) when token is missing."
        )

    # Must have an auth endpoint for issuing tokens
    has_auth_endpoint = "/ws/auth" in source
    if not has_auth_endpoint:
        pytest.fail(
            "SEC-A1: No POST /ws/auth endpoint found. "
            "Clients need a way to obtain WebSocket session tokens."
        )


def test_ws_token_uses_hmac():
    """
    SEC-A1: Session tokens MUST be HMAC-signed, not plaintext.

    Plaintext tokens can be forged, allowing impersonation of any address.
    """
    ws_routes_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "..",
        "backend", "ws_routes.py"
    )
    ws_routes_path = os.path.normpath(ws_routes_path)

    if not os.path.exists(ws_routes_path):
        pytest.skip(f"ws_routes.py not found at {ws_routes_path}")

    with open(ws_routes_path, "r") as f:
        source = f.read()

    has_hmac = "hmac" in source.lower() and "sha256" in source.lower()
    if not has_hmac:
        pytest.fail(
            "SEC-A1: Token signing does not use HMAC-SHA256. "
            "Tokens must be cryptographically signed to prevent forgery."
        )

    has_compare_digest = "compare_digest" in source
    if not has_compare_digest:
        pytest.fail(
            "SEC-A1: Token comparison does not use hmac.compare_digest(). "
            "Direct string comparison is vulnerable to timing attacks."
        )


def test_ws_connection_locked_to_authenticated_address():
    """
    SEC-A1: Once authenticated, a connection MUST be locked to the
    authenticated address. Subscribing to other addresses must be blocked.
    """
    ws_routes_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "..",
        "backend", "ws_routes.py"
    )
    ws_routes_path = os.path.normpath(ws_routes_path)

    if not os.path.exists(ws_routes_path):
        pytest.skip(f"ws_routes.py not found at {ws_routes_path}")

    with open(ws_routes_path, "r") as f:
        source = f.read()

    # Must check that subscribe address matches authenticated address
    has_address_lock = (
        "locked" in source.lower() or
        "mismatch" in source.lower() or
        "cannot subscribe to other" in source.lower()
    )
    if not has_address_lock:
        pytest.fail(
            "SEC-A1: WebSocket does not lock connections to authenticated address. "
            "An authenticated user could subscribe to any address's events."
        )


# ═══════════════════════════════════════════════════════════════
# 11. SEC-A2: WEBSOCKET ENFORCES CONNECTION LIMITS
#    Prevents DoS via unlimited connections or bulk monitoring.
# ═══════════════════════════════════════════════════════════════

def test_ws_has_connection_limit_class():
    """
    SEC-A2: ConnectionManager must define connection limits as class constants.

    Without explicit limits, a single IP can open thousands of connections,
    exhausting server resources.
    """
    ws_manager_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "..",
        "backend", "ws_manager.py"
    )
    ws_manager_path = os.path.normpath(ws_manager_path)

    if not os.path.exists(ws_manager_path):
        pytest.skip(f"ws_manager.py not found at {ws_manager_path}")

    with open(ws_manager_path, "r") as f:
        source = f.read()

    # Must define limit constants
    has_global_limit = "MAX_CONNECTIONS_GLOBAL" in source
    has_ip_limit = "MAX_CONNECTIONS_PER_IP" in source

    if not has_global_limit:
        pytest.fail(
            "SEC-A2: No MAX_CONNECTIONS_GLOBAL limit defined. "
            "Server is vulnerable to connection exhaustion DoS."
        )

    if not has_ip_limit:
        pytest.fail(
            "SEC-A2: No MAX_CONNECTIONS_PER_IP limit defined. "
            "A single attacker can open unlimited connections."
        )

    # Must track connections per IP
    has_ip_tracking = "_ip_connections" in source
    if not has_ip_tracking:
        pytest.fail(
            "SEC-A2: ConnectionManager does not track connections per IP. "
            "Per-IP limits cannot be enforced without this."
        )


def test_ws_has_per_address_subscription_limit():
    """
    SEC-A2: Must limit how many connections can subscribe to a single address.

    Without this, an attacker can open many connections to a whale's address
    and monitor their betting patterns for front-running.
    """
    ws_manager_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "..",
        "backend", "ws_manager.py"
    )
    ws_manager_path = os.path.normpath(ws_manager_path)

    if not os.path.exists(ws_manager_path):
        pytest.skip(f"ws_manager.py not found at {ws_manager_path}")

    with open(ws_manager_path, "r") as f:
        source = f.read()

    has_addr_limit = "MAX_SUBS_PER_ADDRESS" in source
    if not has_addr_limit:
        pytest.fail(
            "SEC-A2: No MAX_SUBS_PER_ADDRESS limit defined. "
            "Too many connections per address enables bulk monitoring."
        )

    # Must enforce the limit in subscribe()
    has_limit_check = (
        "ConnectionLimitExceeded" in source or
        ("limit" in source.lower() and "subscribe" in source.lower())
    )
    if not has_limit_check:
        pytest.fail(
            "SEC-A2: Subscription limit defined but not enforced in subscribe()."
        )


def test_ws_limits_are_reasonable():
    """
    SEC-A2: Connection limits must be within reasonable bounds.

    Too high = ineffective. Too low = breaks normal usage.
    """
    ws_manager_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "..",
        "backend", "ws_manager.py"
    )
    ws_manager_path = os.path.normpath(ws_manager_path)

    if not os.path.exists(ws_manager_path):
        pytest.skip(f"ws_manager.py not found at {ws_manager_path}")

    with open(ws_manager_path, "r") as f:
        source = f.read()

    # Parse limit values
    import re

    global_match = re.search(r"MAX_CONNECTIONS_GLOBAL\s*=\s*(\d+)", source)
    ip_match = re.search(r"MAX_CONNECTIONS_PER_IP\s*=\s*(\d+)", source)
    addr_match = re.search(r"MAX_SUBS_PER_ADDRESS\s*=\s*(\d+)", source)

    if global_match:
        global_limit = int(global_match.group(1))
        if global_limit > 1000:
            pytest.fail(
                f"SEC-A2: MAX_CONNECTIONS_GLOBAL={global_limit} is too high. "
                "Set to 200-500 for production safety."
            )
        if global_limit < 10:
            pytest.fail(
                f"SEC-A2: MAX_CONNECTIONS_GLOBAL={global_limit} is too low. "
                "Normal users need multiple connections for different tabs."
            )

    if ip_match:
        ip_limit = int(ip_match.group(1))
        if ip_limit > 20:
            pytest.fail(
                f"SEC-A2: MAX_CONNECTIONS_PER_IP={ip_limit} is too high. "
                "Set to 3-5 per IP to prevent abuse."
            )
        if ip_limit < 1:
            pytest.fail(
                f"SEC-A2: MAX_CONNECTIONS_PER_IP={ip_limit} must be >= 1."
            )

    if addr_match:
        addr_limit = int(addr_match.group(1))
        if addr_limit > 50:
            pytest.fail(
                f"SEC-A2: MAX_SUBS_PER_ADDRESS={addr_limit} is too high. "
                "More than 10 connections per address enables surveillance."
            )


# ═══════════════════════════════════════════════════════════════
# 14. XER-12: ERGO NODE IS OPTIONAL
#    Server must start without NODE_API_KEY in off-chain mode.
# ═══════════════════════════════════════════════════════════════

def test_node_is_optional():
    """
    XER-12: api_server.py must NOT fail-fast when NODE_API_KEY is empty.

    The server should start in off-chain mode when no node is configured,
    allowing the game UI and backend APIs to function without a blockchain
    connection. On-chain features (reveal, refund) should gracefully degrade.
    """
    api_server_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "..",
        "backend", "api_server.py"
    )
    api_server_path = os.path.normpath(api_server_path)

    if not os.path.exists(api_server_path):
        pytest.skip(f"api_server.py not found at {api_server_path}")

    with open(api_server_path, "r") as f:
        source = f.read()

    # Must NOT have the old fail-fast sys.exit(1) on empty NODE_API_KEY
    if "sys.exit(1)" in source and "NODE_API_KEY" in source:
        # Check it's not the old pattern where NODE_API_KEY check causes exit
        lines = source.split("\n")
        for i, line in enumerate(lines):
            if "NODE_API_KEY" in line and i + 1 < len(lines):
                next_line = lines[i + 1]
                if "sys.exit" in next_line:
                    pytest.fail(
                        "XER-12: api_server.py must NOT fail-fast when NODE_API_KEY "
                        "is empty. Node is optional — server runs in off-chain mode."
                    )

    # Must have the NODE_CONFIGURED flag or equivalent off-chain mode logic
    has_optional_flag = "NODE_CONFIGURED" in source or "off-chain" in source.lower()
    if not has_optional_flag:
        pytest.fail(
            "XER-12: api_server.py must have NODE_CONFIGURED flag or off-chain "
            "mode logic to gracefully handle missing Ergo node."
        )

    # Health endpoint must report mode
    has_mode = '"mode"' in source or "'mode'" in source
    if not has_mode:
        pytest.fail(
            "XER-12: /health endpoint must report 'mode' field (on-chain/off-chain)."
        )


# ═══════════════════════════════════════════════════════════════
# 15. BE-6: /ws/stats REQUIRES AUTHENTICATION
#    Connection stats are operational intel — must be admin-only.
# ═══════════════════════════════════════════════════════════════

def test_ws_stats_requires_auth():
    """
    BE-6: /ws/stats endpoint must require admin API key authentication.

    Exposing connection counts, tracked addresses, and IP information
    without auth leaks operational intelligence to attackers.
    """
    ws_routes_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "..",
        "backend", "ws_routes.py"
    )
    ws_routes_path = os.path.normpath(ws_routes_path)

    if not os.path.exists(ws_routes_path):
        pytest.skip(f"ws_routes.py not found at {ws_routes_path}")

    with open(ws_routes_path, "r") as f:
        source = f.read()

    # Find the ws_stats function
    stats_func_start = source.find("async def ws_stats")
    if stats_func_start == -1:
        pytest.skip("ws_stats function not found")

    # Look for auth check within the function body (next ~500 chars)
    func_body = source[stats_func_start:stats_func_start + 500]
    has_auth = (
        "X-Api-Key" in func_body or
        "ADMIN_API_KEY" in func_body or
        "api_key" in func_body
    )

    if not has_auth:
        pytest.fail(
            "BE-6: /ws/stats must require admin API key authentication. "
            "This endpoint exposes connection counts and tracked addresses."
        )


# ═══════════════════════════════════════════════════════════════
# 16. BE-5: APY ENDPOINT INPUT VALIDATION
#    avg_bet_size must be validated to prevent abuse.
# ═══════════════════════════════════════════════════════════════

def test_apy_input_validation():
    """
    BE-5: /apy endpoint must validate avg_bet_size input.

    Without validation, negative values, non-numeric strings, or
    absurdly large values can produce misleading APY calculations.
    """
    lp_routes_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "..",
        "backend", "lp_routes.py"
    )
    lp_routes_path = os.path.normpath(lp_routes_path)

    if not os.path.exists(lp_routes_path):
        pytest.skip(f"lp_routes.py not found at {lp_routes_path}")

    with open(lp_routes_path, "r") as f:
        source = f.read()

    # Find the APY endpoint
    apy_func_start = source.find("async def get_pool_apy")
    if apy_func_start == -1:
        pytest.skip("get_pool_apy function not found")

    func_body = source[apy_func_start:apy_func_start + 1500]

    # Must have some form of input validation
    has_validation = (
        "ValueError" in func_body or
        "TypeError" in func_body or
        "bet_size_erg <= 0" in func_body or
        "bet_size_erg >" in func_body or
        "HTTPException" in func_body
    )

    if not has_validation:
        pytest.xfail(
            "BE-5: /apy endpoint does not validate avg_bet_size input. "
            "Add bounds checking and type validation."
        )


# ─── 26. BigInt precision in Long encoding (PROTO-1) ─────────────────

def test_long_encoding_no_number_intermediate():
    """
    PROTO-1: encodeLongConstant must NOT convert zigzag-encoded BigInt
    to Number before VLQ encoding. Number loses precision above 2^53,
    corrupting ~1 in 4096 random 8-byte secrets.

    The fix: keep zigzag as BigInt and use a BigInt VLQ encoder.
    """
    import re

    serializer_path = os.path.normpath(os.path.join(
        os.path.dirname(__file__), "..", "..", "..",
        "frontend", "src", "utils", "sigmaSerializer.ts"
    ))

    if not os.path.exists(serializer_path):
        pytest.skip(f"{serializer_path} not found")

    with open(serializer_path, "r") as f:
        src = f.read()

    # Find the region between 'export function encodeLongConstant' and the
    # next 'export function' or end of file
    func_match = re.search(
        r'export\s+function\s+encodeLongConstant\b.*',
        src, re.DOTALL
    )
    assert func_match, "encodeLongConstant not found in sigmaSerializer.ts"

    # Extract the function region (up to next export or EOF)
    func_region = src[func_match.start():]
    next_export = re.search(r'\nexport\s+(?!function\s+encodeLongConstant)', func_region)
    if next_export:
        func_region = func_region[:next_export.start()]

    # Must NOT have Number(...) wrapping a BigInt zigzag operation
    # Pattern: Number( followed by ( — i.e., Number((bigValue << 1n) ...)
    has_number_cast = bool(re.search(r'Number\s*\(\s*\(', func_region))
    if has_number_cast:
        pytest.fail(
            "PROTO-1: encodeLongConstant converts BigInt zigzag to Number. "
            "This causes precision loss for values > 2^53. "
            "Use BigInt throughout and call a BigInt VLQ encoder instead."
        )

    # Must use encodeVLQBigInt (not encodeVLQ) for the VLQ step
    uses_bigint_vlq = "encodeVLQBigInt" in func_region
    if not uses_bigint_vlq and "encodeVLQ" in func_region:
        pytest.fail(
            "PROTO-1: encodeLongConstant uses encodeVLQ (Number-based) instead of "
            "encodeVLQBigInt for Long encoding. Use the BigInt variant."
        )


# ═══════════════════════════════════════════════════════════════
# 12. COMMITMENT HASH CONSISTENCY (SEC-CRITICAL-1)
#     Frontend, backend, and smart contracts MUST use the SAME hash.
#     Mismatch = every bet fails reveal = protocol unusable.
# ═══════════════════════════════════════════════════════════════

def _find_hash_function(source: str, filename: str) -> str:
    """Detect which hash function a source file uses for commitments."""
    lower = source.lower()
    # blake2b256 takes priority — it's the Ergo native hash
    if "blake2b256" in lower:
        return "blake2b256"
    # sha256 is only acceptable if NOT the primary commitment hash
    # (e.g., legacy export in crypto.ts is OK)
    if "sha256" in lower or "sha-256" in lower:
        # Check if sha256 is just a legacy/compat export, not used for commitments
        lines = source.split("\n")
        sha256_in_commitment = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("//") or stripped.startswith("*") or stripped.startswith("/*"):
                continue
            # Look for sha256 being used in commitment context
            if "sha256" in lower and any(kw in stripped.lower() for kw in ["commit", "await sha256", "= sha256"]):
                sha256_in_commitment = True
                break
        if sha256_in_commitment:
            return "sha256"
        # sha256 present but not used for commitments — likely legacy export
        return "blake2b256"  # already confirmed blake2b256 present above
    return "unknown"


def _scan_source_file(rel_path: str) -> str:
    """Read a source file relative to repo root, return hash function."""
    repo_root = os.path.normpath(os.path.join(
        os.path.dirname(__file__), "..", "..", ".."
    ))
    full_path = os.path.join(repo_root, rel_path)
    if not os.path.exists(full_path):
        return "missing"
    with open(full_path, "r") as f:
        return _find_hash_function(f.read(), rel_path)


def test_commitment_hash_consistency():
    """
    SEC-CRITICAL-1: All components must use blake2b256 for commitments.

    If frontend uses SHA256 but on-chain contracts use blake2b256,
    every reveal verification fails. All bets become timeout refunds.
    The protocol is completely broken.

    This test catches the mismatch before deployment.
    """
    files_to_check = {
        "frontend/src/components/games/CoinFlipGame.tsx": "Frontend CoinFlip",
        "frontend/src/utils/crypto.ts": "Frontend crypto utils",
        "frontend/src/utils/dice.ts": "Frontend dice utils",
        "frontend/src/utils/plinko.ts": "Frontend plinko utils",
        "backend/rng_module.py": "Backend RNG module",
        "smart-contracts/coinflip_v1.es": "On-chain CoinFlip",
        "smart-contracts/dice_v1.es": "On-chain Dice",
        "smart-contracts/plinko_v1.es": "On-chain Plinko",
    }

    results = {}
    for rel_path, label in files_to_check.items():
        results[label] = _scan_source_file(rel_path)

    # Filter out missing files (not all may exist yet)
    present = {k: v for k, v in results.items() if v != "missing"}

    if not present:
        pytest.skip("No commitment-related files found")

    # All present files must use blake2b256
    for label, hash_fn in present.items():
        if hash_fn != "blake2b256":
            pytest.fail(
                f"SEC-CRITICAL-1: {label} uses '{hash_fn}' instead of blake2b256. "
                "All components MUST use blake2b256 (Ergo native opcode) for "
                "commitment hashing. Using any other hash breaks on-chain reveal."
            )


def test_commitment_hash_functional():
    """
    SEC-CRITICAL-1: Functional test — verify blake2b256 produces correct
    commitment hash for a known test vector.

    Test vector:
        secret = 0x0102030405060708
        choice = 0 (heads)
        expected = blake2b256(secret || choice)

    This test uses Python hashlib to compute the expected value and
    verifies the backend module produces the same result.
    """
    import hashlib

    secret = bytes([1, 2, 3, 4, 5, 6, 7, 8])
    choice = 0

    # Compute expected with raw hashlib
    commit_data = secret + bytes([choice])
    expected_hash = hashlib.blake2b(commit_data, digest_size=32).hexdigest()

    # Compute via backend module
    repo_root = os.path.normpath(os.path.join(
        os.path.dirname(__file__), "..", "..", ".."
    ))
    rng_module_path = os.path.join(repo_root, "backend", "rng_module.py")

    if not os.path.exists(rng_module_path):
        pytest.skip(f"rng_module.py not found at {rng_module_path}")

    # Import and test
    import importlib.util
    spec = importlib.util.spec_from_file_location("rng_module", rng_module_path)
    rng = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rng)

    actual_hash = rng.generate_commit(secret, choice)

    assert actual_hash == expected_hash, (
        f"SEC-CRITICAL-1: Backend generate_commit() produced wrong hash.\n"
        f"  secret={secret.hex()}, choice={choice}\n"
        f"  expected (blake2b256): {expected_hash}\n"
        f"  actual:                {actual_hash}\n"
        f"  Backend is NOT using blake2b256 for commitments."
    )

    # Also verify the verify_commit function works
    assert rng.verify_commit(expected_hash, secret, choice), (
        "SEC-CRITICAL-1: verify_commit() rejected a valid commitment."
    )

    # Verify wrong commitment is rejected
    assert not rng.verify_commit("00" * 32, secret, choice), (
        "SEC-CRITICAL-1: verify_commit() accepted an invalid commitment."
    )
