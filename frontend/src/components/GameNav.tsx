import { motion } from 'framer-motion';
import { useGameStore } from '../stores';
import type { GameType } from '../types/Game';

const games: { id: GameType; label: string; comingSoon?: boolean }[] = [
  { id: 'coinflip', label: 'Coin Flip' },
  { id: 'dice', label: 'Dice' },
  { id: 'plinko', label: 'Plinko' },
];

export default function GameNav() {
  const activeGame = useGameStore((s) => s.activeGame);
  const setActiveGame = useGameStore((s) => s.setActiveGame);

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
              onClick={() => setActiveGame(game.id)}
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
