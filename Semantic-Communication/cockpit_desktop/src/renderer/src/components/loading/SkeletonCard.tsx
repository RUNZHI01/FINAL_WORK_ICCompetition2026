import React from 'react';
import { T } from '../../theme/tokens';

export interface SkeletonCardProps {
  title?: boolean;
  lines?: number;
  height?: number;
  className?: string;
}

/**
 * Skeleton loading card with shimmer effect
 */
export const SkeletonCard: React.FC<SkeletonCardProps> = ({
  title = true,
  lines = 3,
  height = 180,
  className = '',
}) => {
  return (
    <div
      className={className}
      style={{
        background: T.glassBg,
        backdropFilter: 'blur(24px) saturate(190%)',
        WebkitBackdropFilter: 'blur(24px) saturate(190%)',
        borderRadius: T.radiusLg,
        border: `1px solid ${T.glassBorder}`,
        padding: 16,
        height,
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
      }}
    >
      {title && (
        <div
          className="skeleton"
          style={{
            width: '40%',
            height: 16,
            borderRadius: 4,
          }}
        />
      )}
      {Array.from({ length: lines }).map((_, i) => (
        <div
          key={i}
          className="skeleton"
          style={{
            width: i === lines - 1 ? '70%' : '100%',
            height: 12,
            borderRadius: 4,
          }}
        />
      ))}
    </div>
  );
};

export default SkeletonCard;
