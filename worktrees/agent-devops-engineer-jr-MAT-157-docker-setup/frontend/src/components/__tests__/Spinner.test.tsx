import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import Spinner from '../ui/Spinner';

describe('Spinner Component', () => {
  it('renders without crashing', () => {
    const { container } = render(<Spinner />);
    expect(container.querySelector('.ui-spinner')).toBeInTheDocument();
  });

  it('renders with default variant and size', () => {
    const { container } = render(<Spinner />);
    const spinner = container.querySelector('.ui-spinner');
    expect(spinner).toHaveClass('ui-spinner--default');
    expect(spinner).toHaveClass('ui-spinner--md');
  });

  it('renders with specified variant', () => {
    const { container } = render(<Spinner variant="primary" />);
    const spinner = container.querySelector('.ui-spinner');
    expect(spinner).toHaveClass('ui-spinner--primary');
  });

  it('renders with specified size', () => {
    const { container } = render(<Spinner size="lg" />);
    const spinner = container.querySelector('.ui-spinner');
    expect(spinner).toHaveClass('ui-spinner--lg');
  });

  it('renders with custom className', () => {
    const { container } = render(<Spinner className="custom-class" />);
    const spinner = container.querySelector('.ui-spinner');
    expect(spinner).toHaveClass('custom-class');
  });

  it('includes accessibility attributes', () => {
    const { container } = render(<Spinner label="Loading data..." />);
    const spinner = container.querySelector('.ui-spinner');
    expect(spinner).toHaveAttribute('role', 'status');
    expect(spinner).toHaveAttribute('aria-label', 'Loading data...');
    expect(spinner).toHaveAttribute('aria-live', 'polite');
  });

  it('has screen reader only text', () => {
    const { container } = render(<Spinner label="Processing..." />);
    const srText = container.querySelector('.ui-spinner__sr-only');
    expect(srText).toHaveTextContent('Processing...');
  });

  it('renders all variant classes correctly', () => {
    const variants: Array<'default' | 'primary' | 'success' | 'warning' | 'error'> = [
      'default',
      'primary',
      'success',
      'warning',
      'error',
    ];

    variants.forEach((variant) => {
      const { container, unmount } = render(<Spinner variant={variant} />);
      const spinner = container.querySelector('.ui-spinner');
      expect(spinner).toHaveClass(`ui-spinner--${variant}`);
      unmount();
    });
  });

  it('renders all size classes correctly', () => {
    const sizes: Array<'sm' | 'md' | 'lg'> = ['sm', 'md', 'lg'];

    sizes.forEach((size) => {
      const { container, unmount } = render(<Spinner size={size} />);
      const spinner = container.querySelector('.ui-spinner');
      expect(spinner).toHaveClass(`ui-spinner--${size}`);
      unmount();
    });
  });
});
