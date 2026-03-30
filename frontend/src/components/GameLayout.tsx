import { ReactNode } from 'react';
import { NavLink } from 'react-router-dom';
import './GameLayout.css';

interface GameLayoutProps {
  children: ReactNode;
}

function GameLayout({ children }: GameLayoutProps) {
  return (
    <div className="game-layout">
      {/* Navigation */}
      <nav className="game-nav" aria-label="Game navigation">
        <div className="nav-content">
          <NavLink
            to="/"
            end
            className={({ isActive }) =>
              `nav-item${isActive ? ' active' : ''}`
            }
          >
            Home
          </NavLink>
          <NavLink
            to="/play/coinflip"
            className={({ isActive }) =>
              `nav-item${isActive ? ' active' : ''}`
            }
          >
            Coin Flip
          </NavLink>
          <NavLink
            to="/play/dice"
            className={({ isActive }) =>
              `nav-item${isActive ? ' active' : ''}`
            }
          >
            Dice
          </NavLink>
          <NavLink
            to="/play/plinko"
            className={({ isActive }) =>
              `nav-item${isActive ? ' active' : ''}`
            }
          >
            Plinko
          </NavLink>
        </div>
      </nav>

      {/* Main Content */}
      <main className="game-main">
        {children}
      </main>
    </div>
  );
}

export default GameLayout;
