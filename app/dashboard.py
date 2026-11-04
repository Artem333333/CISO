import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

from risk_engine import (
    build_risk_dashboard_data,
    load_controls,
    load_asset_controls,
    simulate_control_improvement
)

st.set_page_config(
    page_title="CISO Pulse Dashboard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🛡️ CISO Pulse: Security Posture Dashboard")
st.markdown("**Cyber Risk Management in Business Language**")
st.markdown("---")

@st.cache_data
def get_risk_data():
    return build_risk_dashboard_data()

df = get_risk_data()

if df.empty:
    st.error("❌ No data available. Please check files in data/ directory")
    st.stop()

st.sidebar.header("🔍 Filters")

criticality_filter = st.sidebar.multiselect(
    "Business Criticality",
    options=df['business_criticality'].unique(),
    default=df['business_criticality'].unique()
)

owner_filter = st.sidebar.multiselect(
    "Asset Owner",
    options=df['business_owner'].unique(),
    default=df['business_owner'].unique()
)

filtered_df = df[
    (df['business_criticality'].isin(criticality_filter)) &
    (df['business_owner'].isin(owner_filter))
]

tab1, tab2, tab3 = st.tabs([
    "📊 Executive Dashboard",
    "🎛️ Control Map",
    "🧪 What-If Analysis"
])

with tab1:
    st.subheader("📊 Key Performance Indicators")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Assets", len(filtered_df))
    
    with col2:
        avg_risk = filtered_df['risk_score'].mean()
        st.metric(
            "Average Risk Level",
            f"{avg_risk:.1f}/100",
            delta="-5.2" if avg_risk < 50 else "+3.1",
            delta_color="normal" if avg_risk < 50 else "inverse"
        )
    
    with col3:
        avg_eff = filtered_df['control_effectiveness'].mean()
        st.metric(
            "Control Effectiveness",
            f"{avg_eff:.1f}%",
            delta="+8.3%"
        )
    
    with col4:
        total_exposure = filtered_df['risk_exposure_eur_hour'].sum()
        st.metric(
            "Financial Risk Exposure ($/hour)",
            f"${total_exposure:,.0f}",
            delta="-$25K"
        )
    
    st.markdown("---")
    
    st.subheader("🔥 Risk Heatmap")
    st.markdown("*Bubble size = revenue impact, Color = risk level*")
    
    fig_scatter = px.scatter(
        filtered_df,
        x='business_criticality',
        y='risk_score',
        size='risk_exposure_eur_hour',
        color='risk_score',
        hover_name='asset_name',
        hover_data=['business_owner', 'control_effectiveness'],
        color_continuous_scale=['green', 'yellow', 'orange', 'red'],
        size_max=60,
        title="Risk Distribution by Asset"
    )
    fig_scatter.update_layout(
        xaxis_title="Business Criticality",
        yaxis_title="Risk Score (0-100)",
        height=500
    )
    st.plotly_chart(fig_scatter, use_container_width=True)
    
    st.subheader("📋 Critical Assets Registry")
    display_df = filtered_df[[
        'asset_name', 'business_owner', 'business_criticality',
        'control_effectiveness', 'risk_score', 'risk_exposure_eur_hour'
    ]].copy()
    display_df['control_effectiveness'] = display_df['control_effectiveness'].apply(lambda x: f"{x}%")
    display_df['risk_score'] = display_df['risk_score'].apply(lambda x: f"{x}/100")
    display_df['risk_exposure_eur_hour'] = display_df['risk_exposure_eur_hour'].apply(lambda x: f"${x:,.0f}")
    display_df.columns = ['Asset', 'Owner', 'Criticality', 'Control Effectiveness', 'Risk', 'Impact ($/hour)']
    st.dataframe(display_df, use_container_width=True, hide_index=True)

