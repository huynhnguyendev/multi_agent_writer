/**
 * Multi-Agent Writer - Frontend logic.
 *
 * Toàn bộ API backend đều cùng origin (FastAPI serve luôn index.html),
 * nên không cần cấu hình base URL riêng.
 */

const API_BASE = "";
const POLL_INTERVAL_MS = 3000;

const NODE_ORDER = [
  "guardrail",
  "supervisor",
  "planner",
  "hitl",
  "executor",
  "image_resolver",
  "synthesizer",
  "evaluator",
  "save_output",
];
const NODE_LABELS = {
  guardrail: "Guardrail",
  supervisor: "Supervisor",
  planner: "Planner",
  hitl: "HITL",
  executor: "Executor",
  image_resolver: "Images",
  synthesizer: "Synthesizer",
  evaluator: "Evaluator",
  save_output: "Output",
};

// ============================================================
// STATE
// ============================================================

const state = {
  workflowId: null,
  pollTimer: null,
  lastStatus: null,
  lastCurrentNode: undefined,
  cachedPlan: null,
  articleMarkdown: null,
  editTaskCounter: 0,
  planUiMode: "view", // "view" | "edit" | "reject"
  isRegeneratingPlan: false,
};

// ============================================================
// DOM REFS
// ============================================================

const el = {
  pipelineRail: document.getElementById("pipeline-rail"),
  overallFill: document.getElementById("overall-progress-fill"),
  overallText: document.getElementById("overall-progress-text"),

  errorBanner: document.getElementById("error-banner"),
  errorTitle: document.getElementById("error-banner-title"),
  errorMessage: document.getElementById("error-banner-message"),
  retryBtn: document.getElementById("retry-btn"),

  composerPanel: document.getElementById("composer-panel"),
  composerForm: document.getElementById("composer-form"),
  composerSummary: document.getElementById("composer-summary"),
  composerSummaryTopic: document.getElementById("composer-summary-topic"),
  startBtn: document.getElementById("start-btn"),

  fTopic: document.getElementById("f-topic"),
  fRawInput: document.getElementById("f-raw-input"),
  fLanguage: document.getElementById("f-language"),
  fArticleType: document.getElementById("f-article-type"),
  fAudience: document.getElementById("f-audience"),
  fTone: document.getElementById("f-tone"),

  planPanel: document.getElementById("plan-panel"),
  planStatusBadge: document.getElementById("plan-status-badge"),
  planProgressFill: document.getElementById("plan-progress-fill"),
  planView: document.getElementById("plan-view"),
  planTitle: document.getElementById("plan-title"),
  planObjective: document.getElementById("plan-objective"),
  planAudience: document.getElementById("plan-audience"),
  planTone: document.getElementById("plan-tone"),
  planTaskList: document.getElementById("plan-task-list"),
  planActions: document.getElementById("plan-actions"),
  planHint: document.getElementById("plan-hint"),
  planApproveBtn: document.getElementById("plan-approve-btn"),
  planEditBtn: document.getElementById("plan-edit-btn"),
  planRejectBtn: document.getElementById("plan-reject-btn"),
  planRegeneratingNotice: document.getElementById("plan-regenerating-notice"),

  planEditForm: document.getElementById("plan-edit-form"),
  eTitle: document.getElementById("e-title"),
  eObjective: document.getElementById("e-objective"),
  eAudience: document.getElementById("e-audience"),
  eTone: document.getElementById("e-tone"),
  editTaskList: document.getElementById("edit-task-list"),
  addTaskBtn: document.getElementById("add-task-btn"),
  saveEditBtn: document.getElementById("save-edit-btn"),
  cancelEditBtn: document.getElementById("cancel-edit-btn"),

  planRejectForm: document.getElementById("plan-reject-form"),
  rejectFeedback: document.getElementById("reject-feedback"),
  confirmRejectBtn: document.getElementById("confirm-reject-btn"),
  cancelRejectBtn: document.getElementById("cancel-reject-btn"),

  tasksPanel: document.getElementById("tasks-panel"),
  taskGrid: document.getElementById("task-grid"),

  articlePanel: document.getElementById("article-panel"),
  articleScoreBadge: document.getElementById("article-score-badge"),
  viewRenderedBtn: document.getElementById("view-rendered-btn"),
  viewRawBtn: document.getElementById("view-raw-btn"),
  articleRendered: document.getElementById("article-rendered"),
  articleRaw: document.getElementById("article-raw"),
  copyBtn: document.getElementById("copy-btn"),
  downloadBtn: document.getElementById("download-btn"),
  newArticleBtn: document.getElementById("new-article-btn"),

  logBody: document.getElementById("log-body"),

  taskCardTemplate: document.getElementById("task-card-template"),
  editTaskTemplate: document.getElementById("edit-task-template"),
};

