/**
 * DuckPools SDK - Serialization Example
 *
 * This example demonstrates Sigma-state register serialization:
 * - Int values (type 0x02)
 * - Long values (type 0x04)
 * - Coll[Byte] values (type 0x0E)
 * - SigmaProp values
 * - Deserialization
 */

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
} from '../src/index.js';

function main() {
  console.log('=== Serialization Example ===\n');

  // 1. Serialize Int values
  console.log('1. Serializing Int values...');
  const intExamples = [0, 1, 10, 100, -1, -10];
  for (const value of intExamples) {
    const serialized = serializeInt(value);
    console.log(`   Int(${value}) -> ${serialized}`);
  }
  console.log();

  // 2. Deserialize Int values
  console.log('2. Deserializing Int values...');
  const intHex = '0214'; // Int(10)
  const deserializedInt = deserializeInt(intHex);
  console.log(`   ${intHex} -> Int(${deserializedInt})`);
  console.log();

  // 3. Serialize Long values
  console.log('3. Serializing Long values...');
  const longExamples = [0n, 1n, 1000000000n, 1000000000000n];
  for (const value of longExamples) {
    const serialized = serializeLong(value);
    console.log(`   Long(${value}) -> ${serialized}`);
  }
  console.log();

  // 4. Deserialize Long values
  console.log('4. Deserializing Long values...');
  const longHex = '0410a5d4e800'; // Long(1000000000)
  const deserializedLong = deserializeLong(longHex);
  console.log(`   ${longHex} -> Long(${deserializedLong})`);
  console.log();

  // 5. Format and parse ERG amounts
  console.log('5. Formatting and parsing ERG amounts...');
  const nanoErgAmounts = [0n, 1_000_000_000n, 5_500_000_000n];
  for (const amount of nanoErgAmounts) {
    const erg = formatErg(amount);
    console.log(`   ${amount} nanoERG -> ${erg} ERG`);
  }
  console.log();

  const ergAmounts = ['0', '1.0', '2.5'];
  for (const amount of ergAmounts) {
    const nanoErg = parseErg(amount);
    console.log(`   ${amount} ERG -> ${nanoErg} nanoERG`);
  }
  console.log();

  // 6. Serialize Coll[Byte] values
  console.log('6. Serializing Coll[Byte] values...');
  const byteExamples = [
    '00',
    'ff',
    'deadbeef',
    '0000000000000000000000000000000000000000000000000000000000000000',
  ];
  for (const bytes of byteExamples) {
    const serialized = serializeCollByte(bytes);
    console.log(`   Coll[${bytes.length} bytes] -> ${serialized}`);
  }
  console.log();

  // 7. Deserialize Coll[Byte] values
  console.log('7. Deserializing Coll[Byte] values...');
  const collHex = '0e0104deadbeef';
  const deserializedColl = deserializeCollByte(collHex);
  console.log(`   ${collHex} -> Coll[${deserializedColl} bytes]`);
  console.log();

  // 8. Serialize SValue objects (auto-detect type)
  console.log('8. Auto-serializing SValue objects...');
  const sValues = [
    { type: 'Int' as const, value: 42 },
    { type: 'Long' as const, value: 1000000000n },
    { type: 'Coll[Byte]' as const, value: 'deadbeef' },
  ];
  for (const sValue of sValues) {
    const serialized = serializeSValue(sValue);
    console.log(`   SValue(${JSON.stringify(sValue)}) -> ${serialized}`);
  }
  console.log();

  // 9. Deserialize SValue objects
  console.log('9. Deserializing SValue objects...');
  const sValueHex = '0214'; // Int(10)
  const deserializedSValue = deserializeSValue(sValueHex);
  console.log(`   ${sValueHex} -> ${JSON.stringify(deserializedSValue)}`);
  console.log();

  console.log('=== Example completed ===');
}

main();
