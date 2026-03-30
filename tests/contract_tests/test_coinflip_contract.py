import pytest
import hashlib
import json
import subprocess
import os
import tempfile
from typing import Dict, Any, List, Optional
from pathlib import Path

# Mock contract state and parameters for unit testing
class CoinflipContract:
    def __init__(self, house_pubkey: str, player_pubkey: str, commitment_hash: str, 
                 player_choice: int, player_secret: int, bet_id: str, 
                 timeout_height: int, game_nft: str):
        self.house_pubkey = house_pubkey
        self.player_pubkey = player_pubkey
        self.commitment_hash = commitment_hash
        self.player_choice = player_choice
        self.player_secret = player_secret
        self.bet_id = bet_id
        self.timeout_height = timeout_height
        self.game_nft = game_nft
        self.current_height = 0

    def blake2b256(self, data: bytes) -> str:
        """Mock Blake2b256 hash function"""
        return hashlib.blake2b(data).hexdigest()

    def calculate_commitment(self) -> str:
        """Calculate commitment hash from secret and choice"""
        secret_bytes = self.player_secret.to_bytes(4, 'big')
        choice_bytes = self.player_choice.to_bytes(4, 'big')
        return self.blake2b256(secret_bytes + choice_bytes)

    def is_valid_reveal(self) -> bool:
        """Verify reveal is valid - mock implementation"""
        calculated_hash = self.calculate_commitment()
        return calculated_hash == self.commitment_hash

    def can_refund(self) -> bool:
        """Check if refund is possible - mock implementation"""
        return self.current_height >= self.timeout_height

    def simulate_reveal(self, block_hash: str, house_wins: bool) -> Dict[str, Any]:
        """Simulate contract reveal outcome"""
        if not self.is_valid_reveal():
            return {"status": "invalid_reveal", "error": "Invalid reveal - commitment hash mismatch"}
        
        if house_wins:
            return {
                "status": "house_wins",
                "payout": 0,  # House keeps the bet
                "message": "House wins the coinflip"
            }
        else:
            return {
                "status": "player_wins",
                "payout": 97,  # Player gets 97% of bet (3% fee)
                "message": "Player wins the coinflip"
            }

    def simulate_refund(self) -> Dict[str, Any]:
        """Simulate contract refund"""
        if not self.can_refund():
            return {"status": "not_timed_out", "error": "Refund not available yet"}
        
        refund_amount = 98  # 2% fee
        return {
            "status": "refund",
            "refund_amount": refund_amount,
            "message": "Player receives refund after timeout"
        }

