import streamlit as st


def apply_custom_styles() -> None:
    """Apply the modern VOS Tool 2025 CSS theme globally."""

    st.markdown(
        """
    <style>
    /* ===== ENHANCED VOS TOOL THEME 2025 ===== */

    /* Base Application Styling */
    :root {
        --primary: #3b82f6;
        --primary-hover: #2563eb;
        --bg-dark: #0f172a;
        --bg-card: rgba(15, 23, 42, 0.96);
        --text-primary: #e8edf5;
        --text-secondary: #94a3b8;
        --border-color: rgba(148, 163, 184, 0.25);
        --shadow-sm: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        --shadow-md: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
        --shadow-lg: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
        --radius-sm: 0.5rem;
        --radius-md: 0.75rem;
        --radius-lg: 1rem;
        --transition: all 0.2s ease-in-out;
    }

    .stApp {
        background: linear-gradient(135deg, #010208 0%, #0b0e14 50%, #0e1016 100%);
        background-attachment: fixed;
        min-height: 100vh;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        color: var(--text-primary);
        line-height: 1.6;
    }

    /* Grid System */
    .main .block-container {
        padding: 1.5rem 2rem;
        max-width: 1440px;
        margin: 0 auto;
        row-gap: 1.5rem;
    }

    /* Responsive Grid Layout */
    .grid {
        display: grid;
        gap: 1.5rem;
        grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
        margin-bottom: 2rem;
    }

    .grid-cols-2 {
        grid-template-columns: repeat(2, 1fr);
    }

    .grid-cols-3 {
        grid-template-columns: repeat(3, 1fr);
    }

    .grid-cols-4 {
        grid-template-columns: repeat(4, 1fr);
    }

    @media (max-width: 1024px) {
        .grid-cols-4 {
            grid-template-columns: repeat(3, 1fr);
        }
    }

    @media (max-width: 768px) {
        .grid-cols-3, .grid-cols-4 {
            grid-template-columns: repeat(2, 1fr);
        }
    }

    @media (max-width: 480px) {
        .grid, .grid-cols-2, .grid-cols-3, .grid-cols-4 {
            grid-template-columns: 1fr;
        }
        
        .main .block-container {
            padding: 1rem;
        }
    }

    /* ===== TYPOGRAPHY ===== */
    h1, h2, h3, h4, h5, h6 {
        color: #e8edf5;
        font-weight: 600;
        letter-spacing: -0.02em;
        margin-bottom: 0.85rem;
        transition: color 0.3s ease, transform 0.3s ease;
    }

    /* ===== SMOOTH TRANSITIONS ===== */
    .stTabs {
        transition: all 0.3s ease;
    }

    .stTabs [data-baseweb="tab-list"] {
        transition: all 0.3s ease;
    }

    .stTabs [data-baseweb="tab"] {
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }

    .stTabs [data-baseweb="tab"]:hover {
        transform: translateY(-2px);
        transition: all 0.2s ease;
    }

    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        transition: all 0.3s ease;
    }

    /* Smooth fade-in for content */
    .stVerticalBlock {
        animation: fadeIn 0.4s ease-in-out;
    }

    @keyframes fadeIn {
        from {
            opacity: 0;
            transform: translateY(10px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }

    /* Smooth transitions for containers */
    .stContainer {
        transition: all 0.3s ease;
    }

    /* Smooth transitions for columns */
    .stColumn {
        transition: all 0.3s ease;
    }

    /* Smooth transitions for horizontal blocks */
    .stHorizontalBlock {
        transition: all 0.3s ease;
    }

    /* Loading animation */
    .stSpinner {
        transition: opacity 0.3s ease;
    }

    /* Global Button Styles - Match Login Button Dark Theme */
    .stButton > button {
        background: linear-gradient(135deg, rgba(2, 4, 18, 0.6) 0%, rgba(2, 4, 18, 0.75) 100%) !important;
        color: #ffffff !important;
        border: 2px solid rgba(20, 20, 20, 0.9) !important;
        border-radius: 18px !important;
        padding: 0.75rem 1.5rem !important;
        font-weight: 600 !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(37, 99, 235, 0.05), 0 0 40px rgba(37, 99, 235, 0.05) !important;
        backdrop-filter: blur(16px) !important;
        text-shadow: 0 0 8px rgba(37, 99, 235, 0.08) !important;
    }

    .stButton > button:hover {
        background: linear-gradient(135deg, rgba(2, 4, 18, 0.7) 0%, rgba(2, 4, 18, 0.8) 100%) !important;
        border-color: rgba(20, 20, 20, 0.95) !important;
        transform: translateY(-2px) scale(1.02) !important;
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(37, 99, 235, 0.08), 0 0 60px rgba(37, 99, 235, 0.08) !important;
        text-shadow: 0 0 12px rgba(37, 99, 235, 0.12) !important;
    }
    
    .stButton > button:active {
        transform: translateY(0) scale(0.98) !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(37, 99, 235, 0.05), 0 0 30px rgba(37, 99, 235, 0.05) !important;
    }

    /* Smooth transitions for form elements */
    .stTextInput > div > div > input,
    .stSelectbox > div > div > div,
    .stMultiSelect > div > div > div,
    .stDateInput > div > div > input,
    .stNumberInput > div > div > input,
    .stTextArea > div > div > textarea {
        transition: all 0.2s ease;
    }

    /* Smooth transitions for expandable sections */
    .stExpander {
        transition: all 0.3s ease;
    }

    /* Smooth transitions for dataframes */
    .stDataFrame {
        transition: all 0.3s ease;
    }

    /* Smooth transitions for metrics */
    .stMetric {
        transition: all 0.3s ease;
    }

    /* Smooth transitions for charts */
    .stPlotlyChart {
        transition: opacity 0.3s ease;
    }

    h1 { font-size: 2.1rem; color: #e5e7eb; }
    h2 { font-size: 1.6rem; color: #e5e7eb; }
    h3 { font-size: 1.25rem; color: #cbd5f5; }
    p { color: #cbd5f5; font-size: 0.98rem; line-height: 1.7; }

    /* ===== ENHANCED CARDS ===== */
    .modern-card {
        background: linear-gradient(135deg, rgba(2, 4, 18, 0.75) 0%, rgba(2, 4, 18, 0.85) 100%);
        border: 1px solid rgba(20, 20, 20, 0.8);
        border-radius: var(--radius-lg);
        padding: 1.5rem;
        margin: 0.5rem 0;
        backdrop-filter: blur(16px);
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.6), 0 0 0 1px rgba(37, 99, 235, 0.05), 0 0 80px rgba(37, 99, 235, 0.05);
        transition: var(--transition);
        height: 100%;
        display: flex;
        flex-direction: column;
    }

    .modern-card .card-content {
        flex: 1;
        display: flex;
        flex-direction: column;
    }

    .metric-card {
        text-align: center;
        padding: 1.5rem 1rem;
    }

    .metric-card .metric-value {
        font-size: 2.25rem;
        font-weight: 700;
        line-height: 1.2;
        margin: 0.5rem 0;
        background: linear-gradient(135deg, rgba(37, 99, 235, 0.8), rgba(37, 99, 235, 0.6));
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-shadow: 0 0 20px rgba(37, 99, 235, 0.15);
    }

    .metric-card .metric-label {
        color: var(--text-secondary);
        font-size: 0.9rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    .modern-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 20px 40px rgba(0, 0, 0, 0.7), 0 0 0 1px rgba(37, 99, 235, 0.08), 0 0 100px rgba(37, 99, 235, 0.08);
        border-color: rgba(20, 20, 20, 0.9);
    }

    .card-header {
        border-bottom: 1px solid var(--border-color);
        padding-bottom: 1rem;
        margin-bottom: 1.25rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    .card-actions {
        display: flex;
        gap: 0.5rem;
    }

    .card-title {
        font-size: 1.5rem;
        font-weight: 600;
        margin: 0 0 0.5rem 0;
        color: var(--text-primary);
        letter-spacing: -0.01em;
        line-height: 1.3;
    }

    .card-subtitle {
        color: var(--text-secondary);
        font-size: 0.95rem;
        margin: 0 0 1.5rem 0;
        line-height: 1.5;
    }

    .card-subtitle {
        color: #9ca3af;
        font-size: 1rem;
        font-weight: 400;
        text-shadow: 0 0 4px rgba(0,0,0,0.6);
    }

    /* ===== FORM ELEMENTS ===== */
    .stTextInput > div > div > input,
    .stSelectbox > div > div > div,
    .stMultiSelect > div > div > div,
    .stDateInput > div > div > input,
    .stNumberInput > div > div > input,
    .stTextArea > div > div > textarea {
        background: linear-gradient(135deg, rgba(2, 4, 18, 0.6) 0%, rgba(2, 4, 18, 0.75) 100%) !important;
        border: 2px solid rgba(20, 20, 20, 0.8) !important;
        border-radius: 16px !important;
        color: #e8edf5 !important;
        padding: 1rem 1.5rem !important;
        font-size: 1rem !important;
        font-family: 'Inter', sans-serif !important;
        font-weight: 500 !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
        backdrop-filter: blur(16px) !important;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(37, 99, 235, 0.05), 0 0 40px rgba(37, 99, 235, 0.05) !important;
    }

    .stTextInput > div > div > input:hover:not(:focus),
    .stSelectbox > div > div > div:hover:not(:focus),
    .stMultiSelect > div > div > div:hover:not(:focus),
    .stDateInput > div > div > input:hover:not(:focus),
    .stNumberInput > div > div > input:hover:not(:focus),
    .stTextArea > div > div > textarea:hover:not(:focus) {
        border-color: rgba(20, 20, 20, 0.9) !important;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(37, 99, 235, 0.08), 0 0 50px rgba(37, 99, 235, 0.06) !important;
    }

    .stTextInput > div > div > input:focus,
    .stSelectbox > div > div > div:focus,
    .stMultiSelect > div > div > div:focus,
    .stDateInput > div > div > input:focus,
    .stNumberInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus {
        background: linear-gradient(135deg, rgba(2, 4, 18, 0.7) 0%, rgba(2, 4, 18, 0.8) 100%) !important;
        border-color: rgba(20, 20, 20, 0.95) !important;
        box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.08), 0 6px 20px rgba(0, 0, 0, 0.5), 0 0 60px rgba(37, 99, 235, 0.08) !important;
        transform: scale(1.01) translateY(-1px) !important;
    }

    /* ===== CONSISTENT FORM ELEMENT HEIGHTS ===== */
    .stSelectbox > div,
    .stMultiSelect > div {
        min-height: 3.5rem !important;
    }

    .stSelectbox > div > div,
    .stMultiSelect > div > div {
        min-height: 3.5rem !important;
    }

    /* ===== FORM LABELS ===== */
    .stTextInput > label,
    .stSelectbox > label,
    .stMultiSelect > label,
    .stDateInput > label,
    .stNumberInput > label,
    .stTextArea > label {
        color: #b4bcc8 !important;
        font-weight: 500 !important;
        font-size: 0.9rem !important;
        margin-bottom: 0.75rem !important;
        letter-spacing: 0.025em !important;
        text-transform: uppercase !important;
    }

    /* ===== BUTTONS ===== */
    /* Custom button styles for Heavy and Lite Audit buttons - Dark Theme with Subtle Blue */
    button[data-testid="baseButton-heavy_audit_btn"] {
        background: linear-gradient(135deg, rgba(2, 4, 18, 0.6) 0%, rgba(2, 4, 18, 0.75) 100%) !important;
        border: 2px solid rgba(20, 20, 20, 0.9) !important;
        box-shadow: 0 4px 14px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(37, 99, 235, 0.05), 0 0 40px rgba(37, 99, 235, 0.05) !important;
        color: #ffffff !important;
    }
    
    button[data-testid="baseButton-heavy_audit_btn"]:hover,
    button[data-testid="baseButton-heavy_audit_btn"]:focus {
        background: linear-gradient(135deg, rgba(2, 4, 18, 0.7) 0%, rgba(2, 4, 18, 0.8) 100%) !important;
        border-color: rgba(20, 20, 20, 0.95) !important;
        box-shadow: 0 8px 25px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(37, 99, 235, 0.08), 0 0 60px rgba(37, 99, 235, 0.08) !important;
    }
    
    button[data-testid="baseButton-lite_audit_btn"] {
        background: linear-gradient(135deg, rgba(2, 4, 18, 0.6) 0%, rgba(2, 4, 18, 0.75) 100%) !important;
        border: 2px solid rgba(20, 20, 20, 0.9) !important;
        box-shadow: 0 4px 14px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(37, 99, 235, 0.05), 0 0 40px rgba(37, 99, 235, 0.05) !important;
        color: #ffffff !important;
    }
    
    button[data-testid="baseButton-lite_audit_btn"]:hover,
    button[data-testid="baseButton-lite_audit_btn"]:focus {
        background: linear-gradient(135deg, rgba(2, 4, 18, 0.7) 0%, rgba(2, 4, 18, 0.8) 100%) !important;
        border-color: rgba(20, 20, 20, 0.95) !important;
        box-shadow: 0 8px 25px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(37, 99, 235, 0.08), 0 0 60px rgba(37, 99, 235, 0.08) !important;
    }

    /* Secondary button variant */
    .stButton.secondary > button {
        background: linear-gradient(135deg, rgba(2, 4, 18, 0.5) 0%, rgba(2, 4, 18, 0.65) 100%) !important;
        color: #b4bcc8 !important;
        border: 2px solid rgba(20, 20, 20, 0.8) !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(37, 99, 235, 0.05), 0 0 30px rgba(37, 99, 235, 0.05) !important;
    }

    .stButton.secondary > button:hover {
        background: linear-gradient(135deg, rgba(2, 4, 18, 0.6) 0%, rgba(2, 4, 18, 0.75) 100%) !important;
        border-color: rgba(20, 20, 20, 0.9) !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(37, 99, 235, 0.08), 0 0 50px rgba(37, 99, 235, 0.08) !important;
    }

    /* ===== MODERN TABS ===== */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background: rgba(18, 24, 36, 0.6);
        border-radius: 16px;
        padding: 8px;
        border: 1px solid rgba(100, 116, 139, 0.12);
        backdrop-filter: blur(12px);
    }

    .stTabs [data-baseweb="tab"] {
        background: transparent;
        border-radius: 12px;
        color: #7a8699;
        padding: 1rem 1.5rem;
        border: none;
        font-weight: 500;
        transition: all 0.35s ease;
        flex: 1;
        position: relative;
    }

    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background: linear-gradient(135deg, #3d7fd9, #2d5fa8);
        color: #ffffff;
        box-shadow: 0 4px 12px rgba(61, 127, 217, 0.12);
    }

    .stTabs [data-baseweb="tab"]:hover:not([aria-selected="true"]) {
        background: rgba(100, 116, 139, 0.1);
        color: #b4bcc8;
    }

    /* ===== FILE UPLOAD AREA ===== */
    .stFileUploader > div {
        background: linear-gradient(135deg, rgba(18, 24, 36, 0.9) 0%, rgba(12, 16, 24, 0.9) 100%) !important;
        border: 2px dashed rgba(148, 163, 184, 0.35) !important;
        border-radius: 16px !important;
        padding: 3rem 2rem !important;
        text-align: center !important;
        transition: all 0.35s ease !important;
        backdrop-filter: blur(12px) !important;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.6) !important;
    }

    .stFileUploader > div:hover {
        border-color: #9ca3af !important;
        background: linear-gradient(135deg, rgba(18, 24, 36, 0.95) 0%, rgba(12, 16, 24, 0.95) 100%) !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 12px 40px rgba(0, 0, 0, 0.9) !important;
    }

    /* ===== ALERTS AND MESSAGES ===== */
    .stSuccess {
        background: linear-gradient(135deg, rgba(2, 4, 18, 0.75) 0%, rgba(2, 4, 18, 0.85) 100%) !important;
        color: #3dbd6f !important;
        border: 1px solid rgba(20, 20, 20, 0.8) !important;
        border-radius: 12px !important;
        padding: 1.5rem !important;
        backdrop-filter: blur(16px) !important;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(37, 99, 235, 0.05), 0 0 40px rgba(37, 99, 235, 0.05) !important;
    }

    .stError {
        background: linear-gradient(135deg, rgba(2, 4, 18, 0.75) 0%, rgba(2, 4, 18, 0.85) 100%) !important;
        color: #e85d5d !important;
        border: 1px solid rgba(20, 20, 20, 0.8) !important;
        border-radius: 12px !important;
        padding: 1.5rem !important;
        backdrop-filter: blur(16px) !important;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(37, 99, 235, 0.05), 0 0 40px rgba(37, 99, 235, 0.05) !important;
    }

    .stWarning {
        background: linear-gradient(135deg, rgba(245, 158, 11, 0.08) 0%, rgba(217, 119, 6, 0.08) 100%) !important;
        color: #e6a820 !important;
        border: 1px solid rgba(245, 158, 11, 0.25) !important;
        border-radius: 12px !important;
        padding: 1.5rem !important;
        backdrop-filter: blur(12px) !important;
    }

    .stInfo {
        background: linear-gradient(135deg, rgba(31, 41, 55, 0.9) 0%, rgba(15, 23, 42, 0.9) 100%) !important;
        color: #e5e7eb !important;
        border: 1px solid rgba(148, 163, 184, 0.35) !important;
        border-radius: 12px !important;
        padding: 1.5rem !important;
        backdrop-filter: blur(12px) !important;
    }

    /* ===== PROGRESS BAR ===== */
    .stProgress > div > div > div {
        background: linear-gradient(90deg, rgba(37, 99, 235, 0.6), rgba(37, 99, 235, 0.4)) !important;
        border-radius: 8px !important;
        height: 8px !important;
        box-shadow: 0 0 8px rgba(61, 189, 111, 0.25) !important;
    }

    /* ===== METRICS ===== */
    .metric-container {
        background: linear-gradient(135deg, rgba(2, 4, 18, 0.75) 0%, rgba(2, 4, 18, 0.85) 100%);
        border: 1px solid rgba(20, 20, 20, 0.8);
        border-radius: 16px;
        padding: 1.5rem;
        text-align: center;
        backdrop-filter: blur(16px);
        transition: all 0.35s ease;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(37, 99, 235, 0.05), 0 0 40px rgba(37, 99, 235, 0.05);
    }

    .metric-container:hover {
        transform: translateY(-1px);
        box-shadow: 0 8px 25px rgba(0, 0, 0, 0.8);
    }

    .metric-value {
        font-size: 2rem;
        font-weight: 600;
        color: #f9fafb;
        margin-bottom: 0.5rem;
    }

    .metric-label {
        color: #7a8699;
        font-size: 0.9rem;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    /* ===== DATAFRAME STYLING ===== */
    .stDataFrame {
        background: linear-gradient(135deg, rgba(18, 24, 36, 0.95) 0%, rgba(12, 16, 24, 0.95) 100%) !important;
        border: 1px solid rgba(100, 116, 139, 0.15) !important;
        border-radius: 12px !important;
        overflow: hidden !important;
        backdrop-filter: blur(12px) !important;
    }

    .stDataFrame thead th {
        background: rgba(30, 41, 59, 0.9) !important;
        color: #e8edf5 !important;
        font-weight: 600 !important;
        padding: 1rem !important;
        border-bottom: 1px solid rgba(100, 116, 139, 0.25) !important;
    }

    .stDataFrame tbody td {
        color: #b4bcc8 !important;
        padding: 1rem !important;
        border-bottom: 1px solid rgba(100, 116, 139, 0.1) !important;
    }

    .stDataFrame tbody tr:hover {
        background: rgba(148, 163, 184, 0.08) !important;
    }

    /* ===== FOOTER ===== */
    .app-footer {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        background: rgba(10,10,12,0.95);
        backdrop-filter: blur(18px);
        border-top: 1px solid rgba(31,41,55,0.9);
        padding: 1rem 2rem;
        text-align: center;
        color: #9ca3af;
        font-size: 0.85rem;
        text-shadow: 0 0 5px rgba(0,0,0,0.4);
        z-index: 999;
        box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.2);
    }

    .app-footer a {
        color: #e5e7eb;
        text-decoration: none;
        font-weight: 500;
        transition: color 0.35s ease;
    }

    .app-footer a:hover {
        color: #f9fafb;
        text-decoration: underline;
    }

    /* Add padding to prevent overlap with fixed footer */
    .main .block-container {
        padding-bottom: 80px;
    }

    /* ===== SIDEBAR STYLING ===== */
    /* Sidebar container */
    [data-testid="stSidebar"],
    .sidebar {
        background: linear-gradient(135deg, rgba(2, 4, 18, 0.95) 0%, rgba(2, 4, 18, 1) 100%) !important;
        border-right: 1px solid rgba(20, 20, 20, 0.8) !important;
        box-shadow: none !important;
    }

    /* User Profile Section */
    .sidebar-profile {
        padding: 2rem 1.5rem 1.5rem;
        border-bottom: 1px solid rgba(100, 116, 139, 0.15);
        background: #111827;
        margin-bottom: 2rem;
        border-radius: 0 0 4px 4px;
    }

    .user-avatar-modern {
        width: 56px;
        height: 56px;
        border-radius: 4px;
        background: #4b5563;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #fff;
        font-weight: bold;
        font-size: 20px;
        margin-bottom: 1rem;
        border: 1px solid rgba(255,255,255,0.1);
    }

    .user-info-modern h4 {
        margin: 0 0 0.25rem 0;
        color: #e5e7eb;
        font-size: 18px;
        font-weight: 600;
    }

    .user-info-modern p {
        margin: 0;
        color: #9ca3af;
        font-size: 14px;
        font-weight: 400;
    }

    /* Navigation Section */
    .sidebar-nav {
        padding: 0 1.25rem;
    }

    .nav-header-modern {
        color: #9ca3af;
        font-size: 12px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-bottom: 0.5rem;
        padding: 0 0.5rem;
    }

    /* VOS brand at top of sidebar (smaller, subtle) */
    .sidebar-brand-vos {
        text-align: center;
        padding: 0.25rem 0 0.5rem;
        margin-top: -2rem;
        margin-bottom: 0.75rem;
        border-bottom: 1px solid rgba(148, 163, 184, 0.25);
    }

    .sidebar-brand-vos .vos-title {
        font-size: 1.3rem;
        font-weight: 600;
        letter-spacing: 0.08em;
        margin: 0;
    }

    .sidebar-brand-vos .vos-subtitle {
        font-size: 0.8rem;
        color: #9ca3af;
        letter-spacing: 0.08em;
        margin-top: 0.2rem;
        text-transform: uppercase;
    }

    /* Nav buttons */
    .st-key-nav_dashboard button,
    .st-key-nav_audit button,
    .st-key-nav_actions button,
    .st-key-nav_call_review button,
    .st-key-nav_phrase_management button,
    .st-key-nav_settings button {
        display: flex;
        align-items: center;
        justify-content: flex-start;
        gap: 0.5rem;
        padding: 0.5rem 0.75rem;
        font-size: 0.9rem;
    }

    /* Icon handling */
    .st-key-nav_dashboard button::before,
    .st-key-nav_audit button::before,
    .st-key-nav_actions button::before,
    .st-key-nav_call_review button::before,
    .st-key-nav_phrase_management button::before,
    .st-key-nav_settings button::before {
        content: '';
        width: 16px;
        height: 16px;
        opacity: 0.7;
        background-repeat: no-repeat;
        background-position: center;
        display: inline-block;
    }

    .st-key-nav_dashboard button::before {
        background-image: url("data:image/svg+xml,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%20width='16'%20height='16'%20viewBox='0%200%2024%2024'%20fill='none'%20stroke='%233b82f6'%20stroke-width='1.6'%20stroke-linecap='round'%20stroke-linejoin='round'%3E%3Cpath%20d='M3%2013h8V3H3z'/%3E%3Cpath%20d='M13%2021h8V11h-8z'/%3E%3Cpath%20d='M13%203h8v4h-8z'/%3E%3Cpath%20d='M3%2017h8v4H3z'/%3E%3C/svg%3E");
    }

    .st-key-nav_audit button::before {
        background-image: url("data:image/svg+xml,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%20width='16'%20height='16'%20viewBox='0%200%2024%2024'%20fill='none'%20stroke='%233b82f6'%20stroke-width='1.6'%20stroke-linecap='round'%20stroke-linejoin='round'%3E%3Cpath%20d='M9%203H5a2%202%200%200%200-2%202v14a2%202%200%200%2002%202h14a2%202%200%200%2002-2v-4'/%3E%3Cpath%20d='M9%203h6v4H9z'/%3E%3Cpath%20d='M9%2017v-6h4'/%3E%3Cpath%20d='M21%203l-6%206'/%3E%3C/svg%3E");
    }

    .st-key-nav_actions button::before {
        background-image: url("data:image/svg+xml,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%20width='16'%20height='16'%20viewBox='0%200%2024%2024'%20fill='none'%20stroke='%233b82f6'%20stroke-width='1.6'%20stroke-linecap='round'%20stroke-linejoin='round'%3E%3Cpath%20d='M12%205v14'/%3E%3Cpath%20d='M5%2012h14'/%3E%3C/svg%3E");
    }

    .st-key-nav_call_review button::before {
        background-image: url("data:image/svg+xml,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%20width='16'%20height='16'%20viewBox='0%200%2024%2024'%20fill='none'%20stroke='%233b82f6'%20stroke-width='1.6'%20stroke-linecap='round'%20stroke-linejoin='round'%3E%3Cpath%20d='M22%2016.92V19a2%202%200%2001-2.18%202%2019.79%2019.79%200%2001-8.63-3.07%2019.5%2019.5%200%2001-6-6A19.79%2019.79%200%20012%205.18%202%202%200%20014%203h2.09a2%202%200%20012%201.72%2012.44%2012.44%200%2000.7%202.81%202%202%200%2001-.45%202.11L7.91%2011.09a16%2016%200%20006%206l1.45-1.45a2%202%200%20012.11-.45%2012.44%2012.44%200%20002.81.7A2%202%200%200122%2016.92z'/%3E%3C/svg%3E");
    }

    .st-key-nav_phrase_management button::before {
        background-image: url("data:image/svg+xml,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%20width='16'%20height='16'%20viewBox='0%200%2024%2024'%20fill='none'%20stroke='%233b82f6'%20stroke-width='1.6'%20stroke-linecap='round'%20stroke-linejoin='round'%3E%3Cpath%20d='M7%208h10'/%3E%3Cpath%20d='M7%2012h6'/%3E%3Cpath%20d='M7%2016h4'/%3E%3Cpath%20d='M4%204h16v16H4z'/%3E%3C/svg%3E");
    }

    .st-key-nav_settings button::before {
        background-image: url("data:image/svg+xml,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%20width='16'%20height='16'%20viewBox='0%200%2024%2024'%20fill='none'%20stroke='%233b82f6'%20stroke-width='1.6'%20stroke-linecap='round'%20stroke-linejoin='round'%3E%3Ccircle%20cx='12'%20cy='12'%20r='3'/%3E%3Cpath%20d='M19.4%2015a1.65%201.65%200%2000.33%201.82l.06.06a2%202%200%2011-2.83%202.83l-.06-.06a1.65%201.65%200%2000-1.82-.33%201.65%201.65%200%2000-1%201.51V21a2%202%200%2001-4%200v-.09A1.65%201.65%200%20008%2019.4a1.65%201.65%200%2000-1.82.33l-.06.06a2%202%200%2011-2.83-2.83l.06-.06A1.65%201.65%200%20003.6%2015a1.65%201.65%200%2000-1.51-1H2a2%202%200%20010-4h.09A1.65%201.65%200%20003.6%208a1.65%201.65%200%2000-.33-1.82l-.06-.06a2%202%200%20112.83-2.83l.06.06A1.65%201.65%200%20008%203.6a1.65%201.65%200%20001-1.51V2a2%202%200%20014%200v.09A1.65%201.65%200%200016%203.6a1.65%201.65%200%20001.82-.33l.06-.06a2%202%200%20112.83%202.83l-.06.06A1.65%201.65%200%200019.4%208a1.65%201.65%200%20001.51%201H21a2%202%200%20010%204h-.09A1.65%201.65%200%200019.4%2015z'/%3E%3C/svg%3E");
    }

    /* Usage Metrics Section */
    .sidebar-usage {
        padding: 0.9rem 1rem;
        border-top: 1px solid rgba(148, 163, 184, 0.25);
        background: linear-gradient(135deg, #3498DB 0%, #2980B9 100%);
        margin-top: 1.2rem;
        border-radius: 12px;
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        box-shadow: 0 8px 22px rgba(15, 23, 42, 0.22);
    }

    .usage-header-modern {
        color: #f9fafb;
        font-size: 12px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 1rem;
        text-align: center;
    }

    .usage-metric-modern {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0.75rem 0;
        border-bottom: 1px solid rgba(100, 116, 139, 0.1);
    }

    .usage-metric-modern:last-child {
        border-bottom: none;
    }

    .usage-label-modern {
        color: #dbeafe;
        font-size: 14px;
        font-weight: 500;
    }

    .usage-value-modern {
        color: #f9fafb;
        font-size: 14px;
        font-weight: 700;
    }

    /* Daily Credits circular ring */
    .credits-ring {
        position: relative;
        width: 72px;
        height: 72px;
        margin: 0 auto 0.6rem auto;
    }

    .credits-ring-svg {
        width: 100%;
        height: 100%;
        transform: rotate(-90deg);
    }

    .credits-ring-bg {
        fill: none;
        stroke: rgba(209, 213, 219, 0.7);
        stroke-width: 8;
    }

    .credits-ring-progress {
        fill: none;
        stroke: #2563eb;
        stroke-width: 8;
        stroke-linecap: round;
        stroke-dasharray: 289;
        transition: stroke-dashoffset 0.35s ease-out;
    }

    .credits-ring-center {
        position: absolute;
        inset: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 13px;
        font-weight: 700;
        color: #f9fafb;
    }

    .credits-ring-number {
        letter-spacing: 0.02em;
    }

    .credits-toggle-row {
        margin-top: 0.6rem;
        text-align: center;
    }

    .credits-toggle {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 0.15rem 0.75rem;
        border-radius: 999px;
        font-size: 10px;
        font-weight: 600;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        border: 1px solid rgba(148, 163, 184, 0.8);
        color: #111827;
        background: rgba(255, 255, 255, 0.95);
    }

    .credits-toggle-active {
        box-shadow: 0 0 0 1px rgba(59, 130, 246, 0.35);
    }

    /* Logout Button */
    .sidebar-logout {
        margin: 1.5rem;
        margin-top: 2rem;
    }

    .sidebar-logout button,
    [data-testid="stSidebar"] .logout-btn button {
        width: 100% !important;
        background: linear-gradient(135deg, rgba(239, 68, 68, 0.08) 0%, rgba(220, 38, 38, 0.08) 100%) !important;
        border: 1px solid rgba(239, 68, 68, 0.25) !important;
        color: #e85d5d !important;
        border-radius: 12px !important;
        padding: 0.875rem 1rem !important;
        font-size: 14px !important;
        font-weight: 600 !important;
        cursor: pointer !important;
        transition: all 0.35s ease !important;
        backdrop-filter: blur(12px) !important;
        text-transform: uppercase !important;
        letter-spacing: 0.05em !important;
    }

    .sidebar-logout button:hover,
    [data-testid="stSidebar"] .logout-btn button:hover {
        background: linear-gradient(135deg, rgba(239, 68, 68, 0.15) 0%, rgba(220, 38, 38, 0.15) 100%) !important;
        border-color: #e85d5d !important;
        color: #ffffff !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 12px rgba(232, 93, 93, 0.25) !important;
    }

    /* Top application header bar */
    header[data-testid="stHeader"] {
        background: linear-gradient(90deg, #020617, #0f172a, #111827) !important;
        border-bottom: 1px solid rgba(15, 23, 42, 0.9) !important;
        min-height: 64px !important;
        height: 64px !important;
        display: flex;
        align-items: center;
        justify-content: flex-end;
        padding: 0 1.5rem !important;
        box-shadow: 0 4px 14px rgba(15, 23, 42, 0.9) !important;
        z-index: 980 !important;
    }
    
    /* Hide header wave container (animated wave background) */
    .header-wave-container {
        display: none !important;
    }

    .top-nav-title {
        position: fixed;
        top: 14px;
        left: 260px;
        font-size: 1.25rem;
        font-weight: 600;
        color: #e5e7eb;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        z-index: 1000;
        opacity: 0.9;
    }

    .top-user-pill {
        position: fixed;
        top: 10px;
        right: 18px;
        display: flex;
        align-items: center;
        gap: 0.6rem;
        background: rgba(15, 23, 42, 0.96);
        border-radius: 999px;
        padding: 0.35rem 1rem 0.35rem 0.55rem;
        border: 1px solid rgba(148, 163, 184, 0.6);
        box-shadow: 0 4px 14px rgba(15, 23, 42, 0.8);
        z-index: 1000;
    }

    .top-user-pill-avatar {
        width: 34px;
        height: 34px;
        border-radius: 999px;
        background: linear-gradient(135deg, #38bdf8, #6366f1);
        display: flex;
        align-items: center;
        justify-content: center;
        color: #f9fafb;
        font-size: 1rem;
        font-weight: 700;
        box-shadow: 0 0 10px rgba(59, 130, 246, 0.75);
        border: 2px solid rgba(15, 23, 42, 1);
    }

    .top-user-pill-text {
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        line-height: 1.1;
    }

    .top-user-pill-name {
        font-size: 0.95rem;
        font-weight: 600;
        color: #e5e7eb;
    }

    .top-user-pill-role {
        font-size: 0.8rem;
        font-weight: 500;
        color: #9ca3af;
    }

    .top-user-pill-logout-icon {
        width: 32px;
        height: 32px;
        border-radius: 999px;
        border: 1px solid rgba(148, 163, 184, 0.7);
        display: flex;
        align-items: center;
        justify-content: center;
        color: #e5e7eb;
        font-size: 0.8rem;
        opacity: 0.8;
    }

    .top-user-pill-logout-icon:hover {
        background: rgba(148, 163, 184, 0.15);
        opacity: 1;
    }

    /* Hide default Streamlit elements */
    #MainMenu { display: none !important; }
    footer { display: none !important; }

    @media (max-width: 768px) {
        .top-user-pill {
            display: none;
        }

        .main .block-container {
            padding: 1rem 1.5rem !important;
        }
    }
    </style>
    """,
        unsafe_allow_html=True,
    )


