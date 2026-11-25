const { test, expect } = require('@playwright/test');

test('loads with labelled controls, keyboard focus, and responsive layout', async ({ page }, testInfo) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'AI Cartoon Studio 3D' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Professional Video Editing Studio' })).toBeVisible();
  await expect(page.locator('#timeline-project-name')).toBeVisible();
  await expect(page.getByLabel('Export profile')).toBeVisible();
  await expect(page.getByLabel('Upload MP4 clips')).toBeVisible();

  const missingNames = await page.locator('input:not([type="hidden"]), select, textarea').evaluateAll(controls => controls
    .filter(control => {
      const style = getComputedStyle(control);
      return style.display !== 'none' && style.visibility !== 'hidden';
    })
    .filter(control => {
      const labels = control.labels ? [...control.labels] : [];
      return !control.getAttribute('aria-label') && !control.getAttribute('aria-labelledby') && !labels.some(label => label.textContent.trim());
    })
    .map(control => control.id || control.outerHTML.slice(0, 80)));
  expect(missingNames).toEqual([]);

  const projectName = page.locator('#timeline-project-name');
  await projectName.focus();
  const focusStyle = await projectName.evaluate(element => {
    const style = getComputedStyle(element);
    return { outlineStyle: style.outlineStyle, outlineWidth: style.outlineWidth };
  });
  expect(focusStyle.outlineStyle).not.toBe('none');
  expect(focusStyle.outlineWidth).not.toBe('0px');

  await page.locator('#timeline-add-title').click();
  await page.locator('#timeline-ruler').focus();
  await page.keyboard.press('End');
  await expect(page.locator('#timeline-playhead-time')).toHaveText('00:03.00');
  await page.keyboard.press('Home');
  await expect(page.locator('#timeline-playhead-time')).toHaveText('00:00.00');

  if (testInfo.project.name === 'chromium-mobile') {
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(2);
    const ruler = await page.locator('#timeline-ruler').boundingBox();
    await page.touchscreen.tap(ruler.x + Math.min(160, ruler.width - 5), ruler.y + ruler.height / 2);
    await expect(page.locator('#timeline-playhead-time')).not.toHaveText('00:00.00');
    const touchTargets = await page.locator('.professional-timeline-toolbar button').evaluateAll(buttons => buttons.map(button => button.getBoundingClientRect().height));
    expect(touchTargets.every(height => height >= 44)).toBeTruthy();
  }

  expect(await page.locator('[role="dialog"]').count()).toBe(0);
});
