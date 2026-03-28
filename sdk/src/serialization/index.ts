/**
 * DuckPools SDK - Sigma-State Serialization
 * Helpers for serializing Ergo SValue types (Int, Long, Coll[Byte], etc.)
 *
 * Reference: off-chain-bot/sigma_serializer.py
 */

import type { SValue } from '../types';
import { SerializationError } from '../types';

/**
 * VLQ (Variable-Length Quantity) encoding
 * 7-bit groups, MSB = continuation flag
 */
function encodeVLQ(value: bigint): Buffer {
  if (value === 0n) {
    return Buffer.from([0x00]);
  }

  const bytes: number[] = [];
  let remaining = value;

  while (remaining > 0n) {
    let byte = Number(remaining & 0x7fn);
    remaining >>= 7n;

    // Set continuation flag if more bytes follow
    if (remaining > 0n) {
      byte |= 0x80;
    }

    bytes.push(byte);
  }

  return Buffer.from(bytes);
}

/**
 * ZigZag encoding for signed integers
 * Maps signed integers to unsigned for VLQ
 */
function zigZagEncode(value: bigint): bigint {
  return (value << 1n) ^ (value >> 63n);
}

function zigZagEncodeInt(value: number): number {
  return (value << 1) ^ (value >> 31);
}

/**
 * Serialize IntConstant (32-bit signed)
 * Format: type_tag(0x02) + VLQ(zigzag_i32(value))
 */
export function serializeInt(value: number): string {
  const zigzag = zigZagEncodeInt(value);
  const vlq = encodeVLQ(BigInt(zigzag < 0 ? zigzag + 0x100000000 : zigzag));
  const buffer = Buffer.concat([Buffer.from([0x02]), vlq]);
  return buffer.toString('hex');
}

/**
 * Serialize LongConstant (64-bit signed)
 * Format: type_tag(0x04) + VLQ(zigzag_i64(value))
 */
export function serializeLong(value: bigint | number): string {
  const bigValue = typeof value === 'bigint' ? value : BigInt(value);
  const zigzag = zigZagEncode(bigValue);
  const vlq = encodeVLQ(zigzag);
  const buffer = Buffer.concat([Buffer.from([0x04]), vlq]);
  return buffer.toString('hex');
}

/**
 * Serialize Coll[Byte] (Collection of bytes)
 * Format: type_tag(0x0E) + element_type(0x01) + VLQ(length) + raw_bytes
 *
 * Note: Two formats exist in practice:
 * (A) 0e 01 VLQ(len) data - with SByte type tag
 * (B) 0e VLQ(len) data - without SByte type tag (node API)
 *
 * This implementation uses format (A) with explicit element type tag.
 */
export function serializeCollByte(data: string | Buffer | Uint8Array): string {
  let buffer: Buffer;

  if (typeof data === 'string') {
    // Assume hex string
    buffer = Buffer.from(data, 'hex');
  } else if (Buffer.isBuffer(data)) {
    buffer = data;
  } else {
    buffer = Buffer.from(data);
  }

  const typeTag = Buffer.from([0x0e]); // Coll type
  const elementType = Buffer.from([0x01]); // SByte element type
  const length = encodeVLQ(BigInt(buffer.length));

  const serialized = Buffer.concat([typeTag, elementType, length, buffer]);
  return serialized.toString('hex');
}

/**
 * Serialize SigmaProp (Sigma proposition)
 * Format: 0x08 + 0xcd + 33-byte compressed public key
 *
 * For P2PK addresses from ErgoTree:
 * ErgoTree format for P2PK: 0008cd<33-byte-pk>
 * We skip the first 4 bytes and use: 08cd<33-byte-pk>
 */
export function serializeSigmaProp(publicKey: string): string {
  // publicKey should be 33 bytes (66 hex chars)
  const pkBuffer = Buffer.from(publicKey, 'hex');

  if (pkBuffer.length !== 33) {
    throw new SerializationError('Public key must be 33 bytes', {
      expectedLength: 33,
      actualLength: pkBuffer.length,
    });
  }

  const buffer = Buffer.concat([Buffer.from([0x08, 0xcd]), pkBuffer]);
  return buffer.toString('hex');
}

/**
 * Serialize SBoolean (Boolean)
 * Format: type_tag(0x06) for false, type_tag(0x07) for true
 */
export function serializeBoolean(value: boolean): string {
  const buffer = Buffer.from([value ? 0x07 : 0x06]);
  return buffer.toString('hex');
}

/**
 * Serialize SOption (Optional value)
 * Format: type_tag(0x0b) for None, type_tag(0x0b) + inner_type for Some
 */