def render_header_bar(active_section: str, display_name: str, avatar_letter: str, role_label: str, username: str) -> None:
    """Render the top application header bar (title + user pill).

    This centralizes the header UI markup so the main app can call it
    instead of embedding raw HTML.
    """

    # Dynamic header title based on active nav tab
    st.markdown(
        f"""
        <div class="top-nav-title">{active_section}</div>
        """,
        unsafe_allow_html=True,
    )

    # User pill on the right
    st.markdown(
        f"""
        <div class="top-user-pill">
            <div class="top-user-pill-avatar">{avatar_letter}</div>
            <div class="top-user-pill-text">
                <div class="top-user-pill-name">{display_name}</div>
                <div class="top-user-pill-role">{role_label}</div>
            </div>
            <div class="top-user-pill-logout-icon">
                <a href="?header_logout=1&header_logout_user={username}" target="_self" style="display:flex;align-items:center;justify-content:center;color:inherit;text-decoration:none;">
                    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                        <polyline points="16 17 21 12 16 7" />
                        <line x1="21" y1="12" x2="9" y2="12" />
                    </svg>
                </a>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def apply_login_styles() -> None:
    """Apply CSS specific to the login page layout and theming."""

    st.markdown(
        """
    <style>
    /* Login page specific styling */

    /* ============================================
       DEEP SPACE BACKGROUND - Login Page Only (Sandra AI Style)
       ============================================ */
    .stApp {
        background-color: #010208 !important; /* Near-black base (darker) */
        background-image: 
            /* Subtle Particle Texture (granular depth) - minimal blue */
            radial-gradient(circle at 15% 25%, rgba(37, 99, 235, 0.01) 0%, transparent 2%),
            radial-gradient(circle at 85% 35%, rgba(37, 99, 235, 0.008) 0%, transparent 1.5%),
            radial-gradient(circle at 45% 70%, rgba(30, 58, 138, 0.01) 0%, transparent 2%),
            radial-gradient(circle at 25% 60%, rgba(37, 99, 235, 0.008) 0%, transparent 1.8%),
            radial-gradient(circle at 75% 50%, rgba(30, 58, 138, 0.01) 0%, transparent 2%),
            radial-gradient(circle at 35% 80%, rgba(37, 99, 235, 0.01) 0%, transparent 1.5%),
            radial-gradient(circle at 65% 20%, rgba(30, 58, 138, 0.008) 0%, transparent 2%),
            radial-gradient(circle at 55% 90%, rgba(37, 99, 235, 0.01) 0%, transparent 1.8%),
            /* Top Accent Glow (visual balance) - subtle */
            radial-gradient(ellipse at 50% 0%, rgba(37, 99, 235, 0.03) 0%, transparent 40%),
            /* Secondary Center Glow (inner orb for depth) - minimal */
            radial-gradient(circle at 50% 45%, rgba(37, 99, 235, 0.04) 0%, transparent 30%),
            /* Primary Center Spotlight (behind login card) - subtle hint */
            radial-gradient(circle at 50% 45%, rgba(37, 99, 235, 0.08) 0%, transparent 65%),
            /* Ambient Side Glows (left and right for depth) - minimal */
            radial-gradient(ellipse at 20% 50%, rgba(30, 58, 138, 0.02) 0%, transparent 50%),
            radial-gradient(ellipse at 80% 50%, rgba(30, 58, 138, 0.02) 0%, transparent 50%),
            /* Secondary Bottom Glow (depth layer) - subtle */
            radial-gradient(ellipse at 50% 100%, rgba(30, 58, 138, 0.05) 0%, transparent 60%),
            /* Primary Bottom Horizon Glow - minimal */
            radial-gradient(ellipse at 50% 100%, rgba(30, 58, 138, 0.08) 0%, transparent 80%) !important;
        background-attachment: fixed !important;
        background-size: cover !important;
        background-repeat: no-repeat !important;
    }

    /* Completely hide Streamlit header on login page */
    header[data-testid="stHeader"] {
        display: none !important;
    }
    
    /* Hide header toolbar and deploy button on login page */
    .stAppToolbar[data-testid="stToolbar"],
    .stAppDeployButton[data-testid="stAppDeployButton"],
    .stMainMenu[data-testid="stMainMenu"] {
        display: none !important;
    }
    
    /* Remove gap above VOS header card - target Streamlit's main container */
    [data-testid="stMainBlockContainer"],
    div[class*="st-emotion-cache"][data-testid="stMainBlockContainer"],
    .block-container[data-testid="stMainBlockContainer"],
    .main .block-container {
        padding-top: 0 !important;
        padding: 0 1rem 10rem !important;
    }
    .login-header {
        background: linear-gradient(135deg, #161b22 0%, #1c2128 100%);
        padding: 2rem;
        border-bottom: 1px solid #30363d;
        margin: -0.5rem -1rem 1.25rem -1rem;
        text-align: center;
    }
    
    .login-title {
        color: #f0f6fc;
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
        letter-spacing: -0.5px;
    }
    
    .login-subtitle {
        color: #9ca3af;
        font-size: 1.2rem;
        font-weight: 500;
        margin-bottom: 0;
    }
    
    .login-card {
        background: linear-gradient(135deg, rgba(2, 4, 18, 0.75) 0%, rgba(2, 4, 18, 0.85) 100%);
        border: 1px solid rgba(20, 20, 20, 0.8);
        border-radius: 24px;
        padding: 3rem;
        margin: 1rem auto;
        max-width: 450px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.6), 0 0 0 1px rgba(37, 99, 235, 0.05), 0 0 80px rgba(37, 99, 235, 0.05);
        backdrop-filter: blur(16px);
    }
    
    /* Ensure form elements are styled within the card */
    .stForm {
        background: linear-gradient(135deg, rgba(2, 4, 18, 0.75) 0%, rgba(2, 4, 18, 0.85) 100%) !important;
        border: 1px solid rgba(20, 20, 20, 0.8) !important;
        border-radius: 24px !important;
        padding: 3rem !important;
        margin: 1rem auto !important;
        max-width: 450px !important;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.6), 0 0 0 1px rgba(37, 99, 235, 0.05), 0 0 80px rgba(37, 99, 235, 0.05) !important;
        backdrop-filter: blur(16px) !important;
        position: relative !important;
        overflow: hidden !important;
        /* Animation - form starts visible but animates in smoothly */
        animation: slideUpScaleIn 0.6s cubic-bezier(0.4, 0, 0.2, 1) 0.5s forwards,
                   formGlowPulse 4s ease-in-out 1.1s infinite !important;
        will-change: opacity, transform, box-shadow;
    }
    
    /* Wave animations for login card - synced with header */
    .stForm::before,
    .stForm::after {
        content: '';
        position: absolute;
        width: 100%;
        height: 100%;
        top: 0;
        left: -100%;
        animation: wave-slide 4s ease-in-out infinite !important;
        pointer-events: none;
        z-index: 0;
        mix-blend-mode: screen;
    }
    
    .stForm::before {
        background: linear-gradient(90deg, transparent, rgba(37, 99, 235, 0.08), transparent) !important;
        animation-delay: 0s;
    }
    
    .stForm::after {
        background: linear-gradient(90deg, transparent, rgba(30, 58, 138, 0.06), transparent) !important;
        animation-delay: 1s;
    }
    
    /* Wave slide animation keyframe */
    @keyframes wave-slide {
        0% { left: -100%; }
        100% { left: 100%; }
    }
    
    /* Ensure form content stays above waves */
    .stForm > * {
        position: relative;
        z-index: 1;
    }
    
    .login-card-title {
        color: #e8edf5;
        font-size: 1.75rem;
        font-weight: 600;
        text-align: center;
        margin-bottom: 0.75rem;
    }
    
    .login-card-description {
        color: #7a8699;
        text-align: center;
        margin-bottom: 2.5rem;
        font-size: 1rem;
        line-height: 1.5;
    }
    
    .login-description {
        color: #9ca3af;
        text-align: center;
        font-size: 0.9rem;
        font-style: italic;
        margin-top: 0.5rem;
        opacity: 0.9;
    }
    
    /* Enhanced login button - Glassy Bold Style Matching Login Card */
    /* Target all possible button selectors for maximum compatibility */
    .stForm .stButton > button,
    .stForm button[data-testid*="stBaseButton"],
    .stForm button[kind="secondaryFormSubmit"],
    .stForm button[data-testid="stBaseButton-secondaryFormSubmit"],
    .stForm button.st-emotion-cache-1anq8dj {
        background: linear-gradient(135deg, rgba(2, 4, 18, 0.6) 0%, rgba(2, 4, 18, 0.75) 100%) !important;
        color: #ffffff !important;
        border: 2px solid rgba(20, 20, 20, 0.9) !important;
        border-radius: 18px !important;
        padding: 1rem 2.5rem !important;
        font-size: 1.1rem !important;
        font-weight: 700 !important;
        letter-spacing: 0.05em !important;
        width: 100% !important;
        height: auto !important;
        cursor: pointer !important;
        text-transform: uppercase !important;
        box-shadow: 0 6px 24px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(37, 99, 235, 0.08), 0 0 60px rgba(37, 99, 235, 0.05) !important;
        backdrop-filter: blur(16px) !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
        text-shadow: 0 0 10px rgba(37, 99, 235, 0.08) !important;
        position: relative !important;
        overflow: hidden !important;
    }
    
    .stForm .stButton > button:hover,
    .stForm button[data-testid*="stBaseButton"]:hover,
    .stForm button[kind="secondaryFormSubmit"]:hover,
    .stForm button[data-testid="stBaseButton-secondaryFormSubmit"]:hover,
    .stForm button.st-emotion-cache-1anq8dj:hover {
        background: linear-gradient(135deg, rgba(2, 4, 18, 0.7) 0%, rgba(2, 4, 18, 0.8) 100%) !important;
        border-color: rgba(20, 20, 20, 0.95) !important;
        transform: translateY(-2px) scale(1.02) !important;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.6), 0 0 0 1px rgba(37, 99, 235, 0.12), 0 0 80px rgba(37, 99, 235, 0.08) !important;
        text-shadow: 0 0 15px rgba(37, 99, 235, 0.12) !important;
    }
    
    .stForm .stButton > button:active,
    .stForm button[data-testid*="stBaseButton"]:active,
    .stForm button[kind="secondaryFormSubmit"]:active,
    .stForm button[data-testid="stBaseButton-secondaryFormSubmit"]:active,
    .stForm button.st-emotion-cache-1anq8dj:active {
        transform: translateY(0) scale(0.98) !important;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(37, 99, 235, 0.08), 0 0 50px rgba(37, 99, 235, 0.05) !important;
        transition: all 0.15s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }
    
    /* Style the text inside the button */
    .stForm .stButton > button p,
    .stForm button[data-testid*="stBaseButton"] p,
    .stForm button[kind="secondaryFormSubmit"] p,
    .stForm button[data-testid="stBaseButton-secondaryFormSubmit"] p {
        color: #ffffff !important;
        font-weight: 700 !important;
        font-size: 1.1rem !important;
        letter-spacing: 0.05em !important;
        text-transform: uppercase !important;
        text-shadow: 0 0 10px rgba(37, 99, 235, 0.08) !important;
        margin: 0 !important;
    }
    
    .login-footer {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        background: linear-gradient(135deg, rgba(8, 12, 18, 0.98) 0%, rgba(12, 16, 24, 0.98) 100%);
        border-top: 1px solid rgba(100, 116, 139, 0.15);
        padding: 1rem 2rem;
        text-align: center;
        color: #7a8699;
        font-size: 0.85rem;
        backdrop-filter: blur(12px);
        z-index: 999;
        box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.2);
    }
    
    .login-footer a {
        color: #e5e7eb;
        text-decoration: none;
    }
    
    /* Login page input field styling - Glassy Bold Style Matching Login Card */
    .stTextInput > div > div > input {
        background: linear-gradient(135deg, rgba(2, 4, 18, 0.6) 0%, rgba(2, 4, 18, 0.75) 100%) !important;
        border: 2px solid rgba(20, 20, 20, 0.8) !important; /* Dark border with subtle blue glow */
        border-radius: 16px !important;
        color: #e8edf5 !important;
        padding: 1rem 1.5rem !important;
        font-size: 1rem !important;
        font-family: 'Inter', sans-serif !important;
        font-weight: 500 !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
        backdrop-filter: blur(16px) !important;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(37, 99, 235, 0.05), 0 0 40px rgba(37, 99, 235, 0.05) !important;
        position: relative !important;
    }

    .stTextInput > div > div > input:hover:not(:focus) {
        border-color: rgba(20, 20, 20, 0.9) !important;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(37, 99, 235, 0.08), 0 0 50px rgba(37, 99, 235, 0.06) !important;
        transform: translateY(-0.5px) !important;
    }

    .stTextInput > div > div > input:focus {
        background: linear-gradient(135deg, rgba(2, 4, 18, 0.7) 0%, rgba(2, 4, 18, 0.8) 100%) !important;
        border-color: rgba(20, 20, 20, 0.95) !important; /* Dark border with subtle blue hint */
        box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.08), 0 6px 20px rgba(0, 0, 0, 0.5), 0 0 60px rgba(37, 99, 235, 0.08) !important; /* Multi-layer glow - minimal */
        transform: scale(1.01) translateY(-1px) !important;
    }

    .stTextInput > div > div > input::placeholder {
        color: rgba(184, 188, 200, 0.6) !important;
        font-weight: 400 !important;
    }

    .stTextInput > label {
        color: #b4bcc8 !important;
        font-weight: 600 !important; /* Increased from 500 for bold appearance */
        font-size: 0.9rem !important;
        margin-bottom: 0.75rem !important;
        letter-spacing: 0.025em !important;
        text-transform: uppercase !important;
        transition: color 0.3s ease !important;
    }
    
    /* Label accent on input focus */
    .stTextInput:has(input:focus) > label {
        color: rgba(37, 99, 235, 0.2) !important;
    }
    
    /* Password visibility toggle button - Glassy Bold Style */
    .stTextInput button[aria-label*="password"],
    .stTextInput button[title*="password"],
    .stTextInput button[aria-label*="Show password"],
    .stTextInput button[title*="Show password"] {
        background: linear-gradient(135deg, rgba(2, 4, 18, 0.6) 0%, rgba(2, 4, 18, 0.75) 100%) !important;
        border: 2px solid rgba(20, 20, 20, 0.8) !important;
        border-radius: 12px !important;
        padding: 0.5rem !important;
        min-width: 40px !important;
        height: 40px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        cursor: pointer !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
        backdrop-filter: blur(16px) !important;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(37, 99, 235, 0.05), 0 0 40px rgba(37, 99, 235, 0.05) !important;
        position: relative !important;
        overflow: hidden !important;
    }
    
    /* Password toggle button SVG icon styling */
    .stTextInput button[aria-label*="password"] svg,
    .stTextInput button[title*="password"] svg,
    .stTextInput button[aria-label*="Show password"] svg,
    .stTextInput button[title*="Show password"] svg {
        width: 20px !important;
        height: 20px !important;
        fill: rgba(37, 99, 235, 0.2) !important;
        transition: all 0.3s ease !important;
    }
    
    /* Password toggle button hover state */
    .stTextInput button[aria-label*="password"]:hover,
    .stTextInput button[title*="password"]:hover,
    .stTextInput button[aria-label*="Show password"]:hover,
    .stTextInput button[title*="Show password"]:hover {
        background: linear-gradient(135deg, rgba(2, 4, 18, 0.7) 0%, rgba(2, 4, 18, 0.8) 100%) !important;
        border-color: rgba(20, 20, 20, 0.95) !important;
        transform: translateY(-1px) scale(1.05) !important;
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(37, 99, 235, 0.1), 0 0 60px rgba(37, 99, 235, 0.08) !important;
    }
    
    .stTextInput button[aria-label*="password"]:hover svg,
    .stTextInput button[title*="password"]:hover svg,
    .stTextInput button[aria-label*="Show password"]:hover svg,
    .stTextInput button[title*="Show password"]:hover svg {
        fill: rgba(37, 99, 235, 0.3) !important;
        transform: scale(1.1) !important;
    }
    
    /* Password toggle button active state */
    .stTextInput button[aria-label*="password"]:active,
    .stTextInput button[title*="password"]:active,
    .stTextInput button[aria-label*="Show password"]:active,
    .stTextInput button[title*="Show password"]:active {
        transform: translateY(0) scale(0.95) !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(37, 99, 235, 0.05), 0 0 30px rgba(37, 99, 235, 0.05) !important;
        transition: all 0.15s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }
    
    /* ============================================
       PAGE-LOAD ANIMATIONS
       ============================================ */
    
    /* Header animations - staggered fade-in */
    .login-header-animated {
        opacity: 0.5; /* Start slightly visible */
        animation: fadeInUp 0.6s ease-out 0.1s forwards;
        will-change: opacity, transform;
    }
    
    .login-title-animated {
        opacity: 0.6; /* Start slightly visible */
        animation: fadeInUp 0.5s ease-out 0.2s forwards;
        will-change: opacity, transform;
    }
    
    .login-subtitle-animated {
        opacity: 0.5; /* Start slightly visible */
        animation: fadeInUp 0.5s ease-out 0.3s forwards;
        will-change: opacity, transform;
    }
    
    .login-tagline-animated {
        opacity: 0.4; /* Start slightly visible */
        animation: fadeInUp 0.5s ease-out 0.4s forwards;
        will-change: opacity, transform;
    }
    
    
    /* Input field animations - sequential */
    .login-input-1 {
        opacity: 0.7; /* Start slightly visible */
        transform: translateY(10px);
        animation: fadeInUp 0.4s ease-out 0.7s forwards;
        will-change: opacity, transform;
    }
    
    .login-input-2 {
        opacity: 0.7; /* Start slightly visible */
        transform: translateY(10px);
        animation: fadeInUp 0.4s ease-out 0.8s forwards;
        will-change: opacity, transform;
    }
    
    .login-button-wrapper {
        opacity: 0.8; /* Start slightly visible */
        transform: scale(0.98);
        animation: scaleIn 0.4s ease-out 0.9s forwards;
        will-change: opacity, transform;
    }
    
    /* Footer animation */
    .login-footer-animated {
        opacity: 0.6; /* Start slightly visible */
        transform: translateY(15px);
        animation: fadeInUp 0.5s ease-out 1s forwards;
        will-change: opacity, transform;
    }
    
    /* ============================================
       BACKGROUND MOTION ANIMATIONS
       ============================================ */
    
    /* Animated gradient background */
    .main {
        background: linear-gradient(135deg, #0a0f1a 0%, #0f1419 25%, #0a0f1a 50%, #0f1419 75%, #0a0f1a 100%);
        background-size: 400% 400%;
        animation: gradientShift 60s ease infinite;
    }
    
    /* Subtle particle effect using pseudo-elements */
    .login-header-animated::before,
    .login-header-animated::after {
        content: '';
        position: absolute;
        width: 4px;
        height: 4px;
        background: rgba(37, 99, 235, 0.05);
        border-radius: 50%;
        pointer-events: none;
        animation: particleFloat 20s ease-in-out infinite;
    }
    
    .login-header-animated::before {
        top: 20%;
        left: 15%;
        animation-delay: 0s;
    }
    
    .login-header-animated::after {
        top: 60%;
        right: 20%;
        animation-delay: 3s;
        width: 3px;
        height: 3px;
        background: rgba(37, 99, 235, 0.04);
    }
    
    /* Pulsing glow animation keyframe */
    @keyframes formGlowPulse {
        0%, 100% {
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.6), 0 0 0 1px rgba(37, 99, 235, 0.05), 0 0 80px rgba(37, 99, 235, 0.05);
        }
        50% {
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.6), 0 0 0 1px rgba(37, 99, 235, 0.08), 0 0 100px rgba(37, 99, 235, 0.08);
        }
    }
    
    /* ============================================
       ENHANCED MICRO-INTERACTIONS
       ============================================ */
    
    /* Input field focus enhancements - Updated to match glassy style */
    /* Note: Main input styling is defined in login page input field styling section */
    /* This section ensures consistency across all input interactions */
    
    /* Button micro-interactions - Ripple effect for glassy button */
    .stForm .stButton > button::before,
    .stForm button[data-testid*="stBaseButton"]::before,
    .stForm button[kind="secondaryFormSubmit"]::before {
        content: '';
        position: absolute;
        top: 50%;
        left: 50%;
        width: 0;
        height: 0;
        border-radius: 50%;
        background: rgba(37, 99, 235, 0.08);
        transform: translate(-50%, -50%);
        transition: width 0.6s, height 0.6s;
        pointer-events: none;
        z-index: 0;
    }
    
    .stForm .stButton > button:hover::before,
    .stForm button[data-testid*="stBaseButton"]:hover::before,
    .stForm button[kind="secondaryFormSubmit"]:hover::before {
        width: 300px;
        height: 300px;
    }
    
    /* Ensure button text stays above ripple effect */
    .stForm .stButton > button > *,
    .stForm button[data-testid*="stBaseButton"] > *,
    .stForm button[kind="secondaryFormSubmit"] > * {
        position: relative;
        z-index: 1;
    }
    
    /* ============================================
       FORM VALIDATION ANIMATIONS
       ============================================ */
    
    /* Shake animation for invalid inputs */
    @keyframes shake {
        0%, 100% { transform: translateX(0); }
        10%, 30%, 50%, 70%, 90% { transform: translateX(-8px); }
        20%, 40%, 60%, 80% { transform: translateX(8px); }
    }
    
    .stTextInput.error-shake > div > div > input {
        animation: shake 0.5s ease-in-out;
        border-color: rgba(239, 68, 68, 0.6) !important;
        box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.15) !important;
    }
    
    /* Pulse animation for error states */
    @keyframes errorPulse {
        0%, 100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4); }
        50% { box-shadow: 0 0 0 4px rgba(239, 68, 68, 0); }
    }
    
    .stTextInput.error-pulse > div > div > input {
        animation: errorPulse 0.6s ease-in-out;
    }
    
    /* Success checkmark animation */
    @keyframes checkmark {
        0% { transform: scale(0) rotate(45deg); opacity: 0; }
        50% { transform: scale(1.2) rotate(45deg); opacity: 1; }
        100% { transform: scale(1) rotate(45deg); opacity: 1; }
    }
    
    /* ============================================
       ANIMATION KEYFRAMES
       ============================================ */
    
    @keyframes fadeInUp {
        from {
            opacity: 0;
            transform: translateY(20px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    @keyframes slideUpScaleIn {
        from {
            opacity: 0.3;
            transform: translateY(20px) scale(0.98);
        }
        to {
            opacity: 1;
            transform: translateY(0) scale(1);
        }
    }
    
    @keyframes scaleIn {
        from {
            opacity: 0;
            transform: scale(0.95);
        }
        to {
            opacity: 1;
            transform: scale(1);
        }
    }
    
    @keyframes gradientShift {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }
    
    @keyframes particleFloat {
        0%, 100% {
            transform: translate(0, 0) scale(1);
            opacity: 0.15;
        }
        25% {
            transform: translate(20px, -30px) scale(1.2);
            opacity: 0.25;
        }
        50% {
            transform: translate(-15px, -50px) scale(0.8);
            opacity: 0.1;
        }
        75% {
            transform: translate(30px, -20px) scale(1.1);
            opacity: 0.2;
        }
    }
    
    @keyframes pulseGlow {
        0%, 100% {
            opacity: 0.3;
            transform: translate(-50%, -50%) scale(1);
        }
        50% {
            opacity: 0.6;
            transform: translate(-50%, -50%) scale(1.1);
        }
    }
    
    /* ============================================
       PERFORMANCE OPTIMIZATIONS
       ============================================ */
    
    /* Reduce motion for accessibility */
    @media (prefers-reduced-motion: reduce) {
        .login-header-animated,
        .login-title-animated,
        .login-subtitle-animated,
        .login-tagline-animated,
        .login-card-animated,
        .login-input-1,
        .login-input-2,
        .login-button-wrapper,
        .login-footer-animated {
            animation: none !important;
            opacity: 1 !important;
            transform: none !important;
        }
        
        .main {
            animation: none !important;
        }
        
        .login-header-animated::before,
        .login-header-animated::after {
            animation: none !important;
            display: none !important;
        }
        
        .stForm {
            animation: none !important;
        }
        
        .stTextInput > div > div > input,
        .stForm .stButton > button {
            transition: none !important;
        }
    }
    
    /* Mobile optimizations - simpler animations */
    @media (max-width: 768px) {
        .login-header-animated::before,
        .login-header-animated::after {
            display: none;
        }
        
        .stForm {
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(100, 116, 139, 0.08) !important;
        }
        
        .stForm .stButton > button:hover {
            transform: translateY(-1px) scale(1.01) !important;
        }
    }
    </style>
    """,
        unsafe_allow_html=True,
    )