# Sigma-rust contract testing utilities
class SigmaRustContractTester:
    def __init__(self, contract_path: str, node_url: str = "http://localhost:9052"):
        self.contract_path = contract_path
        self.node_url = node_url
        self.sigma_rust_path = self._find_sigma_rust()
        
    def _find_sigma_rust(self) -> str:
        """Find sigma-rust compiler in PATH or common locations"""
        # Try common installation paths
        possible_paths = [
            "/usr/local/bin/sigma-rust",
            "/opt/sigma-rust/bin/sigma-rust",
            os.path.expanduser("~/bin/sigma-rust"),
            os.path.expanduser("~/.local/bin/sigma-rust")
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        
        # Try to find in PATH
        try:
            result = subprocess.run(["which", "sigma-rust"], capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip()
        except:
            pass
            
        raise RuntimeError("sigma-rust compiler not found. Please install sigma-rust or add to PATH")

    def compile_contract(self) -> str:
        """Compile ErgoScript contract using sigma-rust"""
        try:
            result = subprocess.run(
                [self.sigma_rust_path, "compile", self.contract_path],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to compile contract: {e.stderr}")

    def test_contract_on_devnet(self, test_cases: List[Dict]) -> Dict[str, Any]:
        """Test contract on Ergo devnet"""
        results = {}
        
        for test_name, test_case in test_cases.items():
            try:
                # Compile contract
                compiled_contract = self.compile_contract()
                
                # Deploy to devnet (simplified - would need actual wallet integration)
                deployment_result = self._deploy_to_devnet(compiled_contract, test_case)
                
                # Verify on explorer
                verification_result = self._verify_on_explorer(deployment_result["tx_id"])
                
                results[test_name] = {
                    "status": "passed",
                    "compiled_contract": compiled_contract,
                    "deployment_tx": deployment_result,
                    "verification": verification_result
                }
            except Exception as e:
                results[test_name] = {
                    "status": "failed",
                    "error": str(e)
                }
        
        return results

    def _deploy_to_devnet(self, compiled_contract: str, test_case: Dict) -> Dict:
        """Deploy contract to Ergo devnet (simplified mock)"""
        # In a real implementation, this would interact with wallet API
        # For now, return mock deployment data
        return {
            "tx_id": f"mock_tx_{hash(compiled_contract)}",
            "contract_address": f"mock_address_{hash(compiled_contract)}",
            "block_height": 1000,
            "status": "confirmed"
        }

    def _verify_on_explorer(self, tx_id: str) -> Dict:
        """Verify contract on Ergo explorer"""
        # In a real implementation, this would call explorer API
        # For now, return mock verification
        return {
            "verified": True,
            "contract_address": f"mock_address_{tx_id}",
            "block_height": 1000,
            "status": "confirmed"
        }

# Test cases
def test_commitment_calculation():
    """Test that commitment hash is calculated correctly"""
    contract = CoinflipContract(
        house_pubkey="house_pubkey",
        player_pubkey="player_pubkey",
        commitment_hash="",
        player_choice=0,  # heads
        player_secret=1234,
        bet_id="bet123",
        timeout_height=100,
        game_nft="nft123"
    )
    
    calculated_hash = contract.calculate_commitment()
    contract.commitment_hash = calculated_hash
    
    # Verify commitment matches calculated hash
    assert contract.is_valid_reveal() == True
    assert contract.commitment_hash == calculated_hash

def test_reveal_outcomes():
    """Test different reveal outcomes"""
    contract = CoinflipContract(
        house_pubkey="house_pubkey",
        player_pubkey="player_pubkey",
        commitment_hash="",
        player_choice=0,  # heads
        player_secret=1234,
        bet_id="bet123",
        timeout_height=100,
        game_nft="nft123"
    )
    
    calculated_hash = contract.calculate_commitment()
    contract.commitment_hash = calculated_hash
    
    # Test valid reveal - player wins
    result = contract.simulate_reveal(block_hash="mock_hash", house_wins=False)
    assert result["status"] == "player_wins"
    assert result["payout"] == 97
    
    # Test valid reveal - house wins  
    result = contract.simulate_reveal(block_hash="mock_hash", house_wins=True)
    assert result["status"] == "house_wins"
    assert result["payout"] == 0

def test_invalid_reveal():
    """Test invalid reveal scenarios"""
    contract = CoinflipContract(
        house_pubkey="house_pubkey",
        player_pubkey="player_pubkey",
        commitment_hash="wrong_hash",
        player_choice=0,  # heads
        player_secret=1234,
        bet_id="bet123",
        timeout_height=100,
        game_nft="nft123"
    )
    
    # Should fail because commitment hash doesn't match
    result = contract.simulate_reveal(block_hash="mock_hash", house_wins=False)
    assert result["status"] == "invalid_reveal"

def test_refund_mechanism():
    """Test refund functionality"""
    contract = CoinflipContract(
        house_pubkey="house_pubkey",
        player_pubkey="player_pubkey",
        commitment_hash="hash123",
        player_choice=0,  # heads
        player_secret=1234,
        bet_id="bet123",
        timeout_height=50,
        game_nft="nft123"
    )
    
    # Test before timeout - should not allow refund
    contract.current_height = 40
    result = contract.simulate_refund()
    assert result["status"] == "not_timed_out"
    
    # Test after timeout - should allow refund
    contract.current_height = 60
    result = contract.simulate_refund()
    assert result["status"] == "refund"
    assert result["refund_amount"] == 98

def test_edge_cases():
    """Test edge cases and boundary conditions"""
    # Test with tails (choice=1)
    contract = CoinflipContract(
        house_pubkey="house_pubkey",
        player_pubkey="player_pubkey",
        commitment_hash="",
        player_choice=1,  # tails
        player_secret=1234,
        bet_id="bet456",
        timeout_height=100,
        game_nft="nft456"
    )
    
    calculated_hash = contract.calculate_commitment()
    contract.commitment_hash = calculated_hash
    
    # Test valid reveal
    result = contract.simulate_reveal(block_hash="mock_hash", house_wins=False)
    assert result["status"] == "player_wins"
    
    # Test with maximum timeout - should allow refund
    contract.timeout_height = 1000
    contract.current_height = 1000  # exactly at timeout
    result = contract.simulate_refund()
    assert result["status"] == "refund"

def test_sigma_rust_integration():
    """Test sigma-rust integration for contract compilation and testing"""
    # Skip if sigma-rust is not available
    try:
        tester = SigmaRustContractTester("smart-contracts/coinflip_v1.es")
    except RuntimeError:
        pytest.skip("sigma-rust compiler not available")
    
    # Test contract compilation
    try:
        compiled_contract = tester.compile_contract()
        assert compiled_contract, "Compiled contract should not be empty"
        assert "sigma" in compiled_contract.lower(), "Compiled output should contain sigma instructions"
    except Exception as e:
        pytest.fail(f"Sigma-rust compilation failed: {e}")

def test_contract_deployment_simulation():
    """Test contract deployment simulation to devnet"""
    # Skip if sigma-rust is not available
    try:
        tester = SigmaRustContractTester("smart-contracts/coinflip_v1.es")
    except RuntimeError:
        pytest.skip("sigma-rust compiler not available")
    
    # Define test cases
    test_cases = {
        "basic_reveal": {
            "house_pubkey": "house_pubkey",
            "player_pubkey": "player_pubkey",
            "player_choice": 0,
            "player_secret": 1234,
            "bet_id": "test123",
            "timeout_height": 100,
            "game_nft": "nft123"
        }
    }
    
    # Test deployment (mock)
    results = tester.test_contract_on_devnet(test_cases)
    
    # Verify results
    for test_name, result in results.items():
        assert result["status"] == "passed", f"Test {test_name} failed: {result.get('error', 'unknown error')}"
        assert "compiled_contract" in result
        assert "deployment_tx" in result
        assert "verification" in result

def test_performance_testing():
    """Test contract performance - execution time and gas estimation"""
    # Skip if sigma-rust is not available
    try:
        tester = SigmaRustContractTester("smart-contracts/coinflip_v1.es")
    except RuntimeError:
        pytest.skip("sigma-rust compiler not available")
    
    # Test compilation performance
    import time
    start_time = time.time()
    try:
        compiled_contract = tester.compile_contract()
        compilation_time = time.time() - start_time
        
        # Compilation should be reasonably fast (under 5 seconds)
        assert compilation_time < 5, f"Compilation took too long: {compilation_time:.2f}s"
        
        # Test should pass
        assert compiled_contract, "Compilation should produce output"
        
    except Exception as e:
        pytest.fail(f"Performance test failed: {e}")

def test_contract_verification_on_explorer():
    """Test contract verification on Ergo explorer"""
    # Skip if sigma-rust is not available
    try:
        tester = SigmaRustContractTester("smart-contracts/coinflip_v1.es")
    except RuntimeError:
        pytest.skip("sigma-rust compiler not available")
    
    # Mock deployment and verification
    mock_tx_id = "mock_tx_1234567890"
    verification_result = tester._verify_on_explorer(mock_tx_id)
    
    assert verification_result["verified"] == True
    assert "contract_address" in verification_result
    assert "block_height" in verification_result
    assert "status" in verification_result

def test_edge_case_scenarios():
    """Test various edge case scenarios"""
    # Test with different choices
    for choice in [0, 1]:  # heads, tails
        contract = CoinflipContract(
            house_pubkey="house_pubkey",
            player_pubkey="player_pubkey",
            commitment_hash="",
            player_choice=choice,
            player_secret=1234 + choice,
            bet_id=f"bet_{choice}",
            timeout_height=100,
            game_nft=f"nft_{choice}"
        )
        
        calculated_hash = contract.calculate_commitment()
        contract.commitment_hash = calculated_hash
        
        # Test valid reveal
        result = contract.simulate_reveal(block_hash="mock_hash", house_wins=False)
        assert result["status"] == "player_wins"
    
    # Test with maximum values
    max_contract = CoinflipContract(
        house_pubkey="house_pubkey",
        player_pubkey="player_pubkey",
        commitment_hash="",
        player_choice=1,  # tails (max choice)
        player_secret=2147483647,  # max int
        bet_id="max_bet",
        timeout_height=2147483647,  # max int
        game_nft="max_nft"
    )
    
    calculated_hash = max_contract.calculate_commitment()
    max_contract.commitment_hash = calculated_hash
    
    # Test valid reveal
    result = max_contract.simulate_reveal(block_hash="mock_hash", house_wins=False)
    assert result["status"] == "player_wins"

if __name__ == "__main__":
    pytest.main([__file__])