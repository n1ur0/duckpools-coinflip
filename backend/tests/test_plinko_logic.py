"""
Tests for plinko_logic.py

MAT-251: Verify that compute_expected_return uses probability-weighted
average instead of arithmetic mean.
"""

import pytest
from src.core.plinko_logic import (
    binomial_coefficient,
    get_zone_probabilities,
    get_multiplier_table,
    get_expected_value_table,
    compute_expected_return,
    compute_house_edge,
    calculate_payout,
    get_theoretical_rtp,
    validate_multiplier_table,
    validate_probability_sum,
    PLINKO_MIN_ROWS,
    PLINKO_MAX_ROWS,
    PLINKO_HOUSE_EDGE,
)


class TestBinomialCoefficient:
    """Test binomial coefficient calculations."""
    
    def test_basic_cases(self):
        """Test basic binomial coefficient values."""
        assert binomial_coefficient(4, 2) == 6  # C(4,2) = 6
        assert binomial_coefficient(5, 0) == 1  # C(n,0) = 1
        assert binomial_coefficient(5, 5) == 1  # C(n,n) = 1
        assert binomial_coefficient(8, 4) == 70  # C(8,4) = 70
    
    def test_out_of_range(self):
        """Test out of range values."""
        assert binomial_coefficient(5, 6) == 0
        assert binomial_coefficient(5, -1) == 0


class TestZoneProbabilities:
    """Test zone probability calculations."""
    
    def test_8_rows(self):
        """Test probabilities for 8 rows."""
        probs = get_zone_probabilities(8)
        assert len(probs) == 9  # 8 rows = 9 slots
        
        # Check some known values
        assert abs(probs[0] - 0.00390625) < 1e-10  # C(8,0)/256
        assert abs(probs[4] - 0.2734375) < 1e-10   # C(8,4)/256 (center)
        assert abs(probs[8] - 0.00390625) < 1e-10  # C(8,8)/256
    
    def test_12_rows(self):
        """Test probabilities for 12 rows."""
        probs = get_zone_probabilities(12)
        assert len(probs) == 13  # 12 rows = 13 slots
        
        # Center should have highest probability
        center_idx = 6
        assert probs[center_idx] == max(probs)
        
        # Should be symmetric
        assert abs(probs[0] - probs[12]) < 1e-10
        assert abs(probs[1] - probs[11]) < 1e-10
        assert abs(probs[2] - probs[10]) < 1e-10
    
    def test_invalid_rows(self):
        """Test invalid row counts."""
        with pytest.raises(ValueError):
            get_zone_probabilities(7)  # Too few
        
        with pytest.raises(ValueError):
            get_zone_probabilities(17)  # Too many


