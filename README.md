**VAT Identifier Discovery Research and PoC**

This repository contains my work for the VAT Identifier Discovery challenge.
The goal was to see how realistic it is to find UK company VAT numbers using public sources, without starting with a paid database.

**What I tried**

I tested a few different ways of finding the VAT numbers:

- Manual Google searches
- Company websites
- Python requests + BeautifulSoup
- Brave Search API
- Gemini API + Google Search
- Selenium + Google
- Endole and VAT-Search
- HMRC checker for verification

Most of them had some kind of problem. Websites often blocked automated requests, some companies did not have an obvious website, search APIs were inconsistent, and the free versions of some services were too limited for a large dataset.

The approach that worked best for me was using Selenium to search Google in a normal browser and extracting possible VAT numbers from the results.

**First test**

I tested 100 active companies with SIC code 45112, incorporated between 2014 and 2019.

The Google + Selenium search found VAT candidates for:

31 / 100 companies

I then checked the candidates with HMRC, with one important finding: a VAT number can be completely valid but still belong to the wrong company. Because of that, I also compared the company details returned by HMRC before considering a result verified.

**Second test**

I also selected 500 active companies incorporated from 2020 onwards, excluding SIC code 45112.

The same search and verification process is being used for this sample.

**Files**

    semi_auto_google_search.py
Google search using Selenium and VAT number extraction.

    hmrc_checker.py
Checks VAT candidates with HMRC.

    csv_cleaner.py
Used to prepare the Companies House data.

    tester.py
Various tests made during development.

    requirements.txt
Python packages used by the scripts.


The sample files and results are included in the repository as well.

The full Companies House dataset used for the research is not included because it is very large.

**Full research**

The detailed research, tests, failed approaches and results are in:

    VAT Identifier Discovery Research and PoC.pdf

This repository is a proof of concept, not a finished production system. The Python code was developed with AI assistance, but the decisions behind the project were mine. I chose what to test, which approaches to try, how to select the samples, how to evaluate the results, and what to do when an approach did not work.
