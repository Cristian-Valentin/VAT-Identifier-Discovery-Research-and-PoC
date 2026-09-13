import pandas as pd

columns_i_want = [
    "CompanyName",
    " CompanyNumber",
    "RegAddress.AddressLine1",
    "RegAddress.PostCode",
    "CompanyStatus",
    "IncorporationDate",
    "SICCode.SicText_1"
]

df = pd.read_csv(
    r"D:\Veridion\BasicCompanyDataAsOneFile-2026-09-01.csv",
    usecols=columns_i_want,
    low_memory=False,
    encoding="utf-8"
)

df = df.rename(columns={
    "CompanyName":"company_name",
    " CompanyNumber":"company_number",
    "RegAddress.AddressLine1":"address",
    "RegAddress.PostCode":"postcode",
    "CompanyStatus":"status",
    "IncorporationDate":"incorporation_date",
    "SICCode.SicText_1":"sic_code"
})
df["incorporation_date"] = pd.to_datetime(
    df["incorporation_date"],
    dayfirst=True,
    errors="coerce"
).dt.strftime("%Y-%m-%d")

df.to_csv(
    "companies_small.csv",
    index=False,
    encoding="utf-8"
)