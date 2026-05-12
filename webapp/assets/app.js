import { fetchHealth, getWebAppConfig } from "./api.js";


const pageId = document.body.dataset.page || "home";
const config = getWebAppConfig();

const pageContent = {
  home: {
    eyebrow: "Hosted webapp shell",
    title: "Un front propre pour parler a l'API, sans passer par l'UI locale.",
    body:
      "Cette base pose un shell webapp separe, des routes pretes pour login, docs et chat, et un branchement HTTP direct vers l'API FastAPI.",
    primaryCta: { label: "Tester l'API", href: "#api-status" },
    secondaryCta: { label: "Ouvrir le chat", href: "/chat/" },
    panels: `
      <section class="panel panel-glow">
        <div class="panel-head">
          <span class="kicker">Routes pretes</span>
          <h2>Un shell deja decoupe par usages.</h2>
        </div>
        <div class="feature-grid">
          <article class="feature-card reveal">
            <span class="feature-tag">Login</span>
            <h3>Accueil utilisateur</h3>
            <p>Un ecran d'entree est pret pour brancher l'authentification plus tard.</p>
          </article>
          <article class="feature-card reveal">
            <span class="feature-tag">Docs</span>
            <h3>Contrat API visible</h3>
            <p>La route docs met en avant les endpoints et renvoie vers la doc FastAPI.</p>
          </article>
          <article class="feature-card reveal">
            <span class="feature-tag">Chat</span>
            <h3>Surface produit</h3>
            <p>La page chat prepare la disposition qui recevra plus tard <code>POST /ask</code> et les citations.</p>
          </article>
        </div>
      </section>
    `,
  },
  login: {
    eyebrow: "Route login",
    title: "Une porte d'entree sobre pour l'auth utilisateur.",
    body:
      "La page est volontairement simple: elle reserve la place pour l'identite, les roles et le session management sans engager le backend tout de suite.",
    primaryCta: { label: "Voir le chat", href: "/chat/" },
    secondaryCta: { label: "Voir les docs", href: "/docs/" },
    panels: `
      <section class="panel panel-form">
        <div class="panel-head">
          <span class="kicker">Login shell</span>
          <h2>Structure prete pour auth.</h2>
        </div>
        <form class="auth-form" data-placeholder-form>
          <label>
            Email
            <input type="email" placeholder="prenom@equipe.fr" />
          </label>
          <label>
            Mot de passe
            <input type="password" placeholder="********" />
          </label>
          <button type="submit" class="button button-primary">Continuer</button>
          <p class="form-note">Le backend d'auth n'est pas encore branche. Ce shell garde deja la place pour la suite.</p>
        </form>
      </section>
    `,
  },
  docs: {
    eyebrow: "Route docs",
    title: "Une page front qui rend le contrat backend lisible sans ouvrir le code.",
    body:
      "La webapp expose les points d'entree utiles, l'etat de l'API et un lien direct vers Swagger pour garder l'integration front-back simple.",
    primaryCta: { label: "Ouvrir Swagger", href: config.docsUrl, external: true },
    secondaryCta: { label: "Voir l'accueil", href: "/" },
    panels: `
      <section class="panel">
        <div class="panel-head">
          <span class="kicker">API map</span>
          <h2>Points d'entree visibles depuis le front.</h2>
        </div>
        <div class="endpoint-list">
          <article class="endpoint-card reveal">
            <span class="method method-get">GET</span>
            <div>
              <h3>/health</h3>
              <p>Disponible maintenant pour smoke test, monitoring et validation du boot API.</p>
            </div>
          </article>
          <article class="endpoint-card reveal">
            <span class="method method-post">POST</span>
            <div>
              <h3>/ask</h3>
              <p>Prochaine brique front produit: question utilisateur, answer, citations, sources et statut.</p>
            </div>
          </article>
          <article class="endpoint-card reveal">
            <span class="method method-post">POST</span>
            <div>
              <h3>/ingest</h3>
              <p>Route reservee pour l'alimentation des documents avec un suivi de job exploitable.</p>
            </div>
          </article>
        </div>
      </section>
    `,
  },
  chat: {
    eyebrow: "Route chat",
    title: "Une disposition deja calibree pour la conversation, les citations et les sources.",
    body:
      "Le shell anticipe les trois blocs qui compteront vraiment: saisie question, reponse structuree, et panneau lateral pour les pieces justificatives.",
    primaryCta: { label: "Verifier l'API", href: "#api-status" },
    secondaryCta: { label: "Voir les docs", href: "/docs/" },
    panels: `
      <section class="chat-layout">
        <article class="panel chat-panel">
          <div class="panel-head">
            <span class="kicker">Chat shell</span>
            <h2>Zone de conversation</h2>
          </div>
          <div class="message-list">
            <div class="message message-user reveal">
              <span class="message-label">Utilisateur</span>
              <p>Quelles pieces dois-je preparer pour une demande de titre de sejour ?</p>
            </div>
            <div class="message message-assistant reveal">
              <span class="message-label">Assistant</span>
              <p>Le flux <code>POST /ask</code> viendra remplir cette zone avec <code>answer</code>, <code>citations</code>, <code>sources</code> et <code>answer_status</code>.</p>
            </div>
          </div>
          <form class="composer" data-chat-form>
            <label class="composer-label" for="chat-question">Question</label>
            <textarea id="chat-question" name="question" placeholder="La route /ask arrive ensuite. Ce shell garde deja la place pour le vrai flux."></textarea>
            <button type="submit" class="button button-primary">Simuler le branchement</button>
            <p class="form-note" data-chat-feedback>Le front est connecte a <code>/health</code> maintenant. La soumission attend encore <code>POST /ask</code>.</p>
          </form>
        </article>

        <aside class="panel side-panel">
          <div class="panel-head">
            <span class="kicker">Future sidecar</span>
            <h2>Citations & sources</h2>
          </div>
          <div class="source-card reveal">
            <h3>Citations</h3>
            <p>La reponse affichera ici les extraits relies a la reponse principale.</p>
          </div>
          <div class="source-card reveal">
            <h3>Documents</h3>
            <p>Le panneau lateral est deja dimensionne pour les sources, scores et metadonnees utiles.</p>
          </div>
        </aside>
      </section>
    `,
  },
};


