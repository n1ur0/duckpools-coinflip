import { HelpCircle, Dice5, Target, Zap } from 'lucide-react';
import { formatErg } from '../utils/ergo';
import type { GameType } from '../types/Game';
import './GameCard.css';

export interface GameCardProps {
  gameType: GameType;
  name: string;
  description: string;
  tvl?: string; // nanoERG
  houseEdge: number;
  icon?: React.ReactNode;
  isActive?: boolean;
  onClick?: () => void;
}

const GAME_CONFIG: Record<GameType, { icon: React.ReactNode; defaultName: string; description: string }> = {
  coinflip: {
    icon: <HelpCircle size={32} />,
    defaultName: 'Coin Flip',
    description: 'Heads or tails? 50/50 odds with 3% house edge.',
  },
  dice: {
    icon: <Dice5 size={32} />,
    defaultName: 'Dice',
    description: 'Roll the dice and predict your outcome.',
  },
  plinko: {
    icon: <Target size={32} />,
    defaultName: 'Plinko',
    description: 'Drop the ball and watch it fall to your prize.',
  },
  crash: {
    icon: <Zap size={32} />,
    defaultName: 'Crash',
    description: 'Cash out before the crash to win!',
  },
};

export default function GameCard({
  gameType,
  name,
  description,
  tvl,
  houseEdge,
  icon,
  isActive = false,
  onClick,
}: GameCardProps) {
  const config = GAME_CONFIG[gameType];
  const displayName = name || config.defaultName;
  const displayDescription = description || config.description;
  const displayIcon = icon || config.icon;

  return (
    <button
      className={`game-card ${isActive ? 'game-card--active' : ''}`}
      onClick={onClick}
      disabled={!onClick}
    >
      <div className="game-card__icon-wrapper">{displayIcon}</div>
      <div className="game-card__content">
        <h3 className="game-card__title">{displayName}</h3>
        <p className="game-card__description">{displayDescription}</p>
        <div className="game-card__stats">
          {tvl && (
            <div className="game-card__stat">
              <span className="game-card__stat-label">TVL</span>
              <span className="game-card__stat-value">{formatErg(tvl)} ERG</span>
            </div>
          )}
          <div className="game-card__stat">
            <span className="game-card__stat-label">House Edge</span>
            <span className="game-card__stat-value">{(houseEdge * 100).toFixed(1)}%</span>
          </div>
        </div>
      </div>
      {onClick && <div className="game-card__play-badge">Play Now</div>}
    </button>
  );
}
