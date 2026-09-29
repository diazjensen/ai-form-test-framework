"""
Quality Intelligence Dashboard (Streamlit).

Reads results/quality.db, which pytest (conftest.py hooks) and
ingest_locust.py populate after every run. Nothing is stored in Streamlit
itself -- refresh the page after a new run to see it.

    py -m streamlit run dashboard/streamlit_app.py
"""
import os
import sys
import sqlite3
import subprocess

import pandas as pd
import streamlit as st

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_PATH = os.path.join(ROOT, "results", "quality.db")
DIFF_DIR = os.path.join(ROOT, "results", "visual_diffs")
BASELINE_DIR = os.path.join(ROOT, "quality_suite", "baselines")

st.set_page_config(page_title="Quality Intelligence Dashboard", page_icon="🧪", layout="wide")


@st.cache_data(ttl=5)
def q(sql, params=()):
    if not os.path.exists(DB_PATH):
        return pd.DataFrame()
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query(sql, conn, params=params)


st.title("🧪 Quality Intelligence Dashboard")
st.caption("AI-based web-form testing · Playwright (functional + visual) · PyTest (contract) · Locust (API load)")

runs = q("SELECT * FROM runs ORDER BY id DESC")
if runs.empty:
    st.info("No runs recorded yet. Run `py run_quality_suite.py` from the project root, then refresh.")
    st.stop()

# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("Run Selection")
    labels = {int(r.id): f"#{int(r.id)} · {r.started_at} · {int(r.passed)}/{int(r.total)} passed"
              for r in runs.itertuples()}
    run_id = st.selectbox("Select run", list(labels), format_func=lambda i: labels[i])
    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()
    st.caption(f"DB: `{os.path.relpath(DB_PATH, ROOT)}`")

    st.divider()
    st.header("⚡ Phase 1 Pytest Runner")
    p1_mode = st.radio(
        "Requirements Source",
        ["Case A: SRS Document Provided", "Case B: Black Box (Accessibility Tree + DOM)"],
        index=0,
    )
    p1_url = st.text_input("Target Web Form URL", value="http://127.0.0.1:5000/")
    if st.button("▶️ Execute Phase 1 Tests", type="primary"):
        with st.spinner("Executing Phase 1 unit testing suite..."):
            py_bin = "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3"
            if not os.path.exists(py_bin):
                py_bin = sys.executable

            phase1_script = os.path.join(ROOT, "run_phase1.py")
            cmd = [py_bin, phase1_script, "--url", p1_url.strip()]
            if "Case A" in p1_mode:
                cmd.extend(["--srs", os.path.join(ROOT, "srs", "registration_srs.md")])
            else:
                cmd.append("--blackbox")

            res = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
            st.cache_data.clear()
            if res.returncode == 0:
                st.success("Phase 1 executed successfully!")
            else:
                st.warning("Phase 1 run finished with test failures or errors.")
            st.rerun()

run = runs[runs.id == run_id].iloc[0]
results = q("SELECT * FROM test_results WHERE run_id=?", (run_id,))
catalog = q("SELECT * FROM catalog")
perf = q("SELECT * FROM perf_stats WHERE run_id=?", (run_id,))
perf_hist = q("SELECT * FROM perf_history WHERE run_id=? ORDER BY id", (run_id,))

tab_overview, tab_catalog, tab_fail, tab_perf, tab_visual, tab_ai_gen = st.tabs(
    ["📊 Overview", "📖 Test Catalog", "🩺 Failures & Root Cause", "⚡ Performance", "🖼️ Visual Regression", "🤖 AI Test Generator"]
)

