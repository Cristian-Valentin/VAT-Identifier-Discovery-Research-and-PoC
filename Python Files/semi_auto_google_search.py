import re
import time
import random
from pathlib import Path
from urllib.parse import quote_plus

import pandas as pd
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import WebDriverException


# ------------------------------------------------------------
# FILES
# ------------------------------------------------------------

INPUT_FILE = Path(
    r"D:\Veridion\500_random_companies_from_2020_excluding_45112.csv"
)

OUTPUT_FILE = Path(
    r"D:\Veridion\google_selenium_results_500.xlsx"
)


# ------------------------------------------------------------
# VAT REGEX
# ------------------------------------------------------------

VAT_PATTERN = re.compile(
    r"\b(?:GB\s*)?\d{3}\s?\d{3}\s?\d{3}\b",
    re.IGNORECASE
)


# ------------------------------------------------------------
# SELENIUM
# ------------------------------------------------------------

def create_driver():

    options = Options()

    # Keep the browser visible.
    options.add_argument("--start-maximized")
    options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(options=options)

    driver.set_page_load_timeout(30)

    return driver


# ------------------------------------------------------------
# VAT CLEANING
# ------------------------------------------------------------

def normalize_vat(value):
    """
    Convert things like:

        369 855 041
        GB369855041
        GB 369 855 041

    into:

        GB369855041
    """

    digits = re.sub(r"\D", "", value)

    if len(digits) == 9:
        return "GB" + digits

    return None


def extract_vats(text):

    matches = VAT_PATTERN.findall(text)

    vats = []

    for match in matches:

        vat = normalize_vat(match)

        if vat and vat not in vats:
            vats.append(vat)

    return vats


# ------------------------------------------------------------
# GOOGLE SEARCH
# ------------------------------------------------------------

def search_google(driver, company_name, company_number):

    query = f'"{company_name}" "{company_number}" VAT'

    search_url = (
        "https://www.google.com/search?q="
        + quote_plus(query)
    )

    print(f"  Google query: {query}")

    try:

        driver.get(search_url)

        # Give Google/Gemini enough time to finish rendering.
        time.sleep(random.uniform(10, 13))

        # Read visible page text.
        page_text = driver.find_element(
            By.TAG_NAME,
            "body"
        ).text.lower()

        # Detect Google's unusual-traffic / human verification page.
        if (
            "our systems have detected unusual traffic from your computer network"
            in page_text
            or "unusual traffic" in page_text
            or "not a robot" in page_text
            or "verify you are human" in page_text
        ):

            print()
            print("    Google unusual-traffic verification detected.")
            print(
                "    Complete the verification in Chrome, "
                "then press ENTER to continue..."
            )

            input()

            # Give Google time to finish after verification.
            time.sleep(random.uniform(6, 8))

        # Read the final rendered page.
        html = driver.page_source

        soup = BeautifulSoup(
            html,
            "html.parser"
        )

        text = soup.get_text(
            " ",
            strip=True
        )

        vats = extract_vats(text)

        return {
            "status": "OK",
            "query": query,
            "vat_candidates": vats,
            "page_text": text,
            "error": ""
        }

    except WebDriverException as e:

        return {
            "status": "ERROR",
            "query": query,
            "vat_candidates": [],
            "page_text": "",
            "error": str(e)[:500]
        }


# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------

def main():

    # --------------------------------------------------------
    # LOAD XLSX
    # --------------------------------------------------------

    df = pd.read_csv(INPUT_FILE)

    print("Columns found:")
    print(list(df.columns))
    print()

    # First run = 100 companies / 500 next
    df = df.head(500).copy()

    print(f"Companies loaded: {len(df)}")
    print()

    # --------------------------------------------------------
    # START BROWSER
    # --------------------------------------------------------

    driver = create_driver()

    results = []

    try:

        # ----------------------------------------------------
        # LOAD GOOGLE FIRST
        # ----------------------------------------------------

        print()
        print("Loading Google...")

        driver.get("https://www.google.com/")

        time.sleep(3)

        input(
            "Google should now be loaded. "
            "If you see a verification page, complete it. "
            "Press ENTER when you're ready to start the searches..."
        )

        print()

        # ----------------------------------------------------
        # START COMPANY SEARCHES
        # ----------------------------------------------------

        for i, row in df.iterrows():

            company_name = str(
                row["company_name"]
            ).strip()

            company_number = str(
                row["company_number"]
            ).strip()

            print(
                f"[{i + 1}/{len(df)}] "
                f"{company_name}"
            )

            print(
                f"  Company number: "
                f"{company_number}"
            )

            result = search_google(
                driver,
                company_name,
                company_number
            )

            vats = result["vat_candidates"]

            print(
                f"  Status: {result['status']}"
            )

            print(
                f"  VAT candidates: "
                f"{', '.join(vats) if vats else 'none'}"
            )

            # ------------------------------------------------
            # SAVE RESULT
            # ------------------------------------------------

            results.append({
                "company_name": company_name,
                "company_number": company_number,
                "google_query": result["query"],
                "search_status": result["status"],
                "vat_candidates": "|".join(vats),
                "error": result["error"]
            })

            # Save after every company
            pd.DataFrame(results).to_excel(
                OUTPUT_FILE,
                index=False
            )

            print(
                f"  Progress saved "
                f"({len(results)} companies)"
            )

            print()

            # Short delay after saving.
            time.sleep(
                random.uniform(1, 2)
            )

    finally:

        driver.quit()

    # --------------------------------------------------------
    # FINAL SAVE
    # --------------------------------------------------------

    results_df = pd.DataFrame(results)

    results_df.to_excel(
        OUTPUT_FILE,
        index=False
    )

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    total = len(results_df)

    companies_with_candidate = (
        results_df["vat_candidates"]
        .astype(str)
        .str.len()
        .gt(0)
        .sum()
    )

    successful_searches = (
        results_df["search_status"]
        == "OK"
    ).sum()

    print("====================================")
    print("Finished.")
    print(
        f"Companies searched: {total}"
    )
    print(
        f"Successful page loads: "
        f"{successful_searches}"
    )
    print(
        f"Companies with VAT candidate: "
        f"{companies_with_candidate}"
    )
    print(
        f"Results saved to: {OUTPUT_FILE}"
    )
    print("====================================")


# ------------------------------------------------------------
# RUN
# ------------------------------------------------------------

if __name__ == "__main__":
    main()