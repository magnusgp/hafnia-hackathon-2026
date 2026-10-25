import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import { chromium } from "playwright";
const base = process.env.REVIEW_URL || "http://127.0.0.1:4174";
const output = new URL("../../runs/product-integration/", import.meta.url);
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ channel: "msedge", headless: true });
const results = [];
try {
  for (const [width, height] of [
    [1440, 900],
    [1920, 1080],
  ]) {
    const page = await browser.newPage({ viewport: { width, height } });
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.goto(`${base}/#/monitoring`, { waitUntil: "networkidle" });
    const response = await page.request.get(`${base}/api/incidents`);
    assert.equal(response.status(), 200);
    const { records, cameras } = await response.json();
    assert.ok(
      records.length >= 2,
      "Import both real retrospective records before checking",
    );
    assert.equal(
      await page.locator(".incident-list article").count(),
      records.length,
    );
    assert.equal(await page.locator("tbody tr").count(), cameras.length);
    await page
      .getByRole("textbox", { name: "Search cameras" })
      .fill(cameras[0].name.replaceAll("_", " "));
    assert.equal(await page.locator("tbody tr").count(), 1);
    await page.getByRole("textbox", { name: "Search cameras" }).fill("");
    await page.evaluate(() => document.fonts.ready);
    await page.screenshot({
      path: new URL(
        `monitoring-${width}x${height}.png`,
        output,
      ).pathname.replace(/^\/(\w:)/, "$1"),
    });
    for (const record of records) {
      await page.goto(`${base}/#/monitoring`, { waitUntil: "networkidle" });
      await page.locator(`a[href="#/investigation/${record.id}"]`).click();
      await page.locator(".frame img").evaluate((img) => img.decode());
      assert.equal(
        await page.locator(".camera-name").innerText(),
        record.camera,
      );
      assert.ok(page.url().endsWith(record.id));
      const data = await (
        await page.request.get(`${base}/api/incidents/${record.id}`)
      ).json();
      assert.equal(data.id, record.id);
      assert.ok(
        (await page.locator(".frame img").getAttribute("src")).includes(
          record.id,
        ),
      );
      await page.screenshot({
        path: new URL(
          `${record.id}-${width}x${height}.png`,
          output,
        ).pathname.replace(/^\/(\w:)/, "$1"),
      });
      await page.getByRole("checkbox", { name: "Draft region" }).check();
      assert.equal(await page.locator(".frame polygon").count(), 1);
      await page.getByRole("slider").fill("0");
      assert.equal(
        await page.locator(".frame rect").count(),
        data.frames[0].box ? 1 : 0,
      );
      await page
        .getByRole("button", { name: "Hold for geometry review" })
        .click();
      await page.getByRole("status").waitFor();
      await page.locator(".provenance>summary").click();
      await page.locator(".provenance dl").waitFor();
      assert.equal(
        await page.evaluate(
          () => document.documentElement.scrollWidth > innerWidth,
        ),
        false,
      );
      results.push({
        width,
        height,
        id: record.id,
        camera: record.camera,
        source: data.evidenceKind,
        frames: data.frames.length,
        errors: [...errors],
      });
    }
    await page.goto(`${base}/#/investigation/${"0".repeat(24)}`, {
      waitUntil: "networkidle",
    });
    await page.getByRole("heading", { name: "Evidence unavailable" }).waitFor();
    assert.deepEqual(errors, []);
    await page.close();
  }
  await writeFile(
    new URL("checks.json", output),
    JSON.stringify(results, null, 2),
  );
  console.log(JSON.stringify(results, null, 2));
} finally {
  await browser.close();
}
