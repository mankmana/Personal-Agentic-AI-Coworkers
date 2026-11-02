const state = { currentView: "overview", running: false, selectedArticle: 0, backendOnline: false, currentQuestion: null, learning: null };
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
};

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("show");
  window.clearTimeout(showToast.timeout);
  showToast.timeout = window.setTimeout(() => toast.classList.remove("show"), 3600);
}

function setView(view) {
  if (!titles[view]) return;
  state.currentView = view;
  navItems.forEach((item) => {
    const active = item.dataset.view === view;
    item.classList.toggle("active", active);
    item.setAttribute("aria-current", active ? "page" : "false");
  });
  panels.forEach((panel) => {
    const active = panel.dataset.panel === view;
    panel.classList.toggle("active", active);
    panel.hidden = !active;
    panel.setAttribute("aria-hidden", String(!active));
  });
  breadcrumb.textContent = titles[view].breadcrumb;
  pageTitle.innerHTML = titles[view].title;
  window.scrollTo({ top: 0, behavior: "smooth" });
}

document.querySelectorAll("[data-view-target]").forEach((button) => {
  button.addEventListener("click", () => setView(button.dataset.viewTarget));
});
navItems.forEach((item) => item.addEventListener("click", () => setView(item.dataset.view)));
setView(state.currentView);

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
  if (data.learning) applyLearning(data.learning);
  renderArticleList(data.articles || []);
}

function applyLearning(learning) {
  state.learning = learning;
  const streak = document.querySelector("#learning-streak");
  const trend = document.querySelector("#learning-trend");
  const note = document.querySelector("#learning-note");
  const days = document.querySelector("#learning-days");
  if (streak) streak.textContent = String(learning.streak_days || 0).padStart(2, "0");
  if (trend) {
    const delta = Number(learning.week_delta || 0);
    trend.textContent = `${delta >= 0 ? "↗" : "↘"} ${Math.abs(delta)} days`;
    trend.classList.toggle("up", delta >= 0);
    trend.classList.toggle("neutral", delta < 0);
  }
  if (note) note.innerHTML = learning.completed_today ? "Today’s challenge is complete. Keep the streak alive tomorrow." : "Complete one article challenge today to start or continue your streak.";
  if (days) days.innerHTML = (learning.completed_days || []).map((complete, index, values) => `<span class="${complete ? "done" : ""} ${index === values.length - 1 ? "today" : ""}"></span>`).join("");
}

function showLearningChallenge(learning) {
  state.learning = learning;
  const challenge = learning.challenge || {};
  document.querySelector("#challenge-source").textContent = `Grounded article · ${challenge.source_title || "today’s technical brief"} · ${challenge.source || "source"}`;
  document.querySelector("#challenge-prompt").textContent = challenge.prompt || "Choose one technical idea from today’s brief and explain how you would apply it safely.";
  document.querySelector("#challenge-answer").value = "";
  const completeButton = document.querySelector("#complete-learning");
  completeButton.innerHTML = "Complete challenge <span>↗</span>";
  completeButton.disabled = Boolean(learning.completed_today);
  document.querySelector("#challenge-modal").hidden = false;
  document.querySelector("#challenge-answer").focus();
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
    const selectedDomain = filter.dataset.filter || "all";
    document.querySelectorAll(".radar-card").forEach((card) => {
      const domains = (card.dataset.domains || "all").split(" ");
      const visible = selectedDomain === "all" || domains.includes(selectedDomain);
      card.classList.toggle("is-hidden", !visible);
      card.setAttribute("aria-hidden", String(!visible));
    });
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

document.querySelector("#reference-button")?.addEventListener("click", () => {
  const article = articleData[state.selectedArticle];
  if (article?.reference) {
    window.open(article.reference, "_blank", "noopener,noreferrer");
    return;
  }
  showToast("No source URL is loaded yet. Run the daily scan first.");
});

document.querySelector("#learning-challenge-button")?.addEventListener("click", async () => {
  try {
    const learning = await apiRequest("/api/learning");
    state.backendOnline = true;
    showLearningChallenge(learning);
  } catch {
    showToast("The daily challenge is unavailable until the backend is connected.");
  }
});

document.querySelectorAll("[data-close-challenge]").forEach((element) => {
  element.addEventListener("click", () => { document.querySelector("#challenge-modal").hidden = true; });
});

document.querySelector("#complete-learning")?.addEventListener("click", async (event) => {
  const answer = document.querySelector("#challenge-answer").value.trim();
  if (answer.length < 20) {
    showToast("Write at least 20 characters to complete today’s challenge.");
    return;
  }
  const button = event.currentTarget;
  button.disabled = true;
  button.textContent = "Saving…";
  try {
    const result = await apiRequest("/api/learning/complete", { method: "POST", body: JSON.stringify({ article_id: state.learning?.challenge?.source_article_id || null, answer }) });
    applyLearning(result.learning);
    document.querySelector("#challenge-modal").hidden = true;
    showToast(`Learning day complete · ${result.learning.streak_days}-day streak.`);
  } catch (error) {
    button.disabled = false;
    button.innerHTML = 'Complete challenge <span>↗</span>';
    showToast("The challenge could not be saved. Try again.");
  }
});

syncDashboard();
