from playwright.sync_api import sync_playwright

from time import sleep

def main():
    with sync_playwright() as p:
        
        browser = p.chromium.launch(headless=False)

        print(type(browser))

        page = browser.new_page()

        page.goto("https://www.google.com")
        print(page.title())

        sleep(20)

        browser.close()

        print("建立資源")
    print("釋放資源")


#12
if __name__ == "__main__":
    main()

