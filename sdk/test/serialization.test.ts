/**
 * DuckPools SDK - Serialization Tests
 */

import { describe, it } from 'node:test';
import assert from 'node:assert';
import {
  serializeInt,
  serializeLong,
  serializeCollByte,
  serializeSigmaProp,
  serializeSValue,
  deserializeInt,
  deserializeLong,
  deserializeCollByte,
  deserializeSValue,
  formatErg,
  parseErg,
} from '../src/serialization/index.js';

describe('Serialization', () => {
  describe('serializeInt', () => {
    it('should serialize Int(0) correctly', () => {
      const result = serializeInt(0);
      assert.strictEqual(result, '0200');
    });

    it('should serialize Int(1) correctly', () => {
      const result = serializeInt(1);
      assert.strictEqual(result, '0202');
    });

    it('should serialize Int(10) correctly', () => {
      const result = serializeInt(10);
      assert.strictEqual(result, '0214');
    });

    it('should serialize Int(-1) correctly', () => {
      const result = serializeInt(-1);
      assert.strictEqual(result, '0201');
    });
  });

  describe('deserializeInt', () => {
    it('should deserialize Int(0) correctly', () => {
      const result = deserializeInt('0200');
      assert.strictEqual(result, 0);
    });

    it('should deserialize Int(10) correctly', () => {
      const result = deserializeInt('0214');
      assert.strictEqual(result, 10);
    });
  });

  describe('serializeLong', () => {
    it('should serialize Long(0) correctly', () => {
      const result = serializeLong(0n);
      assert.strictEqual(result, '0400');
    });

    it('should serialize Long(1) correctly', () => {
      const result = serializeLong(1n);
      assert.strictEqual(result, '0402');
    });

    it('should serialize Long(1000000000) correctly', () => {
      const result = serializeLong(1000000000n);
      assert.strictEqual(result, '0410a5d4e800');
    });

    it('should serialize Long(1000000000000) correctly', () => {
      const result = serializeLong(1000000000000n);
      assert.strictEqual(result, '04c0e4b73900');
    });
  });

  describe('deserializeLong', () => {
    it('should deserialize Long(0) correctly', () => {
      const result = deserializeLong('0400');
      assert.strictEqual(result, 0n);
    });

    it('should deserialize Long(1000000000) correctly', () => {
      const result = deserializeLong('0410a5d4e800');
      assert.strictEqual(result, 1000000000n);
    });
  });

  describe('serializeCollByte', () => {
    it('should serialize empty Coll[Byte] correctly', () => {
      const result = serializeCollByte('');
      assert.ok(result.startsWith('0e01'));
    });

    it('should serialize 1-byte Coll[Byte] correctly', () => {
      const result = serializeCollByte('ff');
      assert.ok(result.startsWith('0e0101'));
    });

    it('should serialize 4-byte Coll[Byte] correctly', () => {
      const result = serializeCollByte('deadbeef');
      assert.ok(result.startsWith('0e0104'));
    });

    it('should serialize 32-byte Coll[Byte] correctly', () => {
      const bytes = '00'.repeat(32);
      const result = serializeCollByte(bytes);
      assert.ok(result.startsWith('0e0120'));
    });
  });

  describe('deserializeCollByte', () => {
    it('should deserialize Coll[Byte] correctly', () => {
      const result = deserializeCollByte('0e0104deadbeef');
      assert.strictEqual(result, 4);
    });
  });

  describe('serializeSValue', () => {
    it('should auto-serialize Int SValue', () => {
      const result = serializeSValue({ type: 'Int', value: 42 });
      assert.ok(result.startsWith('02'));
    });

    it('should auto-serialize Long SValue', () => {
      const result = serializeSValue({ type: 'Long', value: 1000000000n });
      assert.ok(result.startsWith('04'));
    });

    it('should auto-serialize Coll[Byte] SValue', () => {
      const result = serializeSValue({ type: 'Coll[Byte]', value: 'deadbeef' });
      assert.ok(result.startsWith('0e'));
    });
  });

  describe('deserializeSValue', () => {
    it('should deserialize Int SValue', () => {
      const result = deserializeSValue('0214');
      assert.strictEqual(result.type, 'Int');
      assert.strictEqual(result.value, 10);
    });
  });

  describe('formatErg', () => {
    it('should format 0 nanoERG as 0.00 ERG', () => {
      const result = formatErg(0n);
      assert.strictEqual(result, '0.00');
    });

    it('should format 1_000_000_000 nanoERG as 1.00 ERG', () => {
      const result = formatErg(1_000_000_000n);
      assert.strictEqual(result, '1.00');
    });

    it('should format 2_500_000_000 nanoERG as 2.50 ERG', () => {
      const result = formatErg(2_500_000_000n);
      assert.strictEqual(result, '2.50');
    });
  });

  describe('parseErg', () => {
    it('should parse 0 ERG as 0 nanoERG', () => {
      const result = parseErg('0');
      assert.strictEqual(result, 0n);
    });

    it('should parse 1 ERG as 1_000_000_000 nanoERG', () => {
      const result = parseErg('1');
      assert.strictEqual(result, 1_000_000_000n);
    });

    it('should parse 1.5 ERG as 1_500_000_000 nanoERG', () => {
      const result = parseErg('1.5');
      assert.strictEqual(result, 1_500_000_000n);
    });
  });

  describe('Round-trip serialization', () => {
    it('should serialize and deserialize Int correctly', () => {
      const original = 42;
      const serialized = serializeInt(original);
      const deserialized = deserializeInt(serialized);
      assert.strictEqual(deserialized, original);
    });

    it('should serialize and deserialize Long correctly', () => {
      const original = 1000000000n;
      const serialized = serializeLong(original);
      const deserialized = deserializeLong(serialized);
      assert.strictEqual(deserialized, original);
    });
  });
});
