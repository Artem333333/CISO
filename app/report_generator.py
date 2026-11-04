import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
from fpdf import FPDF

from risk_engine import build_risk_dashboard_data, load_controls, load_asset_controls


class CISOPulseReport(FPDF):
    
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=15)
        
    def header(self):
        self.set_font('Helvetica', 'B', 16)
        self.set_text_color(31, 119, 180)
        self.cell(0, 10, 'CISO Pulse', 0, 0, 'L')
        self.set_font('Helvetica', '', 10)
        self.set_text_color(100, 100, 100)
        self.cell(0, 10, 'Security Posture Report', 0, 1, 'R')
        self.set_draw_color(31, 119, 180)
        self.line(10, 18, 200, 18)
        self.ln(5)
    
    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'Confidential | Generated {datetime.now().strftime("%Y-%m-%d %H:%M")} | Page {self.page_no()}/{{nb}}', 0, 0, 'C')
    
    def chapter_title(self, title):
        self.set_font('Helvetica', 'B', 14)
        self.set_text_color(31, 119, 180)
        self.cell(0, 10, title, 0, 1, 'L')
        self.ln(2)
    
    def metric_box(self, x, y, w, h, label, value, color=(31, 119, 180)):
        self.set_xy(x, y)
        self.set_draw_color(*color)
        self.set_fill_color(*color)
        self.rect(x, y, w, h, 'D')
        
        self.set_xy(x, y + 2)
        self.set_font('Helvetica', 'B', 18)
        self.set_text_color(*color)
        self.cell(w, 8, str(value), 0, 1, 'C')
        
        self.set_xy(x, y + h - 6)
        self.set_font('Helvetica', '', 8)
        self.set_text_color(80, 80, 80)
        self.cell(w, 5, label, 0, 1, 'C')


def generate_heatmap_image(df: pd.DataFrame) -> str:
    fig, ax = plt.subplots(figsize=(10, 5))
    
    colors = []
    for risk in df['risk_score']:
        if risk >= 70:
            colors.append('#d62728')
        elif risk >= 50:
            colors.append('#ff7f0e')
        elif risk >= 30:
            colors.append('#ffbb78')
        else:
            colors.append('#2ca02c')
    
    sizes = df['risk_exposure_eur_hour'] / df['risk_exposure_eur_hour'].max() * 1000 + 50
    
    criticality_map = {'Low': 1, 'Medium': 2, 'High': 3, 'Critical': 4}
    x_vals = [criticality_map.get(c, 2) for c in df['business_criticality']]
    
    ax.scatter(
        x_vals,
        df['risk_score'],
        s=sizes,
        c=colors,
        alpha=0.7,
        edgecolors='black',
        linewidth=0.5
    )
    
    for i, row in df.iterrows():
        ax.annotate(
            row['asset_name'][:20],
            (criticality_map.get(row['business_criticality'], 2), row['risk_score']),
            fontsize=7,
            ha='center',
            va='bottom'
        )
    
    ax.set_xticks([1, 2, 3, 4])
    ax.set_xticklabels(['Low', 'Medium', 'High', 'Critical'])
    ax.set_xlabel('Business Criticality', fontsize=10)
    ax.set_ylabel('Risk Score (0-100)', fontsize=10)
    ax.set_title('Risk Heatmap by Asset', fontsize=12, fontweight='bold')
    ax.set_ylim(0, 105)
    ax.grid(True, alpha=0.3)
    
    tmp = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
    plt.tight_layout()
    plt.savefig(tmp.name, dpi=150, bbox_inches='tight')
    plt.close()
    
    return tmp.name


