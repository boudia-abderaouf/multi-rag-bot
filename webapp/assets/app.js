import { fetchHealth, getWebAppConfig } from "./api.js";
import {
  authenticateDemoUser,
  buildLoginUrl,
  clearSession,
  hasExpiredSession,
  getLoginReasonMessage,
  getSession,
  getSessionDurationHours,
  listDemoUsers,
  sanitizeInternalPath,
  startSession,
} from "./auth.js";


const pageId = document.body.dataset.page || "home";
const config = getWebAppConfig();
const currentUrl = new URL(window.location.href);
const requestedNextPath = sanitizeInternalPath(
  currentUrl.searchParams.get("next"),
  "/chat/"
);
const loginReason = currentUrl.searchParams.get("reason") || "";
const demoUsers = listDemoUsers();
let session = getSession();
const expiredSession = !session && hasExpiredSession();


try {
  if (guardPageAccess()) {
    renderApp();
    bindUi();
    updateHealthState();
  }
} catch (error) {
  renderBootError(error);
}


function guardPageAccess() {
  if (pageId === "chat" && !session) {
    window.location.replace(
      buildLoginUrl({
        next: `${window.location.pathname}${window.location.search}`,
        reason: expiredSession ? "session-expired" : "auth-required",
      })
    );
    return false;
  }

  if (pageId === "login" && session) {
    window.location.replace(requestedNextPath);
    return false;
  }

  return true;
}


