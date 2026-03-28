import React, { useState, useRef, useEffect } from 'react';
import { CircleDot, Dice5, Triangle, TrendingUp } from 'lucide-react';
import type { GameType } from '../types/Game';
import './GameNav.css';

export type { GameType };

interface GameTab {
  id: GameType;
  label: string;
  icon: React.ReactNode;
  comingSoon?: boolean;
}

const GAME_TABS: GameTab[] = [
  { id: 'coinflip', label: 'Coinflip', icon: <CircleDot size={18} /> },
  { id: 'dice', label: 'Dice', icon: <Dice5 size={18} /> },
  { id: 'plinko', label: 'Plinko', icon: <Triangle size={18} /> },
  { id: 'crash', label: 'Crash', icon: <TrendingUp size={18} />, comingSoon: true },
];

interface GameNavProps {
  activeGame: GameType;
  onGameChange: (game: GameType) => void;
  className?: string;
}

const GameNav: React.FC<GameNavProps> = ({ activeGame, onGameChange, className = '' }) => {
  const [showMobileMenu, setShowMobileMenu] = useState(false);
  const navRef = useRef<HTMLDivElement>(null);
  const tabsRef = useRef<HTMLDivElement>(null);

  // Close mobile menu on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (navRef.current && !navRef.current.contains(e.target as Node)) {
        setShowMobileMenu(false);
      }
    };
    if (showMobileMenu) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [showMobileMenu]);

  // Close mobile menu on resize to desktop
  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth > 640) {
        setShowMobileMenu(false);
      }
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const handleTabClick = (tab: GameTab) => {
    if (tab.comingSoon) return;
    onGameChange(tab.id);
    setShowMobileMenu(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent, tab: GameTab) => {
    if (tab.comingSoon) return;
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onGameChange(tab.id);
      setShowMobileMenu(false);
    }
  };

  return (
    <nav className={`game-nav ${className}`} ref={navRef} role="tablist" aria-label="Game selection">
      {/* Mobile toggle button */}
      <button
        className="game-nav-mobile-toggle"
        onClick={() => setShowMobileMenu(prev => !prev)}
        aria-expanded={showMobileMenu}
        aria-controls="game-nav-tabs"
        aria-label="Select game"
      >
        <span className="game-nav-mobile-toggle-icon">
          {GAME_TABS.find(t => t.id === activeGame)?.icon}
        </span>
        <span className="game-nav-mobile-toggle-label">
          {GAME_TABS.find(t => t.id === activeGame)?.label}
        </span>
        <span className={`game-nav-mobile-toggle-chevron ${showMobileMenu ? 'open' : ''}`}>
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <path d="M3 4.5L6 7.5L9 4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </span>
      </button>

      {/* Tab bar */}
      <div
        className={`game-nav-tabs ${showMobileMenu ? 'game-nav-tabs--open' : ''}`}
        id="game-nav-tabs"
        ref={tabsRef}
      >
        {GAME_TABS.map(tab => {
          const isActive = tab.id === activeGame;
          return (
            <button
              key={tab.id}
              className={`game-nav-tab ${isActive ? 'game-nav-tab--active' : ''} ${tab.comingSoon ? 'game-nav-tab--coming' : ''}`}
              onClick={() => handleTabClick(tab)}
              onKeyDown={e => handleKeyDown(e, tab)}
              role="tab"
              aria-selected={isActive}
              aria-disabled={tab.comingSoon || undefined}
              tabIndex={tab.comingSoon ? -1 : 0}
              title={tab.comingSoon ? `${tab.label} — coming soon` : tab.label}
            >
              <span className="game-nav-tab-icon">{tab.icon}</span>
              <span className="game-nav-tab-label">{tab.label}</span>
              {tab.comingSoon && (
                <span className="game-nav-tab-badge">SOON</span>
              )}
              {isActive && (
                <span className="game-nav-tab-indicator" />
              )}
            </button>
          );
        })}
      </div>
    </nav>
  );
};

export default GameNav;
export { GAME_TABS };
export type { GameTab };
