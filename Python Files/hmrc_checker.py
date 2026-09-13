import re
import time
import random
from pathlib import Path
from difflib import SequenceMatcher

import pandas as pd

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys


# ------------------------------------------------------------
# FILES
# ------------------------------------------------------------

GOOGLE_RESULTS_FILE = Path(
    r"D:\Veridion\google_selenium_results_500.xlsx"
)

SOURCE_COMPANIES_FILE = Path(
    r"D:\Veridion\500_random_companies_from_2020_excluding_45112.xlsx"
)

OUTPUT_FILE = Path(
    r"D:\Veridion\google_selenium_results_500.xlsx"
)


# ------------------------------------------------------------
# HMRC
# ------------------------------------------------------------

HMRC_URL = (
    "https://www.tax.service.gov.uk/"
    "check-vat-number/enter-vat-details"
)


# ------------------------------------------------------------
# SELENIUM
# ------------------------------------------------------------

def create_driver():

    options = Options()

    options.add_argument("--start-maximized")
    options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(options=options)

    driver.set_page_load_timeout(30)

    return driver


# ------------------------------------------------------------
# VAT CLEANING
# ------------------------------------------------------------

def clean_vat(vat):

    digits = re.sub(r"\D", "", str(vat))

    if len(digits) == 9:
        return digits

    return None


# ------------------------------------------------------------
# TEXT NORMALISATION
# ------------------------------------------------------------

def normalize_text(text):

    if text is None:
        return ""

    text = str(text).upper()

    # Replace punctuation with spaces
    text = re.sub(r"[^A-Z0-9 ]", " ", text)

    # Collapse repeated whitespace
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def normalize_name(name):

    text = normalize_text(name)

    # Remove common company suffixes.
    suffixes = [
        " LIMITED",
        " LTD",
        " PUBLIC LIMITED COMPANY",
        " PLC",
        " LLP"
    ]

    changed = True

    while changed:

        changed = False

        for suffix in suffixes:

            if text.endswith(suffix):

                text = text[:-len(suffix)].strip()
                changed = True
                break

    return text


def names_match(target_name, hmrc_name):

    target = normalize_name(target_name)
    hmrc = normalize_name(hmrc_name)

    if not target or not hmrc:
        return False

    if target == hmrc:
        return True

    # Allow one name to contain the other.
    if target in hmrc or hmrc in target:
        return True

    # Fuzzy comparison for small wording differences.
    similarity = SequenceMatcher(
        None,
        target,
        hmrc
    ).ratio()

    return similarity >= 0.85


def postcode_match(target_postcode, hmrc_address):

    target = normalize_text(target_postcode)

    address = normalize_text(hmrc_address)

    if not target or not address:
        return False

    return target in address


# ------------------------------------------------------------
# HMRC RESULT EXTRACTION
# ------------------------------------------------------------

def extract_hmrc_details(body_text):

    lines = [
        line.strip()
        for line in body_text.splitlines()
        if line.strip()
    ]

    body_lower = body_text.lower()

    # --------------------------------------------------------
    # INVALID
    # --------------------------------------------------------

    if "invalid uk vat number" in body_lower:

        return {
            "status": "INVALID",
            "business": "",
            "address": ""
        }

    # --------------------------------------------------------
    # VALID
    # --------------------------------------------------------

    if "valid uk vat number" not in body_lower:

        return {
            "status": "NO RESULT",
            "business": "",
            "address": ""
        }

    business = ""
    address = ""

    # Find the sections in the plain text.
    for i, line in enumerate(lines):

        line_lower = line.lower()

        if line_lower == "registered business name":

            if i + 1 < len(lines):
                business = lines[i + 1]

        if line_lower == "registered business address":

            address_lines = []

            for next_line in lines[i + 1:]:

                lower = next_line.lower()

                # Stop after the actual address section.
                if lower in [
                    "search completed",
                    "print or save this page",
                    "check another vat number",
                    "what did you think of this service?",
                    "is this page not working properly?",
                    "support links",
                    "cookies",
                    "accessibility statement",
                    "privacy",
                    "terms and conditions",
                    "help"
                ]:
                    break

                address_lines.append(next_line)

                # HMRC ends the address with the country code.
                if next_line.upper() == "GB":
                    break

            address = " ".join(address_lines)

    return {
        "status": "VALID",
        "business": business,
        "address": address
    }


