import os
from pathlib import Path
from dotenv import load_dotenv
import yaml
import pandas as pd

from summary_helpers import get_xarray, plot_xarray, LONG_ALPHABETIC

_ = load_dotenv("/opt/bot-expenses/bot-expenses.env")

DATA_DIR: Path = Path(os.environ.get("DATA_DIR"))
PLOTS_DIR: Path = Path(os.environ.get("PLOTS_DIR"))
CATEGORIES_FILE: str = os.environ.get("CATEGORIES_FILE")

with open(CATEGORIES_FILE, "r") as file:
    CATEGORIES: dict[str, list[str] | str] = yaml.safe_load(file)


def process_caixabank(filename: Path) -> pd.DataFrame:
    df = pd.read_csv(filename, sep=";", skiprows=2, decimal=",")

    if "Amount" in df:
        amount = "Amount"
        balance = "Available balance"
        date = "Date"
        concept = "Concept"
    elif "Import" in df:
        amount = "Import"
        balance = "Saldo disponible"
        date = "Data"
        concept = "Concepte"
    else:
        raise ValueError("Language of CaixaBank file is not catalan or english")

    # create column specifying bank
    df["bank"] = "CaixaBank"
    # convert "Import" and "Saldo disponible" into floats
    df[amount] = df[amount].apply(
        lambda x: float(x.replace(".", "").replace(",", ".").replace("EUR", ""))
    )
    df[balance] = df[balance].apply(
        lambda x: float(x.replace(".", "").replace(",", ".").replace("EUR", ""))
    )
    # convert "Data" from DD/MM/YYYY to YYYYMMDD
    df[date] = df[date].apply(lambda x: int("".join(x.split("/")[::-1])))

    df.rename(
        columns={
            concept: "description",
            date: "date",
            amount: "amount",
            balance: "balance",
        },
        inplace=True,
    )
    df = df[["date", "amount", "balance", "bank", "description"]]

    return df


def process_abn_amro(filename: Path) -> tuple[pd.DataFrame, list[str]]:
    headers = [
        "accountNumber",
        "mutationcode",
        "transactiondate",
        "startsaldo",
        "endsaldo",
        "valuedate",
        "amount",
        "description",
    ]
    df = pd.read_csv(filename, sep="\t", header=None, names=headers, decimal=",")
    warnings: list[str] = []

    # checks
    account_numbers = [104989904, 147785936]
    if set(df["accountNumber"]) > set(account_numbers):
        warnings.append("Different account number found in ABN AMRO file")
    currency = "EUR"
    if not (df["mutationcode"] == currency).all():
        warnings.append("Non Euro currency found in ABN AMRO file")

    add_deposit = False
    if 147785936 not in set(df["accountNumber"]):
        add_deposit = True

    df.rename(
        columns={
            "valuedate": "date",
            "endsaldo": "balance",
            "accountNumber": "bank",
        },
        inplace=True,
    )
    df.replace(
        {"bank": {104989904: "ABN AMRO", 147785936: "ABN AMRO Savings"}}, inplace=True
    )
    df.drop(
        labels=["mutationcode", "transactiondate", "startsaldo"],
        axis=1,
        inplace=True,
    )
    df = df[["date", "amount", "balance", "bank", "description"]]

    if add_deposit:
        date = filename.name.split("_")[0]
        df.loc[len(df)] = [
            int(date.replace("-", "") + "01"),
            0.00,
            40_000.00,
            "ABN AMRO Savings",
            "Deposit at ABN AMRO Savings",
        ]

    return df, warnings


def get_category(string: str) -> str:
    categories_found: list[str] = []
    for key, words in CATEGORIES.items():
        if isinstance(words, str):
            words = [words]

        for word in words:
            if word.lower() in string.lower():
                categories_found.append(key)
                break

    if len(categories_found) > 1:
        raise ValueError(
            f"ERROR: more than one category found:\n{string}\n{categories_found}"
        )
    elif len(categories_found) == 1:
        return categories_found[0]
    return "unknown"


