"""
Data Job Market Radar — dashboard over the dbt-modeled DuckDB warehouse.
Run:  streamlit run dashboard/app.py
"""

from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

WAREHOUSE = Path(__file__).resolve().parent.parent / "warehouse.duckdb"
GREEN, MUTED = "#0e7c3a", "#8f97a3"

st.set_page_config(page_title="Data Job Market Radar", page_icon="📡",
                   layout="wide", initial_sidebar_state="expanded")


@st.cache_resource
def get_con():
    return duckdb.connect(str(WAREHOUSE), read_only=True)


@st.cache_data(ttl=3600)
def q(sql: str) -> pd.DataFrame:
    return get_con().execute(sql).fetchdf()


jobs = q("SELECT * FROM fct_job_postings WHERE is_active")
skills = q("SELECT * FROM agg_skill_demand ORDER BY n_jobs DESC")
salary = q("SELECT * FROM agg_salary_benchmarks")
trends = q("SELECT * FROM agg_skill_by_snapshot ORDER BY snapshot_date")
taxonomy = q("SELECT skill, category FROM skill_taxonomy")

snapshots = q("SELECT DISTINCT snapshot_date FROM raw_job_postings ORDER BY 1")

st.title("📡 Data Job Market Radar")
st.caption("What employers actually ask remote data candidates — scraped weekly from "
           "**RemoteOK · Jobicy · Remotive · Arbeitnow**, modeled with dbt, tested end-to-end.")

# ----------------------------------------------------------------- KPI row
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Active postings tracked", f"{len(jobs):,}")
c2.metric("Distinct skills detected", f"{skills['skill'].nunique():,}")
with_sal = jobs["salary_mid_usd"].dropna()
c3.metric("Postings with salary", f"{len(with_sal):,}",
          f"{len(with_sal)/len(jobs)*100:.0f}% share")
c4.metric("Median salary (where stated)",
          f"${with_sal.median():,.0f}" if len(with_sal) else "—")
c5.metric("Globally-open roles", f"{jobs['globally_remote'].sum():,}",
          help="Location phrased worldwide/anywhere/remote — open to Pakistan-based applicants")

tab_over, tab_skill, tab_sal, tab_explore, tab_docs = st.tabs(
    ["🏠 Overview", "🧠 Skills", "💰 Salaries", "🔎 Job explorer", "📐 Methodology"])

# ---------------------------------------------------------------- Overview
with tab_over:
    a, b = st.columns([3, 2])
    with a:
        fam = jobs["role_family"].value_counts().rename_axis("role_family").reset_index(name="n")
        fig = px.bar(fam, x="n", y="role_family", orientation="h",
                     color_discrete_sequence=[GREEN],
                     title="Active postings by role family")
        fig.update_layout(height=340, template="plotly_white",
                          margin=dict(l=10, r=10, t=40, b=10),
                          yaxis=dict(categoryorder="total ascending"), xaxis_title=None, yaxis_title=None)
        st.plotly_chart(fig, width="stretch")
    with b:
        sen = jobs["seniority"].value_counts()
        fig2 = px.pie(values=sen.values, names=sen.index, hole=.55,
                      title="Seniority mix", color_discrete_sequence=px.colors.sequential.Greens[3:])
        fig2.update_layout(height=340, margin=dict(l=10, r=10, t=40, b=10),
                           legend=dict(orientation="h"))
        st.plotly_chart(fig2, width="stretch")

    if len(snapshots) > 1:
        st.subheader("Skill demand over weekly snapshots")
        top5 = skills.head(5)["skill"].tolist()
        tr = trends[trends["skill"].isin(top5)]
        fig3 = px.line(tr, x="snapshot_date", y="n_jobs", color="skill", markers=True)
        fig3.update_layout(height=300, template="plotly_white", margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig3, width="stretch")
    else:
        st.info("📈 Trend lines build up automatically — the weekly GitHub Action appends a new "
                "snapshot every Monday (currently: week 1). Posting lifecycle fields "
                "(`first_seen`, `days_listed_observed`) become meaningful from week 2.")

# ------------------------------------------------------------------ Skills
with tab_skill:
    a, b = st.columns([3, 2])
    with a:
        top = skills.head(20)
        fig = px.bar(top, x="share_of_active_pct", y="skill", orientation="h",
                     color="skill_category", text="share_of_active_pct",
                     title="Share of active postings mentioning each skill (%)")
        fig.update_layout(height=560, template="plotly_white", margin=dict(l=10, r=10, t=40, b=10),
                          yaxis=dict(categoryorder="total ascending"),
                          xaxis_title=None, yaxis_title=None, showlegend=True,
                          legend=dict(orientation="h", title=None))
        fig.update_traces(texttemplate="%{text}%", textposition="outside")
        st.plotly_chart(fig, width="stretch")
    with b:
        st.subheader("Skill × salary")
        ss = skills.dropna(subset=["median_salary_mid_usd"]).nlargest(14, "median_salary_mid_usd")
        if len(ss):
            fig2 = px.scatter(ss, x="median_salary_mid_usd", y="skill",
                              size="n_jobs", color="skill_category",
                              title="Median salary where mentioned (USD)")
            fig2.update_layout(height=560, template="plotly_white",
                               margin=dict(l=10, r=10, t=40, b=10), xaxis_title=None,
                               yaxis_title=None, showlegend=False)
            st.plotly_chart(fig2, width="stretch")
        else:
            st.warning("Salary coverage is thin this week — RemoteOK is the only source that "
                       "publishes salary fields natively. Coverage grows with history.")

