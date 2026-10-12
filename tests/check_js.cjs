/* Syntax validation without loading browser scripts into a Node runtime. */
const fs = require('node:fs');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const root = path.resolve(__dirname, '..');
let count = 0;
for (const directory of ['web', 'tests']) {
  for (const name of fs.readdirSync(path.join(root, directory))) {
    if (!/\.(?:js|cjs)$/.test(name)) continue;
    execFileSync(process.execPath, ['--check', path.join(root, directory, name)], { stdio: 'inherit', windowsHide: true });
    count++;
  }
}
console.log(`PASS: syntax checked ${count} JavaScript files.`);
