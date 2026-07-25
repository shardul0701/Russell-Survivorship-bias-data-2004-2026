const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

async function main() {
  const [url, slug] = process.argv.slice(2);
  if (!url || !slug) {
    console.error("usage: node scripts/capture_scribd_rendered.js <scribd-url> <slug>");
    process.exit(2);
  }

  const outDir = path.join("source_raw", "scribd_browser");
  fs.mkdirSync(outDir, { recursive: true });

  const browser = await chromium.launch({
    headless: false,
    executablePath: "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
    args: ["--disable-blink-features=AutomationControlled"],
  });
  const page = await browser.newPage({ viewport: { width: 1400, height: 2200 } });
  page.setDefaultTimeout(45000);
  await page.goto(url, { waitUntil: "domcontentloaded", timeout: 90000 });
  await page.waitForTimeout(8000);

  let lastHeight = 0;
  for (let i = 0; i < 70; i++) {
    await page.mouse.wheel(0, 2200);
    await page.waitForTimeout(700);
    const height = await page.evaluate(() => document.body.scrollHeight);
    if (height === lastHeight && i > 20) {
      await page.waitForTimeout(2000);
    }
    lastHeight = height;
  }

  const html = await page.content();
  const text = await page.locator("body").innerText({ timeout: 10000 }).catch(() => "");
  fs.writeFileSync(path.join(outDir, `${slug}_rendered.html`), html, "utf8");
  fs.writeFileSync(path.join(outDir, `${slug}_scrolled.txt`), text, "utf8");
  console.log("wrote", slug, "html chars", html.length, "text chars", text.length);
  await browser.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
