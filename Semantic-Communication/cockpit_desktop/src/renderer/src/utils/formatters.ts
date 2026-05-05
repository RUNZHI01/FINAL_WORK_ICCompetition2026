/**
 * Format utilities for displaying data
 */

import { T } from '../theme/tokens'

/**
 * Format number with specified precision
 */
export function formatNumber(value: number, precision = 2): string {
  if (Number.isNaN(value)) return '—';
  return value.toFixed(precision);
}

/**
 * Format bytes to human readable size
 */
export function formatBytes(bytes: number, decimals = 2): string {
  if (bytes === 0) return '0 B';

  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));

  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
}

/**
 * Format milliseconds to human readable time
 */
export function formatMs(ms: number, showUnit = true): string {
  if (Number.isNaN(ms) || ms === null || ms === undefined) return '—';

  if (ms < 1000) {
    return `${ms.toFixed(2)}${showUnit ? ' ms' : ''}`;
  }

  const seconds = ms / 1000;
  if (seconds < 60) {
    return `${seconds.toFixed(2)}${showUnit ? ' s' : ''}`;
  }

  const minutes = seconds / 60;
  if (minutes < 60) {
    return `${minutes.toFixed(2)}${showUnit ? ' min' : ''}`;
  }

  const hours = minutes / 60;
  return `${hours.toFixed(2)}${showUnit ? ' hr' : ''}`;
}

/**
 * Format percentage
 */
export function formatPercent(value: number, precision = 1): string {
  if (Number.isNaN(value)) return '—';
  return `${value.toFixed(precision)}%`;
}

/**
 * Format timestamp to relative time
 */
export function formatRelativeTime(timestamp: number | Date): string {
  const now = Date.now();
  const diff = now - (typeof timestamp === 'number' ? timestamp : timestamp.getTime());

  const seconds = Math.floor(diff / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);

  if (seconds < 60) return '刚刚';
  if (minutes < 60) return `${minutes} 分钟前`;
  if (hours < 24) return `${hours} 小时前`;
  if (days < 7) return `${days} 天前`;

  const date = new Date(timestamp);
  return date.toLocaleDateString('zh-CN');
}

/**
 * Format date to locale string
 */
export function formatDate(date: number | Date, format: 'full' | 'long' | 'short' = 'long'): string {
  const d = typeof date === 'number' ? new Date(date) : date;

  switch (format) {
    case 'full':
      return d.toLocaleString('zh-CN', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      });
    case 'short':
      return d.toLocaleDateString('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      });
    default:
      return d.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      });
  }
}

/**
 * Format frequency to human readable
 */
export function formatFrequency(hz: number): string {
  if (hz < 1000) return `${hz.toFixed(2)} Hz`;
  if (hz < 1000000) return `${(hz / 1000).toFixed(2)} kHz`;
  return `${(hz / 1000000).toFixed(2)} MHz`;
}

/**
 * Format coordinate (lat/lng)
 */
export function formatCoordinate(lat: number, lng: number, precision = 4): string {
  return `${lat.toFixed(precision)}, ${lng.toFixed(precision)}`;
}

/**
 * Truncate text with ellipsis
 */
export function truncate(text: string, maxLength = 50): string {
  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength - 3)}...`;
}

/**
 * Pluralize word based on count
 */
export function pluralize(word: string, count: number): string {
  if (count === 1) return word;
  return `${word}s`;
}

/**
 * Format count with pluralization
 */
export function formatCount(count: number, singular: string, plural?: string): string {
  const word = count === 1 ? singular : (plural || `${singular}s`);
  return `${count} ${word}`;
}

/**
 * Format duration in HH:MM:SS
 */
export function formatDuration(seconds: number): string {
  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);

  const pad = (n: number) => n.toString().padStart(2, '0');

  if (hrs > 0) {
    return `${pad(hrs)}:${pad(mins)}:${pad(secs)}`;
  }
  return `${pad(mins)}:${pad(secs)}`;
}

/**
 * Format currency
 */
export function formatCurrency(amount: number, currency = 'CNY'): string {
  return new Intl.NumberFormat('zh-CN', {
    style: 'currency',
    currency,
  }).format(amount);
}

/**
 * Safe JSON parse with fallback
 */
export function safeJsonParse<T>(json: string, fallback: T): T {
  try {
    return JSON.parse(json);
  } catch {
    return fallback;
  }
}

/**
 * Get color based on value (heat map style)
 */
export function getHeatMapColor(value: number, min = 0, max = 100): string {
  const ratio = (value - min) / (max - min);

  if (ratio < 0.33) {
    return T.toneSuccess;
  } else if (ratio < 0.66) {
    return T.toneWarning;
  } else {
    return T.toneError;
  }
}

/**
 * Check if value is in range
 */
export function inRange(value: number, min: number, max: number): boolean {
  return value >= min && value <= max;
}

/**
 * Clamp value between min and max
 */
export function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

/**
 * Generate random ID
 */
export function randomId(prefix = 'id'): string {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

/**
 * Debounce function
 */
export function debounce<T extends (...args: any[]) => any>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeout: NodeJS.Timeout | null = null;

  return (...args: Parameters<T>) => {
    if (timeout) clearTimeout(timeout);
    timeout = setTimeout(() => func(...args), wait);
  };
}

/**
 * Throttle function
 */
export function throttle<T extends (...args: any[]) => any>(
  func: T,
  limit: number
): (...args: Parameters<T>) => void {
  let inThrottle: boolean;

  return (...args: Parameters<T>) => {
    if (!inThrottle) {
      func(...args);
      inThrottle = true;
      setTimeout(() => (inThrottle = false), limit);
    }
  };
}

/**
 * Sleep utility
 */
export function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Retry function with exponential backoff
 */
export async function retry<T>(
  fn: () => Promise<T>,
  maxRetries = 3,
  delay = 1000
): Promise<T> {
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await fn();
    } catch (error) {
      if (i === maxRetries - 1) throw error;
      await sleep(delay * Math.pow(2, i));
    }
  }
  throw new Error('Max retries reached');
}
