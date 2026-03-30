import { useState } from 'react';
import './HomePage.css';

function HomePage() {
  const [selectedGame, setSelectedGame] = useState<string | null>(null);

  return (
    <div className="home-page">
      <div className="home-content">
        <div className="hero-section">
          <h1 className="hero-title">Welcome to DuckPools</h1>
          <p className="hero-subtitle">Play provably fair games on the Ergo blockchain</p>
        </div>

        <div className="game-selector">
          <h2 className="selector-title">Choose Your Game</h2>
          <div className="game-options">
            <button 
              className={`game-option ${selectedGame === 'coinflip' ? 'selected' : ''}`}
              onClick={() => setSelectedGame('coinflip')}
            >
              🪙 Coin Flip
            </button>
            <button 
              className={`game-option ${selectedGame === 'dice' ? 'selected' : ''}`}
              onClick={() => setSelectedGame('dice')}
            >
              🎲 Dice
            </button>
            <button 
              className={`game-option ${selectedGame === 'plinko' ? 'selected' : ''}`}
              onClick={() => setSelectedGame('plinko')}
            >
              🎰 Plinko
            </button>
          </div>
        </div>

        <div className="featured-games">
          <h2 className="featured-title">Featured Games</h2>
          <div className="games-grid">
            <div className="game-card">
              <div className="game-icon">🪙</div>
              <h3 className="game-name">Coin Flip</h3>
              <p className="game-description">Classic heads or tails betting game</p>
            </div>
            <div className="game-card">
              <div className="game-icon">🎲</div>
              <h3 className="game-name">Dice</h3>
              <p className="game-description">Roll the dice and test your luck</p>
            </div>
            <div className="game-card">
              <div className="game-icon">🎰</div>
              <h3 className="game-name">Plinko</h3>
              <p className="game-description">Drop the ball and watch it fall</p>
            </div>
          </div>
        </div>

        <div className="how-it-works">
          <h2 className="how-it-works-title">How It Works</h2>
          <div className="steps">
            <div className="step">
              <div className="step-number">1</div>
              <div className="step-content">
                <h3 className="step-title">Connect Wallet</h3>
                <p className="step-description">Use your Ergo wallet to play</p>
              </div>
            </div>
            <div className="step">
              <div className="step-number">2</div>
              <div className="step-content">
                <h3 className="step-title">Choose Game</h3>
                <p className="step-description">Pick your favorite game</p>
              </div>
            </div>
            <div className="step">
              <div className="step-number">3</div>
              <div className="step-content">
                <h3 className="step-title">Place Bet</h3>
                <p className="step-description">Bet with ERG and play</p>
              </div>
            </div>
            <div className="step">
              <div className="step-number">4</div>
              <div className="step-content">
                <h3 className="step-title">Win & Collect</h3>
                <p className="step-description">Collect your winnings instantly</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default HomePage;