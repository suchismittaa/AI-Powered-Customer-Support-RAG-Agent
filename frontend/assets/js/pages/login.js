import { api, setSession } from "../api.js";
import { escapeHtml, toast } from "../ui.js";

export function renderLogin(root, onSuccess) {
  let tab = "signin";

  function paint() {
    root.innerHTML = `
      <div class="login-screen">
        <div class="login-left">
          <div class="brand">
            <div class="sidebar-brand" style="padding:0">
              <div class="mark">S</div>
              <div class="name" style="font-size:15px">SUPPORTAI</div>
            </div>
          </div>
          <h1>AI support, grounded in your knowledge.</h1>
          <p class="lede">Resolve routine customer questions instantly, surface the evidence behind every answer, and escalate complex issues to humans when necessary.</p>
          <div class="feature-line">
            <div class="feature-chip"><span class="tick">●</span> RAG-powered</div>
            <div class="feature-chip"><span class="tick">●</span> Human escalation</div>
            <div class="feature-chip"><span class="tick">●</span> Support analytics</div>
          </div>
          <div class="status-pill" style="width:fit-content">
            <span class="dot ok"></span> AI ENGINE OPERATIONAL
          </div>
        </div>
        <div class="login-right">
          <div class="auth-card">
            <h2>${tab === "signin" ? "Welcome back" : "Create your workspace account"}</h2>
            <p class="sub">${tab === "signin" ? "Sign in to your workspace" : "Set up agent access in seconds"}</p>
            <div class="auth-tabs">
              <div class="auth-tab ${tab === "signin" ? "active" : ""}" data-tab="signin">Sign In</div>
              <div class="auth-tab ${tab === "signup" ? "active" : ""}" data-tab="signup">Create Account</div>
            </div>
            <div id="auth-error"></div>
            <div id="auth-form"></div>
          </div>
        </div>
      </div>
    `;

    root.querySelectorAll(".auth-tab").forEach(t => t.addEventListener("click", () => {
      tab = t.dataset.tab;
      paint();
    }));

    if (tab === "signin") paintSignIn(); else paintSignUp();
  }

  function paintSignIn() {
    const form = root.querySelector("#auth-form");
    form.innerHTML = `
      <div class="field"><label>Email</label><input class="input" id="li-email" type="email" placeholder="you@company.com" /></div>
      <div class="field"><label>Password</label><input class="input" id="li-pw" type="password" placeholder="••••••••" /></div>
      <button class="btn btn-primary btn-block" id="li-submit">Continue →</button>
      <p class="auth-hint">Demo: <code>admin@demo.com</code> / <code>Admin@1234</code></p>
    `;
    const submit = async () => {
      const email = root.querySelector("#li-email").value.trim();
      const password = root.querySelector("#li-pw").value;
      const btn = root.querySelector("#li-submit");
      const errBox = root.querySelector("#auth-error");
      errBox.innerHTML = "";
      if (!email || !password) {
        errBox.innerHTML = `<div class="auth-error">Enter your email and password to continue.</div>`;
        return;
      }
      btn.disabled = true; btn.textContent = "Signing in…";
      try {
        const session = await api.login(email, password);
        setSession(session);
        onSuccess();
      } catch (e) {
        errBox.innerHTML = `<div class="auth-error">${escapeHtml(e.message)}</div>`;
        btn.disabled = false; btn.textContent = "Continue →";
      }
    };
    root.querySelector("#li-submit").addEventListener("click", submit);
    form.querySelectorAll("input").forEach(i => i.addEventListener("keydown", e => { if (e.key === "Enter") submit(); }));
  }

  function paintSignUp() {
    const form = root.querySelector("#auth-form");
    form.innerHTML = `
      <div class="field"><label>Full name</label><input class="input" id="su-name" placeholder="Jordan Rivera" /></div>
      <div class="field"><label>Email</label><input class="input" id="su-email" type="email" placeholder="you@company.com" /></div>
      <div class="field"><label>Organization ID</label><input class="input" id="su-org" placeholder="acme-corp" /></div>
      <div class="field"><label>Password (min 8 characters)</label><input class="input" id="su-pw" type="password" placeholder="••••••••" /></div>
      <button class="btn btn-primary btn-block" id="su-submit">Create Account</button>
    `;
    root.querySelector("#su-submit").addEventListener("click", async () => {
      const name = root.querySelector("#su-name").value.trim();
      const email = root.querySelector("#su-email").value.trim();
      const org_id = root.querySelector("#su-org").value.trim() || "default";
      const password = root.querySelector("#su-pw").value;
      const errBox = root.querySelector("#auth-error");
      errBox.innerHTML = "";
      if (!name || !email || !password) {
        errBox.innerHTML = `<div class="auth-error">Please fill in all fields.</div>`;
        return;
      }
      const btn = root.querySelector("#su-submit");
      btn.disabled = true; btn.textContent = "Creating…";
      try {
        await api.register({ name, email, password, org_id, role: "agent" });
        toast("Account created — sign in to continue.");
        tab = "signin";
        paint();
      } catch (e) {
        errBox.innerHTML = `<div class="auth-error">${escapeHtml(e.message)}</div>`;
        btn.disabled = false; btn.textContent = "Create Account";
      }
    });
  }

  paint();
}
