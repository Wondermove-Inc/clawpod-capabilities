#!/usr/bin/env node
/**
 * Web Browser Skill — CLI Entry Point
 *
 * Usage:
 *   node browse.js <command> [args...]
 *
 * Commands:
 *   navigate <url>            Navigate to URL
 *   snapshot                  Capture accessibility tree
 *   screenshot [filename]     Take screenshot
 *   click <ref>               Click element by ref
 *   type <ref> <text>         Type text into element
 *   select <ref> <value>      Select dropdown option
 *   key <key>                 Press keyboard key
 *   scroll <direction>        Scroll page (up|down|top|bottom)
 *   wait <seconds>            Wait for time
 *   waitfor <text>            Wait for text to appear
 *   back                      Go back
 *   tabs [action]             Tab management (list|new|close|select)
 *   close                     Close browser
 *   verify <text>             Check if text exists on page
 *   errors                    Detect error messages
 *
 * Examples:
 *   node browse.js navigate "https://google.com"
 *   node browse.js snapshot
 *   node browse.js click e15
 *   node browse.js type e8 "hello world"
 *   node browse.js screenshot /tmp/page.png
 */

import * as browser from './lib/browser.js';
import * as verifier from './lib/verify.js';

const [,, command, ...args] = process.argv;

if (!command) {
  console.error('Usage: node browse.js <command> [args...]');
  console.error('Commands: navigate, snapshot, screenshot, click, type, select, key, scroll, wait, waitfor, back, tabs, close, verify, errors');
  process.exit(1);
}

async function main() {
  try {
    let result;

    switch (command) {
      case 'navigate':
      case 'nav':
      case 'go':
        if (!args[0]) { console.error('Usage: navigate <url>'); process.exit(1); }
        result = await browser.navigate(args[0]);
        break;

      case 'snapshot':
      case 'snap':
        result = await browser.snapshot({ force: true });
        break;

      case 'screenshot':
      case 'ss':
        result = await browser.screenshot({
          filename: args[0],
          fullPage: args.includes('--full'),
        });
        break;

      case 'click':
        if (!args[0]) { console.error('Usage: click <ref>'); process.exit(1); }
        result = await browser.click(args[0], {
          doubleClick: args.includes('--double'),
        });
        break;

      case 'type':
        if (!args[0] || !args[1]) { console.error('Usage: type <ref> <text>'); process.exit(1); }
        result = await browser.type(args[0], args.slice(1).join(' '), {
          submit: args.includes('--submit'),
        });
        break;

      case 'select':
        if (!args[0] || !args[1]) { console.error('Usage: select <ref> <value>'); process.exit(1); }
        result = await browser.select(args[0], [args[1]]);
        break;

      case 'key':
      case 'press':
        if (!args[0]) { console.error('Usage: key <keyname>'); process.exit(1); }
        result = await browser.pressKey(args[0]);
        break;

      case 'scroll':
        result = await browser.scroll(args[0] || 'down');
        break;

      case 'wait':
        if (!args[0]) { console.error('Usage: wait <seconds>'); process.exit(1); }
        result = await browser.waitFor({ time: parseFloat(args[0]) });
        break;

      case 'waitfor':
        if (!args[0]) { console.error('Usage: waitfor <text>'); process.exit(1); }
        result = await browser.waitFor({ text: args.join(' ') });
        break;

      case 'back':
        result = await browser.goBack();
        break;

      case 'tabs':
        result = await browser.tabs(args[0] || 'list', args[1] ? parseInt(args[1]) : undefined);
        break;

      case 'close':
        result = await browser.close();
        break;

      case 'hover':
        if (!args[0]) { console.error('Usage: hover <ref>'); process.exit(1); }
        result = await browser.hover(args[0]);
        break;

      case 'fill':
        console.error('Use: type <ref> <text> for each field');
        process.exit(1);
        break;

      case 'verify':
        if (!args[0]) { console.error('Usage: verify <text>'); process.exit(1); }
        const found = await verifier.verifyText(args.join(' '));
        result = found ? `✅ Found: "${args.join(' ')}"` : `❌ Not found: "${args.join(' ')}"`;
        break;

      case 'errors':
        const errResult = await verifier.detectErrors();
        result = errResult.hasError
          ? `⚠️ Errors detected:\n${errResult.errors.join('\n')}`
          : '✅ No errors detected';
        break;

      case 'eval':
        if (!args[0]) { console.error('Usage: eval <js-function>'); process.exit(1); }
        result = await browser.evaluate(args.join(' '));
        break;

      default:
        console.error(`Unknown command: ${command}`);
        console.error('Commands: navigate, snapshot, screenshot, click, type, select, key, scroll, wait, waitfor, back, tabs, close, verify, errors');
        process.exit(1);
    }

    if (result !== undefined && result !== null) {
      console.log(typeof result === 'string' ? result : JSON.stringify(result, null, 2));
    }
  } catch (err) {
    console.error(`[ERROR] ${err.message}`);
    if (err.context) console.error('Context:', JSON.stringify(err.context));
    process.exit(1);
  }
}

main();
