import { Component, ErrorInfo, ReactNode, useState, useEffect } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { WalletProvider } from './contexts/WalletContext';
import { useGameStore } from './stores';
import GameHistory from './components/GameHistory';
import StatsDashboard from './components/StatsDashboard';
import Leaderboard from './components/Leaderboard';
import CompPoints from './components/CompPoints';
import BetForm from './components/BetForm';
import PoolManager from './components/PoolManager';
import TestWallet from './components/TestWallet';
import WalletConnector from './components/WalletConnector';
import GameNav from './components/GameNav';
import DiceGame from './components/games/DiceGame';
import OnboardingWizard, {
  hasCompletedOnboarding,
  triggerOnboarding,
} from './components/OnboardingWizard';
import './App.css';

interface ErrorBoundaryState {
  hasError: boolean;
  error?: Error;
}

class ErrorBoundary extends Component<{ children: ReactNode }, ErrorBoundaryState> {
  constructor(props: { children: ReactNode }) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('App error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="error-boundary">
          <div className="error-boundary-card">
            <span className="error-icon">&#9888;&#65039;</span>
            <h2>Something went wrong</h2>
            <p>{this.state.error?.message}</p>
            <button onClick={() => window.location.reload()}>
              Reload Page
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

function App() {
  const network = import.meta.env.VITE_NETWORK || 'testnet';
  const explorerUrl = import.meta.env.VITE_EXPLORER_URL || 'https://testnet.ergoplatform.com';
  const [showDevPanel, setShowDevPanel] = useState(false);
  const activeGame = useGameStore((s) => s.activeGame);

  // Onboarding state
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [manuallyTriggeredOnboarding, setManuallyTriggeredOnboarding] = useState(false);
  const [highlightBetForm, setHighlightBetForm] = useState(false);

  useEffect(() => {
    if (!hasCompletedOnboarding()) {
      setShowOnboarding(true);
    }
  }, []);

  useEffect(() => {
    const handleTriggerOnboarding = () => {
      setManuallyTriggeredOnboarding(true);
      setShowOnboarding(true);
    };

    window.addEventListener('trigger-onboarding', handleTriggerOnboarding);
    return () => window.removeEventListener('trigger-onboarding', handleTriggerOnboarding);
  }, []);

  const handleOnboardingComplete = () => {
    setShowOnboarding(false);
    setManuallyTriggeredOnboarding(false);
    setHighlightBetForm(true);
    setTimeout(() => setHighlightBetForm(false), 3000);
  };

  const handleOnboardingClose = () => {
    setShowOnboarding(false);
    setManuallyTriggeredOnboarding(false);
  };

  const handleHelpClick = () => {
    triggerOnboarding();
  };

  return (
    <ErrorBoundary>
      <WalletProvider>
        <div className="app">
          <a href="#main-content" className="skip-link">
            Skip to content
          </a>

          {/* Header */}
          <header className="app-header">
            <div className="header-left">
              <span className="header-logo">&#129689;</span>
              <h1 className="header-title">DuckPools</h1>
              <span className={`network-badge network-${network}`}>
                {network.toUpperCase()}
              </span>
            </div>
            <div className="header-right">
              <button
                className="help-button"
                onClick={handleHelpClick}
                title="Show onboarding help"
                aria-label="Show onboarding help"
              >
                Help
              </button>
              <a
                href={explorerUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="explorer-link"
              >
                Explorer &#8599;
              </a>
              <WalletConnector />
            </div>
          </header>

          {/* Main */}
          <main id="main-content" className="app-main">
            <div className="main-content">
              {/* Game Navigation */}
              <GameNav />
              
              {/* Game Content with Animation */}
              <div className="game-container">
                <AnimatePresence mode="wait">
                  <motion.div
                    key={activeGame}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.15, ease: "easeInOut" }}
                    className="game-transition-wrapper"
                  >
                    {activeGame === 'coinflip' && (
                      <div className={highlightBetForm ? 'bet-form-highlight' : ''}>
                        <BetForm />
                      </div>
                    )}
                    {activeGame === 'dice' && (
                      <DiceGame />
                    )}
                    {activeGame === 'plinko' && (
                      <div className="coming-soon-game">
                        <h3>Plinko Game</h3>
                        <p>Coming soon!</p>
                      </div>
                    )}
                  </motion.div>
                </AnimatePresence>
              </div>
              
              <PoolManager />
              <GameHistory />
              <StatsDashboard />
              <CompPoints />
              <Leaderboard />
            </div>

            {showDevPanel && (
              <div className="dev-panel">
                <div className="dev-panel-header">
                  <span>&#129504; Developer Tools</span>
                  <button
                    className="dev-panel-close"
                    onClick={() => setShowDevPanel(false)}
                    aria-label="Close dev panel"
                  >
                    &#10005;
                  </button>
                </div>
                <TestWallet />
              </div>
            )}
          </main>

          {/* Footer */}
          <footer className="app-footer">
            <div className="footer-content">
              <p className="footer-disclaimer">
                &#9888;&#65039; Decentralized gambling on Ergo. Play responsibly. All transactions are final.
              </p>
              <div className="footer-links">
                <a href="https://ergoplatform.com" target="_blank" rel="noopener noreferrer">
                  About Ergo
                </a>
                <a href="https://github.com/duckpools/coinflip-game" target="_blank" rel="noopener noreferrer">
                  GitHub
                </a>
                <a href="https://discord.gg/duckpools" target="_blank" rel="noopener noreferrer">
                  Discord
                </a>
                <button
                  className="footer-dev-btn"
                  onClick={() => setShowDevPanel(prev => !prev)}
                  title="Toggle developer tools"
                >
                  Dev {showDevPanel ? '&#9650;' : '&#9660;'}
                </button>
              </div>
            </div>
          </footer>

          {/* Onboarding Wizard */}
          {showOnboarding && (
            <OnboardingWizard
              isOpen={showOnboarding}
              onComplete={handleOnboardingComplete}
              onClose={handleOnboardingClose}
              manuallyTriggered={manuallyTriggeredOnboarding}
            />
          )}
        </div>
      </WalletProvider>
    </ErrorBoundary>
  );
}

export default App;
