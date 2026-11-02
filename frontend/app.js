const state = { currentView: "overview", running: false, selectedArticle: 0, backendOnline: false, currentQuestion: null, learning: null, quiz: null };
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
  const referenceLink = document.querySelector("#reference-link");
  if (referenceLink) {
    referenceLink.href = article.reference || "#";
    referenceLink.hidden = !article.reference;
  }
}

function applyDashboard(data) {
  if (!data) return;
  if (data.learning) applyLearning(data.learning);
  renderArticleList(data.articles || []);
  renderRadar(data.articles || []);
}

function renderRadar(articles) {
  const radarArticles = articles.filter((article) => article.lane === "sre_devops_support").slice(0, 4);
  document.querySelectorAll(".radar-card").forEach((card, index) => {
    const article = radarArticles[index];
    if (!article) {
      card.hidden = true;
      return;
    }
    card.hidden = false;
    const tag = card.querySelector(".tag");
    const score = card.querySelector(".radar-score");
    const heading = card.querySelector("h3");
    const summary = card.querySelector("p");
    const sourceLink = card.querySelector(".radar-source-link");
    if (tag) {
      tag.className = `tag ${articleTagClass(article)}`;
      tag.textContent = article.source || "LIVE SOURCE";
    }
    if (score) score.textContent = `${article.source_type === "rss_atom" ? "grounded" : "source"}`;
    if (heading) heading.textContent = article.title;
    if (summary) summary.textContent = article.summary;
    if (sourceLink) {
      sourceLink.href = article.reference || "#";
      sourceLink.hidden = !article.reference;
    }
  });
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
  if (note) {
    note.innerHTML = learning.completed_today
      ? `Today’s 3-question quiz is complete${learning.quiz_score == null ? "" : ` · ${learning.quiz_score}/100`}. Keep the streak alive tomorrow.`
      : "Complete today’s 3-question quiz to start or continue your streak.";
  }
  if (days) days.innerHTML = (learning.completed_days || []).map((complete, index, values) => `<span class="${complete ? "done" : ""} ${index === values.length - 1 ? "today" : ""}"></span>`).join("");
}

function showLearningChallenge(learning) {
  state.learning = learning;
  const challenge = learning.challenge || {};
  document.querySelector("#challenge-source").textContent = `Grounded article · ${challenge.source_title || "today’s technical brief"} · ${challenge.source || "source"}`;
  const questions = challenge.questions || [{ prompt: challenge.prompt || "Choose one technical idea from today’s brief.", options: ["Option unavailable"] }];
  const savedAnswers = (learning.quiz_results || []).map((result) => result.selected_option);
  state.quiz = { questions, answers: questions.map((_, index) => savedAnswers[index] ?? null), index: 0 };
  const result = document.querySelector("#challenge-result");
  if (result) {
    result.hidden = !learning.completed_today;
    result.textContent = learning.completed_today ? `Today’s quiz is already complete${learning.quiz_score == null ? "" : ` · score ${learning.quiz_score}/100`}.` : "";
  }
  renderQuizQuestion();
  document.querySelector("#challenge-modal").hidden = false;
  document.querySelector("#challenge-options input")?.focus();
}

function renderQuizQuestion() {
  const quiz = state.quiz;
  if (!quiz) return;
  const question = quiz.questions[quiz.index] || quiz.questions[0];
  const completed = Boolean(state.learning?.completed_today);
  const progress = document.querySelector("#challenge-progress");
  const prompt = document.querySelector("#challenge-prompt");
  const options = document.querySelector("#challenge-options");
  const previous = document.querySelector("#quiz-previous");
  const next = document.querySelector("#complete-learning");
  if (progress) progress.textContent = `Question ${quiz.index + 1} of ${quiz.questions.length}`;
  if (prompt) prompt.textContent = question.prompt;
  if (options) {
    options.innerHTML = (question.options || []).map((option, index) => `<label class="quiz-option"><input type="radio" name="daily-quiz-option" value="${index}" ${quiz.answers[quiz.index] === index ? "checked" : ""} ${completed ? "disabled" : ""}><span class="quiz-option-marker">${String.fromCharCode(65 + index)}</span><span>${escapeHtml(option)}</span></label>`).join("");
    options.querySelectorAll("input").forEach((input) => {
      input.addEventListener("change", () => { quiz.answers[quiz.index] = Number(input.value); });
    });
  }
  if (previous) previous.disabled = completed || quiz.index === 0;
  if (next) {
    next.disabled = completed;
    next.innerHTML = quiz.index === quiz.questions.length - 1 ? "Submit quiz <span>↗</span>" : "Next question <span>↗</span>";
  }
}

function escapeHtml(value) {
  return String(value).replace(/[&<>\"]/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;" }[character]));
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

document.querySelectorAll(".radar-card").forEach((card) => {
  card.addEventListener("click", (event) => {
    if (event.target.closest("a")) return;
    const sourceLink = card.querySelector(".radar-source-link");
    if (sourceLink?.href && sourceLink.getAttribute("href") !== "#") window.open(sourceLink.href, "_blank", "noopener,noreferrer");
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

document.querySelector("#quiz-previous")?.addEventListener("click", () => {
  if (!state.quiz || state.quiz.index === 0) return;
  state.quiz.index -= 1;
  renderQuizQuestion();
  document.querySelector("#challenge-options input")?.focus();
});

document.querySelector("#complete-learning")?.addEventListener("click", async (event) => {
  if (!state.quiz || state.learning?.completed_today) return;
  if (state.quiz.answers[state.quiz.index] == null) {
    showToast("Choose one answer before continuing.");
    return;
  }
  if (state.quiz.index < state.quiz.questions.length - 1) {
    state.quiz.index += 1;
    renderQuizQuestion();
    document.querySelector("#challenge-options input")?.focus();
    return;
  }
  const button = event.currentTarget;
  button.disabled = true;
  button.textContent = "Saving…";
  try {
    const result = await apiRequest("/api/learning/complete", { method: "POST", body: JSON.stringify({ article_id: state.learning?.challenge?.source_article_id || null, answers: state.quiz.answers }) });
    applyLearning(result.learning);
    document.querySelector("#challenge-modal").hidden = true;
    showToast(`Quiz complete · ${result.learning.quiz_score}/100 · ${result.learning.streak_days}-day streak.`);
  } catch (error) {
    button.disabled = false;
    renderQuizQuestion();
    showToast("The challenge could not be saved. Try again.");
  }
});

syncDashboard();
