/**
 * Browser Control Core — Hybrid Accessibility Tree + Screenshot
 *
 * Wraps Playwright MCP calls into a clean async API.
 * Uses mcporter CLI under the hood for all browser interactions.
 *
 * Design principles:
 * - Accessibility tree (snapshot) for element identification (precise refs)
 * - Screenshots for visual verification (when needed)
 * - Retry with backoff on transient failures
 * - Stale ref detection → auto re-snapshot
 */

import { execSync } from 'node:child_process';
import { writeFileSync, readFileSync, existsSync } from 'node:fs';
import { BrowserError, withRetry, sleep } from './errors.js';

/** Timeout for mcporter calls (ms) */
const MCPORTER_TIMEOUT = 30_000;

/** Last snapshot cache to avoid redundant calls */
let lastSnapshot = null;
let lastSnapshotTime = 0;
const SNAPSHOT_CACHE_MS = 2000; // 2 second cache

/**
 * Execute mcporter command and return stdout.
 * Throws BrowserError on failure.
 *
 * @param {string} tool - Playwright tool name (e.g., 'browser_navigate')
 * @param {object} [args] - Tool arguments
 * @returns {string} Command output
 */
function mcporter(tool, args = {}) {
  const hasArgs = Object.keys(args).length > 0;
  let cmd;

  if (hasArgs) {
    // Use --args JSON for complex parameters
    const argsJson = JSON.stringify(args);
    cmd = `mcporter call playwright.${tool} --args '${argsJson.replace(/'/g, "'\\''")}'`;
  } else {
    cmd = `mcporter call playwright.${tool}`;
  }

  try {
    const output = execSync(cmd, {
      timeout: MCPORTER_TIMEOUT,
      encoding: 'utf-8',
      cwd: '/workspace', // mcporter reads config from ./config/mcporter.json
      stdio: ['pipe', 'pipe', 'pipe'],
    });
    return output.trim();
  } catch (err) {
    const stderr = err.stderr?.toString() || '';
    const stdout = err.stdout?.toString() || '';
    throw new BrowserError(
      `mcporter ${tool} failed: ${stderr || stdout || err.message}`,
      'mcporter',
      { tool, args }
    );
  }
}

/**
 * Navigate to a URL and wait for page load.
 *
 * @param {string} url - Target URL
 * @returns {Promise<string>} Page title or navigation result
 */
export async function navigate(url) {
  if (!url || typeof url !== 'string') {
    throw new BrowserError('URL is required', 'navigation', { url });
  }

  return withRetry(
    () => {
      lastSnapshot = null; // Invalidate cache on navigation
      return mcporter('browser_navigate', { url });
    },
    {
      maxRetries: 2,
      baseDelay: 2000,
      onRetry: (err, attempt) => {
        console.error(`[browser] Navigate retry ${attempt}: ${err.message}`);
      },
    }
  );
}

/**
 * Capture accessibility snapshot of the current page.
 * Returns structured element tree with refs for precise interaction.
 *
 * Uses a short cache to avoid redundant calls when multiple
 * actions happen on the same page state.
 *
 * @param {object} [options] - Snapshot options
 * @param {boolean} [options.force=false] - Bypass cache
 * @param {string} [options.filename] - Save to file instead of returning
 * @returns {Promise<string>} Accessibility tree as text
 */
export async function snapshot(options = {}) {
  const { force = false, filename } = options;

  // Return cached snapshot if recent enough
  if (!force && lastSnapshot && (Date.now() - lastSnapshotTime) < SNAPSHOT_CACHE_MS) {
    return lastSnapshot;
  }

  const args = {};
  if (filename) args.filename = filename;

  const result = mcporter('browser_snapshot', args);
  lastSnapshot = result;
  lastSnapshotTime = Date.now();
  return result;
}

/**
 * Take a screenshot of the current page.
 *
 * @param {object} [options] - Screenshot options
 * @param {string} [options.filename] - Output file path (default: auto-generated)
 * @param {boolean} [options.fullPage=false] - Capture full scrollable page
 * @param {string} [options.type='png'] - Image format (png|jpeg)
 * @returns {Promise<string>} Screenshot result (file path or base64)
 */
