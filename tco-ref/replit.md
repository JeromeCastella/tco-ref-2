# TCO Reference Calculator

## Overview

This is a Streamlit-based web application for calculating Total Cost of Ownership (TCO) for different vehicle technologies: Internal Combustion Engine (ICE), Battery Electric Vehicle (BEV), and Plug-in Hybrid Electric Vehicle (PHEV). The application implements the BFE/EBP 2023 methodology, a standardized Swiss framework for vehicle cost analysis.

The calculator provides detailed cost breakdowns across multiple categories including acquisition (CAPEX), energy, maintenance, tires, and other costs (taxes, insurance, vehicle care, charging infrastructure). It generates comparative analyses and visualizations to help users understand the total ownership costs over an 8-year period.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Application Framework
- **Frontend**: Streamlit web application (`app/app.py`)
- **Core Logic**: Modular Python package (`tco_core/`) with domain-specific modules
- **Testing**: Pytest-based test suite covering all core functionality
- **Configuration**: JSON-based vehicle class defaults with Swiss market data

### Core Calculation Engine (`tco_core/`)

**Design Pattern**: Separation of concerns with dedicated modules for each cost category

1. **Models (`models.py`)**: Central data structures
   - `Tech` enum: Vehicle technologies (ICE, BEV, PHEV)
   - `GlobalParams`: Calculation parameters (horizon, km/year, discount rates, inflation rates)
   - `VehicleSpec`: Vehicle-specific parameters (prices, consumption, costs)
   - `Results`: Calculation outputs with annual tables and NPV

2. **Energy Costs (`energy.py`)**: 
   - **PHEV Weighted Pricing**: Implements weighted electricity pricing for PHEVs based on charging location mix (home/work/public)
   - **Inflation Series**: Compound inflation calculations for energy prices over time
   - Rationale: PHEVs require sophisticated pricing models reflecting mixed charging behavior

3. **Maintenance (`maintenance.py`)**:
   - **7/6 Rule**: BFE/EBP 2023 methodology where years 1-6 use base cost, years 7+ apply 7/6 multiplier
   - 6-year cumulative cost as baseline, extrapolated with adjustment factor
   - Rationale: Reflects real-world maintenance patterns where costs increase slightly in later years

4. **Residual Value (`residual.py`)**:
   - **BFE/EBP 2023 Method**: Year 6 base value with linear interpolation (years < 6) or geometric extrapolation (years > 6)
   - 10% reduction factor from year 6 to year 8
   - Rationale: Industry-standard residual value curves based on Swiss market data

5. **Tire Replacement (`tires.py`)**:
   - **Discrete Replacement Logic**: Tires replaced every 40,000 km based on cumulative mileage
   - Costs occur only in replacement years, not amortized
   - Optional 2x multiplier for premium tires
   - Rationale: Reflects actual discrete purchase behavior rather than continuous amortization

6. **Cash Flow Aggregation (`cashflows.py`)**:
   - Orchestrates all cost components into annual cash flows
   - Handles inflation, discounting, and NPV calculations
   - Technology-specific logic (ICE fuel-only, BEV electric-only, PHEV mixed)

7. **Other Costs (`cashflows.py` - other_costs_series)**:
   - **Swiss Tax Averages**: Canton-specific annual vehicle taxes (ASA Tableau 16 data)
   - **Insurance**: Vollkasko premiums by segment and technology (Comparis Aargau 43-year profile)
   - **Vehicle Care**: Fixed 150 CHF/year (TCS standard)
   - **Charging Infrastructure**: One-time 3,040 CHF for BEV/PHEV (Helion/CKW market rates)

8. **Vehicle Defaults (`defaults.py`)**:
   - JSON-based configuration system for 4 vehicle classes × 3 technologies
   - Swiss market data for purchase prices, consumption, maintenance costs
   - Lazy-loaded with caching for performance

### Data Flow Architecture

1. **User Input** → Streamlit UI collects parameters
2. **Defaults Loading** → JSON configuration provides baseline values
3. **Spec Creation** → `VehicleSpec` objects instantiated with user/default values
4. **Calculation** → `compute_tco_vehicle()` orchestrates all cost modules
5. **Results** → `Results` object with annual breakdown and NPV
6. **Visualization** → Charts module renders comparative analyses

### Parameter Customization System

- **Session State Keys**: `{classe}_{tech}_{param}` format (e.g., `petite_ice_purchase_price`, `suv_bev_consumption_elec`)
- **Real-Time Updates**: All parameters update immediately using direct session_state keys (no apply buttons needed)
- **Single Expander Organization**: All calculation parameters grouped under one "🔧 Paramètres avancés" expander
  - Costs/Consumption: Purchase prices and consumption for all vehicle classes × technologies
  - Global Parameters: Discount rate, inflation rates, tire/maintenance settings
  - Energy Prices: Fuel and electricity prices (home/work/public)
  - Charge Profile: BEV/PHEV charging location weights
  - PHEV Share: Electric vs thermal split percentage
  - Other Costs: Taxes, insurance, vehicle care, charging infrastructure
- **Display-All Approach**: All vehicle classes (petite, moyenne, supérieure, SUV) × all technologies (VE, VT, VHR) shown in organized sections
- **Reset Method**: Simple page reload (F5) restores all default values

### Discount & Inflation Model

- **Dual Inflation Rates**: Separate rates for energy (volatile) and OPEX (stable)
- **Present Value Discounting**: All future cash flows discounted to year 0
- **Compound Growth**: Inflation applied annually with compound calculation
- Rationale: Reflects economic reality where energy prices behave differently from maintenance costs

### Technology-Specific Logic

**ICE**: Fuel consumption only, standard maintenance
**BEV**: Electric consumption only, reduced maintenance, charging infrastructure cost
**PHEV**: Mixed fuel/electric with weighted pricing, electric share parameter (0-100%), standard maintenance

## External Dependencies

### Python Framework & Libraries
- **Streamlit** (≥1.37): Web application framework for interactive UI
- **Pandas** (≥2.2): Data manipulation and tabular results
- **NumPy** (≥1.26): Numerical calculations
- **Plotly** (≥5.22): Interactive charting
- **Altair** (≥5.4): Declarative visualization
- **Pytest** (≥8): Testing framework

### Data Sources
- **JSON Configuration**: `data/processed/defaults_by_class.json` contains Swiss market data
  - Vehicle prices from Swiss market (2023)
  - ASA Tableau 16: Canton tax averages
  - Comparis: Insurance premiums (Aargau, 43-year profile)
  - TCS: Vehicle care costs
  - Helion/CKW: Charging infrastructure costs

### Development Environment
- **Replit Environment**: Python 3.11
- **Port Configuration**: Streamlit on port 5000 (0.0.0.0:5000)
- **CORS/XSRF**: Disabled for development ease via `.streamlit/config.toml`
- **Deployment**: Configured for autoscale deployment (stateless web app)

### Methodology Reference
- **BFE/EBP 2023**: Swiss Federal Office of Energy standardized TCO methodology
  - Residual value calculations (Section 3.x)
  - Maintenance patterns (7/6 rule)
  - Other costs categorization (Section 3.6)
  - 8-year analysis horizon standard