function renderApp() {
  const page = pageContent[pageId] || pageContent.home;
  const app = document.getElementById("app");

  app.innerHTML = `
    <div class="page-shell">
      <div class="ambient ambient-a"></div>
      <div class="ambient ambient-b"></div>

      <header class="topbar">
        <a class="brand" href="/">
          <span class="brand-mark">MR</span>
          <span class="brand-copy">
            <strong>Multi RAG Bot</strong>
            <small>Hosted webapp shell</small>
          </span>
        </a>

        <nav class="nav">
          ${renderNavLink("/", "home", "Accueil")}
          ${renderNavLink("/login/", "login", "Login")}
          ${renderNavLink("/docs/", "docs", "Docs")}
          ${renderNavLink("/chat/", "chat", "Chat")}
        </nav>
      </header>

      <main class="content">
        <section class="hero panel">
          <div class="hero-copy">
            <span class="kicker">${page.eyebrow}</span>
            <h1>${page.title}</h1>
            <p>${page.body}</p>
            <div class="cta-row">
              ${renderAction(page.primaryCta, "button button-primary")}
              ${renderAction(page.secondaryCta, "button button-secondary")}
            </div>
          </div>

          <aside class="hero-meta">
            <div class="meta-card">
              <span class="meta-label">API cible</span>
              <strong>${config.apiBaseUrl}</strong>
            </div>
            <div class="meta-card" id="api-status">
              <span class="meta-label">Etat backend</span>
              <strong data-health-state>Verification...</strong>
              <small data-health-detail>Connexion a /health en cours.</small>
            </div>
          </aside>
        </section>

        ${page.panels}

        <section class="panel">
          <div class="panel-head">
            <span class="kicker">Smoke test</span>
            <h2>Une preuve simple que le front parle au backend.</h2>
          </div>
          <div class="status-grid">
            <div class="status-card">
              <span class="status-label">Health URL</span>
              <code>${config.healthUrl}</code>
            </div>
            <div class="status-card">
              <span class="status-label">OpenAPI</span>
              <code>${config.openApiUrl}</code>
            </div>
            <div class="status-card">
              <span class="status-label">Action</span>
              <button type="button" class="button button-inline" data-health-refresh>Rafraichir le statut</button>
            </div>
          </div>
        </section>
      </main>
    </div>
  `;
}


function renderNavLink(href, id, label) {
  const activeClass = pageId === id ? "nav-link is-active" : "nav-link";
  return `<a class="${activeClass}" href="${href}">${label}</a>`;
}


function renderAction(action, className) {
  if (!action) {
    return "";
  }

  const target = action.external ? ' target="_blank" rel="noreferrer"' : "";
  return `<a class="${className}" href="${action.href}"${target}>${action.label}</a>`;
}


function bindUi() {
  const refreshButton = document.querySelector("[data-health-refresh]");
  if (refreshButton) {
    refreshButton.addEventListener("click", updateHealthState);
  }

  const placeholderForm = document.querySelector("[data-placeholder-form]");
  if (placeholderForm) {
    placeholderForm.addEventListener("submit", (event) => {
      event.preventDefault();
      const note = placeholderForm.querySelector(".form-note");
      note.textContent =
        "Le shell login est pret. L'authentification sera branchee quand le backend session sera disponible.";
    });
  }

  const chatForm = document.querySelector("[data-chat-form]");
  if (chatForm) {
    chatForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const feedback = chatForm.querySelector("[data-chat-feedback]");
      feedback.textContent =
        "Le shell front est deja relie a /health. La prochaine etape sera de brancher ce formulaire a POST /ask.";
      await updateHealthState();
    });
  }
}


async function updateHealthState() {
  const stateNode = document.querySelector("[data-health-state]");
  const detailNode = document.querySelector("[data-health-detail]");

  if (!stateNode || !detailNode) {
    return;
  }

  stateNode.textContent = "Verification...";
  stateNode.className = "";
  detailNode.textContent = `Appel en cours vers ${config.healthUrl}`;

  try {
    const result = await fetchHealth();
    stateNode.textContent = result.payload.status.toUpperCase();
    stateNode.className = "status-ok";
    detailNode.textContent = `${result.payload.service} repond correctement.`;
  } catch (error) {
    stateNode.textContent = "OFFLINE";
    stateNode.className = "status-offline";
    detailNode.textContent = error.message;
  }
}


renderApp();
bindUi();
updateHealthState();
