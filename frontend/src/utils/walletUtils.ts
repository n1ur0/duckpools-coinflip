export function truncateTxId(txId: string, chars: number = 8): string {
  if (!txId || txId.length <= chars * 2) return txId;
  return `${txId.slice(0, chars)}...${txId.slice(-chars)}`;
}

export function timeAgo(timestamp: string): string {
  const now = Date.now();
  const then = new Date(timestamp).getTime();
  const diffMs = now - then;
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHr = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHr / 24);

  if (diffSec < 60) return 'just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHr < 24) return `${diffHr}h ago`;
  if (diffDay < 30) return `${diffDay}d ago`;
  return new Date(timestamp).toLocaleDateString();
}

export function getTierColor(tier: string): string {
  switch (tier.toLowerCase()) {
    case 'bronze': return '#cd7f32';
    case 'silver': return '#c0c0c0';
    case 'gold': return '#ffd700';
    case 'platinum': return '#e5e4e2';
    case 'diamond': return '#b9f2ff';
    default: return '#888';
  }
}
