// Reference implementation of mcp-tool-set-digest/1 (SPEC.md). Node.js 20+, no dependencies.
// The same file is valid TypeScript-checked JavaScript (JSDoc types, `// @ts-check`).
//
//   import { digests } from './tool-set-digest.mjs';
//   const { contract, extras } = digests(jsonTextOfTheToolsArray);   // extras is null when no tool has any
//
// `node tool-set-digest.mjs < tools.json` prints both digests.
// `node tool-set-digest.mjs --vectors ../../vectors/vectors.json` checks every published vector.
//
// Licence: Apache-2.0 OR MIT.
// @ts-check

import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

export class DigestError extends Error {
  /** @param {string} code @param {string} detail */
  constructor(code, detail) { super(`${code}: ${detail}`); this.code = code; }
}

// --- parsing (section 3) -------------------------------------------------------------------------

export const MAX_LEVEL = 512;        // section 12: the tools array is level 1, a tool level 2
const WRAPPER_LEVELS = 2;             // a JSON-RPC response and its result can wrap the tools array
// A string token (so brackets inside strings are skipped) or a bracket.
const TOKEN = /"[^"\\]*(?:\\.[^"\\]*)*"|[[\]{}]/gs;
/** @type {Record<string, string>} */
const CLOSER = { '[': ']', '{': '}' };

/** The text with every array or object nested deeper than `limit` (counting the outermost value
 * as 1) replaced by an empty one of the same kind. Nothing deeper than level 512 can reach a digest
 * (section 12: a digest that would cover it gives TSD-DEPTH), and a replaced container keeps its
 * kind and its level, so every answer stays what it would have been. It keeps the parser and the
 * writer out of deep recursion; mismatched brackets are refused as JSON.parse would refuse them.
 * @param {string} text @param {number} [limit] */
export function cutDeep(text, limit = MAX_LEVEL + WRAPPER_LEVELS) {
  let depth = 0, last = 0;
  /** @type {string[]} */
  const pieces = [];
  const tokens = text.matchAll(TOKEN);
  for (const token of tokens) {
    const mark = token[0];
    if (mark[0] === '"') continue;
    if (mark === '[' || mark === '{') {
      if (++depth <= limit) continue;
      const start = /** @type {number} */ (token.index);
      const closers = [CLOSER[mark]];
      let end = -1;
      for (const inner of tokens) {
        const found = inner[0];
        if (found[0] === '"') continue;
        if (found === '[' || found === '{') closers.push(CLOSER[found]);
        else if (closers.pop() !== found) throw new SyntaxError(`brackets do not match at ${inner.index}`);
        if (!closers.length) { end = /** @type {number} */ (inner.index) + 1; break; }
      }
      if (end < 0) throw new SyntaxError(`a nested value is not closed at ${start}`);
      pieces.push(text.slice(last, start), mark === '[' ? '[]' : '{}');
      last = end;
      depth--;
    } else depth--;
  }
  return pieces.length ? pieces.join('') + text.slice(last) : text;
}

/** JSON text to values. JSON.parse already reads every number as the nearest IEEE 754 double; a
 * literal too large for one (1e400) becomes Infinity and is refused when a digest that covers it
 * is computed, so a member outside the contract cannot take the contract digest away. Arrays and
 * objects deeper than any digest can cover are read as empty (cutDeep).
 * @param {string} text @returns {unknown} */
export const parse = (text) => JSON.parse(cutDeep(text));

/** Whether an array or object inside `value` (itself at `level`) sits deeper than `limit`.
 * @param {unknown} value @param {number} level @param {number} [limit] */
export function deeperThan(value, level, limit = MAX_LEVEL) {
  /** @type {[unknown, number][]} */
  const stack = [[value, level]];
  while (stack.length) {
    const [item, at] = /** @type {[unknown, number]} */ (stack.pop());
    if (at > limit) return true;
    for (const child of Object.values(/** @type {object} */ (item))) {
      if (child && typeof child === 'object') stack.push([child, at + 1]);
    }
  }
  return false;
}

/** Section 12: each projection is a tool's contract entry or its extras, read at level 2 (the tool's
 * own level), so the values of its members are at level 3.
 * @param {[string, object][]} projections */
function checkDepth(projections) {
  for (const [name, projection] of projections) {
    if (deeperThan(projection, 2)) {
      throw new DigestError('TSD-DEPTH', `a value of tool ${JSON.stringify(name)} is nested deeper than level ${MAX_LEVEL}`);
    }
  }
}

// --- canonical form (section 6): RFC 8785 --------------------------------------------------------

/** @param {string} text */
function string(text) {
  if (!text.isWellFormed()) throw new DigestError('TSD-TEXT', 'a string holds a lone surrogate');
  return JSON.stringify(text);
}

/** @param {unknown} value @returns {string} */
export function canonical(value) {
  if (value === null || typeof value === 'boolean') return String(value);
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) throw new DigestError('TSD-NUMBER', 'a number with no IEEE 754 double');
    return JSON.stringify(value);                          // ECMAScript Number::toString; -0 is "0"
  }
  if (typeof value === 'string') return string(value);
  if (Array.isArray(value)) return '[' + value.map(canonical).join(',') + ']';
  if (typeof value === 'object') {
    const object = /** @type {Record<string, unknown>} */ (value);
    // Default string comparison is by UTF-16 code units: the order RFC 8785 section 3.2.3 asks for.
    return '{' + Object.keys(object).sort().map((key) => string(key) + ':' + canonical(object[key])).join(',') + '}';
  }
  throw new TypeError(`${typeof value} is not a JSON value`);
}

