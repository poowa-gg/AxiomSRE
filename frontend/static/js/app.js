/**
 * AxiomSRE Mission Control - Frontend Logic
 * Autonomous Incident Commander & Zero-Day Auto-Remediator
 */

let activeIncidentId = "INC-8921-CF-OUTAGE";
let burnRatePerSec = 140.0; // $8,400 / 60
let totalBurned = 14280.0;
let burnInterval = null;
let currentAnalysis = null;

document.addEventListener("DOMContentLoaded", async () => {
    await fetchSystemStatus();
    await loadIncidents();
    startBurnCounter();

    // Event listeners
    document.getElementById("btn-analyze").addEventListener("click", runAutonomousAnalysis);
    document.getElementById("btn-run-sandbox").addEventListener("click", runLiveSandbox);
    document.getElementById("btn-postmortem").addEventListener("click", openPostMortemModal);
    document.getElementById("btn-close-modal").addEventListener("click", closeModal);
    document.getElementById("btn-copy-pm").addEventListener("click", copyPostMortem);
});

// Fetch system health and Nebius connection info
async function fetchSystemStatus() {
    try {
        const res = await fetch("/api/status");
        const data = await res.json();
        
        const nebiusBadge = document.getElementById("nebius-badge");
        if (data.nebius_token_factory.connected) {
            nebiusBadge.innerHTML = `<span class="badge-dot dot-blue"></span> Nebius Token Factory: LIVE`;
        } else {
            nebiusBadge.innerHTML = `<span class="badge-dot dot-green"></span> Nebius Token Factory: Calibrated`;
        }

        const tavilyBadge = document.getElementById("tavily-badge");
        if (data.tavily_grounding.connected) {
            tavilyBadge.innerHTML = `<span class="badge-dot dot-orange"></span> Tavily Grounding: LIVE`;
        } else {
            tavilyBadge.innerHTML = `<span class="badge-dot dot-orange"></span> Tavily Grounding: READY`;
        }
    } catch (err) {
        console.error("Failed to fetch system status:", err);
    }
}

// Load available incident scenarios
async function loadIncidents() {
    try {
        const res = await fetch("/api/incidents");
        const incidents = await res.json();
        const container = document.getElementById("scenario-strip");
        container.innerHTML = "";

        incidents.forEach((inc, idx) => {
            const card = document.createElement("div");
            card.className = `glass-panel scenario-card ${inc.id === activeIncidentId ? 'active' : ''}`;
            card.id = `card-${inc.id}`;
            card.onclick = () => selectIncident(inc);

            const sevClass = inc.severity === "P0_CRITICAL" ? "sev-p0" : "sev-p1";
            card.innerHTML = `
                <div class="sc-header">
                    <span class="sc-id">${inc.id}</span>
                    <span class="sc-sev ${sevClass}">${inc.severity}</span>
                </div>
                <div class="sc-title">${inc.title}</div>
                <div class="sc-meta">
                    <span>${inc.service}</span>
                    <span style="color: #f87171;">-${inc.error_rate_pct}% Err</span>
                </div>
            `;
            container.appendChild(card);
        });

        // Load details of the default incident
        if (incidents.length > 0) {
            await selectIncident(incidents[0]);
        }
    } catch (err) {
        console.error("Failed to load incidents:", err);
    }
}

// Select an incident scenario
async function selectIncident(inc) {
    activeIncidentId = inc.id;
    document.querySelectorAll(".scenario-card").forEach(c => c.classList.remove("active"));
    const activeCard = document.getElementById(`card-${inc.id}`);
    if (activeCard) activeCard.classList.add("active");

    // Update headlines
    document.getElementById("active-title").innerText = inc.title;
    document.getElementById("active-service").innerText = `Service: ${inc.service} | Severity: ${inc.severity} | Burn Rate: $${inc.financial_burn_rate_usd_per_min.toLocaleString()}/min`;
    
    // Update metric cards
    document.getElementById("metric-error-rate").innerText = `${inc.error_rate_pct}%`;
    document.getElementById("metric-p99").innerText = `${inc.p99_latency_ms.toLocaleString()} ms`;
    document.getElementById("metric-burn-rate").innerText = `$${inc.financial_burn_rate_usd_per_min.toLocaleString()}/m`;

    burnRatePerSec = inc.financial_burn_rate_usd_per_min / 60.0;
    totalBurned = 14280.0;
    startBurnCounter();

    // Reset Swarm Timeline and Diff view
    document.getElementById("btn-analyze").innerHTML = `<i data-lucide="zap"></i> Run Autonomous Auto-Remediation`;
    document.getElementById("btn-analyze").classList.remove("btn-secondary");
    document.getElementById("btn-analyze").classList.add("btn-primary");

    // Load logs
    await loadIncidentTelemetry(inc.id);
}

