import { fetchHealth, getWebAppConfig } from "./api.js";


const pageId = document.body.dataset.page || "home";
const config = getWebAppConfig();
const workspaceDocuments = getWorkspaceDocuments();

const WORKSPACE_STATUS_META = {
  active: {
    label: "Actif",
    className: "status-active",
    description: "Document disponible dans l'espace de travail.",
  },
  queued: {
    label: "Pret a ingerer",
    className: "status-queued",
    description: "Document connu mais ingestion encore a lancer.",
  },
  review: {
    label: "A verifier",
    className: "status-review",
    description: "Un point de source ou de configuration reste a confirmer.",
  },
  refresh: {
    label: "A rafraichir",
    className: "status-refresh",
    description: "Le document existe mais une mise a jour de contenu est attendue.",
  },
};

const INDEXING_STATUS_META = {
  indexed: {
    label: "Indexe",
    className: "status-indexed",
    description: "La recherche pourra consommer ce document sans ambiguite.",
    actionLabel: "Reindexation bientot",
  },
  pending: {
    label: "En attente",
    className: "status-pending",
    description: "L'indexation n'a pas encore demarre ou n'est pas terminee.",
    actionLabel: "Indexation bientot",
  },
  blocked: {
    label: "Bloque",
    className: "status-blocked",
    description: "Une action preparatoire est necessaire avant indexation.",
    actionLabel: "Verification bientot",
  },
  stale: {
    label: "A reindexer",
    className: "status-stale",
    description: "Le document est present mais une reindexation sera utile.",
    actionLabel: "Reindexation bientot",
  },
};

const pageContent = {
  home: {
    eyebrow: "Hosted webapp shell",
    title: "Un front propre pour parler a l'API, sans passer par l'UI locale.",
    body:
      "Cette base pose un shell webapp separe, des routes pretes pour login, documents, docs et chat, et un branchement HTTP direct vers l'API FastAPI.",
    primaryCta: { label: "Voir la bibliotheque", href: "/documents/" },
    secondaryCta: { label: "Ouvrir le chat", href: "/chat/" },
    panels: renderHomePanels,
  },
  login: {
    eyebrow: "Route login",
    title: "Une porte d'entree sobre pour l'auth utilisateur.",
    body:
      "La page reste volontairement simple: elle garde la place pour l'identite, les roles et la future gestion de session sans bloquer le reste du front.",
    primaryCta: { label: "Voir les documents", href: "/documents/" },
    secondaryCta: { label: "Voir les docs", href: "/docs/" },
    panels: renderLoginPanels,
  },
  documents: {
    eyebrow: "Workspace library",
    title: "Une vue claire des documents disponibles dans l'espace de travail.",
    body:
      "La bibliotheque montre sans ambiguite le nom, le type, la date connue, le statut workspace et l'etat d'indexation de chaque document, tout en reservant la place pour la reindexation plus tard.",
    primaryCta: { label: "Voir le chat", href: "/chat/" },
    secondaryCta: { label: "Voir les docs API", href: "/docs/" },
    panels: renderDocumentsPanels,
  },
  docs: {
    eyebrow: "Route docs",
    title: "Une page front qui rend le contrat backend lisible sans ouvrir le code.",
    body:
      "La webapp expose les points d'entree utiles, l'etat de l'API et un lien direct vers Swagger pour garder l'integration front-back simple.",
    primaryCta: { label: "Ouvrir Swagger", href: config.docsUrl, external: true },
    secondaryCta: { label: "Voir les documents", href: "/documents/" },
    panels: renderApiPanels,
  },
  chat: {
    eyebrow: "Route chat",
    title: "Une disposition deja calibree pour la conversation, les citations et les sources.",
    body:
      "Le shell anticipe les trois blocs qui compteront vraiment: saisie question, reponse structuree, et panneau lateral pour les pieces justificatives.",
    primaryCta: { label: "Verifier l'API", href: "#api-status" },
    secondaryCta: { label: "Voir les documents", href: "/documents/" },
    panels: renderChatPanels,
  },
};


renderApp();
bindUi();
updateHealthState();


