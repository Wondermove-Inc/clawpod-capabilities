#!/usr/bin/env node
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

// Conservative authoring lint for quoted generated HTML. The portal's inert HTML parser
// and runtime sandbox remain authoritative; this is not an HTML security sanitizer.
export function checkLiveArtifact(html) {
  const errors = [];
  if (html.length > 200_000) errors.push('HTML exceeds 200000 characters');
  const markup = html.replace(/<!--[\s\S]*?-->/g, '').replace(/<(script|style|textarea|title)\b[^>]*>[\s\S]*?<\/\1\s*>/gi, '');
  const metas = [...markup.matchAll(/<meta\b(?:[^>"']|"[^"]*"|'[^']*')*>/gi)]
    .filter(([tag]) => /\bname\s*=\s*(["'])clawpod-live\1/i.test(tag));
  if (metas.length !== 1) errors.push('Use exactly one quoted clawpod-live meta element');
  else {
    const content = /\bcontent\s*=\s*(["'])([\s\S]*?)\1/i.exec(metas[0][0]);
    try {
      if (!content) throw Error('Missing quoted content');
      const decode = content[2].replace(/&(?:quot|apos|amp|lt|gt);|&#(?:x[\da-f]+|\d+);/gi, (entity) => {
        const names = { '&quot;': '"', '&apos;': "'", '&amp;': '&', '&lt;': '<', '&gt;': '>' };
        if (names[entity.toLowerCase()]) return names[entity.toLowerCase()];
        return String.fromCodePoint(entity[2].toLowerCase() === 'x' ? parseInt(entity.slice(3), 16) : parseInt(entity.slice(2), 10));
      });
      const manifest = JSON.parse(decode);
      if (manifest.v !== 1 || !Array.isArray(manifest.keys) || !manifest.keys.length || manifest.keys.length > 8 || manifest.keys.some(key => !['agent.data', 'org-package.checklist'].includes(key))) {
        errors.push('Manifest requires v:1 and 1..8 known keys');
      } else if (manifest.schemaVersions !== undefined) {
        const versions = manifest.schemaVersions;
        if (!versions || typeof versions !== 'object' || Array.isArray(versions) ||
            Object.keys(versions).some(key => !manifest.keys.includes(key)) ||
            manifest.keys.some(key => !Object.hasOwn(versions, key) || !Number.isInteger(versions[key]) || versions[key] < 1 || versions[key] > 2147483647))
          errors.push('schemaVersions must declare a positive integer version for every key');
      }
    } catch { errors.push('Manifest content must be valid JSON'); }
  }
  for (const [name, pattern] of [
    ['fetch', /\bfetch\s*\(/i], ['XMLHttpRequest', /\bXMLHttpRequest\b/],
    ['external URL', /(?:https?:\/\/|(?:src|href)\s*=\s*["']?\/\/)/i],
    ['innerHTML', /\binnerHTML\b/], ['WebSocket', /\bWebSocket\b/],
  ]) if (pattern.test(html)) errors.push(`Forbidden authoring pattern: ${name}`);
  return errors;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const path = process.argv[2];
  if (!path) { console.error('Usage: node check-live-artifact.mjs <file.html>'); process.exitCode = 2; }
  else {
    try {
      const errors = checkLiveArtifact(readFileSync(path, 'utf8'));
      console.log(JSON.stringify({ file: path, passed: errors.length === 0, errors }, null, 2));
      process.exitCode = errors.length ? 1 : 0;
    } catch (error) { console.error(error.message); process.exitCode = 2; }
  }
}
