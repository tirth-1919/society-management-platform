export default async function run(page) {
  const base = 'http://127.0.0.1:5055';
  const errors = [];
  const failed = [];
  page.on('console', msg => { if (msg.type() === 'error') errors.push(msg.text()); });
  page.on('requestfailed', req => failed.push({ url: req.url(), failure: req.failure()?.errorText }));
  const pages = ['/dashboard', '/resident/profile', '/resident/complaints', '/resident/visitors', '/facilities', '/resident/support', '/resident/events', '/resident/notifications', '/resident/ai-assistant'];
  await page.goto(base + '/login');
  await page.locator('input[name="mobile"]').fill('9800001');
  await page.locator('input[name="password"]').fill('Resident@123');
  await page.locator('button[type="submit"]').click();
  await page.waitForLoadState('domcontentloaded');
  const loginUrl = page.url();
  const statuses = {};
  for (const path of pages) { const r = await page.goto(base + path, { waitUntil: 'domcontentloaded' }); statuses[path] = { status: r?.status() ?? null, url: page.url() }; }
  const storage = await page.evaluate(() => ({ local: Object.keys(localStorage), session: Object.keys(sessionStorage), cookies: document.cookie }));
  await page.goto(base + '/logout', { waitUntil: 'domcontentloaded' });
  const afterLogout = await page.goto(base + '/dashboard', { waitUntil: 'domcontentloaded' });
  return { loginUrl, statuses, afterLogout: { status: afterLogout?.status() ?? null, url: page.url() }, storage, errors, failed };
}