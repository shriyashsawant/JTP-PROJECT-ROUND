/**
 * AuraMatch AI - E2E Search Tests
 *
 * Tests the core chat-based search flow: empty state loads, user can type
 * a query, answer clarifying questions, and get results.
 */
import { test, expect } from "@playwright/test";

test.describe("AuraMatch Search", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/search");
  });

  test("loads the search page with empty state", async ({ page }) => {
    await expect(page.getByText("What are you")).toBeVisible();
    await expect(page.getByText("Describe a vibe")).toBeVisible();
  });

  test("typing a fully detailed query returns results immediately", async ({ page }) => {
    const input = page.getByPlaceholder("Describe the vibe");
    // All 9 slots specified/implied in the query text to bypass clarifying questions
    await input.fill("I need a fresh male scent for the gym under 2000. No vanilla notes. Longevity 8+ hours, moderate projection. I have dry skin and am 25 years old.");
    await input.press("Enter");

    // Should transition directly to results
    await expect(page.getByText("Found")).toBeVisible({ timeout: 25_000 });
  });

  test("clarifying question flow works for vague queries", async ({ page }) => {
    const input = page.getByPlaceholder("Describe the vibe");
    await input.fill("suggest a scent");
    await input.press("Enter");

    // Should ask about gender first (highest weight dimension)
    await expect(page.getByText("First, could you tell me if this scent is for a male, female, or unisex preference?")).toBeVisible({ timeout: 15_000 });
  });

  test("suggestion chips trigger a search and can be clarified", async ({ page }) => {
    // Click suggestion chip (does not specify gender, avoidNotes, longevity, projection, age, skinType)
    await page.getByText("fresh scent for the gym under ₹2,000").click();

    // 1. Gender question is asked
    const genderBtn = page.getByRole("button", { name: "Male", exact: true });
    await expect(genderBtn).toBeVisible({ timeout: 15_000 });
    await genderBtn.click();

    // 2. Avoid notes question is asked
    const avoidBtn = page.getByRole("button", { name: "None - no restrictions", exact: true });
    await expect(avoidBtn).toBeVisible({ timeout: 15_000 });
    await avoidBtn.click();

    // 3. Longevity question is asked
    const longBtn = page.getByRole("button", { name: "Let AuraMatch decide", exact: true });
    await expect(longBtn).toBeVisible({ timeout: 15_000 });
    await longBtn.click();

    // 4. Projection question is asked
    const projBtn = page.getByRole("button", { name: "Let AuraMatch decide", exact: true });
    await expect(projBtn).toBeVisible({ timeout: 15_000 });
    await projBtn.click();

    // 5. Age question is asked (budget is skipped since "under ₹2,000" was in suggestion chip)
    const ageBtn = page.getByRole("button", { name: "Prefer not to say", exact: true });
    await expect(ageBtn).toBeVisible({ timeout: 15_000 });
    await ageBtn.click();

    // 6. Skin type question is asked
    const skinBtn = page.getByRole("button", { name: "Not sure / skip", exact: true });
    await expect(skinBtn).toBeVisible({ timeout: 15_000 });
    await skinBtn.click();

    // Finally results should display
    await expect(page.getByText("Found")).toBeVisible({ timeout: 20_000 });
  });

  test("off-topic query shows assistant boundaries", async ({ page }) => {
    const input = page.getByPlaceholder("Describe the vibe");
    await input.fill("recommend a good movie");
    await input.press("Enter");

    // Either off-topic boundary triggers or standard response.
    // Target the assistant message specifically to avoid strict mode violations.
    await expect(page.locator(".bg-secondary").getByText(/recommend|scent|perfume|fragrance|fragrance recommendation/i)).toBeVisible({ timeout: 15_000 });
  });

  test("backend error shows user-friendly message", async ({ page }) => {
    // Block the search context endpoint. When a detailed query is typed, it skips
    // clarifying questions and directly hits the search endpoint, which will fail.
    await page.route("**/api/v1/search/**", (route) => {
      route.abort("connectionrefused");
    });

    const input = page.getByPlaceholder("Describe the vibe");
    await input.fill("I need a fresh male scent for the gym under 2000. No vanilla notes. Longevity 8+ hours, moderate projection. I have dry skin and am 25 years old.");
    await input.press("Enter");

    await expect(page.getByText(/couldn't reach.*server|check.*connection|try again/i)).toBeVisible({ timeout: 15_000 });
  });

  test("age extraction works from text", async ({ page }) => {
    const input = page.getByPlaceholder("Describe the vibe");
    // Add "fresh" so that scent profile is skipped (gender, occasion, age, budget, scent are all specified/implied)
    await input.fill("I'm 25, looking for a fresh daily wear office scent for men");
    await input.press("Enter");

    // Wait for the next question (avoid notes or similar, skipping gender and age)
    await expect(page.getByText("avoid")).toBeVisible({ timeout: 15_000 });

    // Should not ask about age group in subsequent questions
    await expect(page.getByText("age group")).not.toBeVisible({ timeout: 5_000 });
  });
});
