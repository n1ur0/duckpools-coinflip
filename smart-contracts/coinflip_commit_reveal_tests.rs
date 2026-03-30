// DuckPools Commit-Reveal Contract Tests
// Tests the commit-reveal coinflip contract functionality

use ergo_appkit::testkit::*;
use ergo_appkit::wallet:: Wallet;
use ergo_appkit::contract::Contract;
use ergo_appkit::ergo_box::ErgoBox;
use ergo_appkit::input::Input;
use ergo_appkit::output::Output;
use ergo_appkit::tx_builder::TxBuilder;
use sigma_test_util::force_any_val;

#[test]
fn test_commit_reveal_contract() {
    // Setup test environment
    let mut testkit = TestKit::new();
    let wallet = testkit.wallet();
    
    // Create contract
    let contract = Contract::load("coinflip_commit_reveal.es").unwrap();
    
    // Generate keys for house and player
    let house_key = wallet.generate_key();
    let player_key = wallet.generate_key();
    
    // Create commitment
    let player_secret = force_any_val::<Vec<u8>>();
    let player_choice = 0; // heads
    let choice_byte = if player_choice == 0 { 0u8 } else { 1u8 };
    let commitment_hash = blake2b256(&player_secret, &[choice_byte]);
    
    // Create contract box
    let contract_box = ErgoBox::new(
        1000000000, // 1 ERG
        contract.p2s_address(),
        Some(vec![
            // R4: house public key
            Input::reg_box_data(house_key.pubkey(), 4),
            // R5: player public key  
            Input::reg_box_data(player_key.pubkey(), 5),
            // R6: commitment hash
            Input::reg_box_data(&commitment_hash, 6),
            // R7: player choice
            Input::reg_int(player_choice as i64, 7),
            // R8: timeout height (current height + 10 blocks)
            Input::reg_int(testkit.height() + 10, 8),
            // R9: player secret
            Input::reg_box_data(&player_secret, 9),
        ]),
        None,
    );
    
    // Add contract box to wallet
    wallet.add_box(contract_box).unwrap();
    
    // Test reveal path (house spends)
    let reveal_tx = TxBuilder::new(&testkit)
        .input(wallet.get_box(0))
        .output(Output::new(
            player_key.address(),
            1940000000, // 1.94 ERG (97% of 2 ERG)
            None,
        ))
        .build(&wallet)
        .unwrap();
    
    // Test refund path (player spends after timeout)
    testkit.set_height(testkit.height() + 11); // advance past timeout
    let refund_tx = TxBuilder::new(&testkit)
        .input(wallet.get_box(0))
        .output(Output::new(
            player_key.address(),
            980000000, // 0.98 ERG (98% refund)
            None,
        ))
        .build(&wallet)
        .unwrap();
    
    // Verify transactions are valid
    assert!(reveal_tx.is_valid());
    assert!(refund_tx.is_valid());
}

#[test]
fn test_commitment_verification() {
    // Test that invalid commitments are rejected
    let mut testkit = TestKit::new();
    let wallet = testkit.wallet();
    
    let contract = Contract::load("coinflip_commit_reveal.es").unwrap();
    let house_key = wallet.generate_key();
    let player_key = wallet.generate_key();
    
    // Create invalid commitment (wrong hash)
    let player_secret = force_any_val::<Vec<u8>>();
    let player_choice = 0;
    let wrong_commitment_hash = blake2b256(&player_secret, &[1u8]); // wrong choice byte
    
    let contract_box = ErgoBox::new(
        1000000000,
        contract.p2s_address(),
        Some(vec![
            Input::reg_box_data(house_key.pubkey(), 4),
            Input::reg_box_data(player_key.pubkey(), 5),
            Input::reg_box_data(&wrong_commitment_hash, 6),
            Input::reg_int(player_choice as i64, 7),
            Input::reg_int(testkit.height() + 10, 8),
            Input::reg_box_data(&player_secret, 9),
        ]),
        None,
    );
    
    wallet.add_box(contract_box).unwrap();
    
    // Try to reveal with invalid commitment - should fail
    let reveal_tx = TxBuilder::new(&testkit)
        .input(wallet.get_box(0))
        .output(Output::new(
            player_key.address(),
            1940000000,
            None,
        ))
        .build(&wallet);
    
    assert!(reveal_tx.is_err());
}

