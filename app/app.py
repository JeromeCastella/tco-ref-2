from __future__ import annotations

# ...imports...






import streamlit as st
import pandas as pd

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from tco_core.models import Tech, GlobalParams, VehicleSpec
from tco_core.tco import compute_all_techs
from tco_core.defaults import get_default

TECH_LABELS = {
    'BEV': 'VE',
    'ICE': 'VT',
    'PHEV': 'VHR',
}

# Ordre d'affichage des technologies (BEV, ICE, PHEV)
TECH_ORDER = [Tech.BEV, Tech.ICE, Tech.PHEV]



try:
    from app.charts import (
        make_decomposition_df_by_post,
        fig_bar_decomposition_by_post,
        make_cum_df,
        fig_line_cumulative,
        make_expenses_by_category_df,
        fig_line_expenses_by_category,
    )
except ModuleNotFoundError:
    from charts import (
        make_decomposition_df_by_post,
        fig_bar_decomposition_by_post,
        make_cum_df,
        fig_line_cumulative,
        make_expenses_by_category_df,
        fig_line_expenses_by_category,
    )


def make_spec(tech: Tech, vehicle_class: str, fuel_price: float, elec_home: float, 
              elec_work: float, elec_public: float, w_home: float, w_work: float, 
              w_public: float, phev_share_elec: float = 0.5, 
              purchase_price: float = None, consumption_fuel: float = None, 
              consumption_elec: float = None) -> VehicleSpec:
    """Create VehicleSpec using defaults for the given tech and vehicle class."""
    defaults = get_default(tech, vehicle_class)
    
    return VehicleSpec(
        tech=tech,
        vehicle_class=vehicle_class,
        purchase_price=float(purchase_price if purchase_price is not None else defaults["purchase_price"]),
        residual_rate_8y_hint=float(defaults["residual_rate_8y_hint"]),
        consumption_fuel_l_per_100=float(consumption_fuel if consumption_fuel is not None else defaults["consumption_fuel_l_per_100"]),
        consumption_elec_kwh_per_100=float(consumption_elec if consumption_elec is not None else defaults["consumption_elec_kwh_per_100"]),
        fuel_price_chf_per_l=float(fuel_price),
        elec_price_home=float(elec_home),
        elec_price_work=float(elec_work),
        elec_price_public=float(elec_public),
        w_home=float(w_home),
        w_work=float(w_work),
        w_public=float(w_public),
        maint_6y_chf=float(defaults["maint_6y_chf"]),
        tires_base_chf=float(defaults["tires_base_chf"]),
        annual_tax_chf=float(defaults["annual_tax_chf"]),
        annual_insurance_chf=float(defaults["annual_insurance_chf"]),
        phev_share_elec=float(phev_share_elec) if tech == Tech.PHEV else 0.0,
    )


