"""
Unit tests for load testing data generation.

Run these tests to verify the test data generation functions work correctly.
"""

import unittest
import hashlib
from locustfile import (
    generate_wallet_address,
    generate_bet_amount,
    generate_secret,
    generate_commitment,
    generate_bet_id,
    create_bet_payload,
)


class TestDataGeneration(unittest.TestCase):
    """Test data generation functions."""
    
    def test_generate_wallet_address(self):
        """Test wallet address generation."""
        address = generate_wallet_address()
        self.assertIsInstance(address, str)
        self.assertTrue(len(address) > 0)
        self.assertIn(address, [
            "9iDqY3bZ7yZ5bZ7yZ5bZ7yZ5bZ7yZ5bZ7yZ5bZ7yZ5bZ7yZ5bZ7yZ5b",
            "8hCpX2aY6aY4aY6aY4aY6aY4aY6aY4aY6aY4aY6aY4aY6aY4aY6aY4aY6",
            "7gBoW1zX5zX3zX5zX3zX5zX3zX5zX3zX5zX3zX5zX3zX5zX3zX5zX3zX5",
        ])
    
    def test_generate_bet_amount(self):
        """Test bet amount generation."""
        for _ in range(100):
            amount = generate_bet_amount()
            self.assertIsInstance(amount, float)
            self.assertGreaterEqual(amount, 0.1)
            self.assertLessEqual(amount, 5.0)
    
    def test_generate_secret(self):
        """Test secret generation."""
        secret = generate_secret()
        self.assertIsInstance(secret, str)
        self.assertEqual(len(secret), 4)  # 4 hex chars = 2 bytes
        
        # Verify it's valid hex
        try:
            int(secret, 16)
        except ValueError:
            self.fail("Secret is not valid hex")
    
    def test_generate_commitment(self):
        """Test commitment generation."""
        secret = generate_secret()
        commitment = generate_commitment(secret)
        
        # Commitment should be 64 hex chars (SHA256)
        self.assertIsInstance(commitment, str)
        self.assertEqual(len(commitment), 64)
        
        # Verify it's valid hex
        try:
            int(commitment, 16)
        except ValueError:
            self.fail("Commitment is not valid hex")
        
        # Verify it's correct SHA256 hash of secret
        secret_bytes = bytes.fromhex(secret)
        expected = hashlib.sha256(secret_bytes).hexdigest()
        self.assertEqual(commitment, expected)
    
    def test_generate_bet_id(self):
        """Test bet ID generation."""
        bet_id_1 = generate_bet_id()
        bet_id_2 = generate_bet_id()
        
        self.assertIsInstance(bet_id_1, str)
        self.assertIsInstance(bet_id_2, str)
        self.assertNotEqual(bet_id_1, bet_id_2)  # Should be unique
        
        # Check format: bet_<timestamp>
        self.assertTrue(bet_id_1.startswith("bet_"))
    
    def test_create_bet_payload(self):
        """Test complete bet payload creation."""
        payload = create_bet_payload()
        
        # Check all required fields
        self.assertIn("address", payload)
        self.assertIn("amount", payload)
        self.assertIn("commitment", payload)
        self.assertIn("secret", payload)
        self.assertIn("betId", payload)
        self.assertIn("gameType", payload)
        
        # Check types
        self.assertIsInstance(payload["address"], str)
        self.assertIsInstance(payload["amount"], str)
        self.assertIsInstance(payload["commitment"], str)
        self.assertIsInstance(payload["secret"], str)
        self.assertIsInstance(payload["betId"], str)
        self.assertIsInstance(payload["gameType"], str)
        
        # Check values
        self.assertEqual(payload["gameType"], "plinko")
        self.assertEqual(len(payload["secret"]), 4)
        self.assertEqual(len(payload["commitment"]), 64)
        
        # Check amount is valid number
        amount_int = int(payload["amount"])
        self.assertGreater(amount_int, 0)


class TestConfig(unittest.TestCase):
    """Test configuration module."""
    
    def test_scenarios_defined(self):
        """Test that all scenarios are properly defined."""
        from config import SCENARIOS
        
        expected_scenarios = ["smoke", "normal", "peak", "stress", "burst", "endurance"]
        
        for scenario_name in expected_scenarios:
            self.assertIn(scenario_name, SCENARIOS)
            scenario = SCENARIOS[scenario_name]
            
            # Check scenario has all required fields
            self.assertIsNotNone(scenario.name)
            self.assertIsNotNone(scenario.description)
            self.assertGreater(scenario.users, 0)
            self.assertGreater(scenario.spawn_rate, 0)
            self.assertIsNotNone(scenario.run_time)
            self.assertGreater(len(scenario.user_classes), 0)


if __name__ == "__main__":
    unittest.main()
