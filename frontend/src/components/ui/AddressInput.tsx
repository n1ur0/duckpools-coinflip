import React, { useState, useCallback } from 'react';
import './AddressInput.css';

/** Props for the AddressInput component. */
export interface AddressInputProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'size'> {
  /** Label text displayed above the input. */
  label?: string;
  /** Error message displayed below the input. Triggers error styling when set. */
  error?: string;
  /** Placeholder text when input is empty. */
  placeholder?: string;
  /** Whether to truncate the address display (show first 6 and last 4 chars). */
  truncate?: boolean;
  /** Maximum length for ergo addresses (typically 51 chars). */
  maxLength?: number;
  /** Validation function for the address. */
  validator?: (address: string) => boolean;
  /** Called when the address changes. */
  onAddressChange?: (address: string, isValid: boolean) => void;
}

/**
 * AddressInput component specialized for Ergo addresses with truncation and validation.
 * Supports displaying full addresses or truncated format (first 6...last 4 characters).
 *
 * @example
 * ```tsx
 * <AddressInput
 *   label="Recipient Address"
 *   placeholder="Enter Ergo address..."
 *   truncate={true}
 *   onAddressChange={(addr, isValid) => console.log(addr, isValid)}
 * />
 * ```
 */
const AddressInput = React.forwardRef<HTMLInputElement, AddressInputProps>(({
  label,
  error,
  placeholder = 'Enter Ergo address...',
  truncate = false,
  maxLength = 51,
  validator,
  onAddressChange,
  disabled = false,
  className = '',
  id,
  value: controlledValue,
  onChange,
  onBlur,
  ...rest
}, ref) => {
  const [internalValue, setInternalValue] = useState('');
  const [isFocused, setIsFocused] = useState(false);
  
  // Determine if we're using controlled or uncontrolled input
  const value = controlledValue !== undefined ? controlledValue : internalValue;
  
  const inputId = id || (label ? `ui-address-input-${label.replace(/\s+/g, '-').toLowerCase()}` : undefined);
  const hasError = !!error;
  
  // Validate address if validator is provided
  const isValid = validator ? validator(value) : true;
  
  // Truncate address for display if needed (but only when not focused)
  const displayValue = truncate && !isFocused && value ? 
    `${value.slice(0, 6)}...${value.slice(-4)}` : 
    value;

  const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = e.target.value;
    
    if (controlledValue === undefined) {
      setInternalValue(newValue);
    }
    
    if (onChange) {
      onChange(e);
    }
    
    if (onAddressChange) {
      const valid = validator ? validator(newValue) : true;
      onAddressChange(newValue, valid);
    }
  }, [controlledValue, onChange, onAddressChange, validator]);

  const handleFocus = useCallback((e: React.FocusEvent<HTMLInputElement>) => {
    setIsFocused(true);
    if (rest.onFocus) {
      rest.onFocus(e);
    }
  }, [rest.onFocus]);

  const handleBlur = useCallback((e: React.FocusEvent<HTMLInputElement>) => {
    setIsFocused(false);
    if (onBlur) {
      onBlur(e);
    }
  }, [onBlur]);

  return (
    <div className="ui-address-input-group">
      {label && (
        <label className="ui-address-input__label" htmlFor={inputId}>
          {label}
        </label>
      )}
      
      <div className="ui-address-input__wrapper">
        <input
          ref={ref}
          id={inputId}
          className={[
            'ui-address-input',
            hasError && 'ui-address-input--error',
            !isValid && value && 'ui-address-input--invalid',
            className,
          ].filter(Boolean).join(' ')}
          type="text"
          placeholder={placeholder}
          maxLength={maxLength}
          value={displayValue}
          onChange={handleChange}
          onFocus={handleFocus}
          onBlur={handleBlur}
          disabled={disabled}
          aria-invalid={hasError || (!isValid && value)}
          aria-describedby={hasError ? `${inputId}-error` : undefined}
          {...rest}
        />
        
        {truncate && value && (
          <button
            type="button"
            className="ui-address-input__toggle"
            onClick={() => setIsFocused(!isFocused)}
            title={isFocused ? 'Show truncated' : 'Show full address'}
            disabled={disabled}
          >
            <span className="ui-address-input__toggle-icon">
              {isFocused ? '👁️‍🗨️' : '👁️'}
            </span>
          </button>
        )}
      </div>
      
      {hasError && (
        <span className="ui-address-input__error" id={`${inputId}-error`} role="alert">
          {error}
        </span>
      )}
      
      {value && !hasError && !isValid && (
        <span className="ui-address-input__error" id={`${inputId}-error`} role="alert">
          Invalid Ergo address format
        </span>
      )}
    </div>
  );
});

AddressInput.displayName = 'AddressInput';

export default AddressInput;