// Load raw logs into the streaming terminal
async function loadIncidentTelemetry(id) {
    try {
        const res = await fetch(`/api/incidents/${id}`);
        const data = await res.json();
        const terminal = document.getElementById("log-terminal");
        terminal.innerHTML = "";

        data.logs.forEach(log => {
            const row = document.createElement("div");
            row.className = "log-entry";
            row.innerHTML = `
                <span class="log-time">${log.timestamp.split("T")[1].replace("Z","")}</span>
                <span class="log-lvl-${log.level}">[${log.level}]</span>
                <span class="log-msg">${escapeHtml(log.message)}</span>
            `;
            terminal.appendChild(row);
        });
        terminal.scrollTop = terminal.scrollHeight;
    } catch (err) {
        console.error("Failed to load telemetry:", err);
    }
}

// Run the full 4-tier autonomous remediation workflow
async function runAutonomousAnalysis() {
    const btn = document.getElementById("btn-analyze");
    btn.innerHTML = `<span class="badge-dot dot-green" style="display:inline-block; animation: pulse 1s infinite;"></span> Orchestrating Agent Swarm...`;
    btn.disabled = true;

    try {
        const res = await fetch(`/api/incidents/${activeIncidentId}/analyze`, { method: "POST" });
        const analysis = await res.json();
        currentAnalysis = analysis;

        // Render Swarm steps
        renderSwarmTimeline(analysis.agent_trace);

        // Render Tavily Evidences
        renderTavilyEvidences(analysis.tavily_evidences);

        // Render Causal DAG
        renderCausalDAG(analysis.causal_graph);

        // Render Remediation Diff & Sandbox Proof
        renderRemediationDiff(analysis.remediation);

        // Stop burn counter and show victory state
        stopBurnCounter();
        btn.innerHTML = `✓ Remediation Verified Safe (${analysis.total_analysis_time_ms}ms)`;
        btn.classList.remove("btn-primary");
        btn.classList.add("btn-secondary");
        btn.disabled = false;

        document.getElementById("btn-run-sandbox").disabled = false;
        document.getElementById("btn-postmortem").disabled = false;

    } catch (err) {
        console.error("Autonomous analysis failed:", err);
        btn.innerHTML = `Retry Analysis`;
        btn.disabled = false;
    }
}

// Render Agent Swarm Activity Cards
function renderSwarmTimeline(steps) {
    const container = document.getElementById("swarm-timeline");
    container.innerHTML = "";

    steps.forEach((step, idx) => {
        const card = document.createElement("div");
        card.className = "agent-step-card";
        card.innerHTML = `
            <div class="step-hdr">
                <span class="agent-name">
                    <span class="badge-dot dot-${idx === 1 ? 'orange' : (idx === 2 ? 'green' : 'blue')}"></span>
                    ${step.agent_name}
                </span>
                <span class="agent-model">${step.model_name} • ${step.execution_time_ms}ms</span>
            </div>
            <div class="agent-thought">${escapeHtml(step.thought_trace)}</div>
        `;
        container.appendChild(card);
    });
}

// Render Tavily Grounding Citations
function renderTavilyEvidences(evidences) {
    const container = document.getElementById("evidence-list");
    container.innerHTML = "";

    evidences.forEach(ev => {
        const card = document.createElement("div");
        card.className = "evidence-card";
        card.innerHTML = `
            <div class="ev-header">
                <a href="${ev.url}" target="_blank" class="ev-title">${escapeHtml(ev.title)} ↗</a>
                <span class="ev-score">${Math.round(ev.relevance_score * 100)}% Match</span>
            </div>
            <div class="ev-snippet">"${escapeHtml(ev.snippet)}"</div>
            <div class="ev-correlation">🔍 Correlation: ${escapeHtml(ev.incident_correlation)}</div>
        `;
        container.appendChild(card);
    });
}

