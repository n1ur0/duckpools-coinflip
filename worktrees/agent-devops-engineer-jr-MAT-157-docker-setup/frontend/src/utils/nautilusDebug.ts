// Nautilus debug utilities for development
// Only loaded in DEV mode via dynamic import in main.tsx

if (import.meta.env.DEV) {
  console.log('[Nautilus Debug] Development mode active');
  console.log('[Nautilus Debug] ergo object:', typeof (window as any).ergo);

  // Poll for Nautilus injection
  let checks = 0;
  const interval = setInterval(() => {
    checks++;
    if ((window as any).ergo) {
      console.log('[Nautilus Debug] Nautilus wallet detected after', checks * 500, 'ms');
      clearInterval(interval);
    } else if (checks > 20) {
      console.log('[Nautilus Debug] Nautilus wallet not detected after 10s');
      clearInterval(interval);
    }
  }, 500);
}
