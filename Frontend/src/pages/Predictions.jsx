import { useState, useRef } from "react";
import { Line, Bar } from "react-chartjs-2";
import {
  Chart as ChartJS, CategoryScale, LinearScale, PointElement,
  LineElement, BarElement, Tooltip, Legend, Filler
} from "chart.js";
import { API_BASE } from "../utils/api";
import ExportMenu from "../components/ExportMenu";
import { exportPredictionPDF, exportPredictionCSV } from "../utils/exportUtils";

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, BarElement, Tooltip, Legend, Filler);

const STATES = [
  "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
  "Delhi", "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand",
  "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur",
  "Meghalaya", "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim",
  "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand",
  "West Bengal",
];

const CATEGORY_COLORS = {
  "Safe": "#2ecc71", "Semi-Critical": "#f39c12",
  "Critical": "#e67e22", "Over-Exploited": "#e74c3c",
};

export default function Predictions() {
  const [riskForm, setRiskForm] = useState({ extraction_pct: 85, state: "Punjab" });
  const [riskResult, setRiskResult] = useState(null);
  const [riskLoading, setRiskLoading] = useState(false);

  const [predForm, setPredForm] = useState({ year: 2027, state: "Punjab" });
  const [predResult, setPredResult] = useState(null);
  const [predLoading, setPredLoading] = useState(false);

  const [twinForm, setTwinForm] = useState({
    state: "Punjab",
    baseline_extraction_pct: 115,
    start_year: 2024,
    horizon_years: 8,
    rainfall_scenario: "normal",
    crop_shift_pct: 25,
    recharge_structures_pct: 35,
    pumping_reduction_pct: 15,
    urban_permeability_pct: 10,
  });
  const [twinResult, setTwinResult] = useState(null);
  const [twinLoading, setTwinLoading] = useState(false);

  const trendChartRef = useRef(null);

  const predictRisk = async () => {
    setRiskLoading(true);
    setRiskResult(null);
    try {
      const res = await fetch(`${API_BASE}/api/ml/predict-risk`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(riskForm),
      });
      setRiskResult(await res.json());
    } catch { setRiskResult({ error: "Request failed" }); }
    setRiskLoading(false);
  };

  const predictExtraction = async () => {
    setPredLoading(true);
    setPredResult(null);
    try {
      const res = await fetch(`${API_BASE}/api/ml/predict-groundwater`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(predForm),
      });
      setPredResult(await res.json());
    } catch { setPredResult({ error: "Request failed" }); }
    setPredLoading(false);
  };

  const simulateDigitalTwin = async () => {
    setTwinLoading(true);
    setTwinResult(null);
    try {
      const res = await fetch(`${API_BASE}/api/ml/simulate-digital-twin`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(twinForm),
      });
      setTwinResult(await res.json());
    } catch { setTwinResult({ error: "Request failed" }); }
    setTwinLoading(false);
  };

  const trendChartData = predResult?.trend_forecast ? {
    labels: predResult.trend_forecast.map(t => t.year),
    datasets: [{
      label: "Predicted Extraction (%)",
      data: predResult.trend_forecast.map(t => t.predicted_extraction),
      fill: true,
      borderColor: "#00A3E0",
      backgroundColor: "rgba(0,163,224,0.15)",
      tension: 0.4,
      pointRadius: 5,
      pointBackgroundColor: "#00A3E0",
    }]
  } : null;

  const probChartData = riskResult?.probabilities ? {
    labels: Object.keys(riskResult.probabilities),
    datasets: [{
      label: "Probability (%)",
      data: Object.values(riskResult.probabilities),
      backgroundColor: Object.keys(riskResult.probabilities).map(k => CATEGORY_COLORS[k] || "#888"),
      borderRadius: 6,
      borderSkipped: false,
    }]
  } : null;

  const twinChartData = twinResult?.intervention_series ? {
    labels: twinResult.intervention_series.map(t => t.year),
    datasets: [
      {
        label: "Baseline",
        data: twinResult.baseline_series.map(t => t.extraction),
        borderColor: "#e74c3c",
        backgroundColor: "rgba(231,76,60,0.08)",
        borderDash: [6, 5],
        tension: 0.35,
        pointRadius: 3,
      },
      {
        label: "Scenario",
        data: twinResult.intervention_series.map(t => t.extraction),
        borderColor: "#00A3E0",
        backgroundColor: "rgba(0,163,224,0.14)",
        fill: true,
        tension: 0.35,
        pointRadius: 4,
      },
      {
        label: "Low band",
        data: twinResult.intervention_series.map(t => t.low),
        borderColor: "rgba(0,163,224,0.16)",
        backgroundColor: "rgba(0,163,224,0.05)",
        pointRadius: 0,
        tension: 0.35,
      },
      {
        label: "High band",
        data: twinResult.intervention_series.map(t => t.high),
        borderColor: "rgba(0,163,224,0.16)",
        backgroundColor: "rgba(0,163,224,0.05)",
        pointRadius: 0,
        tension: 0.35,
      },
    ]
  } : null;

  const hasExportableResults = (riskResult && !riskResult.error) || (predResult && !predResult.error);
  const exportState = riskForm.state || predForm.state;

  const exportOptions = hasExportableResults ? [
    {
      id: "pdf",
      type: "pdf",
      label: "Full Prediction Report",
      action: () => exportPredictionPDF({
        riskResult,
        predResult,
        state: exportState,
        extractionPct: riskForm.extraction_pct,
        targetYear: predForm.year,
        chartRef: trendChartRef,
      }),
    },
    {
      id: "csv",
      type: "csv",
      label: "Prediction Data",
      action: () => exportPredictionCSV(riskResult, predResult, exportState),
    },
  ] : [];

  return (
    <div className="page-content predictions-page">
      <div className="page-header-row">
        <div>
          <h1>ML Predictions</h1>
          <p>Predict groundwater risk category and future extraction levels using trained ML models</p>
        </div>
        {hasExportableResults && <ExportMenu options={exportOptions} />}
      </div>

      <div className="predictions-grid">
        <div className="pred-panel">
          <div className="pred-panel-header">
            <div className="pred-icon risk-icon">🎯</div>
            <div>
              <h3>Risk Classification</h3>
              <p>SVM + Random Forest Classifier</p>
            </div>
          </div>

          <div className="form-group">
            <label>State</label>
            <select value={riskForm.state} onChange={e => setRiskForm(f => ({ ...f, state: e.target.value }))}>
              {STATES.map(s => <option key={s}>{s}</option>)}
            </select>
          </div>

          <div className="form-group">
            <label>Current Extraction Rate: <strong>{riskForm.extraction_pct}%</strong></label>
            <input
              type="range" min="5" max="220" step="1"
              value={riskForm.extraction_pct}
              onChange={e => setRiskForm(f => ({ ...f, extraction_pct: parseFloat(e.target.value) }))}
              className="slider"
            />
            <div className="slider-labels"><span>Safe (5%)</span><span>Over-Exploited (220%)</span></div>
          </div>

          <button className="pred-btn" onClick={predictRisk} disabled={riskLoading}>
            {riskLoading ? <span className="btn-loader"></span> : "Classify Risk"}
          </button>

          {riskResult && !riskResult.error && (
            <div className="pred-result">
              <div className="result-category" style={{ borderColor: riskResult.color, color: riskResult.color }}>
                <span className="result-cat-label">Predicted Category</span>
                <span className="result-cat-value">{riskResult.category}</span>
              </div>
              <div className="result-inputs">
                <div className="ri-item"><span>Extraction</span><strong>{riskResult.input?.extraction_pct}%</strong></div>
                <div className="ri-item"><span>Recharge</span><strong>{riskResult.input?.recharge_level} mm</strong></div>
                <div className="ri-item"><span>Rainfall</span><strong>{riskResult.input?.rainfall_mm} mm</strong></div>
                <div className="ri-item"><span>Pop. Density</span><strong>{riskResult.input?.population_density}/km²</strong></div>
              </div>
              {probChartData && (
                <div style={{ height: 200, marginTop: 12 }}>
                  <Bar data={probChartData} options={{
                    responsive: true, maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                      y: { max: 100, ticks: { callback: v => `${v}%` }, grid: { color: "rgba(0,0,0,0.05)" } },
                      x: { grid: { display: false } }
                    }
                  }} />
                </div>
              )}
            </div>
          )}
        </div>

        <div className="pred-panel">
          <div className="pred-panel-header">
            <div className="pred-icon forecast-icon">📈</div>
            <div>
              <h3>Extraction Forecast</h3>
              <p>Random Forest Regressor</p>
            </div>
          </div>

          <div className="form-group">
            <label>State</label>
            <select value={predForm.state} onChange={e => setPredForm(f => ({ ...f, state: e.target.value }))}>
              {STATES.map(s => <option key={s}>{s}</option>)}
            </select>
          </div>

          <div className="form-group">
            <label>Target Year: <strong>{predForm.year}</strong></label>
            <input
              type="range" min="2024" max="2035" step="1"
              value={predForm.year}
              onChange={e => setPredForm(f => ({ ...f, year: parseInt(e.target.value) }))}
              className="slider"
            />
            <div className="slider-labels"><span>2024</span><span>2035</span></div>
          </div>

          <button className="pred-btn" onClick={predictExtraction} disabled={predLoading}>
            {predLoading ? <span className="btn-loader"></span> : "Predict Extraction"}
          </button>

          {predResult && !predResult.error && (
            <div className="pred-result">
              <div className="result-category" style={{ borderColor: predResult.color, color: predResult.color }}>
                <span className="result-cat-label">Predicted Extraction in {predResult.year}</span>
                <span className="result-cat-value">{predResult.predicted_extraction}%</span>
              </div>
              <div className="result-category-sub" style={{ background: predResult.color + "22", color: predResult.color }}>
                Status: {predResult.category}
              </div>
              {trendChartData && (
                <div style={{ height: 220, marginTop: 16 }}>
                  <Line
                    ref={trendChartRef}
                    data={trendChartData}
                    options={{
                      responsive: true, maintainAspectRatio: false,
                      plugins: { legend: { display: false } },
                      scales: {
                        y: { ticks: { callback: v => `${v}%` }, grid: { color: "rgba(0,0,0,0.05)" } },
                        x: { grid: { display: false } }
                      }
                    }}
                  />
                </div>
              )}
              <div className="result-inputs" style={{ marginTop: 8 }}>
                <div className="ri-item"><span>Rainfall</span><strong>{predResult.inputs?.rainfall_mm} mm</strong></div>
                <div className="ri-item"><span>Recharge</span><strong>{predResult.inputs?.recharge_level} mm</strong></div>
                <div className="ri-item"><span>Pop. Density</span><strong>{predResult.inputs?.population_density}/km²</strong></div>
              </div>
            </div>
          )}
        </div>

        <div className="pred-panel digital-twin-panel">
          <div className="pred-panel-header">
            <div className="pred-icon twin-icon">DT</div>
            <div>
              <h3>Scenario Digital Twin</h3>
              <p>Hydro-balance simulator for intervention planning</p>
            </div>
          </div>

          <div className="twin-form-grid">
            <div className="form-group">
              <label>State</label>
              <select value={twinForm.state} onChange={e => setTwinForm(f => ({ ...f, state: e.target.value }))}>
                {STATES.map(s => <option key={s}>{s}</option>)}
              </select>
            </div>

            <div className="form-group">
              <label>Rainfall Scenario</label>
              <select value={twinForm.rainfall_scenario} onChange={e => setTwinForm(f => ({ ...f, rainfall_scenario: e.target.value }))}>
                <option value="dry">Dry monsoon</option>
                <option value="normal">Normal monsoon</option>
                <option value="wet">Wet monsoon</option>
              </select>
            </div>
          </div>

          <div className="twin-slider-grid">
            <div className="form-group">
              <label>Baseline Extraction: <strong>{twinForm.baseline_extraction_pct}%</strong></label>
              <input type="range" min="10" max="220" step="1" value={twinForm.baseline_extraction_pct}
                onChange={e => setTwinForm(f => ({ ...f, baseline_extraction_pct: parseFloat(e.target.value) }))}
                className="slider" />
            </div>
            <div className="form-group">
              <label>Horizon: <strong>{twinForm.horizon_years} years</strong></label>
              <input type="range" min="3" max="15" step="1" value={twinForm.horizon_years}
                onChange={e => setTwinForm(f => ({ ...f, horizon_years: parseInt(e.target.value) }))}
                className="slider" />
            </div>
            <div className="form-group">
              <label>Crop Shift: <strong>{twinForm.crop_shift_pct}%</strong></label>
              <input type="range" min="0" max="80" step="5" value={twinForm.crop_shift_pct}
                onChange={e => setTwinForm(f => ({ ...f, crop_shift_pct: parseFloat(e.target.value) }))}
                className="slider" />
            </div>
            <div className="form-group">
              <label>Recharge Structures: <strong>{twinForm.recharge_structures_pct}%</strong></label>
              <input type="range" min="0" max="100" step="5" value={twinForm.recharge_structures_pct}
                onChange={e => setTwinForm(f => ({ ...f, recharge_structures_pct: parseFloat(e.target.value) }))}
                className="slider" />
            </div>
            <div className="form-group">
              <label>Pumping Reduction: <strong>{twinForm.pumping_reduction_pct}%</strong></label>
              <input type="range" min="0" max="70" step="5" value={twinForm.pumping_reduction_pct}
                onChange={e => setTwinForm(f => ({ ...f, pumping_reduction_pct: parseFloat(e.target.value) }))}
                className="slider" />
            </div>
            <div className="form-group">
              <label>Urban Permeability: <strong>{twinForm.urban_permeability_pct}%</strong></label>
              <input type="range" min="0" max="70" step="5" value={twinForm.urban_permeability_pct}
                onChange={e => setTwinForm(f => ({ ...f, urban_permeability_pct: parseFloat(e.target.value) }))}
                className="slider" />
            </div>
          </div>

          <button className="pred-btn" onClick={simulateDigitalTwin} disabled={twinLoading}>
            {twinLoading ? <span className="btn-loader"></span> : "Simulate Scenario"}
          </button>

          {twinResult && !twinResult.error && (
            <div className="pred-result twin-result">
              <div className="twin-summary">
                <div>
                  <span className="result-cat-label">Aquifer profile</span>
                  <strong>{twinResult.aquifer_profile}</strong>
                </div>
                <div>
                  <span className="result-cat-label">Avoided pressure</span>
                  <strong>{twinResult.impact?.avoided_extraction_pct_points} pts</strong>
                </div>
                <div>
                  <span className="result-cat-label">Final status</span>
                  <strong style={{ color: twinResult.color }}>{twinResult.impact?.intervention_final_category}</strong>
                </div>
                <div>
                  <span className="result-cat-label">Recovery year</span>
                  <strong>{twinResult.impact?.intervention_recovery_year || "Not reached"}</strong>
                </div>
              </div>

              {twinChartData && (
                <div className="twin-chart">
                  <Line data={twinChartData} options={{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { position: "bottom" } },
                    scales: {
                      y: { ticks: { callback: v => `${v}%` }, grid: { color: "rgba(0,0,0,0.05)" } },
                      x: { grid: { display: false } }
                    }
                  }} />
                </div>
              )}

              <div className="policy-levers">
                {twinResult.policy_levers?.map(lever => (
                  <div className="policy-lever" key={lever.name}>
                    <div>
                      <strong>{lever.name}</strong>
                      <span>{lever.interpretation}</span>
                    </div>
                    <b>{lever.score}</b>
                  </div>
                ))}
              </div>

              <div className="twin-recommendation">
                {twinResult.recommendation}
              </div>
              <div className="model-note">{twinResult.method}</div>
            </div>
          )}

          {twinResult?.error && <div className="model-note error-note">{twinResult.error}</div>}
        </div>
      </div>
    </div>
  );
}