def process_expenses(month: str) -> tuple[list[str], list[str]]:
    df_caixa = process_caixabank(DATA_DIR / f"{month}_caixa.csv")
    df_abn, warnings_abn = process_abn_amro(DATA_DIR / f"{month}_ABN.txt")
    df = pd.concat([df_abn, df_caixa], ignore_index=True)

    # create empty column for categories
    df["category"] = ""

    # classify transactions
    for k, description in enumerate(df["description"]):
        category = get_category(description)
        if df.at[k, "category"] != "":
            df.at[k, "category"] += " " + category
        else:
            df.at[k, "category"] += category

    df.sort_values("category", inplace=True)

    # get warnings
    warnings = warnings_abn
    start_month = int(month.replace("-", "") + "00")
    if not (df["date"] >= start_month).all():
        warnings.append("Previous month transaction found")
    if not (df["date"] < start_month + 100).all():
        warnings.append("Next month transaction found")
    if not (df["category"] == "salary").any():
        warnings.append("Salary not found")
    if not (df["category"] == "rent").any():
        warnings.append("Rent not found")

    threshold = 100
    if (
        (df["amount"] < -threshold)
        & (df["category"] != "rent")
        & (df["category"] != "health_insurance")
    ).any():
        warnings.append("Very expensive item found")

    df.to_csv(DATA_DIR / f"{month}_check-missing.csv", index=False)

    # extract unclassified elements
    filename = DATA_DIR / f"{month}_check-missing.csv"
    df = pd.read_csv(filename, sep=",").dropna()
    unknown_mask = df["category"] == "unknown"
    unknown_indices = sorted(df.index[unknown_mask].tolist())

    raw_unclassified = []
    for idx in unknown_indices:
        data = df.loc[idx].to_dict()
        raw_unclassified.append(data)

    # format unclassified elements for bot messages
    unclassified: list[str] = []
    for data in raw_unclassified:
        # "date", "amount", "balance", "bank", "description"
        string = f"{data['date']} - {data['bank']}"
        string += f"\n\n{data['amount']:0.2f}€"
        string += f"\n\n{data['description']}"
        unclassified.append(string)

    return unclassified, warnings


def add_missing_categories(month: str, categories: list[str]):
    input_filename = DATA_DIR / f"{month}_check-missing.csv"
    df = pd.read_csv(input_filename, sep=",").dropna()

    # populate the uncategorized elements (ordering is important)
    unknown_mask = df["category"] == "unknown"
    unknown_indices = sorted(df.index[unknown_mask].tolist())
    for idx, category in zip(unknown_indices, categories):
        df.at[idx, "category"] = category

    output_filename = DATA_DIR / f"{month}_processed.csv"
    df.to_csv(output_filename, index=False)

    os.remove(input_filename)
    return


def plot_summary(date: str):
    if "-" not in date:
        month = f"{date}-12"
        num_months = 12
        title = date
    else:
        month = date
        num_months = 6
        y, m = map(int, date.split("-"))
        title = f"{LONG_ALPHABETIC[m]} {y}"

    ds = get_xarray(month, num_months)
    fig = plot_xarray(ds, title=title)

    fig.savefig(PLOTS_DIR / f"{date}_summary.jpg", dpi=300, format="jpg")
    return


def relabel_bank_statement_files(month: str) -> None:
    file1 = DATA_DIR / f"{month}-0.txt"
    file2 = DATA_DIR / f"{month}-1.txt"

    with open(file1, "r") as file:
        data1 = file.read()

    if "104989904\tEUR\t" not in data1:
        file1, file2 = file2, file1

    os.rename(file1, DATA_DIR / f"{month}_ABN.txt")
    os.rename(file2, DATA_DIR / f"{month}_caixa.csv")
    return
