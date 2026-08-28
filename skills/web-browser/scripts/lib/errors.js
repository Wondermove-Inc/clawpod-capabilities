/**
 * Error handling utilities for web browser skill.
 *
 * Provides retry logic with exponential backoff and
 * categorized error types for browser automation.
 */

/**
 * Custom error for browser automation failures.
 * @param {string} message - Error description
 * @param {string} type - Error category (navigation|element|timeout|action)
 * @param {object} [context] - Additional context (url, ref, etc.)
 */
export class BrowserError extends Error {
  constructor(message, type = 'unknown', context = {}) {
    super(message);
    this.name = 'BrowserError';
    this.type = type;
    this.context = context;
  }
}

/**
 * Retry a function with exponential backoff.
 *
 * @param {Function} fn - Async function to retry
 * @param {object} [options] - Retry options
 * @param {number} [options.maxRetries=3] - Maximum retry attempts
 * @param {number} [options.baseDelay=1000] - Base delay in ms (doubles each retry)
 * @param {Function} [options.onRetry] - Callback before each retry (receives error, attempt)
 * @returns {Promise<*>} Result of the function
 * @throws {BrowserError} After all retries exhausted
 */
export async function withRetry(fn, options = {}) {
  const { maxRetries = 3, baseDelay = 1000, onRetry } = options;

  let lastError;
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await fn(attempt);
    } catch (err) {
      lastError = err;
      if (attempt < maxRetries) {
        const delay = baseDelay * Math.pow(2, attempt);
        if (onRetry) await onRetry(err, attempt + 1);
        await sleep(delay);
      }
    }
  }

  throw lastError instanceof BrowserError
    ? lastError
    : new BrowserError(
        `Failed after ${maxRetries + 1} attempts: ${lastError.message}`,
        'retry_exhausted',
        { originalError: lastError.message }
      );
}

/**
 * Sleep for specified milliseconds.
 * @param {number} ms - Milliseconds to sleep
 * @returns {Promise<void>}
 */
export function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}
