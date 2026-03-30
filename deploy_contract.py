#!/usr/bin/env python3
"""
Contract Deployment Script for DuckPools Coinflip
Deploys ErgoScript contracts to Ergo devnet and verifies deployment
"""

import os
import json
import subprocess
import time
from typing import Dict, List, Optional
import requests

class ContractDeployer:
    def __init__(self, node_url: str = "http://localhost:9052", explorer_url: str = "https://testnet.ergoplatform.com"):
        self.node_url = node_url
        self.explorer_url = explorer_url
        self.contracts = {
            "coinflip_v1": "smart-contracts/coinflip_v1.es",
            "coinflip_v2": "smart-contracts/coinflip_v2.es",
            "coinflip_v3": "smart-contracts/coinflip_v3.es",
            "dice_v1": "smart-contracts/dice_v1.es",
            "plinko_v1": "smart-contracts/plinko_v1.es",
            "test_nft_preservation": "smart-contracts/test_nft_preservation.es",
            "test_nft_refund_preservation": "smart-contracts/test_nft_refund_preservation.es"
        }
        
    def compile_contract(self, contract_path: str) -> Optional[Dict]:
        """Compile ErgoScript contract using sigma-rust compiler"""
        try:
            # Check if sigma-rust is available
            result = subprocess.run(["sigma-rust", "compile", contract_path], 
                                 capture_output=True, text=True, check=True)
            return json.loads(result.stdout)
        except subprocess.CalledProcessError as e:
            print(f"Error compiling {contract_path}: {e}")
            return None
        except FileNotFoundError:
            print("sigma-rust not found. Please install sigma-rust compiler.")
            return None
    
    def deploy_contract(self, compiled_contract: Dict, fee: int = 1000000) -> Optional[Dict]:
        """Deploy compiled contract to Ergo network"""
        try:
            # Create unsigned transaction
            unsigned_tx = {
                "inputs": [],
                "dataInputs": [],
                "outputs": [
                    {
                        "amount": 0,
                        "contract": compiled_contract["contract"],
                        "registers": {},
                        "tokens": []
                    }
                ],
                "fee": fee,
                "inputsCount": 1,
                "dataInputsCount": 0,
                "outputsCount": 1
            }
            
            # Sign and send transaction (simplified - in real implementation would use wallet)
            # This is a placeholder - actual implementation would use Ergo API
            print(f"Deploying contract: {compiled_contract['name']}")
            print(f"Contract size: {len(compiled_contract['contract'])} bytes")
            
            # Mock deployment - in real implementation would send to node
            mock_tx_id = f"mock_tx_{int(time.time())}"
            print(f"Deployment transaction ID: {mock_tx_id}")
            
            return {
                "txId": mock_tx_id,
                "contract": compiled_contract["contract"],
                "name": compiled_contract["name"],
                "status": "deployed"
            }
        except Exception as e:
            print(f"Error deploying contract: {e}")
            return None
    
    def verify_deployment(self, tx_id: str) -> bool:
        """Verify contract deployment on explorer"""
        try:
            explorer_api = f"{self.explorer_url}/api/v1/transactions/{tx_id}"
            response = requests.get(explorer_api)
            if response.status_code == 200:
                tx_data = response.json()
                # Check if transaction contains contract output
                for output in tx_data.get("outputs", []):
                    if "contract" in output:
                        print(f"Contract found in transaction {tx_id}")
                        return True
            return False
        except Exception as e:
            print(f"Error verifying deployment: {e}")
            return False
    
    def deploy_all_contracts(self) -> Dict[str, Dict]:
        """Deploy all contracts and return deployment results"""
        results = {}
        
        for name, path in self.contracts.items():
            print(f"\n=== Deploying {name} ===")
            
            # Compile contract
            compiled = self.compile_contract(path)
            if not compiled:
                results[name] = {"status": "compile_failed", "error": "Compilation failed"}
                continue
            
            # Deploy contract
            deployment = self.deploy_contract(compiled)
            if not deployment:
                results[name] = {"status": "deployment_failed", "error": "Deployment failed"}
                continue
            
            # Verify deployment
            is_verified = self.verify_deployment(deployment["txId"])
            results[name] = {
                "status": "success" if is_verified else "verification_failed",
                "txId": deployment["txId"],
                "contract": deployment["contract"],
                "verified": is_verified
            }
            
            print(f"Deployment result: {results[name]['status']}")
        
        return results
    
    def generate_deployment_report(self, results: Dict[str, Dict]) -> str:
        """Generate deployment report"""
        report = "=== Contract Deployment Report ===\n\n"
        success_count = 0
        failure_count = 0
        
        for name, result in results.items():
            status = result["status"]
            report += f"{name}: {status}\n"
            report += f"  Transaction ID: {result.get('txId', 'N/A')}\n"
            if status == "success":
                success_count += 1
            else:
                failure_count += 1
                report += f"  Error: {result.get('error', 'Unknown error')}\n"
            report += "\n"
        
        report += f"\nSummary: {success_count} successful, {failure_count} failed out of {len(results)} contracts\n"
        return report

def main():
    deployer = ContractDeployer()
    results = deployer.deploy_all_contracts()
    report = deployer.generate_deployment_report(results)
    print(report)
    
    # Save report to file
    with open("contract_deployment_report.txt", "w") as f:
        f.write(report)
    print("Deployment report saved to contract_deployment_report.txt")

if __name__ == "__main__":
    main()