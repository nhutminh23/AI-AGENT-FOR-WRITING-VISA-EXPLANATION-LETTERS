function parseMetadata(code) {
  const meta = {};
  const headerMatch = code.match(/\/\/\s*==UserScript==\s*\n([\s\S]*?)\/\/\s*==\/UserScript==/);
  if (!headerMatch) return meta;

  const lines = headerMatch[1].split('\n');
  for (const line of lines) {
    const m = line.match(/\/\/\s*@(\S+)\s+(.*)/);
    if (!m) continue;
    const key = m[1].trim();
    const value = m[2].trim();
    if (key in meta) {
      if (!Array.isArray(meta[key])) meta[key] = [meta[key]];
      meta[key].push(value);
    } else {
      meta[key] = value;
    }
  }

  if (meta.match && !Array.isArray(meta.match)) {
    meta.match = [meta.match];
  }
  if (meta.include && !Array.isArray(meta.include)) {
    meta.include = [meta.include];
  }

  return meta;
}

function buildMetadataBlock(meta) {
  let block = '// ==UserScript==\n';
  const order = ['name', 'namespace', 'version', 'description', 'author', 'match', 'icon', 'grant'];
  const written = new Set();

  for (const key of order) {
    if (!(key in meta)) continue;
    const values = Array.isArray(meta[key]) ? meta[key] : [meta[key]];
    for (const v of values) {
      block += `// @${key.padEnd(12)} ${v}\n`;
    }
    written.add(key);
  }

  for (const [key, val] of Object.entries(meta)) {
    if (written.has(key)) continue;
    const values = Array.isArray(val) ? val : [val];
    for (const v of values) {
      block += `// @${key.padEnd(12)} ${v}\n`;
    }
  }

  block += '// ==/UserScript==';
  return block;
}
