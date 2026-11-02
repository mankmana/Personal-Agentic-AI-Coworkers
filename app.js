const state = { currentView: "overview", running: false, selectedArticle: 0 };
const panels = [...document.querySelectorAll("[data-panel]")];
const navItems = [...document.querySelectorAll("[data-view]")];
const breadcrumb = document.querySelector("#breadcrumb-current");
const pageTitle = document.querySelector("#page-title");
const toast = document.querySelector("#toast");
const runButton = document.querySelector("#run-button");

const articleData = [
  {
    title: "Why durable execution is becoming the new reliability primitive",
    tag: "FRONTIER LABS",
    tagClass: "tag-teal",
    source: "Temporal Engineering",
    readTime: "7 min read",
    summary: "Long-running agent workflows fail differently from request/response services: they must survive retries, worker restarts, partial tool calls, and human handoffs. Durable execution frameworks externalize progress so the workflow can resume from the last safe checkpoint instead of starting over.",
    takeaways: ["Checkpoint every side effect before moving to the next step.", "Make retries idempotent so recovery does not create duplicate work.", "Trace state transitions, not just individual service calls."],
    action: "SREs who can reason about failure across async systems will be well-positioned to operate agentic platforms.",
  },
  {
    title: "Operating Kubernetes with a platform team mindset",
    tag: "GOOGLE CLOUD",
    tagClass: "tag-blue",
    source: "Google Cloud Blog",
    readTime: "5 min read",
    summary: "Platform engineering is moving beyond a collection of internal tools. The strongest teams build paved roads with clear ownership, observable service-level signals, and enough guardrails to reduce cognitive load without hiding operational reality.",
    takeaways: ["Measure platform adoption and developer friction, not tool count.", "Offer a safe default path while keeping escape hatches visible.", "Treat internal platforms like products with feedback loops."],
    action: "Use your support background as an advantage: document one paved road that would make a recurring handoff easier for developers.",
  },
  {
    title: "Tracing the path from model call to production incident",
    tag: "OPENAI",
    tagClass: "tag-purple",
    source: "OpenAI Engineering",
    readTime: "9 min read",
    summary: "Observability for AI systems needs to connect model calls, tool use, prompt and policy decisions, cost, latency, and human escalation into one incident story. A single request trace is not enough when the system can branch, retry, or ask for help.",
    takeaways: ["Correlate model, tool, and infrastructure spans in one trace.", "Track quality and cost signals beside latency and errors.", "Make human escalation an observable state transition."],
    action: "Sketch the trace context you would want during an incident involving a model call, a tool timeout, and a manual escalation.",
  },
];

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
    showToast(`Brief selected · ${articleData[state.selectedArticle].source}`);
  });
});

function renderArticleDetail(index) {
  const article = articleData[index];
  if (!article) return;
  document.querySelector("#detail-heading").textContent = article.title;
  document.querySelector("#detail-meta").innerHTML = `<span class="tag ${article.tagClass}">${article.tag}</span><span>${article.source}</span><span>${article.readTime}</span>`;
  document.querySelector("#detail-summary").textContent = article.summary;
  document.querySelector("#detail-takeaways").innerHTML = article.takeaways.map((takeaway) => `<li>${takeaway}</li>`).join("");
  document.querySelector("#detail-action-text").textContent = article.action;
  document.querySelector("#detail-reference").textContent = `Reference · ${article.source}`;
}

renderArticleDetail(state.selectedArticle);

document.querySelectorAll(".filter").forEach((filter) => {
  filter.addEventListener("click", () => {
    document.querySelectorAll(".filter").forEach((item) => item.classList.remove("active"));
    filter.classList.add("active");
    showToast(`${filter.textContent} signals are now in view.`);
  });
});

runButton.addEventListener("click", () => {
  if (state.running) return;
  state.running = true;
  runButton.innerHTML = '<span class="button-pulse"></span> Scanning sources…';
  runButton.disabled = true;
  showToast("Daily scan started · checking sources and role signals.");
  window.setTimeout(() => {
    runButton.innerHTML = '<span class="button-pulse"></span> Run daily scan <span class="button-arrow">↗</span>';
    runButton.disabled = false;
    state.running = false;
    showToast("Scan complete · 2 new signals added to your brief.");
  }, 2400);
});

document.querySelector("#challenge-button")?.addEventListener("click", () => {
  setView("lab");
  showToast("Challenge ready · answer the incident command prompt.");
});

document.querySelector("#reference-button")?.addEventListener("click", () => {
  showToast("Reference connector pending · this preview is using sample article content.");
});

document.querySelector("#submit-answer")?.addEventListener("click", (event) => {
  const answer = document.querySelector(".answer-box").textContent.trim();
  if (!answer || answer === "Start typing your response…") {
    showToast("Add a response first so the agent can evaluate your thinking.");
    document.querySelector(".answer-box").focus();
    return;
  }
  const submitButton = event.currentTarget;
  submitButton.innerHTML = "Evaluating…";
  submitButton.disabled = true;
  window.setTimeout(() => {
    submitButton.innerHTML = 'Feedback ready <span>↗</span>';
    showToast("Assessment complete · your readiness report has been updated.");
  }, 1400);
});

document.querySelector(".answer-box")?.addEventListener("focus", (event) => {
  const placeholder = event.currentTarget.querySelector("span");
  if (placeholder) placeholder.remove();
});