export async function screenshot(options = {}) {
  const { filename, fullPage = false, type = 'png' } = options;
  const args = { type };
  if (filename) args.filename = filename;
  if (fullPage) args.fullPage = true;

  return mcporter('browser_take_screenshot', args);
}

/**
 * Click an element by ref (from snapshot).
 * On stale ref, auto re-snapshots and reports.
 *
 * @param {string} ref - Element reference from snapshot (e.g., 'e15')
 * @param {object} [options] - Click options
 * @param {string} [options.element] - Human-readable element description
 * @param {boolean} [options.doubleClick=false] - Double click
 * @param {string} [options.button='left'] - Mouse button
 * @returns {Promise<string>} Click result
 */
export async function click(ref, options = {}) {
  if (!ref) throw new BrowserError('ref is required for click', 'element');

  const { element, doubleClick = false, button = 'left' } = options;
  const args = { ref };
  if (element) args.element = element;
  if (doubleClick) args.doubleClick = true;
  if (button !== 'left') args.button = button;

  return withRetry(
    async (attempt) => {
      if (attempt > 0) {
        // Stale ref — re-snapshot to get fresh refs
        console.error(`[browser] Click retry ${attempt}: re-capturing snapshot`);
        lastSnapshot = null;
        await snapshot({ force: true });
      }
      const result = mcporter('browser_click', args);
      lastSnapshot = null; // Invalidate after action
      return result;
    },
    { maxRetries: 2, baseDelay: 1000 }
  );
}

/**
 * Type text into an element by ref.
 *
 * @param {string} ref - Element reference from snapshot
 * @param {string} text - Text to type
 * @param {object} [options] - Type options
 * @param {string} [options.element] - Human-readable description
 * @param {boolean} [options.submit=false] - Press Enter after typing
 * @param {boolean} [options.slowly=false] - Type one character at a time
 * @returns {Promise<string>} Type result
 */
export async function type(ref, text, options = {}) {
  if (!ref) throw new BrowserError('ref is required for type', 'element');
  if (text === undefined || text === null) {
    throw new BrowserError('text is required for type', 'action');
  }

  const { element, submit = false, slowly = false } = options;
  const args = { ref, text: String(text) };
  if (element) args.element = element;
  if (submit) args.submit = true;
  if (slowly) args.slowly = true;

  return withRetry(
    async (attempt) => {
      if (attempt > 0) {
        console.error(`[browser] Type retry ${attempt}: re-capturing snapshot`);
        lastSnapshot = null;
        await snapshot({ force: true });
      }
      const result = mcporter('browser_type', args);
      lastSnapshot = null;
      return result;
    },
    { maxRetries: 2, baseDelay: 1000 }
  );
}

/**
 * Select option(s) in a dropdown by ref.
 *
 * @param {string} ref - Element reference from snapshot
 * @param {string[]} values - Values to select
 * @param {object} [options] - Select options
 * @param {string} [options.element] - Human-readable description
 * @returns {Promise<string>} Select result
 */
export async function select(ref, values, options = {}) {
  if (!ref) throw new BrowserError('ref is required for select', 'element');
  if (!Array.isArray(values) || values.length === 0) {
    throw new BrowserError('values array is required for select', 'action');
  }

  const { element } = options;
  const args = { ref, values };
  if (element) args.element = element;

  const result = mcporter('browser_select_option', args);
  lastSnapshot = null;
  return result;
}

/**
 * Press a keyboard key.
 *
 * @param {string} key - Key name (e.g., 'Enter', 'ArrowDown', 'a')
 * @returns {Promise<string>} Key press result
 */
export async function pressKey(key) {
  if (!key) throw new BrowserError('key is required', 'action');
  const result = mcporter('browser_press_key', { key });
  lastSnapshot = null;
  return result;
}

/**
 * Hover over an element by ref.
 *
 * @param {string} ref - Element reference from snapshot
 * @param {object} [options] - Hover options
 * @param {string} [options.element] - Human-readable description
 * @returns {Promise<string>} Hover result
 */
