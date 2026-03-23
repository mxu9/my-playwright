const { chromium } = require('playwright');

const TARGET_URL = 'https://github.com';

(async () => {
  const browser = await chromium.launch({ headless: false, slowMo: 100 });
  const page = await browser.newPage();

  try {
    // 打开 GitHub
    console.log(`正在打开 ${TARGET_URL}...`);
    await page.goto(TARGET_URL, { waitUntil: 'networkidle' });
    console.log('页面标题:', await page.title());

    // 点击搜索按钮展开搜索框
    console.log('点击搜索按钮...');
    await page.click('button[aria-label="Search or jump to…"]');
    await page.waitForTimeout(1000);

    // 在展开的搜索框中输入
    const searchInput = page.locator('#query-builder-test, input[name="query-builder-test"]').first();
    console.log('正在搜索 openclaw...');
    await searchInput.fill('openclaw');
    await searchInput.press('Enter');

    // 等待搜索结果页面加载
    await page.waitForLoadState('networkidle');
    console.log('搜索完成，页面标题:', await page.title());

    // 截图
    await page.screenshot({ path: 'C:/work/my-playwright/github-search-result.png', fullPage: true });
    console.log('截图已保存到 github-search-result.png');

    // 暂停让用户看到结果
    await page.waitForTimeout(5000);

  } catch (error) {
    console.error('错误:', error.message);
  } finally {
    await browser.close();
  }
})();