export function serializeOption(value: SValue | null): string {
  if (value === null) {
    const buffer = Buffer.from([0x0b]);
    return buffer.toString('hex');
  }
  // Some: 0x0b + serialized inner value
  const inner = serializeSValue(value);
  const buffer = Buffer.concat([Buffer.from([0x0b]), Buffer.from(inner, 'hex')]);
  return buffer.toString('hex');
}

/**
 * Serialize SPair (Tuple/Pair)
 * Format: type_tag(0x0d) + left_type_tag + left_data + right_type_tag + right_data
 *
 * Note: Simplified format - both elements are SValues with their type tags included
 */
export function serializePair(left: SValue, right: SValue): string {
  const leftSerialized = serializeSValue(left);
  const rightSerialized = serializeSValue(right);
  const buffer = Buffer.concat([
    Buffer.from([0x0d]),
    Buffer.from(leftSerialized, 'hex'),
    Buffer.from(rightSerialized, 'hex'),
  ]);
  return buffer.toString('hex');
}

/**
 * Serialize SValue to hex string
 */
export function serializeSValue(svalue: SValue): string {
  switch (svalue.type) {
    case 'Int':
      return serializeInt(svalue.value);
    case 'Long':
      return serializeLong(svalue.value);
    case 'Coll[Byte]':
    case 'Coll[SByte]':
      return serializeCollByte(svalue.value);
    case 'SigmaProp':
      return serializeSigmaProp(svalue.value);
    case 'Boolean':
      return serializeBoolean(svalue.value);
    case 'Option':
      return serializeOption(svalue.value);
    case 'Pair':
      return serializePair(svalue.left, svalue.right);
    default:
      throw new SerializationError('Unknown SValue type', { type: svalue });
  }
}

/**
 * Serialize multiple SValues (for multiple registers)
 */
export function serializeSValues(values: SValue[]): Record<string, string> {
  const result: Record<string, string> = {};
  const keys = ['R4', 'R5', 'R6', 'R7', 'R8', 'R9'] as const;

  for (let i = 0; i < Math.min(values.length, keys.length); i++) {
    result[keys[i]] = serializeSValue(values[i]);
  }

  return result;
}

/**
 * Deserialize IntConstant
 */
export function deserializeInt(hex: string): number {
  const buffer = Buffer.from(hex, 'hex');

  if (buffer[0] !== 0x02) {
    throw new SerializationError('Not an IntConstant', { prefix: buffer[0].toString(16) });
  }

  // Skip type tag and decode VLQ
  const { value: zigzag, offset } = decodeVLQ(buffer, 1);

  // ZigZag decode
  let value = Number(zigzag);
  value = (value >>> 1) ^ -(value & 1);

  return value;
}

/**
 * Deserialize LongConstant
 */
export function deserializeLong(hex: string): bigint {
  const buffer = Buffer.from(hex, 'hex');

  if (buffer[0] !== 0x04) {
    throw new SerializationError('Not a LongConstant', { prefix: buffer[0].toString(16) });
  }

  // Skip type tag and decode VLQ
  const { value: zigzag } = decodeVLQ(buffer, 1);

  // ZigZag decode
  return (zigzag >> 1n) ^ -(zigzag & 1n);
}

/**
 * Deserialize Coll[Byte]
 */
export function deserializeCollByte(hex: string): Buffer {
  const buffer = Buffer.from(hex, 'hex');

  if (buffer[0] !== 0x0e) {
    throw new SerializationError('Not a Coll[Byte]', { prefix: buffer[0].toString(16) });
  }

  // Check for element type tag (format A) or skip it (format B)
  let offset = 1;
  if (buffer[1] === 0x01) {
    offset = 2; // Skip element type tag
  }

  // Decode length
  const { value: length, offset: lengthOffset } = decodeVLQ(buffer, offset);

  // Extract data bytes
  const dataStart = lengthOffset;
  const dataEnd = dataStart + Number(length);
  return buffer.slice(dataStart, dataEnd);
}

/**
 * Decode VLQ-encoded value
 */
function decodeVLQ(buffer: Buffer, offset: number): { value: bigint; offset: number } {
  let value = 0n;
  let shift = 0n;
  let currentOffset = offset;
  let more = true;

  while (more && currentOffset < buffer.length) {
    const byte = BigInt(buffer[currentOffset]);
    value |= (byte & 0x7fn) << shift;
    more = (byte & 0x80n) !== 0n;
    currentOffset++;
    shift += 7n;
  }

  return { value, offset: currentOffset };
}

/**
 * Deserialize SBoolean (Boolean)
 */
export function deserializeBoolean(hex: string): boolean {
  const buffer = Buffer.from(hex, 'hex');

  if (buffer[0] !== 0x06 && buffer[0] !== 0x07) {
    throw new SerializationError('Not a Boolean', { prefix: buffer[0].toString(16) });
  }

  return buffer[0] === 0x07;
}

