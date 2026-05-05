import { motion } from 'framer-motion';
import { T } from '../../theme/tokens';

interface ScaleOnHoverProps {
  children: React.ReactNode;
  scale?: number;
  disabled?: boolean;
}

/**
 * Scale animation on hover
 * Use for buttons and interactive cards
 */
export function ScaleOnHover({ children, scale = 1.02, disabled = false }: ScaleOnHoverProps) {
  if (disabled) {
    return <>{children}</>;
  }

  return (
    <motion.div
      whileHover={{ scale }}
      whileTap={{ scale: 0.98 }}
      transition={{
        duration: T.durationFast / 1000,
        ease: [0.22, 1, 0.36, 1] as [number, number, number, number],
      }}
    >
      {children}
    </motion.div>
  );
}
