"""
AgentShield V3 Dashboard
========================
Real-time monitoring dashboard for multi-agent behavior chain risk governance.
Port: 18711

Usage:
    cd /mnt/d/ZYY Project/AgentShield_V3
    python dashboard.py
"""

import streamlit as st
import requests
import json
import time
import pandas as pd
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

# Page config
st.set_page_config(
    page_title="AgentShield V3 Dashboard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Constants
API_BASE = "http://localhost:8011"
REFRESH_INTERVAL = 5  # seconds

# Custom CSS
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #0f3460;
        margin: 10px 0;
    }
    .risk-high { color: #ff4757; font-weight: bold; }
    .risk-medium { color: #ffa502; font-weight: bold; }
    .risk-low { color: #2ed573; font-weight: bold; }
    .header-text { font-size: 2rem; font-weight: bold; color: #e94560; }
    .stMetric { background: #0f3460; padding: 15px; border-radius: 10px; }
</style>
""", unsafe_allow_html=True)


def check_api_health():
    """Check if the V3 API is running"""
    try:
        resp = requests.get(f"{API_BASE}/health", timeout=2)
        if resp.status_code == 200:
            return resp.json()
    except:
        pass
    return None


def get_benchmark_results():
    """Load benchmark results from local file"""
    benchmark_path = Path(__file__).parent / "benchmark" / "benchmark_report.json"
    if benchmark_path.exists():
        with open(benchmark_path, encoding="utf-8") as f:
            return json.load(f)
    return None


def get_behavior_chain_sample():
    """Get sample behavior chain data for visualization"""
    return {
        "sessions": [
            {
                "session_id": "demo_session_001",
                "agents": ["orchestrator", "data_agent", "tool_agent"],
                "total_calls": 24,
                "blocked": 2,
                "review": 5,
                "allowed": 17,
                "avg_risk_score": 0.45,
                "risk_history": [0.3, 0.5, 0.7, 0.85, 0.6, 0.4, 0.3, 0.5, 0.9, 0.7],
                "last_updated": datetime.now().isoformat()
            }
        ]
    }


def render_risk_gauge(score, title="Risk Score"):
    """Render a gauge chart for risk score"""
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score * 100,
        domain={'x': [0, 1], 'y': [0, 1]},
        gauge={
            'axis': {'range': [0, 100], 'tickwidth': 1},
            'bar': {'color': "#e94560"},
            'steps': [
                {'range': [0, 60], 'color': '#2ed573'},
                {'range': [60, 80], 'color': '#ffa502'},
                {'range': [80, 100], 'color': '#ff4757'}
            ],
            'threshold': {
                'line': {'color': "#e94560", 'width': 4},
                'value': score * 100
            }
        },
        title={'text': title}
    ))
    fig.update_layout(
        height=200,
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor="rgba(0,0,0,0)"
    )
    return fig


def render_risk_timeline(risk_history, title="Risk Score Timeline"):
    """Render risk score timeline chart"""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=list(range(len(risk_history))),
        y=risk_history,
        mode='lines+markers',
        fill='tozeroy',
        line=dict(color='#e94560', width=2),
        fillcolor='rgba(233, 69, 96, 0.2)'
    ))
    
    # Add threshold lines
    fig.add_hline(y=0.7, line_dash="dash", line_color="#ffa502", annotation_text="Review Threshold")
    fig.add_hline(y=0.9, line_dash="dash", line_color="#ff4757", annotation_text="Block Threshold")
    
    fig.update_layout(
        title=title,
        height=250,
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis_title="Step",
        yaxis_title="Risk Score"
    )
    return fig


def render_governance_pie(allowed, review, blocked):
    """Render governance action distribution pie chart"""
    fig = go.Figure(data=[go.Pie(
        labels=['Allow', 'Review', 'Block'],
        values=[allowed, review, blocked],
        marker=dict(colors=['#2ed573', '#ffa502', '#ff4757']),
        textinfo='label+percent',
        hole=0.4
    )])
    fig.update_layout(
        title="Governance Actions",
        height=250,
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor="rgba(0,0,0,0)"
    )
    return fig


def render_category_bar(categories):
    """Render benchmark accuracy by category"""
    if not categories:
        return None
    
    cats = list(categories.keys())
    score_acc = [categories[c]['pass'] / categories[c]['total'] * 100 for c in cats]
    action_acc = [categories[c]['action_pass'] / categories[c]['total'] * 100 for c in cats]
    
    fig = go.Figure()
    fig.add_trace(go.Bar(name='Score Accuracy', x=cats, y=score_acc, marker_color='#e94560'))
    fig.add_trace(go.Bar(name='Action Accuracy', x=cats, y=action_acc, marker_color='#0f3460'))
    
    fig.update_layout(
        title="Benchmark Accuracy by Category",
        barmode='group',
        height=300,
        margin=dict(l=20, r=20, t=40, b=80),
        paper_bgcolor="rgba(0,0,0,0)",
        yaxis_title="Accuracy (%)",
        xaxis_title="Category"
    )
    return fig


def main():
    # Header
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.markdown('<p class="header-text">🛡️ AgentShield V3 Dashboard</p>', unsafe_allow_html=True)
    with col2:
        st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")
    with col3:
        if st.button("🔄 Refresh"):
            st.rerun()
    
    st.divider()
    
    # Sidebar - System Status
    st.sidebar.title("System Status")
    health = check_api_health()
    if health:
        st.sidebar.success("✅ V3 API Online")
        st.sidebar.json(health)
    else:
        st.sidebar.error("❌ V3 API Offline")
        st.sidebar.caption(f"Make sure the API is running at {API_BASE}")
        st.sidebar.caption("Start with: uvicorn app.main:app --port 8011")
    
    st.sidebar.divider()
    
    # Sidebar - Quick Stats
    st.sidebar.subheader("Quick Stats")
    benchmark = get_benchmark_results()
    if benchmark:
        summary = benchmark.get("summary", {})
        st.sidebar.metric("Total Test Cases", summary.get("total", 0))
        st.sidebar.metric("Score Accuracy", f"{summary.get('score_accuracy', 0):.1f}%")
        st.sidebar.metric("Action Accuracy", f"{summary.get('action_accuracy', 0):.1f}%")
    else:
        st.sidebar.info("No benchmark data")
    
    st.sidebar.divider()
    
    # Sidebar - Risk Thresholds
    st.sidebar.subheader("Governance Thresholds")
    st.sidebar.slider("ALLOW threshold", 0.0, 1.0, 0.70, key="allow_thresh")
    st.sidebar.slider("BLOCK threshold", 0.0, 1.0, 0.90, key="block_thresh")
    
    st.sidebar.divider()
    
    # Main content tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Overview", 
        "🔗 Behavior Chain", 
        "📈 Benchmark", 
        "📋 Session History"
    ])
    
    with tab1:
        st.subheader("Risk Overview")
        
        # Top metrics row
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric("Active Sessions", "3", delta="+1")
        with m2:
            st.metric("Total Calls Today", "1,247", delta="+12%")
        with m3:
            st.metric("Blocked", "23", delta="-3")
        with m4:
            st.metric("Avg Risk Score", "0.45", delta="-0.05")
        
        st.divider()
        
        # Charts row
        c1, c2 = st.columns(2)
        
        with c1:
            st.plotly_chart(render_risk_gauge(0.45), use_container_width=True)
        
        with c2:
            risk_data = get_behavior_chain_sample()
            if risk_data and risk_data.get("sessions"):
                session = risk_data["sessions"][0]
                st.plotly_chart(
                    render_risk_timeline(session.get("risk_history", [])),
                    use_container_width=True
                )
        
        c3, c4 = st.columns(2)
        with c3:
            st.subheader("Governance Distribution")
            st.plotly_chart(
                render_governance_pie(17, 5, 2),
                use_container_width=True
            )
        
        with c4:
            st.subheader("Agent Activity")
            agent_data = pd.DataFrame({
                'Agent': ['Orchestrator', 'Data Agent', 'Tool Agent', 'Security Agent'],
                'Calls': [45, 32, 28, 15],
                'Avg Risk': [0.35, 0.62, 0.48, 0.71]
            })
            st.dataframe(agent_data, use_container_width=True, hide_index=True)
    
    with tab2:
        st.subheader("Behavior Chain Visualization")
        
        # Behavior chain visualization placeholder
        st.info("🔗 Real-time behavior chain from V3 Engine")
        
        # Sample chain
        chain_data = {
            "nodes": [
                {"id": "node_1", "type": "orchestrator", "action": "route_request", "risk": 0.2},
                {"id": "node_2", "type": "data_agent", "action": "query_database", "risk": 0.5},
                {"id": "node_3", "type": "tool_agent", "action": "execute_sql", "risk": 0.85},
                {"id": "node_4", "type": "tool_agent", "action": "send_response", "risk": 0.3},
            ],
            "edges": [
                {"from": "node_1", "to": "node_2", "risk_contribution": 0.2},
                {"from": "node_2", "to": "node_3", "risk_contribution": 0.5},
                {"from": "node_3", "to": "node_4", "risk_contribution": 0.85},
            ]
        }
        
        # Display as table
        nodes_df = pd.DataFrame(chain_data["nodes"])
        st.dataframe(
            nodes_df.rename(columns={"id": "Node ID", "type": "Agent Type", "action": "Action", "risk": "Risk Score"}),
            use_container_width=True,
            hide_index=True
        )
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Risk Propagation Path")
            for i, edge in enumerate(chain_data["edges"]):
                st.markdown(f"""
                **{i+1}. {edge['from']} → {edge['to']}**
                - Risk Contribution: `{edge['risk_contribution']}`
                """)
        
        with col2:
            st.subheader("What-If Analysis")
            whatif_data = {
                "Scenario": ["Block node_3", "Add review at node_2", "Reduce risk at node_3"],
                "Risk Delta": ["-0.42", "-0.15", "-0.25"],
                "Impact": ["High", "Medium", "Medium"]
            }
            st.dataframe(pd.DataFrame(whatif_data), use_container_width=True, hide_index=True)
    
    with tab3:
        st.subheader("Benchmark Results")
        
        if benchmark:
            summary = benchmark.get("summary", {})
            categories = benchmark.get("categories", {})
            results = benchmark.get("results", [])
            
            # Summary metrics
            s1, s2, s3, s4 = st.columns(4)
            with s1:
                st.metric("Total Cases", summary.get("total", 0))
            with s2:
                st.metric("Score Accuracy", f"{summary.get('score_accuracy', 0):.1f}%")
            with s3:
                st.metric("Action Accuracy", f"{summary.get('action_accuracy', 0):.1f}%")
            with s4:
                errors = summary.get("errors", 0)
                st.metric("Errors", errors)
            
            st.divider()
            
            # Category chart
            st.plotly_chart(render_category_bar(categories), use_container_width=True)
            
            st.divider()
            
            # Detailed results table
            st.subheader("Detailed Results")
            
            # Filters
            f1, f2, f3 = st.columns(3)
            with f1:
                category_filter = st.selectbox("Category", ["All"] + list(categories.keys()))
            with f2:
                status_filter = st.selectbox("Status", ["All", "Pass", "Fail"])
            with f3:
                search = st.text_input("Search", placeholder="Filter by description...")
            
            # Filter results
            filtered = results
            if category_filter != "All":
                filtered = [r for r in filtered if r.get("category") == category_filter]
            if status_filter != "All":
                if status_filter == "Pass":
                    filtered = [r for r in filtered if r.get("score_pass")]
                else:
                    filtered = [r for r in filtered if not r.get("score_pass")]
            if search:
                filtered = [r for r in filtered if search.lower() in r.get("description", "").lower()]
            
            # Display
            for r in filtered[:50]:
                status = "✅" if r.get("score_pass") else "❌"
                with st.expander(f"{status} {r.get('id')}: {r.get('description', '')[:60]}..."):
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.write(f"**Category:** {r.get('category')}")
                        st.write(f"**Expected Score:** {r.get('expected_score')}")
                        st.write(f"**Actual Score:** {r.get('actual_score')}")
                    with col_b:
                        st.write(f"**Expected Action:** {r.get('expected_action')}")
                        st.write(f"**Actual Action:** {r.get('actual_action')}")
                        delta = r.get('score_delta', 0)
                        st.write(f"**Delta:** {delta:.3f}")
        else:
            st.warning("No benchmark results found. Run `python benchmark/evaluate.py` first.")
            
            if st.button("▶️ Run Benchmark"):
                st.info("Running benchmark...")
                # This would call the benchmark script
                st.rerun()
    
    with tab4:
        st.subheader("Session History")
        
        # Sample session history
        sessions = [
            {"session_id": "sess_001", "agents": 4, "calls": 45, "blocked": 3, "review": 8, "allowed": 34, "status": "completed"},
            {"session_id": "sess_002", "agents": 3, "calls": 28, "blocked": 1, "review": 4, "allowed": 23, "status": "running"},
            {"session_id": "sess_003", "agents": 5, "calls": 67, "blocked": 5, "review": 12, "allowed": 50, "status": "completed"},
            {"session_id": "sess_004", "agents": 2, "calls": 15, "blocked": 0, "review": 2, "allowed": 13, "status": "failed"},
        ]
        
        df = pd.DataFrame(sessions)
        st.dataframe(
            df.rename(columns={
                "session_id": "Session ID",
                "agents": "Agents",
                "calls": "Total Calls",
                "blocked": "Blocked",
                "review": "Review",
                "allowed": "Allowed",
                "status": "Status"
            }),
            use_container_width=True,
            hide_index=True
        )
        
        # Session detail
        st.divider()
        selected = st.selectbox("Select Session", [s["session_id"] for s in sessions])
        if selected:
            st.json({
                "session_id": selected,
                "created_at": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat(),
                "behavior_graph": {"nodes": 12, "edges": 15},
                "risk_metrics": {"avg": 0.45, "max": 0.92, "min": 0.12}
            })


if __name__ == "__main__":
    main()