/**
 * Deserialize SOption (Optional value)
 */
export function deserializeOption(hex: string): SValue | null {
  const buffer = Buffer.from(hex, 'hex');

  if (buffer[0] !== 0x0b) {
    throw new SerializationError('Not an Option', { prefix: buffer[0].toString(16) });
  }

  // Check if it's None (only 0x0b byte) or Some (0x0b + inner value)
  if (buffer.length === 1) {
    return null; // None
  }

  // Some - deserialize the inner value (skip 0x0b byte)
  return deserializeSValue(hex.substring(2));
}

/**
 * Deserialize SPair (Tuple/Pair)
 */
export function deserializePair(hex: string): { left: SValue; right: SValue } {
  const buffer = Buffer.from(hex, 'hex');

  if (buffer[0] !== 0x0d) {
    throw new SerializationError('Not a Pair', { prefix: buffer[0].toString(16) });
  }

  // Skip pair type tag (0x0d)
  let offset = 1;

  // Deserialize left value
  const leftHex = hex.substring(offset * 2);
  const left = deserializeSValue(leftHex);

  // Calculate offset after left value
  const leftBuffer = Buffer.from(leftHex, 'hex');
  const leftTypeTag = leftBuffer[0];
  const leftLength = getSerializedValueLength(leftTypeTag, leftBuffer);

  offset += leftLength;

  // Deserialize right value
  const rightHex = hex.substring(offset * 2);
  const right = deserializeSValue(rightHex);

  return { left, right };
}

/**
 * Helper to get the length of a serialized SValue
 */
function getSerializedValueLength(typeTag: number, buffer: Buffer): number {
  switch (typeTag) {
    case 0x06: // Boolean false
    case 0x07: // Boolean true
      return 1;
    case 0x0b: // Option None
      return 1;
    case 0x02: { // Int
      const { offset } = decodeVLQ(buffer, 1);
      return offset;
    }
    case 0x04: { // Long
      const { offset } = decodeVLQ(buffer, 1);
      return offset;
    }
    case 0x0e: { // Coll[Byte]
      let offset = 1;
      if (buffer[1] === 0x01) {
        offset = 2;
      }
      const { offset: lengthOffset } = decodeVLQ(buffer, offset);
      const { value: length } = decodeVLQ(buffer, offset);
      return lengthOffset + Number(length);
    }
    default:
      // For complex types like Pair and Option with Some, we need to parse recursively
      // This is a simplified version - real implementation would need more sophisticated parsing
      return buffer.length;
  }
}

/**
 * Deserialize SValue based on type tag
 */
export function deserializeSValue(hex: string): SValue {
  const buffer = Buffer.from(hex, 'hex');
  const typeTag = buffer[0];

  switch (typeTag) {
    case 0x02:
      return { type: 'Int', value: deserializeInt(hex) };
    case 0x04:
      return { type: 'Long', value: deserializeLong(hex) };
    case 0x0e:
      return { type: 'Coll[Byte]', value: deserializeCollByte(hex).toString('hex') };
    case 0x08:
      // SigmaProp - return raw hex for now
      return { type: 'SigmaProp', value: hex.substring(2) };
    case 0x06:
    case 0x07:
      return { type: 'Boolean', value: deserializeBoolean(hex) };
    case 0x0b:
      return { type: 'Option', value: deserializeOption(hex) };
    case 0x0d: {
      const pair = deserializePair(hex);
      return { type: 'Pair', left: pair.left, right: pair.right };
    }
    default:
      throw new SerializationError('Unknown SValue type tag', { typeTag });
  }
}

/**
 * Format ergo value (nanoERG to ERG string)
 */
export function formatErg(value: bigint | number): string {
  const nanoErg = typeof value === 'bigint' ? value : BigInt(value);
  const erg = Number(nanoErg) / 1e9;
  return erg.toFixed(9).replace(/\.?0+$/, '');
}

/**
 * Parse erg string to nanoERG
 */
export function parseErg(erg: string): bigint {
  return BigInt(Math.round(parseFloat(erg) * 1e9));
}

/**
 * Format token amount with decimals
 */
export function formatTokenAmount(amount: bigint, decimals = 0): string {
  if (decimals === 0) {
    return amount.toString();
  }

  const divisor = BigInt(10 ** decimals);
  const whole = amount / divisor;
  const fraction = amount % divisor;

  const fractionStr = fraction.toString().padStart(decimals, '0');
  const trimmedFraction = fractionStr.replace(/0+$/, '');

  if (trimmedFraction === '') {
    return whole.toString();
  }

  return `${whole}.${trimmedFraction}`;
}
