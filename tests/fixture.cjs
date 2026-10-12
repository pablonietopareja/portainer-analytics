/* Synthetic Portainer server and an owned, temporary application process. */
const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const fs = require('node:fs');
const http = require('node:http');
const os = require('node:os');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const token = 'synthetic-test-api-token';
const password = 'Synthetic-Browser-Password-Only';
const delay = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));
const listen = (server) => new Promise((resolve, reject) => {
  server.once('error', reject);
  server.listen(0, '127.0.0.1', () => resolve(server.address().port));
});
const close = (server) => new Promise((resolve, reject) => {
  if (!server.listening) return resolve();
  server.close((error) => error ? reject(error) : resolve());
  server.closeAllConnections();
});

function inventory(environment) {
  const prefix = environment === 1 ? 'a' : 'b';
  const id = prefix.repeat(64);
  const image = 'sha256:' + 'c'.repeat(64);
  const network = 'synthetic-network';
  const volume = 'synthetic-data';
  return { id, image, network, volume, containers: [{
    Id: id, Names: ['/synthetic-api-' + environment], Image: 'example/app:1.0', ImageID: image,
    State: 'running', Status: 'Up 1 hour (healthy)', Created: 1767225600,
    Labels: { 'com.docker.compose.project': 'synthetic-stack', 'com.docker.compose.service': 'api' },
    Ports: [{ PrivatePort: 8080, Type: 'tcp' }],
    Mounts: [{ Type: 'volume', Name: volume, Source: '/synthetic/volume', Destination: '/data', RW: true }],
    NetworkSettings: { Networks: { [network]: { IPAddress: '192.0.2.10', Gateway: '192.0.2.1' } } },
    Portainer: { Agent: { NodeName: 'synthetic-node-' + environment } },
  }] };
}