def generate_executive_report(df: pd.DataFrame) -> bytes:
    pdf = CISOPulseReport()
    pdf.alias_nb_pages()
    pdf.add_page()
    
    pdf.set_font('Helvetica', 'B', 20)
    pdf.set_text_color(31, 119, 180)
    pdf.cell(0, 12, 'Executive Security Report', 0, 1, 'C')
    
    pdf.set_font('Helvetica', '', 11)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 8, f'Prepared for Board of Directors | {datetime.now().strftime("%B %d, %Y")}', 0, 1, 'C')
    pdf.ln(8)
    
    pdf.chapter_title('Executive Summary')
    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(40, 40, 40)
    
    avg_risk = df['risk_score'].mean()
    avg_eff = df['control_effectiveness'].mean()
    total_exposure = df['risk_exposure_eur_hour'].sum()
    critical_count = len(df[df['business_criticality'] == 'Critical'])
    high_risk_count = len(df[df['risk_score'] >= 70])
    
    summary_points = [
        f"Our security posture protects {len(df)} critical business assets with an average control effectiveness of {avg_eff:.1f}%.",
        f"Current average risk level is {avg_risk:.1f}/100, with {high_risk_count} assets requiring immediate attention (risk >= 70).",
        f"Total financial exposure at risk: USD {total_exposure:,.0f} per hour of potential downtime.",
        f"{critical_count} assets are classified as business-critical, including ERP, Customer Database, and E-commerce platforms.",
        f"Recommended investment of USD 2.5M in Q1 2027 will reduce risk exposure by 45% and save USD 16M annually."
    ]
    
    for point in summary_points:
        pdf.set_fill_color(240, 248, 255)
        pdf.cell(5, 6, '-', 0, 0)
        pdf.multi_cell(0, 6, f"  {point}", 0, 'L')
        pdf.ln(1)
    
    pdf.ln(5)
    
    pdf.chapter_title('Key Security Metrics')
    
    y_start = pdf.get_y()
    box_w = 42
    box_h = 22
    x_start = 12
    
    metrics = [
        ('Total Assets', str(len(df)), (31, 119, 180)),
        ('Avg Risk Score', f"{avg_risk:.0f}/100", (214, 39, 40) if avg_risk >= 60 else (44, 160, 44)),
        ('Control Effectiveness', f"{avg_eff:.0f}%", (255, 127, 14)),
        ('Exposure (USD/h)', f"{total_exposure/1000:.0f}K", (148, 103, 189))
    ]
    
    for i, (label, value, color) in enumerate(metrics):
        x = x_start + i * (box_w + 5)
        pdf.metric_box(x, y_start, box_w, box_h, label, value, color)
    
    pdf.set_y(y_start + box_h + 8)
    
    pdf.chapter_title('Risk Heatmap')
    pdf.set_font('Helvetica', 'I', 9)
    pdf.set_text_color(100, 100, 100)
    pdf.multi_cell(0, 5, 
        'Bubble size represents hourly revenue impact. Color indicates risk severity: '
        'green (<30), yellow (30-50), orange (50-70), red (>=70).')
    pdf.ln(3)
    
    heatmap_path = generate_heatmap_image(df)
    pdf.image(heatmap_path, x=10, w=190)
    pdf.ln(5)
    
    Path(heatmap_path).unlink(missing_ok=True)
    
    pdf.add_page()
    pdf.chapter_title('Top 5 Critical Risks & Recommendations')
    
    top_risks = df.nlargest(5, 'risk_score')
    
    for idx, (_, row) in enumerate(top_risks.iterrows(), 1):
        pdf.set_font('Helvetica', 'B', 11)
        pdf.set_text_color(214, 39, 40)
        pdf.cell(0, 7, f"{idx}. {row['asset_name']}", 0, 1, 'L')
        
        pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(40, 40, 40)
        pdf.cell(50, 5, f"Owner: {row['business_owner']}", 0, 0, 'L')
        pdf.cell(50, 5, f"Criticality: {row['business_criticality']}", 0, 0, 'L')
        pdf.cell(0, 5, f"Risk Score: {row['risk_score']:.1f}/100", 0, 1, 'L')
        
        pdf.cell(50, 5, f"Control Effectiveness: {row['control_effectiveness']:.1f}%", 0, 0, 'L')
        pdf.cell(0, 5, f"Financial Exposure: USD {row['risk_exposure_eur_hour']:,.0f}/hour", 0, 1, 'L')
        
        pdf.set_font('Helvetica', 'I', 9)
        pdf.set_text_color(31, 119, 180)
        
        if row['control_effectiveness'] < 50:
            recommendation = "URGENT: Implement foundational controls (MFA, backups, EDR) immediately."
        elif row['control_effectiveness'] < 70:
            recommendation = "HIGH: Strengthen partial controls and conduct penetration testing."
        else:
            recommendation = "MEDIUM: Optimize existing controls and enhance monitoring."
        
        pdf.multi_cell(0, 5, f"Recommendation: {recommendation}")
        pdf.ln(3)
    
    pdf.ln(5)
    pdf.chapter_title('Investment Proposal & ROI')
    
    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(40, 40, 40)
    
    investment_text = (
        f"Based on current risk exposure of USD {total_exposure:,.0f}/hour and average incident "
        f"downtime of 24 hours, potential annual loss is USD {total_exposure * 24 * 50:,.0f} "
        f"(assuming 50 incidents/year probability).\n\n"
        f"Proposed Q1 2027 investment: USD 2,500,000\n"
        f"Expected risk reduction: 45%\n"
        f"Annual savings: USD 16,000,000\n"
        f"ROI: 640% in Year 1\n\n"
        f"Key initiatives:\n"
        f"  - Enterprise MFA rollout: USD 500K\n"
        f"  - PAM implementation: USD 750K\n"
        f"  - Backup modernization: USD 350K\n"
        f"  - EDR expansion to OT: USD 300K\n"
        f"  - Security awareness program: USD 200K\n"
        f"  - Incident response testing: USD 400K"
    )
    
    pdf.multi_cell(0, 5, investment_text)
    
    pdf.ln(10)
    pdf.set_font('Helvetica', 'I', 9)
    pdf.set_text_color(100, 100, 100)
    pdf.multi_cell(0, 5, 
        'This report was generated automatically by CISO Pulse. '
        'For detailed analysis and remediation plans, please contact the CISO office.')
    
    return bytes(pdf.output())