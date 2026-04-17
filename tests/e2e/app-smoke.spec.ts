import { test, expect } from "@playwright/test";

test("smoke test placeholder", async ({ page }) => {
  await page.goto("http://localhost:3000");
  await expect(page).toHaveURL(/localhost/);
});