class TestMultiplierTable:
    """Test multiplier table calculations."""
    
    def test_multiplier_properties(self):
        """Test that multipliers have correct properties."""
        for rows in [8, 12, 16]:
            multipliers = get_multiplier_table(rows)
            probs = get_zone_probabilities(rows)
            
            # Should have correct length
            assert len(multipliers) == rows + 1
            
            # Edge multipliers should be higher than center
            assert multipliers[0] > multipliers[rows // 2]
            assert multipliers[-1] > multipliers[rows // 2]
            
            # Should be symmetric
            for i in range(rows + 1):
                assert abs(multipliers[i] - multipliers[rows - i]) < 1e-10
    
    def test_multiplier_values(self):
        """Test specific multiplier values."""
        multipliers = get_multiplier_table(8)
        
        # Center should be lowest
        center_idx = 4
        assert multipliers[center_idx] == min(multipliers)
        
        # Should all be positive
        assert all(m > 0 for m in multipliers)


class TestExpectedValueTable:
    """Test expected value table calculations."""
    
    def test_expected_value_sum(self):
        """Test that expected values sum to the expected return."""
        for rows in [8, 12, 16]:
            ev_table = get_expected_value_table(rows)
            expected_return = compute_expected_return(rows)
            
            # Sum should equal expected return
            assert abs(sum(ev_table) - expected_return) < 1e-10
    
    def test_expected_value_properties(self):
        """Test expected value properties."""
        ev_table = get_expected_value_table(8)
        
        # Should have correct length
        assert len(ev_table) == 9
        
        # Should all be positive
        assert all(ev > 0 for ev in ev_table)


class TestComputeExpectedReturn:
    """Test expected return calculation (MAT-251 fix)."""
    
    def test_probability_weighted_vs_arithmetic_mean(self):
        """Test that probability-weighted differs from arithmetic mean."""
        rows = 8
        multipliers = get_multiplier_table(rows)
        probs = get_zone_probabilities(rows)
        
        # Probability-weighted calculation (CORRECT)
        prob_weighted = sum(m * p for m, p in zip(multipliers, probs))
        
        # Arithmetic mean (WRONG - assumes equal probability)
        arithmetic_mean = sum(multipliers) / len(multipliers)
        
        # They should be different
        assert abs(prob_weighted - arithmetic_mean) > 0.01
        
        # The probability-weighted should be exactly 1 - house_edge
        expected = 1.0 - PLINKO_HOUSE_EDGE
        assert abs(prob_weighted - expected) < 1e-10
    
    def test_expected_return_values(self):
        """Test expected return values for different row counts."""
        expected = 1.0 - PLINKO_HOUSE_EDGE
        
        for rows in [8, 12, 16]:
            result = compute_expected_return(rows)
            assert abs(result - expected) < 1e-10
    
    def test_invalid_rows(self):
        """Test invalid row counts."""
        with pytest.raises(ValueError):
            compute_expected_return(7)
        
        with pytest.raises(ValueError):
            compute_expected_return(17)


class TestHouseEdge:
    """Test house edge calculation."""
    
    def test_house_edge_values(self):
        """Test house edge values for different row counts."""
        for rows in [8, 12, 16]:
            edge = compute_house_edge(rows)
            assert abs(edge - PLINKO_HOUSE_EDGE) < 1e-10


class TestCalculatePayout:
    """Test payout calculation."""
    
    def test_payout_calculation(self):
        """Test payout calculation for various scenarios."""
        bet_amount = 1000000000  # 1 ERG in nanoERG
        rows = 8
        
        for slot in [0, 4, 8]:  # edge, center, edge
            payout = calculate_payout(bet_amount, rows, slot)
            multipliers = get_multiplier_table(rows)
            expected = int(bet_amount * multipliers[slot])
            assert payout == expected
    
    def test_invalid_slot(self):
        """Test invalid slot."""
        with pytest.raises(ValueError):
            calculate_payout(1000, 8, 9)  # slot > rows
        
        with pytest.raises(ValueError):
            calculate_payout(1000, 8, -1)  # negative slot


class TestTheoreticalRTP:
    """Test theoretical RTP."""
    
    def test_rtp_value(self):
        """Test RTP value."""
        rtp = get_theoretical_rtp()
        expected = (1.0 - PLINKO_HOUSE_EDGE) * 100
        assert abs(rtp - expected) < 1e-10


class TestValidation:
    """Test validation functions."""
    
    def test_validate_multiplier_table(self):
        """Test multiplier table validation."""
        for rows in [8, 12, 16]:
            assert validate_multiplier_table(rows)
    
    def test_validate_probability_sum(self):
        """Test probability sum validation."""
        for rows in [8, 12, 16]:
            assert validate_probability_sum(rows)


class TestMAT251Regression:
    """MAT-251: Regression tests for the expected return fix."""
    
    def test_expected_return_not_arithmetic_mean(self):
        """MAT-251: Ensure expected return is not calculated using arithmetic mean."""
        rows = 8
        multipliers = get_multiplier_table(rows)
        arithmetic_mean = sum(multipliers) / len(multipliers)
        expected_return = compute_expected_return(rows)
        
        # They should be different
        # Arithmetic mean would be around 1.5-2.0 for 8 rows
        # Expected return should be exactly 0.97
        assert abs(expected_return - 0.97) < 1e-10
        assert abs(arithmetic_mean - expected_return) > 0.1
    
    def test_expected_return_consistency(self):
        """MAT-251: Ensure expected return is consistent across row counts."""
        expected_values = []
        
        for rows in [8, 12, 16]:
            ev = compute_expected_return(rows)
            expected_values.append(ev)
        
        # All should be exactly the same (1 - house_edge)
        assert all(abs(ev - expected_values[0]) < 1e-10 for ev in expected_values)
    
    def test_frontend_backend_consistency(self):
        """MAT-251: Ensure backend calculations match frontend expectations."""
        # Test the same calculations that are done in frontend plinko.ts
        rows = 12
        bet_amount = 1000000000  # 1 ERG
        
        # Get probabilities and multipliers
        probs = get_zone_probabilities(rows)
        multipliers = get_multiplier_table(rows)
        
        # Calculate expected return like frontend does
        expected_payout = 0
        for slot in range(rows + 1):
            payout = bet_amount * multipliers[slot]
            expected_payout += probs[slot] * payout
        
        expected_return = expected_payout / bet_amount
        
        # Should match our compute_expected_return
        backend_expected_return = compute_expected_return(rows)
        assert abs(expected_return - backend_expected_return) < 1e-10