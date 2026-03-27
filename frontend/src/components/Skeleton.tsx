import type { CSSProperties } from 'react';
import './Skeleton.css';

// ─── SkeletonLine ──────────────────────────────────────────────────

interface SkeletonLineProps {
  width?: string | number;
  className?: string;
  size?: 'sm' | 'md' | 'lg' | 'xl';
}

export function SkeletonLine({
  width,
  className = '',
  size = 'md',
}: SkeletonLineProps) {
  const style: CSSProperties = width ? { width } : {};
  return (
    <div
      className={`sk-line sk-line--${size} ${className}`}
      style={style}
      role="status"
      aria-hidden="true"
    />
  );
}

// ─── SkeletonCard ──────────────────────────────────────────────────

interface SkeletonCardProps {
  lines?: number;
  hasHeader?: boolean;
  className?: string;
}

export function SkeletonCard({
  lines = 4,
  hasHeader = true,
  className = '',
}: SkeletonCardProps) {
  return (
    <div className={`sk-card ${className}`} role="status" aria-hidden="true">
      {hasHeader && (
        <div className="sk-card__header">
          <div className="sk-card__avatar" />
          <div className="sk-card__title">
            <SkeletonLine size="lg" />
            <SkeletonLine size="sm" />
          </div>
        </div>
      )}
      <div className="sk-card__body">
        {Array.from({ length: lines }).map((_, i) => (
          <SkeletonLine key={i} />
        ))}
      </div>
    </div>
  );
}

// ─── SkeletonTable ─────────────────────────────────────────────────

interface SkeletonTableProps {
  columns?: number;
  rows?: number;
  columnWidths?: number[];
  className?: string;
}

export function SkeletonTable({
  columns = 5,
  rows = 5,
  columnWidths,
  className = '',
}: SkeletonTableProps) {
  const widths = columnWidths || Array(columns).fill(1);

  return (
    <div className={`sk-table ${className}`} role="status" aria-hidden="true">
      {/* Header row */}
      <div
        className="sk-table__header"
        style={{ gridTemplateColumns: widths.map((w) => `${w}fr`).join(' ') }}
      >
        {Array.from({ length: columns }).map((_, i) => (
          <SkeletonLine key={i} size="sm" />
        ))}
      </div>
      {/* Body rows */}
      {Array.from({ length: rows }).map((_, rowIdx) => (
        <div
          key={rowIdx}
          className="sk-table__row"
          style={{ gridTemplateColumns: widths.map((w) => `${w}fr`).join(' ') }}
        >
          {Array.from({ length: columns }).map((_, colIdx) => (
            <SkeletonLine key={colIdx} />
          ))}
        </div>
      ))}
    </div>
  );
}