# ---------------------------------------------------------------- Salaries
with tab_sal:
    if len(salary):
        fig = go.Figure()
        for _, r in salary.sort_values("median_usd").iterrows():
            label = f"{r['role_family']} · {r['seniority']} (n={int(r['n_postings'])})"
            fig.add_trace(go.Scatter(
                x=[r["p25_usd"], r["p75_usd"]], y=[label, label], mode="lines",
                line=dict(color=MUTED, width=8), opacity=.45, showlegend=False))
            fig.add_trace(go.Scatter(x=[r["median_usd"]], y=[label], mode="markers",
                                     marker=dict(color=GREEN, size=13), showlegend=False))
        fig.update_layout(height=420, template="plotly_white", title="Salary bands (p25–p75, median dot)",
                          margin=dict(l=10, r=10, t=40, b=10), xaxis_tickprefix="$", xaxis_title=None)
        st.plotly_chart(fig, width="stretch")
    else:
        st.warning("Not enough salary data yet (need ≥2 postings per family×seniority). "
                   "Bands appear as weekly snapshots accumulate.")

    st.subheader("Salary coverage by source")
    cov = q("""SELECT source, count(*) n,
                      countif(salary_mid_usd IS NOT NULL) with_salary
               FROM fct_job_postings GROUP BY source ORDER BY n DESC""")
    cov["coverage"] = (cov["with_salary"] / cov["n"] * 100).round(1)
    st.dataframe(cov, hide_index=True, width="stretch",
                 column_config={"coverage": st.column_config.ProgressColumn(
                     "salary coverage %", format="%.0f%%", min_value=0, max_value=100)})

# ------------------------------------------------------------- Job explorer
with tab_explore:
    a, b, c = st.columns([2, 1, 1])
    search = a.text_input("Search title/company")
    fam_f = b.multiselect("Family", sorted(jobs["role_family"].unique()))
    sen_f = c.multiselect("Seniority", ["intern", "junior", "mid", "senior"],
                          default=["intern", "junior", "mid", "senior"])
    gl = st.checkbox("Only globally-open roles (worldwide/anywhere)")

    view = jobs.copy()
    if search:
        m = view["title"].str.contains(search, case=False) | view["company"].str.contains(search, case=False)
        view = view[m]
    if fam_f:
        view = view[view["role_family"].isin(fam_f)]
    if sen_f:
        view = view[view["seniority"].isin(sen_f)]
    if gl:
        view = view[view["globally_remote"]]

    st.caption(f"{len(view)} postings")
    st.dataframe(
        view[["title", "company", "location_text", "seniority", "role_family",
              "salary_min_usd", "salary_max_usd", "source", "posted_at", "url"]]
        .sort_values("posted_at", ascending=False),
        hide_index=True, width="stretch", height=520,
        column_config={"url": st.column_config.LinkColumn("apply"),
                       "salary_min_usd": st.column_config.NumberColumn("salary min", format="$%d"),
                       "salary_max_usd": st.column_config.NumberColumn("salary max", format="$%d"),
                       "posted_at": st.column_config.DatetimeColumn("posted", format="DD MMM")})

# ------------------------------------------------------------- Methodology
with tab_docs:
    st.markdown("""
**Pipeline:** 4 keyless public APIs → Python normalizer (salary text parsing, skill
extraction against a 51-skill seeded taxonomy, seniority/family classifiers) →
append-snapshot DuckDB raw layer → dbt (staging → intermediate → marts, 24 tests,
freshness SLAs) → this dashboard. Weekly refresh via GitHub Actions.

**Modeling choices worth knowing about:**
- **Append-snapshot raw layer** — one row per posting *per weekly snapshot*, giving
  posting lifecycle (`first_seen`, `last_seen`, `days_listed_observed`) and trend
  series for free. Same-day reruns are idempotent (delete-and-reload per source).
- **Edge enrichment** — messy parsing (salary text like `$90k-120k`, HTML
  descriptions) happens in Python at the edge; dbt receives clean typed rows.
- **Skill mentions counted on the latest posting version only** — reworded
  descriptions can't double-count.
- **Salary bands filtered to a $20k–$600k sanity band**, with a warning-severity
  dbt test (`assert_salary_sanity`) catching mis-scraped text.

**Known source quirks:** Jobicy's public API exposes salaries for ~0% of listings and
silently ignores `order=latest`; Remotive's `data` category includes non-data gigs
(we re-filter by title); Arbeitnow (EU-heavy) has no salary field at all. Real-world
sources are imperfect — the pipeline is honest about coverage: see the Salaries tab.
""")

st.divider()
st.caption("Built by **[Umer Iqbal](https://github.com/Bilalkhank10)** — Data Analyst & "
           "Analytics Engineer · [Repo & docs](https://github.com/Bilalkhank10/data-job-market-radar)")
