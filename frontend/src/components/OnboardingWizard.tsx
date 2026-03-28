import { useState, useEffect } from 'react';
import { useWallet } from '../contexts/WalletContext';
import './OnboardingWizard.css';

// ─── Exported utilities ────────────────────────────────────────────

const ONBOARDING_KEY = 'duckpools_onboarding_done';

export function hasCompletedOnboarding(): boolean {
  try {
    return localStorage.getItem(ONBOARDING_KEY) === 'true';
  } catch {
    return false;
  }
}

export function markOnboardingComplete(): void {
  try {
    localStorage.setItem(ONBOARDING_KEY, 'true');
  } catch {
    // localStorage unavailable
  }
}

const ONBOARDING_EVENT = 'duckpools:show-onboarding';

export function triggerOnboarding(): void {
  window.dispatchEvent(new CustomEvent(ONBOARDING_EVENT));
}

// ─── Types ─────────────────────────────────────────────────────────

interface OnboardingWizardProps {
  isOpen?: boolean;
  onComplete?: () => void;
  onClose?: () => void;
  manuallyTriggered?: boolean;
}

interface Step {
  icon: string;
  heading: string;
  description: string;
  detail?: React.ReactNode;
}

// ─── Steps ─────────────────────────────────────────────────────────

const STEPS: Step[] = [
  {
    icon: '\u{1F986}', // duck
    heading: 'Welcome to DuckPools',
    description:
      'The premier coinflip gambling platform on the Ergo blockchain. Fair, transparent, and provably random — powered by a cryptographic commit-reveal scheme.',
    detail: (
      <>
        <strong>What makes us different?</strong>
        <br />
        No hidden algorithms. No server-side randomness. Every flip is
        cryptographically verifiable on-chain. The house bankroll is
        transparent and publicly auditable.
      </>
    ),
  },
  {
    icon: '\u{1F511}', // key
    heading: 'Connect Your Wallet',
    description:
      'DuckPools works with Nautilus, the leading Ergo wallet. Connect to start playing with your ERG.',
    detail: (
      <>
        <strong>Getting started:</strong>
        <br />1. Install{' '}
        <a
          href="https://nautiluswallet.com"
          target="_blank"
          rel="noopener noreferrer"
          style={{ color: 'var(--accent-gold, #f0b429)' }}
        >
          Nautilus Wallet
        </a>{' '}
        browser extension
        <br />
        2. Create or import your Ergo wallet
        <br />
        3. Click "Connect Wallet" in the top right
        <br />
        4. Approve the connection in Nautilus
      </>
    ),
  },
  {
    icon: '\u{1FA0}', // coin
    heading: 'How Coinflip Works',
    description:
      'We use a commit-reveal scheme to ensure fairness. Neither you nor the house can influence the outcome.',
    detail: (
      <ol
        className="ow-steps-list"
        style={{ listStyle: 'none', padding: 0 }}
      >
        <li>
          <span className="ow-step-num">1</span>
          <span>
            <strong>Commit:</strong> You pick Heads or Tails and a random
            secret. We compute <code>blake2b256(secret || choice)</code> as your
            commitment.
          </span>
        </li>
        <li>
          <span className="ow-step-num">2</span>
          <span>
            <strong>Bet:</strong> Your commitment is submitted on-chain along
            with your ERG bet amount.
          </span>
        </li>
        <li>
          <span className="ow-step-num">3</span>
          <span>
            <strong>Reveal:</strong> After confirmation, you reveal your
            secret and choice. The oracle result determines the winner.
          </span>
        </li>
        <li>
          <span className="ow-step-num">4</span>
          <span>
            <strong>Payout:</strong> Win and receive <strong>0.97x</strong>{' '}
            your bet (3% house edge). Lose and the house takes it.
          </span>
        </li>
      </ol>
    ),
  },
  {
    icon: '\u{1F680}', // rocket
    heading: 'Ready to Flip!',
    description:
      'You are all set. Pick your side, set your bet, and let the blockchain decide your fate. Good luck!',
    detail: (
      <>
        <strong>Tips:</strong>
        <br />
        \u2022 Start small to get familiar with the flow
        <br />
        \u2022 Check your bet history and stats anytime
        <br />
        \u2022 Earn comp points with every bet to unlock tier benefits
        <br />
        \u2022 Only bet what you can afford to lose
      </>
    ),
  },
];

// ─── Component ─────────────────────────────────────────────────────

export default function OnboardingWizard({
  isOpen: externalOpen,
  onComplete,
  onClose,
  manuallyTriggered,
}: OnboardingWizardProps) {
  const { connect } = useWallet();

  const [visible, setVisible] = useState(() => {
    if (externalOpen !== undefined) return externalOpen;
    if (manuallyTriggered) return true;
    return !hasCompletedOnboarding();
  });

  const [currentStep, setCurrentStep] = useState(0);
  const totalSteps = STEPS.length;

  // Listen for external trigger events
  useEffect(() => {
    const handler = () => setVisible(true);
    window.addEventListener(ONBOARDING_EVENT, handler);
    return () => window.removeEventListener(ONBOARDING_EVENT, handler);
  }, []);

  // Sync with external isOpen
  useEffect(() => {
    if (externalOpen !== undefined) setVisible(externalOpen);
  }, [externalOpen]);

  const handleClose = () => {
    setVisible(false);
    markOnboardingComplete();
    onClose?.();
  };

  const handleComplete = () => {
    setVisible(false);
    markOnboardingComplete();
    onComplete?.();
  };

  const handleBack = () => {
    setCurrentStep((s) => Math.max(0, s - 1));
  };

  const handleNext = () => {
    if (currentStep < totalSteps - 1) {
      setCurrentStep((s) => s + 1);
    } else {
      handleComplete();
    }
  };

  if (!visible) return null;

  const step = STEPS[currentStep];
  const isLastStep = currentStep === totalSteps - 1;
  const isFirstStep = currentStep === 0;

  return (
    <div className="ow-overlay">
      <div className="ow-modal">
        {/* ── Close ─────────────────────────────────────────────────── */}
        <button className="ow-close-btn" onClick={handleClose}>
          Skip
        </button>

        {/* ── Step Indicator ────────────────────────────────────────── */}
        <div className="ow-steps">
          {Array.from({ length: totalSteps }).map((_, i) => (
            <div
              key={i}
              className={`ow-step-dot${
                i === currentStep
                  ? ' ow-step-dot--active'
                  : i < currentStep
                  ? ' ow-step-dot--done'
                  : ''
              }`}
            />
          ))}
        </div>

        {/* ── Content ──────────────────────────────────────────────── */}
        <div className="ow-content">
          <div className="ow-icon">{step.icon}</div>
          <h2 className="ow-heading">{step.heading}</h2>
          <p className="ow-description">{step.description}</p>
          {step.detail && <div className="ow-detail">{step.detail}</div>}
        </div>

        {/* ── Navigation ───────────────────────────────────────────── */}
        <div className="ow-nav">
          <div>
            {!isFirstStep && (
              <button className="ow-nav-btn ow-nav-btn--back" onClick={handleBack}>
                Back
              </button>
            )}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            {!isLastStep && (
              <button className="ow-skip" onClick={handleClose}>
                Skip tour
              </button>
            )}
            <button
              className={`ow-nav-btn ${
                isLastStep ? 'ow-nav-btn--finish' : 'ow-nav-btn--next'
              }`}
              onClick={isLastStep && isFirstStep ? connect : handleNext}
            >
              {isLastStep ? "Let's Go!" : 'Next'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