def three_sliders_sum_to_100(label_a: str, label_b: str, label_c: str, 
                              default_a: float = 0.90, default_b: float = 0.05, 
                              default_c: float = 0.05, key_prefix: str = ""):
    """Retourne (a, b, c) avec a+b+c=1.0, via 3 sliders interdépendants."""
    


    # Étape 1 : si flag de rééquilibrage, corrige les valeurs et rerun
    rebalance_flag = f"{key_prefix}_rebalance_flag"
    if st.session_state.get(rebalance_flag, False):
        vals = [
            st.session_state.get(f"{key_prefix}_slider_a", int(default_a * 100)),
            st.session_state.get(f"{key_prefix}_slider_b", int(default_b * 100)),
            st.session_state.get(f"{key_prefix}_slider_c", int(default_c * 100)),
        ]
        s = sum(vals)
        if s == 0:
            vals = [100, 0, 0]
        else:
            vals = [int(round(v * 100 / s)) for v in vals]
            diff = 100 - sum(vals)
            vals[0] += diff
        st.session_state[f"{key_prefix}_slider_a"] = vals[0]
        st.session_state[f"{key_prefix}_slider_b"] = vals[1]
        st.session_state[f"{key_prefix}_slider_c"] = vals[2]
        st.session_state[rebalance_flag] = False
        st.rerun()
        return vals[0] / 100.0, vals[1] / 100.0, vals[2] / 100.0

    # Étape 2 : affichage normal des sliders
    col1, col2, col3 = st.columns(3)
    with col1:
        val_a = st.slider(f"{label_a} (%)", 0, 100,
                         st.session_state.get(f"{key_prefix}_slider_a", int(default_a * 100)),
                         key=f"{key_prefix}_slider_a")
    with col2:
        val_b = st.slider(f"{label_b} (%)", 0, 100,
                         st.session_state.get(f"{key_prefix}_slider_b", int(default_b * 100)),
                         key=f"{key_prefix}_slider_b")
    with col3:
        val_c = st.slider(f"{label_c} (%)", 0, 100,
                         st.session_state.get(f"{key_prefix}_slider_c", int(default_c * 100)),
                         key=f"{key_prefix}_slider_c")

    total = val_a + val_b + val_c
    st.caption(f"Total: {val_a}% + {val_b}% + {val_c}% = {total}%")

    if total != 100:
        st.warning("La somme des pourcentages n'est pas égale à 100%. Vous pouvez ajuster manuellement ou cliquer sur 'Rééquilibrer'.")
        if st.button("Rééquilibrer", key=f"{key_prefix}_rebalance"):
            st.session_state[rebalance_flag] = True
            st.rerun()

    return val_a / 100.0, val_b / 100.0, val_c / 100.0


def check_decomposition(res, params, tol=0.01):
    """
    Vérifie que |NPV| ~= CAPEX_net + OPEX_actualisés (à tolérance près).
    Retourne (ok, abs_npv, capex_net, opex_disc).
    """
    r = float(params.discount_rate)
    df = res.annual_table.copy()

    df["df"] = (1.0 + r) ** df["Année"]

    e = float((df["Énergie"]     / df["df"]).sum())
    m = float((df["Maintenance"] / df["df"]).sum())
    t = float((df["Pneus"]       / df["df"]).sum())
    o = float((df["Autres"]      / df["df"]).sum()) if "Autres" in df.columns else 0.0
    opex_disc = e + m + t + o

    purchase = float(df.attrs.get("purchase_price", 0.0))
    years    = int(df["Année"].iloc[-1])
    vr_disc  = float(res.residual_value_nominal) / ((1.0 + r) ** years)
    capex_net = purchase - vr_disc

    abs_npv = abs(float(res.npv_total))
    ok = abs(abs_npv - (capex_net + opex_disc)) <= float(tol)
    return ok, abs_npv, capex_net, opex_disc


st.set_page_config(page_title="Comparateur BEV ICE PHEV", page_icon="🚗", layout="wide")

# ==================================================================
# Fin des imports et utilitaires
# ==================================================================

st.title("Comparateur Electrique vs Thermique vs Hybride")


st.markdown("### Paramètres principaux")
col1, col2, col3 = st.columns(3)

with col1:
    vehicle_class = st.selectbox(
        "Classe de véhicule",
        options=["petite", "moyenne", "superieure", "suv"],
        index=1,
        format_func=lambda x: {
            "petite": "Petites voiture",
            "moyenne": "Classe moyenne",
            "superieure": "Classe supérieure",
            "suv": "SUV"
        }[x],
        key="vehicle_class_selector"
    )

with col2:
    years = st.slider("Durée de possession (années)", 3, 15, 8)

with col3:
    km_per_year = st.number_input("Kilométrage annuel (km/an)", 0, 100_000, 15_000, step=1_000)