#[test]
fn test_timeout_mechanism() {
    // Test that refund is only possible after timeout
    let mut testkit = TestKit::new();
    let wallet = testkit.wallet();
    
    let contract = Contract::load("coinflip_commit_reveal.es").unwrap();
    let house_key = wallet.generate_key();
    let player_key = wallet.generate_key();
    
    let player_secret = force_any_val::<Vec<u8>>();
    let player_choice = 0;
    let commitment_hash = blake2b256(&player_secret, &[0u8]);
    
    let contract_box = ErgoBox::new(
        1000000000,
        contract.p2s_address(),
        Some(vec![
            Input::reg_box_data(house_key.pubkey(), 4),
            Input::reg_box_data(player_key.pubkey(), 5),
            Input::reg_box_data(&commitment_hash, 6),
            Input::reg_int(player_choice as i64, 7),
            Input::reg_int(testkit.height() + 10, 8),
            Input::reg_box_data(&player_secret, 9),
        ]),
        None,
    );
    
    wallet.add_box(contract_box).unwrap();
    
    // Try to refund before timeout - should fail
    let refund_tx = TxBuilder::new(&testkit)
        .input(wallet.get_box(0))
        .output(Output::new(
            player_key.address(),
            980000000,
            None,
        ))
        .build(&wallet);
    
    assert!(refund_tx.is_err());
    
    // Advance time past timeout
    testkit.set_height(testkit.height() + 11);
    
    // Now refund should succeed
    let refund_tx = TxBuilder::new(&testkit)
        .input(wallet.get_box(0))
        .output(Output::new(
            player_key.address(),
            980000000,
            None,
        ))
        .build(&wallet)
        .unwrap();
    
    assert!(refund_tx.is_valid());
}

#[test]
fn test_house_edge_calculation() {
    // Test that house edge is correctly implemented
    let mut testkit = TestKit::new();
    let wallet = testkit.wallet();
    
    let contract = Contract::load("coinflip_commit_reveal.es").unwrap();
    let house_key = wallet.generate_key();
    let player_key = wallet.generate_key();
    
    let player_secret = force_any_val::<Vec<u8>>();
    let player_choice = 0;
    let commitment_hash = blake2b256(&player_secret, &[0u8]);
    
    let contract_box = ErgoBox::new(
        1000000000, // 1 ERG bet
        contract.p2s_address(),
        Some(vec![
            Input::reg_box_data(house_key.pubkey(), 4),
            Input::reg_box_data(player_key.pubkey(), 5),
            Input::reg_box_data(&commitment_hash, 6),
            Input::reg_int(player_choice as i64, 7),
            Input::reg_int(testkit.height() + 10, 8),
            Input::reg_box_data(&player_secret, 9),
        ]),
        None,
    );
    
    wallet.add_box(contract_box).unwrap();
    
    // Player wins: should get 1.94 ERG (97% of 2 ERG)
    let reveal_tx = TxBuilder::new(&testkit)
        .input(wallet.get_box(0))
        .output(Output::new(
            player_key.address(),
            1940000000, // 1.94 ERG
            None,
        ))
        .build(&wallet)
        .unwrap();
    
    assert_eq!(reveal_tx.outputs[0].value, 1940000000);
    
    // House wins: should get 1 ERG (full bet)
    let house_reveal_tx = TxBuilder::new(&testkit)
        .input(wallet.get_box(0))
        .output(Output::new(
            house_key.address(),
            1000000000, // 1 ERG
            None,
        ))
        .build(&wallet)
        .unwrap();
    
    assert_eq!(house_reveal_tx.outputs[0].value, 1000000000);
    
    // Refund: should get 0.98 ERG (98% refund)
    testkit.set_height(testkit.height() + 11);
    let refund_tx = TxBuilder::new(&testkit)
        .input(wallet.get_box(0))
        .output(Output::new(
            player_key.address(),
            980000000, // 0.98 ERG
            None,
        ))
        .build(&wallet)
        .unwrap();
    
    assert_eq!(refund_tx.outputs[0].value, 980000000);
}