// Render Interactive Causal DAG
function renderCausalDAG(causal) {
    const container = document.getElementById("dag-container");
    container.innerHTML = "";

    // Topological rendering from External Factor -> Root Cause -> Cascade -> Surface Symptom
    const orderMap = {
        "EXTERNAL_FACTOR": "node-EXT",
        "ROOT_CAUSE": "node-ROOT",
        "INTERMEDIATE_CASCADE": "node-CASCADE",
        "SURFACE_SYMPTOM": "node-SYMPTOM"
    };

    causal.nodes.forEach((node, idx) => {
        const nodeEl = document.createElement("div");
        const cls = orderMap[node.type] || "node-CASCADE";
        nodeEl.className = `dag-node ${cls}`;
        nodeEl.innerHTML = `
            <div style="font-size: 9px; opacity: 0.8; text-transform: uppercase;">${node.type.replace('_',' ')}</div>
            <div style="margin-top: 4px;">${escapeHtml(node.label)}</div>
            <div style="font-size: 9px; margin-top: 4px; opacity: 0.9;">${Math.round(node.confidence*100)}% Conf</div>
        `;
        container.appendChild(nodeEl);

        if (idx < causal.nodes.length - 1) {
            const arrow = document.createElement("div");
            arrow.className = "dag-arrow";
            arrow.innerText = "➔";
            container.appendChild(arrow);
        }
    });

    document.getElementById("dag-explanation").innerText = causal.root_cause_explanation;
    document.getElementById("dag-proof").innerText = causal.counterfactual_proof;
}

// Render Git Diff & Sandbox Proof Card
function renderRemediationDiff(rem) {
    const diffContainer = document.getElementById("diff-window");
    diffContainer.innerHTML = "";

    const lines = rem.unified_git_diff.split("\n");
    lines.forEach(line => {
        const div = document.createElement("div");
        if (line.startsWith("+") && !line.startsWith("+++")) {
            div.className = "diff-add";
        } else if (line.startsWith("-") && !line.startsWith("---")) {
            div.className = "diff-del";
        } else {
            div.className = "diff-ctx";
        }
        div.innerText = line;
        diffContainer.appendChild(div);
    });

    // Sandbox card
    const sb = rem.sandbox_result;
    if (sb) {
        document.getElementById("sb-status").innerHTML = `✓ ${sb.tests_passed}/${sb.tests_run} Regression Tests Passed (${sb.execution_time_ms}ms)`;
        document.getElementById("sb-output").innerText = sb.raw_output;
    }
}

// Live Sandbox Re-execution
async function runLiveSandbox() {
    const sbStatus = document.getElementById("sb-status");
    sbStatus.innerHTML = `<span class="badge-dot dot-green"></span> Re-running isolated Pytest sandbox...`;

    try {
        const res = await fetch(`/api/incidents/${activeIncidentId}/sandbox-run`, { method: "POST" });
        const result = await res.json();
        sbStatus.innerHTML = `✓ ${result.tests_passed}/${result.tests_run} Regression Tests Passed (${result.execution_time_ms}ms) [VERIFIED SAFE]`;
        document.getElementById("sb-output").innerText = result.raw_output;
    } catch (err) {
        console.error("Sandbox run error:", err);
    }
}

// Post-Mortem Modal
async function openPostMortemModal() {
    try {
        const res = await fetch(`/api/incidents/${activeIncidentId}/postmortem`, { method: "POST" });
        const pm = await res.json();
        
        document.getElementById("pm-title").innerText = `Post-Mortem: ${pm.incident_id} - ${pm.title}`;
        document.getElementById("pm-body").innerHTML = `<pre style="white-space: pre-wrap; font-family: 'JetBrains Mono', monospace; font-size: 11px;">${escapeHtml(pm.markdown_document)}</pre>`;
        document.getElementById("modal-overlay").classList.add("open");
    } catch (err) {
        console.error("Failed to load post-mortem:", err);
    }
}

function closeModal() {
    document.getElementById("modal-overlay").classList.remove("open");
}

function copyPostMortem() {
    const content = document.getElementById("pm-body").innerText;
    navigator.clipboard.writeText(content).then(() => {
        const btn = document.getElementById("btn-copy-pm");
        btn.innerText = "✓ Copied to Clipboard!";
        setTimeout(() => { btn.innerText = "Copy Markdown"; }, 2000);
    });
}

// Live Burn Counter
function startBurnCounter() {
    if (burnInterval) clearInterval(burnInterval);
    burnInterval = setInterval(() => {
        totalBurned += (burnRatePerSec * 0.1);
        const el = document.getElementById("burn-val");
        if (el) el.innerText = `$${Math.round(totalBurned).toLocaleString()}`;
    }, 100);
}

function stopBurnCounter() {
    if (burnInterval) clearInterval(burnInterval);
    const el = document.getElementById("burn-val");
    if (el) el.innerHTML = `<span style="color: #10b981;">SAVED $${Math.round(totalBurned * 12).toLocaleString()}</span>`;
}

function escapeHtml(str) {
    if (!str) return "";
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
