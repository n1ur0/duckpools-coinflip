import CoinFlipGame from '../components/games/CoinFlipGame';
import GameHistory from '../components/GameHistory';
import StatsDashboard from '../components/StatsDashboard';
import Leaderboard from '../components/Leaderboard';
import './CoinflipPage.css';

function CoinflipPage() {
  return (
    <div className="coinflip-page">
      <div className="page-content">
        {/* Game Container */}
        <div className="game-container">
          <CoinFlipGame />
        </div>

        {/* Game History */}
        <GameHistory />

        {/* Stats and Leaderboard */}
        <div className="stats-section">
          <StatsDashboard />
          <Leaderboard />
        </div>
      </div>
    </div>
  );
}

export default CoinflipPage;