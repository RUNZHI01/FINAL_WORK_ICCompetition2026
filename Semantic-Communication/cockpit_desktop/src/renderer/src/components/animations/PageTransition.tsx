import { motion } from 'framer-motion';
import { ReactNode } from 'react';

interface PageTransitionProps {
  children: ReactNode;
  className?: string;
}

/**
 * Page transition wrapper with smooth fade and slide effect
 * Use this to wrap page content for smooth transitions
 */
export function PageTransition({ children, className = '' }: PageTransitionProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      transition={{
        duration: 0.3,
        ease: [0.25, 0.8, 0.25, 1],
      }}
      className={className}
      style={{
        // Respect prefers-reduced-motion
        animation: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'none' : undefined,
      }}
    >
      {children}
    </motion.div>
  );
}

/**
 * Staggered list animation for items appearing one by one
 */
export function StaggeredList({
  children,
  className = '',
  staggerDelay = 0.05,
}: {
  children: ReactNode;
  className?: string;
  staggerDelay?: number;
}) {
  return (
    <motion.div
      initial="hidden"
      animate="visible"
      variants={{
        visible: {
          transition: {
            staggerChildren: staggerDelay,
          },
        },
      }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

/**
 * Animated list item
 */
export function AnimatedListItem({
  children,
  className = '',
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <motion.div
      variants={{
        hidden: { opacity: 0, y: 10 },
        visible: { opacity: 1, y: 0 },
      }}
      transition={{ duration: 0.2 }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

/**
 * Scale in animation for modal/panel
 */
export function ScaleIn({
  children,
  className = '',
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      transition={{
        duration: 0.2,
        ease: [0.25, 0.8, 0.25, 1],
      }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

/**
 * Slide in from specific direction
 */
export function SlideFrom({
  children,
  direction = 'left',
  className = '',
}: {
  children: ReactNode;
  direction?: 'left' | 'right' | 'top' | 'bottom';
  className?: string;
}) {
  const variants = {
    left: { x: -50, opacity: 0 },
    right: { x: 50, opacity: 0 },
    top: { y: -50, opacity: 0 },
    bottom: { y: 50, opacity: 0 },
  };

  return (
    <motion.div
      initial={variants[direction]}
      animate={{ x: 0, y: 0, opacity: 1 }}
      transition={{
        duration: 0.3,
        ease: [0.25, 0.8, 0.25, 1],
      }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

export default PageTransition;
