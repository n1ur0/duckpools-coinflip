import { useWallet } from '../../contexts/WalletContext';
import { useBankrollStore } from '../../stores/bankrollStore';
import { formatErg } from '../../utils/ergo';
import './LpStats.css';

export default function LpStats() {
  const { isConnected, walletAddress } = useWallet();
  const lpSummary = useBankrollStore((s) => s.lpSummary);
  const myLpStats = useBankrollStore((s) => s.myLpStats);
  const isLoading = useBankrollStore((s) => s.isLoadingLpStats);

  if (!isConnected) {
    return (
      <div className="bk-lp">
        <div className="bk-lp-icon">&#128184;</div>
        <div className="bk-lp-label">LP Stats</div>
        <div className="bk-lp-connect">Connect wallet to view LP stats</div>
      </div>
    );
  }

  return (
    <div className="bk-lp">
      <div className="bk-lp-icon">&#128184;</div>
      <div className="bk-lp-label">LP Stats</div>

      {isLoading && !myLpStats ? (
        <div className="bk-lp-skeleton-wrap">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="bk-lp-skeleton-row">
              <div className="bk-lp-skeleton-key" />
              <div className="bk-lp-skeleton-val" />
            </div>
          ))}
        </div>
      ) : myLpStats ? (
        <div className="bk-lp-body">
          {/* Personal LP card */}
          <div className="bk-lp-section bk-lp-section--personal">
            <div className="bk-lp-section-title">Your Position</div>
            <div className="bk-lp-apy">
              <span className="bk-lp-apy-value">{myLpStats.apy.toFixed(1)}%</span>
              <span className="bk-lp-apy-label">APY</span>
            </div>
            <div className="bk-lp-grid">
              <LpRow label="Deposited" value={`${formatErg(myLpStats.depositedErg)} ERG`} />
              <LpRow label="Current Value" value={`${formatErg(myLpStats.currentValueErg)} ERG`} />
              <LpRow label="LP Shares" value={myLpStats.currentShares} />
              <LpRow label="Total Return" value={`${formatErg(myLpStats.totalReturnErg)} ERG`}
                positive={parseFloat(myLpStats.totalReturnErg) >= 0} />
              <LpRow label="Deposits" value={String(myLpStats.depositCount)} />
            </div>
          </div>

          {/* Pool-wide stats */}
          {lpSummary && (
            <div className="bk-lp-section">
              <div className="bk-lp-section-title">Pool Overview</div>
              <div className="bk-lp-grid">
                <LpRow label="Total Providers" value={String(lpSummary.totalProviders)} />
                <LpRow label="Total Deposited" value={`${formatErg(lpSummary.totalDepositedErg)} ERG`} />
                <LpRow label="Avg APY" value={`${lpSummary.avgApy.toFixed(1)}%`} />
                <LpRow label="Fees Distributed" value={`${formatErg(lpSummary.totalDistributedErg)} ERG`} />
              </div>
            </div>
          )}

          {walletAddress && !myLpStats && !isLoading && (
            <div className="bk-lp-not-lp">
              You are not a liquidity provider yet. Deposit ERG to earn from the house edge.
            </div>
          )}
        </div>
      ) : (
        <div className="bk-lp-not-lp">
          You are not a liquidity provider yet. Deposit ERG to earn from the house edge.
        </div>
      )}
    </div>
  );
}

function LpRow({ label, value, positive }: { label: string; value: string; positive?: boolean }) {
  return (
    <div className="bk-lp-row">
      <span className="bk-lp-key">{label}</span>
      <span className={`bk-lp-val ${positive === true ? 'bk-lp-val--pos' : positive === false ? 'bk-lp-val--neg' : ''}`}>
        {value}
      </span>
    </div>
  );
}
