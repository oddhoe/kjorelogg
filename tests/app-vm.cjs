const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const entry = path.join(__dirname, '../docs/index.html');

// Run the actual inline app code with isolated state. Tests call the relevant
// entry point themselves and may supply a recorded HTML version or I/O stubs.
function createAppContext(globals = {}, html = fs.readFileSync(entry, 'utf8')) {
  const script = [...html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi)]
    .map(match => match[1]).find(source => source.includes('async function bootApp()'));
  if (!script || !/^bootApp\(\)\.then\(/m.test(script)) {
    throw new Error('Cannot identify the Kjørelogg app entry point');
  }
  const element = {addEventListener() {}};
  const context = vm.createContext({
    console, setTimeout, clearTimeout, setInterval, clearInterval, window: element, navigator: {},
    document: {addEventListener() {}, getElementById: () => element, querySelector: () => null, querySelectorAll: () => []},
    ...globals
  });
  vm.runInContext(script.replace(/^bootApp\(\)\.then\(/m, 'false && bootApp().then('), context);
  return context;
}

module.exports = {createAppContext};
