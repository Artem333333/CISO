import pandas as pd
from pathlib import Path
from typing import Dict, Tuple

CRITICALITY_MULTIPLIER = {
    'Critical': 1.0,
    'High': 0.75,
    'Medium': 0.5,
    'Low': 0.25
}

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"


def load_controls() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "controls.csv")


def load_asset_controls() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "asset_controls.csv")


def load_assets() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "assets.csv")


def calculate_control_effectiveness(
    asset_id: str,
    asset_controls: pd.DataFrame,
    controls: pd.DataFrame
) -> Tuple[float, Dict[str, float]]:
    asset_ctrls = asset_controls[asset_controls['asset_id'] == asset_id].copy()
    
    if asset_ctrls.empty:
        return 0.0, {}
    
    merged = asset_ctrls.merge(
        controls[['control_id', 'weight', 'control_category']],
        on='control_id',
        how='left'
    )
    
    total_weight = merged['weight'].sum()
    if total_weight == 0:
        return 0.0, {}
    
    weighted_score = (merged['effectiveness_score'] * merged['weight']).sum()
    effectiveness_pct = weighted_score / total_weight
    
    category_breakdown = merged.groupby('control_category').apply(
        lambda x: (x['effectiveness_score'] * x['weight']).sum() / x['weight'].sum()
    ).to_dict()
    
    return round(effectiveness_pct, 1), category_breakdown


def calculate_business_risk(
    asset: pd.Series,
    effectiveness_pct: float
) -> float:
    criticality_mult = CRITICALITY_MULTIPLIER.get(asset['business_criticality'], 0.5)
    risk_score = criticality_mult * (100 - effectiveness_pct)
    return round(risk_score, 1)


def calculate_risk_exposure(
    asset: pd.Series,
    risk_score: float
) -> float:
    return round(asset['revenue_impact_per_hour'] * (risk_score / 100), 0)


def build_risk_dashboard_data() -> pd.DataFrame:
    assets = load_assets()
    controls = load_controls()
    asset_controls = load_asset_controls()
    
    results = []
    
    for _, asset in assets.iterrows():
        asset_id = asset['asset_id']
        
        effectiveness, category_breakdown = calculate_control_effectiveness(
            asset_id, asset_controls, controls
        )
        
        risk_score = calculate_business_risk(asset, effectiveness)
        risk_exposure = calculate_risk_exposure(asset, risk_score)
        
        asset_ctrls = asset_controls[asset_controls['asset_id'] == asset_id].copy()
        merged = asset_ctrls.merge(
            controls[['control_id', 'control_name', 'weight']],
            on='control_id',
            how='left'
        )
        weak_controls = merged.nsmallest(3, 'effectiveness_score')[
            ['control_name', 'effectiveness_score']
        ].to_dict('records')
        
        results.append({
            'asset_id': asset_id,
            'asset_name': asset['asset_name'],
            'business_owner': asset['business_owner'],
            'business_criticality': asset['business_criticality'],
            'revenue_impact_per_hour': asset['revenue_impact_per_hour'],
            'control_effectiveness': effectiveness,
            'risk_score': risk_score,
            'risk_exposure_eur_hour': risk_exposure,
            'category_breakdown': category_breakdown,
            'top_weak_controls': weak_controls
        })
    
    return pd.DataFrame(results)


def simulate_control_improvement(
    asset_id: str,
    control_id: str,
    new_effectiveness: float
) -> Dict:
    assets = load_assets()
    controls = load_controls()
    asset_controls = load_asset_controls()
    
    asset = assets[assets['asset_id'] == asset_id].iloc[0]
    
    current_eff, _ = calculate_control_effectiveness(asset_id, asset_controls, controls)
    current_risk = calculate_business_risk(asset, current_eff)
    current_exposure = calculate_risk_exposure(asset, current_risk)
    
    simulated_controls = asset_controls.copy()
    mask = (simulated_controls['asset_id'] == asset_id) & \
           (simulated_controls['control_id'] == control_id)
    simulated_controls.loc[mask, 'effectiveness_score'] = new_effectiveness
    simulated_controls.loc[mask, 'implementation_status'] = 'Implemented'
    
    new_eff, _ = calculate_control_effectiveness(asset_id, simulated_controls, controls)
    new_risk = calculate_business_risk(asset, new_eff)
    new_exposure = calculate_risk_exposure(asset, new_risk)
    
    control_name = controls[controls['control_id'] == control_id]['control_name'].iloc[0]
    
    return {
        'asset_name': asset['asset_name'],
        'control_name': control_name,
        'current_effectiveness': current_eff,
        'new_effectiveness': new_eff,
        'current_risk': current_risk,
        'new_risk': new_risk,
        'risk_reduction': current_risk - new_risk,
        'current_exposure': current_exposure,
        'new_exposure': new_exposure,
        'exposure_savings': current_exposure - new_exposure
    }