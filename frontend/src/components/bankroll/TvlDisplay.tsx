import { formatErg } from '../../utils/ergo';
import { useBankrollStore } from '../../stores/bankrollStore';
import './TvlDisplay.css';

export default function TvlDisplay() {
  const tvl = useBankrollStore((s) => s.tvl);
  const isLoading = useBankrollStore((s) => s.isLoadingOverview);

  return (
    <div className="bk-tvl">
      <div className="bk-tvl-icon">&#128176;</div>
      <div className="bk-tvl-label">Total Value Locked</div>
      <div className="bk-tvl-value">
        {isLoading && !tvl ? (
          <span className="bk-tvl-skeleton" />
        ) : tvl ? (
          <>
            <span className="bk-tvl-erg">{formatErg(tvl.totalErg)} ERG</span>
            {tvl.totalUsd !== '0' && (
              <span className="bk-tvl-usd">
                ${Number(tvl.totalUsd).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
            )}
          </>
        ) : (
          <span className="bk-tvl-na">No data</span>
        )}
      </div>
    </div>
  );
}
