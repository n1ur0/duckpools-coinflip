import React, { useId } from 'react';
import './Toggle.css';

/** Props for the reusable Toggle (switch) component. */
export interface ToggleProps {
  /** Whether the toggle is on. */
  checked?: boolean;
  /** Called when the toggle value changes. */
  onChange?: (checked: boolean) => void;
  /** Disables the toggle. */
  disabled?: boolean;
  /** Label text displayed next to the toggle. */
  label?: string;
  /** Label for the "on" side. */
  labelOn?: string;
  /** Label for the "off" side. */
  labelOff?: string;
  /** Additional class name. */
  className?: string;
}

/**
 * CSS-only toggle switch with smooth animation and optional labels on both sides.
 * Uses hidden checkbox input for accessibility.
 *
 * @example
 * ```tsx
 * <Toggle checked={darkMode} onChange={setDarkMode} label="Dark Mode" />
 * <Toggle checked={sound} onChange={setSound} labelOn="On" labelOff="Off" />
 * ```
 */
const Toggle: React.FC<ToggleProps> = ({
  checked = false,
  onChange,
  disabled = false,
  label,
  labelOn,
  labelOff,
  className = '',
}) => {
  const inputId = useId();

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onChange?.(e.target.checked);
  };

  const groupClasses = [
    'ui-toggle-group',
    disabled && 'ui-toggle-group--disabled',
    className,
  ].filter(Boolean).join(' ');

  return (
    <label className={groupClasses}>
      {labelOff && !label && (
        <span className="ui-toggle__label ui-toggle__label--off">{labelOff}</span>
      )}
      <span className={`ui-toggle ${disabled ? 'ui-toggle--disabled' : ''}`}>
        <input
          id={inputId}
          type="checkbox"
          checked={checked}
          onChange={handleChange}
          disabled={disabled}
          role="switch"
          aria-checked={checked}
        />
        <span className="ui-toggle__track" />
        <span className="ui-toggle__thumb" />
      </span>
      {(label || labelOn) && (
        <span className={`ui-toggle__label ${checked ? 'ui-toggle__label--on' : ''}`}>
          {label || labelOn}
        </span>
      )}
    </label>
  );
};

export default Toggle;
