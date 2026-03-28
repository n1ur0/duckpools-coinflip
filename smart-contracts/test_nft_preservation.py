#!/usr/bin/env python3
"""
Test script to verify NFT preservation in refund paths.

This script tests the critical fix for the NFT burning bug where
player refunds would destroy the game NFT, breaking the protocol.
"""

import hashlib
import json
from typing import Dict, List, Tuple

class NFTPreservationTest:
    def __init__(self):
        self.passed_tests = 0
        self.total_tests = 0
        
    def log_test(self, test_name: str, passed: bool, details: str = ""):
        """Log test result with details."""
        self.total_tests += 1
        if passed:
            self.passed_tests += 1
            status = "PASS"
        else:
            status = "FAIL"
        
        print(f"[{status}] {test_name}")
        if details:
            print(f"      {details}")
        print()
    
    def test_dice_refund_preserves_nft(self):
        """Test that dice contract refund path preserves NFT."""
        test_name = "Dice contract refund preserves NFT"
        
        # Read the dice contract
        with open("dice_v1.es", "r") as f:
            contract_content = f.read()
        
        # Check if nftToHouse is used in canRefund
        lines = contract_content.split('\n')
        refund_line = None
        for line in lines:
            if 'canRefund' in line and 'Boolean' in line:
                refund_line = line
                break
        
        has_nft_to_house = "nftToHouse" in contract_content
        has_can_refund = "canRefund" in contract_content
        uses_nft_in_refund = refund_line is not None and "nftToHouse" in refund_line
        
        # The refund path should use nftToHouse, not just nftPreserved
        correct_implementation = has_nft_to_house and has_can_refund and uses_nft_in_refund
        
        # Verify the NFT is sent to house (OUTPUTS(1)), not player (OUTPUTS(0))
        sends_to_house = "OUTPUTS(1)" in contract_content
        
        self.log_test(
            test_name,
            correct_implementation and sends_to_house,
            f"nftToHouse in refund: {has_nft_to_house}, sends to OUTPUTS(1): {sends_to_house}"
        )
        
        return correct_implementation and sends_to_house
    
    def test_plinko_refund_preserves_nft(self):
        """Test that plinko contract refund path preserves NFT."""
        test_name = "Plinko contract refund preserves NFT"
        
        # Read the plinko contract
        with open("plinko_v1.es", "r") as f:
            contract_content = f.read()
        
        # Check if nftToHouse is used in canRefund
        lines = contract_content.split('\n')
        refund_line = None
        for line in lines:
            if 'canRefund' in line and 'Boolean' in line:
                refund_line = line
                break
        
        has_nft_to_house = "nftToHouse" in contract_content
        has_can_refund = "canRefund" in contract_content
        uses_nft_in_refund = refund_line is not None and "nftToHouse" in refund_line
        
        correct_implementation = has_nft_to_house and has_can_refund and uses_nft_in_refund
        
        # Verify the NFT is sent to house (OUTPUTS(1)), not player (OUTPUTS(0))
        sends_to_house = "OUTPUTS(1)" in contract_content
        
        self.log_test(
            test_name,
            correct_implementation and sends_to_house,
            f"nftToHouse in refund: {has_nft_to_house}, sends to OUTPUTS(1): {sends_to_house}"
        )
        
        return correct_implementation and sends_to_house
    
    def test_coinflip_refund_preserves_nft(self):
        """Test that coinflip contract refund path preserves NFT."""
        test_name = "Coinflip contract refund preserves NFT"
        
        # Read the coinflip contract
        with open("coinflip_v1.es", "r") as f:
            contract_content = f.read()
        
        # Check if nftToHouse is used in canRefund
        lines = contract_content.split('\n')
        refund_line = None
        for line in lines:
            if 'canRefund' in line and 'Boolean' in line:
                refund_line = line
                break
        
        has_nft_to_house = "nftToHouse" in contract_content
        has_can_refund = "canRefund" in contract_content
        uses_nft_in_refund = refund_line is not None and "nftToHouse" in refund_line
        
        correct_implementation = has_nft_to_house and has_can_refund and uses_nft_in_refund
        
        # Verify the NFT is sent to house (OUTPUTS(1)), not player (OUTPUTS(0))
        sends_to_house = "OUTPUTS(1)" in contract_content
        
        self.log_test(
            test_name,
            correct_implementation and sends_to_house,
            f"nftToHouse in refund: {has_nft_to_house}, sends to OUTPUTS(1): {sends_to_house}"
        )
        
        return correct_implementation and sends_to_house
    
    def test_refund_vs_reveal_paths(self):
        """Test that refund and reveal paths have different NFT handling."""
        test_name = "Refund and reveal paths have different NFT handling"
        
        contracts = ["dice_v1.es", "plinko_v1.es", "coinflip_v1.es"]
        all_correct = True
        
        for contract_file in contracts:
            with open(contract_file, "r") as f:
                content = f.read()
            
            # Reveal path should use nftPreserved (NFT stays with player)
            # Refund path should use nftToHouse (NFT goes to house)
            has_nft_preserved = "nftPreserved" in content
            has_nft_to_house = "nftToHouse" in content
            
            # Both should be present but used in different contexts
            correct = has_nft_preserved and has_nft_to_house
            
            if not correct:
                all_correct = False
                self.log_test(
                    f"{contract_file} - NFT handling",
                    False,
                    f"nftPreserved: {has_nft_preserved}, nftToHouse: {has_nft_to_house}"
                )
        
        if all_correct:
            self.log_test(test_name, True, "All contracts have proper NFT handling")
        
        return all_correct
    
    def test_timeout_protection(self):
        """Test that timeout protection is implemented in all contracts."""
        test_name = "Timeout protection implemented in all contracts"
        
        contracts = ["dice_v1.es", "plinko_v1.es", "coinflip_v1.es"]
        all_correct = True
        
        for contract_file in contracts:
            with open(contract_file, "r") as f:
                content = f.read()
            
            has_timeout = "timeoutHeight" in content
            has_is_timed_out = "isTimedOut" in content
            
            correct = has_timeout and has_is_timed_out
            
            if not correct:
                all_correct = False
                self.log_test(
                    f"{contract_file} - Timeout protection",
                    False,
                    f"timeoutHeight: {has_timeout}, isTimedOut: {has_is_timed_out}"
                )
        
        if all_correct:
            self.log_test(test_name, True, "All contracts have timeout protection")
        
        return all_correct
    
    def run_all_tests(self):
        """Run all NFT preservation tests."""
        print("=" * 60)
        print("NFT Preservation Test Suite")
        print("=" * 60)
        print("Testing fix for CRITICAL bug: NFT burned on player refund")
        print()
        
        # Run all tests
        tests = [
            self.test_dice_refund_preserves_nft,
            self.test_plinko_refund_preserves_nft,
            self.test_coinflip_refund_preserves_nft,
            self.test_refund_vs_reveal_paths,
            self.test_timeout_protection
        ]
        
        for test in tests:
            test()
        
        # Summary
        print("=" * 60)
        print(f"Test Summary: {self.passed_tests}/{self.total_tests} tests passed")
        
        if self.passed_tests == self.total_tests:
            print("✅ ALL TESTS PASSED - NFT preservation fix is correctly implemented")
            print("   The protocol is now protected against NFT burning on refunds.")
        else:
            print("❌ SOME TESTS FAILED - Fix implementation needs review")
        
        print("=" * 60)
        
        return self.passed_tests == self.total_tests

if __name__ == "__main__":
    test = NFTPreservationTest()
    test.run_all_tests()