discount_rate = st.session_state.get('discount_rate', 0.04)
energy_inflation = st.session_state.get('energy_inflation', 0.02)
opex_inflation = st.session_state.get('opex_inflation', 0.015)
include_tires_x2 = st.session_state.get('include_tires_x2', True)
apply_maint_7_over_6 = st.session_state.get('apply_maint_7_over_6', True)
fuel_price = st.session_state.get('fuel_price', 2.00)
elec_home = st.session_state.get('elec_home', 0.20)
elec_work = st.session_state.get('elec_work', 0.20)
elec_public = st.session_state.get('elec_public', 0.50)
w_home = st.session_state.get('w_home', 0.90)
w_work = st.session_state.get('w_work', 0.05)
w_public = st.session_state.get('w_public', 0.05)
phev_share_elec = st.session_state.get('phev_share_elec', 0.50)
vehicle_care_annual = st.session_state.get('vehicle_care_annual', 150.0)
charging_infrastructure = st.session_state.get('charging_infrastructure', 3040.0)

global_params = GlobalParams(
    years=years,
    km_per_year=km_per_year,
    discount_rate=discount_rate,
    energy_inflation=energy_inflation,
    opex_inflation=opex_inflation,
    include_tires_x2=include_tires_x2,
    apply_maint_7_over_6=apply_maint_7_over_6,
    vehicle_care_annual=vehicle_care_annual,
    charging_infrastructure=charging_infrastructure,
)

spec_ice = make_spec(
    Tech.ICE, vehicle_class, fuel_price, elec_home, elec_work, 
    elec_public, w_home, w_work, w_public,
    purchase_price=st.session_state.get(f'{vehicle_class}_ice_purchase_price'),
    consumption_fuel=st.session_state.get(f'{vehicle_class}_ice_consumption_fuel')
)
spec_bev = make_spec(
    Tech.BEV, vehicle_class, fuel_price, elec_home, elec_work, 
    elec_public, w_home, w_work, w_public,
    purchase_price=st.session_state.get(f'{vehicle_class}_bev_purchase_price'),
    consumption_elec=st.session_state.get(f'{vehicle_class}_bev_consumption_elec')
)
spec_phev = make_spec(
    Tech.PHEV, vehicle_class, fuel_price, elec_home, elec_work, 
    elec_public, w_home, w_work, w_public, phev_share_elec,
    purchase_price=st.session_state.get(f'{vehicle_class}_phev_purchase_price'),
    consumption_fuel=st.session_state.get(f'{vehicle_class}_phev_consumption_fuel'),
    consumption_elec=st.session_state.get(f'{vehicle_class}_phev_consumption_elec')
)

specs_by_tech = {
    Tech.ICE: spec_ice,
    Tech.BEV: spec_bev,
    Tech.PHEV: spec_phev,
}

results = compute_all_techs(global_params, specs_by_tech)

st.divider()

df_decomp = make_decomposition_df_by_post(results, global_params)
cum_df = make_cum_df(results)

fig_bar = fig_bar_decomposition_by_post(df_decomp)
st.altair_chart(fig_bar, use_container_width=True)
# Padding vertical supplémentaire sous le bar chart pour éviter le chevauchement
st.markdown("<div style='height: 40px'></div>", unsafe_allow_html=True)

cum_df = make_cum_df(results)
fig_line = fig_line_cumulative(cum_df)
st.altair_chart(fig_line, use_container_width=True)

st.markdown('<span style="font-size:20px; font-weight:600;">Coût total par kilomètre (TCO/km)</span>', unsafe_allow_html=True)
kpi_cols = st.columns(3)
for idx, tech in enumerate(TECH_ORDER):
    res = results[tech]
    with kpi_cols[idx]:
        tco_km = res.tco_per_km
        tco_km_formatted = f"{tco_km:.2f}".replace(".", ",")
        label = TECH_LABELS.get(tech.name, tech.value)
        st.markdown(f"""
            <div style="text-align: center; padding: 10px 0;">
                <p style="margin: 0; font-size: 13px; color: #888; font-weight: 500;">{label}</p>
                <p style="margin: 5px 0 0 0; font-size: 24px; font-weight: 600; color: #333;">{tco_km_formatted} CHF/km</p>
            </div>
        """, unsafe_allow_html=True)

st.divider()
st.subheader("⚙️ Paramètres de calcul")
st.caption("Modifiez les paramètres ci-dessous pour recalculer le TCO")