// ============================================================
// LOG
// ============================================================

function log(message, level = "") {
  const empty = el.logBody.querySelector(".log-empty");
  if (empty) empty.remove();

  const entry = document.createElement("p");
  entry.className = `log-entry${level ? ` log-entry--${level}` : ""}`;
  const time = new Date().toLocaleTimeString("vi-VN", { hour12: false });
  entry.innerHTML = `<span class="log-entry__time">${time}</span>${escapeHtml(message)}`;
  el.logBody.prepend(entry);
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

// ============================================================
// API HELPERS
// ============================================================

async function apiRequest(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!res.ok) {
    let detail = `Lỗi HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch (_) {
      /* ignore parse error */
    }
    throw new Error(detail);
  }

  return res.json();
}

// ============================================================
// PIPELINE RAIL
// ============================================================

function renderPipelineRail(data) {
  const states = computePipelineStates(data);

  el.pipelineRail.innerHTML = "";
  NODE_ORDER.forEach((nodeKey, i) => {
    const wrap = document.createElement("div");
    wrap.className = `pipeline-node pipeline-node--${states[nodeKey]}`;
    wrap.innerHTML = `
      <span class="pipeline-node__dot"></span>
      <span class="pipeline-node__label">${NODE_LABELS[nodeKey]}</span>
    `;
    el.pipelineRail.appendChild(wrap);

    if (i < NODE_ORDER.length - 1) {
      const line = document.createElement("span");
      line.className = "pipeline-node__line";
      el.pipelineRail.appendChild(line);
    }
  });
}

function computePipelineStates(data) {
  const states = {};
  NODE_ORDER.forEach((n) => (states[n] = "pending"));
  const { status, current_node: currentNode } = data;

  if (status === "blocked") {
    states.guardrail = "error";
    return states;
  }

  if (status === "failed") {
    const idx = NODE_ORDER.indexOf(currentNode);
    NODE_ORDER.forEach((n, i) => {
      states[n] = i < idx ? "done" : i === idx ? "error" : "pending";
    });
    if (idx === -1) states.guardrail = "error";
    return states;
  }

  if (status === "completed") {
    NODE_ORDER.forEach((n) => (states[n] = "done"));
    return states;
  }

  const idx = NODE_ORDER.indexOf(currentNode);
  NODE_ORDER.forEach((n, i) => {
    states[n] = i <= idx ? "done" : "pending";
  });

  if (status === "waiting_hitl") {
    states.hitl = "waiting";
  } else {
    const nextIdx = idx + 1;
    if (nextIdx < NODE_ORDER.length) states[NODE_ORDER[nextIdx]] = "active";
  }

  return states;
}

// ============================================================
// MAIN RENDER (gọi mỗi lần poll)
// ============================================================

function render(data) {
  el.overallFill.style.width = `${data.overall_progress}%`;
  el.overallText.textContent = `${data.overall_progress}%`;
  renderPipelineRail(data);

  diffLog(data);

  if (data.status === "blocked" || data.status === "failed") {
    showErrorBanner(data);
    stopPolling();
    return;
  }
  hideErrorBanner();

  if (data.status === "waiting_hitl" && data.plan) {
    // Plan mới (do Planner tạo lại sau reject) đã thực sự tới -> tắt
    // trạng thái "đang tạo lại", cập nhật cache về bản mới nhất.
    state.isRegeneratingPlan = false;
    state.cachedPlan = data.plan;
  }

  if (data.status === "waiting_hitl") {
    showPlanPanel(data);
  } else if (state.cachedPlan) {
    showPlanPanel(data, { readOnlyDone: true });
  }

  if (data.tasks && data.tasks.length > 0) {
    showTasksPanel(data.tasks);
  }

  if (data.status === "completed") {
    loadArticle();
    stopPolling();
  }
}

function diffLog(data) {
  if (state.lastCurrentNode !== data.current_node && data.current_node) {
    log(
      `Node "${NODE_LABELS[data.current_node] || data.current_node}" hoàn tất.`,
    );
  }
  if (state.lastStatus !== data.status) {
    const map = {
      running: ["Workflow đang chạy...", ""],
      waiting_hitl: ["Đang chờ bạn xác nhận kế hoạch.", "waiting"],
      completed: ["Hoàn tất! Bài viết đã sẵn sàng.", "success"],
      blocked: ["Yêu cầu bị chặn bởi bộ lọc an toàn.", "error"],
      failed: ["Workflow gặp lỗi.", "error"],
    };
    if (map[data.status]) log(...map[data.status]);
  }
  state.lastStatus = data.status;
  state.lastCurrentNode = data.current_node;
}

// ============================================================
// ERROR BANNER
// ============================================================

function showErrorBanner(data) {
  el.errorBanner.classList.remove("is-hidden");
  el.errorTitle.textContent =
    data.status === "blocked" ? "Yêu cầu bị chặn" : "Workflow thất bại";
  el.errorMessage.textContent =
    data.error_message || "Không có thêm thông tin chi tiết.";
}

function hideErrorBanner() {
  el.errorBanner.classList.add("is-hidden");
}

el.retryBtn.addEventListener("click", resetApp);

// ============================================================
// PLAN PANEL
// ============================================================

function showPlanPanel(data, opts = {}) {
  el.planPanel.classList.remove("is-hidden");
  const plan = data.plan || state.cachedPlan;
  if (!plan) return;

  const isWaiting = data.status === "waiting_hitl";

  // Đang chờ Planner tạo lại Plan mới sau khi reject -> ẩn nội dung
  // Plan CŨ đi, chỉ hiện thông báo, tránh gây hiểu lầm là hệ thống
  // "đứng yên" hoặc chưa nhận được yêu cầu reject.
  if (state.isRegeneratingPlan) {
    el.planRegeneratingNotice.classList.remove("is-hidden");
    el.planTitle.parentElement.classList.add("is-hidden"); // .plan-meta
    el.planTaskList.classList.add("is-hidden");
    el.planActions.classList.add("is-hidden");
    el.planHint.classList.add("is-hidden");
    el.planStatusBadge.textContent = "Đang tạo lại";
    el.planStatusBadge.className = "status-badge status-badge--waiting";
    el.planProgressFill.style.width = `${data.plan_progress}%`;
    return;
  }

  el.planRegeneratingNotice.classList.add("is-hidden");
  el.planTitle.parentElement.classList.remove("is-hidden");
  el.planTaskList.classList.remove("is-hidden");

  el.planTitle.textContent = plan.title;
  el.planObjective.textContent = plan.objective;
  el.planAudience.textContent = plan.target_audience;
  el.planTone.textContent = plan.tone;
  el.planProgressFill.style.width = `${data.plan_progress}%`;

  el.planTaskList.innerHTML = "";
  plan.tasks.forEach((t, i) => {
    const li = document.createElement("li");
    li.innerHTML = `<span class="task-index">${String(i + 1).padStart(2, "0")}</span><span>${escapeHtml(t.title)}</span>`;
    el.planTaskList.appendChild(li);
  });

  el.planStatusBadge.textContent = isWaiting ? "Chờ xác nhận" : "Đã chấp nhận";
  el.planStatusBadge.className = `status-badge ${isWaiting ? "status-badge--waiting" : "status-badge--success"}`;

  el.planActions.classList.toggle("is-hidden", !isWaiting);
  el.planHint.classList.toggle("is-hidden", !isWaiting);

  if (state.planUiMode === "view") {
    el.planEditForm.classList.add("is-hidden");
    el.planRejectForm.classList.add("is-hidden");
    el.planView.classList.remove("is-hidden");
  }
}

el.planApproveBtn.addEventListener("click", async () => {
  await sendHitlDecision({
    action: "approved",
    edited_plan: null,
    feedback: null,
  });
});

el.planRejectBtn.addEventListener("click", () => {
  state.planUiMode = "reject";
  el.planView.classList.add("is-hidden");
  el.planRejectForm.classList.remove("is-hidden");
  pauseHitlTimeout();
});

el.cancelRejectBtn.addEventListener("click", () => {
  state.planUiMode = "view";
  el.planRejectForm.classList.add("is-hidden");
  el.planView.classList.remove("is-hidden");
  resumeHitlTimeout();
});

el.confirmRejectBtn.addEventListener("click", async () => {
  const feedback = el.rejectFeedback.value.trim();
  if (!feedback) {
    alert("Vui lòng nhập yêu cầu chỉnh sửa.");
    return;
  }
  state.isRegeneratingPlan = true;
  await sendHitlDecision({ action: "rejected", edited_plan: null, feedback });
});

// ---------- Edit Plan Form ----------

el.planEditBtn.addEventListener("click", () => {
  const plan = state.cachedPlan;
  if (!plan) return;

  state.planUiMode = "edit";
  pauseHitlTimeout();

  el.eTitle.value = plan.title;
  el.eObjective.value = plan.objective;
  el.eAudience.value = plan.target_audience;
  el.eTone.value = plan.tone;

  el.editTaskList.innerHTML = "";
  plan.tasks.forEach((t) => addEditTaskCard(t));

  el.planView.classList.add("is-hidden");
  el.planEditForm.classList.remove("is-hidden");
});

el.cancelEditBtn.addEventListener("click", () => {
  state.planUiMode = "view";
  el.planEditForm.classList.add("is-hidden");
  el.planView.classList.remove("is-hidden");
  resumeHitlTimeout();
});

el.cancelEditBtn.addEventListener("click", () => {
  el.planEditForm.classList.add("is-hidden");
  el.planView.classList.remove("is-hidden");
});

function addEditTaskCard(taskData) {
  const count = el.editTaskList.children.length;
  if (count >= 7) {
    alert("Tối đa 7 task.");
    return;
  }

  const fragment = el.editTaskTemplate.content.cloneNode(true);
  const card = fragment.querySelector(".edit-task-card");
  const id = taskData?.id || `task_new_${++state.editTaskCounter}`;
  card.dataset.taskId = id;
  card.dataset.dependsOn = JSON.stringify(taskData?.depends_on || []);
  card.dataset.order = taskData?.order ?? count;
  // Giữ nguyên research_queries gốc (nếu có) - chỉ dùng lại khi user
  // KHÔNG đổi trạng thái checkbox, tránh mất query cụ thể mà Planner
  // đã tạo ra ban đầu.
  card.dataset.researchQueries = JSON.stringify(
    taskData?.research_queries || [],
  );

  card.querySelector(".edit-task-card__label").textContent = id;
  card.querySelector(".et-title").value = taskData?.title || "";
  card.querySelector(".et-description").value = taskData?.description || "";
  card.querySelector(".et-objective").value = taskData?.objective || "";
  card.querySelector(".et-expected-output").value =
    taskData?.expected_output || "";
  card.querySelector(".et-requires-research").checked =
    taskData?.requires_research || false;

  card
    .querySelector(".edit-task-card__remove")
    .addEventListener("click", () => {
      if (el.editTaskList.children.length <= 3) {
        alert("Kế hoạch cần tối thiểu 3 task.");
        return;
      }
      removeTaskIdFromDependencies(id);
      card.remove();
    });

  el.editTaskList.appendChild(fragment);
}

function removeTaskIdFromDependencies(removedId) {
  el.editTaskList.querySelectorAll(".edit-task-card").forEach((card) => {
    const deps = JSON.parse(card.dataset.dependsOn || "[]").filter(
      (d) => d !== removedId,
    );
    card.dataset.dependsOn = JSON.stringify(deps);
  });
}

el.addTaskBtn.addEventListener("click", () => addEditTaskCard(null));

el.saveEditBtn.addEventListener("click", async () => {
  const cards = [...el.editTaskList.querySelectorAll(".edit-task-card")];
  if (cards.length < 3 || cards.length > 7) {
    alert("Kế hoạch cần từ 3 đến 7 task.");
    return;
  }

  const tasks = cards.map((card, i) => {
    const title = card.querySelector(".et-title").value.trim();
    const requiresResearch = card.querySelector(
      ".et-requires-research",
    ).checked;
    let researchQueries = JSON.parse(card.dataset.researchQueries || "[]");

    if (requiresResearch && researchQueries.length === 0 && title) {
      researchQueries = [title];
    }
    if (!requiresResearch) {
      researchQueries = [];
    }

    return {
      id: card.dataset.taskId,
      title,
      description: card.querySelector(".et-description").value.trim(),
      objective: card.querySelector(".et-objective").value.trim(),
      expected_output: card.querySelector(".et-expected-output").value.trim(),
      requires_research: requiresResearch,
      research_queries: researchQueries,
      depends_on: JSON.parse(card.dataset.dependsOn || "[]"),
      order: i,
    };
  });

  const hasEmpty = tasks.some(
    (t) => !t.title || !t.description || !t.objective || !t.expected_output,
  );
  if (hasEmpty) {
    alert("Vui lòng điền đầy đủ thông tin cho tất cả task.");
    return;
  }

  const editedPlan = {
    title: el.eTitle.value.trim(),
    objective: el.eObjective.value.trim(),
    target_audience: el.eAudience.value.trim(),
    tone: el.eTone.value.trim(),
    estimated_sections: tasks.length,
    tasks,
  };

  // Cập nhật cache NGAY bằng bản đã edit - vì sau khi approve+edited,
  // backend không còn trả lại data.plan qua /status nữa (chỉ trả khi
  // waiting_hitl), nên nếu không cập nhật ở đây, Plan panel sẽ mãi
  // hiển thị bản GỐC (trước khi edit) thay vì bản user vừa sửa.
  state.cachedPlan = editedPlan;

  await sendHitlDecision({
    action: "edited",
    edited_plan: editedPlan,
    feedback: null,
  });
});

async function sendHitlDecision(body) {
  try {
    await apiRequest(`/workflow/${state.workflowId}/hitl`, {
      method: "POST",
      body: JSON.stringify(body),
    });
    log(`Đã gửi quyết định: ${body.action}.`);
    state.planUiMode = "view";
    el.planEditForm.classList.add("is-hidden");
    el.planRejectForm.classList.add("is-hidden");
    el.planView.classList.remove("is-hidden");
  } catch (err) {
    alert(`Không thể gửi quyết định: ${err.message}`);
  }
}

async function pauseHitlTimeout() {
  try {
    await apiRequest(`/workflow/${state.workflowId}/hitl/pause`, {
      method: "POST",
    });
    log("Đã tạm dừng đếm giờ tự động chấp nhận.", "waiting");
  } catch (err) {
    console.warn("Không thể tạm dừng đếm giờ:", err.message);
  }
}

async function resumeHitlTimeout() {
  try {
    await apiRequest(`/workflow/${state.workflowId}/hitl/resume`, {
      method: "POST",
    });
    log("Đã tiếp tục đếm giờ tự động chấp nhận.");
  } catch (err) {
    console.warn("Không thể tiếp tục đếm giờ:", err.message);
  }
}

// ============================================================
// TASKS PANEL
// ============================================================

function showTasksPanel(tasks) {
  el.tasksPanel.classList.remove("is-hidden");
  el.taskGrid.innerHTML = "";

  tasks.forEach((t) => {
    const fragment = el.taskCardTemplate.content.cloneNode(true);
    const card = fragment.querySelector(".task-card");
    card.classList.add(`task-card--${t.status}`);

    card.querySelector(".task-card__id").textContent = t.task_id;
    card.querySelector(".task-card__title").textContent = t.title;
    card.querySelector(".task-card__badge").textContent = statusLabel(t.status);
    card
      .querySelector(".task-card__badge")
      .classList.add(`status-badge--${statusBadgeVariant(t.status)}`);
    card.querySelector(".progress-bar__fill").style.width = `${t.progress}%`;

    if (t.error_message) {
      const errEl = card.querySelector(".task-card__error");
      errEl.textContent = t.error_message;
      errEl.classList.remove("is-hidden");
    }

    el.taskGrid.appendChild(fragment);
  });
}

function statusLabel(status) {
  return (
    { pending: "Chờ", running: "Đang chạy", success: "Xong", failed: "Lỗi" }[
      status
    ] || status
  );
}
function statusBadgeVariant(status) {
  return (
    {
      pending: "pending",
      running: "running",
      success: "success",
      failed: "error",
    }[status] || "pending"
  );
}

// ============================================================
// ARTICLE PANEL
// ============================================================

async function loadArticle() {
  try {
    const data = await apiRequest(`/workflow/${state.workflowId}/article`);
    state.articleMarkdown = data.markdown;

    el.articlePanel.classList.remove("is-hidden");
    el.articleScoreBadge.textContent =
      data.article_score != null
        ? `Điểm: ${data.article_score.toFixed(1)}/10`
        : "";

    const clean = DOMPurify.sanitize(marked.parse(data.markdown));
    el.articleRendered.innerHTML = clean;
    el.articleRaw.textContent = data.markdown;
  } catch (err) {
    log(`Không tải được bài viết: ${err.message}`, "error");
  }
}

el.viewRenderedBtn.addEventListener("click", () =>
  switchArticleView("rendered"),
);
el.viewRawBtn.addEventListener("click", () => switchArticleView("raw"));

function switchArticleView(mode) {
  const isRendered = mode === "rendered";
  el.articleRendered.classList.toggle("is-hidden", !isRendered);
  el.articleRaw.classList.toggle("is-hidden", isRendered);
  el.viewRenderedBtn.classList.toggle("is-active", isRendered);
  el.viewRawBtn.classList.toggle("is-active", !isRendered);
}

el.copyBtn.addEventListener("click", async () => {
  if (!state.articleMarkdown) return;
  try {
    await navigator.clipboard.writeText(state.articleMarkdown);
    el.copyBtn.textContent = "Đã sao chép!";
    setTimeout(() => (el.copyBtn.textContent = "Sao chép"), 1500);
  } catch (_) {
    alert("Không thể sao chép, trình duyệt không hỗ trợ.");
  }
});

el.downloadBtn.addEventListener("click", () => {
  window.open(`${API_BASE}/workflow/${state.workflowId}/download`, "_blank");
});

el.newArticleBtn.addEventListener("click", resetApp);

// ============================================================
// COMPOSER (start workflow)
// ============================================================

el.composerForm.addEventListener("submit", async (e) => {
  e.preventDefault();

  const topic = el.fTopic.value.trim();
  if (!topic) {
    alert("Vui lòng nhập chủ đề bài viết.");
    return;
  }

  el.startBtn.disabled = true;
  el.startBtn.textContent = "Đang khởi tạo...";

  try {
    const body = {
      topic,
      language: el.fLanguage.value,
      article_type: el.fArticleType.value,
      target_audience: el.fAudience.value.trim() || null,
      tone: el.fTone.value,
      raw_input: el.fRawInput.value.trim() || null,
    };

    const data = await apiRequest("/workflow", {
      method: "POST",
      body: JSON.stringify(body),
    });
    state.workflowId = data.workflow_id;

    log(`Đã tạo workflow: ${data.workflow_id}`);
    el.composerForm.classList.add("is-hidden");
    el.composerSummary.classList.remove("is-hidden");
    el.composerSummaryTopic.textContent = topic;

    startPolling();
  } catch (err) {
    alert(`Không thể bắt đầu workflow: ${err.message}`);
  } finally {
    el.startBtn.disabled = false;
    el.startBtn.textContent = "Bắt đầu viết bài";
  }
});

// ============================================================
// POLLING
// ============================================================

function startPolling() {
  stopPolling();
  poll();
  state.pollTimer = setInterval(poll, POLL_INTERVAL_MS);
}

function stopPolling() {
  if (state.pollTimer) {
    clearInterval(state.pollTimer);
    state.pollTimer = null;
  }
}

async function poll() {
  if (!state.workflowId) return;
  try {
    const data = await apiRequest(`/workflow/${state.workflowId}/status`);
    render(data);
  } catch (err) {
    log(`Lỗi khi cập nhật trạng thái: ${err.message}`, "error");
  }
}

// ============================================================
// RESET
// ============================================================

function resetApp() {
  stopPolling();
  state.workflowId = null;
  state.lastStatus = null;
  state.lastCurrentNode = undefined;
  state.cachedPlan = null;
  state.articleMarkdown = null;
  state.planUiMode = "view";
  state.isRegeneratingPlan = false;

  hideErrorBanner();
  el.composerForm.reset();
  el.composerForm.classList.remove("is-hidden");
  el.composerSummary.classList.add("is-hidden");

  el.planPanel.classList.add("is-hidden");
  el.tasksPanel.classList.add("is-hidden");
  el.articlePanel.classList.add("is-hidden");

  el.overallFill.style.width = "0%";
  el.overallText.textContent = "0%";
  renderPipelineRail({ status: "pending", current_node: null });

  el.logBody.innerHTML = '<p class="log-empty">Chưa có hoạt động nào.</p>';
}

// ============================================================
// INIT
// ============================================================

renderPipelineRail({ status: "pending", current_node: null });
