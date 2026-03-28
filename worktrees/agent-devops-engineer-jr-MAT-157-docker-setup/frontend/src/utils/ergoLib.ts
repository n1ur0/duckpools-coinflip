import type { IErgoLib } from '../types/eip12';

let ergoLibInstance: IErgoLib | null = null;
let ergoLibInitPromise: Promise<IErgoLib> | null = null;
let initFailed = false;

export function isErgoLibInitialized(): boolean {
  return ergoLibInstance !== null;
}

export function wasErgoLibInitFailed(): boolean {
  return initFailed;
}

// Note: we use a variable to prevent Vite from statically analyzing
// and failing on the missing ergo-lib-wasm-browser package.
const ERGO_LIB_MODULE = 'ergo-lib-wasm-browser';

export async function initErgoLib(): Promise<IErgoLib> {
  if (ergoLibInstance) return ergoLibInstance;
  if (ergoLibInitPromise) return ergoLibInitPromise;

  ergoLibInitPromise = (async () => {
    try {
      // eslint-disable-next-line @typescript-eslint/no-implied-eval
      const ergo = await import(/* @vite-ignore */ ERGO_LIB_MODULE);
      const initFn = (ergo as any).default || (ergo as any).init;
      if (initFn) await initFn();
      ergoLibInstance = ergo as unknown as IErgoLib;
      return ergoLibInstance;
    } catch (err) {
      console.warn('[ergoLib] WASM module not available:', err);
      initFailed = true;
      ergoLibInitPromise = null;
      // Return a minimal stub so the app doesn't crash
      ergoLibInstance = null;
      throw err;
    }
  })();

  return ergoLibInitPromise;
}

export function ergoLib(): IErgoLib {
  if (!ergoLibInstance) {
    throw new Error('ErgoLib WASM not initialized. Call initErgoLib() first.');
  }
  return ergoLibInstance;
}

export async function addressToErgoTree(address: string): Promise<string> {
  try {
    const lib = await initErgoLib();
    return lib.Address.from_base58(address).to_ergo_tree().to_hex();
  } catch {
    return '';
  }
}

export async function validateAddress(address: string): Promise<boolean> {
  try {
    const lib = await initErgoLib();
    lib.Address.from_base58(address);
    return true;
  } catch {
    return false;
  }
}
