const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
  const page = await context.newPage();

  await page.goto('https://resva.readymode.com/');
  await page.waitForSelector("input[name='login_account']", { timeout: 15000 });
  await page.waitForTimeout(2000);
  await page.fill("input[name='login_account']", 'Auditing AI');
  await page.fill("input[name='login_password']", '55f^szxM6V');
  const cb = page.locator('#login_as_admin');
  if (!(await cb.isChecked())) await cb.check();
  await page.click("input[type='submit']");
  await page.waitForTimeout(3000);

  // Find and print all buttons/inputs on page
  const buttons = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('input, button, a')).map(el => ({
      tag: el.tagName,
      type: el.type || '',
      value: el.value || '',
      text: el.innerText || '',
      className: el.className || '',
      id: el.id || '',
    })).filter(el => el.value || el.text);
  });
  console.log('Clickable elements after submit:');
  buttons.forEach(b => console.log(JSON.stringify(b)));

  await browser.close();
})();
