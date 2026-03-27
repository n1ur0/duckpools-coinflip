// ERG/nanoERG conversion utilities

export const NANOERG_PER_ERG = 1_000_000_000;

export function ergToNanoErg(erg: string | number): string {
  const ergNum = typeof erg === 'string' ? parseFloat(erg) : erg;
  if (isNaN(ergNum) || ergNum < 0) return '0';
  return Math.floor(ergNum * NANOERG_PER_ERG).toString();
}

export function nanoErgToErg(nanoErg: string | number): string {
  const nano = typeof nanoErg === 'string' ? parseInt(nanoErg, 10) : nanoErg;
  if (isNaN(nano)) return '0';
  return (nano / NANOERG_PER_ERG).toFixed(9).replace(/\.?0+$/, '');
}

export function formatErg(nanoErg: string | number, decimals: number = 4): string {
  if (nanoErg === '0' || nanoErg === 0) return '0.0000';
  const erg = nanoErgToErg(nanoErg);
  const num = parseFloat(erg);
  if (isNaN(num)) return '0.0000';
  return num.toFixed(decimals);
}

export function formatAddress(address: string, chars: number = 6): string {
  if (!address || address.length <= chars * 2) return address;
  return `${address.slice(0, chars)}...${address.slice(-chars)}`;
}

export async function copyToClipboard(text: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed';
    textarea.style.left = '-999999px';
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand('copy');
    document.body.removeChild(textarea);
  }
}
