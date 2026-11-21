const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const entry = path.join(__dirname, '../docs/speed.html');
const html = fs.readFileSync(entry, 'utf8');
const script = [...html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi)]
  .map(match => match[1]).find(source => source.includes('function startGPS('));

// Run the actual watchPosition callback, fetch and rendering path for the standalone page.
async function createSpeedometer(fetch) {
  function element() {
    const classes = new Set(), listeners = new Map();
    return {
      addEventListener(name, fn) { listeners.set(name, fn); },
      click() { listeners.get('click')?.(); },
      setAttribute() {}, style: {setProperty() {}},
      classList: {
        add(...names) { names.forEach(name => classes.add(name)); },
        remove(...names) { names.forEach(name => classes.delete(name)); },
        toggle(name, active) { if (active) classes.add(name); else classes.delete(name); },
        contains(name) { return classes.has(name); }
      }
    };
  }
  const elements = new Map();
  const buttons = ['kmh','mph','knots'].map(unit => ({...element(), dataset: {unit}}));
  const document = {
    addEventListener() {},
    querySelectorAll: selector => selector === '[data-unit]' ? buttons : [],
    getElementById(id) {
      if (!elements.has(id)) elements.set(id, element());
      return elements.get(id);
    }
  };
  let receivePosition;
  let now = 1_800_000_000_000;
  const context = vm.createContext({
    URL, AbortController, fetch, document, console,
    Date: class extends Date { static now() { return now; } },
    localStorage: {getItem: () => null},
    window: {addEventListener() {}},
    navigator: {geolocation: {watchPosition(fn) { receivePosition = fn; return 1; }}},
    setTimeout, clearTimeout, setInterval: () => 1, clearInterval() {}
  });
  vm.runInContext(script, context, {filename: 'speed.html'});
  await vm.runInContext('startGPS()', context);
  assert.equal(typeof receivePosition, 'function');

  return {
    fix({latitude, longitude, accuracy = 3, speed = 12, heading = null}) {
      now += 2000;
      receivePosition({timestamp: now, coords: {latitude, longitude, accuracy, speed, heading}});
    },
    chooseUnit: unit => buttons.find(button => button.dataset.unit === unit).click(),
    hasClass: (id, name) => document.getElementById(id).classList.contains(name),
    speed: () => document.getElementById('speed').textContent,
    message: () => document.getElementById('messageMain').textContent,
    sign: () => document.getElementById('speedSign').textContent,
    road: () => document.getElementById('roadText').textContent,
    idle: () => new Promise(resolve => setImmediate(resolve))
  };
}

module.exports = {createSpeedometer};