// --- the two digests (sections 4 to 8) -------------------------------------------------------------

/** @param {unknown} tool @returns {Record<string, unknown>} */
function toolObject(tool) {
  if (!tool || typeof tool !== 'object' || Array.isArray(tool)) throw new DigestError('TSD-TOOL', 'a tool entry is not a JSON object');
  const object = /** @type {Record<string, unknown>} */ (tool);
  if (typeof object.name !== 'string' || !object.name) throw new DigestError('TSD-TOOL', 'a tool entry has no non-empty string name');
  return object;
}

const isObject = (/** @type {unknown} */ v) => !!v && typeof v === 'object' && !Array.isArray(v);

/** @param {unknown} tool */
export function contractEntry(tool) {
  const t = toolObject(tool);
  /** @type {Record<string, unknown>} */
  const entry = {
    name: t.name,
    description: typeof t.description === 'string' ? t.description : '',
    inputSchema: isObject(t.inputSchema) ? t.inputSchema : {},
  };
  if (isObject(t.outputSchema)) entry.outputSchema = t.outputSchema;
  return entry;
}

/** By name in UTF-16 code units; entries sharing a name by their canonical UTF-8 bytes.
 * @param {Record<string, unknown>[]} entries */
export function ordered(entries) {
  const bytes = new Map();
  const tie = (/** @type {Record<string, unknown>} */ e) => {
    if (!bytes.has(e)) bytes.set(e, Buffer.from(canonical(e), 'utf8'));
    return bytes.get(e);
  };
  return [...entries].sort((a, b) => {
    const x = /** @type {string} */ (a.name), y = /** @type {string} */ (b.name);
    return x < y ? -1 : x > y ? 1 : Buffer.compare(tie(a), tie(b));
  });
}

/** @param {Record<string, unknown>[]} entries */
function digestOf(entries) {
  const text = canonical(ordered(entries));
  return { digest: 'sha256-' + createHash('sha256').update(text, 'utf8').digest('base64'), canonical: text };
}

/** Extract a complete tools array or the tools from an unpaginated tools/list result.
 * @param {any} value @returns {unknown[]} */
export function toolsOf(value) {
  if (Array.isArray(value)) return value;
  for (const result of [value, value?.result]) {
    if (result !== null && typeof result === 'object' && !Array.isArray(result)
        && Object.hasOwn(result, 'tools') && Object.hasOwn(result, 'result')) {
      throw new DigestError('TSD-TOOL', 'an object holds both tools and result (section 3)');
    }
    if (!Array.isArray(result?.tools)) continue;
    if (Object.hasOwn(result, 'nextCursor')) {
      throw new DigestError('TSD-PAGE', 'collect all pages and pass the joined tools array');
    }
    return result.tools;
  }
  throw new DigestError('TSD-TOOL', 'the input holds no tools array');
}

const CONTRACT_MEMBERS = new Set(['name', 'description', 'inputSchema', 'outputSchema']);

/** @param {unknown[]} tools */
export function contract(tools) {
  const entries = tools.map(contractEntry);
  checkDepth(entries.map((entry) => [/** @type {string} */ (entry.name), entry]));
  return digestOf(entries);
}

/** `{"tools": {name: extras}}` for the tools that carry a member outside the contract, or null
 * when none does (section 8).
 * @param {unknown[]} tools @returns {{tools: Record<string, unknown>} | null} */
