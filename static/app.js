/* ===================================================================
   KTH Mass Spectrometry Calibration Platform - Client Application
   Academic Light Theme with rgb(0, 0, 93) Branding
   Authentication (Google & Org Email) + Tracking & File Repository
   =================================================================== */

document.addEventListener('DOMContentLoaded', () => {
  // Application State
  let currentUser = null;
  let useSampleAir = false;
  let activeAirFile = null;
  let latestPredictionData = null;
  let currentYScale = 'linear'; // 'linear' or 'log'
  let chartMode = 'primary'; // 'primary' or 'multi'

  // Standard and common mass spectrometry calibration gases
  const COMMON_GASES = [
    { name: "Oxygen", formula: "O2", display: "Oxygen (O2)", defaultConc: 1.0, benchmark: "cal_O2_1%" },
    { name: "Methane", formula: "CH4", display: "Methane (CH4)", defaultConc: 5.0, benchmark: "cal_CH4_5%" },
    { name: "Nitrous Oxide", formula: "N2O", display: "Nitrous Oxide (N2O)", defaultConc: 1.0, benchmark: "cal_N2O_1%" },
    { name: "Carbon Dioxide", formula: "CO2", display: "Carbon Dioxide (CO2)", defaultConc: 1.0, benchmark: "Synthetic" },
    { name: "Hydrogen", formula: "H2", display: "Hydrogen (H2)", defaultConc: 1.0, benchmark: "Synthetic" },
    { name: "Carbon Monoxide", formula: "CO", display: "Carbon Monoxide (CO)", defaultConc: 1.0, benchmark: "Synthetic" },
    { name: "Argon", formula: "Ar", display: "Argon (Ar)", defaultConc: 1.0, benchmark: "Synthetic" },
    { name: "Nitrogen", formula: "N2", display: "Nitrogen (N2)", defaultConc: 1.0, benchmark: "Synthetic" },
    { name: "Helium", formula: "He", display: "Helium (He)", defaultConc: 1.0, benchmark: "Synthetic" },
    { name: "Water Vapor", formula: "H2O", display: "Water Vapor (H2O)", defaultConc: 1.0, benchmark: "Synthetic" }
  ];

  // Standard Notification Toast
  function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `<span>${message}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      toast.style.transition = 'opacity 0.2s, transform 0.2s';
      setTimeout(() => toast.remove(), 250);
    }, 4500);
  }

  // ---------------------------------------------------------
  // USER AUTHENTICATION & SESSION MANAGEMENT
  // ---------------------------------------------------------
  const btnHeaderSignin = document.getElementById('btn-header-signin');
  const userInitialsWrapper = document.getElementById('user-initials-wrapper');
  const userInitialsCircle = document.getElementById('user-initials-circle');
  const userDropdownMenu = document.getElementById('user-dropdown-menu');
  const dropdownUserName = document.getElementById('dropdown-user-name');
  const dropdownUserEmail = document.getElementById('dropdown-user-email');
  const dropdownUserOrg = document.getElementById('dropdown-user-org');
  const btnLogout = document.getElementById('btn-logout');
  const contribAuthName = document.getElementById('contrib-auth-name');
  const contribAuthOrg = document.getElementById('contrib-auth-org');
  const btnChangeContributor = document.getElementById('btn-change-contributor');

  // Gatekeeping Modal
  const modalGate = document.getElementById('modal-gate');
  const gateModalTitle = document.getElementById('gate-modal-title');
  const gateActionTitle = document.getElementById('gate-action-title');
  const gateModalMsg = document.getElementById('gate-modal-msg');
  const btnGateSignin = document.getElementById('btn-gate-signin');
  const btnCancelGate = document.getElementById('btn-cancel-gate');
  const btnCloseGateModal = document.getElementById('btn-close-gate-modal');

  // Prediction History elements
  const historyAuthGate = document.getElementById('history-auth-gate');
  const historyContentCard = document.getElementById('history-content-card');

  function getInitials(name, email) {
    if (!name && email) return email.slice(0, 2).toUpperCase();
    const cleanName = (name || '').trim();
    const parts = cleanName.split(/\s+/).filter(p => !['dr', 'dr.', 'prof', 'prof.', 'mr', 'mr.', 'ms', 'mrs'].includes(p.toLowerCase()));
    if (parts.length === 0) return (cleanName.slice(0, 2) || 'MI').toUpperCase();
    if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  }

  function initUserSession() {
    try {
      const stored = localStorage.getItem('kth_massspec_user');
      if (stored) {
        currentUser = JSON.parse(stored);
      } else {
        currentUser = null;
      }
    } catch (e) {
      currentUser = null;
    }
    applyUserToUI(currentUser);
  }

  function applyUserToUI(user) {
    if (user && user.email) {
      if (btnHeaderSignin) btnHeaderSignin.style.display = 'none';
      if (userInitialsWrapper) userInitialsWrapper.style.display = 'inline-block';
      
      const initials = getInitials(user.name, user.email);
      if (userInitialsCircle) {
        userInitialsCircle.textContent = initials;
        userInitialsCircle.title = `${user.name || user.email} (${user.organization || 'KTH'})`;
      }
      if (dropdownUserName) dropdownUserName.textContent = user.name || user.email;
      if (dropdownUserEmail) dropdownUserEmail.textContent = user.email || '';
      if (dropdownUserOrg) dropdownUserOrg.textContent = user.organization || 'KTH Royal Institute of Technology';

      if (contribAuthName) contribAuthName.textContent = user.name || user.email;
      if (contribAuthOrg) contribAuthOrg.textContent = `(${user.organization || 'KTH Research'})`;

      if (historyAuthGate) historyAuthGate.style.display = 'none';
      if (historyContentCard) historyContentCard.style.display = 'block';
      closeGateModal();
    } else {
      if (btnHeaderSignin) btnHeaderSignin.style.display = 'inline-flex';
      if (userInitialsWrapper) userInitialsWrapper.style.display = 'none';
      if (userDropdownMenu) userDropdownMenu.classList.remove('active');

      if (contribAuthName) contribAuthName.textContent = 'Not Signed In (Sign in required before submitting)';
      if (contribAuthOrg) contribAuthOrg.textContent = '';

      if (historyAuthGate) historyAuthGate.style.display = 'block';
      if (historyContentCard) historyContentCard.style.display = 'none';
    }
  }

  // Toggle user dropdown menu on clicking initials circle
  if (userInitialsCircle && userDropdownMenu) {
    userInitialsCircle.addEventListener('click', (e) => {
      e.stopPropagation();
      userDropdownMenu.classList.toggle('active');
    });

    document.addEventListener('click', (e) => {
      if (userInitialsWrapper && !userInitialsWrapper.contains(e.target)) {
        userDropdownMenu.classList.remove('active');
      }
    });
  }

  // Logout action
  if (btnLogout) {
    btnLogout.addEventListener('click', () => {
      currentUser = null;
      localStorage.removeItem('kth_massspec_user');
      applyUserToUI(null);
      showToast("Signed out of session.", 'info');
      loadPredictionsHistory();
    });
  }

  // Gatekeeping Modal Logic
  function showGateModal(actionType) {
    if (!modalGate) return;
    if (currentUser) {
      closeGateModal();
      return;
    }

    if (actionType === 'generate') {
      if (gateModalTitle) gateModalTitle.textContent = "Sign In Required";
      if (gateActionTitle) gateActionTitle.textContent = "Virtual Calibration Generator";
      if (gateModalMsg) gateModalMsg.textContent = "You need to log in to generate virtual calibrations using the AI model.";
      if (btnGateSignin) btnGateSignin.href = "/login?redirect=consumer";
    } else if (actionType === 'contributor') {
      if (gateModalTitle) gateModalTitle.textContent = "Sign In Required";
      if (gateActionTitle) gateActionTitle.textContent = "Laboratory Data Ingestion";
      if (gateModalMsg) gateModalMsg.textContent = "You need to log in to submit experimental calibration records to the institutional repository.";
      if (btnGateSignin) btnGateSignin.href = "/login?redirect=contributor";
    } else if (actionType === 'history') {
      if (gateModalTitle) gateModalTitle.textContent = "Sign In Required";
      if (gateActionTitle) gateActionTitle.textContent = "Consumer Prediction History";
      if (gateModalMsg) gateModalMsg.textContent = "Prediction history is private to your account. Please sign in to view your records.";
      if (btnGateSignin) btnGateSignin.href = "/login?redirect=history";
    }

    modalGate.style.setProperty('display', 'flex', 'important');
    modalGate.classList.add('active');
  }

  function closeGateModal() {
    if (modalGate) {
      modalGate.classList.remove('active');
      modalGate.style.setProperty('display', 'none', 'important');
    }
  }

  if (btnCloseGateModal) btnCloseGateModal.addEventListener('click', closeGateModal);
  if (btnCancelGate) btnCancelGate.addEventListener('click', closeGateModal);
  if (modalGate) {
    modalGate.addEventListener('click', (e) => {
      if (e.target === modalGate) closeGateModal();
    });
  }

  if (btnChangeContributor) {
    btnChangeContributor.addEventListener('click', () => {
      window.location.href = '/login?redirect=contributor';
    });
  }

  initUserSession();

  // ---------------------------------------------------------
  // SYSTEM TELEMETRY
  // ---------------------------------------------------------
  async function fetchSystemStatus() {
    try {
      const res = await fetch('/api/status');
      if (!res.ok) return;
      const data = await res.json();
      
      const txtEngine = document.getElementById('txt-engine');
      const txtDb = document.getElementById('txt-db');
      const tabBadgeCount = document.getElementById('tab-badge-count');
      const tabBadgePreds = document.getElementById('tab-badge-preds');

      if (txtEngine) {
        txtEngine.textContent = `Model: ${data.hardware_acceleration || 'Hosted ZeroGPU'}`;
      }
      if (txtDb) {
        txtDb.textContent = `DB: ${data.database_backend || 'SQLite'}`;
      }
      if (tabBadgeCount) {
        tabBadgeCount.textContent = `${data.total_submissions || 0}`;
      }
      if (tabBadgePreds && !currentUser) {
        tabBadgePreds.textContent = `${data.total_predictions || 0}`;
      }
    } catch (e) {
      console.warn("Status fetch failed:", e);
    }
  }
  fetchSystemStatus();
  setInterval(fetchSystemStatus, 30000);

  // ---------------------------------------------------------
  // TAB NAVIGATION
  // ---------------------------------------------------------
  const tabButtons = document.querySelectorAll('.tab-btn');
  const tabContents = document.querySelectorAll('.tab-content');

  tabButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      const targetTab = btn.getAttribute('data-tab');
      tabButtons.forEach(b => b.classList.remove('active'));
      tabContents.forEach(c => c.classList.remove('active'));

      btn.classList.add('active');
      const targetContent = document.getElementById(`tab-${targetTab}`);
      if (targetContent) {
        targetContent.classList.add('active');
      }

      if (targetTab === 'archive') {
        loadDatabaseArchive();
      } else if (targetTab === 'history') {
        loadPredictionsHistory();
      }
    });
  });

  // ---------------------------------------------------------
  // CONSUMER PORTAL: FILE HANDLING & GAS AUTOCOMPLETE
  // ---------------------------------------------------------
  const consDropzone = document.getElementById('cons-dropzone');
  const consFileInput = document.getElementById('cons-air-file');
  const consAirPreview = document.getElementById('cons-air-preview');
  const consAirName = document.getElementById('cons-air-name');
  const consAirRemove = document.getElementById('cons-air-remove');
  const btnUseSample = document.getElementById('btn-use-sample');
  const consGasInput = document.getElementById('cons-gas-input');
  const gasSuggestions = document.getElementById('gas-suggestions');
  const consConcInput = document.getElementById('cons-conc-input');
  const concHint = document.getElementById('conc-hint');

  if (consDropzone && consFileInput) {
    consDropzone.addEventListener('click', () => consFileInput.click());

    consDropzone.addEventListener('dragover', (e) => {
      e.preventDefault();
      consDropzone.classList.add('dragover');
    });

    consDropzone.addEventListener('dragleave', () => {
      consDropzone.classList.remove('dragover');
    });

    consDropzone.addEventListener('drop', (e) => {
      e.preventDefault();
      consDropzone.classList.remove('dragover');
      if (e.dataTransfer.files && e.dataTransfer.files[0]) {
        handleConsumerAirFile(e.dataTransfer.files[0]);
      }
    });

    consFileInput.addEventListener('change', () => {
      if (consFileInput.files && consFileInput.files[0]) {
        handleConsumerAirFile(consFileInput.files[0]);
      }
    });
  }

  function handleConsumerAirFile(file) {
    activeAirFile = file;
    useSampleAir = false;
    consAirName.textContent = `${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
    consAirPreview.classList.add('active');
    consDropzone.style.display = 'none';
  }

  if (consAirRemove) {
    consAirRemove.addEventListener('click', () => {
      activeAirFile = null;
      useSampleAir = false;
      consFileInput.value = '';
      consAirPreview.classList.remove('active');
      consDropzone.style.display = 'block';
    });
  }

  if (btnUseSample) {
    btnUseSample.addEventListener('click', () => {
      activeAirFile = null;
      useSampleAir = true;
      consAirName.textContent = 'compressed_air.csv (KTH Laboratory Reference)';
      consAirPreview.classList.add('active');
      consDropzone.style.display = 'none';
      showToast('Loaded benchmark compressed air scan', 'info');
    });
  }

  function selectGasItem(gasObj) {
    consGasInput.value = gasObj.display;
    gasSuggestions.classList.remove('active');

    // Auto-populate benchmark concentration for this gas
    if (gasObj.defaultConc !== undefined && consConcInput) {
      consConcInput.value = gasObj.defaultConc.toFixed(1);
    }
    if (concHint) {
      concHint.textContent = `Ground Truth Benchmark: ${gasObj.benchmark} (${gasObj.defaultConc || 1.0}%)`;
    }
  }

  function renderGasSuggestions(query) {
    if (!gasSuggestions || !consGasInput) return;
    const q = (query || '').trim().toLowerCase();
    
    const matches = COMMON_GASES.filter(g => 
      !q ||
      g.name.toLowerCase().includes(q) ||
      g.formula.toLowerCase().includes(q) ||
      g.display.toLowerCase().includes(q)
    );

    if (matches.length === 0) {
      gasSuggestions.innerHTML = `<div style="padding: 0.65rem 0.9rem; font-size: 0.82rem; color: var(--text-muted);">No catalog match. Custom species will be used as "${consGasInput.value}".</div>`;
      gasSuggestions.classList.add('active');
      return;
    }

    gasSuggestions.innerHTML = matches.map(g => `
      <div class="autocomplete-item" data-value="${g.display}">
        <span class="autocomplete-item-name">${g.name} (${g.formula})</span>
        <span class="autocomplete-item-formula">${g.defaultConc}% benchmark</span>
      </div>
    `).join('');

    gasSuggestions.classList.add('active');

    gasSuggestions.querySelectorAll('.autocomplete-item').forEach((item, idx) => {
      item.addEventListener('mousedown', (e) => {
        e.preventDefault();
        selectGasItem(matches[idx]);
      });
    });
  }

  if (consGasInput && gasSuggestions) {
    consGasInput.addEventListener('input', () => {
      renderGasSuggestions(consGasInput.value);
      // If user typed Methane specifically, update hint
      const v = consGasInput.value.toLowerCase();
      if (v.includes('methane') || v.includes('ch4')) {
        if (consConcInput && consConcInput.value === '1.0') {
          consConcInput.value = '5.0';
        }
        if (concHint) concHint.textContent = "Physical benchmark is calibrated at 5.0% for Methane (cal_CH4_5%)";
      }
    });

    consGasInput.addEventListener('focus', () => {
      renderGasSuggestions(consGasInput.value);
    });

    consGasInput.addEventListener('blur', () => {
      setTimeout(() => gasSuggestions.classList.remove('active'), 150);
    });

    document.addEventListener('click', (e) => {
      if (!consGasInput.contains(e.target) && !gasSuggestions.contains(e.target)) {
        gasSuggestions.classList.remove('active');
      }
    });
  }

  // ---------------------------------------------------------
  // CALIBRATION GENERATION
  // ---------------------------------------------------------
  const btnGenerate = document.getElementById('btn-generate');
  const neuralOverlay = document.getElementById('neural-overlay');
  const resultsContainer = document.getElementById('results-container');

  if (btnGenerate) {
    btnGenerate.addEventListener('click', async () => {
      // Gate: Authentication required to generate virtual calibrations
      if (!currentUser) {
        showGateModal('generate');
        return;
      }

      if (!activeAirFile && !useSampleAir) {
        showToast('Please upload an air scan CSV or load the benchmark scan.', 'error');
        return;
      }

      const targetGas = consGasInput && consGasInput.value.trim() ? consGasInput.value.trim() : 'Oxygen (O2)';
      const targetConc = consConcInput && consConcInput.value ? `${consConcInput.value}%` : '1.0%';
      const brand = document.getElementById('cons-brand').value || 'Hiden HPR-20';
      const vac = parseFloat(document.getElementById('cons-vac').value) || 1e-5;
      const detector = document.getElementById('cons-detector').value;

      btnGenerate.disabled = true;
      btnGenerate.textContent = 'Computing Virtual Calibration...';
      neuralOverlay.classList.add('active');
      resultsContainer.classList.remove('active');

      const s1 = document.getElementById('step-1');
      const s2 = document.getElementById('step-2');
      const s3 = document.getElementById('step-3');
      const s4 = document.getElementById('step-4');

      [s1, s2, s3, s4].forEach(s => {
        s.className = 'progress-step';
      });

      s1.classList.add('current');

      setTimeout(() => {
        s1.className = 'progress-step done';
        s2.classList.add('current');
      }, 500);

      setTimeout(() => {
        s2.className = 'progress-step done';
        s3.classList.add('current');
      }, 1200);

      // Build Form Data including researcher identity
      const formData = new FormData();
      formData.append('gas', targetGas);
      formData.append('conc', targetConc);
      formData.append('brand', brand);
      formData.append('vac', vac);
      formData.append('detector', detector);
      formData.append('use_sample_air', useSampleAir ? 'true' : 'false');

      if (currentUser) {
        formData.append('user_id', currentUser.id);
        formData.append('user_name', currentUser.name);
        formData.append('user_email', currentUser.email);
        formData.append('organization', currentUser.organization);
      }

      if (activeAirFile) {
        formData.append('air_file', activeAirFile);
      }

      try {
        const response = await fetch('/api/predict', {
          method: 'POST',
          body: formData
        });

        const data = await response.json();

        if (!response.ok || !data.success) {
          throw new Error(data.error || 'Computation failed.');
        }

        s3.className = 'progress-step done';
        s4.className = 'progress-step done';

        setTimeout(() => {
          neuralOverlay.classList.remove('active');
          btnGenerate.disabled = false;
          btnGenerate.textContent = 'Generate Virtual Calibration';
          renderPredictionResults(data);
          const displayAcc = data.primary_quantitation 
            ? data.primary_quantitation.quantitation_accuracy_pct 
            : data.overall_accuracy;
          showToast(`Virtual calibration generated for ${data.gas} (${displayAcc}% primary peak accuracy)`, 'success');
          fetchSystemStatus();
        }, 400);

      } catch (err) {
        neuralOverlay.classList.remove('active');
        btnGenerate.disabled = false;
        btnGenerate.textContent = 'Generate Virtual Calibration';
        showToast(err.message, 'error');
      }
    });
  }

  // ---------------------------------------------------------
  // RENDER RESULTS & PROFESSIONAL SCIENTIFIC PLOTLY CHART
  // ---------------------------------------------------------
  function renderPredictionResults(data) {
    latestPredictionData = data;
    resultsContainer.classList.add('active');

    // --- Primary Quantitation KPI ---
    const kpiAccuracy = document.getElementById('kpi-accuracy');
    const kpiBenchmark = document.getElementById('kpi-benchmark-name');

    if (data.primary_quantitation) {
      const pq = data.primary_quantitation;
      kpiAccuracy.textContent = `${pq.quantitation_accuracy_pct}%`;
      kpiBenchmark.textContent = `Primary Peak: ${pq.target_amu} — ${pq.concentration_label}`;
    } else {
      kpiAccuracy.textContent = `${data.overall_accuracy}%`;
      kpiBenchmark.textContent = `vs. ${data.benchmark_source || 'Physical Ground Truth'}`;
    }

    document.getElementById('kpi-vacuum').textContent = `${data.sensor_baseline.pressure_mbar}`;
    document.getElementById('kpi-n2').textContent = `${data.sensor_baseline.n2_amps}`;
    document.getElementById('kpi-ar').textContent = `${data.sensor_baseline.ar_amps}`;

    document.getElementById('chart-subhead').textContent = 
      `Multi-AMU Fingerprint: ${data.gas} Ground Truth Benchmark vs. Virtual Model (Gemma-2B ZeroGPU)`;

    // Render Data Table
    const tbody = document.getElementById('metrics-tbody');
    tbody.innerHTML = '';

    data.metrics.forEach(m => {
      const tr = document.createElement('tr');
      
      let badgeClass = 'good';
      if (m.accuracy_pct < 60) badgeClass = 'low';
      else if (m.accuracy_pct < 80) badgeClass = 'medium';

      // Highlight the primary peak row
      const isPrimary = m.is_primary;
      const primaryBadge = isPrimary 
        ? '<span style="margin-left: 8px; font-size: 0.72rem; padding: 2px 7px; background: #e0f2fe; color: #0284c7; border-radius: 4px; font-weight: 600;">★ Target Peak</span>' 
        : '';
      const primaryStyle = isPrimary ? 'background: rgba(0, 100, 200, 0.06); border-left: 3px solid var(--kth-blue);' : '';

      tr.style.cssText = primaryStyle;
      tr.innerHTML = `
        <td style="font-weight: 600; color: #00005d;">${m.amu}${primaryBadge}</td>
        <td>${m.real_mean.toExponential(4)} A</td>
        <td>${m.virtual_mean.toExponential(4)} A</td>
        <td>${m.error_pct.toFixed(2)}%</td>
        <td><span class="score-badge ${badgeClass}">${m.accuracy_pct.toFixed(2)}%</span></td>
      `;
      tbody.appendChild(tr);
    });

    // Configure Download Action
    const btnDownload = document.getElementById('btn-download');
    const downloadTitle = document.getElementById('download-title');
    const downloadDesc = document.getElementById('download-desc');

    downloadTitle.textContent = `${data.download_filename} Ready`;
    downloadDesc.textContent = `${data.total_rows} synthesized calibration scan rows generated.`;

    btnDownload.onclick = () => {
      window.location.href = `/api/download/${data.download_file_id}`;
    };

    // Draw Plotly Chart
    drawSpectralChart();

    // Scroll smoothly to results
    resultsContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function drawSpectralChart() {
    if (!latestPredictionData) return;

    if (chartMode === 'primary' && latestPredictionData.primary_peak_chart) {
      drawPrimaryPeakChart();
    } else {
      drawMultiAmuChart();
    }
  }

  // --- Primary Peak Single-Channel Comparison Bar Plot (User Specification) ---
  function drawPrimaryPeakChart() {
    const pc = latestPredictionData.primary_peak_chart;
    if (!pc) {
      drawMultiAmuChart();
      return;
    }

    const titleEl = document.getElementById('chart-main-title');
    const subheadEl = document.getElementById('chart-subhead');
    if (titleEl) titleEl.textContent = pc.chart_title;
    if (subheadEl) {
      subheadEl.textContent = `Physical Ground Truth vs. AI Virtual Model (5% Industrial Tolerance Window: [${pc.lower_bound.toExponential(4)} A , ${pc.upper_bound.toExponential(4)} A])`;
    }

    // Bar 1: Physical Ground Truth (Color: #1f77b4 / Institutional Blue)
    const traceGt = {
      x: [pc.categories[0]],
      y: [pc.values[0]],
      name: 'Physical Ground Truth',
      type: 'bar',
      marker: {
        color: '#1f77b4',
        line: { color: '#0f4c81', width: 1.5 }
      },
      width: [0.36],
      text: [`${pc.values[0].toExponential(4)} A`],
      textposition: 'outside',
      textfont: { family: 'Consolas, monospace', size: 12, color: '#0f172a' },
      cliponaxis: false,
      hovertemplate: '<b>%{x}</b><br>Ground Truth: %{y:.4e} A<extra></extra>'
    };

    // Bar 2: AI Virtual Model (Color: #2ca02c / Vibrant Emerald Green)
    const traceVirt = {
      x: [pc.categories[1]],
      y: [pc.values[1]],
      name: 'AI Virtual Model',
      type: 'bar',
      marker: {
        color: '#2ca02c',
        line: { color: '#15803d', width: 1.5 }
      },
      width: [0.36],
      text: [`${pc.values[1].toExponential(4)} A`],
      textposition: 'outside',
      textfont: { family: 'Consolas, monospace', size: 12, color: '#0f172a' },
      cliponaxis: false,
      hovertemplate: '<b>%{x}</b><br>AI Synthesized: %{y:.4e} A<extra></extra>'
    };

    // Dummy legend traces for the 5% tolerance lines
    const traceLowerLimit = {
      x: [null],
      y: [null],
      mode: 'lines',
      name: pc.lower_label,
      line: { color: '#ef4444', width: 2, dash: 'dash' }
    };

    const traceUpperLimit = {
      x: [null],
      y: [null],
      mode: 'lines',
      name: pc.upper_label,
      line: { color: '#ef4444', width: 2, dash: 'dash' }
    };

    const maxVal = Math.max(pc.values[0], pc.values[1], pc.upper_bound);
    const yMax = maxVal * 1.38;

    const layout = {
      paper_bgcolor: '#ffffff',
      plot_bgcolor: '#ffffff',
      font: {
        family: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
        color: '#334155',
        size: 13
      },
      legend: {
        orientation: 'h',
        yanchor: 'bottom',
        y: 1.02,
        xanchor: 'center',
        x: 0.5,
        font: { size: 12, color: '#0f172a' }
      },
      xaxis: {
        tickfont: { size: 13, color: '#0f172a', family: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif' },
        linecolor: '#cbd5e1',
        linewidth: 1
      },
      yaxis: {
        title: { text: pc.y_axis_title, font: { size: 13, color: '#0f172a' } },
        type: currentYScale,
        range: currentYScale === 'log' ? undefined : [0, yMax],
        gridcolor: '#e2e8f0',
        tickformat: '.2e',
        tickfont: { family: 'Consolas, monospace', size: 11, color: '#475569' },
        linecolor: '#cbd5e1',
        linewidth: 1
      },
      shapes: [
        // -5% Spec Limit Line
        {
          type: 'line',
          xref: 'paper',
          x0: 0,
          x1: 1,
          y0: pc.lower_bound,
          y1: pc.lower_bound,
          line: { color: '#ef4444', width: 2, dash: 'dash' }
        },
        // +5% Spec Limit Line
        {
          type: 'line',
          xref: 'paper',
          x0: 0,
          x1: 1,
          y0: pc.upper_bound,
          y1: pc.upper_bound,
          line: { color: '#ef4444', width: 2, dash: 'dash' }
        }
      ],
      annotations: [
        // -5% Spec line tag on right
        {
          xref: 'paper',
          x: 1,
          y: pc.lower_bound,
          xanchor: 'right',
          yanchor: 'bottom',
          text: `<b>${pc.lower_label}</b>`,
          showarrow: false,
          font: { size: 10, color: '#dc2626', family: 'Consolas, monospace' }
        },
        // +5% Spec line tag on right
        {
          xref: 'paper',
          x: 1,
          y: pc.upper_bound,
          xanchor: 'right',
          yanchor: 'bottom',
          text: `<b>${pc.upper_label}</b>`,
          showarrow: false,
          font: { size: 10, color: '#dc2626', family: 'Consolas, monospace' }
        }
      ],
      margin: { l: 85, r: 40, t: 55, b: 60 },
      hovermode: 'closest'
    };

    const config = {
      responsive: true,
      displayModeBar: true,
      displaylogo: false,
      modeBarButtonsToRemove: ['lasso2d', 'select2d']
    };

    Plotly.newPlot('spectral-chart', [traceGt, traceVirt, traceLowerLimit, traceUpperLimit], layout, config);
  }

  // --- Multi-AMU Spectral Fingerprint Grouped Bar Chart ---
  function drawMultiAmuChart() {
    if (!latestPredictionData || !latestPredictionData.chart_data) return;

    const chartData = latestPredictionData.chart_data;
    const titleEl = document.getElementById('chart-main-title');
    const subheadEl = document.getElementById('chart-subhead');
    if (titleEl) titleEl.textContent = "Multi-AMU Spectral Fingerprint Comparison";
    if (subheadEl) {
      subheadEl.textContent = `Ground Truth Benchmark vs. Virtual Model (${latestPredictionData.gas})`;
    }

    const traceReal = {
      x: chartData.amus,
      y: chartData.real_values,
      name: `Physical MS Benchmark (${latestPredictionData.benchmark_source || 'Ground Truth'})`,
      type: 'bar',
      marker: {
        color: 'rgb(0, 0, 93)',
        line: { color: '#00003c', width: 1 }
      },
      hovertemplate: '<b>%{x}</b><br>Benchmark: %{y:.4e} A<extra></extra>'
    };

    const traceVirt = {
      x: chartData.amus,
      y: chartData.virtual_values,
      name: 'Virtual Model (ZeroGPU AI Synthesized)',
      type: 'bar',
      marker: {
        color: '#2563eb',
        line: { color: '#1d4ed8', width: 1 }
      },
      hovertemplate: '<b>%{x}</b><br>Virtual: %{y:.4e} A<extra></extra>'
    };

    const layout = {
      barmode: 'group',
      bargap: 0.25,
      bargroupgap: 0.08,
      paper_bgcolor: '#ffffff',
      plot_bgcolor: '#ffffff',
      font: {
        family: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
        color: '#334155',
        size: 13
      },
      legend: {
        orientation: 'h',
        yanchor: 'bottom',
        y: 1.05,
        xanchor: 'right',
        x: 1,
        font: { size: 12, color: '#0f172a' }
      },
      xaxis: {
        title: { text: 'Mass-to-Charge Ratio (AMU)', font: { size: 13, color: '#0f172a' } },
        gridcolor: '#f1f5f9',
        tickfont: { family: 'Consolas, monospace', size: 12, color: '#0f172a' },
        linecolor: '#cbd5e1',
        linewidth: 1
      },
      yaxis: {
        title: { text: 'Current Intensity (Amperes)', font: { size: 13, color: '#0f172a' } },
        type: currentYScale,
        gridcolor: '#e2e8f0',
        tickformat: '.1e',
        tickfont: { family: 'Consolas, monospace', size: 11, color: '#475569' },
        linecolor: '#cbd5e1',
        linewidth: 1
      },
      margin: { l: 75, r: 25, t: 30, b: 60 },
      hovermode: 'closest'
    };

    const config = {
      responsive: true,
      displayModeBar: true,
      displaylogo: false,
      modeBarButtonsToRemove: ['lasso2d', 'select2d']
    };

    Plotly.newPlot('spectral-chart', [traceReal, traceVirt], layout, config);
  }

  // Chart View Mode Controls
  const btnChartPrimary = document.getElementById('btn-chart-primary');
  const btnChartMulti = document.getElementById('btn-chart-multi');

  if (btnChartPrimary) {
    btnChartPrimary.addEventListener('click', () => {
      chartMode = 'primary';
      btnChartPrimary.classList.add('active');
      if (btnChartMulti) btnChartMulti.classList.remove('active');
      drawSpectralChart();
    });
  }

  if (btnChartMulti) {
    btnChartMulti.addEventListener('click', () => {
      chartMode = 'multi';
      btnChartMulti.classList.add('active');
      if (btnChartPrimary) btnChartPrimary.classList.remove('active');
      drawSpectralChart();
    });
  }

  // Toggle Log/Linear Scale
  const btnToggleScale = document.getElementById('btn-toggle-scale');
  if (btnToggleScale) {
    btnToggleScale.addEventListener('click', () => {
      currentYScale = currentYScale === 'log' ? 'linear' : 'log';
      btnToggleScale.textContent = currentYScale === 'log' ? 'Scale: Logarithmic' : 'Scale: Linear';
      drawSpectralChart();
    });
  }

  // ---------------------------------------------------------
  // CONTRIBUTOR PORTAL: FILE UPLOADS & INGESTION FORM
  // ---------------------------------------------------------
  function setupDropzone(dzId, inputId, prevId, nameId, rmId) {
    const dz = document.getElementById(dzId);
    const input = document.getElementById(inputId);
    const prev = document.getElementById(prevId);
    const name = document.getElementById(nameId);
    const rm = document.getElementById(rmId);

    if (!dz || !input) return;

    dz.addEventListener('click', () => input.click());

    dz.addEventListener('dragover', (e) => {
      e.preventDefault();
      dz.classList.add('dragover');
    });

    dz.addEventListener('dragleave', () => {
      dz.classList.remove('dragover');
    });

    dz.addEventListener('drop', (e) => {
      e.preventDefault();
      dz.classList.remove('dragover');
      if (e.dataTransfer.files && e.dataTransfer.files[0]) {
        input.files = e.dataTransfer.files;
        showFile(e.dataTransfer.files[0]);
      }
    });

    input.addEventListener('change', () => {
      if (input.files && input.files[0]) {
        showFile(input.files[0]);
      }
    });

    function showFile(file) {
      name.textContent = `${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
      prev.classList.add('active');
      dz.style.display = 'none';
    }

    if (rm) {
      rm.addEventListener('click', () => {
        input.value = '';
        prev.classList.remove('active');
        dz.style.display = 'block';
      });
    }
  }

  setupDropzone('dz-contrib-air', 'contrib-air-file', 'prev-contrib-air', 'name-contrib-air', 'rm-contrib-air');
  setupDropzone('dz-contrib-cal', 'contrib-cal-file', 'prev-contrib-cal', 'name-contrib-cal', 'rm-contrib-cal');
  setupDropzone('dz-contrib-spec', 'contrib-spec-file', 'prev-contrib-spec', 'name-contrib-spec', 'rm-contrib-spec');

  const contribForm = document.getElementById('contrib-form');
  if (contribForm) {
    contribForm.addEventListener('submit', async (e) => {
      e.preventDefault();

      // Gate: Authentication required to submit ingestion records
      if (!currentUser) {
        showGateModal('contributor');
        return;
      }

      const airInput = document.getElementById('contrib-air-file');
      const calInput = document.getElementById('contrib-cal-file');
      const specInput = document.getElementById('contrib-spec-file');

      if (!airInput.files[0] || !calInput.files[0]) {
        showToast('Both Background Air and Calibration Gas scan CSVs are required.', 'error');
        return;
      }

      const btnSubmit = document.getElementById('btn-submit-contrib');
      btnSubmit.disabled = true;
      btnSubmit.textContent = 'Storing Ingestion Record...';

      const formData = new FormData();
      formData.append('air_scan_file', airInput.files[0]);
      formData.append('cal_scan_file', calInput.files[0]);
      if (specInput.files[0]) {
        formData.append('spec_file', specInput.files[0]);
      }

      formData.append('target_gas', document.getElementById('contrib-target-gas').value);
      formData.append('conc_pct', document.getElementById('contrib-conc').value);
      formData.append('ref_gas', document.getElementById('contrib-ref-gas').value);
      formData.append('brand_model', document.getElementById('contrib-brand').value);
      formData.append('serial_id', document.getElementById('contrib-serial').value);
      formData.append('detector_mode', document.getElementById('contrib-detector').value);
      formData.append('vac_pressure', document.getElementById('contrib-vac').value);
      formData.append('emission_current', document.getElementById('contrib-emission').value || 0.0);

      // Attach contributor identity
      if (currentUser) {
        formData.append('user_id', currentUser.id);
        formData.append('user_name', currentUser.name);
        formData.append('user_email', currentUser.email);
        formData.append('organization', currentUser.organization);
      }

      try {
        const response = await fetch('/api/contribute', {
          method: 'POST',
          body: formData
        });

        const result = await response.json();

        if (!response.ok || !result.success) {
          throw new Error(result.error || 'Failed to submit record.');
        }

        showToast(`Record stored in repository (ID: ${result.submission_id.slice(0, 8)})`, 'success');
        contribForm.reset();

        ['prev-contrib-air', 'prev-contrib-cal', 'prev-contrib-spec'].forEach(id => {
          const el = document.getElementById(id);
          if (el) el.classList.remove('active');
        });
        ['dz-contrib-air', 'dz-contrib-cal', 'dz-contrib-spec'].forEach(id => {
          const el = document.getElementById(id);
          if (el) el.style.display = 'block';
        });

        fetchSystemStatus();
        loadDatabaseArchive();

      } catch (err) {
        showToast(err.message, 'error');
      } finally {
        btnSubmit.disabled = false;
        btnSubmit.textContent = 'Submit Ingestion Record';
      }
    });
  }

  // ---------------------------------------------------------
  // CONTRIBUTOR REPOSITORY ARCHIVE TABLE
  // ---------------------------------------------------------
  let allSubmissions = [];

  async function loadDatabaseArchive() {
    const tbody = document.getElementById('archive-tbody');
    if (!tbody) return;
    tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">Loading experimental records...</td></tr>`;

    try {
      const res = await fetch('/api/submissions');
      const data = await res.json();
      allSubmissions = data.submissions || [];
      renderArchiveTable(allSubmissions);
      const badge = document.getElementById('tab-badge-count');
      if (badge) badge.textContent = `${allSubmissions.length}`;
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--status-danger); padding: 1.5rem;">Failed to load records from repository.</td></tr>`;
    }
  }

  function renderArchiveTable(submissions) {
    const tbody = document.getElementById('archive-tbody');
    if (!tbody) return;
    tbody.innerHTML = '';

    if (!submissions || submissions.length === 0) {
      tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--text-muted); padding: 2rem;">No contributor calibration records registered in the database.</td></tr>`;
      return;
    }

    submissions.forEach(row => {
      const tr = document.createElement('tr');
      const dateStr = row.timestamp ? row.timestamp.replace('T', ' ').slice(0, 19) : '--';
      
      // File download links
      let filesHtml = '';
      if (row.cal_scan_path) {
        filesHtml += `<a class="file-download-link" href="/api/files/download?path=${encodeURIComponent(row.cal_scan_path)}" download>Cal Scan</a>`;
      }
      if (row.air_scan_path) {
        filesHtml += `<a class="file-download-link" href="/api/files/download?path=${encodeURIComponent(row.air_scan_path)}" download>Air Scan</a>`;
      }
      if (row.spec_file_path) {
        filesHtml += `<a class="file-download-link" href="/api/files/download?path=${encodeURIComponent(row.spec_file_path)}" download>Specs</a>`;
      }

      tr.innerHTML = `
        <td style="color: var(--text-muted);">${dateStr}</td>
        <td>
          <strong style="color: var(--kth-blue);">${row.user_name || 'Contributor'}</strong>
          <div style="font-size: 0.74rem; color: var(--text-muted);">${row.user_email || '--'}</div>
        </td>
        <td>${row.organization || 'KTH Research'}</td>
        <td style="font-weight: 600; color: #00005d;">${row.target_gas || '--'}</td>
        <td>${row.conc_pct != null ? row.conc_pct + '%' : '--'}</td>
        <td>${row.brand_model || '--'}</td>
        <td>${filesHtml || '--'}</td>
        <td><code>${row.id ? row.id.slice(0, 8) : '--'}</code></td>
      `;
      tbody.appendChild(tr);
    });
  }

  const btnRefreshDb = document.getElementById('btn-refresh-db');
  if (btnRefreshDb) {
    btnRefreshDb.addEventListener('click', loadDatabaseArchive);
  }

  const searchInput = document.getElementById('db-search');
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      const term = e.target.value.toLowerCase();
      const filtered = allSubmissions.filter(s => {
        return (s.target_gas && s.target_gas.toLowerCase().includes(term)) ||
               (s.brand_model && s.brand_model.toLowerCase().includes(term)) ||
               (s.user_name && s.user_name.toLowerCase().includes(term)) ||
               (s.organization && s.organization.toLowerCase().includes(term)) ||
               (s.id && s.id.toLowerCase().includes(term));
      });
      renderArchiveTable(filtered);
    });
  }

  // ---------------------------------------------------------
  // CONSUMER PREDICTION HISTORY TABLE
  // ---------------------------------------------------------
  let allPredictions = [];

  async function loadPredictionsHistory() {
    // Privacy Gate: If not logged in, show auth gate and do not fetch
    if (!currentUser) {
      if (historyAuthGate) historyAuthGate.style.display = 'block';
      if (historyContentCard) historyContentCard.style.display = 'none';
      const badge = document.getElementById('tab-badge-preds');
      if (badge) badge.textContent = '0';
      return;
    }

    if (historyAuthGate) historyAuthGate.style.display = 'none';
    if (historyContentCard) historyContentCard.style.display = 'block';

    const tbody = document.getElementById('preds-tbody');
    if (!tbody) return;
    tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">Loading your private prediction history...</td></tr>`;

    try {
      const res = await fetch(`/api/predictions?user_id=${encodeURIComponent(currentUser.id)}`);
      const data = await res.json();
      allPredictions = data.predictions || [];
      renderPredictionsTable(allPredictions);
      const badge = document.getElementById('tab-badge-preds');
      if (badge) badge.textContent = `${allPredictions.length}`;
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--status-danger); padding: 1.5rem;">Failed to load prediction history.</td></tr>`;
    }
  }

  function renderPredictionsTable(predictions) {
    const tbody = document.getElementById('preds-tbody');
    if (!tbody) return;
    tbody.innerHTML = '';

    if (!predictions || predictions.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 2rem;">No AI virtual calibration predictions tracked yet under your account.</td></tr>`;
      return;
    }

    predictions.forEach(row => {
      const tr = document.createElement('tr');
      const dateStr = row.timestamp ? row.timestamp.replace('T', ' ').slice(0, 19) : '--';
      
      let badgeClass = 'good';
      if (row.overall_accuracy < 60) badgeClass = 'low';
      else if (row.overall_accuracy < 80) badgeClass = 'medium';

      tr.innerHTML = `
        <td style="color: var(--text-muted);">${dateStr}</td>
        <td>
          <strong style="color: var(--kth-blue);">${row.user_name || 'Researcher'}</strong>
          <div style="font-size: 0.74rem; color: var(--text-muted);">${row.user_email || '--'}</div>
        </td>
        <td>${row.organization || 'KTH Laboratory'}</td>
        <td style="font-weight: 600; color: #00005d;">${row.gas} (${row.conc})</td>
        <td><span class="score-badge ${badgeClass}">${row.overall_accuracy != null ? Number(row.overall_accuracy).toFixed(2) + '%' : '--'}</span></td>
        <td>${row.baseline_pressure != null ? Number(row.baseline_pressure).toExponential(2) : '--'}</td>
        <td>
          ${row.download_file_id ? 
            `<a class="file-download-link" href="/api/download/${row.download_file_id}" download="${row.download_filename}">
              Download CSV
            </a>` : '--'}
        </td>
      `;
      tbody.appendChild(tr);
    });
  }

  const btnRefreshPreds = document.getElementById('btn-refresh-preds');
  if (btnRefreshPreds) {
    btnRefreshPreds.addEventListener('click', loadPredictionsHistory);
  }

  const btnExportPredsCsv = document.getElementById('btn-export-preds-csv');
  if (btnExportPredsCsv) {
    btnExportPredsCsv.addEventListener('click', () => {
      if (!currentUser) {
        showGateModal('history');
        return;
      }
      window.location.href = `/api/predictions/export?user_id=${encodeURIComponent(currentUser.id)}`;
    });
  }

  const searchPredsInput = document.getElementById('pred-search');
  if (searchPredsInput) {
    searchPredsInput.addEventListener('input', (e) => {
      const term = e.target.value.toLowerCase();
      const filtered = allPredictions.filter(p => {
        return (p.gas && p.gas.toLowerCase().includes(term)) ||
               (p.user_name && p.user_name.toLowerCase().includes(term)) ||
               (p.organization && p.organization.toLowerCase().includes(term)) ||
               (p.download_filename && p.download_filename.toLowerCase().includes(term));
      });
      renderPredictionsTable(filtered);
    });
  }

  // Pre-load contributor repository (public to all users)
  loadDatabaseArchive();

  // Load private predictions history (only for signed-in user)
  loadPredictionsHistory();

  // Handle URL tab parameter (e.g. ?tab=history or ?tab=archive or ?tab=contributor)
  const urlParams = new URLSearchParams(window.location.search);
  const activeTabParam = urlParams.get('tab');
  if (activeTabParam) {
    const matchingBtn = document.querySelector(`.tab-btn[data-tab="${activeTabParam}"]`);
    if (matchingBtn) {
      matchingBtn.click();
    }
  }
});
