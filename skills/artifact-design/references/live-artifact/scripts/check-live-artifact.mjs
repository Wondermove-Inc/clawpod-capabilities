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
      const submit = Array.isArray(manifest.capabilities) && manifest.capabilities.length === 1 && manifest.capabilities[0] === 'submit';
      if (manifest.capabilities !== undefined && (!Array.isArray(manifest.capabilities) || manifest.capabilities.length > 1 || manifest.capabilities.some(value => value !== 'submit'))) errors.push('Unknown capability');
      if (manifest.v !== 1 || !Array.isArray(manifest.keys) || (!manifest.keys.length && !submit) || manifest.keys.length > 8 || manifest.keys.some(key => !['agent.data', 'org-package.checklist'].includes(key))) {
        errors.push('Manifest requires v:1 and known keys, or the submit capability');
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
  const ids = sectionIds(markup);
  for (const id of new Set(ids.filter((value, index) => ids.indexOf(value) !== index))) errors.push(`duplicate data-section "${id}"`);
  return errors;
}

// Values of data-section attributes on elements (comments, script and style bodies excluded by caller).
export function sectionIds(markup) {
  return [...markup.matchAll(/<[a-z][^>"']*(?:"[^"]*"|'[^']*'|[^>"'])*>/gi)]
    .map(([tag]) => /\sdata-section\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>"']+))/i.exec(tag))
    .filter(Boolean).map(match => match[1] ?? match[2] ?? match[3]);
}

// Shared artifacts need data-section units to be section-editable; absence is a warning, not an error.
export function checkShared(html) {
  const markup = html.replace(/<!--[\s\S]*?-->/g, '').replace(/<(script|style|textarea|title)\b[^>]*>[\s\S]*?<\/\1\s*>/gi, '');
  return sectionIds(markup).length ? [] : ['no data-section found: add data-section="<id>" to each top-level editable element, or the artifact can only be saved whole (PUT .../content)'];
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const args = process.argv.slice(2);
  const shared = args.includes('--shared');
  const path = args.find(arg => !arg.startsWith('--'));
  if (!path) { console.error('Usage: node check-live-artifact.mjs [--shared] <file.html>'); process.exitCode = 2; }
  else {
    try {
      const html = readFileSync(path, 'utf8');
      const errors = checkLiveArtifact(html);
      const result = { file: path, passed: errors.length === 0, errors };
      if (shared) result.warnings = checkShared(html);
      console.log(JSON.stringify(result, null, 2));
      process.exitCode = errors.length ? 1 : 0;
    } catch (error) { console.error(error.message); process.exitCode = 2; }
  }
}