export function extrasObject(tools) {
  /** @type {Map<string, Record<string, unknown>>} */
  const byName = new Map();
  for (const item of tools) {
    const tool = toolObject(item);
    const extra = Object.fromEntries(Object.entries(tool).filter(([key]) => !CONTRACT_MEMBERS.has(key)));
    if (!Object.keys(extra).length) continue;
    const name = /** @type {string} */ (tool.name);
    if (byName.has(name)) throw new DigestError('TSD-NAME', `two tools named ${JSON.stringify(name)} both carry extras`);
    byName.set(name, extra);
  }
  if (!byName.size) return null;
  // A null-prototype object, filled with defineProperty, keeps a tool named "__proto__" an ordinary member.
  const members = Object.create(null);
  for (const [name, extra] of byName) Object.defineProperty(members, name, { value: extra, enumerable: true });
  return { tools: members };
}

/** The extras digest; `{digest: null}` when no tool carries extras.
 * @param {unknown[]} tools @returns {{digest: string, canonical: string} | {digest: null}} */
export function extras(tools) {
  const body = extrasObject(tools);
  if (!body) return { digest: null };
  checkDepth(Object.entries(body.tools));
  const text = canonical(body);
  return { digest: 'sha256-' + createHash('sha256').update(text, 'utf8').digest('base64'), canonical: text };
}

/** Both digests, each `{digest, canonical}` or `{error}`, computed apart.
 * @param {string} text */
export function both(text) {
  const tools = toolsOf(parse(text));
  /** @type {Record<string, {digest: string | null, canonical?: string} | {error: string}>} */
  const out = {};
  for (const [kind, compute] of /** @type {const} */ ([['contract', contract], ['extras', extras]])) {
    try { out[kind] = compute(tools); }
    catch (error) { if (!(error instanceof DigestError)) throw error; out[kind] = { error: error.code }; }
  }
  return out;
}

/** `{contract, extras}` digests (extras null when no tool has any); throws DigestError when either
 * cannot be computed.
 * @param {string} text */
export function digests(text) {
  const tools = toolsOf(parse(text));
  return { contract: contract(tools).digest, extras: extras(tools).digest };
}

/** The same hash as `sha256:<lowercase hex>`. @param {string} digest */
export const hexForm = (digest) => 'sha256:' + Buffer.from(digest.slice(digest.indexOf('-') + 1), 'base64').toString('hex');

// --- command line ---------------------------------------------------------------------------------

/** @param {string} path */
function checkVectors(path) {
  const document = JSON.parse(readFileSync(path, 'utf8'));
  let failed = 0;
  /** @type {Record<string, Record<string, any>>} */
  const byId = {};
  for (const vector of document.vectors) {
    let got;
    try { got = both(vector.tools); }
    catch (error) {
      if (!(error instanceof DigestError)) throw error;      // the input holds no tools array
      got = { contract: { error: error.code }, extras: { error: error.code } };
    }
    byId[vector.id] = got;
    for (const kind of ['contract', 'extras']) {
      const { hex, ...want } = vector[kind];
      const same = JSON.stringify(Object.entries(got[kind]).sort()) === JSON.stringify(Object.entries(want).sort());
      if (!same) { failed++; console.log(`FAIL ${vector.id} ${kind}: ${got[kind].digest ?? got[kind].error} != ${want.digest ?? want.error}`); }
      else if (want.digest && hexForm(want.digest) !== hex) { failed++; console.log(`FAIL ${vector.id} ${kind}: hex form`); }
    }
  }
  for (const [relation, same] of /** @type {const} */ ([['equal', true], ['differ', false]])) {
    for (const row of document[relation] ?? []) {
      const [first, second] = row.ids.map((/** @type {string} */ id) => byId[id][row.digest].digest);
      if (!first || !second || (first === second) !== same) { failed++; console.log(`FAIL ${relation} ${row.ids} ${row.digest}`); }
    }
  }
  console.log(`javascript: ${document.vectors.length} vectors, ${failed} failed`);
  return failed ? 1 : 0;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const args = process.argv.slice(2);
  if (args.length === 2 && args[0] === '--vectors') process.exit(checkVectors(args[1]));
  try {
    const result = both(readFileSync(0, 'utf8'));
    console.log(JSON.stringify(Object.fromEntries(Object.entries(result).map(
      ([kind, value]) => [kind, 'digest' in value ? value.digest : { error: value.error }]))));
    process.exit(Object.values(result).every((value) => 'digest' in value) ? 0 : 2);
  } catch (error) {
    if (!(error instanceof DigestError)) throw error;
    console.log(JSON.stringify({ error: error.code, detail: error.message }));
    process.exit(2);
  }
}
