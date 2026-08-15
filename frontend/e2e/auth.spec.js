import { test, expect } from '@playwright/test';

test.describe('Authentication & Protected Routes Flow', () => {
  test.beforeEach(async ({ page }) => {
    // Intercept API calls and return mock data to prevent ECONNREFUSED proxy errors
    await page.route('**/api/v1/sessions/years', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
    });
    await page.route('**/api/v1/sessions/', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
    });
  });

  test('should verify login modal lifecycle and protected route hiding', async ({ page }) => {
    // 1. Visit landing page
    await page.goto('/');

    // Verify main dashboard or header elements load
    await expect(page).toHaveTitle(/F1 Telemetry/i);
    await expect(page.locator('text=F1 Telemetry & Strategy Platform')).toBeVisible();

    // 2. Verify that the restricted page "Platform Internals" is NOT visible in the sidebar when signed out
    const platformInternalsBtn = page.locator('text=Platform Internals');
    await expect(platformInternalsBtn).not.toBeVisible();

    // 3. Click the header "Sign In" button to open the Clerk login modal
    const headerSignInBtn = page.locator('header button:has-text("Sign In")');
    await expect(headerSignInBtn).toBeVisible();
    await headerSignInBtn.click();

    // Verify that the Auth Modal opens containing Clerk's login components
    await expect(page.locator('text=Create Account')).toBeVisible();
    // Clerk's standard sign in element (email input) can be detected
    await expect(page.locator('input[type="email"], input[name="identifier"]')).toBeVisible();

    // 4. Test tab switching in the Auth Modal (Sign In -> Create Account)
    const createAccountTab = page.locator('button:has-text("Create Account")');
    await createAccountTab.click();
    
    // Tab switcher shows "Sign In" option inside the modal
    const modalSignInTab = page.locator('button:has-text("Sign In")').nth(1);
    await expect(modalSignInTab).toBeVisible();

    // 5. Test closing the Auth Modal
    const closeBtn = page.locator('button:has-text("✕ Close")');
    await expect(closeBtn).toBeVisible();
    await closeBtn.click();

    // Verify modal is closed (Clerk components are no longer in the DOM)
    await expect(page.locator('input[type="email"]')).not.toBeVisible();
  });
});
