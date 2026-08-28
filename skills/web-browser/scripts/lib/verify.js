/**
 * Verification Engine — Post-action state validation
 *
 * Verifies browser state after actions to ensure correctness.
 * Uses snapshot (accessibility tree) as primary verification,
 * screenshot as fallback for visual-only state.
 */

import { snapshot, screenshot } from './browser.js';
import { BrowserError } from './errors.js';

/**
 * Verify that current page URL matches expected pattern.
 *
 * @param {string} expectedUrl - Full URL or partial pattern to match
 * @returns {Promise<boolean>} Whether URL matches
 */
export async function verifyNavigation(expectedUrl) {
  const snap = await snapshot({ force: true });
  // Snapshot includes page URL in the output
  const urlMatch = snap.toLowerCase().includes(expectedUrl.toLowerCase());
  if (!urlMatch) {
    console.warn(`[verify] Expected URL containing "${expectedUrl}" not found in snapshot`);
  }
  return urlMatch;
}

/**
 * Verify that specific text exists on the page.
 *
 * @param {string} text - Text to search for
 * @returns {Promise<boolean>} Whether text was found
 */
export async function verifyText(text) {
  if (!text) throw new BrowserError('text is required for verifyText', 'verify');
  const snap = await snapshot({ force: true });
  return snap.includes(text);
}

/**
 * Verify that specific text does NOT exist on the page.
 * Useful for confirming error messages disappeared.
 *
 * @param {string} text - Text that should be absent
 * @returns {Promise<boolean>} Whether text is absent
 */
export async function verifyTextGone(text) {
  if (!text) throw new BrowserError('text is required for verifyTextGone', 'verify');
  const snap = await snapshot({ force: true });
  return !snap.includes(text);
}

/**
 * Detect common error indicators on the page.
 * Checks for error messages, alert dialogs, HTTP error pages.
 *
 * @returns {Promise<{hasError: boolean, errors: string[]}>} Error detection result
 */
export async function detectErrors() {
  const snap = await snapshot({ force: true });
  const errors = [];

  const errorPatterns = [
    /error/i,
    /failed/i,
    /not found/i,
    /404/,
    /500/,
    /403/,
    /unauthorized/i,
    /forbidden/i,
    /에러/,
    /실패/,
    /오류/,
  ];

  const lines = snap.split('\n');
  for (const line of lines) {
    for (const pattern of errorPatterns) {
      if (pattern.test(line) && line.trim().length < 200) {
        errors.push(line.trim());
        break; // One match per line is enough
      }
    }
  }

  return {
    hasError: errors.length > 0,
    errors: [...new Set(errors)].slice(0, 10), // Dedupe, limit to 10
  };
}

/**
 * Take a verification screenshot and save it.
 * Used when snapshot-based verification is insufficient.
 *
 * @param {string} [label='verify'] - Label for the screenshot file
 * @returns {Promise<string>} Screenshot file path
 */
export async function captureVerification(label = 'verify') {
  const timestamp = Date.now();
  const filename = `/tmp/browser-${label}-${timestamp}.png`;
  await screenshot({ filename });
  return filename;
}

/**
 * Combined verification: check text + detect errors.
 * Returns a structured verification report.
 *
 * @param {object} checks - What to verify
 * @param {string[]} [checks.textPresent] - Texts that should exist
 * @param {string[]} [checks.textAbsent] - Texts that should be absent
 * @param {boolean} [checks.noErrors=true] - Whether to check for errors
 * @returns {Promise<{passed: boolean, details: object}>} Verification report
 */
export async function verify(checks = {}) {
  const { textPresent = [], textAbsent = [], noErrors = true } = checks;
  const details = { textPresent: {}, textAbsent: {}, errors: null };
  let allPassed = true;

  // Check texts that should be present
  for (const text of textPresent) {
    const found = await verifyText(text);
    details.textPresent[text] = found;
    if (!found) allPassed = false;
  }

  // Check texts that should be absent
  for (const text of textAbsent) {
    const gone = await verifyTextGone(text);
    details.textAbsent[text] = gone;
    if (!gone) allPassed = false;
  }

  // Check for errors
  if (noErrors) {
    const errorCheck = await detectErrors();
    details.errors = errorCheck;
    if (errorCheck.hasError) allPassed = false;
  }

  return { passed: allPassed, details };
}
