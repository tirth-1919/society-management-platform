export default async function run(page) {
  const base = 'http://127.0.0.1:5055'; const errors = [], failed = [], statuses = {};
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()) }); page.on('requestfailed', r => failed.push({ url: r.url(), error: r.failure()?.errorText }));
  await page.goto(base + '/admin/login'); await page.locator('input[name="username"]').fill('admin'); await page.locator('input[name="password"]').fill('Admin@123'); await page.locator('button[type="submit"]').click(); await page.waitForLoadState('domcontentloaded');
  const loginUrl = page.url(); const paths = ['/dashboard', '/admin/residents', '/admin/registrations', '/payments/bills', '/admin/payments', '/complaints/', '/visitors/', '/facilities', '/admin/events', '/admin/events/photos', '/resident/notifications', '/admin/support', '/admin/ai', '/admin/automation'];
  for (const p of paths) { const r = await page.goto(base + p, { waitUntil: 'domcontentloaded' }); statuses[p] = { status: r?.status() ?? null, url: page.url() }; }
  await page.goto(base + '/logout'); const after = await page.goto(base + '/admin/residents'); return { loginUrl, statuses, afterLogout: { status: after?.status() ?? null, url: page.url() }, errors, failed };
}