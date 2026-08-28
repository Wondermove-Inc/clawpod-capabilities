/**
 * Workflow Engine — Complex multi-step browser operations
 *
 * Provides pre-built workflows for common tasks like login,
 * form filling, and data extraction. Each workflow uses the
 * snapshot → action → verify pattern.
 */

import * as browser from './browser.js';
import * as verifier from './verify.js';
import { BrowserError, sleep } from './errors.js';

/**
 * Login workflow.
 * Navigates to URL, finds username/password fields, fills them, submits.
 *
 * @param {string} url - Login page URL
 * @param {string} username - Username/email
 * @param {string} password - Password
 * @param {object} [options] - Login options
 * @param {string} [options.usernameRef] - Explicit ref for username field
 * @param {string} [options.passwordRef] - Explicit ref for password field
 * @param {string} [options.submitRef] - Explicit ref for submit button
 * @param {string} [options.successText] - Text expected after login
 * @returns {Promise<{success: boolean, message: string}>}
 */
export async function login(url, username, password, options = {}) {
  try {
    // 1. Navigate
    await browser.navigate(url);
    await sleep(2000); // Wait for page render

    // 2. Snapshot to find form elements
    const snap = await browser.snapshot({ force: true });

    // 3. Find refs from snapshot (or use provided)
    const usernameRef = options.usernameRef;
    const passwordRef = options.passwordRef;
    const submitRef = options.submitRef;

    if (!usernameRef || !passwordRef) {
      return {
        success: false,
        message: 'Could not auto-detect login fields. Provide usernameRef and passwordRef from snapshot.',
        snapshot: snap,
      };
    }

    // 4. Fill credentials
    await browser.type(usernameRef, username);
    await sleep(500);
    await browser.type(passwordRef, password);
    await sleep(500);

    // 5. Submit
    if (submitRef) {
      await browser.click(submitRef);
    } else {
      await browser.pressKey('Enter');
    }

    // 6. Wait for navigation
    await sleep(3000);

    // 7. Verify
    if (options.successText) {
      const found = await verifier.verifyText(options.successText);
      return {
        success: found,
        message: found ? 'Login successful' : `Login may have failed — "${options.successText}" not found`,
      };
    }

    return { success: true, message: 'Login submitted (no success text verification)' };
  } catch (err) {
    return {
      success: false,
      message: `Login failed: ${err.message}`,
    };
  }
}

/**
 * Search workflow.
 * Finds search input, types query, submits, waits for results.
 *
 * @param {string} searchRef - Ref for search input field
 * @param {string} query - Search query
 * @param {object} [options] - Search options
 * @param {string} [options.submitRef] - Ref for search button (default: press Enter)
 * @param {number} [options.waitTime=3] - Seconds to wait for results
 * @returns {Promise<{success: boolean, snapshot: string}>}
 */
export async function search(searchRef, query, options = {}) {
  try {
    await browser.type(searchRef, query, {
      submit: !options.submitRef,
    });

    if (options.submitRef) {
      await sleep(500);
      await browser.click(options.submitRef);
    }

    await sleep((options.waitTime || 3) * 1000);
    const snap = await browser.snapshot({ force: true });

    return { success: true, snapshot: snap };
  } catch (err) {
    return { success: false, message: `Search failed: ${err.message}` };
  }
}

/**
 * Extract text content from the current page.
 * Uses snapshot to get all visible text.
 *
 * @returns {Promise<string>} Page text content
 */
export async function extractPageText() {
  return browser.snapshot({ force: true });
}

/**
 * Navigate and extract — go to URL and return page content.
 *
 * @param {string} url - Target URL
 * @param {object} [options] - Options
 * @param {string} [options.waitForText] - Wait for text before extracting
 * @param {number} [options.waitTime=2] - Seconds to wait after navigation
 * @returns {Promise<{url: string, content: string}>}
 */
export async function navigateAndExtract(url, options = {}) {
  await browser.navigate(url);

  if (options.waitForText) {
    await browser.waitFor({ text: options.waitForText });
  } else {
    await sleep((options.waitTime || 2) * 1000);
  }

  const content = await browser.snapshot({ force: true });
  return { url, content };
}
