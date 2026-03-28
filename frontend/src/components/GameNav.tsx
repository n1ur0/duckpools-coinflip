import React from 'react';
import { motion } from 'framer-motion';
import { GameType } from '../types/Game';

interface GameNavProps {
  activeGame: GameType | null;
  onGameChange: (game: GameType) => void;
}

const games: { id: GameType; label: string; comingSoon?: boolean }[] = [
  { id: 'coinflip', label: 'Coin Flip' },
  { id: 'dice', label: 'Dice' },
  { id: 'plinko', label: 'Plinko', comingSoon: true },
];

export default function GameNav({ activeGame, onGameChange }: GameNavProps) {
  return (
    <nav className="game-nav">
      <div className="game-nav-tabs">
        {games.map((game) => {
          if (game.comingSoon) {
            return (
              <div key={game.id} className="game-nav-tab game-nav-tab--coming-soon">
                <span className="game-nav-label">{game.label}</span>
                <span className="game-nav-coming-soon">Soon</span>
              </div>
            );
          }

          const isActive = activeGame === game.id;
          
          return (
            <button
              key={game.id}
              className={`game-nav-tab ${isActive ? 'game-nav-tab--active' : ''}`}
              onClick={() => onGameChange(game.id)}
              disabled={isActive}
            >
              <span className="game-nav-label">{game.label}</span>
              {isActive && (
                <motion.div
                  className="game-nav-indicator"
                  layoutId="activeGameIndicator"
                  initial={false}
                  animate={{ opacity: 1 }}
                  transition={{
                    type: 'spring',
                    stiffness: 500,
                    damping: 30,
                  }}
                />
              )}
            </button>
          );
        })}
      </div>
    </nav>
  );
}