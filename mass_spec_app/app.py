import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io

from rga_parser import flatten_rga_wrapper
from validator import validate_air_scan
from model_engine import load_model, generate_virtual_calibration
from db import init_db, save_uploaded_file, insert_submission

# Initialize the SQLite database
init_db()

st.set_page_config(page_title="Mass Spec AI Calibration", layout="wide", page_icon="🔬")

st.title("Mass Spectrometer AI System")
st.markdown("### Powered by Gemma 2B V9 Log10 Adapter")

tab1, tab2 = st.tabs(["Contributor Portal", "Consumer Portal"])

with tab1:
    st.header("Role A: Contributor Portal")
    st.markdown("Submit Training & Calibration Data to expand the model's dataset.")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Upload Files")
        air_scan_file = st.file_uploader("Background Air Scan CSV", type=['csv'], key='contrib_air')
        cal_scan_file = st.file_uploader("Calibration Gas Scan CSV", type=['csv'], key='contrib_cal')
        spec_file = st.file_uploader("Instrument Specification File (PDF/TXT/Image)", type=['pdf', 'txt', 'png', 'jpg'], key='contrib_spec')
        
    with col2:
        st.subheader("Data Entry Form")
        with st.form("contrib_form"):
            st.markdown("**Gas Calibration Details**")
            target_gas = st.text_input("Target Gas Species (e.g., Methane CH4, Oxygen O2)")
            conc_pct = st.number_input("Calibrated Concentration (%)", min_value=0.0, max_value=100.0, step=0.1)
            ref_gas = st.text_input("Reference/Balance Gas (e.g., Nitrogen N2, Argon Ar)")
            
            st.markdown("**Mass Spectrometer Hardware Specs**")
            brand_model = st.text_input("Instrument Brand/Model")
            serial_id = st.text_input("Serial ID")
            detector_mode = st.selectbox("Detector Mode", ["Faraday Cup", "Electron Multiplier"])
            vac_pressure = st.number_input("Operating Vacuum Pressure (mBar)", format="%.2e")
            emission_current = st.number_input("Emission Current / Ionization Voltage", format="%.2f")
            
            submitted = st.form_submit_button("Submit Data")
            if submitted:
                if air_scan_file and cal_scan_file and target_gas and brand_model:
                    try:
                        # Save files locally
                        air_path = save_uploaded_file(air_scan_file, prefix="air")
                        cal_path = save_uploaded_file(cal_scan_file, prefix="cal")
                        spec_path = save_uploaded_file(spec_file, prefix="spec") if spec_file else None
                        
                        # Store in database
                        data = {
                            'target_gas': target_gas,
                            'conc_pct': conc_pct,
                            'ref_gas': ref_gas,
                            'brand_model': brand_model,
                            'serial_id': serial_id,
                            'detector_mode': detector_mode,
                            'vac_pressure': vac_pressure,
                            'emission_current': emission_current,
                            'air_scan_path': air_path,
                            'cal_scan_path': cal_path,
                            'spec_file_path': spec_path
                        }
                        
                        sub_id = insert_submission(data)
                        st.success(f"Data successfully ingested! Database Submission ID: {sub_id}")
                    except Exception as e:
                        st.error(f"Failed to store data: {e}")
                else:
                    st.error("Please upload required files and fill out the form.")

