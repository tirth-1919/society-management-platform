export default async function run(page) {
  await page.locator('input[name="mobile"]').fill('9800001');
  await page.locator('input[name="password"]').fill('Resident@123');
  await page.locator('button[type="submit"]').click();
  await page.waitForTimeout(1200);
  if (page.url().includes('/login')) return { loginFailed: await page.locator('body').innerText() };
  await page.goto('http://127.0.0.1:5000/resident/events', { waitUntil: 'domcontentloaded' });
  await page.reload({ waitUntil: 'domcontentloaded' });
  const options = await page.locator('#event-select option').allTextContents();
  const values = await page.locator('#event-select option').evaluateAll(xs => xs.map(x => x.value));
  const eventIds = await page.locator('#event-select option').evaluateAll(xs => xs.map(x => x.value).filter(Boolean));
  const result = { url: page.url(), options, values, empty: await page.getByText('No events yet').count() > 0 };
  for (const id of eventIds) {
    await page.goto('http://127.0.0.1:5000' + id, { waitUntil: 'domcontentloaded' });
    result[id] = { status: await page.locator('body').innerText().then(t => ({ photos: (t.match(/approved media item/g) || []).length, hasAdd: t.includes('+ Add Image / Video') })) };
  }
  return result;
}