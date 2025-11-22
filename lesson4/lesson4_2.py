from playwright.sync_api import sync_playwright



def main():
    with sync_playwright() as p:
        print("建立資源")
    print("釋放資源")



if __name__ == "__main__":
    main()