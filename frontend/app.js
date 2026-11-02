const state = { currentView: "overview", running: false, selectedArticle: 0, backendOnline: false, currentQuestion: null };
const panels = [...document.querySelectorAll("[data-panel]")];
const navItems = [...document.querySelectorAll("[data-view]")];
const breadcrumb = document.querySelector("#breadcrumb-current");
const pageTitle = document.querySelector("#page-title");
const toast = document.querySelector("#toast");
const runButton = document.querySelector("#run-button");

async function apiRequest(path, options = {}) {
  const response = await fetch(path, { headers: { "Content-Type": "application/json" }, ...options });
  if (!response.ok) throw new Error(`API ${response.status}`);
  return response.json();
}

const articleData = [];

const titles = {
  overview: { breadcrumb: "Overview", title: "Your technical edge,<br /><em>one day sharper.</em>" },
  workflow: { breadcrumb: "Agent workflow", title: "See the loop,<br /><em>step by step.</em>" },
  radar: { breadcrumb: "Technical radar", title: "Signals worth<br /><em>your attention.</em>" },
  lab: { breadcrumb: "Career lab", title: "Practice the work,<br /><em>earn the edge.</em>" },
};

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("show");
  window.clearTimeout(showToast.timeout);
  showToast.timeout = window.setTimeout(() => toast.classList.remove("show"), 3600);
}

function setView(view) {
  state.currentView = view;
  navItems.forEach((item) => item.classList.toggle("active", item.dataset.view === view));
  panels.forEach((panel) => panel.classList.toggle("active", panel.dataset.panel === view));
  breadcrumb.textContent = titles[view].breadcrumb;
  pageTitle.innerHTML = titles[view].title;
  window.scrollTo({ top: 0, behavior: "smooth" });
}

document.querySelectorAll("[data-view-target]").forEach((button) => {
  button.addEventListener("click", () => setView(button.dataset.viewTarget));
});
navItems.forEach((item) => item.addEventListener("click", () => setView(item.dataset.view)));

document.querySelectorAll(".agent-card").forEach((agent) => {
  agent.addEventListener("click", () => {
    if (agent.dataset.agent === "coach") {
      showToast("NextLevelPersonalCoachForCareerLevel is queued for phase two.");
      return;
    }
    showToast("DailyTechUpgradeAgent is already your active coworker.");
  });
});

document.querySelectorAll(".article-row").forEach((article) => {
  article.addEventListener("click", () => {
    state.selectedArticle = Number(article.dataset.article);
    document.querySelectorAll(".article-row").forEach((row) => row.classList.remove("selected"));
    article.classList.add("selected");
    renderArticleDetail(state.selectedArticle);
    showToast(`Brief selected · ${articleData[state.selectedArticle]?.source || "live source"}`);
  });
});

function articleTagClass(article) {
  if (article.tagClass) return article.tagClass;
  if (article.lane === "sre_devops_support") return "tag-blue";
  if ((article.tag || "").toLowerCase().includes("anthropic")) return "tag-purple";
  return "tag-teal";
}

function renderArticleList(articles) {
  if (!articles?.length) return;
  articleData.splice(0, articleData.length, ...articles.slice(0, 3).map((article) => ({
    ...article,
    tagClass: articleTagClass(article),
    readTime: article.readTime || article.read_time || "fresh signal",
    action: article.action || article.why_it_matters || "Turn this insight into a small practice task.",
  })));
  document.querySelectorAll(".article-row").forEach((row, index) => {
    const article = articleData[index];
    if (!article) return;
    row.querySelector(".article-number").textContent = String(index + 1).padStart(2, "0");
    row.querySelector(".article-meta .tag").className = `tag ${article.tagClass}`;
    row.querySelector(".article-meta .tag").textContent = article.tag || "LIVE SOURCE";
    row.querySelector(".article-meta span:nth-child(2)").textContent = article.readTime;
    row.querySelector("h3").textContent = article.title;
    row.querySelector("p").textContent = article.summary;
    row.querySelector(".article-footer span").textContent = article.source;
  });
  document.querySelectorAll(".article-row").forEach((row) => row.classList.remove("selected"));
  document.querySelector(`.article-row[data-article="${state.selectedArticle}"]`)?.classList.add("selected");
  renderArticleDetail(state.selectedArticle);
}

function renderArticleDetail(index) {
  const article = articleData[index];
  if (!article) return;
  const grounded = Boolean(article.grounded || article.reference);
  const kicker = document.querySelector("#detail-kicker");
  if (kicker) kicker.textContent = grounded ? "Selected article · live source summary" : "Selected article · source unavailable";
  document.querySelector("#detail-heading").textContent = article.title;
  document.querySelector("#detail-meta").innerHTML = `<span class="tag ${article.tagClass}">${article.tag}</span><span>${article.source}</span><span>${article.readTime}</span>`;
  document.querySelector("#detail-summary").textContent = article.summary;
  document.querySelector("#detail-takeaways").innerHTML = article.takeaways.map((takeaway) => `<li>${takeaway}</li>`).join("");
  document.querySelector("#detail-action-text").textContent = article.action || article.why_it_matters || "Turn this insight into a small practice task.";
  document.querySelector("#detail-reference").textContent = grounded ? `Reference · ${article.source}` : "No source loaded";
}

