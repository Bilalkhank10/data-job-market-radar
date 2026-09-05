"""Export portfolio/README PNGs from the marts. Run after dbt build."""
from pathlib import Path
import duckdb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"; ASSETS.mkdir(exist_ok=True)
GREEN, DARK, MUTED, GRID = "#0e7c3a", "#1a1f24", "#8f97a3", "#e5e9ec"
plt.rcParams.update({"figure.facecolor": "white", "axes.facecolor": "white",
    "axes.edgecolor": GRID, "axes.grid": True, "grid.color": GRID,
    "grid.linewidth": .6, "axes.spines.top": False, "axes.spines.right": False,
    "font.size": 11, "axes.titlesize": 14, "axes.titleweight": "bold",
    "axes.labelcolor": DARK, "text.color": DARK, "xtick.color": MUTED,
    "ytick.color": MUTED})

con = duckdb.connect(str(ROOT / "warehouse.duckdb"), read_only=True)

s = con.execute("""SELECT skill, share_of_active_pct FROM agg_skill_demand
                   ORDER BY share_of_active_pct LIMIT 15""").fetchdf()
fig, ax = plt.subplots(figsize=(10, 6))
ax.barh(s["skill"], s["share_of_active_pct"], color=GREEN)
for i, v in enumerate(s["share_of_active_pct"]):
    ax.text(v + 1, i, f"{v:.0f}%", va="center", fontsize=10, color=DARK)
ax.set_title("Most-demanded skills in remote data jobs (share of postings)")
ax.set_xlabel("share of active postings (%)"); ax.grid(axis="y", visible=False)
fig.tight_layout(); fig.savefig(ASSETS / "chart_top_skills.png", dpi=160); plt.close(fig)

sal = con.execute("""SELECT role_family || ' · ' || seniority AS grp, p25_usd,
                     p75_usd, median_usd FROM agg_salary_benchmarks
                     ORDER BY median_usd""").fetchdf()
if len(sal):
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.hlines(sal["grp"], sal["p25_usd"] / 1000, sal["p75_usd"] / 1000,
              color=MUTED, lw=7, alpha=.5)
    ax.plot(sal["median_usd"] / 1000, sal["grp"], "o", color=GREEN, ms=11)
    ax.set_title("Remote data salaries by role & seniority ($k/yr, p25–p75 + median)")
    ax.grid(axis="y", visible=False)
    fig.tight_layout(); fig.savefig(ASSETS / "chart_salary_bands.png", dpi=160)
    plt.close(fig)

print("wrote:", *[p.name for p in sorted(ASSETS.glob("chart_*.png"))])
