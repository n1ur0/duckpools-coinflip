import React from 'react';
import './Input.css';

/** Props for the reusable Input component. */
export interface InputProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'size'> {
  /** Label text displayed above the input. */
  label?: string;
  /** Error message displayed below the input. Triggers error styling when set. */
  error?: string;
  /** Icon element placed inside the input on the left. */
  icon?: React.ReactNode;
  /** Suffix text (e.g. "ERG") displayed after the input. */
  suffix?: string;
  /** Uses body font instead of monospace. Useful for text inputs. */
  textMode?: boolean;
}

/**
 * Reusable Input component with label, error state, icon prefix, and suffix support.
 * Matches the existing input patterns from BetForm.
 *
 * @example
 * ```tsx
 * <Input label="Bet Amount" placeholder="0.0" suffix="ERG" error="Insufficient balance" />
 * <Input label="Memo" placeholder="Optional note" textMode />
 * ```
 */
const Input = React.forwardRef<HTMLInputElement, InputProps>(({
  label,
  error,
  icon,
  suffix,
  textMode = false,
  disabled,
  className = '',
  id,
  ...rest
}, ref) => {
  const inputId = id || (label ? `ui-input-${label.replace(/\s+/g, '-').toLowerCase()}` : undefined);
  const hasError = !!error;
  const hasIcon = !!icon;
  const hasSuffix = !!suffix;

  return (
    <div className="ui-input-group">
      {label && (
        <label className="ui-input__label" htmlFor={inputId}>
          {label}
        </label>
      )}
      <div className={[
        'ui-input__row',
        hasIcon && 'ui-input__row--has-icon-start',
      ].filter(Boolean).join(' ')}>
        {hasIcon && <span className="ui-input__icon-start">{icon}</span>}
        <input
          ref={ref}
          id={inputId}
          className={[
            'ui-input',
            hasError && 'ui-input--error',
            textMode && 'ui-input--text',
            className,
          ].filter(Boolean).join(' ')}
          disabled={disabled}
          aria-invalid={hasError}
          aria-describedby={hasError ? `${inputId}-error` : undefined}
          {...rest}
        />
        {hasSuffix && <span className="ui-input__suffix">{suffix}</span>}
      </div>
      {hasError && (
        <span className="ui-input__error" id={`${inputId}-error`} role="alert">
          {error}
        </span>
      )}
    </div>
  );
});

Input.displayName = 'Input';

export default Input;