with st.expander("⚙️ Coûts et consommations par technologie"):
    st.caption("Personnalisez les prix d'achat et consommations pour toutes les classes de véhicules. Les changements sont appliqués en temps réel.")
    
    # Compteur de reset pour forcer la recréation des widgets
    reset_counter = st.session_state.get('costs_reset_counter', 0)
    
    # Fonction callback pour mettre à jour les valeurs
    def update_param(source_key, target_key):
        st.session_state[target_key] = st.session_state[source_key]
    
    for class_key, class_label in [("petite", "Petites voiture"), ("moyenne", "Classe moyenne"), 
                                     ("superieure", "Classe supérieure"), ("suv", "SUV")]:
        st.markdown(f"### {class_label}")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("**VE**")
            bev_defaults = get_default(Tech.BEV, class_key)
            bev_price_key = f"{class_key}_bev_purchase_price"
            bev_elec_key = f"{class_key}_bev_consumption_elec"
            
            st.number_input(
                "Prix CHF", 
                min_value=0.0, 
                max_value=200000.0, 
                value=st.session_state.get(bev_price_key, float(bev_defaults['purchase_price'])),
                step=1000.0,
                key=f"{bev_price_key}_{reset_counter}",
                on_change=update_param,
                args=(f"{bev_price_key}_{reset_counter}", bev_price_key)
            )
            
            st.number_input(
                "kWh/100km", 
                min_value=0.0, 
                max_value=50.0, 
                value=st.session_state.get(bev_elec_key, float(bev_defaults['consumption_elec_kwh_per_100'])),
                step=0.1,
                key=f"{bev_elec_key}_{reset_counter}",
                on_change=update_param,
                args=(f"{bev_elec_key}_{reset_counter}", bev_elec_key)
            )
        
        with col2:
            st.markdown("**VT**")
            ice_defaults = get_default(Tech.ICE, class_key)
            ice_price_key = f"{class_key}_ice_purchase_price"
            ice_fuel_key = f"{class_key}_ice_consumption_fuel"
            
            st.number_input(
                "Prix CHF", 
                min_value=0.0, 
                max_value=200000.0, 
                value=st.session_state.get(ice_price_key, float(ice_defaults['purchase_price'])),
                step=1000.0,
                key=f"{ice_price_key}_{reset_counter}",
                on_change=update_param,
                args=(f"{ice_price_key}_{reset_counter}", ice_price_key)
            )
            
            st.number_input(
                "L/100km", 
                min_value=0.0, 
                max_value=30.0, 
                value=st.session_state.get(ice_fuel_key, float(ice_defaults['consumption_fuel_l_per_100'])),
                step=0.1,
                key=f"{ice_fuel_key}_{reset_counter}",
                on_change=update_param,
                args=(f"{ice_fuel_key}_{reset_counter}", ice_fuel_key)
            )
        
        with col3:
            st.markdown("**VHR**")
            phev_defaults = get_default(Tech.PHEV, class_key)
            phev_price_key = f"{class_key}_phev_purchase_price"
            phev_fuel_key = f"{class_key}_phev_consumption_fuel"
            phev_elec_key = f"{class_key}_phev_consumption_elec"
            
            st.number_input(
                "Prix CHF", 
                min_value=0.0, 
                max_value=200000.0, 
                value=st.session_state.get(phev_price_key, float(phev_defaults['purchase_price'])),
                step=1000.0,
                key=f"{phev_price_key}_{reset_counter}",
                on_change=update_param,
                args=(f"{phev_price_key}_{reset_counter}", phev_price_key)
            )
            
            st.number_input(
                "L/100km", 
                min_value=0.0, 
                max_value=30.0, 
                value=st.session_state.get(phev_fuel_key, float(phev_defaults['consumption_fuel_l_per_100'])),
                step=0.1,
                key=f"{phev_fuel_key}_{reset_counter}",
                on_change=update_param,
                args=(f"{phev_fuel_key}_{reset_counter}", phev_fuel_key)
            )
            
            st.number_input(
                "kWh/100km", 
                min_value=0.0, 
                max_value=50.0, 
                value=st.session_state.get(phev_elec_key, float(phev_defaults['consumption_elec_kwh_per_100'])),
                step=0.1,
                key=f"{phev_elec_key}_{reset_counter}",
                on_change=update_param,
                args=(f"{phev_elec_key}_{reset_counter}", phev_elec_key)
            )
        
        st.divider()
    
    if st.button("🔄 Réinitialiser aux valeurs par défaut", key="reset_costs_btn"):
        vehicle_classes = ['petite', 'moyenne', 'superieure', 'suv']
        techs = ['ice', 'bev', 'phev']
        for key in list(st.session_state.keys()):
            for vc in vehicle_classes:
                for tech in techs:
                    if key.startswith(f'{vc}_{tech}_'):
                        del st.session_state[key]
        # Incrémenter le compteur pour forcer la recréation des widgets
        st.session_state['costs_reset_counter'] = st.session_state.get('costs_reset_counter', 0) + 1
        st.rerun()

