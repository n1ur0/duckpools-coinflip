import React, { useState, useRef, useEffect } from 'react';
import { Input, InputProps } from './Input';
import { Copy, Check } from 'lucide-react';

/** Props for the AddressInput component */
export interface AddressInputProps extends Omit<InputProps, 'value' | 'onChange'> {
  /** The ergo address value */
  value: string;
  /** Called when the address changes */
  onChange: (value: string) => void;
  /** Number of characters to show before truncation. Default: 8 */
  truncateLength?: number;
  /** Enable copy to clipboard functionality. Default: true */
  enableCopy?: boolean;
  /** Show truncated address by default. Default: true */
  showTruncated?: boolean;
  /** Custom placeholder for the address input */
  placeholder?: string;
}

/**
 * Specialized Input component for Ergo addresses with truncation and copy functionality.
 * 
 * Features:
 * - Truncates long addresses (e.g., "3WyrB3...VfXytDPgxF26")
 * - Shows full address on hover/focus
 * - Copy to clipboard with feedback
 * - Maintains all base Input features (validation, error states, etc.)
 * 
 * @example
 * ```tsx
 * <AddressInput
 *   label="Wallet Address"
 *   value={address}
 *   onChange={setAddress}
 *   error={error}
 *   placeholder="Enter your Ergo address"
 * />
 * ```
 */
const AddressInput: React.FC<AddressInputProps> = ({
  value,
  onChange,
  truncateLength = 8,
  enableCopy = true,
  showTruncated = true,
  placeholder = '3W...',
  className = '',
  ...rest
}) => {
  const [isFocused, setIsFocused] = useState(false);
  const [copied, setCopied] = useState(false);
  const [displayValue, setDisplayValue] = useState(value);
  const inputRef = useRef<HTMLInputElement>(null);

  // Truncate address function
  const truncateAddress = (address: string): string => {
    if (!address || address.length <= truncateLength * 2 + 3) {
      return address;
    }
    const start = address.slice(0, truncateLength);
    const end = address.slice(-truncateLength);
    return `${start}...${end}`;
  };

  // Update display value based on focus and settings
  useEffect(() => {
    if (isFocused || !showTruncated) {
      setDisplayValue(value);
    } else {
      setDisplayValue(truncateAddress(value));
    }
  }, [value, isFocused, showTruncated, truncateLength]);

  // Copy to clipboard handler
  const handleCopy = async () => {
    if (!enableCopy || !value) return;

    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy address:', err);
    }
  };

  // Focus handlers
  const handleFocus = (e: React.FocusEvent<HTMLInputElement>) => {
    setIsFocused(true);
    if (rest.onFocus) {
      rest.onFocus(e);
    }
  };

  const handleBlur = (e: React.FocusEvent<HTMLInputElement>) => {
    setIsFocused(false);
    if (rest.onBlur) {
      rest.onBlur(e);
    }
  };

  // Change handler
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onChange(e.target.value);
  };

  const inputClasses = [
    'ui-address-input',
    enableCopy && value && 'ui-address-input--with-copy',
    className,
  ].filter(Boolean).join(' ');

  return (
    <div className="ui-address-input-group">
      <Input
        ref={inputRef}
        value={displayValue}
        onChange={handleChange}
        onFocus={handleFocus}
        onBlur={handleBlur}
        placeholder={placeholder}
        className={inputClasses}
        {...rest}
      />
      {enableCopy && value && (
        <button
          type="button"
          className={`ui-address-input__copy ${copied ? 'ui-address-input__copy--copied' : ''}`}
          onClick={handleCopy}
          aria-label={copied ? 'Copied to clipboard' : 'Copy address to clipboard'}
          title={copied ? 'Copied!' : 'Copy address'}
        >
          {copied ? (
            <Check size={16} className="ui-address-input__copy-icon" />
          ) : (
            <Copy size={16} className="ui-address-input__copy-icon" />
          )}
        </button>
      )}
      {value && showTruncated && !isFocused && (
        <div className="ui-address-input__tooltip">
          Full address: {value}
        </div>
      )}
    </div>
  );
};

export default AddressInput;