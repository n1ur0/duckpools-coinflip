// VLQ encoding for Sigma-state register values
function encodeVLQ(value: number): string {
  const bytes: number[] = [];
  let v = value;
  do {
    let byte = v & 0x7f;
    v >>>= 7;
    if (v > 0) byte |= 0x80;
    bytes.push(byte);
  } while (v > 0);
  return bytes.map(b => b.toString(16).padStart(2, '0')).join('');
}

// BigInt VLQ encoding — avoids precision loss for values > 2^53 (PROTO-1)
function encodeVLQBigInt(value: bigint): string {
  if (value === 0n) return '00';
  const bytes: number[] = [];
  let remaining = value;
  while (remaining > 0n) {
    let byte = Number(remaining & 0x7fn);
    remaining >>= 7n;
    if (remaining > 0n) byte |= 0x80;
    bytes.push(byte);
  }
  return bytes.map(b => b.toString(16).padStart(2, '0')).join('');
}

function zigzagEncode32(value: number): number {
  return (value << 1) ^ (value >> 31);
}

export function zigzagEncode64(value: bigint): bigint {
  return (value << 1n) ^ (value >> 63n);
}

// IntConstant: type_tag(0x02) + VLQ(zigzag_i32)
export function encodeIntConstant(value: number): string {
  return '02' + encodeVLQ(zigzagEncode32(value));
}

// LongConstant: type_tag(0x04) + VLQ(zigzag_i64)
export function encodeLongConstant(value: number | bigint): string {
  const bigValue = typeof value === 'bigint' ? value : BigInt(value);
  // Zigzag-encode as BigInt to avoid precision loss for values > 2^53 (PROTO-1)
  const zigzag = (bigValue << 1n) ^ (bigValue >> 63n);
  const unsigned = BigInt.asUintN(64, zigzag);
  return '04' + encodeVLQBigInt(unsigned);
}

// Coll[Byte]: type_tag(0x0E) + element_type(0x01) + VLQ(length) + raw_bytes
export function encodeCollByte(bytes: Uint8Array | string): string {
  let hex: string;
  if (typeof bytes === 'string') {
    hex = bytes.startsWith('0x') ? bytes.slice(2) : bytes;
  } else {
    hex = Array.from(bytes).map(b => b.toString(16).padStart(2, '0')).join('');
  }
  const len = hex.length / 2;
  return '0e01' + encodeVLQ(len) + hex;
}

export function encodeHexAsCollByte(hexStr: string): string {
  return encodeCollByte(hexStr);
}

export function encodeStringAsCollByte(str: string): string {
  const encoder = new TextEncoder();
  return encodeCollByte(encoder.encode(str));
}