with st.expander("⚙️ Plus de paramètres (globaux)"):
    discount_rate_input = st.number_input("Taux d'actualisation r (%)", 0.0, 15.0, discount_rate * 100, step=0.5, key="dr_input") / 100.0
    energy_inflation_input = st.number_input("Inflation énergie (%/an)", -5.0, 50.0, energy_inflation * 100, step=0.5, key="ei_input") / 100.0
    opex_inflation_input = st.number_input("Inflation OPEX (%/an)", -5.0, 20.0, opex_inflation * 100, step=0.5, key="oi_input") / 100.0
    include_tires_x2_input = st.checkbox("Pneus ×2 (méthodo)", include_tires_x2, key="tires_input")
    apply_maint_7_over_6_input = st.checkbox("Maintenance règle 7/6 → 8 ans (placeholder)", apply_maint_7_over_6, key="maint_input")
    
    col_apply, col_reset = st.columns([1, 1])
    with col_apply:
        if st.button("✅ Appliquer", key="apply_global_params"):
            st.session_state['discount_rate'] = discount_rate_input
            st.session_state['energy_inflation'] = energy_inflation_input
            st.session_state['opex_inflation'] = opex_inflation_input
            st.session_state['include_tires_x2'] = include_tires_x2_input
            st.session_state['apply_maint_7_over_6'] = apply_maint_7_over_6_input
            st.rerun()
    with col_reset:
        if st.button("🔄 Réinitialiser", key="reset_global_params"):
            st.session_state['discount_rate'] = 0.04
            st.session_state['energy_inflation'] = 0.02
            st.session_state['opex_inflation'] = 0.015
            st.session_state['include_tires_x2'] = True
            st.session_state['apply_maint_7_over_6'] = True
            st.rerun()

with st.expander("⚡ Prix énergie"):
    fuel_price_input = st.number_input("Prix carburant (CHF/L)", 0.0, 5.0, fuel_price, step=0.01, key="fuel_input")
    colh, colw, colp = st.columns(3)
    with colh:
        elec_home_input = st.number_input("Élec. Maison (CHF/kWh)", 0.0, 1.0, elec_home, step=0.01, key="home_input")
    with colw:
        elec_work_input = st.number_input("Élec. Travail (CHF/kWh)", 0.0, 1.0, elec_work, step=0.01, key="work_input")
    with colp:
        elec_public_input = st.number_input("Élec. Déplacement (CHF/kWh)", 0.0, 2.0, elec_public, step=0.01, key="public_input")
    
    col_apply, col_reset = st.columns([1, 1])
    with col_apply:
        if st.button("✅ Appliquer", key="apply_energy_prices"):
            st.session_state['fuel_price'] = fuel_price_input
            st.session_state['elec_home'] = elec_home_input
            st.session_state['elec_work'] = elec_work_input
            st.session_state['elec_public'] = elec_public_input
            st.rerun()
    with col_reset:
        if st.button("🔄 Réinitialiser", key="reset_energy_prices"):
            st.session_state['fuel_price'] = 2.00
            st.session_state['elec_home'] = 0.20
            st.session_state['elec_work'] = 0.20
            st.session_state['elec_public'] = 0.50
            st.rerun()