# ---------------------------------------------------------------- overview
with tab_overview:
    total, passed, failed, skipped = (int(run[k]) for k in ("total", "passed", "failed", "skipped"))
    rate = (passed / total * 100) if total else 0
    c = st.columns(5)
    c[0].metric("Pass rate", f"{rate:.0f}%")
    c[1].metric("Passed", passed)
    c[2].metric("Failed", failed)
    c[3].metric("Skipped", skipped)
    c[4].metric("Duration", f"{run.duration_s:.1f}s")
    st.caption(f"Framework mode for this run: **{run.case_mode}**")

    left, right = st.columns(2)
    with left:
        st.subheader("Outcome by layer")
        if not results.empty:
            by_layer = results.pivot_table(index="layer", columns="outcome", values="id",
                                           aggfunc="count", fill_value=0)
            st.bar_chart(by_layer)
    with right:
        st.subheader("Pass rate across runs")
        hist = runs.sort_values("id").copy()
        hist["pass_rate_%"] = (hist.passed / hist.total.replace(0, pd.NA) * 100).astype(float)
        st.line_chart(hist.set_index("id")["pass_rate_%"])

    st.subheader("Slowest tests")
    if not results.empty:
        st.dataframe(results.nlargest(5, "duration_s")[["name", "layer", "outcome", "duration_s"]],
                     hide_index=True, width="stretch")

    # flaky: tests whose outcome differs between runs
    all_res = q("SELECT nodeid, outcome FROM test_results")
    if not all_res.empty:
        flaky = (all_res.groupby("nodeid")["outcome"].nunique().loc[lambda s: s > 1]).index.tolist()
        if flaky:
            st.warning(f"⚠️ {len(flaky)} test(s) changed outcome between runs (possible flakiness / regressions):")
            st.write(flaky)

# ---------------------------------------------------------------- catalog
with tab_catalog:
    st.subheader("Plain-English test catalog")
    st.caption("Generated from `@pytest.mark.description(...)` markers and docstrings in the test code.")
    if catalog.empty:
        st.info("Catalog is empty.")
    else:
        last = results[["nodeid", "outcome"]].rename(columns={"outcome": "last_outcome"})
        merged = catalog.merge(last, on="nodeid", how="left")
        f1, f2 = st.columns(2)
        layers = f1.multiselect("Layer", sorted(merged.layer.unique()), default=sorted(merged.layer.unique()))
        search = f2.text_input("Search intent / field / expected")
        view = merged[merged.layer.isin(layers)]
        if search:
            mask = view[["intent", "target_fields", "expected", "docstring"]].fillna("").apply(
                lambda col: col.str.contains(search, case=False)).any(axis=1)
            view = view[mask]
        st.dataframe(
            view[["layer", "intent", "target_fields", "expected", "last_outcome", "name"]],
            hide_index=True, width="stretch",
            column_config={"intent": "What it checks", "target_fields": "Fields",
                           "expected": "Expected outcome", "last_outcome": "Last result", "name": "Test id"},
        )
        st.caption(f"{len(view)} of {len(merged)} tests shown")

# ---------------------------------------------------------------- failures
with tab_fail:
    fails = results[results.outcome == "failed"] if not results.empty else results
    if fails.empty:
        st.success("No failures in this run. 🎉")
    else:
        fails = fails.astype(object).where(fails.notna(), "")  # NaN -> "" so blank fields are falsy
        st.subheader(f"{len(fails)} failure(s)")
        for r in fails.itertuples():
            with st.expander(f"❌ {r.name}  ·  {r.layer}", expanded=True):
                if r.diagnosis:
                    st.info(f"**AI diagnosis** _(by {r.diagnosis_provider})_\n\n{r.diagnosis}")
                st.markdown(f"**Intent:** {r.intent or '—'}  \n**Expected:** {r.expected or '—'}  \n"
                            f"**Fields:** {r.target_fields or '—'}")
                a, b = st.columns(2)
                with a:
                    st.markdown("**Error**")
                    st.code(r.error or "—", language="text")
                    st.markdown(f"**Last HTTP status:** `{r.http_status if r.http_status != '' else '—'}`")
                    st.code(r.http_trace or "—", language="text")
                with b:
                    if r.screenshot and os.path.exists(os.path.join(ROOT, r.screenshot)):
                        st.image(os.path.join(ROOT, r.screenshot), caption="Failure screenshot")
                    st.markdown("**Browser console**")
                    st.code(r.console_logs or "—", language="text")
                with st.popover("Full stack trace"):
                    st.code(r.stack or "—", language="text")

