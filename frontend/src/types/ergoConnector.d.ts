/**
 * TypeScript declarations for the Ergo wallet connector extension
 */

import type { EIP12Connection } from './eip12';

declare global {
  interface Window {
    ergoConnector?: Record<string, EIP12Connection>;
  }
}

export {};