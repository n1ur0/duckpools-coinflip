import React from 'react';
import './Input.css';

export interface InputProps {
  /** Input label */
  label?: string;
  /** Error message */
  error?: string;
  /** Disabled state */
  disabled?: boolean;
  /** Icon prefix */
  icon?: React.ReactNode;
  /** Input type */
  type?: 'text' | 'password' | 'email' | 'number' | 'tel';
  /** Placeholder text */
  placeholder?: string;
  /** Input value */
  value?: string | number;
  /** Change handler */
  onChange?: (e: React.ChangeEvent<HTMLInputElement>) => void;
  /** Focus handler */
  onFocus?: (e: React.FocusEvent<HTMLInputElement>) => void;
  /** Blur handler */
  onBlur?: (e: React.FocusEvent<HTMLInputElement>) => void;
  /** Input mode for mobile keyboards */
  inputMode?: 'text' | 'numeric' | 'decimal' | 'tel' | 'search' | 'email' | 'url' | 'none';
  /** Additional className */
  className?: string;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(({
  label,
  error,
  disabled = false,
  icon,
  type = 'text',
  placeholder,
  value,
  onChange,
  onFocus,
  onBlur,
  inputMode,
  className = '',
}, ref) => {
  const baseClasses = 'ui-input';
  const errorClass = error ? 'ui-input--error' : '';
  const disabledClass = disabled ? 'ui-input--disabled' : '';
  const iconClass = icon ? 'ui-input--with-icon' : '';
  const numberClass = type === 'number' ? 'ui-input--number' : '';

  const classes = [
    baseClasses,
    errorClass,
    disabledClass,
    iconClass,
    numberClass,
    className,
  ].filter(Boolean).join(' ');

  return (
    <div className="ui-input__container">
      {label && (
        <label className="ui-input__label">
          {label}
        </label>
      )}
      <div className="ui-input__wrapper">
        <input
          ref={ref}
          type={type}
          inputMode={inputMode}
          placeholder={placeholder}
          value={value}
          onChange={onChange}
          onFocus={onFocus}
          onBlur={onBlur}
          disabled={disabled}
          className={classes}
          aria-label={label}
          aria-describedby={error ? 'input-error' : undefined}
          aria-invalid={!!error}
        />
        {icon && (
          <div className="ui-input__icon">
            {icon}
          </div>
        )}
      </div>
      {error && (
        <div id="input-error" className="ui-input__error">
          {error}
        </div>
      )}
    </div>
  );
});

Input.displayName = 'Input';

export default Input;