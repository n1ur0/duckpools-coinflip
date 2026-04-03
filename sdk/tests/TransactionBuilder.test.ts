import { describe, it, expect } from 'vitest';
import { TransactionBuilder } from '../src/transaction/TransactionBuilder';

describe('TransactionBuilder', () => {
  describe('build (generic)', () => {
    it('creates a transaction with inputs and outputs', () => {
      const builder = new TransactionBuilder({
        fee: 1000000n,
        changeAddress: '9hEQHEMiBYWsWoVZ4eFJgfk3Vcq5vFn3xe1BsJ4g2hJmNVDUrcB',
      });

      const tx = builder.build(
        [{ boxId: 'abc123', value: 5000000n }],
        [{ address: '9hEQHEMiBYWsWoVZ4eFJgfk3Vcq5vFn3xe1BsJ4g2hJmNVDUrcB', value: 3000000n }]
      );

      expect(tx.inputs).toHaveLength(1);
      expect(tx.inputs[0].boxId).toBe('abc123');
      expect(tx.outputs).toHaveLength(2); // output + change
      expect(tx.outputs[0].value).toBe(3000000n);
      expect(tx.fee).toBe(1000000n);

      // Change box
      expect(tx.outputs[1].value).toBe(1000000n); // 5M - 3M - 1M fee = 1M change
    });

    it('absorbs dust change into fee', () => {
      const builder = new TransactionBuilder({
        fee: 1000000n,
        changeAddress: '9hEQHEMiBYWsWoVZ4eFJgfk3Vcq5vFn3xe1BsJ4g2hJmNVDUrcB',
        minBoxValue: 100000n,
      });

      const tx = builder.build(
        [{ boxId: 'abc123', value: 4001000n }],
        [{ address: '9hEQHEMiBYWsWoVZ4eFJgfk3Vcq5vFn3xe1BsJ4g2hJmNVDUrcB', value: 3000000n }]
      );

      // 4,001,000 - 3,000,000 = 1,001,000. Fee = 1,000,000. Change = 1,000 (dust, < minBoxValue).
      // So dust should be absorbed into fee: fee becomes 1,001,000.
      expect(tx.fee).toBe(1001000n);
      expect(tx.outputs).toHaveLength(1); // no change box
    });

    it('throws on insufficient input value', () => {
      const builder = new TransactionBuilder({
        fee: 1000000n,
        changeAddress: '9hEQHEMiBYWsWoVZ4eFJgfk3Vcq5vFn3xe1BsJ4g2hJmNVDUrcB',
      });

      expect(() =>
        builder.build(
          [{ boxId: 'abc123', value: 2000000n }],
          [{ address: '9hEQHEMiBYWsWoVZ4eFJgfk3Vcq5vFn3xe1BsJ4g2hJmNVDUrcB', value: 2000000n }]
        )
      ).toThrow('Insufficient input value');
    });

    it('throws if no change address and change is needed', () => {
      const builder = new TransactionBuilder({
        fee: 1000000n,
        // No change address!
      });

      expect(() =>
        builder.build(
          [{ boxId: 'abc123', value: 5000000n }],
          [{ address: '9hEQHEMiBYWsWoVZ4eFJgfk3Vcq5vFn3xe1BsJ4g2hJmNVDUrcB', value: 3000000n }]
        )
      ).toThrow('Change address required');
    });

    it('throws on empty inputs', () => {
      const builder = new TransactionBuilder();

      expect(() =>
        builder.build([], [{ address: 'test', value: 100n }])
      ).toThrow('at least one input');
    });
  });

  describe('buildPlaceBetTransaction', () => {
    it('builds a bet transaction with all registers', () => {
      const builder = new TransactionBuilder({
        fee: 1000000n,
        changeAddress: '9hEQHEMiBYWsWoVZ4eFJgfk3Vcq5vFn3xe1BsJ4g2hJmNVDUrcB',
      });

      const tx = builder.buildPlaceBetTransaction({
        playerAddress: '9hEQHEMiBYWsWoVZ4eFJgfk3Vcq5vFn3xe1BsJ4g2hJmNVDUrcB',
        pendingBetAddress: '9f21509f0e4cb57ef0c3e8d8f2e0c7f5e0c3e8d8f2e0c7f5e0c3e8d8f2e0c7f5',
        amount: 10000000n, // 0.01 ERG
        housePubKey: '02abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890ab',
        playerPubKey: '0212345678abcdef012345678abcdef012345678abcdef012345678abcdef012345',
        commitment: 'a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2',
        choice: 0, // heads
        secret: 'deadbeef',
        timeoutHeight: 500000,
        inputs: [{ boxId: 'input1', value: 20000000n }],
      });

      // Should have the bet output + change output
      expect(tx.outputs.length).toBeGreaterThanOrEqual(1);

      // First output is the bet box
      const betOutput = tx.outputs[0];
      expect(betOutput.value).toBe(10000000n);
      expect(betOutput.address).toBe('9f21509f0e4cb57ef0c3e8d8f2e0c7f5e0c3e8d8f2e0c7f5e0c3e8d8f2e0c7f5');
      expect(betOutput.additionalRegisters).toBeDefined();
      const regs = betOutput.additionalRegisters as Record<string, { value: string | number }>;
      expect(regs['R4'].value).toBe('02abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890ab');
      expect(regs['R5'].value).toBe('0212345678abcdef012345678abcdef012345678abcdef012345678abcdef012345');
      expect(regs['R6'].value).toBe('a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2');
      expect(regs['R7'].value).toBe(0);
      expect(regs['R8'].value).toBe(500000);
      expect(regs['R9'].value).toBe('deadbeef');
    });
  });

  describe('toEIP12Object', () => {
    it('converts transaction to EIP-12 format', () => {
      const builder = new TransactionBuilder({
        fee: 1000000n,
        changeAddress: '9hEQHEMiBYWsWoVZ4eFJgfk3Vcq5vFn3xe1BsJ4g2hJmNVDUrcB',
      });

      const tx = builder.build(
        [{ boxId: 'box1', value: 5000000n }],
        [{ address: '9hEQHEMiBYWsWoVZ4eFJgfk3Vcq5vFn3xe1BsJ4g2hJmNVDUrcB', value: 3000000n }]
      );

      const eip12 = builder.toEIP12Object(tx);

      // EIP-12 uses string values
      expect(typeof eip12.fee).toBe('string');
      expect(eip12.fee).toBe('1000000');
      expect(eip12.inputs).toHaveLength(1);
      expect(eip12.inputs[0].boxId).toBe('box1');
      expect(eip12.outputs).toHaveLength(2);
      expect(typeof eip12.outputs[0].value).toBe('string');
      expect(eip12.outputs[0].value).toBe('3000000');
      expect(eip12.outputs[0].creationHeight).toBe(0);
      expect(Array.isArray(eip12.outputs[0].assets)).toBe(true);
    });

    it('serializes registers in EIP-12 format', () => {
      const builder = new TransactionBuilder({
        fee: 1000000n,
        changeAddress: '9hEQHEMiBYWsWoVZ4eFJgfk3Vcq5vFn3xe1BsJ4g2hJmNVDUrcB',
      });

      const tx = builder.build(
        [{ boxId: 'box1', value: 20000000n }],
        [{
          address: '9f21509f0e4cb57ef0c3e8d8f2e0c7f5e0c3e8d8f2e0c7f5e0c3e8d8f2e0c7f5',
          value: 10000000n,
          additionalRegisters: {
            R4: { type: 'Coll[Byte]' as const, value: '02abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890ab' },
            R7: { type: 'Int' as const, value: 1 },
          } as any,
        }]
      );

      const eip12 = builder.toEIP12Object(tx);

      // First output has registers
      const betOutput = eip12.outputs[0];
      expect(betOutput.additionalRegisters['R4']).toBeDefined();
      expect(typeof betOutput.additionalRegisters['R4']).toBe('string');
      // Coll[Byte] starts with 0x0e
      expect(betOutput.additionalRegisters['R4'].startsWith('0e')).toBe(true);
      expect(betOutput.additionalRegisters['R7']).toBeDefined();
      // Int starts with 0x02
      expect(betOutput.additionalRegisters['R7'].startsWith('02')).toBe(true);
    });
  });

  describe('buildRevealTransaction', () => {
    it('builds a reveal tx for player win', () => {
      const builder = new TransactionBuilder({
        fee: 1000000n,
        changeAddress: '9hEQHEMiBYWsWoVZ4eFJgfk3Vcq5vFn3xe1BsJ4g2hJmNVDUrcB',
      });

      const tx = builder.buildRevealTransaction({
        betBoxId: 'betbox1',
        betBoxValue: 30000000n, // 30M nanoERG — enough to cover 19.4M payout + 1M fee
        houseAddress: '9hEQHEMiBYWsWoVZ4eFJgfk3Vcq5vFn3xe1BsJ4g2hJmNVDUrcB',
        playerAddress: '3WvTaKq7p3WvTaKq7p3WvTaKq7p3WvTaKq7p3WvTaKq7p3WvTaKq7p3WvTa',
        betAmount: 10000000n,
        result: 'win',
        houseEdge: 0.03,
        blockHash: 'abc123',
        secret: 'deadbeef',
      });

      expect(tx.outputs.length).toBeGreaterThanOrEqual(1);
      // Player wins: bet * 2 * (1 - 0.03) = 10000000 * 1.94 = 19400000
      expect(tx.outputs[0].value).toBe(19400000n);
      expect(tx.outputs[0].address).toBe('3WvTaKq7p3WvTaKq7p3WvTaKq7p3WvTaKq7p3WvTaKq7p3WvTaKq7p3WvTa');
    });

    it('builds a reveal tx for house win', () => {
      const builder = new TransactionBuilder({
        fee: 1000000n,
        changeAddress: '3WvTaKq7p3WvTaKq7p3WvTaKq7p3WvTaKq7p3WvTaKq7p3WvTaKq7p3WvTa',
      });

      const tx = builder.buildRevealTransaction({
        betBoxId: 'betbox1',
        betBoxValue: 20000000n, // 20M nanoERG — enough to cover 10M payout + 1M fee
        houseAddress: '9hEQHEMiBYWsWoVZ4eFJgfk3Vcq5vFn3xe1BsJ4g2hJmNVDUrcB',
        playerAddress: '3WvTaKq7p3WvTaKq7p3WvTaKq7p3WvTaKq7p3WvTaKq7p3WvTaKq7p3WvTa',
        betAmount: 10000000n,
        result: 'lose',
        houseEdge: 0.03,
        blockHash: 'abc123',
        secret: 'deadbeef',
      });

      expect(tx.outputs.length).toBeGreaterThanOrEqual(1);
      expect(tx.outputs[0].value).toBe(10000000n);
      expect(tx.outputs[0].address).toBe('9hEQHEMiBYWsWoVZ4eFJgfk3Vcq5vFn3xe1BsJ4g2hJmNVDUrcB');
    });
  });

  describe('buildRefundTransaction', () => {
    it('builds a refund tx returning bet to player', () => {
      const builder = new TransactionBuilder({
        fee: 1000000n,
        changeAddress: '3WvTaKq7p3WvTaKq7p3WvTaKq7p3WvTaKq7p3WvTaKq7p3WvTaKq7p3WvTa',
      });

      const tx = builder.buildRefundTransaction({
        betBoxId: 'betbox1',
        betBoxValue: 20000000n, // 20M nanoERG — enough to cover 10M refund + 1M fee
        playerAddress: '3WvTaKq7p3WvTaKq7p3WvTaKq7p3WvTaKq7p3WvTaKq7p3WvTaKq7p3WvTa',
        betAmount: 10000000n,
      });

      expect(tx.outputs.length).toBeGreaterThanOrEqual(1);
      expect(tx.outputs[0].value).toBe(10000000n);
      expect(tx.outputs[0].address).toBe('3WvTaKq7p3WvTaKq7p3WvTaKq7p3WvTaKq7p3WvTaKq7p3WvTaKq7p3WvTa');
    });
  });
});