function syntheticResponse(environment, endpoint, tick) {
  const { id, image, network, volume, containers } = inventory(environment);
  if (endpoint === 'version') return { ApiVersion: '1.47', MinAPIVersion: '1.24', Version: '27.0.0' };
  if (endpoint === 'info') return {
    Name: 'synthetic-node-' + environment, NCPU: 4, MemTotal: 4 * 1024 ** 3,
    Architecture: 'aarch64', OperatingSystem: 'Synthetic Linux', KernelVersion: 'synthetic',
    ServerVersion: '27.0.0', Driver: 'overlay2', DockerRootDir: '/synthetic/docker',
    CgroupVersion: '2', MemoryLimit: true, LoggingDriver: 'json-file',
    Swarm: { LocalNodeState: 'inactive', ControlAvailable: false }, Warnings: [],
  };
  if (endpoint === 'containers/json') return containers;
  if (endpoint === 'images/json') return [{ Id: image, RepoTags: ['example/app:1.0'], Size: 128 * 1024 ** 2, Created: 1767225600, Labels: {} }];
  if (endpoint === 'volumes') return { Volumes: [{ Name: volume, Driver: 'local', Scope: 'local', Mountpoint: '/synthetic/volume', Labels: {}, CreatedAt: '2026-01-01T00:00:00Z' }] };
  if (endpoint === 'networks') return [{ Id: 'd'.repeat(64), Name: network, Driver: 'bridge', Scope: 'local', Internal: false, Attachable: false, IPAM: { Config: [{ Subnet: '192.0.2.0/24', Gateway: '192.0.2.1' }] } }];
  if (endpoint === 'system/df') return {
    LayersSize: 128 * 1024 ** 2,
    Images: [{ Id: image, Size: 128 * 1024 ** 2, SharedSize: 32 * 1024 ** 2, Containers: 1 }],
    Containers: [{ Id: id, SizeRw: 4 * 1024 ** 2, SizeRootFs: 132 * 1024 ** 2 }],
    Volumes: [{ Name: volume, UsageData: { Size: 16 * 1024 ** 2, RefCount: 1 } }],
    BuildCache: [{ ID: 'synthetic-build-cache', Size: 8 * 1024 ** 2, InUse: false, Shared: false, Type: 'regular', UsageCount: 1 }],
  };
  if (endpoint === 'v2/host/info') return { PhysicalDisks: [{ Vendor: 'Synthetic', Size: 64 * 1024 ** 3 }], PCIDevices: [{ Vendor: 'Synthetic', Name: 'Synthetic network adapter' }] };
  if (endpoint === 'v2/host/docker-storage') return { totalBytes: 64 * 1024 ** 3, availableBytes: 48 * 1024 ** 3, dockerBytes: 160 * 1024 ** 2 };
  if (endpoint === `containers/${id}/json`) return {
    Id: id, Name: containers[0].Names[0], Image: image, Created: '2026-01-01T00:00:00Z', RestartCount: 0,
    State: { Running: true, Status: 'running', StartedAt: '2026-01-01T00:00:00Z', OOMKilled: false, Health: { Status: 'healthy', FailingStreak: 0 } },
    HostConfig: { Memory: 512 * 1024 ** 2, NanoCpus: 1000000000, PidsLimit: 100, ReadonlyRootfs: true },
    Config: { Image: 'example/app:1.0', Labels: containers[0].Labels, Env: ['SYNTHETIC_OPTION=example'] },
    Mounts: containers[0].Mounts, NetworkSettings: containers[0].NetworkSettings,
  };
  if (endpoint === `containers/${id}/stats`) return {
    read: new Date().toISOString(),
    cpu_stats: { online_cpus: 4, system_cpu_usage: 4000000000 + tick * 1000000000, cpu_usage: { total_usage: 100000000 + tick * 10000000, usage_in_usermode: 80000000 + tick * 8000000, usage_in_kernelmode: 20000000 + tick * 2000000 }, throttling_data: { periods: 100 + tick, throttled_periods: 2, throttled_time: 2000000 } },
    precpu_stats: { system_cpu_usage: 3000000000 + tick * 1000000000, cpu_usage: { total_usage: 90000000 + tick * 10000000 } },
    memory_stats: { usage: 160 * 1024 ** 2, limit: 512 * 1024 ** 2, stats: { inactive_file: 32 * 1024 ** 2, anon: 128 * 1024 ** 2, file: 32 * 1024 ** 2, pgfault: 1000 + tick } },
    pids_stats: { current: 8, limit: 100 },
    networks: { eth0: { rx_bytes: 1000000 + tick * 10000, tx_bytes: 500000 + tick * 5000, rx_packets: 1000 + tick * 10, tx_packets: 500 + tick * 5, rx_errors: 0, tx_errors: 0, rx_dropped: 0, tx_dropped: 0 } },
    blkio_stats: { io_service_bytes_recursive: [{ op: 'Read', value: 100000 + tick * 1000 }, { op: 'Write', value: 50000 + tick * 500 }] },
  };
  return undefined;
}