# ------------------------------------------------------------
# HMRC CHECK
# ------------------------------------------------------------

def check_hmrc(
    driver,
    vat,
    target_name,
    target_postcode
):

    vat_digits = clean_vat(vat)

    if not vat_digits:

        return {
            "result": "INVALID FORMAT",
            "hmrc_business": "",
            "hmrc_address": ""
        }

    try:

        # We allow a few attempts because HMRC sometimes
        # does not produce the result on the first submission.
        for attempt in range(3):

            # Always start from the checker page.
            driver.get(HMRC_URL)

            time.sleep(3)

            vat_input = driver.find_element(
                By.ID,
                "target"
            )

            vat_input.clear()
            vat_input.send_keys(vat_digits)
            vat_input.send_keys(Keys.ENTER)

            # Give HMRC time to respond.
            time.sleep(5)

            body_text = driver.find_element(
                By.TAG_NAME,
                "body"
            ).text

            body_lower = body_text.lower()

            # ------------------------------------------------
            # RATE LIMIT
            # ------------------------------------------------

            if (
                "too many requests" in body_lower
                or "too many attempts" in body_lower
                or "429" in body_lower
            ):

                print(
                    "      HMRC rate limit detected."
                )

                if attempt < 2:

                    cooldown = random.uniform(8, 12)

                    print(
                        f"      Waiting "
                        f"{cooldown:.1f} seconds..."
                    )

                    time.sleep(cooldown)

                    continue

                return {
                    "result": "RATE LIMITED",
                    "hmrc_business": "",
                    "hmrc_address": ""
                }

            # ------------------------------------------------
            # EXTRACT RESULT
            # ------------------------------------------------

            details = extract_hmrc_details(
                body_text
            )

            # ------------------------------------------------
            # INVALID
            # ------------------------------------------------

            if details["status"] == "INVALID":

                return {
                    "result": "FALSE POSITIVE",
                    "hmrc_business": "",
                    "hmrc_address": ""
                }

            # ------------------------------------------------
            # VALID
            # ------------------------------------------------

            if details["status"] == "VALID":

                hmrc_business = details["business"]
                hmrc_address = details["address"]

                name_ok = names_match(
                    target_name,
                    hmrc_business
                )

                postcode_ok = postcode_match(
                    target_postcode,
                    hmrc_address
                )

                print(
                    f"      HMRC business: "
                    f"{hmrc_business}"
                )

                print(
                    f"      HMRC address: "
                    f"{hmrc_address}"
                )

                print(
                    f"      Name match: "
                    f"{name_ok}"
                )

                print(
                    f"      Postcode match: "
                    f"{postcode_ok}"
                )

                if name_ok and postcode_ok:
                    return {
                        "result": "VERIFIED",
                        "hmrc_business": hmrc_business,
                        "hmrc_address": hmrc_address
                    }

                return {
                    "result": "NEEDS CHECKING",
                    "hmrc_business": hmrc_business,
                    "hmrc_address": hmrc_address
                }

        return {
            "result": "NO RESULT",
            "hmrc_business": "",
            "hmrc_address": ""
        }

    except Exception as e:

        print(
            f"      HMRC error: "
            f"{str(e)[:300]}"
        )

        return {
            "result": "ERROR",
            "hmrc_business": "",
            "hmrc_address": ""
        }


# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------

