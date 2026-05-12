const STORAGE_KEY = "multi-rag-demo-session-v1";
const DEFAULT_SESSION_HOURS = 12;
const DEFAULT_DEMO_USERS = [
  {
    email: "invite.juriste@demo.local",
    password: "demo-juriste",
    name: "Invite Juriste",
    role: "Parcours sejour",
    description: "Compte de demonstration pour tester le futur espace de chat juridique.",
  },
  {
    email: "invite.ops@demo.local",
    password: "demo-ops",
    name: "Invite Operations",
    role: "Parcours produit",
    description: "Compte de demonstration pour valider le shell applicatif et la navigation.",
  },
];


function normalizeDemoUser(user, index) {
  return {
    id: user.id || `demo-user-${index + 1}`,
    email: String(user.email || "").trim().toLowerCase(),
    password: String(user.password || "").trim(),
    name: String(user.name || `Invite ${index + 1}`).trim(),
    role: String(user.role || "Invite demo").trim(),
    description: String(user.description || "Compte de demonstration.").trim(),
  };
}


function getRawConfig() {
  return window.__MULTI_RAG_WEBAPP_CONFIG__ || {};
}


export function getSessionDurationHours() {
  const rawValue = Number(getRawConfig().demoSessionHours);
  if (!Number.isFinite(rawValue) || rawValue <= 0) {
    return DEFAULT_SESSION_HOURS;
  }
  return rawValue;
}


export function listDemoUsers() {
  const rawUsers = Array.isArray(getRawConfig().demoUsers)
    ? getRawConfig().demoUsers
    : DEFAULT_DEMO_USERS;

  return rawUsers
    .map((user, index) => normalizeDemoUser(user, index))
    .filter((user) => user.email && user.password);
}


export function sanitizeInternalPath(rawPath, fallbackPath = "/chat/") {
  if (!rawPath || typeof rawPath !== "string") {
    return fallbackPath;
  }

  if (!rawPath.startsWith("/") || rawPath.startsWith("//")) {
    return fallbackPath;
  }

  return rawPath;
}


function readStoredSession() {
  try {
    const rawValue = window.localStorage.getItem(STORAGE_KEY);
    return rawValue ? JSON.parse(rawValue) : null;
  } catch (_error) {
    return null;
  }
}


export function clearSession() {
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch (_error) {
    // Ignore local storage cleanup errors to keep logout idempotent.
  }
}


export function getSession() {
  const session = readStoredSession();
  if (!session) {
    return null;
  }

  if (!session.expiresAt || Date.parse(session.expiresAt) <= Date.now()) {
    clearSession();
    return null;
  }

  return session;
}


export function hasExpiredSession() {
  const session = readStoredSession();
  if (!session) {
    return false;
  }

  return !session.expiresAt || Date.parse(session.expiresAt) <= Date.now();
}


export function createSession(user) {
  const expiresAt = new Date(
    Date.now() + getSessionDurationHours() * 60 * 60 * 1000
  ).toISOString();

  return {
    id: user.id,
    email: user.email,
    name: user.name,
    role: user.role,
    description: user.description,
    loginAt: new Date().toISOString(),
    expiresAt,
  };
}


export function startSession(user) {
  const session = createSession(user);
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
  } catch (_error) {
    throw new Error(
      "Impossible de sauvegarder la session demo sur ce navigateur."
    );
  }
  return session;
}


export function authenticateDemoUser({ email, password }) {
  const normalizedEmail = String(email || "").trim().toLowerCase();
  const normalizedPassword = String(password || "").trim();

  if (!normalizedEmail) {
    return {
      ok: false,
      message: "Renseigne l'adresse email du compte de demonstration.",
    };
  }

  if (!normalizedPassword) {
    return {
      ok: false,
      message: "Renseigne le code d'acces demo.",
    };
  }

  const user = listDemoUsers().find(
    (entry) =>
      entry.email === normalizedEmail && entry.password === normalizedPassword
  );

  if (!user) {
    return {
      ok: false,
      message:
        "Connexion impossible. Verifie l'email et le code d'acces du compte demo.",
    };
  }

  return {
    ok: true,
    user,
  };
}


export function buildLoginUrl({ next = "/chat/", reason = "" } = {}) {
  const url = new URL("/login/", window.location.origin);
  const safeNext = sanitizeInternalPath(next);

  if (safeNext) {
    url.searchParams.set("next", safeNext);
  }
  if (reason) {
    url.searchParams.set("reason", reason);
  }

  return `${url.pathname}${url.search}`;
}


export function getLoginReasonMessage(reason) {
  if (reason === "auth-required") {
    return {
      tone: "info",
      message: "Connecte-toi avec un compte demo pour acceder a l'espace applicatif.",
    };
  }

  if (reason === "session-expired") {
    return {
      tone: "error",
      message: "La session demo a expire. Reconnecte-toi pour continuer.",
    };
  }

  if (reason === "signed-out") {
    return {
      tone: "success",
      message: "Tu as bien ete deconnecte.",
    };
  }

  return null;
}