with st.expander("🔌 Profil de recharge BEV/PHEV (Weighted Electricity Price)"):
    st.caption("Ces poids déterminent le prix d'électricité pondéré utilisé pour BEV et la portion électrique de PHEV")
    w_home_new, w_work_new, w_public_new = three_sliders_sum_to_100(
        "Maison", "Travail", "Déplacement", default_a=w_home, default_b=w_work, default_c=w_public, key_prefix="recharge"
    )
    
    from tco_core.energy import weighted_electricity_price
    weighted_price = weighted_electricity_price(elec_home, elec_work, elec_public, w_home_new, w_work_new, w_public_new)
    st.info(f"💡 Prix électrique pondéré: **{weighted_price:.3f} CHF/kWh** (utilisé pour BEV et portion électrique PHEV)")
    
    col_apply, col_reset = st.columns([1, 1])
    with col_apply:
        if st.button("✅ Appliquer", key="apply_charge_profile"):
            st.session_state['w_home'] = w_home_new
            st.session_state['w_work'] = w_work_new
            st.session_state['w_public'] = w_public_new
            st.rerun()
    with col_reset:
        if st.button("🔄 Réinitialiser", key="reset_charge_profile"):
            for key in list(st.session_state.keys()):
                if key.startswith('recharge'):
                    del st.session_state[key]
            st.session_state['w_home'] = 0.90
            st.session_state['w_work'] = 0.05
            st.session_state['w_public'] = 0.05
            st.rerun()

with st.expander("🔋 PHEV: Part électrique vs thermique"):
    st.caption("Ce paramètre définit la proportion de kilomètres parcourus en mode électrique pour le PHEV")
    phev_share_elec_input = st.slider(
        "Part électrique PHEV (%)", 
        min_value=0, 
        max_value=100, 
        value=int(phev_share_elec * 100), 
        step=5,
        key="phev_input",
        help="Pourcentage de kilomètres parcourus en mode électrique. Ex: 50% = moitié électrique, moitié thermique"
    ) / 100.0
    st.caption(f"⚡ Électrique: {int(phev_share_elec_input*100)}% • 🔥 Thermique: {int((1-phev_share_elec_input)*100)}%")
    
    col_apply, col_reset = st.columns([1, 1])
    with col_apply:
        if st.button("✅ Appliquer", key="apply_phev_share"):
            st.session_state['phev_share_elec'] = phev_share_elec_input
            st.rerun()
    with col_reset:
        if st.button("🔄 Réinitialiser", key="reset_phev_share"):
            st.session_state['phev_share_elec'] = 0.50
            st.rerun()

with st.expander("💰 Autres coûts (Taxe, Assurance, Soins, Infrastructure)"):
    st.caption("Ces paramètres permettent d'ajuster les coûts autres que l'énergie, la maintenance et les pneus (BFE/EBP 2023 section 3.6)")
    
    st.markdown("**Taxe cantonale (CHF/an)** - Moyenne suisse par segment (Source: ASA)")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.caption(f"ICE: {get_default(Tech.ICE, vehicle_class)['annual_tax_chf']:.0f} CHF/an")
    with col2:
        st.caption(f"BEV: {get_default(Tech.BEV, vehicle_class)['annual_tax_chf']:.0f} CHF/an")
    with col3:
        st.caption(f"PHEV: {get_default(Tech.PHEV, vehicle_class)['annual_tax_chf']:.0f} CHF/an")
    
    st.markdown("**Assurance (CHF/an)** - Vollkasko, profil type Aargau 43 ans (Source: Comparis)")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.caption(f"ICE: {get_default(Tech.ICE, vehicle_class)['annual_insurance_chf']:.0f} CHF/an")
    with col2:
        st.caption(f"BEV: {get_default(Tech.BEV, vehicle_class)['annual_insurance_chf']:.0f} CHF/an")
    with col3:
        st.caption(f"PHEV: {get_default(Tech.PHEV, vehicle_class)['annual_insurance_chf']:.0f} CHF/an")
    
    st.markdown("**Soins du véhicule** - Nettoyage et entretien courant (Source: TCS)")
    vehicle_care = st.number_input(
        "Coût annuel (CHF/an)",
        min_value=0.0,
        max_value=500.0,
        value=st.session_state.get('vehicle_care_annual', 150.0),
        step=10.0,
        key="vehicle_care_annual"
    )
    
    st.markdown("**Infrastructure de recharge** - Borne 11 kW pour BEV/PHEV (Source: Helion/CKW)")
    charging_infra = st.number_input(
        "Coût installation (CHF)",
        min_value=0.0,
        max_value=10000.0,
        value=st.session_state.get('charging_infrastructure', 3040.0),
        step=100.0,
        key="charging_infrastructure"
    )
    
    st.info("💡 Les valeurs de taxe et assurance sont chargées automatiquement selon la classe de véhicule sélectionnée")