def main():

    # --------------------------------------------------------
    # LOAD GOOGLE RESULTS
    # --------------------------------------------------------

    df = pd.read_excel(GOOGLE_RESULTS_FILE)

    source_df = pd.read_excel(
        SOURCE_COMPANIES_FILE,
        usecols=[
            "company_number",
            "address",
            "postcode"
        ]
    )

    # Build lookups from the original company sample.
    address_lookup = dict(
        zip(
            source_df["company_number"].astype(str),
            source_df["address"]
        )
    )

    postcode_lookup = dict(
        zip(
            source_df["company_number"].astype(str),
            source_df["postcode"]
        )
    )

    # Make sure company numbers are strings.
    df["company_number"] = (
        df["company_number"]
        .astype(str)
        .str.strip()
    )

    # Add the original company details under new column names.
    df["source_address"] = df["company_number"].map(
        address_lookup
    )

    df["source_postcode"] = df["company_number"].map(
        postcode_lookup
    )

    print("Columns found:")
    print(list(df.columns))
    print()

    # Create result columns if needed.
    if "hmrc_vat" not in df.columns:

        df["hmrc_vat"] = pd.Series(
            pd.NA,
            index=df.index,
            dtype="string"
        )

    else:

        df["hmrc_vat"] = df["hmrc_vat"].astype(
            "string"
        )

    if "hmrc_result" not in df.columns:

        df["hmrc_result"] = pd.Series(
            pd.NA,
            index=df.index,
            dtype="string"
        )

    else:

        df["hmrc_result"] = df["hmrc_result"].astype(
            "string"
        )

    if "hmrc_business" not in df.columns:

        df["hmrc_business"] = pd.Series(
            pd.NA,
            index=df.index,
            dtype="string"
        )

    else:

        df["hmrc_business"] = df["hmrc_business"].astype(
            "string"
        )

    if "hmrc_address" not in df.columns:

        df["hmrc_address"] = pd.Series(
            pd.NA,
            index=df.index,
            dtype="string"
        )

    else:

        df["hmrc_address"] = df["hmrc_address"].astype(
            "string"
        )

    # --------------------------------------------------------
    # START BROWSER
    # --------------------------------------------------------

    driver = create_driver()

    try:

        print()
        print("Loading HMRC checker...")

        driver.get(HMRC_URL)

        time.sleep(3)

        print("HMRC checker loaded.")
        print()

        # ----------------------------------------------------
        # PROCESS COMPANIES
        # ----------------------------------------------------

        for i, row in df.iterrows():

            candidates = row["vat_candidates"]

            # Skip companies with no candidate.
            if (
                pd.isna(candidates)
                or str(candidates).strip() == ""
            ):
                continue

            # Skip already completed rows.
            if (
                not pd.isna(row["hmrc_result"])
                and str(row["hmrc_result"]).strip() != ""
            ):
                continue

            vat_list = [
                x.strip()
                for x in str(candidates).split("|")
                if x.strip()
            ]

            # We currently expect one candidate per company.
            vat = vat_list[0]

            company_name = str(
                row["company_name"]
            ).strip()

            postcode = str(
                row["source_postcode"]
            ).strip()

            print(
                f"[{i + 1}/{len(df)}] "
                f"{company_name}"
            )

            print(
                f"  Checking HMRC: {vat}"
            )

            result = check_hmrc(
                driver,
                vat,
                company_name,
                postcode
            )

            print(
                f"    Result: "
                f"{result['result']}"
            )

            # ------------------------------------------------
            # SAVE RESULT
            # ------------------------------------------------

            df.at[i, "hmrc_vat"] = vat

            df.at[i, "hmrc_result"] = (
                result["result"]
            )

            df.at[i, "hmrc_business"] = (
                result["hmrc_business"]
            )

            df.at[i, "hmrc_address"] = (
                result["hmrc_address"]
            )

            # Save after every check.
            df.to_excel(
                OUTPUT_FILE,
                index=False
            )

            print("  Progress saved.")
            print()

            # Small pause between companies.
            time.sleep(
                random.uniform(2, 4)
            )

    finally:

        driver.quit()

    # --------------------------------------------------------
    # FINAL SUMMARY
    # --------------------------------------------------------

    print("====================================")
    print("HMRC verification finished.")

    print(
        f"Verified: "
        f"{(df['hmrc_result'] == 'VERIFIED').sum()}"
    )

    print(
        f"False positives: "
        f"{(df['hmrc_result'] == 'FALSE POSITIVE').sum()}"
    )

    print(
        f"Rate limited: "
        f"{(df['hmrc_result'] == 'RATE LIMITED').sum()}"
    )

    print(
        f"Errors: "
        f"{(df['hmrc_result'] == 'ERROR').sum()}"
    )

    print(
        f"Results saved to: "
        f"{OUTPUT_FILE}"
    )

    print("====================================")


# ------------------------------------------------------------
# RUN
# ------------------------------------------------------------

if __name__ == "__main__":
    main()