export default async function run(page) {
  const base = 'http://127.0.0.1:5055';
  const errors = [], failed = [], responses = [];
  page.on('console', msg => { if (msg.type() === 'error') errors.push(msg.text()); });
  page.on('requestfailed', req => failed.push({ url: req.url(), error: req.failure()?.errorText }));
  page.on('response', r => { if (r.status() >= 400) responses.push({ url: r.url(), status: r.status() }); });
  await page.goto(base + '/login');
  await page.locator('input[name="mobile"]').fill('9800001');
  await page.locator('input[name="password"]').fill('Resident@123');
  await page.locator('button[type="submit"]').click();
  await page.waitForLoadState('domcontentloaded');
  const login = { url: page.url(), text: (await page.locator('body').innerText()).slice(0, 120) };
  const paths = ['/dashboard', '/resident/profile', '/resident/complaints', '/resident/visitors', '/facilities', '/resident/support', '/resident/events', '/resident/notifications', '/resident/ai-assistant'];
  const pages = {};
  for (const path of paths) { const r = await page.goto(base + path, { waitUntil: 'domcontentloaded' }); pages[path] = { status: r?.status() ?? null, url: page.url() }; }
  const storage = await page.evaluate(() => ({ local: Object.keys(localStorage), session: Object.keys(sessionStorage), cookieNames: document.cookie.split(';').filter(Boolean).map(x => x.split('=')[0]) }));
  await page.goto(base + '/logout', { waitUntil: 'domcontentloaded' });
  const after = await page.goto(base + '/dashboard', { waitUntil: 'domcontentloaded' });
  return { login, pages, storage, afterLogout: { status: after?.status() ?? null, url: page.url() }, errors, failed, responses };
}