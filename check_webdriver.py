from selenium import webdriver
from selenium.webdriver.chrome.service import Service
import traceback
import sys

print(f"Python version: {sys.version}")
print(f"Selenium version: {webdriver.__version__}")

try:
    print("Attempting to initialize Chrome WebDriver...")
    driver = webdriver.Chrome()
    print("SUCCESS: Chrome WebDriver initialized successfully!")
    print(f"Chrome Driver version: {driver.capabilities['chrome']['chromedriverVersion']}")
    print(f"Chrome Browser version: {driver.capabilities['browserVersion']}")
    driver.quit()
    print("WebDriver closed properly.")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
    print("\nDetailed traceback:")
    traceback.print_exc()
    print("\nPossible issues:")
    print("1. Chrome browser not installed")
    print("2. WebDriver not in PATH or incompatible with Chrome version")
    print("3. Permission issues or antivirus blocking WebDriver")

