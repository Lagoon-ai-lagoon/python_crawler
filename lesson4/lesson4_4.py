from playwright.sync_api import sync_playwright
import os

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False,slow_mo=500)
       
        
        page = browser.new_page()
       
         
        current_dir = os.path.dirname(os.path.abspath(__file__))
        html_file = os.path.join(current_dir,"login_demo.html")
        #print(f"file://{html_file}")
        page.goto(f"file://{html_file}")
        
        page.fill("#username","admin")
        page.fill("#password","password")
        page.click("#login-button")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(5000)


        browser.close()


if __name__ == "__main__":
    main()