function applyDashboard(data) {
  if (!data) return;
  if (data.readiness) {
    const score = document.querySelector(".readiness-card .metric-value-row strong");
    const note = document.querySelector(".readiness-card .metric-note");
    if (score) score.textContent = data.readiness.overall;
    if (note) note.innerHTML = `You’re <b>${100 - data.readiness.overall} points</b> from your ${data.readiness.target} target.`;
    const reportScore = document.querySelector(".report-score > strong");
    if (reportScore) reportScore.textContent = data.readiness.overall;
  }
  renderArticleList(data.articles || []);
}

async function syncDashboard() {
  try {
    const data = await apiRequest("/api/dashboard");
    state.backendOnline = true;
    applyDashboard(data);
  } catch {
    state.backendOnline = false;
  }
}

document.querySelectorAll(".filter").forEach((filter) => {
  filter.addEventListener("click", () => {
    document.querySelectorAll(".filter").forEach((item) => item.classList.remove("active"));
    filter.classList.add("active");
    showToast(`${filter.textContent} signals are now in view.`);
  });
});

runButton.addEventListener("click", async () => {
  if (state.running) return;
  state.running = true;
  runButton.innerHTML = '<span class="button-pulse"></span> Scanning sources…';
  runButton.disabled = true;
  showToast("Daily scan started · checking sources and role signals.");
  try {
    const result = await apiRequest("/api/scan", { method: "POST", body: JSON.stringify({ lanes: ["general_ai_development", "sre_devops_support"] }) });
    state.backendOnline = true;
    applyDashboard(result.dashboard);
    runButton.innerHTML = '<span class="button-pulse"></span> Run daily scan <span class="button-arrow">↗</span>';
    runButton.disabled = false;
    state.running = false;
    showToast(`Scan complete · ${result.run.fetched} new source signals added.`);
  } catch {
    state.backendOnline = false;
    window.setTimeout(() => {
      runButton.innerHTML = '<span class="button-pulse"></span> Run daily scan <span class="button-arrow">↗</span>';
      runButton.disabled = false;
      state.running = false;
      showToast("Scan preview complete · backend connection is not available.");
    }, 1200);
    return;
  }
});

document.querySelector("#challenge-button")?.addEventListener("click", async () => {
  setView("lab");
  try {
    const articleId = articleData[state.selectedArticle]?.id || "";
    const challenge = await apiRequest(`/api/challenges/next?article_id=${encodeURIComponent(articleId)}`);
    state.backendOnline = true;
    state.currentQuestion = challenge;
    document.querySelector("#question-copy").textContent = challenge.prompt;
    showToast("Challenge ready · answer the personalized prompt.");
  } catch {
    state.backendOnline = false;
    showToast("Challenge ready · answer the article-based prompt.");
  }
});

document.querySelector("#reference-button")?.addEventListener("click", () => {
  const article = articleData[state.selectedArticle];
  if (article?.reference) {
    window.open(article.reference, "_blank", "noopener,noreferrer");
    return;
  }
  showToast("No source URL is loaded yet. Run the daily scan first.");
});

document.querySelector("#submit-answer")?.addEventListener("click", async (event) => {
  const answer = document.querySelector(".answer-box").textContent.trim();
  if (!answer || answer === "Start typing your response…") {
    showToast("Add a response first so the agent can evaluate your thinking.");
    document.querySelector(".answer-box").focus();
    return;
  }
  const submitButton = event.currentTarget;
  submitButton.innerHTML = "Evaluating…";
  submitButton.disabled = true;
  if (state.backendOnline) {
    try {
      const result = await apiRequest("/api/assessments", { method: "POST", body: JSON.stringify({ answer, question: state.currentQuestion }) });
      submitButton.innerHTML = 'Feedback ready <span>↗</span>';
      const score = document.querySelector(".report-score > strong");
      if (score) score.textContent = result.readiness.overall;
      showToast(`Assessment complete · readiness is now ${result.readiness.overall}/100.`);
      return;
    } catch {
      state.backendOnline = false;
    }
  }
  window.setTimeout(() => {
    submitButton.innerHTML = 'Feedback ready <span>↗</span>';
    submitButton.disabled = true;
    showToast("Assessment preview complete · connect the backend for scored feedback.");
  }, 800);
});

document.querySelector(".answer-box")?.addEventListener("focus", (event) => {
  const placeholder = event.currentTarget.querySelector("span");
  if (placeholder) placeholder.remove();
});

syncDashboard();