async function createFixture({ initialize = true } = {}) {
  const data = fs.mkdtempSync(path.join(os.tmpdir(), 'portainer-analytics-test-'));
  let child, childClosed, processError, cookie = '', tick = 0, output = '';
  const unexpected = [];
  const upstream = http.createServer((req, res) => {
    res.setHeader('Content-Type', 'application/json');
    if (req.headers['x-api-key'] !== token) { res.writeHead(401); res.end('{}'); return; }
    const pathname = new URL(req.url, 'http://synthetic.invalid').pathname;
    if (pathname === '/api/endpoints') return res.end(JSON.stringify([1, 2].map((Id) => ({ Id, Name: 'Synthetic edge ' + Id, Type: 2, Status: 1 }))));
    if (pathname === '/api/stacks') return res.end(JSON.stringify([1, 2].map((EndpointId) => ({ Id: EndpointId, Name: 'synthetic-stack', EndpointId, Type: 2, Status: 1 }))));
    const match = pathname.match(/^\/api\/endpoints\/([12])\/docker\/(?:v1\.\d+\/)?(.+)$/);
    if (match) {
      if (match[2] === 'events') return res.end(JSON.stringify({ Type: 'container', Action: 'start', time: Math.floor(Date.now() / 1000), Actor: { ID: inventory(Number(match[1])).id, Attributes: { name: 'synthetic-api-' + match[1] } } }) + '\n');
      if (match[2].endsWith('/logs')) return res.end('Synthetic application started successfully\n');
      const value = syntheticResponse(Number(match[1]), match[2], ++tick);
      if (value !== undefined) return res.end(JSON.stringify(value));
    }
    unexpected.push(pathname);
    res.writeHead(404); res.end('{}');
  });
  const upstreamPort = await listen(upstream);
  const probe = http.createServer();
  const port = await listen(probe);
  await close(probe);
  const base = `http://127.0.0.1:${port}`;
  const upstreamURL = `http://127.0.0.1:${upstreamPort}`;

  async function request(route, options = {}) {
    const url = new URL(route, base);
    assert.equal(url.origin, base, 'Tests may only request their own fixture application');
    const headers = new Headers(options.headers || {});
    if (cookie) headers.set('Cookie', cookie);
    const response = await fetch(url, { ...options, headers, signal: options.signal || AbortSignal.timeout(10000) });
    const setCookie = response.headers.get('set-cookie');
    if (setCookie) cookie = setCookie.split(';')[0];
    return response;
  }
  async function start() {
    output = ''; processError = undefined;
    const env = { ...process.env };
    for (const name of Object.keys(env)) if (/^(CONSOLE_|PORTAINER_)/.test(name)) delete env[name];
    Object.assign(env, { CONSOLE_STANDALONE: 'true', CONSOLE_REQUIRE_LOGIN: 'true', PYTHONDONTWRITEBYTECODE: '1' });
    child = spawn(process.env.TEST_PYTHON || process.env.PYTHON || 'python', ['-u', 'portainer_console.py', '--host', '127.0.0.1', '--port', String(port), '--interval', '2', '--data-dir', data, '--require-login'], { cwd: root, env, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
    childClosed = new Promise((resolve) => child.once('close', resolve));
    child.on('error', (error) => { processError = error; });
    child.stdout.on('data', (chunk) => { output = (output + chunk).slice(-12000); });
    child.stderr.on('data', (chunk) => { output = (output + chunk).slice(-12000); });
    for (let attempt = 0; attempt < 150; attempt++) {
      if (processError) throw processError;
      if (child.exitCode !== null) throw Error('Fixture process exited: ' + output);
      try { if ((await request('/api/health')).ok) return; } catch { /* Startup is asynchronous. */ }
      await delay(100);
    }
    throw Error('Fixture startup timed out: ' + output);
  }
  async function stop() {
    if (child?.pid && child.exitCode === null) {
      child.kill('SIGTERM');
      const timer = setTimeout(() => child.kill('SIGKILL'), 10000);
      await childClosed; clearTimeout(timer);
    }
    if (childClosed) await childClosed;
    child = undefined; cookie = '';
  }
  async function dispose() {
    await stop(); await close(upstream);
    const parent = path.resolve(os.tmpdir()) + path.sep;
    assert.ok(path.resolve(data).startsWith(parent), 'Only an owned temporary directory may be removed');
    fs.rmSync(data, { recursive: true, force: true, maxRetries: 10, retryDelay: 100 });
    assert.deepEqual(unexpected, [], 'Every upstream request must have a synthetic response');
  }
  async function initializeWorkspace() {
    const session = await (await request('/api/session')).json();
    const response = await request('/api/setup', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Console-CSRF': session.csrf }, body: JSON.stringify({ password, url: upstreamURL, token, verify: true, timeout: 2 }) });
    assert.equal(response.status, 201, JSON.stringify(await response.json()));
    for (let attempt = 0; attempt < 100; attempt++) {
      const snapshot = await (await request('/api/snapshot')).json();
      if (snapshot.status === 'live' && snapshot.sequence >= 2) return;
      await delay(100);
    }
    throw Error('Synthetic inventory did not become live: ' + output);
  }
  try {
    await start();
    if (initialize) await initializeWorkspace();
    return { base, upstreamURL, password, token, request, start, stop, dispose, data };
  } catch (error) { await dispose(); throw error; }
}

function browserOptions() {
  const channel = process.env.TEST_BROWSER_CHANNEL;
  return { headless: true, ...(channel ? { channel } : {}) };
}

module.exports = { createFixture, browserOptions };
