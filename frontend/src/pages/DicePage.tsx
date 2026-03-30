import GameHistory from '../components/GameHistory';
import StatsDashboard from '../components/StatsDashboard';
import Leaderboard from '../components/Leaderboard';
import './DicePage.css';

function DicePage() {
  return (
    <div className="dice-page">
      <div className="page-content">
        {/* Dice Game Content */}
        <div className="game-container">
          <div className="dice-game-placeholder">
            <h2>🎲 Dice Game</h2>
            <p>Coming Soon!</p>
          </div>
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

export default DicePage;