function buildPageContent() {
  const isConnected = Boolean(session);
  const sessionHours = getSessionDurationHours();
  const activeSession = session || {
    name: "Invite demo",
    role: "Acces invite",
  };

  return {
    home: {
      eyebrow: isConnected ? "Session demo active" : "Hosted webapp shell",
      title: isConnected
        ? "L'espace applicatif est pret pour ton parcours demo."
        : "Un front propre pour parler a l'API, sans passer par l'UI locale.",
      body: isConnected
        ? `Tu es connecte en tant que ${escapeHtml(
            session.name
          )}. Le parcours demo peut maintenant t'envoyer vers le chat et garder une session locale simple.`
        : "Cette base pose un shell webapp separe, des routes pretes pour login, docs et chat, et un branchement HTTP direct vers l'API FastAPI.",
      primaryCta: isConnected
        ? { label: "Entrer dans l'espace applicatif", href: "/chat/" }
        : { label: "Se connecter en demo", href: "/login/" },
      secondaryCta: { label: "Voir les docs", href: "/docs/" },
      panels: `
        <section class="panel panel-glow">
          <div class="panel-head">
            <span class="kicker">Routes pretes</span>
            <h2>Un shell deja decoupe par usages.</h2>
          </div>
          <div class="feature-grid">
            <article class="feature-card reveal">
              <span class="feature-tag">Login</span>
              <h3>Acces invite</h3>
              <p>Les utilisateurs demo peuvent entrer sans backend d'auth complet ni complexite inutile.</p>
            </article>
            <article class="feature-card reveal">
              <span class="feature-tag">Docs</span>
              <h3>Contrat API visible</h3>
              <p>La route docs met en avant les endpoints et renvoie vers la doc FastAPI.</p>
            </article>
            <article class="feature-card reveal">
              <span class="feature-tag">Chat</span>
              <h3>Surface produit</h3>
              <p>La page chat est maintenant l'espace applicatif cible du parcours de connexion demo.</p>
            </article>
          </div>
        </section>
      `,
    },
    login: {
      eyebrow: "Login demo",
      title: "Une entree simple pour les utilisateurs invites.",
      body:
        "Choisis un profil demo ou saisis ses identifiants. La session reste locale au navigateur et te redirige ensuite vers l'espace applicatif.",
      primaryCta: { label: "Voir les comptes demo", href: "#demo-users" },
      secondaryCta: { label: "Retour accueil", href: "/" },
      panels: `
        <section class="auth-layout">
          <article class="panel panel-form">
            <div class="panel-head">
              <span class="kicker">Connexion</span>
              <h2>Entrer dans la webapp</h2>
            </div>
            <p class="panel-subcopy">
              Utilise un compte de demonstration. En cas d'erreur, le message reste lisible et la page ne casse pas.
            </p>
            <div class="notice notice-info" data-login-notice aria-live="polite"></div>
            <form class="auth-form" data-login-form novalidate>
              <input type="hidden" name="next" value="${escapeHtml(
                requestedNextPath
              )}" />
              <label>
                Email demo
                <input type="email" name="email" autocomplete="username" placeholder="invite.juriste@demo.local" />
              </label>
              <label>
                Code d'acces demo
                <input type="password" name="password" autocomplete="current-password" placeholder="demo-juriste" />
              </label>
              <div class="form-actions">
                <button type="submit" class="button button-primary">Entrer dans l'espace applicatif</button>
                <a class="button button-secondary" href="/">Annuler</a>
              </div>
              <p class="form-note">
                La session demo reste active ${sessionHours}h sur ce navigateur, sauf deconnexion manuelle.
              </p>
            </form>
          </article>

          <aside class="panel" id="demo-users">
            <div class="panel-head">
              <span class="kicker">Acces invites</span>
              <h2>Comptes de demonstration</h2>
            </div>
            <div class="demo-grid">
              ${demoUsers.map(renderDemoUserCard).join("")}
            </div>
          </aside>
        </section>
      `,
    },
    docs: {
      eyebrow: "Route docs",
      title: "Une page front qui rend le contrat backend lisible sans ouvrir le code.",
      body:
        "La webapp expose les points d'entree utiles, l'etat de l'API et un lien direct vers Swagger pour garder l'integration front-back simple.",
      primaryCta: { label: "Ouvrir Swagger", href: config.docsUrl, external: true },
      secondaryCta: session
        ? { label: "Entrer dans le chat", href: "/chat/" }
        : { label: "Se connecter", href: "/login/" },
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
      eyebrow: "Espace applicatif",
      title: "Une disposition deja calibree pour la conversation, les citations et les sources.",
      body: `Connecte en tant que ${escapeHtml(
        activeSession.name
      )}. Le shell anticipe deja la saisie question, la reponse structuree et le panneau lateral de preuves.`,
      primaryCta: { label: "Verifier l'API", href: "#api-status" },
      secondaryCta: { label: "Voir les docs", href: "/docs/" },
      panels: `
        <section class="chat-layout">
          <article class="panel chat-panel">
            <div class="panel-head">
              <span class="kicker">Chat shell</span>
              <h2>Zone de conversation</h2>
            </div>
            <div class="app-chip">
              <strong>${escapeHtml(activeSession.name)}</strong>
              <span>${escapeHtml(activeSession.role)}</span>
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
}


function renderApp() {
  const page = buildPageContent()[pageId] || buildPageContent().home;
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

        <div class="topbar-actions">
          <nav class="nav">
            ${renderNavLink("/", "home", "Accueil")}
            ${renderNavLink("/docs/", "docs", "Docs")}
            ${renderNavLink("/chat/", "chat", "Chat")}
            ${
              session
                ? ""
                : renderNavLink("/login/", "login", "Login")
            }
          </nav>
          ${renderSessionControls()}
        </div>
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
            ${
              session
                ? `
            <div class="meta-card">
              <span class="meta-label">Session demo</span>
              <strong>${escapeHtml(session.name)}</strong>
              <small>${escapeHtml(session.role)}</small>
            </div>
            `
                : `
            <div class="meta-card">
              <span class="meta-label">Acces courant</span>
              <strong>Invite demo</strong>
              <small>Connecte-toi pour entrer dans le chat.</small>
            </div>
            `
            }
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


function renderSessionControls() {
  if (!session) {
    return "";
  }

  return `
    <div class="session-controls">
      <div class="session-pill">
        <strong>${escapeHtml(session.name)}</strong>
        <small>${escapeHtml(session.role)}</small>
      </div>
      <button type="button" class="button button-inline logout-button" data-logout-button>Deconnexion</button>
    </div>
  `;
}


function renderDemoUserCard(user, index) {
  return `
    <article class="demo-card reveal">
      <span class="feature-tag">Compte ${index + 1}</span>
      <h3>${escapeHtml(user.name)}</h3>
      <p>${escapeHtml(user.description)}</p>
      <div class="demo-meta">
        <span><strong>Email</strong> ${escapeHtml(user.email)}</span>
        <span><strong>Code</strong> <code>${escapeHtml(user.password)}</code></span>
      </div>
      <button
        type="button"
        class="button button-secondary"
        data-demo-login
        data-demo-email="${escapeHtml(user.email)}"
        data-demo-password="${escapeHtml(user.password)}"
      >
        Utiliser ce compte
      </button>
    </article>
  `;
}


function bindUi() {
  const refreshButton = document.querySelector("[data-health-refresh]");
  if (refreshButton) {
    refreshButton.addEventListener("click", updateHealthState);
  }

  const logoutButton = document.querySelector("[data-logout-button]");
  if (logoutButton) {
    logoutButton.addEventListener("click", () => {
      clearSession();
      window.location.assign(buildLoginUrl({ reason: "signed-out" }));
    });
  }

  const loginForm = document.querySelector("[data-login-form]");
  if (loginForm) {
    const reasonMessage = getLoginReasonMessage(loginReason);
    if (reasonMessage) {
      setLoginNotice(reasonMessage.message, reasonMessage.tone);
    } else {
      setLoginNotice(
        "Choisis un compte demo ci-contre ou saisis ses identifiants pour entrer dans l'application.",
        "info"
      );
    }

    loginForm.addEventListener("submit", (event) => {
      event.preventDefault();
      const formData = new FormData(loginForm);
      const result = authenticateDemoUser({
        email: formData.get("email"),
        password: formData.get("password"),
      });

      if (!result.ok) {
        setLoginNotice(result.message, "error");
        return;
      }

      try {
        session = startSession(result.user);
        setLoginNotice(
          `Connexion reussie. Redirection vers ${requestedNextPath}`,
          "success"
        );
        window.setTimeout(() => {
          window.location.assign(
            sanitizeInternalPath(formData.get("next"), "/chat/")
          );
        }, 180);
      } catch (error) {
        setLoginNotice(error.message, "error");
      }
    });
  }

  document.querySelectorAll("[data-demo-login]").forEach((button) => {
    button.addEventListener("click", () => {
      const form = document.querySelector("[data-login-form]");
      if (!form) {
        return;
      }

      const emailInput = form.querySelector('input[name="email"]');
      const passwordInput = form.querySelector('input[name="password"]');
      emailInput.value = button.dataset.demoEmail || "";
      passwordInput.value = button.dataset.demoPassword || "";
      passwordInput.focus();
      setLoginNotice(
        "Compte demo charge. Tu peux entrer directement dans l'espace applicatif.",
        "info"
      );
    });
  });

  const chatForm = document.querySelector("[data-chat-form]");
  if (chatForm) {
    chatForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const feedback = chatForm.querySelector("[data-chat-feedback]");
      feedback.textContent =
        "Le front est deja relie a /health. La prochaine etape sera de brancher ce formulaire a POST /ask.";
      await updateHealthState();
    });
  }
}


function setLoginNotice(message, tone) {
  const noticeNode = document.querySelector("[data-login-notice]");
  if (!noticeNode) {
    return;
  }

  noticeNode.textContent = message;
  noticeNode.className = `notice notice-${tone}`;
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


function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}


function renderBootError(error) {
  const app = document.getElementById("app");
  if (!app) {
    return;
  }

  const message =
    error instanceof Error && error.message
      ? error.message
      : "Erreur inconnue pendant le demarrage de la webapp.";

  app.innerHTML = `
    <div class="page-shell">
      <section class="panel">
        <div class="panel-head">
          <span class="kicker">Boot error</span>
          <h2>La webapp n'a pas demarre correctement.</h2>
        </div>
        <div class="notice notice-error">
          ${escapeHtml(message)}
        </div>
        <p class="panel-subcopy">
          Recharge la page ou verifie la configuration locale du shell front.
        </p>
      </section>
    </div>
  `;
}
