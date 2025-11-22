from playwright.sync_api import sync_playwright
import os

def demo_1_delayed_element(page):
    print(page)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False,slow_mo=500)
        page = browser.new_page()
        current_dir = os.path.dirname(os.path.abspath(__file__))
        html_file = os.path.join(current_dir,"waiting_demo.html")
        #print(f"file://{html_file}")
        page.goto(f"file://{html_file}")
        demo_1_delayed_element(page)

        
        page.wait_for_timeout(5000)
        browser.close()


if __name__ == "__main__":
    main()