with st.expander("🔧 Données techniques et exports", expanded=False):
    st.subheader("📊 Analyse par poste de dépense")
    selected_posts = st.multiselect(
        "Sélectionner les postes à afficher",
        options=["Énergie", "Maintenance", "Pneus", "Autres"],
        default=["Énergie", "Maintenance"]
    )
    cumulative_view = st.checkbox("Vue cumulée", value=False)

    expenses_df = make_expenses_by_category_df(results)
    if selected_posts:
        fig_expenses = fig_line_expenses_by_category(expenses_df, selected_posts, cumulative_view)
        st.altair_chart(fig_expenses, use_container_width=True)
    else:
        st.info("Sélectionnez au moins un poste pour afficher le graphique")

    for tech in TECH_ORDER:
        ok, abs_npv, capex_net, opex_disc = check_decomposition(results[tech], global_params, tol=0.01)
        label = TECH_LABELS.get(tech.name, tech.value)
        msg = f"{label}: |NPV|={abs_npv:,.0f} vs CAPEX_net={capex_net:,.0f} + OPEX={opex_disc:,.0f}"
        (st.success if ok else st.error)(("OK — " if ok else "Écart — ") + msg)

    st.subheader("Export")

    agg = df_decomp.pivot_table(index="Technologie", columns="Poste", values="CHF", aggfunc="sum").reset_index()

    POSTS = ["Acquisition (achat – VR act.)", "Énergie", "Maintenance", "Pneus", "Autres"]
    for p in POSTS:
        if p not in agg.columns:
            agg[p] = 0.0
    agg["Total (somme postes)"] = agg[POSTS].sum(axis=1)

    st.dataframe(agg, use_container_width=True)

    def _to_csv(df: pd.DataFrame) -> bytes:
        return df.to_csv(index=False).encode("utf-8")

    col_a, col_b, col_c, col_d = st.columns(4)
    with col_a:
        st.download_button("⬇️ Décomp. (CSV)", data=_to_csv(df_decomp), file_name="decomposition.csv", mime="text/csv")
    with col_b:
        st.download_button("⬇️ Agrégé (CSV)", data=_to_csv(agg), file_name="aggregat.csv", mime="text/csv")
    with col_c:
        st.download_button("⬇️ BEV annuel (CSV)", data=_to_csv(results[Tech.BEV].annual_table), file_name="bev_annuel.csv", mime="text/csv")
    with col_d:
        st.download_button("⬇️ ICE annuel (CSV)", data=_to_csv(results[Tech.ICE].annual_table), file_name="ice_annuel.csv", mime="text/csv")

st.markdown("## Résultats (NPV et TCO/km)")
recap = []
for tech in TECH_ORDER:
    r = results[tech]
    label = TECH_LABELS.get(tech.name, tech.value)
    recap.append({
        "Technologie": label,
        "Classe": r.vehicle_class,
        "NPV total (CHF)": f"{r.npv_total:,.0f}",
        "TCO (CHF/km)": f"{r.tco_per_km:.2f}",
    })
st.dataframe(pd.DataFrame(recap), use_container_width=True)

with st.expander("Voir la table annuelle détaillée (BEV)"):
    st.dataframe(results[Tech.BEV].annual_table, use_container_width=True)
