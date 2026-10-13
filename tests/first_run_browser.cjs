/* First-run setup and restart with real HTTP/SQLite and synthetic Portainer. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { chromium } = require('playwright');
const { createFixture, browserOptions } = require('./fixture.cjs');

async function main() {
  const fixture = await createFixture({ initialize: false });
  const { base, password, token, upstreamURL } = fixture;
  const evidence = fs.mkdtempSync(path.join(os.tmpdir(), 'portainer-first-run-evidence-'));
  const failures = [];
  let browser;
  try {
    browser = await chromium.launch(browserOptions());
    const context = await browser.newContext({ viewport: { width: 1366, height: 1000 }, colorScheme: 'dark' });
    const page = await context.newPage();
    page.on('pageerror', (error) => failures.push(error.message));
    await page.goto(base);
    await page.locator('#setup-form').waitFor();
    assert.equal(await page.locator('#setup-url').inputValue(), '');
    assert.equal(await page.locator('#setup-token').inputValue(), '');
    await page.screenshot({ path: path.join(evidence, 'first-run-dark.png'), fullPage: true });
    assert.equal((await context.request.get(base + '/api/dashboards')).status(), 401);
    await page.locator('#setup-password').fill(password);
    await page.locator('#setup-confirm').fill(password);
    await page.locator('#setup-url').fill(upstreamURL);
    await page.locator('#setup-token').fill('wrong-synthetic-token');
    await page.getByRole('button', { name: 'Test connection & create workspace' }).click();
    await page.locator('#setup-result').filter({ hasText: 'Invalid credentials' }).waitFor();
    assert.equal((await (await context.request.get(base + '/api/session')).json()).setup_required, true);
    await page.locator('#setup-token').fill(token);
    await page.getByRole('button', { name: 'Test connection & create workspace' }).click();
    await page.locator('#auth-screen').waitFor({ state: 'hidden' });
    const boards = await (await context.request.get(base + '/api/dashboards')).json();
    assert.deepEqual(boards.dashboards, []);
    await page.locator('[data-view="settings"]').click();
    await page.locator('#portainer-url').waitFor();
    assert.equal(await page.locator('#portainer-token').inputValue(), '');
    await context.close();
    await fixture.stop();
    await fixture.start();
    const again = await browser.newContext();
    const login = await again.newPage();
    login.on('pageerror', (error) => failures.push(error.message));
    await login.goto(base);
    await login.locator('#login-password').waitFor();
    assert.equal(await login.locator('.auth-card .eyebrow').innerText(), 'EDGE CONSOLE / ADMINISTRATION');
    assert.equal(await login.locator('#workspace-port').innerText(), ':' + new URL(base).port);
    assert.equal(await login.locator('#setup-form').count(), 0);
    await login.locator('#login-password').fill(password);
    await login.getByRole('button', { name: 'Sign in', exact: true }).click();
    await login.locator('#auth-screen').waitFor({ state: 'hidden' });
    assert.equal((await (await again.request.get(base + '/api/settings')).json()).saved, true);
    assert.deepEqual(failures, []);
    console.log('PASS: clean first-run browser, empty connection, no dashboards, failed-test rollback, initialization and restart/login persistence. Synthetic integration only.');
    console.log('Evidence: ' + evidence);
  } finally {
    await browser?.close();
    await fixture.dispose();
  }
}

main().catch((error) => { console.error(error); process.exitCode = 1; });