# ---------------------------------------------------------------- performance
with tab_perf:
    if perf.empty:
        st.info("No Locust data for this run. `run_quality_suite.py` runs it automatically.")
    else:
        agg = perf[perf.endpoint == "Aggregated"]
        if not agg.empty:
            a = agg.iloc[0]
            c = st.columns(5)
            c[0].metric("Requests", int(a.requests))
            c[1].metric("Failures", int(a.failures))
            c[2].metric("Median", f"{a.median_ms:.0f} ms")
            c[3].metric("p95", f"{a.p95_ms:.0f} ms")
            c[4].metric("Throughput", f"{a.rps:.1f} req/s")
        st.subheader("Per endpoint")
        st.dataframe(perf[["endpoint", "requests", "failures", "median_ms", "avg_ms", "p95_ms", "rps"]],
                     hide_index=True, width="stretch")
        if not perf_hist.empty:
            ph = perf_hist.reset_index(drop=True)
            l, r = st.columns(2)
            l.subheader("Throughput & users over time")
            l.line_chart(ph[["rps", "users"]])
            r.subheader("p95 latency over time (ms)")
            r.line_chart(ph[["p95_ms"]])

# ---------------------------------------------------------------- visual
with tab_visual:
    st.subheader("Visual regression")
    vis = results[results.layer == "visual"] if not results.empty else results
    if vis.empty:
        st.info("No visual tests in this run.")
    else:
        st.dataframe(vis[["name", "outcome", "intent"]], hide_index=True, width="stretch")
    diffs = sorted(f for f in os.listdir(DIFF_DIR)) if os.path.isdir(DIFF_DIR) else []
    diff_imgs = [f for f in diffs if f.endswith("_diff.png")]
    if diff_imgs:
        st.warning("Differences against the approved baseline were found:")
        for f in diff_imgs:
            base = f.replace("_diff.png", "")
            c = st.columns(3)
            bp = os.path.join(BASELINE_DIR, base + ".png")
            if os.path.exists(bp):
                c[0].image(bp, caption=f"Baseline: {base}")
            ap = os.path.join(DIFF_DIR, base + "_actual.png")
            if os.path.exists(ap):
                c[1].image(ap, caption="Actual")
            c[2].image(os.path.join(DIFF_DIR, f), caption="Changed pixels (red)")
    else:
        st.success("No visual diffs on record.")
    baselines = sorted(os.listdir(BASELINE_DIR)) if os.path.isdir(BASELINE_DIR) else []
    with st.expander(f"Approved baselines ({len(baselines)})"):
        cols = st.columns(3)
        for i, f in enumerate(baselines):
            cols[i % 3].image(os.path.join(BASELINE_DIR, f), caption=f)

# ---------------------------------------------------------------- AI generator
with tab_ai_gen:
    st.subheader("🤖 AI Test Skeleton Generator")
    st.caption("Auto-generate basic test skeleton scripts from natural language prompts using the light LLM wrapper.")

    sys.path.insert(0, os.path.join(ROOT, "quality_suite"))
    import llm_client
    from generate_skeleton import generate

    prov = llm_client.active_provider()
    st.info(f"Active LLM Provider: **{prov.upper()}** (fallback: deterministic rule-based template)")

    prompt_input = st.text_input(
        "Enter test description / prompt:",
        placeholder="e.g. check that age below 18 is rejected, or verify that country dropdown enables state dropdown",
    )

    if st.button("✨ Auto-Generate Test Skeleton", type="primary"):
        if not prompt_input.strip():
            st.error("Please enter a prompt first.")
        else:
            with st.spinner("Generating test skeleton..."):
                out_path, provider_label, code_content = generate(prompt_input.strip())
                st.success(f"Generated via **{provider_label}**!")
                st.markdown(f"Saved to: `{os.path.relpath(out_path, ROOT)}`")
                st.code(code_content, language="python")

