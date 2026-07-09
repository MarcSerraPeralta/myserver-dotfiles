import os
from pathlib import Path
from dotenv import load_dotenv
import math
import numpy as np
import xarray as xr
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.colors import to_rgb

_ = load_dotenv("/opt/bot-expenses/bot-expenses.env")

DATA_DIR: Path = Path(os.environ.get("DATA_DIR"))

SHORT_ALPHABETIC = {
    1: "Jan",
    2: "Feb",
    3: "Mar",
    4: "Apr",
    5: "May",
    6: "Jun",
    7: "Jul",
    8: "Aug",
    9: "Sep",
    10: "Oct",
    11: "Nov",
    12: "Dec",
}
LONG_ALPHABETIC = {
    1: "Januray",
    2: "February",
    3: "March",
    4: "April",
    5: "May",
    6: "June",
    7: "July",
    8: "August",
    9: "September",
    10: "October",
    11: "November",
    12: "December",
}

SKIP_CATEGORIES = ("salary", "rent")
CATEGORY_COLORS = {
    "rent": "peru",
    "supermarket": "yellow",
    "hobbies": "purple",
    "public_transport": "orange",
    "house": "gray",
    "health_insurance": "royalblue",
    "restaurants": "orangered",
    "bar": "gold",
    "games": "violet",
    "flights": "deepskyblue",
    "trips": "hotpink",
    "bike": "lightgray",
    "presents": "red",
    "hair": "darkgoldenrod",
    "other": "black",
    "SIM": "blueviolet",
    "turist_attractions": "olivedrab",
    "bank_fee": "darkgreen",
    "conference_budget": "darkblue",
    "visit_budget": "darkblue",
}


def get_xarray(month: str, num_months: int) -> xr.Dataset:
    months = get_months(month, num_months)

    datasets: list[pd.DataFrame] = []
    for month in months:
        filename = DATA_DIR / f"{month}_processed.csv"
        df = pd.read_csv(filename, sep=",").dropna()
        datasets.append(df)

    # balances
    balances: dict[str, dict[str, float]] = {}
    for month, dataset in zip(months, datasets):
        balance = get_balances(dataset)
        balances[month] = balance

    balances = pd.DataFrame.from_dict(balances).fillna(0)
    balances = balances.sort_values(months)
    balances = balances.T
    balances = balances["TOTAL"]
    balances_np = balances.to_numpy()

    # expenses
    expenses: dict[str, dict[str, float]] = {}
    for month, dataset in zip(months, datasets):
        expense, categories = get_expenses(dataset)
        expenses[month] = expense

    expenses = pd.DataFrame.from_dict(expenses).fillna(0)
    expenses = expenses.sort_values(months)
    expenses = expenses.T
    categories = expenses.columns
    expenses_np = expenses.to_numpy()

    months = [m.split("-")[1] for m in months]
    months = [SHORT_ALPHABETIC[int(m)] for m in months]

    ds = xr.Dataset(
        data_vars=dict(
            balance=(("month"), balances_np),
            expenses=(("month", "category"), expenses_np),
        ),
        coords=dict(
            month=months,
            category=categories,
        ),
    )
    return ds


def get_balances(df: pd.DataFrame) -> dict[str, float]:
    output: dict[str, float] = {}
    banks: list[str] = sorted(df["bank"].unique())
    total = 0
    for bank in banks:
        df_bank = df.loc[df["bank"] == bank]
        latest_operation = df_bank["date"].idxmax()
        latest_balance = df_bank.loc[latest_operation]["balance"]

        output[bank] = latest_balance
        total += latest_balance

    output["TOTAL"] = total

    return output


def get_expenses(df: pd.DataFrame) -> tuple[dict[str, float], list[str]]:
    categories: list[str] = df["category"].unique()
    for category in categories:
        if "0_" in category:
            raise ValueError(f"Categories in file still have warnings: {category}")
    if "unknown" in categories:
        raise ValueError("Some elements are in the 'unknown' category.")

    expenses: dict[str, float] = {}
    for category in categories:
        value = sum(df.loc[df["category"] == category]["amount"])
        expenses[category] = value

    return expenses, categories


def get_months(month: str, num_months: int) -> list[str]:
    months = [month]
    previous = month
    for _ in range(num_months - 1):
        y, m = map(int, previous.split("-"))
        if m == 1:
            m = 12
            y -= 1
        else:
            m -= 1

        previous = f"{y}-{m:02d}"
        months.append(previous)

    months = months[::-1]
    return months