export async function hover(ref, options = {}) {
  if (!ref) throw new BrowserError('ref is required for hover', 'element');
  const args = { ref };
  if (options.element) args.element = options.element;
  return mcporter('browser_hover', args);
}

/**
 * Scroll the page.
 *
 * @param {string} [direction='down'] - Scroll direction
 * @returns {Promise<string>} Scroll result
 */
export async function scroll(direction = 'down') {
  const keyMap = {
    down: 'PageDown',
    up: 'PageUp',
    top: 'Home',
    bottom: 'End',
  };
  const key = keyMap[direction] || direction;
  return pressKey(key);
}

/**
 * Wait for a condition.
 *
 * @param {object} options - Wait options (one required)
 * @param {number} [options.time] - Seconds to wait
 * @param {string} [options.text] - Text to wait for (appear)
 * @param {string} [options.textGone] - Text to wait for (disappear)
 * @returns {Promise<string>} Wait result
 */
export async function waitFor(options = {}) {
  if (!options.time && !options.text && !options.textGone) {
    throw new BrowserError('One of time, text, or textGone is required', 'action');
  }
  const args = {};
  if (options.time) args.time = options.time;
  if (options.text) args.text = options.text;
  if (options.textGone) args.textGone = options.textGone;

  return mcporter('browser_wait_for', args);
}

/**
 * Fill multiple form fields at once.
 *
 * @param {Array<{ref: string, value: string}>} fields - Fields to fill
 * @returns {Promise<string[]>} Results for each field
 */
export async function fillForm(fields) {
  if (!Array.isArray(fields) || fields.length === 0) {
    throw new BrowserError('fields array is required', 'action');
  }

  const results = [];
  for (const field of fields) {
    if (!field.ref || field.value === undefined) {
      throw new BrowserError('Each field needs ref and value', 'action', { field });
    }
    const result = await type(field.ref, field.value);
    results.push(result);
  }
  return results;
}

/**
 * Go back to previous page.
 * @returns {Promise<string>} Navigation result
 */
export async function goBack() {
  lastSnapshot = null;
  return mcporter('browser_navigate_back');
}

/**
 * Manage browser tabs.
 *
 * @param {string} action - Tab action (list|new|close|select)
 * @param {number} [index] - Tab index for close/select
 * @returns {Promise<string>} Tab operation result
 */
export async function tabs(action, index) {
  const args = { action };
  if (index !== undefined) args.index = index;
  return mcporter('browser_tabs', args);
}

/**
 * Close the browser.
 * @returns {Promise<string>} Close result
 */
export async function close() {
  lastSnapshot = null;
  lastSnapshotTime = 0;
  return mcporter('browser_close');
}

/**
 * Evaluate JavaScript on the page.
 *
 * @param {string} fn - JavaScript function string
 * @param {object} [options] - Eval options
 * @param {string} [options.ref] - Element ref to pass as argument
 * @param {string} [options.element] - Human-readable element description
 * @returns {Promise<string>} Evaluation result
 */
export async function evaluate(fn, options = {}) {
  if (!fn) throw new BrowserError('function is required for evaluate', 'action');
  const args = { function: fn };
  if (options.ref) args.ref = options.ref;
  if (options.element) args.element = options.element;
  return mcporter('browser_evaluate', args);
}

/**
 * Drag and drop between two elements.
 *
 * @param {string} startRef - Source element ref
 * @param {string} endRef - Target element ref
 * @param {object} [options] - Drag options
 * @param {string} [options.startElement] - Source description
 * @param {string} [options.endElement] - Target description
 * @returns {Promise<string>} Drag result
 */
export async function drag(startRef, endRef, options = {}) {
  if (!startRef || !endRef) {
    throw new BrowserError('startRef and endRef are required', 'element');
  }
  const args = {
    startRef,
    endRef,
    startElement: options.startElement || 'source',
    endElement: options.endElement || 'target',
  };
  lastSnapshot = null;
  return mcporter('browser_drag', args);
}
