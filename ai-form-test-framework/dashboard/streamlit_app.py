"""
Web Form Testing Application & Quality Intelligence Dashboard.

A standalone, interactive web application to:
1. Input any target web form URL directly without an IDE or prior sample runs.
2. Conditionally generate and execute tests:
   - Case A: Specification-Driven (upload or select SRS document)
   - Case B: Black Box Testing (Chromium Accessibility Tree + DOM Features)
3. Browse Plain-English Test Catalog, AI Root Cause Diagnostics, and Error Logs.
4. Generate AI test skeletons from natural language prompts.
"""
import json
import os
import sqlite3
import subprocess
import sys

import pandas as pd
import streamlit as st

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_PATH = os.path.join(ROOT, "results", "quality.db")
DIFF_DIR = os.path.join(ROOT, "results", "visual_diffs")
BASELINE_DIR = os.path.join(ROOT, "quality_suite", "baselines")
ERROR_LOG_PATH = os.path.join(ROOT, "results", "test_errors.log")
CONFIG_PATH = os.path.join(ROOT, "config.json")
SRS_DIR = os.path.join(ROOT, "srs")

st.set_page_config(
    page_title="Web Form Testing Framework",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1e293b;
        margin-bottom: 0.2rem;
    }
    .sub-caption {
        font-size: 1rem;
        color: #64748b;
        margin-bottom: 1.5rem;
    }
    .run-box {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 1.5rem;
        margin-bottom: 2rem;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=5)
def q(sql, params=()):
    if not os.path.exists(DB_PATH):
        return pd.DataFrame()
    try:
        with sqlite3.connect(DB_PATH) as conn:
            return pd.read_sql_query(sql, conn, params=params)
    except Exception:
        return pd.DataFrame()


def get_default_url():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                return json.load(f).get("target_url", "")
        except Exception:
            pass
    return ""


# Header
st.markdown('<div class="main-header">🧪 AI-Based Web Form Testing Framework</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-caption">Autonomous Form Verification · Chromium Accessibility Tree · DOM Extraction · Pytest Contract Testing · AI Root Cause Diagnostics</div>', unsafe_allow_html=True)

# --------------------------------------------------------------------------------
# STANDALONE FORM TESTER CONSOLE (Direct input without needing an IDE)
# --------------------------------------------------------------------------------
with st.container():
    st.subheader("🎯 Test a Web Form")
    st.caption("Enter any live web form URL to extract inputs, generate tests, and execute validations immediately.")

    col1, col2 = st.columns([3, 2])
    with col1:
        target_url = st.text_input(
            "Web Form URL under test",
            value="",
            placeholder="https://...",
            help="Enter the direct URL of any interactive web form."
        )

    with col2:
        test_mode = st.radio(
            "Requirements Specification Mode",
            [
                "Case B: Black-Box (Accessibility Tree + DOM) [No SRS needed]",
                "Case A: Specification-Driven (SRS Document)"
            ],
            index=0,
            help="Case B uses Chromium Accessibility Tree & DOM attributes. Case A asserts against formal SRS specifications."
        )

    srs_path = None
    if "Case A" in test_mode:
        srs_col1, srs_col2 = st.columns(2)
        with srs_col1:
            existing_srs = []
            if os.path.isdir(SRS_DIR):
                existing_srs = [os.path.join("srs", f) for f in os.listdir(SRS_DIR) if f.endswith((".md", ".txt"))]
            selected_srs = st.selectbox(
                "Select existing SRS Document from workspace",
                existing_srs if existing_srs else ["None found"],
                index=0 if existing_srs else 0
            )
            if selected_srs and selected_srs != "None found":
                srs_path = os.path.join(ROOT, selected_srs)

        with srs_col2:
            uploaded_srs = st.file_uploader("Or upload your own SRS document (.md / .txt)", type=["md", "txt"])
            if uploaded_srs is not None:
                os.makedirs(SRS_DIR, exist_ok=True)
                save_path = os.path.join(SRS_DIR, f"uploaded_{uploaded_srs.name}")
                with open(save_path, "wb") as f:
                    f.write(uploaded_srs.getbuffer())
                srs_path = save_path
                st.success(f"Loaded: `{uploaded_srs.name}`")

    demo_fail = st.checkbox("Include intentional failure assertions (to test failure detection & AI diagnostics)", value=False)

    btn_col1, btn_col2 = st.columns([1, 4])
    with btn_col1:
        run_btn = st.button("🚀 Run AI Test Suite", type="primary", use_container_width=True)

    if run_btn:
        if not target_url or not target_url.strip().startswith("http"):
            st.error("Please enter a valid HTTP or HTTPS Web Form URL (e.g. `https://example.com/form`).")
        else:
            with st.spinner("Extracting form elements, building unified model, and running tests..."):
                py_bin = "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3"
                if not os.path.exists(py_bin):
                    py_bin = sys.executable

                phase1_script = os.path.join(ROOT, "run_phase1.py")
                cmd = [py_bin, phase1_script, "--url", target_url.strip()]
                if "Case A" in test_mode and srs_path:
                    cmd.extend(["--srs", srs_path])
                else:
                    cmd.append("--blackbox")

                if demo_fail:
                    cmd.append("--demo-fail")

                res = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
                st.cache_data.clear()

                if res.returncode == 0:
                    st.success("✅ Test suite generation & execution finished!")
                else:
                    st.warning("⚠️ Test run completed with failure(s) or validation issues.")

                with st.expander("📄 View Live Test Output & Error Log", expanded=True):
                    st.code(res.stdout if res.stdout else res.stderr, language="text")

                st.rerun()

