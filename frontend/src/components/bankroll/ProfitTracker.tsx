import { formatErg } from '../../utils/ergo';
import { useBankrollStore } from '../../stores/bankrollStore';
import './ProfitTracker.css';

function formatSignedErg(nanoErg: string): string {
  const val = parseFloat(nanoErg);
  const formatted = formatErg(Math.abs(val));
  return val >= 0 ? `+${formatted}` : `-${formatted}`;
}

export default function ProfitTracker() {
  const profit = useBankrollStore((s) => s.profit);
  const isLoading = useBankrollStore((s) => s.isLoadingOverview);

  const cumProfit = profit ? parseFloat(profit.cumulativeProfitErg) : 0;
  const dailyProfit = profit ? parseFloat(profit.dailyProfitErg) : 0;
  const isCumPositive = cumProfit >= 0;
  const isDailyPositive = dailyProfit >= 0;

  return (
    <div className="bk-profit">
      <div className="bk-profit-icon">&#128200;</div>
      <div className="bk-profit-label">House Profit / Loss</div>

      {isLoading && !profit ? (
        <div className="bk-profit-skeleton-wrap">
          <div className="bk-profit-skeleton" />
          <div className="bk-profit-skeleton bk-profit-skeleton--small" />
        </div>
      ) : profit ? (
        <div className="bk-profit-values">
          <div className="bk-profit-main">
            <span className={`bk-profit-number ${isCumPositive ? 'bk-profit-positive' : 'bk-profit-negative'}`}>
              {formatSignedErg(profit.cumulativeProfitErg)} ERG
            </span>
            <span className="bk-profit-sublabel">Cumulative</span>
          </div>
          <div className="bk-profit-divider" />
          <div className="bk-profit-daily">
            <span className={`bk-profit-number ${isDailyPositive ? 'bk-profit-positive' : 'bk-profit-negative'}`}>
              {formatSignedErg(profit.dailyProfitErg)} ERG
            </span>
            <span className="bk-profit-sublabel">Last 24h</span>
          </div>
        </div>
      ) : (
        <div className="bk-profit-na">No data</div>
      )}
    </div>
  );
}
