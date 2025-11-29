import os
from playwright.sync_api import sync_playwright






def main():
    path = "https://www.thsrc.com.tw/"

    with sync_playwright() as p:

        # 啟動瀏覽器
        browser = p.chromium.launch(headless=False, slow_mo=500)
        
        # 打開新頁面
        page = browser.new_page()
        
        # 導航到HTML文件
        page.goto(path)

        # 等待頁面載入完成
        page.wait_for_load_state("domcontentloaded")

        # 等待3秒鐘以便觀察效果
        page.wait_for_timeout(3000)

        browser.close()
    


if __name__ == "__main__":
    main()