function renderApp() {
  const page = pageContent[pageId] || pageContent.home;
  const app = document.getElementById("app");
  const panels =
    typeof page.panels === "function" ? page.panels() : page.panels;

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
          ${renderNavLink("/documents/", "documents", "Documents")}
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
            <div class="meta-card">
              <span class="meta-label">Documents connus</span>
              <strong>${workspaceDocuments.length}</strong>
              <small>${countIndexedDocuments()} deja interrogeables dans l'etat courant.</small>
            </div>
            <div class="meta-card" id="api-status">
              <span class="meta-label">Etat backend</span>
              <strong data-health-state>Verification...</strong>
              <small data-health-detail>Connexion a /health en cours.</small>
            </div>
          </aside>
        </section>

        ${panels}

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


function renderHomePanels() {
  return `
    <section class="panel panel-glow">
      <div class="panel-head">
        <span class="kicker">Routes pretes</span>
        <h2>Un shell deja decoupe par usages.</h2>
      </div>
      <div class="feature-grid">
        <article class="feature-card reveal">
          <span class="feature-tag">Documents</span>
          <h3>Bibliotheque workspace</h3>
          <p>Une route dediee liste deja les documents, leurs statuts et leur etat d'indexation.</p>
        </article>
        <article class="feature-card reveal">
          <span class="feature-tag">Login</span>
          <h3>Entree utilisateur</h3>
          <p>Le shell garde la place pour le parcours de connexion sans ralentir la suite du front.</p>
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
  `;
}


function renderLoginPanels() {
  return `
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
  `;
}


function renderDocumentsPanels() {
  return `
    <section class="panel">
      <div class="panel-head">
        <span class="kicker">Workspace overview</span>
        <h2>Les documents sont visibles et leur etat reste explicite.</h2>
      </div>
      <div class="library-summary">
        <article class="summary-card reveal">
          <span class="status-label">Documents</span>
          <strong>${workspaceDocuments.length}</strong>
          <p>elements connus dans l'espace de travail actuel.</p>
        </article>
        <article class="summary-card reveal">
          <span class="status-label">Indexes prets</span>
          <strong>${countIndexedDocuments()}</strong>
          <p>documents deja interrogeables depuis le moteur de retrieval.</p>
        </article>
        <article class="summary-card reveal">
          <span class="status-label">Actions a venir</span>
          <strong>${countDocumentsNeedingAttention()}</strong>
          <p>documents qui demandent ingestion, verification ou future reindexation.</p>
        </article>
      </div>
    </section>

    <section class="panel" id="document-list">
      <div class="panel-head">
        <span class="kicker">Library view</span>
        <h2>Bibliotheque des documents du workspace.</h2>
      </div>
      <div class="documents-grid">
        ${workspaceDocuments.map(renderDocumentCard).join("")}
      </div>
    </section>

    <section class="panel panel-glow">
      <div class="panel-head">
        <span class="kicker">Future action</span>
        <h2>Le terrain est pret pour la reindexation.</h2>
      </div>
      <div class="reindex-banner">
        <p>
          La vue montre deja quels documents sont indexes, en attente, bloques ou a reindexer.
          La prochaine etape naturelle sera de brancher ici l'action de reindexation et le suivi de job.
        </p>
        <button type="button" class="button button-inline button-disabled" disabled>
          Reindexation bientot
        </button>
      </div>
      <div class="legend-grid">
        ${renderLegendCard("Actif", WORKSPACE_STATUS_META.active.description, "status-active")}
        ${renderLegendCard("Pret a ingerer", WORKSPACE_STATUS_META.queued.description, "status-queued")}
        ${renderLegendCard("A verifier", WORKSPACE_STATUS_META.review.description, "status-review")}
        ${renderLegendCard("A reindexer", INDEXING_STATUS_META.stale.description, "status-stale")}
      </div>
    </section>
  `;
}


function renderApiPanels() {
  return `
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
  `;
}


function renderChatPanels() {
  return `
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
  `;
}


function renderDocumentCard(document) {
  const workspaceMeta = getWorkspaceStatusMeta(document.workspaceStatus);
  const indexingMeta = getIndexingStatusMeta(document.indexingStatus);

  return `
    <article class="document-card reveal">
      <div class="document-card-head">
        <div>
          <span class="feature-tag">${escapeHtml(document.documentType)}</span>
          <h3>${escapeHtml(document.name)}</h3>
        </div>
        <div class="document-status-stack">
          ${renderStatusPill(workspaceMeta)}
          ${renderStatusPill(indexingMeta)}
        </div>
      </div>

      <p class="document-note">${escapeHtml(document.notes)}</p>

      <div class="document-meta-grid">
        ${renderMetaItem("Nom technique", document.id)}
        ${renderMetaItem("Type source", document.fileType)}
        ${renderMetaItem("Date connue", formatDateLabel(document.lastUpdatedAt))}
        ${renderMetaItem("Collection", document.collection)}
        ${renderMetaItem("Domaine", document.domain)}
        ${renderMetaItem("Indexation", indexingMeta.label)}
      </div>

      <div class="document-footer">
        <p class="form-note">
          ${escapeHtml(workspaceMeta.description)} ${escapeHtml(indexingMeta.description)}
        </p>
        <button type="button" class="button button-inline button-disabled" disabled>
          ${escapeHtml(indexingMeta.actionLabel)}
        </button>
      </div>
    </article>
  `;
}


function renderLegendCard(title, body, statusClass) {
  return `
    <article class="legend-card">
      <div class="legend-head">
        <span class="status-pill ${statusClass}">${escapeHtml(title)}</span>
      </div>
      <p>${escapeHtml(body)}</p>
    </article>
  `;
}


function renderStatusPill(meta) {
  return `<span class="status-pill ${meta.className}">${escapeHtml(meta.label)}</span>`;
}


function renderMetaItem(label, value) {
  return `
    <div class="meta-item">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
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
        "Le front est deja relie a /health. La prochaine etape sera de brancher ce formulaire a POST /ask.";
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


function getWorkspaceDocuments() {
  if (Array.isArray(config.workspaceDocuments) && config.workspaceDocuments.length > 0) {
    return config.workspaceDocuments.map(normalizeDocument);
  }

  return [
    normalizeDocument({
      id: "ceseda",
      name: "Code de l'entree et du sejour des etrangers et du droit d'asile (CESEDA)",
      documentType: "Code legislatif",
      fileType: "PDF distant",
      lastUpdatedAt: "2026-05-04",
      workspaceStatus: "active",
      indexingStatus: "indexed",
      domain: "droit_etranger",
      collection: "droit_etranger",
      notes: "Source officielle active et deja exploitable dans le workspace.",
    }),
  ];
}


function normalizeDocument(document) {
  return {
    id: String(document.id || "document").trim(),
    name: String(document.name || "Document sans nom").trim(),
    documentType: String(document.documentType || "Document").trim(),
    fileType: String(document.fileType || "Source").trim(),
    lastUpdatedAt: String(document.lastUpdatedAt || "Date inconnue").trim(),
    workspaceStatus: String(document.workspaceStatus || "review").trim(),
    indexingStatus: String(document.indexingStatus || "pending").trim(),
    domain: String(document.domain || "non_defini").trim(),
    collection: String(document.collection || "non_definie").trim(),
    notes: String(document.notes || "Aucun commentaire disponible.").trim(),
  };
}


function getWorkspaceStatusMeta(status) {
  return WORKSPACE_STATUS_META[status] || WORKSPACE_STATUS_META.review;
}


function getIndexingStatusMeta(status) {
  return INDEXING_STATUS_META[status] || INDEXING_STATUS_META.pending;
}


function countIndexedDocuments() {
  return workspaceDocuments.filter(
    (document) => document.indexingStatus === "indexed"
  ).length;
}


function countDocumentsNeedingAttention() {
  return workspaceDocuments.filter((document) => {
    return (
      document.workspaceStatus !== "active" ||
      document.indexingStatus !== "indexed"
    );
  }).length;
}


function formatDateLabel(value) {
  return value;
}


function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
