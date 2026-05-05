const state = {
  snapshot: null,
  systemStatus: null,
  linkDirectorStatus: null,
  linkDirectorPending: false,
  activeAct: "act1",
  selectedImageIndex: 0,
  currentResult: null,
  baselineResult: null,
  faultResult: null,
  activeInferenceJobId: null,
  activeInferenceVariant: "",
  jobManifestGatePending: false,
  archiveSessions: [],
  archiveSession: null,
  selectedArchiveSessionId: "",
  currentArchiveSessionId: "",
  userSelectedAct: false,
  selectedWeakScenarioId: "",
  weakScenarioPinnedByUser: false,
  activeDrawer: "",
};

function docHref(path) {
  return `/docs?path=${encodeURIComponent(path)}`;
}

function fetchJSON(url, options = {}) {
  return fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  }).then(async (response) => {
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload.message || `Request failed: ${response.status}`);
    }
    return payload;
  });
}

function escapeHtml(text) {
  return String(text || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function toneClass(value) {
  const normalized = String(value || "").toLowerCase();
  if (normalized.includes("online") || normalized.includes("live") || normalized.includes("pass") || normalized.includes("ready")) {
    return "tone-online";
  }
  if (normalized.includes("degraded") || normalized.includes("warning") || normalized.includes("fallback") || normalized.includes("replay")) {
    return "tone-degraded";
  }
  if (normalized.includes("offline") || normalized.includes("fail") || normalized.includes("deny") || normalized.includes("timeout")) {
    return "tone-offline";
  }
  return "tone-neutral";
}

function lampClass(value) {
  const normalized = String(value || "").toLowerCase();
  if (normalized.includes("online") || normalized.includes("ready") || normalized.includes("green")) {
    return "lamp-online";
  }
  if (normalized.includes("warning") || normalized.includes("degraded") || normalized.includes("yellow")) {
    return "lamp-warning";
  }
  if (normalized.includes("danger") || normalized.includes("red") || normalized.includes("fault") || normalized.includes("deny")) {
    return "lamp-danger";
  }
  return "";
}

function formatMaybeMs(value) {
  if (value === null || value === undefined || value === "") return "NA";
  const numeric = Number(value);
  if (Number.isNaN(numeric)) return String(value);
  return `${numeric.toFixed(numeric >= 100 ? 1 : 3).replace(/\.000$/, "").replace(/(\.\d)00$/, "$1")} ms`;
}

function formatNumber(value, digits = 3) {
  if (value === null || value === undefined || value === "") return "NA";
  const numeric = Number(value);
  if (Number.isNaN(numeric)) return String(value);
  return numeric.toFixed(digits).replace(/\.000$/, "").replace(/(\.\d)00$/, "$1").replace(/(\.\d\d)0$/, "$1");
}

function formatCoordinate(value, positiveLabel, negativeLabel) {
  const numeric = Number(value);
  if (Number.isNaN(numeric)) return "定位待定";
  const direction = numeric >= 0 ? positiveLabel : negativeLabel;
  return `${Math.abs(numeric).toFixed(4)}° ${direction}`;
}

function compactTimestampLabel(value) {
  const text = String(value || "").trim();
  if (!text) return "NA";
  if (text.includes("T") && text.length >= 19) {
    return `${text.slice(5, 10)} ${text.slice(11, 19)}`;
  }
  return text;
}

function fieldLabel(field) {
  const labels = {
    host: "主机",
    user: "用户名",
    password: "密码",
    port: "SSH 端口",
    env_file: "推理 env",
  };
  return labels[field] || field;
}

function summarizeMissing(fields) {
  if (!fields || !fields.length) return "无";
  return fields.map((field) => fieldLabel(field)).join("、");
}

function isPasswordOnlyMissing(access) {
  const missingFields = access?.missing_connection_fields || [];
  return missingFields.length === 1 && missingFields[0] === "password";
}

function renderFieldChip(label, value, state) {
  const tone = state === "preloaded" ? "tone-online" : state === "missing" ? "tone-degraded" : "tone-neutral";
  return `
    <div class="field-chip ${tone}" data-state="${escapeHtml(state)}">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
    </div>
  `;
}

function renderLinks(links) {
  if (!links || !links.length) return "";
  return `
    <div class="inline-links">
      ${links
        .map((link) => `<a class="doc-link" href="${docHref(link.path)}">${escapeHtml(link.label)}</a>`)
        .join("")}
    </div>
  `;
}

function statCard(label, value, caption) {
  return `
    <div class="mini-metric">
      <div class="label">${escapeHtml(label)}</div>
      <div class="value">${escapeHtml(value)}</div>
      <div class="compact-copy">${escapeHtml(caption)}</div>
    </div>
  `;
}

function kpiCard(label, value, note, lamp = "") {
  return `
    <article class="status-kpi">
      <div class="label">${escapeHtml(label)}</div>
      <div class="inline-actions">
        <div class="status-dot ${lampClass(lamp)}"></div>
        <div class="value">${escapeHtml(value)}</div>
      </div>
      <div class="compact-copy">${escapeHtml(note)}</div>
    </article>
  `;
}

function shortSha(value) {
  const text = String(value || "");
  return text ? text.slice(0, 12) : "NA";
}

function compactModeBoundary(note) {
  const text = String(note || "").trim();
  if (!text) {
    return "4-core headline performance 只保留在正式证据口径；当前页面如实展示 3-core Linux + RTOS OpenAMP demo。";
  }
  const normalized = text.toLowerCase();
  if (normalized.includes("4-core") && normalized.includes("3-core")) {
    return "4-core headline performance 只保留在正式证据口径；当前页面如实展示 3-core Linux + RTOS OpenAMP demo。";
  }
  return text;
}

function compactManualNote(note) {
  const text = String(note || "").trim();
  if (!text) {
    return "Operator assist only：探板、预检、运行、故障注入与 SAFE_STOP 仍由操作员手动触发。";
  }
  const normalized = text.toLowerCase();
  if (normalized.includes("operator-assist") || normalized.includes("manual")) {
    return "Operator assist only：探板、预检、运行、故障注入与 SAFE_STOP 仍由操作员手动触发。";
  }
  return text;
}

function compactSentence(text, limit = 140) {
  const value = String(text || "").trim().replace(/\s+/g, " ");
  if (!value) return "";
  if (value.length <= limit) return value;
  return `${value.slice(0, Math.max(limit - 1, 0)).trimEnd()}...`;
}

function setStatusBadge(id, label, tone) {
  const element = document.getElementById(id);
  if (!element) return;
  element.className = `status-pill ${toneClass(tone)}`;
  element.textContent = label;
}

function weakMetricCard(label, value, note = "", tone = "neutral") {
  return `
    <article class="weak-metric-card" data-tone="${escapeHtml(tone)}">
      <div class="label">${escapeHtml(label)}</div>
      <div class="value">${escapeHtml(value)}</div>
      <div class="compact-copy">${escapeHtml(note)}</div>
    </article>
  `;
}

function missionMetric(label, value, note = "") {
  return `
    <div class="mission-metric">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
      ${note ? `<small>${escapeHtml(note)}</small>` : ""}
    </div>
  `;
}

function missionNote(text) {
  return `<p class="compact-copy mission-note">${escapeHtml(text)}</p>`;
}

function normalizeCueJump(item) {
  if (!item) return null;
  const targetId = item.targetId || item.target_id || "";
  if (!targetId) return null;
  return {
    label: item.label || "",
    targetId,
    actId: item.actId || item.act_id || "",
    primary: Boolean(item.primary),
  };
}

function normalizeOperatorCue(cue) {
  if (!cue || typeof cue !== "object") {
    return {
      statusLabel: "",
      statusTone: "neutral",
      currentSceneId: "",
      currentSceneLabel: "",
      currentSceneTone: "neutral",
      presenterLine: "",
      nextStepLabel: "",
      nextStepNote: "",
      nextAction: null,
      boundaryNote: "",
      manualBoundaryNote: "",
      quickJumps: [],
      scenes: [],
    };
  }
  return {
    statusLabel: cue.status_label || "",
    statusTone: cue.status_tone || "neutral",
    currentSceneId: cue.current_scene_id || "",
    currentSceneLabel: cue.current_scene_label || cue.status_label || "",
    currentSceneTone: cue.current_scene_tone || cue.status_tone || "neutral",
    presenterLine: cue.presenter_line || "",
    nextStepLabel: cue.next_step_label || "",
    nextStepNote: cue.next_step_note || "",
    nextAction: normalizeCueJump(cue.next_action),
    boundaryNote: cue.boundary_note || "",
    manualBoundaryNote: cue.manual_boundary_note || "",
    quickJumps: (cue.quick_jumps || []).map((item) => normalizeCueJump(item)).filter(Boolean),
    scenes: (cue.scenes || []).map((scene) => ({
      ...scene,
      jump: normalizeCueJump(scene.jump),
      checks: Array.isArray(scene.checks) ? scene.checks : [],
      ready_count: Number(scene.ready_count || 0),
      total_checks: Number(scene.total_checks || (scene.checks || []).length),
      recommended: Boolean(scene.recommended),
    })),
  };
}

function actIdForSceneId(sceneId) {
  const mapping = {
    scene1: "act1",
    scene2: "act2",
    scene3: "act3",
    scene4: "act4",
  };
  return mapping[String(sceneId || "").trim()] || "";
}

function drawerIdForAct(actId) {
  const mapping = {
    act1: "sessionDrawer",
    act2: "currentDrawer",
    act3: "compareDrawer",
    act4: "safetyDrawer",
  };
  return mapping[String(actId || "").trim()] || "";
}

function drawerIdForTarget(targetId) {
  const mapping = {
    credentialPanel: "sessionDrawer",
    jobManifestGateShell: "sessionDrawer",
    act1Panel: "sessionDrawer",
    act2Panel: "currentDrawer",
    compareViewerShell: "compareDrawer",
    performanceGrid: "compareDrawer",
    act3Panel: "compareDrawer",
    missionPanel: "safetyDrawer",
    archiveTimelineCard: "safetyDrawer",
    act4Panel: "safetyDrawer",
  };
  return mapping[String(targetId || "").trim()] || "";
}

function openDrawer(drawerId) {
  if (!drawerId) return;
  state.activeDrawer = drawerId;
  document.querySelectorAll("[data-drawer]").forEach((drawer) => {
    drawer.classList.toggle("open", drawer.id === drawerId);
  });
  const overlay = document.getElementById("drawerOverlay");
  if (overlay) {
    overlay.hidden = false;
    overlay.classList.add("open");
  }
}

function closeDrawer(drawerId = "") {
  const nextDrawerId = drawerId || state.activeDrawer;
  if (!nextDrawerId) return;
  state.activeDrawer = "";
  document.querySelectorAll("[data-drawer]").forEach((drawer) => {
    drawer.classList.remove("open");
  });
  const overlay = document.getElementById("drawerOverlay");
  if (overlay) {
    overlay.classList.remove("open");
    overlay.hidden = true;
  }
}

function focusMissionPasswordInput() {
  const missionPasswordInput = document.getElementById("missionPasswordInput");
  if (!missionPasswordInput) return;
  missionPasswordInput.focus();
  missionPasswordInput.select();
}

function syncActiveActFromCue() {
  if (state.userSelectedAct) return;
  const suggestedActId = actIdForSceneId(state.systemStatus?.operator_cue?.current_scene_id || "");
  if (suggestedActId) {
    state.activeAct = suggestedActId;
  }
}

function commandJumpButton(item, primary = false) {
  const jump = normalizeCueJump(item);
  if (!jump || !jump.targetId) return "";
  return `
    <button
      class="button ${primary ? "button-primary" : "button-secondary"}"
      type="button"
      data-jump-target="${escapeHtml(jump.targetId)}"
      ${jump.actId ? `data-jump-act="${escapeHtml(jump.actId)}"` : ""}
    >${escapeHtml(jump.label)}</button>
  `;
}

function cueCheckChip(check) {
  return `
    <div class="cue-check-chip" data-tone="${escapeHtml(check.tone || (check.ready ? "online" : "degraded"))}">
      <div class="status-dot ${lampClass(check.tone || (check.ready ? "online" : "degraded"))}"></div>
      <div>
        <strong>${escapeHtml(check.label || "检查项")}</strong>
        <small>${escapeHtml(check.note || "")}</small>
      </div>
    </div>
  `;
}

function commandRollupCard(item) {
  return `
    <article class="command-rollup" data-tone="${escapeHtml(item.tone || "neutral")}">
      <div class="command-rollup-head">
        <div>
          <div class="label">${escapeHtml(item.label)}</div>
          <h4>${escapeHtml(item.title || item.label)}</h4>
        </div>
        <div class="status-pill ${toneClass(item.tone || "neutral")}">${escapeHtml(item.status || "状态")}</div>
      </div>
      <div class="command-rollup-value">${escapeHtml(item.value || "NA")}</div>
      <p class="command-rollup-note">${escapeHtml(item.note || "")}</p>
    </article>
  `;
}

function commandSceneCard(scene) {
  const readyLabel = scene.total_checks ? `${scene.ready_count || 0} / ${scene.total_checks} ready` : "";
  const metaItems = [...(scene.meta || [])];
  if (readyLabel) {
    metaItems.unshift(readyLabel);
  }
  return `
    <article class="command-scene-card" data-tone="${escapeHtml(scene.tone || "neutral")}" ${scene.recommended ? 'data-current="true"' : ""}>
      <div class="command-scene-top">
        <span class="command-scene-number">${escapeHtml(scene.number || "")}</span>
        <div class="status-pill ${toneClass(scene.tone || "neutral")}">${escapeHtml(scene.status || "待命")}</div>
      </div>
      <div>
        <div class="label">${escapeHtml(scene.eyebrow || "场景")}</div>
        <h3>${escapeHtml(scene.title || "")}</h3>
      </div>
      <p class="command-scene-note">${escapeHtml(compactSentence(scene.cue_line || scene.note || "", 120) || "等待操作员切换到本幕。")}</p>
      ${metaItems.length ? `
        <div class="command-scene-meta">
          ${metaItems.slice(0, 3).map((item) => `<span>${escapeHtml(item)}</span>`).join("")}
        </div>
      ` : ""}
      <div class="command-scene-actions">
        ${commandJumpButton(scene.jump, scene.jump?.primary)}
        ${scene.jump_hint ? `<span class="status-inline">${escapeHtml(scene.jump_hint)}</span>` : ""}
      </div>
    </article>
  `;
}

function archiveCommandSummary(systemStatus) {
  const archiveSummary = state.archiveSession?.summary || {};
  const eventSpine = systemStatus.event_spine || {};
  const sessionId =
    archiveSummary.session_id ||
    state.selectedArchiveSessionId ||
    state.currentArchiveSessionId ||
    eventSpine.session_id ||
    "archive pending";
  const eventCount = archiveSummary.event_count ?? eventSpine.event_count ?? 0;
  const lastEvent =
    archiveSummary.last_event_type ||
    archiveSummary.last_snapshot_reason ||
    eventSpine.last_event_at ||
    "等待首次写盘";
  const readErrors = state.archiveSession?.read_errors || [];
  const tone = readErrors.length
    ? "degraded"
    : archiveSummary.session_id
      ? eventCount > 0
        ? "online"
        : "neutral"
      : eventCount > 0
        ? "degraded"
        : "neutral";
  return {
    sessionId,
    eventCount,
    lastEvent,
    tone,
    note: archiveSummary.session_id
      ? `${eventCount} events / ${lastEvent}`
      : "当前仍可能显示 mission fallback timeline，直到本地 archive 会话写盘。",
  };
}

function operatorCueSceneCard(scene, currentSceneId) {
  const recommended = scene.recommended || scene.scene_id === currentSceneId;
  const readyLabel = scene.total_checks ? `${scene.ready_count || 0} / ${scene.total_checks} ready` : (scene.jump_hint || "");
  return `
    <article class="operator-cue-scene-card" data-tone="${escapeHtml(scene.tone || "neutral")}" ${recommended ? 'data-current="true"' : ""}>
      <div class="operator-cue-scene-top">
        <div>
          <div class="label">${escapeHtml(scene.eyebrow || "场景")}</div>
          <h4>${escapeHtml(scene.title || "")}</h4>
        </div>
        <div class="status-pill ${toneClass(scene.tone || "neutral")}">${escapeHtml(scene.status || "待命")}</div>
      </div>
      <p class="compact-copy">${escapeHtml(compactSentence(scene.note || scene.cue_line || "", 88) || "等待操作员推进。")}</p>
      ${readyLabel ? `<div class="status-inline">${escapeHtml(readyLabel)}</div>` : ""}
    </article>
  `;
}

function renderOperatorCue(cue) {
  const shell = document.getElementById("operatorCueShell");
  if (!cue.currentSceneLabel) {
    shell.innerHTML = `
      <div class="label">Operator Cue</div>
      <p class="compact-copy">等待 operator cue 数据。</p>
    `;
    return;
  }
  const currentScene =
    cue.scenes.find((scene) => scene.scene_id === cue.currentSceneId)
    || cue.scenes.find((scene) => scene.recommended)
    || cue.scenes[0]
    || null;
  const currentChecks = Array.isArray(currentScene?.checks) ? currentScene.checks : [];
  const nextStep = cue.nextStepNote || cue.nextStepLabel || compactManualNote(cue.manualBoundaryNote);
  const presenterLine = cue.presenterLine || currentScene?.cue_line || cue.nextStepNote || "";
  const boundaryBits = [
    compactManualNote(cue.manualBoundaryNote),
    compactSentence(cue.boundaryNote, 120),
  ].filter(Boolean).slice(0, 1);
  shell.innerHTML = `
    <div class="operator-cue-top">
      <div>
        <div class="label">Operator Cue</div>
        <h3>${escapeHtml(cue.currentSceneLabel)}</h3>
      </div>
      <div class="status-pill ${toneClass(cue.currentSceneTone || cue.statusTone || "neutral")}">${escapeHtml(cue.statusLabel || cue.currentSceneLabel)}</div>
    </div>
    ${currentScene ? `
      <div class="operator-cue-focus">
        <div class="operator-cue-focus-head">
          <div>
            <div class="label">Presenter Line</div>
            <strong>${escapeHtml(currentScene.title || cue.currentSceneLabel)}</strong>
          </div>
          <div class="status-pill ${toneClass(currentScene.tone || cue.currentSceneTone || "neutral")}">${escapeHtml(currentScene.status || cue.statusLabel || "待命")}</div>
        </div>
        <p class="operator-cue-line">${escapeHtml(compactSentence(presenterLine, 116))}</p>
        ${currentChecks.length ? `<div class="operator-cue-check-grid">${currentChecks.map((check) => cueCheckChip(check)).join("")}</div>` : ""}
      </div>
    ` : ""}
    <div class="operator-cue-actions">
      <div class="operator-cue-copy">
        <div class="label">Next Operator Action</div>
        <div class="compact-copy">${escapeHtml(compactSentence(nextStep, 108))}</div>
      </div>
      ${commandJumpButton(cue.nextAction, true)}
    </div>
    <div class="operator-cue-boundary-list">
      ${boundaryBits.map((item) => `<p class="compact-copy operator-cue-subnote">${escapeHtml(item)}</p>`).join("")}
    </div>
  `;
}

function buildCommandCenterModel(snapshot, systemStatus) {
  const mission = snapshot.mission || {};
  const live = systemStatus.live || {};
  const boardAccess = systemStatus.board_access || {};
  const gate = systemStatus.job_manifest_gate || {};
  const safetyPanel = effectiveSafetyPanel(systemStatus);
  const linkDirector = effectiveLinkDirectorStatus(snapshot);
  const operatorCue = normalizeOperatorCue(systemStatus.operator_cue || {});
  const selectedLinkProfile = linkDirector.selected_profile || {};
  const archive = archiveCommandSummary(systemStatus);
  const compareSample = selectedCompareViewerSample(snapshot);
  const currentPane = compareViewerPaneState(snapshot, "current");
  const baselinePane = compareViewerPaneState(snapshot, "baseline");
  const active = systemStatus.active_inference || {};
  const activeProgress = normalizeProgress(active.progress || null);
  const currentLiveProgress =
    active.running && active.variant === "current"
      ? activeProgress
      : normalizeProgress(state.currentResult?.live_progress || null);
  const currentLiveDone = Boolean(state.currentResult && state.currentResult.request_state !== "running");
  const currentFallback =
    state.currentResult?.status === "fallback" || state.currentResult?.execution_mode === "prerecorded";
  const boardBusy = String(live.guard_state || "").toUpperCase() === "JOB_ACTIVE";
  const faultLatched = String(safetyPanel.latch_state || "").toUpperCase() === "LATCHED";

  let summaryLabel = operatorCue.currentSceneLabel || "指挥席就绪";
  let summaryTone = operatorCue.currentSceneTone || "online";
  let summaryText = operatorCue.nextStepNote
    || "把会话、Current / Compare、安全与 archive 收在同一操作层；所有推进仍由操作员手动触发。";
  let primaryJump = operatorCue.nextAction || { label: "跳到第三幕 Compare", actId: "act3", targetId: "compareViewerShell", primary: true };

  if (!operatorCue.currentSceneLabel && faultLatched) {
    summaryLabel = "安全收口优先";
    summaryTone = safetyPanel.panel_tone || "offline";
    summaryText =
      `当前 last_fault_code=${safetyPanel.last_fault_code || "UNKNOWN"} 仍锁存在控制面镜像中；是否执行 SAFE_STOP 收口仍由操作员决定。`;
    primaryJump = { label: "跳到第四幕 SAFE_STOP", actId: "act4", targetId: "act4Panel", primary: true };
  } else if (!operatorCue.currentSceneLabel && !boardAccess.connection_ready) {
    summaryLabel = "先补本场会话";
    summaryTone = systemStatus.execution_mode?.tone || "degraded";
    summaryText = systemStatus.execution_mode?.summary || "先录入本场板卡会话，再触发真机探板和 live 动作。";
    primaryJump = { label: "跳到会话接入", targetId: "credentialPanel", primary: true };
  } else if (!operatorCue.currentSceneLabel && !live.board_online) {
    summaryLabel = "先完成探板";
    summaryTone = systemStatus.execution_mode?.tone || "degraded";
    summaryText =
      "当前没有新的 live 板卡读数。第一幕会继续如实显示证据态，但若要推进真机动作，需要先由操作员执行探板。";
    primaryJump = { label: "跳到第一幕探板", actId: "act1", targetId: "act1Panel", primary: true };
  } else if (!operatorCue.currentSceneLabel && boardBusy) {
    summaryLabel = "等待当前作业收口";
    summaryTone = activeProgress.tone || "degraded";
    summaryText =
      `guard_state=JOB_ACTIVE；当前 count=${currentLiveProgress.count_label || activeProgress.count_label || "进行中"}。页面只做监看和跳转，不自动 SAFE_STOP。`;
    primaryJump = {
      label: active.variant === "baseline" ? "查看第三幕进度" : "查看第二幕进度",
      actId: active.variant === "baseline" ? "act3" : "act2",
      targetId: active.variant === "baseline" ? "act3Panel" : "act2Panel",
      primary: true,
    };
  } else if (!operatorCue.currentSceneLabel && String(gate.verdict || "").toLowerCase() !== "allow") {
    summaryLabel = "先看任务票闸机";
    summaryTone = gate.tone || "degraded";
    summaryText =
      gate.message || "当前 ticket 仍处于草案或保守阻断态；页面不会把它包装成已放行。";
    primaryJump = { label: "跳到任务票闸机", actId: "act1", targetId: "jobManifestGateShell", primary: true };
  } else if (!operatorCue.currentSceneLabel && !state.currentResult) {
    summaryLabel = "推进第二幕 Current live";
    summaryTone = "online";
    summaryText =
      "会话、探板和 gate 均已具备后，第二幕仍由操作员手动触发 Current 300 张图在线推进。";
    primaryJump = { label: "跳到第二幕 Current", actId: "act2", targetId: "act2Panel", primary: true };
  } else if (!operatorCue.currentSceneLabel && currentFallback) {
    summaryLabel = "当前仍是归档展示";
    summaryTone = "degraded";
    summaryText =
      "本场 Current 结果仍在归档/回退态。页面会如实保留 archive provenance，不伪装为本轮 live 已完成。";
    primaryJump = { label: "回到第二幕 Current", actId: "act2", targetId: "act2Panel", primary: true };
  } else if (!operatorCue.currentSceneLabel && !currentLiveDone) {
    summaryLabel = "等待第二幕推进";
    summaryTone = currentLiveProgress.tone || "degraded";
    summaryText =
      `Current live 当前状态=${currentLiveProgress.label || "等待触发"}；第三幕对照会继续沿用同一选样和边界口径。`;
    primaryJump = { label: "跳到第二幕 Current", actId: "act2", targetId: "act2Panel", primary: true };
  } else if (!operatorCue.currentSceneLabel && safetyPanel.safe_stop_state === "RECOVERED") {
    summaryLabel = "SAFE_STOP 已收口";
    summaryTone = safetyPanel.panel_tone || "degraded";
    summaryText =
      "最近一次 SAFE_STOP 收口结果已经回写到当前面板镜像；是否继续演示仍由操作员决定，Linux UI 不宣称物理所有权。";
    primaryJump = { label: "跳到第四幕 SAFE_STOP", actId: "act4", targetId: "act4Panel", primary: true };
  }

  const sessionTarget = boardAccess.host
    ? `${boardAccess.user || "user"}@${boardAccess.host}:${boardAccess.port || 22}`
    : "未录入本场会话";
  const currentCompareTone =
    active.running && active.variant === "current"
      ? activeProgress.tone || "online"
      : currentFallback
        ? "degraded"
        : currentPane?.badgeTone === "online" || baselinePane?.badgeTone === "online"
          ? "online"
          : currentPane?.badgeTone || baselinePane?.badgeTone || "neutral";
  const rollups = [
    {
      label: "Launch Readiness",
      title: "会话与 Gate",
      status: boardAccess.connection_ready ? (gate.verdict_label || "待预检") : "待会话",
      value: boardAccess.connection_ready ? sessionTarget : "补录 SSH / env",
      note: boardAccess.connection_ready
        ? `${gate.label || "Job Manifest Gate"} ｜ ${gate.message || gate.admission_label || "等待预检"}`
        : `仍缺 ${summarizeMissing(boardAccess.missing_connection_fields || [])}`,
      tone: !boardAccess.connection_ready ? "degraded" : gate.tone || "neutral",
    },
    {
      label: "Current / Compare",
      title: "第二幕到第三幕",
      status: active.running && active.variant === "current"
        ? activeProgress.label || "推进中"
        : currentFallback
          ? "archive fallback"
          : currentLiveDone
            ? state.currentResult?.source_label || "Current ready"
            : compareSample?.sample?.label || "待选样例",
      value: compareSample?.sample?.label || currentLiveProgress.count_label || "等待样例",
      note: `${currentPane?.badgeLabel || "current pending"} ｜ ${baselinePane?.badgeLabel || "baseline pending"} ｜ ${selectedLinkProfile.label || linkDirector.selected_profile_label || "normal link"}`,
      tone: currentCompareTone,
    },
    {
      label: "Safety / Archive",
      title: "SAFE_STOP 与 Blackbox",
      status: safetyPanel.panel_label || "安全态",
      value: archive.eventCount > 0 ? `${archive.eventCount} events` : (safetyPanel.safe_stop_state || "archive pending"),
      note: archive.eventCount > 0
        ? `${archive.sessionId} ｜ ${archive.lastEvent}`
        : `fault=${safetyPanel.last_fault_code || "UNKNOWN"} ｜ ${safetyPanel.status_source || "unknown"}`,
      tone: faultLatched ? (safetyPanel.panel_tone || "offline") : archive.tone || safetyPanel.panel_tone || "neutral",
    },
  ];

  const defaultScenes = [
    {
      number: "01",
      eyebrow: "可信状态",
      title: "第一幕 / 板卡接入与 gate",
      status: !boardAccess.connection_ready
        ? "待录入会话"
        : !live.board_online
          ? "待探板"
          : String(gate.verdict || "").toLowerCase() === "allow"
            ? "可信状态就绪"
            : gate.verdict_label || "待预检",
      note: !boardAccess.connection_ready
        ? "先补齐本场 SSH / 推理会话，然后再做 live 探板。"
        : live.board_online
          ? `board=${live.remoteproc_state || "unknown"} / guard=${live.guard_state || "UNKNOWN"}。`
          : "当前仍显示证据态；探板后会更新 live board / RPMsg / guard_state。",
      meta: [
        `admission=${gate.admission_label || "未设置"}`,
        `manifest=${gate.verdict_label || "待补全"}`,
      ],
      tone: !boardAccess.connection_ready ? "degraded" : live.board_online ? (gate.tone || "online") : "degraded",
      jump: {
        label: !boardAccess.connection_ready ? "跳到会话接入" : "跳到第一幕",
        actId: !boardAccess.connection_ready ? "" : "act1",
        targetId: !boardAccess.connection_ready ? "credentialPanel" : "jobManifestGateShell",
      },
      jump_hint: !boardAccess.connection_ready ? "录入本场会话" : "看探板与 ticket gate",
    },
    {
      number: "02",
      eyebrow: "语义回传",
      title: "第二幕 / Current live",
      status: active.running && active.variant === "current"
        ? activeProgress.label || "推进中"
        : currentFallback
          ? "归档展示"
          : currentLiveDone
            ? state.currentResult?.source_label || "Current live 已落盘"
            : "待推进",
      note: active.running && active.variant === "current"
        ? activeProgress.current_stage || "Current live 正在推进。"
        : currentFallback
          ? state.currentResult?.message || "当前画面仍在归档 / fallback 态。"
          : currentLiveDone
            ? state.currentResult?.message || "Current live 结果已回到页面。"
            : "会话与 gate 就位后，由操作员手动发起 300 张图在线推进。",
      meta: [
        `count=${currentLiveProgress.count_label || "0 / 300"}`,
        `mode=${state.currentResult?.execution_mode || "pending"}`,
      ],
      tone: active.running && active.variant === "current"
        ? activeProgress.tone || "online"
        : currentFallback
          ? "degraded"
          : currentLiveDone
            ? "online"
            : "neutral",
      jump: { label: "跳到第二幕", actId: "act2", targetId: "act2Panel" },
      jump_hint: "看 live progress 与样例画面",
    },
    {
      number: "03",
      eyebrow: "正式对照",
      title: "第三幕 / Compare viewer",
      status: compareSample?.sample?.label
        ? `${compareSample.sample.label} / 对照就位`
        : "待选样例",
      note: compareSample?.sample?.label
        ? `Current=${currentPane?.badgeLabel || "pending"}，Baseline=${baselinePane?.badgeLabel || "pending"}。`
        : "第三幕会沿用当前样例选择，并继续明确区分 4-core performance 与 3-core demo boundary。",
      meta: [
        compareSample?.sample?.title || "等待样例上下文",
        "4-core headline / 3-core live boundary",
      ],
      tone:
        currentPane?.badgeTone === "online" || baselinePane?.badgeTone === "online"
          ? "online"
          : currentPane?.badgeTone || baselinePane?.badgeTone || "neutral",
      jump: { label: "跳到第三幕", actId: "act3", targetId: "compareViewerShell" },
      jump_hint: "看样例 provenance 与正式口径",
    },
    {
      number: "04",
      eyebrow: "故障收口",
      title: "第四幕 / SAFE_STOP 与 archive",
      status: faultLatched
        ? "告警锁存"
        : safetyPanel.safe_stop_state === "RECOVERED"
          ? "SAFE_STOP 已收口"
          : "SAFE_STOP 待命",
      note: faultLatched
        ? `last_fault_code=${safetyPanel.last_fault_code || "UNKNOWN"}；Linux UI 只显示镜像与恢复入口。`
        : `${archive.sessionId} ｜ ${archive.eventCount} events ｜ ${archive.lastEvent}`,
      meta: [
        `SAFE_STOP=${safetyPanel.safe_stop_state || "UNKNOWN"}`,
        `archive=${archive.eventCount} events`,
      ],
      tone: faultLatched ? (safetyPanel.panel_tone || "offline") : archive.tone || safetyPanel.panel_tone || "neutral",
      jump: { label: "跳到第四幕", actId: "act4", targetId: "act4Panel" },
      jump_hint: "看 fault / recover 与 blackbox timeline",
    },
  ];

  return {
    boundaryNote: operatorCue.boundaryNote || mission.mode_split_note || "",
    summaryLabel,
    summaryTone,
    summaryText,
    primaryJump,
    rollups,
    quickJumps: operatorCue.quickJumps.length ? operatorCue.quickJumps.slice(0, 5) : [
      { label: "会话接入", targetId: "credentialPanel" },
      { label: "第一幕可信状态", actId: "act1", targetId: "act1Panel" },
      { label: "第二幕 Current", actId: "act2", targetId: "act2Panel" },
      { label: "第三幕 Compare", actId: "act3", targetId: "compareViewerShell" },
      { label: "第四幕 SAFE_STOP", actId: "act4", targetId: "act4Panel" },
    ],
    manualNote: compactManualNote(operatorCue.manualBoundaryNote),
    scenes: operatorCue.scenes.length ? operatorCue.scenes : defaultScenes,
    operatorCue,
  };
}

function renderCommandCenter(snapshot, systemStatus) {
  const model = buildCommandCenterModel(snapshot, systemStatus);
  document.getElementById("commandCenterBoundaryNote").textContent =
    compactModeBoundary(model.boundaryNote || snapshot.mission?.mode_split_note || "");
  renderOperatorCue(model.operatorCue);
  document.getElementById("commandStripCard").innerHTML = `
    <div class="command-strip-head">
      <div>
        <div class="label">Primary Story</div>
        <h3>${escapeHtml(model.summaryLabel)}</h3>
      </div>
      <div class="status-pill ${toneClass(model.summaryTone || "neutral")}">${escapeHtml(model.operatorCue.currentSceneId ? `Scene ${model.operatorCue.currentSceneId.replace("scene", "")}` : model.summaryLabel)}</div>
    </div>
    <p class="command-strip-summary">${escapeHtml(compactSentence(model.summaryText, 200))}</p>
    <div class="command-primary-row">
      <div class="command-primary-copy">
        <div class="label">Next Operator Action</div>
        <div class="compact-copy">${escapeHtml(model.primaryJump.label || model.manualNote)}</div>
        <div class="status-inline">${escapeHtml(model.manualNote)}</div>
      </div>
      ${commandJumpButton(model.primaryJump, true)}
    </div>
    <div class="command-guard-row">
      <span>${escapeHtml(compactModeBoundary(model.boundaryNote || snapshot.mission?.mode_split_note || ""))}</span>
      <span>${escapeHtml(model.rollups[2]?.note || model.manualNote)}</span>
    </div>
    <div class="command-rollup-grid">
      ${model.rollups.map((item) => commandRollupCard(item)).join("")}
    </div>
  `;
  document.getElementById("commandQuickJumpRow").innerHTML = model.quickJumps
    .map((item) => commandJumpButton(item, false))
    .join("");
  document.getElementById("commandSceneGrid").innerHTML = model.scenes
    .map((scene) => commandSceneCard(scene))
    .join("");
}

function effectiveSafetyPanel(systemStatus) {
  const live = systemStatus.live || {};
  const lastFault = state.faultResult || systemStatus.last_fault || {};
  const panel = systemStatus.safety_panel || {};
  if (panel.safe_stop_state) {
    return {
      ...panel,
      last_fault_result: panel.last_fault_result || {},
      recover_action: panel.recover_action || {},
    };
  }

  const lastFaultCode = lastFault.last_fault_code || live.last_fault_code || "UNKNOWN";
  const recovered = lastFault.status === "recovered";
  const latched = !["", "NONE", "UNKNOWN"].includes(String(lastFaultCode).toUpperCase());
  return {
    panel_label: recovered ? "SAFE_STOP 已执行" : (latched ? "告警锁存" : "无告警"),
    panel_tone: recovered ? (lastFaultCode === "NONE" ? "online" : "degraded") : (latched ? "offline" : "online"),
    safe_stop_state: recovered ? "RECOVERED" : (latched ? "FAULT" : "IDLE"),
    safe_stop_tone: recovered ? (lastFaultCode === "NONE" ? "online" : "degraded") : (latched ? "offline" : "online"),
    safe_stop_note: recovered
      ? "最近一次 recover 已记录到当前面板镜像。"
      : "当前 SAFE_STOP 继续沿用现有控制面语义，不扩展物理 GPIO 所有权。",
    latch_state: latched ? "LATCHED" : "CLEAR",
    latch_tone: latched ? "offline" : "online",
    latch_note: latched ? `last_fault_code=${lastFaultCode}` : "当前没有新的 fault latch。",
    guard_state: lastFault.guard_state || live.guard_state || "UNKNOWN",
    last_fault_code: lastFaultCode,
    total_fault_count: live.total_fault_count ?? 0,
    board_online: Boolean(live.board_online),
    status_source: live.status_source || "unknown",
    status_note: lastFault.message || live.status_note || "",
    last_fault_result: {
      status: lastFault.status || "",
      execution_mode: lastFault.execution_mode || "",
      source_label: lastFault.source_label || "",
      message: lastFault.message || "",
      guard_state: lastFault.guard_state || live.guard_state || "UNKNOWN",
      last_fault_code: lastFaultCode,
      status_lamp: lastFault.status_lamp || "",
      log_tail: lastLogLine(lastFault.log_entries),
    },
    recover_action: {
      action_id: "recover_safe_stop",
      label: "SAFE_STOP 收口",
      api_path: "/api/recover",
      method: "POST",
      note: "沿用现有 recover action，不新增 destructive 操作。",
    },
    ownership_note: "RTOS/Bare Metal owns physical SAFE_STOP/GPIO; Linux UI is mirror/control surface only.",
  };
}

function safetyIndicator(label, value, tone = "neutral", note = "") {
  return `
    <div class="safety-indicator" data-tone="${escapeHtml(tone)}">
      <div class="status-dot ${lampClass(tone)}"></div>
      <div>
        <span>${escapeHtml(label)}</span>
        <strong>${escapeHtml(value)}</strong>
        ${note ? `<small>${escapeHtml(note)}</small>` : ""}
      </div>
    </div>
  `;
}

function safetyReadout(label, value, note = "") {
  return `
    <div class="safety-readout">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
      ${note ? `<small>${escapeHtml(note)}</small>` : ""}
    </div>
  `;
}

function renderSafetyFrontPanel(safetyPanel) {
  const lastResult = safetyPanel.last_fault_result || {};
  const recoverAction = safetyPanel.recover_action || {};
  const lastResultVisible = Boolean(lastResult.status || lastResult.message || lastResult.source_label || lastResult.log_tail);
  const footerBits = [
    `${recoverAction.label || "SAFE_STOP 收口"} ${recoverAction.method || "POST"} ${recoverAction.api_path || "/api/recover"}`.trim(),
    safetyPanel.ownership_note || "",
    safetyPanel.status_note || "",
  ].filter(Boolean);
  const headlineNote = [safetyPanel.panel_label || "", safetyPanel.safe_stop_note || ""].filter(Boolean).join(" ｜ ");
  return `
    <div class="safety-front-panel" data-tone="${escapeHtml(safetyPanel.panel_tone || "neutral")}">
      <div class="safety-front-top">
        <div class="safety-big-readout">
          <span>SAFE_STOP mirror</span>
          <strong>${escapeHtml(safetyPanel.safe_stop_state || "UNKNOWN")}</strong>
          <small>${escapeHtml(headlineNote)}</small>
        </div>
        <div class="safety-indicator-grid">
          ${safetyIndicator("LATCH", safetyPanel.latch_state || "UNKNOWN", safetyPanel.latch_tone || "neutral", "fault latch")}
          ${safetyIndicator("BOARD", safetyPanel.board_online ? "ONLINE" : "OFFLINE", safetyPanel.board_online ? "online" : "degraded", safetyPanel.status_source || "status source")}
          ${safetyIndicator("SOURCE", safetyPanel.status_source || "unknown", safetyPanel.panel_tone || "neutral", "live / evidence")}
        </div>
      </div>
      <div class="safety-readout-grid">
        ${safetyReadout("guard_state", safetyPanel.guard_state || "UNKNOWN", "控制面 guard_state")}
        ${safetyReadout("fault code", safetyPanel.last_fault_code || "UNKNOWN", "保留原始 last_fault_code")}
        ${safetyReadout("fault count", String(safetyPanel.total_fault_count ?? 0), safetyPanel.latch_note || "control plane 计数")}
      </div>
      ${lastResultVisible ? `
        <div class="safety-trace">
          <div class="label">最近 replay / live 结果</div>
          <strong>${escapeHtml(lastResult.source_label || lastResult.status || "最近结果")}</strong>
          <p class="compact-copy">${escapeHtml(lastResult.message || lastResult.log_tail || "当前没有额外 last_fault 结果。")}</p>
          <div class="status-meta">
            <span>mode=${escapeHtml(lastResult.execution_mode || "NA")}</span>
            <span>status=${escapeHtml(lastResult.status || "NA")}</span>
            <span>guard=${escapeHtml(lastResult.guard_state || safetyPanel.guard_state || "UNKNOWN")}</span>
            <span>fault=${escapeHtml(lastResult.last_fault_code || safetyPanel.last_fault_code || "UNKNOWN")}</span>
          </div>
        </div>
      ` : ""}
      <p class="compact-copy safety-footer">${escapeHtml(footerBits.join(" ｜ "))}</p>
    </div>
  `;
}

function renderFlowStrip(stages) {
  if (!stages || !stages.length) return "";
  return `
    <div class="flow-strip">
      ${stages
        .map(
          (stage) => `
            <div class="flow-chip" data-status="${escapeHtml(stage.status || "pending")}">
              <span>${escapeHtml(stage.label || stage.key || "阶段")}</span>
              <strong>${escapeHtml(stage.status === "done" ? "已完成" : stage.status === "current" ? "推进中" : stage.status === "error" ? "阻断" : "待命")}</strong>
            </div>
          `
        )
        .join("")}
    </div>
  `;
}

function latestResultForVariant(variant) {
  if (variant === "baseline") {
    if (state.baselineResult) return state.baselineResult;
  } else if (state.currentResult) {
    return state.currentResult;
  }
  const recent = state.systemStatus?.recent_results?.[variant];
  if (recent) return recent;
  const lastInference = state.systemStatus?.last_inference || {};
  return lastInference.variant === variant ? lastInference : null;
}

function hydrateRecentResultsFromSystemStatus(systemStatus) {
  const recentResults = systemStatus?.recent_results || {};
  if (recentResults.current) {
    state.currentResult = recentResults.current;
  }
  if (recentResults.baseline) {
    state.baselineResult = recentResults.baseline;
  }
}

function effectiveLinkDirectorStatus(snapshot) {
  const missionDirector = snapshot?.mission?.link_director || {};
  const fallbackSelectedId = state.linkDirectorStatus?.selected_profile_id || "normal";
  const profiles = (state.linkDirectorStatus?.profiles || missionDirector.profiles || []).map((profile) => ({
    ...profile,
    active: profile.active !== undefined ? profile.active : profile.profile_id === fallbackSelectedId,
  }));
  const selectedProfile = state.linkDirectorStatus?.selected_profile
    || profiles.find((profile) => profile.active)
    || profiles.find((profile) => profile.profile_id === fallbackSelectedId)
    || profiles[0]
    || {};
  return {
    status: state.linkDirectorStatus?.status || "idle",
    label: state.linkDirectorStatus?.label || "导演台待命",
    tone: state.linkDirectorStatus?.tone || selectedProfile.tone || "neutral",
    backend_binding: state.linkDirectorStatus?.backend_binding || missionDirector.backend_status || "ui_scaffold_only",
    backend_status: state.linkDirectorStatus?.backend_status || missionDirector.backend_status || "ui_scaffold_only",
    summary: state.linkDirectorStatus?.summary || missionDirector.summary || "",
    plane_split_note: state.linkDirectorStatus?.plane_split_note || missionDirector.plane_split_note || "",
    mode_boundary_note: state.linkDirectorStatus?.mode_boundary_note || snapshot?.mission?.mode_split_note || "",
    truth_note: state.linkDirectorStatus?.truth_note || "当前仅记录导演台预案；live 控制面与证据读数继续如实显示。",
    selected_profile_id: state.linkDirectorStatus?.selected_profile_id || selectedProfile.profile_id || "normal",
    selected_profile_label: state.linkDirectorStatus?.selected_profile_label || selectedProfile.label || "正常链路",
    selected_profile: selectedProfile,
    profiles,
    last_applied_at: state.linkDirectorStatus?.last_applied_at || "",
    last_operator_action: state.linkDirectorStatus?.last_operator_action || missionDirector.summary || "",
    change_applied: state.linkDirectorStatus?.change_applied,
    status_message: state.linkDirectorStatus?.status_message || "",
  };
}

function weakNetworkCatalog(snapshot) {
  const weakNetwork = snapshot?.weak_network || {};
  const scenarios = Array.isArray(weakNetwork.scenarios) ? weakNetwork.scenarios : [];
  return {
    ...weakNetwork,
    scenarios,
    recommendedScenarioId: weakNetwork.recommended_scenario_id || scenarios[0]?.scenario_id || "",
  };
}

function resolveWeakNetworkSelection(snapshot) {
  const catalog = weakNetworkCatalog(snapshot);
  const linkDirector = effectiveLinkDirectorStatus(snapshot);
  const linkedScenarioId = linkDirector.selected_profile?.evidence_binding?.scenario_id || "";
  const preferredId = state.selectedWeakScenarioId || linkedScenarioId || catalog.recommendedScenarioId;
  const selectedScenario =
    catalog.scenarios.find((item) => item.scenario_id === preferredId)
    || catalog.scenarios.find((item) => item.recommended)
    || catalog.scenarios[0]
    || null;
  return {
    catalog,
    linkedScenarioId,
    selectedScenario,
  };
}

function syncWeakNetworkSelection(snapshot) {
  const catalog = weakNetworkCatalog(snapshot);
  const knownIds = new Set(catalog.scenarios.map((item) => item.scenario_id));
  const linkedScenarioId = effectiveLinkDirectorStatus(snapshot).selected_profile?.evidence_binding?.scenario_id || "";
  if (state.selectedWeakScenarioId && knownIds.has(state.selectedWeakScenarioId)) {
    return;
  }
  if (linkedScenarioId && knownIds.has(linkedScenarioId)) {
    state.selectedWeakScenarioId = linkedScenarioId;
    return;
  }
  state.selectedWeakScenarioId = catalog.recommendedScenarioId || "";
}

function effectiveAircraftPosition(snapshot, systemStatus) {
  return systemStatus?.aircraft_position || snapshot?.aircraft_position || {};
}

function aircraftFeedTone(aircraft) {
  const status = String(aircraft?.source_status || "").toLowerCase();
  if (status === "live") return "online";
  if (status === "stale") return "degraded";
  if (status === "stub") return "degraded";
  return "neutral";
}

function aircraftFeedStateLabel(aircraft) {
  const status = String(aircraft?.source_status || "").toLowerCase();
  if (status === "live") return "LIVE";
  if (status === "stale") return "STALE";
  if (status === "stub") return "STUB";
  return status ? status.toUpperCase() : "UNKNOWN";
}

function aircraftContractValue(aircraft) {
  return aircraft?.feed_contract?.active_source_label || aircraft?.source_label || "Backend Stub Contract";
}

function aircraftScreenPosition(aircraft) {
  const latitude = Number(aircraft?.position?.latitude);
  const longitude = Number(aircraft?.position?.longitude);
  if (Number.isNaN(latitude) || Number.isNaN(longitude)) {
    return { left: 50, top: 48 };
  }
  const left = Math.max(8, Math.min(92, ((longitude + 180) / 360) * 100));
  const top = Math.max(10, Math.min(90, ((90 - latitude) / 180) * 100));
  return { left, top };
}

function aircraftReadoutCard(label, value, note, tone = "neutral") {
  return `
    <article class="aircraft-readout-card" data-tone="${escapeHtml(tone)}">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
      <small>${escapeHtml(note || "")}</small>
    </article>
  `;
}

function aircraftContractChip(label, value, tone = "neutral") {
  return `
    <div class="aircraft-contract-chip" data-tone="${escapeHtml(tone)}">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
    </div>
  `;
}

function cockpitSignalCell(label, value, note, tone = "neutral") {
  return `
    <article class="cockpit-signal-cell" data-tone="${escapeHtml(tone)}">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
      <small>${escapeHtml(note || "")}</small>
    </article>
  `;
}

function cockpitBusCell(label, value, tone = "neutral") {
  return `
    <article class="cockpit-bus-cell" data-tone="${escapeHtml(tone)}">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
    </article>
  `;
}

function aircraftRouteMarkup(track, aircraft) {
  const points = Array.isArray(track) ? track.slice() : [];
  const currentPoint = aircraft?.position || null;
  if (currentPoint && Number.isFinite(Number(currentPoint.latitude)) && Number.isFinite(Number(currentPoint.longitude))) {
    points.push(currentPoint);
  }
  if (points.length < 2) return "";
  const encoded = points
    .map((point) => {
      const position = aircraftScreenPosition({ position: point });
      return `${formatNumber(position.left, 2)},${formatNumber(position.top, 2)}`;
    })
    .join(" ");
  return `
    <polyline class="aircraft-route-glow" points="${encoded}"></polyline>
    <polyline class="aircraft-route-line" points="${encoded}"></polyline>
  `;
}

function aircraftTrailMarkup(track) {
  if (!Array.isArray(track) || !track.length) return "";
  const total = track.length;
  return track
    .map((point, index) => {
      const position = aircraftScreenPosition({ position: point });
      return `
        <span
          class="aircraft-trail-dot"
          style="left:${position.left}%; top:${position.top}%; opacity:${Math.max(0.18, (index + 1) / total)}"
        ></span>
      `;
    })
    .join("");
}

function cockpitMissionRollup(item) {
  return `
    <article class="cockpit-rollup" data-tone="${escapeHtml(item.tone || "neutral")}">
      <div class="label">${escapeHtml(item.label || "")}</div>
      <strong>${escapeHtml(item.status || item.value || "等待")}</strong>
      <span>${escapeHtml(item.value || "")}</span>
      <small>${escapeHtml(compactSentence(item.note || "", 58))}</small>
    </article>
  `;
}

function cockpitSceneChip(scene) {
  return `
    <article class="cockpit-scene-chip" data-tone="${escapeHtml(scene.tone || "neutral")}" ${scene.recommended ? 'data-current="true"' : ""}>
      <div class="cockpit-scene-chip-top">
        <span>${escapeHtml(scene.number || "")}</span>
        <strong>${escapeHtml(scene.status || "待命")}</strong>
      </div>
      <p>${escapeHtml(scene.title || "")}</p>
      <small>${escapeHtml(compactSentence(scene.note || scene.cue_line || "", 54))}</small>
    </article>
  `;
}

function lastLogLine(entries) {
  if (!entries || !entries.length) return "";
  return String(entries[entries.length - 1] || "");
}

function timelineEvent(stamp, lane, title, summary, tone, links = []) {
  return { stamp, lane, title, summary, tone, links };
}

function buildMissionTimeline(snapshot, systemStatus) {
  const items = [];
  const live = systemStatus.live || {};
  const active = systemStatus.active_inference || {};
  const activeProgress = active.progress || {};
  const lastInference = systemStatus.last_inference || {};
  const lastFault = state.faultResult || systemStatus.last_fault || {};

  if (live.last_probe_at) {
    items.push(
      timelineEvent(
        live.last_probe_at,
        "device",
        "板卡只读探板",
        `remoteproc=${live.remoteproc_state} | RPMsg=${live.rpmsg_device} | guard=${live.guard_state}`,
        live.board_online ? "online" : systemStatus.execution_mode?.tone || "degraded"
      )
    );
  }
  if (active.running) {
    items.push(
      timelineEvent(
        active.job_id || activeProgress.count_label || "live",
        "queue",
        `${active.variant === "baseline" ? "PyTorch" : active.variant === "current" ? "Current" : "板端"} 活动作业`,
        activeProgress.current_stage || active.message || "当前 live 作业正在推进。",
        activeProgress.tone || "degraded"
      )
    );
    const activeLog = lastLogLine(activeProgress.event_log);
    if (activeLog) {
      items.push(timelineEvent("live", "queue", "最近控制面事件", activeLog, activeProgress.tone || "degraded"));
    }
  } else if (lastInference.variant) {
    items.push(
      timelineEvent(
        systemStatus.generated_at,
        "return",
        `${lastInference.variant === "baseline" ? "PyTorch" : "Current"} 最近一次结果`,
        lastInference.message || lastInference.source_label || "已记录最近一次 operator 可见结果。",
        lastInference.execution_mode === "live" || lastInference.execution_mode === "reference" ? "online" : "degraded"
      )
    );
  }
  if (lastFault.last_fault_code) {
    items.push(
      timelineEvent(
        lastFault.status === "recovered" ? "SAFE_STOP" : lastFault.last_fault_code,
        "safety",
        lastFault.status === "recovered" ? "SAFE_STOP 收口" : "最近告警",
        lastLogLine(lastFault.log_entries) || lastFault.message || `last_fault_code=${lastFault.last_fault_code}`,
        lastFault.status_lamp === "green" ? "online" : lastFault.status_lamp === "yellow" ? "degraded" : "offline"
      )
    );
  }

  return items.concat(snapshot.mission?.archive_timeline || []).slice(0, 6);
}

function truncateMiddle(text, prefix = 32, suffix = 24) {
  const value = String(text || "");
  if (!value || value.length <= prefix + suffix + 3) return value || "未写入";
  return `${value.slice(0, prefix)}...${value.slice(-suffix)}`;
}

function archiveSessionOptionLabel(session) {
  const sessionId = session?.session_id || "archive session";
  const lastEvent = session?.last_event_type || session?.last_snapshot_reason || "pending";
  const currentSuffix = session?.is_current_session ? " / current" : "";
  return `${sessionId}${currentSuffix} / ${lastEvent}`;
}

function archivePathRow(label, value) {
  const text = String(value || "");
  return `
    <div class="archive-path-row">
      <span>${escapeHtml(label)}</span>
      <code title="${escapeHtml(text || "未写入")}">${escapeHtml(truncateMiddle(text))}</code>
    </div>
  `;
}

function archiveTimelineItems(snapshot, systemStatus) {
  const archiveSession = state.archiveSession;
  if (archiveSession?.timeline?.length) return archiveSession.timeline;
  return buildMissionTimeline(snapshot, systemStatus).map((item) => ({
    timestamp: item.stamp,
    lane: item.lane,
    title: item.title,
    summary: item.summary,
    tone: item.tone,
    source: "mission_snapshot",
    mode_scope: snapshot.mission?.mode_split_note || "",
    links: item.links || [],
  }));
}

function renderArchiveTimelineModule(snapshot, systemStatus) {
  const sessions = state.archiveSessions || [];
  const archiveSession = state.archiveSession;
  const summary = archiveSession?.summary || null;
  const selectedSessionId = state.selectedArchiveSessionId || "";
  const hasArchiveData = Boolean(summary);
  const timelineItems = archiveTimelineItems(snapshot, systemStatus);
  const selector = sessions.length
    ? `
      <label class="sample-picker archive-picker">
        <span>Archive Session</span>
        <select id="archiveSessionSelect">
          ${sessions
            .map(
              (session) => `
                <option value="${escapeHtml(session.session_id)}" ${session.session_id === selectedSessionId ? "selected" : ""}>
                  ${escapeHtml(archiveSessionOptionLabel(session))}
                </option>
              `
            )
            .join("")}
        </select>
      </label>
    `
    : `<div class="status-pill tone-neutral">Archive pending</div>`;
  const summaryMetrics = hasArchiveData
    ? `
      <div class="mission-metrics">
        ${missionMetric("Archive Session", summary.session_id || "NA", summary.last_event_at || "等待事件写入")}
        ${missionMetric("事件计数", String(summary.event_count ?? 0), summary.last_event_type || "尚无 recent event")}
        ${missionMetric("最近快照", summary.last_snapshot_reason || "尚未写入", summary.last_snapshot_at || "等待快照")}
      </div>
      <details class="archive-path-details">
        <summary>查看 archive 路径</summary>
        <div class="archive-path-grid">
          ${archivePathRow("session_dir", archiveSession.paths?.session_dir)}
          ${archivePathRow("events.jsonl", archiveSession.paths?.events_jsonl)}
          ${archivePathRow("state_snapshot.json", archiveSession.paths?.state_snapshot_json)}
        </div>
      </details>
    `
    : `
      <div class="archive-empty-state">
        <strong>Archive pending</strong>
        <p class="compact-copy">
          当前 session_id=${escapeHtml(state.currentArchiveSessionId || systemStatus.event_spine?.session_id || "unknown")}。
          一旦 JSONL / snapshot 落盘，这里会自动切到真实 blackbox timeline；现在保留 fallback timeline 只做态势参考。
        </p>
      </div>
    `;
  return `
    <div class="archive-toolbar">
      ${selector}
      <div class="status-inline">${escapeHtml(hasArchiveData ? "local-only / read-only replay" : "fallback timeline only")}</div>
    </div>
    <p class="compact-copy archive-summary-note">${escapeHtml(
      hasArchiveData
        ? `${summary.session_id} ｜ ${summary.event_count ?? 0} events ｜ ${summary.last_event_type || summary.last_snapshot_reason || "等待事件"}`
        : "尚无本地 archive session；当前仍显示 live / snapshot fallback timeline。"
    )}</p>
    ${summaryMetrics}
    <div class="event-list">
      ${timelineItems
        .map(
          (item) => `
            <article class="event-item" data-tone="${escapeHtml(item.tone || "neutral")}">
              <div class="event-head">
                <span class="event-stamp">${escapeHtml(item.timestamp || item.stamp || "NA")}</span>
                <span class="event-lane">${escapeHtml(item.lane || "event")}</span>
              </div>
              <strong>${escapeHtml(item.title || item.type || "事件")}</strong>
              <p class="compact-copy">${escapeHtml(item.summary || "")}</p>
              <div class="status-meta">
                ${item.source ? `<span>source=${escapeHtml(item.source)}</span>` : ""}
                ${item.job_id ? `<span>job_id=${escapeHtml(item.job_id)}</span>` : ""}
                ${item.mode_scope ? `<span>${escapeHtml(item.mode_scope)}</span>` : ""}
              </div>
              ${renderLinks(item.links || [])}
            </article>
          `
        )
        .join("")}
    </div>
  `;
}

function setFeedback(message, tone) {
  const banner = document.getElementById("feedbackBanner");
  if (!message) {
    banner.hidden = true;
    banner.textContent = "";
    banner.removeAttribute("data-tone");
    return;
  }
  banner.hidden = false;
  banner.setAttribute("data-tone", tone);
  banner.textContent = message;
}

function renderCockpitShell(snapshot, systemStatus) {
  const cue = normalizeOperatorCue(systemStatus.operator_cue || {});
  const latestLive = snapshot.latest_live_status || {};
  const live = systemStatus.live || {};
  const safetyPanel = effectiveSafetyPanel(systemStatus);
  const linkDirector = effectiveLinkDirectorStatus(snapshot);
  const weakNetwork = resolveWeakNetworkSelection(snapshot);
  const selectedScenario = weakNetwork.selectedScenario;
  const aircraft = effectiveAircraftPosition(snapshot, systemStatus);
  const aircraftPosition = aircraftScreenPosition(aircraft);
  const boundary = compactModeBoundary(cue.boundaryNote || snapshot.mission?.mode_split_note || "");
  const nextStep = compactSentence(cue.nextStepNote || cue.nextStepLabel || "等待操作员选择下一步。", 128);
  const sceneLabel = cue.currentSceneLabel || systemStatus.execution_mode.label || "Command deck";
  const model = buildCommandCenterModel(snapshot, systemStatus);
  const active = systemStatus.active_inference || {};
  const activeProgress = normalizeProgress(active.progress || null);
  const currentResult = latestResultForVariant("current");
  const currentProgress =
    active.running && active.variant === "current"
      ? activeProgress
      : normalizeProgress(currentResult?.live_progress || null);
  const currentPane = compareViewerPaneState(snapshot, "current");
  const baselinePane = compareViewerPaneState(snapshot, "baseline");
  const comparison = snapshot.guided_demo?.comparison || {};
  document.getElementById("cockpitHeadline").textContent =
    [
      sceneLabel,
      `BOARD ${live.board_online ? "ONLINE" : "EVIDENCE"}`,
      `GUARD ${live.guard_state || "UNKNOWN"}`,
      `GPS ${aircraftFeedStateLabel(aircraft)}`,
      `NEXT ${nextStep}`,
    ].join(" · ");

  const modePill = document.getElementById("cockpitModePill");
  modePill.className = `mode-pill ${toneClass(systemStatus.execution_mode.tone)}`;
  modePill.textContent = systemStatus.execution_mode.label;
  document.getElementById("cockpitSummaryLine").textContent = compactSentence(systemStatus.execution_mode.summary || "等待执行模式。", 104);
  document.getElementById("cockpitTimestamp").textContent = `快照更新 ${snapshot.generated_at}`;
  document.getElementById("cockpitBoundaryNote").textContent = boundary;
  const signalStrip = document.getElementById("cockpitSignalStrip");
  if (signalStrip) {
    signalStrip.innerHTML = [
      cockpitSignalCell("Board Link", live.board_online ? "ONLINE" : "EVIDENCE", `fault=${live.last_fault_code || "UNKNOWN"}`, live.board_online ? "online" : "degraded"),
      cockpitSignalCell("Guard State", live.guard_state || "UNKNOWN", compactSentence(systemStatus.execution_mode.label || "等待执行模式。", 30), live.board_online ? "online" : "neutral"),
      cockpitSignalCell("Aircraft Feed", aircraftFeedStateLabel(aircraft), aircraftContractValue(aircraft), aircraftFeedTone(aircraft)),
    ].join("");
  }
  const busGrid = document.getElementById("cockpitBusGrid");
  if (busGrid) {
    busGrid.innerHTML = [
      cockpitBusCell("Link Profile", linkDirector.selected_profile_label || "Nominal", linkDirector.tone || "neutral"),
      cockpitBusCell(
        "Feed Sample",
        `#${aircraft.sample?.sequence ?? 0} · ${compactTimestampLabel(aircraft.sample?.captured_at || aircraft.updated_at)}`,
        aircraftFeedTone(aircraft)
      ),
      cockpitBusCell("Safety", safetyPanel.safe_stop_state || "UNKNOWN", safetyPanel.panel_tone || "neutral"),
    ].join("");
  }

  document.getElementById("missionStatStrip").innerHTML = [
    statCard("Board", live.board_online ? "ONLINE" : "EVIDENCE", `fault=${live.last_fault_code || "UNKNOWN"}`),
    statCard("Current", currentProgress.count_label || latestLive.current?.completed || "等待", currentProgress.current_stage || latestLive.current?.note || "Current run"),
    statCard(
      "Weak-Net",
      selectedScenario ? `${formatNumber(selectedScenario.comparison?.throughput_uplift_pct || 0)}% uplift` : "等待场景",
      selectedScenario ? `${formatNumber(selectedScenario.channel?.snr_db || 0, 1)} dB / ${formatNumber(selectedScenario.comparison?.pipeline_images_per_sec || 0)} img/s` : "repo compare"
    ),
    statCard("SAFE_STOP", safetyPanel.safe_stop_state || "UNKNOWN", `fault=${safetyPanel.last_fault_code || live.last_fault_code || "UNKNOWN"}`),
  ].join("");

  const aircraftVector = document.getElementById("aircraftVector");
  aircraftVector.style.left = `${aircraftPosition.left}%`;
  aircraftVector.style.top = `${aircraftPosition.top}%`;
  aircraftVector.style.setProperty("--aircraft-heading", `${formatNumber(aircraft.kinematics?.heading_deg || 0, 1)}deg`);
  document.getElementById("aircraftCallsign").textContent =
    `${aircraft.mission_call_sign || "M9-DEMO"} / ${aircraft.aircraft_id || "FT-AIR-01"}`;
  document.getElementById("aircraftPositionText").textContent =
    `${formatCoordinate(aircraft.position?.latitude, "N", "S")} ｜ ${formatCoordinate(aircraft.position?.longitude, "E", "W")}`;
  document.getElementById("aircraftRoute").innerHTML = aircraftRouteMarkup(aircraft.track || [], aircraft);
  document.getElementById("aircraftTrail").innerHTML = aircraftTrailMarkup(aircraft.track || []);
  document.getElementById("aircraftStageSource").textContent =
    `${linkDirector.selected_profile_label || "Nominal Link"} · ${aircraft.source_api_path || aircraft.feed_contract?.api_path || "/api/aircraft-position"}`;
  document.getElementById("aircraftReadoutGrid").innerHTML = [
    aircraftReadoutCard(
      "Feed State",
      aircraftFeedStateLabel(aircraft),
      aircraftContractValue(aircraft),
      aircraftFeedTone(aircraft)
    ),
    aircraftReadoutCard(
      "Altitude",
      `${formatNumber(aircraft.kinematics?.altitude_m || 0, 0)} m`,
      `v/s ${formatNumber(aircraft.kinematics?.vertical_speed_mps || 0, 1)} m/s`,
      "neutral"
    ),
    aircraftReadoutCard(
      "Ground Speed",
      `${formatNumber(aircraft.kinematics?.ground_speed_kph || 0, 0)} km/h`,
      `heading ${formatNumber(aircraft.kinematics?.heading_deg || 0, 1)}°`,
      "online"
    ),
    aircraftReadoutCard(
      "GPS Fix",
      aircraft.fix?.type || "UNKNOWN",
      `confidence ${formatNumber(aircraft.fix?.confidence_m || 0, 1)} m / sats ${aircraft.fix?.satellites ?? "NA"}`,
      aircraftFeedTone(aircraft)
    ),
  ].join("");
  document.getElementById("aircraftContractStrip").innerHTML = [
    aircraftContractChip("Feed", aircraftContractValue(aircraft), aircraftFeedTone(aircraft)),
    aircraftContractChip(
      "Sample",
      `#${aircraft.sample?.sequence ?? 0} · ${compactTimestampLabel(aircraft.sample?.captured_at || aircraft.updated_at)}`,
      aircraftFeedTone(aircraft)
    ),
    aircraftContractChip("Transport", aircraft.sample?.transport || "backend_http_post", "neutral"),
    aircraftContractChip("API", aircraft.source_api_path || aircraft.feed_contract?.api_path || "/api/aircraft-position", "neutral"),
  ].join("");
  document.getElementById("aircraftFeedNote").textContent = compactSentence(
    [
      aircraft.feed_contract?.summary || "",
      aircraft.source_note || aircraft.fallback_note || "",
    ].filter(Boolean).join(" "),
    158
  );

  document.getElementById("flightFeedPills").innerHTML = [
    `<div class="status-pill ${toneClass(aircraftFeedTone(aircraft))}">${escapeHtml(aircraftContractValue(aircraft))}</div>`,
    `<div class="status-pill ${toneClass(live.board_online ? "online" : systemStatus.execution_mode.tone || "degraded")}">${escapeHtml(live.board_online ? "Board Online" : "Evidence Mode")}</div>`,
    `<div class="status-pill ${toneClass(linkDirector.tone || "neutral")}">${escapeHtml(linkDirector.selected_profile_label || "正常链路")}</div>`,
    selectedScenario
      ? `<div class="status-pill ${toneClass(selectedScenario.tone || "neutral")}">${escapeHtml(`${formatNumber(selectedScenario.channel?.snr_db || 0, 1)} dB / ${formatNumber(selectedScenario.comparison?.pipeline_images_per_sec || 0)} img/s`)}</div>`
      : "",
  ].join("");

  document.getElementById("missionCoreCard").innerHTML = `
    <div class="mission-core-head">
      <div>
        <div class="label">Primary Story</div>
        <h3>${escapeHtml(model.summaryLabel)}</h3>
      </div>
      <div class="status-pill ${toneClass(model.summaryTone || "neutral")}">${escapeHtml(model.operatorCue.currentSceneId ? `Scene ${model.operatorCue.currentSceneId.replace("scene", "")}` : model.summaryLabel)}</div>
    </div>
    <p class="mission-core-summary">${escapeHtml(compactSentence(model.summaryText, 102))}</p>
    <div class="cockpit-rollup-grid">
      ${model.rollups.map((item) => cockpitMissionRollup(item)).join("")}
    </div>
    <div class="cockpit-scene-track">
      ${model.scenes.map((scene) => cockpitSceneChip(scene)).join("")}
    </div>
    <div class="mission-core-actions">
      ${commandJumpButton(model.primaryJump, true)}
      <div class="inline-actions">
        ${(model.quickJumps || []).slice(0, 3).map((item) => commandJumpButton(item, false)).join("")}
      </div>
    </div>
  `;

  document.getElementById("comparePeekCard").innerHTML = `
    <div class="compare-peek-head">
      <div>
        <div class="label">Compare Peek</div>
        <h3>${escapeHtml(selectedCompareViewerSample(snapshot)?.sample?.label || "等待样例")}</h3>
      </div>
      <div class="status-pill ${toneClass(currentPane?.badgeTone || baselinePane?.badgeTone || "neutral")}">${escapeHtml(`${comparison.end_to_end?.speedup_x?.toFixed ? comparison.end_to_end.speedup_x.toFixed(1) : formatNumber(comparison.end_to_end?.speedup_x || 0, 1)}x headline`)}</div>
    </div>
    <div class="status-meta compare-peek-meta">
      <span>${escapeHtml(currentPane?.badgeLabel || "current pending")}</span>
      <span>${escapeHtml(baselinePane?.badgeLabel || "baseline pending")}</span>
      <span>${escapeHtml(selectedScenario ? `weak +${formatNumber(selectedScenario.comparison?.throughput_uplift_pct || 0)}%` : "repo compare")}</span>
    </div>
    <div class="compare-peek-grid">
      ${currentPane ? `
        <figure class="compare-peek-pane">
          <img src="${currentPane.imageSrc}" alt="${escapeHtml(currentPane.title)}">
          <figcaption>
            <strong>${escapeHtml(currentPane.title)}</strong>
            <small>${escapeHtml(currentPane.badgeLabel)}</small>
          </figcaption>
        </figure>
      ` : ""}
      ${baselinePane ? `
        <figure class="compare-peek-pane">
          <img src="${baselinePane.imageSrc}" alt="${escapeHtml(baselinePane.title)}">
          <figcaption>
            <strong>${escapeHtml(baselinePane.title)}</strong>
            <small>${escapeHtml(baselinePane.badgeLabel)}</small>
          </figcaption>
        </figure>
      ` : ""}
    </div>
    <div class="metric-inline compare-peek-metrics">
      <div class="metric-chip">payload ${formatMaybeMs(comparison.payload?.current_ms)}</div>
      <div class="metric-chip">end-to-end ${formatMaybeMs(comparison.end_to_end?.current_ms)}</div>
      <div class="metric-chip">${selectedScenario ? `weak-net +${formatNumber(selectedScenario.comparison?.throughput_uplift_pct || 0)}%` : "repo compare"}</div>
    </div>
    <div class="inline-actions">
      <button class="button button-secondary" type="button" data-open-drawer="compareDrawer">展开 Compare Drawer</button>
    </div>
  `;

  document.getElementById("mainSafetyMirror").innerHTML = `
    <div class="cockpit-card-head">
      <div>
        <div class="label">Safety Mirror</div>
        <h2>SAFE_STOP / Alarm</h2>
      </div>
      <div class="status-pill ${toneClass(safetyPanel.panel_tone || "neutral")}">${escapeHtml(safetyPanel.panel_label || "安全面板")}</div>
    </div>
    ${renderSafetyFrontPanel(safetyPanel)}
  `;
}

function renderLatestLiveStatus(snapshot) {
  const latest = snapshot.latest_live_status;
  if (!latest) return;
  const links = latest.links || [latest.report, latest.probe].filter(Boolean);
  const facts = Array.isArray(latest.facts) ? latest.facts.slice(0, 3) : [];
  document.getElementById("latestLiveStatusCard").innerHTML = `
    <div class="label">Live Verdict</div>
    <div class="inline-actions latest-live-top">
      <div class="mini-title">${escapeHtml(latest.headline)}</div>
      <div class="status-pill tone-online">${escapeHtml(latest.status_label)}</div>
    </div>
    <div class="status-meta latest-live-meta">
      <span>${escapeHtml(`report=${latest.report_date}`)}</span>
      <span>${escapeHtml(`instance=${latest.valid_instance}`)}</span>
      <span>${escapeHtml(`as_of=${latest.as_of}`)}</span>
    </div>
    <div class="metric-strip metric-strip-rail">
      ${statCard(latest.current.label, latest.current.completed, latest.current.note)}
      ${statCard(latest.baseline.label, latest.baseline.completed, latest.baseline.note)}
      ${statCard(latest.board.label, latest.board.value, latest.board.note)}
      ${statCard("有效实例", latest.valid_instance, `收口 ${latest.as_of}`)}
    </div>
    ${facts.length ? `<div class="metric-inline latest-live-facts">${facts.map((item) => `<div class="metric-chip">${escapeHtml(compactSentence(item, 56))}</div>`).join("")}</div>` : ""}
    ${renderLinks(links)}
  `;
}

function renderWeakNetworkConsole(snapshot, systemStatus) {
  const shell = document.getElementById("weakNetworkConsole");
  const { catalog, linkedScenarioId, selectedScenario } = resolveWeakNetworkSelection(snapshot);
  const linkDirector = effectiveLinkDirectorStatus(snapshot);
  const liveAnchor = catalog.live_anchor || {};
  if (!selectedScenario) {
    shell.innerHTML = `
      <div class="label">Weak-Net Console</div>
      <p class="compact-copy">等待仓库内弱网对照证据。</p>
    `;
    return;
  }

  const scenarioButtons = catalog.scenarios
    .map(
      (scenario) => `
        <button
          class="button ${scenario.scenario_id === selectedScenario.scenario_id ? "button-primary" : "button-secondary"} button-small"
          type="button"
          data-weak-scenario-id="${escapeHtml(scenario.scenario_id)}"
        >${escapeHtml(scenario.label)}</button>
      `
    )
    .join("");
  const directorButtons = (linkDirector.profiles || [])
    .map(
      (profile) => `
        <button
          class="button ${profile.active ? "button-primary" : "button-secondary"} button-small"
          type="button"
          data-link-profile-id="${escapeHtml(profile.profile_id)}"
          ${(state.linkDirectorPending || profile.active) ? "disabled" : ""}
        >${escapeHtml(profile.label)}</button>
      `
    )
    .join("");
  const stageCards = (selectedScenario.stage_timings || [])
    .map((stage) => weakMetricCard(stage.label, `${formatNumber(stage.mean_ms)} ms`, `med ${formatNumber(stage.median_ms)} / max ${formatNumber(stage.max_ms)}`, stage.tone || "neutral"))
    .join("");
  const linkedScenarioNote = linkedScenarioId
    ? `当前导演位默认绑定到 ${linkDirector.selected_profile?.evidence_binding?.label || linkedScenarioId}。`
    : (linkDirector.selected_profile?.evidence_binding?.note || "当前导演位没有一一对应的真机 compare 档位。");
  shell.innerHTML = `
    <div class="weak-console-head">
      <div>
        <div class="label">Weak-Net Console</div>
        <h3>${escapeHtml(selectedScenario.label)}</h3>
      </div>
      <div class="status-pill ${toneClass(selectedScenario.tone || "neutral")}">${escapeHtml(`${formatNumber(selectedScenario.channel?.snr_db || 0, 1)} dB`)}</div>
    </div>
    <div class="status-meta weak-console-meta">
      <span>${escapeHtml(`SNR ${formatNumber(selectedScenario.channel?.snr_db || 0, 1)} dB`)}</span>
      <span>${escapeHtml(`batch ${selectedScenario.channel?.batch_size || "NA"} / max ${selectedScenario.channel?.max_inputs || "NA"}`)}</span>
      <span>${escapeHtml(`anchor ${liveAnchor.valid_instance || "NA"} / ${liveAnchor.current_completed || "pending"}`)}</span>
    </div>
    <div class="weak-console-selector">${scenarioButtons}</div>
    <div class="weak-console-metrics">
      ${weakMetricCard("Pipeline", `${formatNumber(selectedScenario.comparison?.pipeline_images_per_sec || 0)} img/s`, `${formatNumber(selectedScenario.comparison?.pipeline_ms_per_image || 0)} ms/image`, "online")}
      ${weakMetricCard("Serial", `${formatNumber(selectedScenario.comparison?.serial_images_per_sec || 0)} img/s`, `${formatNumber(selectedScenario.comparison?.serial_ms_per_image || 0)} ms/image`, "neutral")}
      ${weakMetricCard("Throughput", `+${formatNumber(selectedScenario.comparison?.throughput_uplift_pct || 0)}%`, `${formatNumber(selectedScenario.comparison?.saved_seconds_per_batch || 0)} s / 300 张`, "degraded")}
      ${weakMetricCard("Topology", `${(selectedScenario.topology?.big_cores || []).join(",") || "NA"} | ${(selectedScenario.topology?.little_cores || []).join(",") || "NA"}`, `Q ${selectedScenario.topology?.input_queue_size || 0}/${selectedScenario.topology?.output_queue_size || 0} ｜ ${shortSha(selectedScenario.channel?.artifact_sha256 || "")}`, "warning")}
    </div>
    <div class="weak-stage-grid">
      ${stageCards}
    </div>
    <div class="weak-console-footer">
      <div class="status-meta">
        <span>${escapeHtml(compactSentence(selectedScenario.operator_note || "", 54))}</span>
        <span>${escapeHtml(compactSentence(linkedScenarioNote, 76))}</span>
      </div>
    </div>
    <div class="weak-console-director">
      <div class="label">Link Director</div>
      <div class="weak-console-selector">${directorButtons}</div>
      <div class="status-meta">
        <span>${escapeHtml(compactSentence(linkDirector.truth_note || catalog.truth_note || "", 84))}</span>
      </div>
    </div>
    ${renderLinks([...(selectedScenario.evidence || []), ...(liveAnchor.links || [])].filter(Boolean))}
  `;
}

function renderBoardAccess(systemStatus) {
  const access = systemStatus.board_access;
  const baselineSupport = systemStatus.live?.variant_support?.baseline || {};
  const defaults = access.preloaded_defaults || {};
  const currentMissing = access.missing_inference_fields_by_variant?.current || access.missing_inference_fields || [];
  const baselineMissing = access.missing_inference_fields_by_variant?.baseline || [];
  const baselineReadiness = access.inference_ready_variants?.baseline ? "已就绪" : `仍缺 ${summarizeMissing(baselineMissing)}`;
  const baselineSummary = baselineSupport.note
    ? `${baselineSupport.label || "PyTorch live"}：${baselineSupport.note}`
    : `PyTorch：${baselineReadiness}。`;
  const onlyPasswordMissing = isPasswordOnlyMissing(access);

  if (access.connection_ready) {
    document.getElementById("boardAccessSummary").textContent =
      `当前会话已可复用：${access.user || "未填用户"}@${access.host || "未填主机"}:${access.port}。`;
  } else if (defaults.active && onlyPasswordMissing) {
    document.getElementById("boardAccessSummary").textContent =
      `已预载 ${access.user || "未填用户"}@${access.host || "未填主机"}:${access.port} 与推理 env；当前只差密码。`;
  } else if (access.configured) {
    document.getElementById("boardAccessSummary").textContent =
      `已记录部分会话信息：${access.user || "未填用户"}@${access.host || "未填主机"}:${access.port}。`;
  } else {
    document.getElementById("boardAccessSummary").textContent = "尚未录入板卡会话。";
  }
  if (access.host) document.getElementById("hostInput").value = access.host;
  if (access.user) document.getElementById("userInput").value = access.user;
  if (access.port) document.getElementById("portInput").value = access.port;
  if (access.env_file) document.getElementById("envFileInput").value = access.env_file;
  document.getElementById("passwordInput").placeholder = access.has_password
    ? "已保存在当前 demo 进程内；留空则继续复用"
    : defaults.active
      ? "当前唯一必填项；输入一次后复用"
      : "仅保存在当前 demo 进程内";

  const sourceNotes = [];
  if (defaults.ssh_env_file) sourceNotes.push(`SSH 默认：${defaults.ssh_env_file}`);
  if (defaults.inference_env_file) sourceNotes.push(`推理默认：${defaults.inference_env_file}`);
  document.getElementById("boardAccessHints").innerHTML = `
    <div class="credential-chip-row">
      ${renderFieldChip(fieldLabel("host"), access.host || "未预载", access.field_sources?.host || "missing")}
      ${renderFieldChip(fieldLabel("user"), access.user || "未预载", access.field_sources?.user || "missing")}
      ${renderFieldChip(fieldLabel("port"), String(access.port || "未预载"), access.field_sources?.port || "missing")}
      ${renderFieldChip(fieldLabel("env_file"), access.env_file || "未预载", access.field_sources?.env_file || "missing")}
      ${renderFieldChip(fieldLabel("password"), access.has_password ? "已录入" : "待填写", access.field_sources?.password || "missing")}
    </div>
    <div class="credential-note">
      SSH 会话：${escapeHtml(access.connection_ready ? "已就绪" : `仍缺 ${summarizeMissing(access.missing_connection_fields)}`)}。
      Current：${escapeHtml(access.inference_ready_variants?.current ? "已就绪" : `仍缺 ${summarizeMissing(currentMissing)}`)}。
      ${escapeHtml(baselineSummary)}
    </div>
    ${sourceNotes.length ? `<div class="credential-note">${escapeHtml(sourceNotes.join(" ｜ "))}</div>` : ""}
  `;
}

function renderMissionPasswordInline(systemStatus) {
  const access = systemStatus.board_access || {};
  const status = document.getElementById("missionPasswordStatus");
  const input = document.getElementById("missionPasswordInput");
  const button = document.getElementById("missionPasswordSaveButton");
  if (!status || !input || !button) return;

  const defaults = access.preloaded_defaults || {};
  const onlyPasswordMissing = Boolean(defaults.active) && isPasswordOnlyMissing(access);
  const currentMissing = access.missing_inference_fields_by_variant?.current || access.missing_inference_fields || [];
  const sessionTarget = access.host
    ? `${access.user || "user"}@${access.host}:${access.port || 22}`
    : "当前板卡会话";

  if (access.connection_ready && !currentMissing.length) {
    status.textContent = `当前会话已复用 ${sessionTarget}；如需更新板卡密码，可在此直接覆盖。`;
  } else if (onlyPasswordMissing) {
    status.textContent = `已预载 ${sessionTarget} 与推理 env；在此补录一次密码后，探板与 live 动作会直接复用。`;
  } else if (access.connection_ready) {
    status.textContent = `SSH 会话已就绪，但推理仍缺 ${summarizeMissing(currentMissing)}；完整参数仍可在 Session / Gate 调整。`;
  } else if (access.configured) {
    status.textContent = `当前会话仍缺 ${summarizeMissing(access.missing_connection_fields)}；首页可先补密码，完整 host / user / port / env 仍可在 Session / Gate 调整。`;
  } else {
    status.textContent = "常见预载场景可在首页直接补录板卡密码；完整 host / user / port / env 仍可在 Session / Gate 调整。";
  }

  input.placeholder = access.has_password
    ? "当前密码已保存；输入新密码可覆盖"
    : defaults.active
      ? "当前唯一必填项；输入一次后复用"
      : "仅保存在当前 demo 进程内";
  button.textContent = access.has_password ? "更新并复用密码" : "保存并复用密码";
}

function currentMissionProgressState(systemStatus) {
  const active = systemStatus.active_inference || {};
  const currentResult = latestResultForVariant("current");
  const progress = active.running && active.variant === "current"
    ? active.progress || null
    : currentResult?.live_progress || null;
  return {
    currentResult,
    progress,
    normalized: normalizeProgress(progress),
  };
}

function buildMissionCurrentProgressMeta(progress, result, systemStatus) {
  const access = systemStatus.board_access || {};
  const defaults = access.preloaded_defaults || {};
  if (progress.state === "idle") {
    if (Boolean(defaults.active) && isPasswordOnlyMissing(access)) {
      return "当前仅差板卡密码；保存后即可从首页直接启动远端 Current 重建。";
    }
    if (!access.connection_ready) {
      return "会话未完全就绪时，仍可在首页先补密码；完整 host / user / port / env 继续在 Session / Gate 调整。";
    }
    return `当前会话已就绪；可直接发起本场 ${progress.expected_count} 张图远端 Current 重建。`;
  }
  return buildCompactProgressMeta(progress, result);
}

function buildMissionCurrentLaunchNote(progress, result, systemStatus) {
  const access = systemStatus.board_access || {};
  const defaults = access.preloaded_defaults || {};
  const sessionTarget = access.host
    ? `${access.user || "user"}@${access.host}:${access.port || 22}`
    : "当前板卡会话";
  if (progress.state === "idle") {
    if (Boolean(defaults.active) && isPasswordOnlyMissing(access)) {
      return `已预载 ${sessionTarget} 与推理 env；先保存密码，再点击“启动远端 Current 重建”。`;
    }
    if (access.connection_ready) {
      return `当前会话已复用 ${sessionTarget}；可直接从首页启动远端 Current 重建。`;
    }
    return "密码就绪后，可直接在首页启动远端 Current 重建，并同步查看 300 张图在线进度。";
  }
  if (progress.state === "running") {
    return `远端 Current 重建正在推进，首页直接显示 ${progress.count_label} 与当前阶段；Drawer 内保留完整阶段和日志。`;
  }
  if (result?.execution_mode === "live") {
    return "上一次远端 Current 重建已完成；首页保留计数与阶段摘要，可继续再次发起。";
  }
  if (result?.status === "fallback" || result?.execution_mode === "prerecorded") {
    return "最近一次 live 已回退到归档展示；首页仍保留同一入口与最近进度摘要，便于重新发起。";
  }
  return "首页保留远端 Current 重建入口与最近进度摘要，Current Drawer 展示完整证据细节。";
}

function renderMissionCurrentLaunch(systemStatus) {
  const note = document.getElementById("missionCurrentLaunchNote");
  if (!note) return;
  const { currentResult, progress, normalized } = currentMissionProgressState(systemStatus);
  renderProgressFrame(
    progress,
    {
      badgeId: "missionCurrentProgressBadge",
      countId: "missionCurrentProgressCount",
      barId: "missionCurrentProgressBar",
      markerId: "missionCurrentProgressMarker",
      axisId: "missionCurrentProgressAxis",
      stageId: "missionCurrentProgressStage",
      metaId: "missionCurrentProgressMeta",
    },
    buildMissionCurrentProgressMeta(normalized, currentResult, systemStatus)
  );
  note.textContent = buildMissionCurrentLaunchNote(normalized, currentResult, systemStatus);
}

function renderMissionDashboard(snapshot, systemStatus) {
  const mission = snapshot.mission || {};
  const live = systemStatus.live || {};
  const linkDirector = effectiveLinkDirectorStatus(snapshot);
  const selectedLinkProfile = linkDirector.selected_profile || {};
  const simulatedMetrics = selectedLinkProfile.simulated_metrics || {};
  const futureBinding = selectedLinkProfile.future_binding || {};
  const active = systemStatus.active_inference || {};
  const activeProgress = normalizeProgress(active.progress || null);
  const currentLiveState = currentMissionProgressState(systemStatus);
  const currentResult = currentLiveState.currentResult;
  const baselineResult = latestResultForVariant("baseline");
  const currentLiveProgress = currentLiveState.normalized;
  const safetyPanel = effectiveSafetyPanel(systemStatus);
  const queueStages = active.running ? activeProgress.stages : (currentResult?.live_progress?.stages || []);
  const currentSampleLabel =
    currentResult?.sample?.label ||
    currentResult?.sample_label ||
    snapshot.guided_demo?.sample_catalog?.[0]?.label ||
    "样例 208";

  document.getElementById("missionSummary").textContent =
    compactSentence(
      mission.summary || "下方保留 blackbox timeline、device、queue 与 return evidence；gate、link 与 SAFE_STOP 收进主控制台侧栏。",
      140
    );

  setStatusBadge(
    "taskQueueBadge",
    active.running ? activeProgress.label || "队列占用" : "Idle",
    active.running ? activeProgress.tone || "degraded" : "neutral"
  );
  document.getElementById("taskQueueModule").innerHTML = `
    <div class="mission-big">${escapeHtml(active.running ? activeProgress.count_label : "0 active / 0 queued")}</div>
    <div class="mission-metrics">
      ${missionMetric("当前阶段", active.running ? activeProgress.current_stage : "等待操作员发起任务", active.running ? progressSourceLabel(activeProgress.count_source) : "control plane queue")}
      ${missionMetric("Current 批次", `${mission.batch_target || 300} 张 / 轮`, "数据面 batch target")}
      ${missionMetric("最近结果", systemStatus.last_inference?.variant ? `${systemStatus.last_inference.variant} / ${systemStatus.last_inference.execution_mode}` : "尚无记录", systemStatus.last_inference?.source_label || "等待第一轮动作")}
    </div>
    ${renderFlowStrip(queueStages)}
    ${missionNote(compactSentence(active.running ? active.message : (mission.control_plane_note || "OpenAMP 当前只负责 control plane queue / safety gate。"), 140))}
  `;

  setStatusBadge(
    "deviceStatusBadge",
    live.board_online ? "Board Online" : systemStatus.execution_mode?.label || "Evidence",
    live.board_online ? "online" : systemStatus.execution_mode?.tone || "degraded"
  );
  document.getElementById("deviceStatusModule").innerHTML = `
    <div class="mission-metrics">
      ${missionMetric("会话模式", systemStatus.execution_mode?.label || "未知", "3-core Linux + RTOS demo mode")}
      ${missionMetric("remoteproc", live.remoteproc_state || "unknown", `RPMsg ${live.rpmsg_device || "unknown"}`)}
      ${missionMetric("guard_state", live.guard_state || "UNKNOWN", `fault=${live.last_fault_code || "UNKNOWN"}`)}
      ${missionMetric("runtime / target", `${live.runtime || "unknown"} / ${live.target || "unknown"}`, `trusted SHA ${shortSha(live.trusted_sha)}`)}
    </div>
    ${missionNote(compactSentence(live.last_probe_at ? `最近只读探板 ${live.last_probe_at}` : snapshot.board?.evidence_status?.summary || "当前设备状态以正式证据包为准。", 140))}
    ${renderLinks([...(snapshot.board?.current_status?.evidence || []), ...(snapshot.board?.evidence_status?.evidence || [])].slice(0, 2))}
  `;

  let currentPathLabel = "等待 Current live";
  let currentPathTone = "neutral";
  if (active.running && active.variant === "current") {
    currentPathLabel = "Current live 正在推进";
    currentPathTone = activeProgress.tone || "online";
  } else if (currentResult?.execution_mode === "live") {
    currentPathLabel = "Current live 已完成";
    currentPathTone = "online";
  } else if (currentResult?.status === "fallback" || currentResult?.execution_mode === "prerecorded") {
    currentPathLabel = "Current 归档展示";
    currentPathTone = "degraded";
  }

  setStatusBadge(
    "linkStatusBadge",
    `导演台 ${linkDirector.selected_profile_label || "正常链路"}`,
    linkDirector.tone || currentPathTone
  );
  document.getElementById("linkStatusModule").innerHTML = `
    <div class="inline-actions">
      <div class="status-pill ${toneClass(linkDirector.tone || currentPathTone)}">${escapeHtml(linkDirector.selected_profile_label || "正常链路")}</div>
      <span class="status-inline">${escapeHtml(linkDirector.label || "导演台待命")}</span>
    </div>
    <div class="mission-metrics">
      ${missionMetric("控制面", live.board_online ? "OpenAMP / RPMsg 在线" : "证据 / 降级态", live.status_note || "当前不会改写 lower layer 协议")}
      ${missionMetric("Current 数据面", currentPathLabel, currentResult?.source_label || "等待本轮 live 或归档展示")}
      ${missionMetric("导演台预案", linkDirector.selected_profile_label || "正常链路", selectedLinkProfile.summary || linkDirector.summary || "当前仅更新导演台态势")}
      ${missionMetric("预留绑定", futureBinding.netem || "未绑定 tc/netem", `RTT ${simulatedMetrics.rtt_ms ?? "NA"} ms / jitter ${simulatedMetrics.jitter_ms ?? "NA"} ms / loss ${simulatedMetrics.loss_pct ?? "NA"}%`)}
    </div>
    <div class="status-meta">
      <span>绑定状态=${escapeHtml(linkDirector.backend_binding || "ui_scaffold_only")}</span>
      <span>物理预案=${escapeHtml(futureBinding.physical || "未绑定物理弱网设备")}</span>
      <span>模拟断续=${escapeHtml(simulatedMetrics.outage || "无")}</span>
      <span>${escapeHtml(linkDirector.last_applied_at ? `最近切换=${linkDirector.last_applied_at}` : "最近切换=尚未切换")}</span>
    </div>
    <div class="inline-actions">
      ${(linkDirector.profiles || [])
        .map(
          (profile) => `
            <button
              class="button ${profile.active ? "button-primary" : "button-secondary"}"
              type="button"
              data-link-profile-id="${escapeHtml(profile.profile_id)}"
              ${(state.linkDirectorPending || profile.active) ? "disabled" : ""}
            >${escapeHtml(profile.label)}</button>
          `
        )
        .join("")}
    </div>
    ${missionNote(compactSentence(linkDirector.status_message || linkDirector.last_operator_action || selectedLinkProfile.summary || linkDirector.summary || "导演台当前只做 operator cue 与预案切换。", 150))}
    ${missionNote(compactSentence(linkDirector.truth_note || "导演台是 operator scaffold；board telemetry 继续保持只读。", 140))}
  `;

  const currentCountLabel =
    (active.running && active.variant === "current")
      ? currentLiveProgress.count_label
      : currentResult?.live_progress?.count_label || snapshot.latest_live_status?.current?.completed || "等待执行";
  const baselineCountLabel =
    baselineResult?.live_progress?.count_label || snapshot.latest_live_status?.baseline?.completed || "archive";
  const qualityNote = currentResult?.quality?.psnr_db !== undefined && currentResult?.quality?.psnr_db !== null
    ? `PSNR ${Number(currentResult.quality.psnr_db || 0).toFixed(2)} dB / SSIM ${Number(currentResult.quality.ssim || 0).toFixed(4)}`
    : "图像与指标默认来自归档样例 / PyTorch reference manifest";
  const returnTone = active.running && active.variant === "current"
    ? activeProgress.tone || "online"
    : currentResult?.execution_mode === "live" || baselineResult?.execution_mode === "reference"
      ? "online"
      : currentResult?.status === "fallback" || currentResult?.execution_mode === "prerecorded"
        ? "degraded"
        : "neutral";
  const returnLabel = active.running && active.variant === "current"
    ? currentLiveProgress.label || "Current live"
    : currentResult?.source_label || snapshot.latest_live_status?.status_label || "等待执行";
  setStatusBadge("returnStatusBadge", returnLabel, returnTone);
  document.getElementById("returnStatusModule").innerHTML = `
    <div class="mission-big">${escapeHtml(currentCountLabel)}</div>
    <div class="mission-metrics">
      ${missionMetric("Current", currentCountLabel, currentResult?.source_label || snapshot.latest_live_status?.current?.note || "数据面 operator run")}
      ${missionMetric("参考基线", baselineCountLabel, baselineResult?.source_label || snapshot.latest_live_status?.baseline?.note || "reference archive")}
      ${missionMetric("当前样例", currentSampleLabel, "归档样例画面用于稳定展示")}
      ${missionMetric("质量", qualityNote, "仅在有可用图像/质量记录时展示")}
    </div>
    ${missionNote(compactSentence(currentResult?.message || baselineResult?.message || snapshot.latest_live_status?.summary || "等待 operator 触发回传 / 重建任务。", 150))}
  `;

  setStatusBadge("safetyStatusBadge", safetyPanel.panel_label || "安全面板", safetyPanel.panel_tone || "neutral");
  document.getElementById("safetyStatusModule").innerHTML = renderSafetyFrontPanel(safetyPanel);

  const archiveHasTimeline = Boolean(state.archiveSession?.timeline?.length);
  setStatusBadge(
    "timelineStatusBadge",
    archiveHasTimeline ? "Blackbox Timeline" : (active.running ? "Live + Archive" : "Archive Pending"),
    archiveHasTimeline ? (state.archiveSession?.read_errors?.length ? "degraded" : "online") : (active.running ? activeProgress.tone || "degraded" : "neutral")
  );
  document.getElementById("eventTimelineModule").innerHTML = renderArchiveTimelineModule(snapshot, systemStatus);
  renderMissionCurrentLaunch(systemStatus);
  renderMissionPasswordInline(systemStatus);
}

function renderAct1(snapshot, systemStatus) {
  const live = systemStatus.live;
  const admission = live.admission || {};
  const currentSupport = live.variant_support?.current || {};
  const baselineSupport = live.variant_support?.baseline || {};
  document.getElementById("act1StatusNote").textContent = live.status_note;
  document.getElementById("act1StatusGrid").innerHTML = [
    kpiCard("飞腾派 / SSH", live.board_online ? "在线" : "未在线", live.board_online ? "当前演示进程已拿到最新只读读数。" : "尚无新的在线读数，回退到证据。", live.board_online ? "online" : "offline"),
    kpiCard("OpenAMP / remoteproc", live.remoteproc_state, `RPMsg 设备：${live.rpmsg_device}`, live.remoteproc_state),
    kpiCard("guard_state", live.guard_state, `last_fault_code：${live.last_fault_code}`, live.guard_state),
    kpiCard("数据面运行目标", live.target, `runtime：${live.runtime}`, "online"),
    kpiCard("准入策略", admission.label || "Legacy SHA allowlist", admission.note || "当前 live 准入配置。", admission.tone || "neutral"),
    kpiCard("Current 数据面", currentSupport.label || "Current live", currentSupport.note || "Current 路径状态。", currentSupport.tone || "neutral"),
    kpiCard("PyTorch 参考 / live", baselineSupport.label || "PyTorch live", baselineSupport.note || "PyTorch 路径状态。", baselineSupport.tone || "neutral"),
  ].join("");

  const evidence = snapshot.board.evidence_status;
  document.getElementById("boardEvidenceCard").innerHTML = `
    <div class="status-pill tone-online">${escapeHtml(evidence.label)}</div>
    <div class="compact-copy">${escapeHtml(evidence.summary)}</div>
    <div class="status-meta">
      <span>remoteproc=${escapeHtml(evidence.transport.remoteproc_state)}</span>
      <span>RPMsg=${escapeHtml(evidence.transport.rpmsg_dev)}</span>
      <span>trusted SHA=${escapeHtml(evidence.trusted_current_sha.slice(0, 12))}</span>
    </div>
    ${renderLinks(evidence.evidence)}
  `;

  const current = snapshot.board.current_status;
  document.getElementById("boardLiveCard").innerHTML = `
    <div class="status-pill ${current.reachable ? "tone-online" : "tone-degraded"}">${escapeHtml(current.label)}</div>
    <div class="compact-copy">${escapeHtml(current.summary)}</div>
    <div class="status-meta">
      <span>读取时间=${escapeHtml(current.requested_at || "尚未执行")}</span>
      <span>guard=${escapeHtml(live.guard_state)}</span>
      <span>fault=${escapeHtml(live.last_fault_code)}</span>
    </div>
    ${renderLinks(current.evidence)}
  `;

  document.getElementById("milestonesGrid").innerHTML = snapshot.milestones
    .map(
      (item) => `
        <article class="milestone-card">
          <div class="milestone-meta">
            <span>${escapeHtml(item.stage)}</span>
            <span>${escapeHtml(item.mapped_id)}</span>
          </div>
          <h3>${escapeHtml(item.coverage_item)}</h3>
          <div class="status-pill ${toneClass(item.status)}">${escapeHtml(item.status)}</div>
          <div class="compact-copy">${escapeHtml(item.key_proof_point)}</div>
          ${renderLinks(item.evidence)}
        </article>
      `
    )
    .join("");
}

function renderJobManifestGate(snapshot, systemStatus) {
  const gate = systemStatus.job_manifest_gate || {};
  const contract = snapshot.mission?.job_manifest_gate || {};
  const button = document.getElementById("previewManifestGateButton");
  button.disabled = state.jobManifestGatePending;
  button.textContent = state.jobManifestGatePending ? "正在执行 demo-only 票据预检..." : "demo-only 票据预检";

  const reasons = gate.reasons || [];
  const wireFields = gate.wire_fields || [];
  const contextFields = gate.context_fields || [];
  const evidence = gate.evidence || contract.evidence || [];
  const gateFootnote = [
    gate.protocol_boundary_note || contract.protocol_boundary_note || "",
    gate.demo_only_note || "当前页面仅做 operator-side 闸机可视化，不宣称协议或板端执行已变更。",
  ].filter(Boolean).join(" ");
  const reasonItems = reasons.length
    ? reasons.map((item) => `<li>${escapeHtml(item)}</li>`).join("")
    : `<li>${escapeHtml(gate.message || contract.summary || "当前暂无额外 gate 原因说明。")}</li>`;

  document.getElementById("jobManifestGateCard").innerHTML = `
    <div class="inline-actions">
      <div class="status-pill ${toneClass(gate.verdict || gate.tone || "neutral")}">${escapeHtml(gate.verdict_label || "等待状态")}</div>
      <span class="status-inline">${escapeHtml(gate.label || contract.title || "Job Manifest Gate")}</span>
    </div>
    <p class="compact-copy">${escapeHtml(gate.message || contract.summary || "")}</p>
    <div class="status-meta">
      <span>variant=${escapeHtml(gate.variant_label || "Current")}</span>
      <span>admission=${escapeHtml(gate.admission_label || "未设置")}</span>
      <span>status_source=${escapeHtml(gate.status_source || "demo_snapshot")}</span>
      <span>wire verdict=${escapeHtml(gate.status || "draft")}</span>
    </div>
    <ul class="list-plain">${reasonItems}</ul>
    <div class="credential-chip-row">
      ${wireFields
        .slice(0, 5)
        .map((field) => renderFieldChip(field.label, field.value, field.source))
        .join("")}
    </div>
    <div class="credential-chip-row">
      ${contextFields
        .slice(0, 3)
        .map((field) => renderFieldChip(field.label, field.value, field.source))
        .join("")}
    </div>
    <p class="compact-copy">${escapeHtml(gateFootnote)}</p>
    ${renderLinks(evidence)}
  `;
}

function renderSampleOptions(snapshot) {
  const select = document.getElementById("imageSelect");
  if (select.options.length) return;
  select.innerHTML = snapshot.guided_demo.sample_catalog
    .map(
      (item) =>
        `<option value="${item.index}">${escapeHtml(item.label)} | current PSNR ${Number(item.quality_preview.current_psnr_db || 0).toFixed(2)} dB</option>`
    )
    .join("");
  select.value = String(state.selectedImageIndex);
}

function barWidth(value, max) {
  if (!max || max <= 0) return 0;
  return Math.max(6, Math.round((value / max) * 100));
}

function clampPercent(value) {
  const percent = Number(value || 0);
  if (Number.isNaN(percent)) return 0;
  return Math.max(0, Math.min(100, percent));
}

function progressSourceLabel(source) {
  const labels = {
    "runner_log.missing": "未生成 runner 日志",
    "runner_log.sample_latency_lines": "实时 runner 日志",
    "runner_summary.processed_count": "最终 runner 汇总",
    pytorch_reference_manifest: "PyTorch 参考 manifest",
    board_status: "板端状态缓存",
    demo_default: "演示默认值",
  };
  return labels[source] || "实时状态";
}

function progressAxisLabels(expectedCount) {
  const total = Math.max(Number(expectedCount || 0), 0);
  const ticks = total > 0 ? [0, 0.25, 0.5, 0.75, 1].map((ratio) => Math.round(total * ratio)) : [0, 25, 50, 75, 100];
  if (ticks.length === 5) ticks[4] = total > 0 ? total : 100;
  return ticks
    .map((tick) => `<span>${escapeHtml(String(tick))}</span>`)
    .join("");
}

function normalizeProgress(progress) {
  const expectedCount = Math.max(Number(progress?.expected_count || 300), 0) || 300;
  const completedCount = Math.max(Number(progress?.completed_count || 0), 0);
  const remainingCount = progress?.remaining_count !== undefined
    ? Math.max(Number(progress.remaining_count || 0), 0)
    : Math.max(expectedCount - completedCount, 0);
  const percent = progress?.percent !== undefined
    ? clampPercent(progress.percent)
    : clampPercent(expectedCount > 0 ? (completedCount / expectedCount) * 100 : 0);
  return {
    state: progress?.state || "idle",
    label: progress?.label || "等待触发",
    tone: progress?.tone || "neutral",
    percent,
    phase_percent: clampPercent(progress?.phase_percent || 0),
    completed_count: completedCount,
    expected_count: expectedCount,
    remaining_count: remainingCount,
    completion_ratio: Number(progress?.completion_ratio || 0),
    count_source: progress?.count_source || "",
    count_label: progress?.count_label || `${completedCount} / ${expectedCount}`,
    current_stage: progress?.current_stage || "等待触发",
    stages: progress?.stages || [],
    event_log: progress?.event_log || [],
  };
}

function renderProgressFrame(progress, ids, metaText) {
  const normalized = normalizeProgress(progress);
  const badge = document.getElementById(ids.badgeId);
  const count = document.getElementById(ids.countId);
  const bar = document.getElementById(ids.barId);
  const marker = document.getElementById(ids.markerId);
  const axis = document.getElementById(ids.axisId);
  const stage = ids.stageId ? document.getElementById(ids.stageId) : null;
  const meta = ids.metaId ? document.getElementById(ids.metaId) : null;

  badge.className = `status-pill ${toneClass(normalized.tone || normalized.label)}`;
  badge.textContent = normalized.label;
  count.textContent = normalized.count_label;
  bar.style.width = `${normalized.percent}%`;
  marker.style.left = `${normalized.percent}%`;
  marker.style.opacity = normalized.percent > 0 || normalized.completed_count > 0 ? "1" : "0";
  axis.innerHTML = progressAxisLabels(normalized.expected_count);
  if (stage) stage.textContent = `当前阶段：${normalized.current_stage}`;
  if (meta) meta.textContent = metaText;
  return normalized;
}

function buildProgressMeta(progress) {
  if (progress.state === "idle") {
    return `等待本场 ${progress.expected_count} 张图 live run。`;
  }
  return `计数来源：${progressSourceLabel(progress.count_source)} ｜ 当前阶段：${progress.current_stage} ｜ 剩余 ${progress.remaining_count} 张`;
}

function buildCompactProgressMeta(progress, result) {
  if (!result) {
    return "尚未开始 live run。";
  }
  const modeLabel = result.execution_mode === "live"
    ? "真实在线"
    : result.execution_mode === "reference"
      ? "PyTorch 参考基线"
      : "已回退归档样例";
  return `${modeLabel} ｜ 计数来源：${progressSourceLabel(progress.count_source)} ｜ 剩余 ${progress.remaining_count} 张`;
}

function baselineLiveDisplayLabel(support) {
  return support?.mode === "signed_manifest_v1" ? "PyTorch signed live" : "PyTorch live";
}

function baselineProgressHeading(result, support) {
  const liveLabel = baselineLiveDisplayLabel(support);
  const liveActive = Boolean(result) && (result.request_state === "running" || result.execution_mode === "live");
  return liveActive
    ? { label: liveLabel, title: `${liveLabel} 300 张图` }
    : { label: "PyTorch reference", title: "PyTorch reference 300 张图" };
}

function defaultBaselineProgress(snapshot) {
  const expectedCount = Math.max(Number(snapshot?.guided_demo?.comparison?.baseline_source?.output_count || 300), 0) || 300;
  return {
    expected_count: expectedCount,
    completed_count: expectedCount,
    remaining_count: 0,
    percent: 100,
    label: "Archive Ready",
    tone: "neutral",
    count_label: `${expectedCount} / ${expectedCount} (archive)`,
    current_stage: "默认展示 archived PyTorch reference",
    count_source: "pytorch_reference_manifest",
  };
}

function baselineProgressMetaText(support) {
  return `第三幕默认显示 archived PyTorch reference；${baselineLiveDisplayLabel(support)} 只在操作员显式触发时进入 live flow，2026-03-17 dual-path 继续只作历史 evidence。`;
}

function renderLiveProgress(progress) {
  const normalized = renderProgressFrame(
    progress,
    {
      badgeId: "liveProgressBadge",
      countId: "liveProgressCount",
      barId: "liveProgressBar",
      markerId: "liveProgressMarker",
      axisId: "liveProgressAxis",
      metaId: "liveProgressMeta",
    },
    buildProgressMeta(normalizeProgress(progress))
  );
  const badge = document.getElementById("liveProgressBadge");
  const chips = document.getElementById("liveStageChips");
  const trace = document.getElementById("liveTracePanel");

  if (!progress) {
    badge.className = "status-pill tone-neutral";
    chips.innerHTML = "";
    trace.textContent = "等待板端推进。";
    return;
  }
  chips.innerHTML = normalized.stages
    .map(
      (stage) => `
        <article class="stage-chip" data-status="${escapeHtml(stage.status)}">
          <span class="label">${escapeHtml(stage.label)}</span>
          <strong>${escapeHtml(stage.status === "done" ? "已完成" : stage.status === "current" ? "推进中" : stage.status === "error" ? "停在此处" : "待推进")}</strong>
          <small>${escapeHtml(stage.detail || "")}</small>
        </article>
      `
    )
    .join("");
  trace.textContent = normalized.event_log.join("\n") || "等待板端推进。";
}

function renderComparisonProgressCards() {
  const baselineSupport = state.systemStatus?.live?.variant_support?.baseline || {};
  const baselineHeading = baselineProgressHeading(state.baselineResult, baselineSupport);
  const baselineLabel = document.getElementById("baselineProgressLabel");
  const baselineTitle = document.getElementById("baselineProgressTitle");
  if (baselineLabel) baselineLabel.textContent = baselineHeading.label;
  if (baselineTitle) baselineTitle.textContent = baselineHeading.title;

  const baselineDefaultProgress = state.baselineResult?.live_progress || defaultBaselineProgress(state.snapshot);
  const baselineProgress = renderProgressFrame(
    baselineDefaultProgress,
    {
      badgeId: "baselineProgressBadge",
      countId: "baselineProgressCount",
      barId: "baselineProgressBar",
      markerId: "baselineProgressMarker",
      axisId: "baselineProgressAxis",
      stageId: "baselineProgressStage",
      metaId: "baselineProgressMeta",
    },
    state.baselineResult
      ? buildCompactProgressMeta(normalizeProgress(state.baselineResult?.live_progress || null), state.baselineResult)
      : baselineProgressMetaText(baselineSupport)
  );
  const currentProgress = renderProgressFrame(
    state.currentResult?.live_progress || null,
    {
      badgeId: "comparisonCurrentProgressBadge",
      countId: "comparisonCurrentProgressCount",
      barId: "comparisonCurrentProgressBar",
      markerId: "comparisonCurrentProgressMarker",
      axisId: "comparisonCurrentProgressAxis",
      stageId: "comparisonCurrentProgressStage",
      metaId: "comparisonCurrentProgressMeta",
    },
    buildCompactProgressMeta(normalizeProgress(state.currentResult?.live_progress || null), state.currentResult)
  );
  return { baselineProgress, currentProgress };
}

function renderTimingRows(stageValues, labelFormatter = (label) => label) {
  const maxValue = Math.max(...stageValues.map((item) => Number(item.value_ms || 0)), 1);
  return stageValues
    .map((item) => {
      const emphasisClass = item.emphasis === "board" ? "bar-board" : item.emphasis === "total" ? "bar-total" : "bar-host";
      return `
        <div class="timing-row">
          <div class="timing-label">
            <span>${escapeHtml(labelFormatter(item.label))}</span>
            <span>${formatMaybeMs(item.value_ms)}</span>
          </div>
          <div class="timing-bar"><span class="${emphasisClass}" style="width:${barWidth(Number(item.value_ms || 0), maxValue)}%"></span></div>
        </div>
      `;
    })
    .join("");
}

function renderInference(result) {
  if (!result) {
    document.getElementById("act2SourceLabel").textContent = "等待执行。";
    document.getElementById("timingBoard").innerHTML = "";
    document.getElementById("qualityMetrics").innerHTML = "";
    document.getElementById("inferenceMessage").textContent = "等待触发重建。";
    renderLiveProgress(null);
    if (state.systemStatus) {
      renderMissionCurrentLaunch(state.systemStatus);
    }
    return;
  }
  renderLiveProgress(result.live_progress || null);
  if (state.systemStatus) {
    renderMissionCurrentLaunch(state.systemStatus);
  }
  document.getElementById("act2SourceLabel").textContent = `${result.source_label} | ${result.sample.label}`;
  document.getElementById("originalImage").src = result.original_image_b64;
  document.getElementById("reconstructedImage").src = result.reconstructed_image_b64;
  document.getElementById("inferenceMessage").textContent = result.message;

  if (result.request_state === "running") {
    document.getElementById("timingBoard").innerHTML = `
      <div class="timing-row">
        <div class="timing-label">
          <span>当前阶段</span>
          <span>${escapeHtml(result.live_progress?.current_stage || "等待板端响应")}</span>
        </div>
        <div class="timing-bar"><span class="bar-board" style="width:${Math.max(6, Number(result.live_progress?.percent || 0))}%"></span></div>
      </div>
    `;
    document.getElementById("qualityMetrics").innerHTML = [
      `<div class="metric-chip">状态: ${escapeHtml(result.live_progress?.label || "真实在线推进")}</div>`,
      `<div class="metric-chip">阶段: ${escapeHtml(result.live_progress?.current_stage || "等待板端响应")}</div>`,
      `<div class="metric-chip">进度: ${escapeHtml(result.live_progress?.count_label || "0 / 300")}</div>`,
      `<div class="metric-chip">画面: 归档样例稳定展示</div>`,
    ].join("");
    return;
  }

  if (result.status === "fallback") {
    const stageValues = result.timings?.stages || [];
    const handshakeIncomplete = result.live_attempt?.control_handshake_complete === false;
    const archiveNotice = handshakeIncomplete
      ? "本次 live 未完成 STATUS_RESP/JOB_ACK 握手，以下图像与指标仅来自归档样例和正式报告。"
      : "当前画面与以下图像/指标来自归档样例和正式报告，不代表本次 live 已完成。";
    document.getElementById("timingBoard").innerHTML = `
      <div class="compact-copy">${escapeHtml(archiveNotice)}</div>
      ${renderTimingRows(stageValues, (label) => `归档参考 · ${label}`)}
    `;
    const qualityChips = [
      `<div class="metric-chip">live: ${escapeHtml(result.live_progress?.label || "已回退")}</div>`,
      `<div class="metric-chip">${escapeHtml(handshakeIncomplete ? "握手: 未完成" : "展示: 归档样例")}</div>`,
    ];
    if (result.quality?.psnr_db !== null && result.quality?.psnr_db !== undefined) {
      qualityChips.push(`<div class="metric-chip">归档 PSNR: ${Number(result.quality.psnr_db || 0).toFixed(2)} dB</div>`);
    }
    if (result.quality?.ssim !== null && result.quality?.ssim !== undefined) {
      qualityChips.push(`<div class="metric-chip">归档 SSIM: ${Number(result.quality.ssim || 0).toFixed(4)}</div>`);
    }
    document.getElementById("qualityMetrics").innerHTML = qualityChips.join("");
    return;
  }

  const stageValues = result.timings.stages || [];
  document.getElementById("timingBoard").innerHTML = renderTimingRows(stageValues);

  document.getElementById("qualityMetrics").innerHTML = [
    `<div class="metric-chip">PSNR: ${Number(result.quality.psnr_db || 0).toFixed(2)} dB</div>`,
    `<div class="metric-chip">SSIM: ${Number(result.quality.ssim || 0).toFixed(4)}</div>`,
    `<div class="metric-chip">artifact: ${escapeHtml(String(result.artifact_sha).slice(0, 12))}</div>`,
  ].join("");
}

function selectedCompareViewerSample(snapshot) {
  const samples = snapshot?.guided_demo?.compare_viewer?.samples || [];
  if (!samples.length) return null;
  return samples.find((sample) => Number(sample.index) === Number(state.selectedImageIndex)) || samples[0];
}

function resultMatchesSelectedSample(result, sampleIndex) {
  return Boolean(result) && Number(result.image_index) === Number(sampleIndex);
}

function compareViewerMetrics(pane) {
  const chips = [];
  if (pane.executionMode) {
    chips.push(`<div class="metric-chip">mode: ${escapeHtml(pane.executionMode)}</div>`);
  }
  if (pane.quality?.psnr_db !== null && pane.quality?.psnr_db !== undefined) {
    chips.push(`<div class="metric-chip">PSNR: ${Number(pane.quality.psnr_db || 0).toFixed(2)} dB</div>`);
  }
  if (pane.quality?.ssim !== null && pane.quality?.ssim !== undefined) {
    chips.push(`<div class="metric-chip">SSIM: ${Number(pane.quality.ssim || 0).toFixed(4)}</div>`);
  }
  return chips.length ? `<div class="metric-inline compare-viewer-metrics">${chips.join("")}</div>` : "";
}

function compareViewerPaneState(snapshot, variant) {
  const compareSample = selectedCompareViewerSample(snapshot);
  if (!compareSample) return null;
  const fallback = variant === "baseline" ? compareSample.baseline : compareSample.current;
  const latest = variant === "baseline" ? state.baselineResult : state.currentResult;
  const baselineSupport = state.systemStatus?.live?.variant_support?.baseline || {};
  const useLatest = resultMatchesSelectedSample(latest, compareSample.index);
  const source = useLatest ? latest : fallback;
  const quality = {
    psnr_db: source?.quality?.psnr_db ?? fallback?.quality?.psnr_db,
    ssim: source?.quality?.ssim ?? fallback?.quality?.ssim,
  };

  let badgeLabel = variant === "baseline" ? "PyTorch reference archive" : "current archive";
  let badgeTone = variant === "baseline" ? "neutral" : "degraded";
  if (useLatest && source.execution_mode === "live") {
    badgeLabel = variant === "baseline"
      ? `${baselineLiveDisplayLabel(baselineSupport)} ${source.request_state === "running" ? "status" : "result"}`
      : source.request_state === "running" ? "latest live status" : "latest live result";
    badgeTone = "online";
  } else if (useLatest) {
    badgeLabel = variant === "baseline" && source.execution_mode === "reference"
      ? "PyTorch reference archive"
      : "latest result";
    badgeTone = variant === "baseline" ? "neutral" : "degraded";
  }

  return {
    sideLabel: variant === "baseline" ? "右侧" : "左侧",
    title: fallback.label || (variant === "baseline" ? "PyTorch reference" : "Current reconstruction"),
    badgeLabel,
    badgeTone,
    sourceLabel: source?.source_label || fallback.source_label || "",
    imageSrc: useLatest ? source.reconstructed_image_b64 : fallback.image_b64,
    imagePath: useLatest
      ? source?.image_sources?.reconstructed_path || fallback.image_path || ""
      : fallback.image_path || "",
    note: useLatest
      ? String(source?.message || fallback.fallback_note || "")
      : String(fallback.fallback_note || source?.message || ""),
    executionMode: source?.execution_mode || fallback.execution_mode || "",
    quality,
  };
}

function compareViewerPane(pane) {
  if (!pane) return "";
  return `
    <figure class="compare-viewer-pane">
      <div class="compare-viewer-pane-head">
        <div>
          <div class="label">${escapeHtml(pane.sideLabel)}</div>
          <h4>${escapeHtml(pane.title)}</h4>
        </div>
        <div class="status-pill ${toneClass(pane.badgeTone)}">${escapeHtml(pane.badgeLabel)}</div>
      </div>
      <div class="compare-viewer-source" title="${escapeHtml(pane.sourceLabel || "")}">${escapeHtml(pane.sourceLabel)}</div>
      <img src="${pane.imageSrc}" alt="${escapeHtml(pane.title)}">
      ${compareViewerMetrics(pane)}
      <figcaption class="compact-copy">${escapeHtml(compactSentence(pane.note, 130))}</figcaption>
      ${pane.imagePath ? `<div class="compare-viewer-path" title="${escapeHtml(pane.imagePath)}">${escapeHtml(truncateMiddle(pane.imagePath, 22, 20))}</div>` : ""}
    </figure>
  `;
}

function renderCompareViewer(snapshot) {
  const compareSample = selectedCompareViewerSample(snapshot);
  const currentPane = compareViewerPaneState(snapshot, "current");
  const baselinePane = compareViewerPaneState(snapshot, "baseline");
  const baselineSupport = state.systemStatus?.live?.variant_support?.baseline || {};
  const sampleLabel = compareSample?.sample?.label || "等待样例";
  const sampleTitle = compareSample?.sample?.title || "";
  document.getElementById("compareViewerSampleLabel").textContent = sampleTitle
    ? `${sampleLabel} | ${sampleTitle}`
    : sampleLabel;
  document.getElementById("compareViewerModeNote").textContent =
    `性能卡片沿用 4-core 正式口径；第三幕默认显示 archived PyTorch reference，${baselineLiveDisplayLabel(baselineSupport)} 只在操作员显式触发时出现，2026-03-17 dual-path baseline live 仅保留历史 evidence。`;

  if (!compareSample) {
    document.getElementById("compareViewerContext").innerHTML = "";
    document.getElementById("compareViewerBoard").innerHTML = "";
    return;
  }

  document.getElementById("compareViewerContext").innerHTML = [
    `
      <div class="compare-context-card">
        <span>当前样例</span>
        <strong>${escapeHtml(compareSample.sample?.label || "")}</strong>
        <small>${escapeHtml(compareSample.sample?.note || "")}</small>
      </div>
    `,
    `
      <div class="compare-context-card">
        <span>viewer provenance</span>
        <strong>${escapeHtml(`${currentPane?.badgeLabel || "current pending"} ｜ ${baselinePane?.badgeLabel || "baseline pending"}`)}</strong>
        <small>${escapeHtml(`image_index=${compareSample.index}`)}</small>
      </div>
    `,
  ].join("");

  document.getElementById("compareViewerBoard").innerHTML = [
    compareViewerPane(currentPane),
    compareViewerPane(baselinePane),
  ].join("");
}

function comparisonCard(card) {
  const baselineLabel = card.baseline_label || "baseline";
  const currentLabel = card.current_label || "current";
  const { label, baseline_ms: baselineMs, current_ms: currentMs, improvement_pct: improvementPct, speedup_x: speedupX, callout } = card;
  const maxValue = Math.max(baselineMs, currentMs, 1);
  return `
    <article class="comparison-card">
      <div class="comparison-title">${escapeHtml(label)}<span class="comparison-speedup">${speedupX.toFixed(1)}x / ${improvementPct.toFixed(2)}%</span></div>
      <div class="comparison-row">
        <div class="timing-label"><span>${escapeHtml(baselineLabel)}</span><span>${formatMaybeMs(baselineMs)}</span></div>
        <div class="comparison-bar"><span class="bar-host" style="width:${barWidth(baselineMs, maxValue)}%"></span></div>
      </div>
      <div class="comparison-row">
        <div class="timing-label"><span>${escapeHtml(currentLabel)}</span><span>${formatMaybeMs(currentMs)}</span></div>
        <div class="comparison-bar"><span class="bar-board" style="width:${barWidth(currentMs, maxValue)}%"></span></div>
      </div>
      <div class="comparison-callout">${escapeHtml(callout)}</div>
    </article>
  `;
}

function renderComparison(snapshot) {
  const comparison = snapshot.guided_demo.comparison;
  const currentSupport = state.systemStatus?.live?.variant_support?.current || {};
  const baselineSupport = state.systemStatus?.live?.variant_support?.baseline || {};
  const boardBusy = String(state.systemStatus?.live?.guard_state || "").toUpperCase() === "JOB_ACTIVE";
  const compareSample = selectedCompareViewerSample(snapshot);
  renderComparisonProgressCards();
  document.getElementById("comparisonBoard").innerHTML = [
    comparisonCard(comparison.payload),
    comparisonCard(comparison.end_to_end),
  ].join("");
  renderCompareViewer(snapshot);

  const notes = [];
  if (compareSample?.sample?.label) {
    notes.push(`当前样例=${compareSample.sample.label}`);
  }
  if (state.baselineResult) {
    notes.push(`PyTorch=${state.baselineResult.source_label}`);
  }
  if (state.currentResult) {
    notes.push(`Current=${state.currentResult.source_label}`);
  }
  if (!state.baselineResult && baselineSupport.note) {
    notes.push(`PyTorch=${baselineSupport.note}`);
  }
  if (!state.currentResult && currentSupport.note) {
    notes.push(`Current=${currentSupport.note}`);
  }
  if (boardBusy) {
    notes.push("guard_state=JOB_ACTIVE；新的 live launch 继续保守阻断，不自动 SAFE_STOP。");
  }
  document.getElementById("comparisonRunNote").textContent =
    notes.join(" ｜ ") || "Current 与 PyTorch 仍由操作员手动触发；若无新结果，则继续显示已标注 provenance 的 archive 画面。";
}

function renderFault(snapshot) {
  const result = state.faultResult;
  const system = state.systemStatus;
  const act4Lamp = document.getElementById("act4Lamp");
  if (act4Lamp) {
    act4Lamp.className = `act-lamp ${lampClass(result ? result.status_lamp : system.live.guard_state)}`;
  }
  if (!result) {
    document.getElementById("faultStatusHeadline").textContent = "等待注入动作。";
    document.getElementById("faultSummary").innerHTML = [
      kpiCard("当前 guard_state", system.live.guard_state, "来自当前缓存状态或正式证据。", system.live.guard_state),
      kpiCard("last_fault_code", system.live.last_fault_code, "注入后会在此处高亮变化。", system.live.last_fault_code),
      kpiCard("FIT 汇总", "FIT-01 / FIT-02 / FIT-03", "保留原始标识，方便评委追问时核对。", "online"),
    ].join("");
    document.getElementById("faultLogPanel").textContent = "等待故障注入动作。";
  } else {
    document.getElementById("faultStatusHeadline").textContent = `${result.source_label} | ${result.message}`;
    document.getElementById("faultSummary").innerHTML = [
      kpiCard("当前动作", result.fault_type || "recover", result.source_label, result.status_lamp),
      kpiCard("guard_state", result.guard_state, "注入或恢复后的最终状态。", result.guard_state),
      kpiCard("last_fault_code", result.last_fault_code, "保留 fault code 原样便于答辩讲解。", result.last_fault_code),
    ].join("");
    document.getElementById("faultLogPanel").textContent = (result.log_entries || []).join("\n");
  }

  document.getElementById("fitGrid").innerHTML = snapshot.fits
    .map(
      (fit) => `
        <article class="fit-card">
          <div class="fit-meta">
            <span>${escapeHtml(fit.fit_id)}</span>
            <span>${escapeHtml(fit.generated_at)}</span>
          </div>
          <h3>${escapeHtml(fit.scenario)}</h3>
          <div class="status-pill ${toneClass(fit.status)}">${escapeHtml(fit.status)}</div>
          <div class="compact-copy">${escapeHtml(fit.readout)}</div>
          ${renderLinks(fit.evidence)}
        </article>
      `
    )
    .join("");
}

function renderPerformance(snapshot) {
  document.getElementById("performanceNote").textContent = snapshot.performance.positioning_note;
  document.getElementById("performanceGrid").innerHTML = snapshot.performance.metrics
    .map(
      (metric) => `
        <article class="performance-card">
          <div class="label">${escapeHtml(metric.label)}</div>
          <h3>${escapeHtml(metric.current)}</h3>
          <div class="compact-copy">baseline ${escapeHtml(metric.baseline)} | 提升 ${escapeHtml(metric.improvement)}</div>
          ${renderLinks(metric.links || (metric.report ? [metric.report] : []))}
        </article>
      `
    )
    .join("");
}

function renderSources(snapshot) {
  document.getElementById("sourcesGrid").innerHTML = snapshot.docs
    .map(
      (item) => `
        <article class="doc-card">
          <div class="label">材料</div>
          <h3>${escapeHtml(item.label)}</h3>
          <div class="compact-copy">${escapeHtml(item.path)}</div>
          <div class="link-list"><a class="doc-link" href="${docHref(item.path)}">打开</a></div>
        </article>
      `
    )
    .join("");
}

function renderActLamps(systemStatus) {
  document.getElementById("act1Lamp").className = `act-lamp ${lampClass(systemStatus.live.board_online ? "online" : systemStatus.execution_mode.tone)}`;
  if (!state.faultResult) {
    document.getElementById("act4Lamp").className = `act-lamp ${lampClass(systemStatus.live.last_fault_code)}`;
  }
}

function applyLaunchPolicy(systemStatus) {
  const currentSupport = systemStatus.live?.variant_support?.current || {};
  const baselineSupport = systemStatus.live?.variant_support?.baseline || {};
  const boardAccess = systemStatus.board_access || {};
  const baselineLiveLabel = baselineLiveDisplayLabel(baselineSupport);
  const boardBusy = String(systemStatus.live?.guard_state || "").toUpperCase() === "JOB_ACTIVE";
  const boardBusyReason = "板端当前 guard_state=JOB_ACTIVE；demo 保守阻断新的 live launch，不自动 SAFE_STOP。";
  const passwordOnlyReason = "已预载主机、用户名、SSH 端口与推理 env；当前只差板卡密码。请先在首页 Mission 区补录，必要时再到 Session / Gate 调整完整参数。";
  const passwordOnlyMissing = Boolean(boardAccess.preloaded_defaults?.active) && isPasswordOnlyMissing(boardAccess);
  const currentBlocked = boardBusy || currentSupport.launch_allowed === false;
  const baselineBlocked = boardBusy || baselineSupport.launch_allowed === false;

  const currentButton = document.getElementById("runCurrentButton");
  const currentAgainButton = document.getElementById("runCurrentAgainButton");
  const baselineButton = document.getElementById("runBaselineButton");
  const runAllButton = document.getElementById("runAllButton");
  const opsCurrentButton = document.getElementById("opsRunCurrentButton");
  const missionCurrentButton = document.getElementById("missionRunCurrentButton");
  const opsBaselineButton = document.getElementById("opsRunBaselineButton");
  const manifestButtons = [
    document.getElementById("previewManifestGateButton"),
    document.getElementById("opsManifestButton"),
  ].filter(Boolean);

  const currentLabel = currentSupport.mode === "signed_manifest_v1"
    ? "启动远端 Current signed 重建（300 张图）"
    : "启动远端 Current 重建（300 张图）";
  const missionCurrentLabel = currentSupport.mode === "signed_manifest_v1"
    ? "启动远端 Current signed 重建"
    : "启动远端 Current 重建";
  currentButton.textContent = currentLabel;
  currentAgainButton.textContent = currentSupport.mode === "signed_manifest_v1"
    ? "再次运行远端 Current signed 重建（300 张图）"
    : "再次运行远端 Current 重建（300 张图）";
  baselineButton.textContent = baselineSupport.launch_allowed === false
    ? "PyTorch reference（归档）"
    : `运行 ${baselineLiveLabel} 数据面 300 张图`;
  runAllButton.textContent = baselineSupport.launch_allowed === false
    ? "PyTorch reference + Current 当前未开放 live"
    : `一键顺序运行 ${baselineLiveLabel} + Current 数据面 300 张图`;
  if (opsCurrentButton) {
    opsCurrentButton.textContent = missionCurrentLabel;
  }
  if (missionCurrentButton) {
    missionCurrentButton.textContent = missionCurrentLabel;
  }
  if (opsBaselineButton) {
    opsBaselineButton.textContent = baselineSupport.launch_allowed === false
      ? "PyTorch Reference"
      : baselineLiveLabel === "PyTorch signed live"
        ? "PyTorch Signed Live"
        : "PyTorch Live";
  }

  currentButton.disabled = currentBlocked;
  currentAgainButton.disabled = currentBlocked;
  baselineButton.disabled = baselineBlocked;
  runAllButton.disabled = currentBlocked || baselineBlocked;
  if (opsCurrentButton) {
    opsCurrentButton.disabled = currentBlocked;
  }
  if (missionCurrentButton) {
    missionCurrentButton.disabled = currentBlocked;
  }
  if (opsBaselineButton) {
    opsBaselineButton.disabled = baselineBlocked;
  }

  currentButton.title = passwordOnlyMissing ? passwordOnlyReason : boardBusy ? boardBusyReason : (currentSupport.note || "");
  currentAgainButton.title = currentButton.title;
  baselineButton.title = passwordOnlyMissing ? passwordOnlyReason : (baselineSupport.note || "");
  runAllButton.title = passwordOnlyMissing
    ? passwordOnlyReason
    : boardBusy ? boardBusyReason : (currentBlocked ? (currentSupport.note || "") : (baselineSupport.note || ""));
  if (opsCurrentButton) {
    opsCurrentButton.title = currentButton.title;
  }
  if (missionCurrentButton) {
    missionCurrentButton.title = currentButton.title;
  }
  if (opsBaselineButton) {
    opsBaselineButton.title = baselineButton.title;
  }
  manifestButtons.forEach((button) => {
    button.title = systemStatus.job_manifest_gate?.message || systemStatus.job_manifest_gate?.admission_note || "demo-only manifest preview";
  });
}

function renderAll() {
  if (!state.snapshot || !state.systemStatus) return;
  renderCockpitShell(state.snapshot, state.systemStatus);
  renderWeakNetworkConsole(state.snapshot, state.systemStatus);
  renderLatestLiveStatus(state.snapshot);
  renderMissionDashboard(state.snapshot, state.systemStatus);
  renderBoardAccess(state.systemStatus);
  renderAct1(state.snapshot, state.systemStatus);
  renderJobManifestGate(state.snapshot, state.systemStatus);
  renderSampleOptions(state.snapshot);
  renderInference(state.currentResult);
  renderComparison(state.snapshot);
  renderFault(state.snapshot);
  renderPerformance(state.snapshot);
  renderSources(state.snapshot);
  applyLaunchPolicy(state.systemStatus);
}

function applyActiveAct() {
  const drawerId = drawerIdForAct(state.activeAct);
  document.querySelectorAll("[data-drawer]").forEach((drawer) => {
    drawer.classList.toggle("is-active-drawer", drawer.id === drawerId);
  });
}

function switchAct(actId, options = {}) {
  if (!actId) return;
  state.activeAct = actId;
  if (options.user !== false) {
    state.userSelectedAct = true;
  }
  applyActiveAct();
  if (options.openDrawer === false) {
    return;
  }
  const drawerId = drawerIdForAct(actId);
  if (drawerId) {
    openDrawer(drawerId);
  }
}

function jumpToTarget(targetId, actId = "") {
  const drawerId = drawerIdForTarget(targetId) || drawerIdForAct(actId);
  if (drawerId) {
    openDrawer(drawerId);
  }
  if (actId) {
    state.activeAct = actId;
    applyActiveAct();
  }
  window.requestAnimationFrame(() => {
    const element = document.getElementById(targetId);
    if (!element) return;
    element.scrollIntoView({ behavior: "smooth", block: "start" });
  });
}

function preferredArchiveSessionId(archiveSessionsPayload) {
  const sessions = archiveSessionsPayload?.sessions || [];
  if (!sessions.length) return "";
  const selected = String(state.selectedArchiveSessionId || "");
  if (selected && sessions.some((session) => session.session_id === selected)) {
    return selected;
  }
  const currentSessionId = String(archiveSessionsPayload?.current_session_id || "");
  if (currentSessionId && sessions.some((session) => session.session_id === currentSessionId)) {
    return currentSessionId;
  }
  return String(sessions[0]?.session_id || "");
}

async function loadArchiveSession(sessionId) {
  const selectedSessionId = String(sessionId || "").trim();
  state.selectedArchiveSessionId = selectedSessionId;
  if (!selectedSessionId) {
    state.archiveSession = null;
    renderAll();
    return null;
  }
  const payload = await fetchJSON(`/api/archive/session?session_id=${encodeURIComponent(selectedSessionId)}&limit=25`);
  state.archiveSession = payload;
  renderAll();
  return payload;
}

async function refreshAll() {
  const [snapshot, systemStatus, linkDirectorStatus, archiveSessionsPayload] = await Promise.all([
    fetchJSON("/api/snapshot"),
    fetchJSON("/api/system-status"),
    fetchJSON("/api/link-director"),
    fetchJSON("/api/archive/sessions?limit=25"),
  ]);
  const nextArchiveSessionId = preferredArchiveSessionId(archiveSessionsPayload);
  let archiveSession = null;
  if (nextArchiveSessionId) {
    archiveSession = await fetchJSON(`/api/archive/session?session_id=${encodeURIComponent(nextArchiveSessionId)}&limit=25`);
  }
  state.snapshot = snapshot;
  state.systemStatus = systemStatus;
  state.linkDirectorStatus = linkDirectorStatus;
  state.archiveSessions = archiveSessionsPayload.sessions || [];
  state.currentArchiveSessionId = archiveSessionsPayload.current_session_id || "";
  state.selectedArchiveSessionId = nextArchiveSessionId;
  state.archiveSession = archiveSession;
  hydrateRecentResultsFromSystemStatus(systemStatus);
  syncWeakNetworkSelection(snapshot);
  syncActiveActFromCue();
  renderAll();
  applyActiveAct();
}

function clearBoardAccessPasswordInputs() {
  [document.getElementById("passwordInput"), document.getElementById("missionPasswordInput")]
    .filter(Boolean)
    .forEach((input) => {
      input.value = "";
    });
}

function boardAccessSaveFeedback(boardAccess, source) {
  const missingConnection = boardAccess.missing_connection_fields || [];
  const currentMissing = boardAccess.missing_inference_fields_by_variant?.current || boardAccess.missing_inference_fields || [];
  if (boardAccess.connection_ready && !currentMissing.length) {
    return {
      message:
        source === "mission"
          ? "首页已保存板卡密码；后续探板、PyTorch Live 与 Current Live 会直接复用当前会话。"
          : "板卡会话已保存到当前 demo 进程内，后续探板/推理/故障动作会直接复用。",
      tone: "success",
    };
  }
  if (boardAccess.connection_ready) {
    return {
      message: `SSH 会话已保存，但推理仍缺 ${summarizeMissing(currentMissing)}；完整参数仍可在 Session / Gate 调整。`,
      tone: "warning",
    };
  }
  if (source === "mission") {
    return {
      message: `密码已保存，但当前会话仍缺 ${summarizeMissing(missingConnection)}；完整 host / user / port / env 请在 Session / Gate 调整。`,
      tone: "warning",
    };
  }
  return {
    message: "板卡会话已更新，但仍有字段待补全。",
    tone: "warning",
  };
}

async function submitBoardAccess(payload, options = {}) {
  try {
    const result = await fetchJSON("/api/session/board-access", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    const boardAccess = result.board_access || {};
    const feedback = boardAccessSaveFeedback(boardAccess, options.source || "drawer");
    setFeedback(feedback.message, feedback.tone);
    clearBoardAccessPasswordInputs();
    state.systemStatus = {
      ...(state.systemStatus || {}),
      board_access: boardAccess,
    };
    await refreshAll();
  } catch (error) {
    setFeedback(error.message, "error");
  }
}

async function saveBoardAccess() {
  await submitBoardAccess(
    {
      host: document.getElementById("hostInput").value.trim(),
      user: document.getElementById("userInput").value.trim(),
      password: document.getElementById("passwordInput").value,
      port: document.getElementById("portInput").value.trim(),
      env_file: document.getElementById("envFileInput").value.trim(),
    },
    { source: "drawer" }
  );
}

async function saveMissionPassword() {
  const missionPasswordInput = document.getElementById("missionPasswordInput");
  const password = missionPasswordInput?.value || "";
  if (!password) {
    setFeedback(
      state.systemStatus?.board_access?.has_password
        ? "当前已复用板卡密码；如需更新请输入新密码。"
        : "请输入板卡密码后再保存。",
      "warning"
    );
    focusMissionPasswordInput();
    return;
  }
  await submitBoardAccess({ password }, { source: "mission" });
}

async function probeBoard() {
  try {
    setFeedback("正在探测板卡与 OpenAMP 状态...", "warning");
    await fetchJSON("/api/probe-board", {
      method: "POST",
      body: JSON.stringify({}),
    });
    await refreshAll();
    setFeedback("板卡探测已完成。", "success");
    switchAct("act1");
  } catch (error) {
    setFeedback(error.message, "error");
  }
}

async function switchLinkDirectorProfile(profileId) {
  if (!profileId || state.linkDirectorPending) return;
  try {
    state.linkDirectorPending = true;
    renderAll();
    setFeedback("正在切换导演台弱网预案...", "warning");
    const payload = await fetchJSON("/api/link-director/profile", {
      method: "POST",
      body: JSON.stringify({ profile_id: profileId }),
    });
    state.linkDirectorStatus = payload;
    const linkedScenarioId = payload.selected_profile?.evidence_binding?.scenario_id || "";
    if (!state.weakScenarioPinnedByUser && linkedScenarioId) {
      state.selectedWeakScenarioId = linkedScenarioId;
    }
    renderAll();
    await refreshAll();
    setFeedback(
      payload.status_message || payload.last_operator_action || "导演台预案已更新。",
      payload.change_applied === false ? "warning" : "success"
    );
  } catch (error) {
    setFeedback(error.message, "error");
  } finally {
    state.linkDirectorPending = false;
    renderAll();
  }
}

async function previewJobManifestGate() {
  if (state.jobManifestGatePending) return;
  try {
    state.jobManifestGatePending = true;
    renderAll();
    setFeedback("正在执行 demo-only 任务票闸机预检...", "warning");
    const result = await fetchJSON("/api/job-manifest-gate/preview", {
      method: "POST",
      body: JSON.stringify({ variant: "current" }),
    });
    await refreshAll();
    setFeedback(result.message, result.gate?.verdict === "allow" ? "success" : "warning");
    switchAct("act1");
  } catch (error) {
    setFeedback(error.message, "error");
  } finally {
    state.jobManifestGatePending = false;
    renderAll();
  }
}

async function pollInferenceJob(jobId, variant) {
  state.activeInferenceJobId = jobId;
  state.activeInferenceVariant = variant;
  while (true) {
    const result = await fetchJSON(`/api/inference-progress?job_id=${encodeURIComponent(jobId)}`);
    if (variant === "baseline") {
      state.baselineResult = result;
    } else {
      state.currentResult = result;
    }
    renderInference(state.currentResult);
    renderComparison(state.snapshot);
    if (result.request_state !== "running") {
      await refreshAll();
      state.activeInferenceJobId = null;
      state.activeInferenceVariant = "";
      return result;
    }
    await new Promise((resolve) => window.setTimeout(resolve, 350));
  }
}

function feedbackToneForResult(result) {
  return result.execution_mode === "live" || result.execution_mode === "reference" ? "success" : "warning";
}

async function runInferenceAction(endpoint, variant, resultKey, actId, feedbackText, switchActOptions = {}) {
  try {
    setFeedback(feedbackText, "warning");
    state.selectedImageIndex = Number(document.getElementById("imageSelect").value || 0);
    const initial = await fetchJSON(endpoint, {
      method: "POST",
      body: JSON.stringify({ image_index: state.selectedImageIndex, mode: variant }),
    });
    state[resultKey] = initial;
    renderInference(state.currentResult);
    renderComparison(state.snapshot);
    switchAct(actId, switchActOptions);
    if (initial.request_state === "running" && initial.job_id) {
      const finalResult = await pollInferenceJob(initial.job_id, variant);
      setFeedback(finalResult.message, feedbackToneForResult(finalResult));
      return finalResult;
    }
    await refreshAll();
    setFeedback(initial.message, feedbackToneForResult(initial));
    return initial;
  } catch (error) {
    setFeedback(error.message, "error");
    throw error;
  }
}

async function runCurrentInference(options = {}) {
  state.currentResult = await runInferenceAction(
    "/api/run-inference",
    "current",
    "currentResult",
    "act2",
    "正在执行 Current 在线推进...",
    options.switchActOptions || {}
  );
}

async function runCurrentInferenceFromHomepage() {
  await runCurrentInference({ switchActOptions: { openDrawer: false, user: false } });
}

async function runBaseline() {
  const baselineSupport = state.systemStatus?.live?.variant_support?.baseline || {};
  state.baselineResult = await runInferenceAction(
    "/api/run-baseline",
    "baseline",
    "baselineResult",
    "act3",
    `正在执行 ${baselineLiveDisplayLabel(baselineSupport)} 在线推进...`
  );
}

async function runAllComparisons() {
  switchAct("act3");
  await runBaseline();
  await runCurrentInference();
  switchAct("act3");
}

async function injectFault(faultType) {
  try {
    setFeedback("正在执行故障注入动作...", "warning");
    state.faultResult = await fetchJSON("/api/inject-fault", {
      method: "POST",
      body: JSON.stringify({ fault_type: faultType }),
    });
    await refreshAll();
    renderFault(state.snapshot);
    setFeedback(state.faultResult.message, state.faultResult.execution_mode === "live" ? "success" : "warning");
    switchAct("act4");
  } catch (error) {
    setFeedback(error.message, "error");
  }
}

async function recoverFault() {
  try {
    setFeedback("正在执行 SAFE_STOP 收口...", "warning");
    state.faultResult = await fetchJSON("/api/recover", {
      method: "POST",
      body: JSON.stringify({}),
    });
    await refreshAll();
    renderFault(state.snapshot);
    setFeedback(state.faultResult.message, state.faultResult.execution_mode === "live" ? "success" : "warning");
    switchAct("act4");
  } catch (error) {
    setFeedback(error.message, "error");
  }
}

function bindEvents() {
  document.querySelectorAll("[data-open-drawer]").forEach((button) => {
    button.addEventListener("click", () => openDrawer(button.dataset.openDrawer || ""));
  });
  document.querySelectorAll("[data-close-drawer]").forEach((button) => {
    button.addEventListener("click", () => closeDrawer(button.dataset.closeDrawer || ""));
  });
  const overlay = document.getElementById("drawerOverlay");
  if (overlay) {
    overlay.addEventListener("click", () => closeDrawer());
  }
  [document.getElementById("opsReloadButton")].filter(Boolean).forEach((button) => {
    button.addEventListener("click", () => {
      refreshAll().catch((error) => setFeedback(error.message, "error"));
    });
  });
  [document.getElementById("opsProbeButton")].filter(Boolean).forEach((button) => {
    button.addEventListener("click", () => {
      probeBoard();
    });
  });
  document.getElementById("saveAccessButton").addEventListener("click", () => {
    saveBoardAccess();
  });
  document.getElementById("missionPasswordSaveButton").addEventListener("click", () => {
    saveMissionPassword();
  });
  document.getElementById("missionPasswordInput").addEventListener("keydown", (event) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    saveMissionPassword();
  });
  [document.getElementById("previewManifestGateButton"), document.getElementById("opsManifestButton")]
    .filter(Boolean)
    .forEach((button) => {
      button.addEventListener("click", () => {
        previewJobManifestGate();
      });
    });
  [document.getElementById("runCurrentButton")]
    .filter(Boolean)
    .forEach((button) => {
      button.addEventListener("click", () => {
        runCurrentInference();
      });
    });
  [document.getElementById("opsRunCurrentButton"), document.getElementById("missionRunCurrentButton")]
    .filter(Boolean)
    .forEach((button) => {
      button.addEventListener("click", () => {
        runCurrentInferenceFromHomepage();
      });
    });
  [document.getElementById("runBaselineButton"), document.getElementById("opsRunBaselineButton")]
    .filter(Boolean)
    .forEach((button) => {
      button.addEventListener("click", () => {
        runBaseline();
      });
    });
  document.getElementById("runCurrentAgainButton").addEventListener("click", () => {
    runCurrentInference();
  });
  document.getElementById("runAllButton").addEventListener("click", () => {
    runAllComparisons();
  });
  [document.getElementById("recoverButton"), document.getElementById("opsRecoverButton")]
    .filter(Boolean)
    .forEach((button) => {
      button.addEventListener("click", () => {
        recoverFault();
      });
    });

  document.querySelectorAll(".act-tab").forEach((tab) => {
    tab.addEventListener("click", () => switchAct(tab.dataset.act));
  });
  document.querySelectorAll("[data-fault]").forEach((button) => {
    button.addEventListener("click", () => injectFault(button.dataset.fault));
  });
  document.getElementById("imageSelect").addEventListener("change", (event) => {
    state.selectedImageIndex = Number(event.target.value || 0);
    if (state.snapshot) {
      renderComparison(state.snapshot);
    }
  });
  document.addEventListener("click", (event) => {
    const jumpButton = event.target.closest("[data-jump-target]");
    if (jumpButton) {
      jumpToTarget(jumpButton.dataset.jumpTarget, jumpButton.dataset.jumpAct || "");
      return;
    }
    const drawerButton = event.target.closest("[data-open-drawer]");
    if (drawerButton) {
      openDrawer(drawerButton.dataset.openDrawer || "");
      return;
    }
    const button = event.target.closest("[data-link-profile-id]");
    if (button) {
      switchLinkDirectorProfile(button.dataset.linkProfileId);
      return;
    }
    const weakScenarioButton = event.target.closest("[data-weak-scenario-id]");
    if (!weakScenarioButton) return;
    state.selectedWeakScenarioId = weakScenarioButton.dataset.weakScenarioId || "";
    state.weakScenarioPinnedByUser = true;
    renderAll();
  });
  document.addEventListener("change", (event) => {
    if (event.target.id !== "archiveSessionSelect") return;
    loadArchiveSession(event.target.value).catch((error) => setFeedback(error.message, "error"));
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeDrawer();
    }
  });
}

async function bootstrap() {
  bindEvents();
  await refreshAll();
  applyActiveAct();
}

bootstrap().catch((error) => {
  setFeedback(error.message, "error");
});
