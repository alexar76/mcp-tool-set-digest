// Checks every vector against WARDEN's own code. Its contract digest (warden/src/mtl.ts) was
// written before this specification and separately from its reference implementations; its extras
// digest (warden/src/tool-set-digest.ts) was written from this specification.
//
//   node scripts/cross_check_warden.mjs <path to warden/dist>
//
// WARDEN's older error codes are its own: MTL-SUBJ-001 (not a tool, or a string it cannot
// canonicalise) and MTL-NUM-001 (a number with no double).
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';

const dist = process.argv[2];
const { mtlToolSetDigest, MtlError } = await import(pathToFileURL(join(dist, 'mtl.js')).href);
const { extrasDigest, ToolSetDigestError } = await import(pathToFileURL(join(dist, 'tool-set-digest.js')).href);
const SAME_REASON = { 'TSD-TOOL': ['MTL-SUBJ-001'], 'TSD-TEXT': ['MTL-SUBJ-001'], 'TSD-NUMBER': ['MTL-NUM-001'] };
const document = JSON.parse(readFileSync(new URL('../vectors/vectors.json', import.meta.url), 'utf8'));
let failed = 0;
for (const vector of document.vectors) {
  const tools = JSON.parse(vector.tools);
  const want = vector.contract;
  try {
    const got = mtlToolSetDigest(tools);
    if (got !== want.digest) { failed++; console.log(`FAIL ${vector.id} contract: WARDEN ${got} != ${want.digest ?? want.error}`); }
  } catch (error) {
    if (!(error instanceof MtlError) || !(SAME_REASON[want.error] ?? []).includes(error.code)) {
      failed++; console.log(`FAIL ${vector.id} contract: WARDEN refuses with ${error.code ?? error}, the vector says ${JSON.stringify(want)}`);
    }
  }
  const extras = vector.extras;
  try {
    const got = extrasDigest(tools) ?? null;
    if (extras.error || got !== extras.digest) { failed++; console.log(`FAIL ${vector.id} extras: WARDEN ${got} != ${extras.digest ?? extras.error}`); }
  } catch (error) {
    if (!(error instanceof ToolSetDigestError) || error.code !== extras.error) {
      failed++; console.log(`FAIL ${vector.id} extras: WARDEN refuses with ${error.code ?? error}, the vector says ${JSON.stringify(extras)}`);
    }
  }
}
console.log(`warden: ${document.vectors.length} vectors, contract and extras digests, ${failed} failed`);
process.exit(failed ? 1 : 0);