def pprint(x: object, no_decimals: bool = False) -> str:
    if not isinstance(x, float):
        return str(x)
    if x == 0.0:
        return "0€" if no_decimals else "0.00€"
    negative = x < 0
    x, dec = f"{(-1) ** negative * x:.2f}".split(".")
    string = ",".join([x[::-1][i : i + 3] for i in range(0, len(x), 3)])[::-1]
    if no_decimals:
        return f"-{string}€" if negative else f"{string}€"
    return f"-{string}.{dec}€" if negative else f"{string}.{dec}€"


def text_color(color: str | None) -> str:
    if color is None:
        return "black"
    r, g, b = to_rgb(color)
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    return "black" if luminance > 0.5 else "white"


def plot_xarray(ds: xr.Dataset, title: str) -> plt.Figure:
    # load data
    balances = ds.balance
    expenses = ds.expenses
    months: list[str] = [m.item() for m in ds.month]
    all_categories: list[str] = [
        str(c)
        for c in ds.category.values
        if expenses.sel(month=months[-1], category=c) != 0
    ]
    categories = [c for c in all_categories if c not in SKIP_CATEGORIES]

    x = list(range(len(months)))

    # create figure
    height = math.ceil(len(categories) / 2) * 6.75 + 10
    width = len(months) * 2 + 5
    margin = 0.02

    def w(x: float | int) -> float:
        return x / width

    def h(x: float | int) -> float:
        return x / height

    cm = 1 / 2.54  # centimeters in inches
    fig = plt.figure(figsize=(width * cm, height * cm))
    curr_y = height

    # title
    curr_height = 1
    curr_y -= curr_height
    _ = fig.text(w(0.5), h(curr_y), title, ha="left", va="bottom", fontsize=15)

    # monthly balance
    curr_height = 5
    curr_y -= curr_height + 1
    ax = fig.add_axes(
        (margin, h(curr_y), 0.5 - 2 * margin, h(curr_height))
    )  # [left, bottom, width, height] — all between 0 and 1

    exp: list[float] = []
    sav: list[float] = []
    for xi, month in zip(x, months):
        curr_pos, curr_neg = 0, 0
        for c in all_categories:
            value: float = expenses.sel(month=month, category=c).values
            if value > 0:
                curr_pos += value
            else:
                curr_neg += value

        curr_sav = curr_pos + curr_neg
        sav.append(curr_sav)
        exp.append(curr_neg)

    ax.axhline(
        np.average(exp), color="gray", linestyle="--", zorder=-1, alpha=0.5, linewidth=1
    )

    ax.bar(x[:-1], np.clip(sav[:-1], a_min=0, a_max=np.inf), color="green", alpha=0.7)
    ax.bar(x[:-1], exp[:-1], color="red", alpha=0.7)
    ax.bar(x[:-1], np.clip(sav[:-1], a_min=-np.inf, a_max=0), color="white")

    ax.bar(x[-1], np.clip(sav[-1], a_min=0, a_max=np.inf), color="green")
    ax.bar(x[-1], exp[-1], color="red")
    ax.bar(x[-1], np.clip(sav[-1], a_min=-np.inf, a_max=0), color="white")

    ax.axhline(0, color="gray", linewidth=1)

    total_range = max(sav) - min(exp)
    for xi, curr_sav, curr_neg in zip(x, sav, exp):
        if curr_sav >= 0:
            ax.text(
                xi,
                curr_sav + total_range * 0.03,
                pprint(curr_sav, no_decimals=True),
                fontsize=6,
                ha="center",
                va="bottom",
            )
        ax.text(
            xi,
            curr_neg - total_range * 0.03,
            pprint(curr_neg, no_decimals=True),
            fontsize=6,
            ha="center",
            va="top",
        )

    extra_space = total_range * 0.15
    ax.set_ylim(min(exp) - extra_space, max(sav) + extra_space)
    ax.set_xlim(-0.7, len(months) - 0.3)

    ax.set_xticks(x)
    ax.set_xticklabels(months)
    ax.set_yticks([])
    ax.set_yticklabels([])

    ax.set_title("Montly balance", fontsize=11, loc="left")

    # total balance
    ax = fig.add_axes(
        (0.5 + margin, h(curr_y), 0.5 - 2 * margin, h(curr_height))
    )  # [left, bottom, width, height] — all between 0 and 1

    ax.plot(x, balances, ".", color="blue")

    total_range = (balances[-1] - balances[0]).item()
    for xi, month in zip(x, months):
        value = balances.sel(month=month).item()
        ax.text(
            xi,
            value - 0.1 * total_range,
            pprint(value, no_decimals=True),
            fontsize=6,
            ha="center",
            va="bottom",
        )

    ave_savings = ((balances[-1] - balances[0]) / len(months)).item()
    ax.text(
        -0.275,
        max(balances),
        f"average = {pprint(ave_savings, no_decimals=True)}/month",
        fontsize=8,
        ha="left",
        color="gray",
    )

    extra_space = (max(balances) - min(balances)) * 0.15
    ax.set_ylim(min(balances) - extra_space, max(balances) + extra_space)
    ax.set_xlim(-0.7, len(months) - 0.3)

    ax.set_xticks(x)
    ax.set_xticklabels(months)
    ax.set_yticks([])
    ax.set_yticklabels([])

    ax.set_title("Balance", fontsize=11, loc="left")

    # percentage bar
    curr_height = 1
    curr_y -= curr_height + 1
    ax = fig.add_axes(
        (margin, h(curr_y), 1 - 2 * margin, h(curr_height))
    )  # [left, bottom, width, height] — all between 0 and 1

    negative_exp: dict[str, float] = {}
    for c in categories:
        value = expenses.sel(month=months[-1], category=c).item()
        if value < 0:
            negative_exp[c] = value

    total_neg_exp = sum(negative_exp.values())
    percentages = {c: v / total_neg_exp for c, v in negative_exp.items()}
    ordered = sorted(percentages.items(), key=lambda x: x[1], reverse=True)
    xi = 0
    for c, v in ordered:
        r = Rectangle((xi, 0), v, 1, color=CATEGORY_COLORS.get(c))
        ax.add_patch(r)

        if v > 0.05:
            ax.text(
                xi + v / 2,
                0.5,
                f"{c[:6]}\n{pprint(-v * total_neg_exp)}",
                ha="center",
                va="center",
                fontsize=7,
                color=text_color(CATEGORY_COLORS.get(c)),
            )

        xi += v

    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    ax.set_xticks([0, 0.25, 0.5, 0.75, 1])
    ax.set_xticklabels(["0%", "25%", "50%", "75%", "100%"], fontsize=6)
    ax.set_yticks([])
    ax.set_yticklabels([])

    # category plots
    total_neg_exp = sum(negative_exp.values())
    percentages = {c: v / total_neg_exp for c, v in negative_exp.items()}
    ordered = sorted(percentages.items(), key=lambda x: x[1], reverse=True)
    categories_ordered = [c for c, _ in ordered if c not in SKIP_CATEGORIES]

    curr_height = 5

    for k, c in enumerate(categories_ordered):
        if k % 2 == 0:
            separation = 1.75 if k != 0 else 1.5
            curr_y -= curr_height + separation
            ax = fig.add_axes(
                (margin, h(curr_y), 0.5 - 2 * margin, h(curr_height))
            )  # [left, bottom, width, height] — all between 0 and 1
        else:
            ax = fig.add_axes(
                (0.5 + margin, h(curr_y), 0.5 - 2 * margin, h(curr_height))
            )  # [left, bottom, width, height] — all between 0 and 1

        data = -expenses.sel(category=c).to_numpy()

        color = "gray" if np.average(data) >= 0 else "green"
        ax.axhline(
            np.average(data),
            color=color,
            linestyle="--",
            zorder=-1,
            alpha=0.5,
            linewidth=1,
        )

        total_range = max(abs(data))
        for i, (xi, d) in enumerate(zip(x, data)):
            alpha = 1 if i == len(data) - 1 else 0.5
            hatch = None if d >= 0 else "//"
            text = pprint(d) if d >= 0 else "+" + pprint(np.abs(d))
            bar = ax.bar(
                xi, np.abs(d), color=CATEGORY_COLORS.get(c), alpha=alpha, hatch=hatch
            )
            if c not in CATEGORY_COLORS:
                CATEGORY_COLORS[c] = bar.patches[0].get_facecolor()
            ax.text(
                xi,
                np.abs(d) + total_range * 0.08,
                text,
                fontsize=6,
                ha="center",
                va="top",
            )

        ax.set_ylim(0, max(abs(data)) + total_range * 0.15)
        ax.set_xlim(-0.7, len(months) - 0.3)

        ax.set_xticks(x)
        ax.set_xticklabels(months)
        ax.set_yticks([])
        ax.set_yticklabels([])

        ax.set_title(c, loc="left")

    return fig