st.divider()

# --------------------------------------------------------------------------------
# DASHBOARD METRICS & RUN REPORTS
# --------------------------------------------------------------------------------
runs = q("SELECT * FROM runs ORDER BY id DESC")

# Sidebar
with st.sidebar:
    st.header("⚙️ Framework Status")
    st.success("🟢 Server Running (Port 8501)")
    if st.button("🔄 Refresh Dashboard Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.divider()
    st.header("📜 Run History")
    if runs.empty:
        st.info("No runs recorded yet. Use the console above to run your first test.")
        run_id = None
    else:
        labels = {
            int(r.id): f"#{int(r.id)} · {r.started_at} ({int(r.passed)}/{int(r.total)} passed)"
            for r in runs.itertuples()
        }
        run_id = st.selectbox("Select historical run", list(labels), format_func=lambda i: labels[i])
        st.caption(f"Database: `{os.path.relpath(DB_PATH, ROOT)}`")

# Main tabs
tab_overview, tab_catalog, tab_fail, tab_log, tab_perf, tab_visual, tab_ai_gen = st.tabs(
    ["📊 Overview", "📖 Test Catalog", "🩺 Failures & Root Cause", "📋 Error Log", "⚡ Performance", "🖼️ Visual Regression", "🤖 AI Test Generator"]
)

if runs.empty:
    with tab_overview:
        st.info("👋 Welcome! To begin, enter the URL of the web form you want to test in the console above and click **'🚀 Run AI Test Suite'**.")
else:
    run = runs[runs.id == run_id].iloc[0]
    results = q("SELECT * FROM test_results WHERE run_id=?", (run_id,))
    catalog = q("SELECT * FROM catalog")
    perf = q("SELECT * FROM perf_stats WHERE run_id=?", (run_id,))
    perf_hist = q("SELECT * FROM perf_history WHERE run_id=? ORDER BY id", (run_id,))

    # ---------------------------------------------------------------- overview
    with tab_overview:
        total, passed, failed, skipped = (int(run[k]) for k in ("total", "passed", "failed", "skipped"))
        rate = (passed / total * 100) if total else 0
        c = st.columns(5)
        c[0].metric("Pass Rate", f"{rate:.0f}%")
        c[1].metric("Passed Tests", passed)
        c[2].metric("Failed Tests", failed)
        c[3].metric("Skipped Tests", skipped)
        c[4].metric("Execution Duration", f"{run.duration_s:.2f}s")
        st.caption(f"Testing Mode: **{run.case_mode}** · Started: `{run.started_at}`")

        left, right = st.columns(2)
        with left:
            st.subheader("Outcome Breakdown")
            if not results.empty:
                by_layer = results.pivot_table(index="layer", columns="outcome", values="id",
                                               aggfunc="count", fill_value=0)
                st.bar_chart(by_layer)
        with right:
            st.subheader("Pass Rate Trend Across Runs")
            hist = runs.sort_values("id").copy()
            hist["pass_rate_%"] = (hist.passed / hist.total.replace(0, pd.NA) * 100).astype(float)
            st.line_chart(hist.set_index("id")["pass_rate_%"])

        st.subheader("Test Execution Times")
        if not results.empty:
            st.dataframe(results.nlargest(10, "duration_s")[["name", "layer", "outcome", "duration_s"]],
                         hide_index=True, width="stretch")

    # ---------------------------------------------------------------- catalog
    with tab_catalog:
        st.subheader("Plain-English Test Catalog")
        st.caption("Cataloged directly from `@pytest.mark.description(...)` markers and docstrings in generated code.")
        if catalog.empty:
            st.info("Catalog is empty for this run.")
        else:
            last = results[["nodeid", "outcome"]].rename(columns={"outcome": "last_outcome"})
            merged = catalog.merge(last, on="nodeid", how="left")
            f1, f2 = st.columns(2)
            layers = f1.multiselect("Layer filter", sorted(merged.layer.unique()), default=sorted(merged.layer.unique()))
            search = f2.text_input("Search intent / field / expected", placeholder="e.g. required, password, boundary")
            view = merged[merged.layer.isin(layers)]
            if search:
                mask = view[["intent", "target_fields", "expected", "docstring"]].fillna("").apply(
                    lambda col: col.str.contains(search, case=False)).any(axis=1)
                view = view[mask]
            st.dataframe(
                view[["layer", "intent", "target_fields", "expected", "last_outcome", "name"]],
                hide_index=True, width="stretch",
                column_config={"intent": "Test Intent", "target_fields": "Fields Validated",
                               "expected": "Expected Outcome", "last_outcome": "Result", "name": "Test ID"},
            )
            st.caption(f"Showing {len(view)} of {len(merged)} cataloged tests")

    # ---------------------------------------------------------------- failures
    with tab_fail:
        fails = results[results.outcome == "failed"] if not results.empty else results
        if fails.empty:
            st.success("🎉 All test assertions passed with 0 failures for this run!")
        else:
            fails = fails.astype(object).where(fails.notna(), "")
            st.subheader(f"Observed Failures ({len(fails)})")
            for r in fails.itertuples():
                with st.expander(f"❌ {r.name}  ·  {r.layer}", expanded=True):
                    if r.diagnosis:
                        st.info(f"**AI Root Cause Diagnostic** _(by {r.diagnosis_provider})_\n\n{r.diagnosis}")
                    st.markdown(f"**Intent:** {r.intent or '—'}  \n**Expected:** {r.expected or '—'}  \n"
                                f"**Fields:** {r.target_fields or '—'}")
                    a, b = st.columns(2)
                    with a:
                        st.markdown("**Error Details**")
                        st.code(r.error or "—", language="text")
                        st.markdown(f"**Last HTTP Status:** `{r.http_status if r.http_status != '' else '—'}`")
                        st.code(r.http_trace or "—", language="text")
                    with b:
                        if r.screenshot and os.path.exists(os.path.join(ROOT, r.screenshot)):
                            st.image(os.path.join(ROOT, r.screenshot), caption="Failure Screenshot")
                        st.markdown("**Browser Console Output**")
                        st.code(r.console_logs or "—", language="text")
                    with st.popover("Full Stack Trace"):
                        st.code(r.stack or "—", language="text")

    # ---------------------------------------------------------------- error log
    with tab_log:
        st.subheader("📋 Structured Error Log (`test_errors.log`)")
        st.caption("Standardized error output formatted specifically for logging observed validation anomalies.")
        if os.path.exists(ERROR_LOG_PATH):
            with open(ERROR_LOG_PATH, encoding="utf-8") as f:
                log_data = f.read()
            st.code(log_data, language="text")
            st.download_button(
                "⬇️ Download Error Log (.log)",
                data=log_data,
                file_name="test_errors.log",
                mime="text/plain"
            )
        else:
            st.info("No error log generated yet.")

    # ---------------------------------------------------------------- performance
    with tab_perf:
        st.subheader("⚡ Performance & Load Metrics")
        if perf.empty:
            st.info("No Locust load data recorded for this unit test run. Run `python3 run_all.py` to trigger full Locust stress profiling.")
        else:
            agg = perf[perf.endpoint == "Aggregated"]
            if not agg.empty:
                a = agg.iloc[0]
                c = st.columns(5)
                c[0].metric("Requests", int(a.requests))
                c[1].metric("Failures", int(a.failures))
                c[2].metric("Median Latency", f"{a.median_ms:.0f} ms")
                c[3].metric("p95 Latency", f"{a.p95_ms:.0f} ms")
                c[4].metric("Throughput", f"{a.rps:.1f} req/s")
            st.dataframe(perf[["endpoint", "requests", "failures", "median_ms", "avg_ms", "p95_ms", "rps"]],
                         hide_index=True, width="stretch")

    # ---------------------------------------------------------------- visual
    with tab_visual:
        st.subheader("🖼️ Visual Regression & Snapshots")
        vis = results[results.layer == "visual"] if not results.empty else results
        if vis.empty:
            st.info("No visual tests executed in this unit test run.")
        else:
            st.dataframe(vis[["name", "outcome", "intent"]], hide_index=True, width="stretch")
        diffs = sorted(f for f in os.listdir(DIFF_DIR)) if os.path.isdir(DIFF_DIR) else []
        diff_imgs = [f for f in diffs if f.endswith("_diff.png")]
        if diff_imgs:
            st.warning("Visual regressions detected:")
            for f in diff_imgs:
                base = f.replace("_diff.png", "")
                c = st.columns(3)
                bp = os.path.join(BASELINE_DIR, base + ".png")
                if os.path.exists(bp):
                    c[0].image(bp, caption=f"Baseline: {base}")
                ap = os.path.join(DIFF_DIR, base + "_actual.png")
                if os.path.exists(ap):
                    c[1].image(ap, caption="Actual")
                c[2].image(os.path.join(DIFF_DIR, f), caption="Pixel Diffs (Red)")
        else:
            st.success("No visual regressions recorded.")

    # ---------------------------------------------------------------- AI generator
    with tab_ai_gen:
        st.subheader("🤖 AI Test Skeleton Generator")
        st.caption("Draft custom test skeletons from plain English descriptions using the light LLM wrapper.")

        sys.path.insert(0, os.path.join(ROOT, "quality_suite"))
        try:
            import llm_client
            from generate_skeleton import generate
            prov = llm_client.active_provider()
            st.info(f"Active LLM Provider: **{prov.upper()}** (fallback: rule-based template)")
        except Exception:
            prov = "offline template"

        prompt_input = st.text_input(
            "Natural language test intent:",
            placeholder="e.g. verify that entering age below 18 shows an error, or check password minimum length",
        )

        if st.button("✨ Generate Test Skeleton", type="primary"):
            if not prompt_input.strip():
                st.error("Please enter a test prompt.")
            else:
                with st.spinner("Generating test skeleton..."):
                    out_path, provider_label, code_content = generate(prompt_input.strip())
                    st.success(f"Generated via **{provider_label}**!")
                    st.markdown(f"Saved to: `{os.path.relpath(out_path, ROOT)}`")
                    st.code(code_content, language="python")
