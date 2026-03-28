import React, { useState, useEffect } from 'react';
import { Triangle } from 'lucide-react';
import { formatErg } from '../utils/ergo';
import {
  getMultipliersForRows,
  formatMultiplier,
  getRiskLevel,
  calculatePayout,
  getSlotProbabilities,
} from '../utils/plinko';
import './PlinkoGame.css';

interface PlinkoGameProps {
  onBet: (betData: {
    gameType: 'plinko';
    amount: string;
    rows: number;
    targetSlot?: number;
  }) => void;
  disabled?: boolean;
  isLoading?: boolean;
}

const ROWS_OPTIONS = [8, 12, 16] as const;
type RowsOption = typeof ROWS_OPTIONS[number];

export default function PlinkoGame({ onBet, disabled = false, isLoading = false }: PlinkoGameProps) {
  const [betAmount, setBetAmount] = useState<string>('0.01');
  const [selectedRows, setSelectedRows] = useState<RowsOption>(8);
  const [multipliers, setMultipliers] = useState<number[]>([]);
  const [probabilities, setProbabilities] = useState<number[]>([]);

  useEffect(() => {
    // Update multipliers and probabilities when rows change
    try {
      const newMultipliers = getMultipliersForRows(selectedRows);
      const newProbabilities = getSlotProbabilities(selectedRows);
      setMultipliers(newMultipliers);
      setProbabilities(newProbabilities);
    } catch (error) {
      console.error('Error loading Plinko data:', error);
    }
  }, [selectedRows]);

  const handleBet = () => {
    if (disabled || isLoading) return;
    
    const amount = parseFloat(betAmount);
    if (isNaN(amount) || amount <= 0) {
      alert('Please enter a valid bet amount');
      return;
    }
    
    onBet({
      gameType: 'plinko',
      amount: betAmount,
      rows: selectedRows,
    });
  };

  const getSlotWidth = () => {
    return 100 / (selectedRows + 1);
  };

  const getSlotColor = (multiplier: number) => {
    if (multiplier >= 50) return '#ef4444'; // red
    if (multiplier >= 20) return '#f97316'; // orange
    if (multiplier >= 10) return '#eab308'; // yellow
    if (multiplier >= 5) return '#22c55e'; // green
    return '#3b82f6'; // blue
  };

  return (
    <div className="plinko-game">
      <div className="plinko-game__header">
        <div className="plinko-game__title">
          <Triangle size={24} />
          <h2>Plinko</h2>
        </div>
        <div className="plinko-game__risk-badge">
          {getRiskLevel(selectedRows)}
        </div>
      </div>

      <div className="plinko-game__controls">
        <div className="plinko-game__bet-input">
          <label htmlFor="betAmount">Bet Amount (ERG)</label>
          <input
            id="betAmount"
            type="number"
            value={betAmount}
            onChange={(e) => setBetAmount(e.target.value)}
            min="0.000000001"
            step="0.000000001"
            disabled={disabled || isLoading}
            placeholder="0.01"
          />
        </div>

        <div className="plinko-game__rows-selector">
          <label>Rows (Risk Level)</label>
          <div className="plinko-game__rows-options">
            {ROWS_OPTIONS.map((rows) => (
              <button
                key={rows}
                className={`plinko-game__rows-option ${
                  selectedRows === rows ? 'plinko-game__rows-option--active' : ''
                }`}
                onClick={() => setSelectedRows(rows)}
                disabled={disabled || isLoading}
              >
                {rows} rows
              </button>
            ))}
          </div>
        </div>

        <button
          className="plinko-game__bet-button"
          onClick={handleBet}
          disabled={disabled || isLoading}
        >
          {isLoading ? 'Processing...' : `Drop Ball (${formatErg(betAmount)} ERG)`}
        </button>
      </div>

      <div className="plinko-game__board">
        <div className="plinko-game__pegs">
          {/* Render pegs */}
          {Array.from({ length: selectedRows }, (_, row) => (
            <div key={row} className="plinko-game__peg-row">
              {Array.from({ length: row + 1 }, (_, peg) => (
                <div key={peg} className="plinko-game__peg" />
              ))}
            </div>
          ))}
        </div>

        <div className="plinko-game__slots">
          {multipliers.map((multiplier, slot) => (
            <div
              key={slot}
              className="plinko-game__slot"
              style={{
                width: `${getSlotWidth()}%`,
                backgroundColor: getSlotColor(multiplier),
              }}
            >
              <div className="plinko-game__slot-info">
                <div className="plinko-game__slot-number">{slot}</div>
                <div className="plinko-game__slot-multiplier">
                  {formatMultiplier(multiplier)}
                </div>
                <div className="plinko-game__slot-probability">
                  {(probabilities[slot] * 100).toFixed(1)}%
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="plinko-game__info">
        <div className="plinko-game__house-edge">
          House Edge: 3.00%
        </div>
        <div className="plinko-game__formula">
          Multiplier calculated using: A × (1/P)^0.5
        </div>
      </div>
    </div>
  );
}