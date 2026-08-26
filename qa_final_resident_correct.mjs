export default async function run(page) {
  const base = 'http://127.0.0.1:5055'; const errors = [], failed = [], statuses = {};
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()) }); page.on('requestfailed', r => failed.push({ url: r.url(), error: r.failure()?.errorText }));
  await page.goto(base + '/login'); await page.locator('input[name="mobile"]').fill('9800001'); await page.locator('input[name="password"]').fill('Resident@123'); await page.locator('button[type="submit"]').click(); await page.waitForLoadState('domcontentloaded');
  const loginUrl = page.url(); const paths = ['/dashboard', '/resident/profile', '/resident/complaints', '/resident/visitors', '/facilities', '/resident/support', '/resident/events', '/resident/notifications', '/resident/ai-assistant'];
  for (const p of paths) { const r = await page.goto(base + p, { waitUntil: 'domcontentloaded' }); statuses[p] = { status: r?.status() ?? null, url: page.url() }; }
  const storage = await page.evaluate(() => ({ local: Object.keys(localStorage), session: Object.keys(sessionStorage), cookies: document.cookie })); await page.goto(base + '/logout'); const after = await page.goto(base + '/dashboard');
  return { loginUrl, statuses, storage, afterLogout: { status: after?.status() ?? null, url: page.url() }, errors, failed };
}