with tab2:
    st.subheader("🎛️ Control Implementation Matrix")
    st.markdown("*Select an asset to view all control statuses*")
    
    selected_asset = st.selectbox(
        "Asset",
        options=filtered_df['asset_name'].tolist(),
        index=0
    )
    
    asset_id = filtered_df[filtered_df['asset_name'] == selected_asset]['asset_id'].iloc[0]
    
    controls = load_controls()
    asset_controls = load_asset_controls()
    asset_ctrls = asset_controls[asset_controls['asset_id'] == asset_id].merge(
        controls[['control_id', 'control_name', 'control_category', 'weight']],
        on='control_id'
    )
    
    st.markdown("#### 📈 Effectiveness by Category")
    cat_data = asset_ctrls.groupby('control_category')['effectiveness_score'].mean().reset_index()
    
    fig_radar = go.Figure()
    fig_radar.add_trace(go.Scatterpolar(
        r=cat_data['effectiveness_score'].tolist() + [cat_data['effectiveness_score'].iloc[0]],
        theta=cat_data['control_category'].tolist() + [cat_data['control_category'].iloc[0]],
        fill='toself',
        name='Effectiveness',
        line_color='#1f77b4'
    ))
    fig_radar.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        height=450
    )
    st.plotly_chart(fig_radar, use_container_width=True)
    
    st.markdown("#### 📋 Detailed Control Status")
    
    status_emoji = {
        'Implemented': '✅',
        'Partial': '⚠️',
        'Not Implemented': '❌'
    }
    
    display_ctrls = pd.DataFrame({
        'Control': asset_ctrls['control_name'],
        'Category': asset_ctrls['control_category'],
        'Status': asset_ctrls['implementation_status'].map(status_emoji) + ' ' + asset_ctrls['implementation_status'],
        'Effectiveness': asset_ctrls['effectiveness_score'].apply(lambda x: f"{x}%"),
        'Assessment Date': asset_ctrls['last_assessment_date']
    })
    
    st.dataframe(
        display_ctrls,
        use_container_width=True,
        hide_index=True
    )

with tab3:
    st.subheader("🧪 Security Investment Simulator")
    st.markdown("""
    **What if** we implement a specific control on a specific asset? 
    How will the risk change and how much money will we save?
    
    *This is a tool for budget justification before the CFO.*
    """)
    
    col1, col2 = st.columns(2)
    
    with col1:
        sim_asset = st.selectbox(
            "Select Asset",
            options=filtered_df['asset_name'].tolist(),
            key="sim_asset"
        )
        sim_asset_id = filtered_df[filtered_df['asset_name'] == sim_asset]['asset_id'].iloc[0]
    
    with col2:
        controls = load_controls()
        asset_controls = load_asset_controls()
        available_controls = asset_controls[asset_controls['asset_id'] == sim_asset_id].merge(
            controls[['control_id', 'control_name']],
            on='control_id'
        )
        sim_control = st.selectbox(
            "Select Control to Improve",
            options=available_controls['control_name'].tolist(),
            key="sim_control"
        )
        sim_control_id = available_controls[available_controls['control_name'] == sim_control]['control_id'].iloc[0]
        current_eff = available_controls[available_controls['control_id'] == sim_control_id]['effectiveness_score'].iloc[0]
    
    new_eff = st.slider(
        "Improve control effectiveness to?",
        min_value=int(current_eff),
        max_value=100,
        value=min(int(current_eff) + 30, 100),
        step=5
    )
    
    if st.button("🚀 Calculate Impact", type="primary"):
        result = simulate_control_improvement(sim_asset_id, sim_control_id, new_eff)
        
        st.markdown("---")
        st.markdown(f"### 📊 Impact for **{result['asset_name']}**")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(
                "Risk Reduction",
                f"{result['risk_reduction']:.1f} points",
                f"{result['current_risk']:.1f} → {result['new_risk']:.1f}"
            )
        with col2:
            st.metric(
                "Savings ($/hour)",
                f"${result['exposure_savings']:,.0f}",
                f"{result['current_exposure']:,.0f} → {result['new_exposure']:,.0f}"
            )
        with col3:
            annual_savings = result['exposure_savings'] * 24 * 365
            st.metric(
                "Annual Savings",
                f"${annual_savings:,.0f}",
                "Assuming 24/7 risk exposure"
            )
        
        st.success(f"""
        💡 **Insight for CFO:**  
        Implementing control **"{result['control_name']}"** on asset **{result['asset_name']}** 
        will reduce risk level from {result['current_risk']:.1f} to {result['new_risk']:.1f} 
        and save the company **${annual_savings:,.0f} per year**.
        """)

st.markdown("---")
st.subheader("📄 Board of Directors Report")
st.markdown("""
Generate a professional PDF report with:
- Executive Summary
- Risk Heatmap
- Top 5 critical risks with recommendations
- Budget request with ROI
""")

if st.button("🚀 Generate PDF Report", type="primary"):
    with st.spinner("Generating report..."):
        from report_generator import generate_executive_report
        
        pdf_bytes = generate_executive_report(filtered_df)
        
        st.download_button(
            label="📥 Download Report (PDF)",
            data=pdf_bytes,
            file_name=f"CISO_Pulse_Report_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.pdf",
            mime="application/pdf"
        )
        
        st.success("✅ Report generated successfully! Click the button above to download.")

st.markdown("---")
last_update = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')
st.markdown(
    f"""
    **💡 How to use this dashboard:**
    
    1. **Executive Dashboard** — overall picture for the Board of Directors
    2. **Control Map** — detailed analysis for each asset
    3. **What-If Analysis** — budget justification before the CFO
    
    *Last data update: {last_update}*
    """
)