with tab2:
    st.header("Role B: Consumer Portal")
    st.markdown("Generate a virtual calibration file for your instrument instantly.")
    
    col3, col4 = st.columns(2)
    with col3:
        st.subheader("Upload Air Baseline")
        cons_air_file = st.file_uploader("Background Air Run CSV", type=['csv'], key='cons_air')
        
        st.subheader("Target Gas")
        cons_gas = st.selectbox("Select Target Calibration Gas", ["O2", "CH4", "N2O"])
        cons_conc = st.selectbox("Select Concentration", ["1%", "5%"])
        
    with col4:
        st.subheader("Instrument Specs")
        cons_brand = st.text_input("Machine Brand/Model", key="cons_brand")
        cons_vac = st.number_input("Current Baseline Vacuum Pressure (mBar)", format="%.2e", value=1e-5)
        cons_detector = st.selectbox("Detector Mode", ["Faraday Cup", "Electron Multiplier"], key="cons_det")
        
    if st.button("Generate Virtual Calibration"):
        if not cons_air_file:
            st.error("Please upload a background air run CSV.")
        else:
            with st.spinner("Parsing and Validating File..."):
                try:
                    df = flatten_rga_wrapper(cons_air_file)
                    
                    is_valid, msg = validate_air_scan(df)
                    if not is_valid:
                        st.error(msg)
                    else:
                        st.success("Air scan validated successfully.")
                        
                        st.info("Loading Gemma V9 Adapter...")
                        model, tokenizer = load_model()
                        
                        st.info("Predicting Virtual Calibration...")
                        full_gas_name = f"{cons_gas} {cons_conc}"
                        out_df, parsed_amuss = generate_virtual_calibration(df, full_gas_name, model, tokenizer, num_rows=150)
                        
                        st.success("Virtual Calibration Generated!")
                        
                        st.subheader("Multi-AMU Spectral Fingerprint Accuracy Metrics")
                        
                        # Use the real file for evaluation
                        real_file = "/Users/mi/Desktop/KTH internship/massspec_kth/dataset/zzz_converted_csv/kth/training/master_pinn_dataset.csv"
                        
                        try:
                            df_real = pd.read_csv(real_file)
                            
                            # Dictionary map for target gas amus
                            gas_fingerprints = {
                                "O2": [32, 16, 34, 33],
                                "CH4": [16, 15, 14, 13, 12],
                                "N2O": [44, 30, 45, 46, 28, 16, 14]
                            }
                            
                            # Filter source file in ground truth
                            cal_str = f"cal_{cons_gas}_{cons_conc}"
                            if "Source_File" in df_real.columns:
                                df_real_filtered = df_real[df_real["Source_File"] == cal_str].copy()
                            else:
                                df_real_filtered = df_real
                            
                            if len(df_real_filtered) == 0:
                                st.warning(f"No ground truth data found for {cal_str} in master dataset.")
                                df_real_filtered = df_real # fallback
                                
                            relevant_amus = [f"{amu}_amu" for amu in gas_fingerprints.get(cons_gas, [])]
                            if not relevant_amus:
                                relevant_amus = list(parsed_amuss.keys()) # Use predicted if not in dict
                                
                            real_means, virt_means, errors, accuracies = [], [], [], []
                            
                            for col in relevant_amus:
                                real_val = pd.to_numeric(df_real_filtered[col], errors='coerce').dropna().mean() if col in df_real_filtered.columns else 1e-15
                                virt_val = pd.to_numeric(out_df[col], errors='coerce').dropna().mean() if col in out_df.columns else 0
                                if pd.isna(real_val) or real_val <= 0: real_val = 1e-15
                                if pd.isna(virt_val) or virt_val <= 0: virt_val = 1e-15
                                    
                                error = abs((virt_val - real_val) / real_val) * 100
                                accuracy = max(0, 100 - error)
                                
                                real_means.append(real_val)
                                virt_means.append(virt_val)
                                errors.append(error)
                                accuracies.append(accuracy)
                                
                            # Show accuracy metrics as a dataframe
                            metrics_df = pd.DataFrame({
                                "AMU": relevant_amus,
                                "Real Mean (A)": real_means,
                                "Virtual Mean (A)": virt_means,
                                "Error (%)": errors,
                                "Accuracy (%)": accuracies
                            })
                            
                            st.dataframe(metrics_df.style.format({
                                "Real Mean (A)": "{:.4e}",
                                "Virtual Mean (A)": "{:.4e}",
                                "Error (%)": "{:.2f}",
                                "Accuracy (%)": "{:.2f}"
                            }))
                            
                            overall_acc = np.mean(accuracies)
                            st.metric("Overall Spectral Fingerprint Match Accuracy", f"{overall_acc:.2f}%")
                            
                            # Plotting
                            x = np.arange(len(relevant_amus))
                            width = 0.35
                            fig, ax = plt.subplots(figsize=(10, 6))
                            ax.bar(x - width/2, real_means, width, label='Real MS Pattern', color='#2b5c8f')
                            ax.bar(x + width/2, virt_means, width, label='Virtual AI Pattern (V9 Log)', color='#2e8b57')
                            ax.set_ylabel('Signal Intensity (Amperes)')
                            ax.set_title(f'Multi-AMU Spectral Fingerprint Comparison: {full_gas_name} (V9 Clean Log)')
                            ax.set_xticks(x)
                            ax.set_xticklabels(relevant_amus)
                            ax.legend()
                            ax.set_yscale('log')
                            ax.grid(axis='y', linestyle=':', alpha=0.6)
                            plt.tight_layout()
                            st.pyplot(fig)
                            
                        except Exception as e:
                            st.error(f"Could not calculate accuracy metrics: {e}")
                            
                        
                        # Download button
                        csv_buffer = io.StringIO()
                        out_df.to_csv(csv_buffer, index=False)
                        
                        conc_short = cons_conc.replace("%", "")
                        file_name = f"Virtual_Cal_{cons_gas}_{conc_short}_v9.csv"
                        
                        st.download_button(
                            label=f"Download {file_name}",
                            data=csv_buffer.getvalue(),
                            file_name=file_name,
                            mime="text/csv"
                        )
                except Exception as e:
                    st.error(f"An error occurred: {e}")
