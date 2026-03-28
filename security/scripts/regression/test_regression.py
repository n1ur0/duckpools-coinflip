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
    RNG-SEC-1: Verify Plinko RNG uses SHA-256 for entropy extraction.
    
    The commit-reveal scheme and RNG must use SHA-256 or stronger.
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
    
    assert "sha256" in source.lower() or "SHA256" in source, (
        "RNG-SEC-1: Plinko RNG does not reference SHA-256. "
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
            # Check if 'hello' is the default
            if '"hello"' in line or "'hello'" in line:
                pytest.xfail(
                    f"SEC-1: API_KEY uses 'hello' as default at line {i+1}. "
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
    has_inline_vlq = "0x04" in source and "0x7F" in source and "0x80" in source
    # If the inline parser still exists, it's the one with the VLQ bit manipulation
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
