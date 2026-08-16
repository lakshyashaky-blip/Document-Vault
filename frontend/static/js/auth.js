let mode = "login"; // or "signup"

const form = document.getElementById("auth-form");
const title = document.getElementById("form-title");
const submitBtn = document.getElementById("submit-btn");
const switchBtn = document.getElementById("switch-btn");
const switchText = document.getElementById("switch-text");
const errorBanner = document.getElementById("error-banner");

function applyMode() {
  if (mode === "signup") {
    title.textContent = "Create your account";
    submitBtn.textContent = "Sign up";
    switchText.textContent = "Already have an account?";
    switchBtn.textContent = "Log in";
  } else {
    title.textContent = "Welcome back";
    submitBtn.textContent = "Log in";
    switchText.textContent = "Need an account?";
    switchBtn.textContent = "Sign up";
  }
}

// Support /index.html?mode=signup so the landing page's "Sign up" button
// can drop the visitor straight into the signup form instead of login.
const initialParams = new URLSearchParams(window.location.search);
if (initialParams.get("mode") === "signup") {
  mode = "signup";
  applyMode();
}

// If already logged in, skip straight to the library
fetch("/api/auth/me", { credentials: "include" })
  .then((r) => (r.ok ? (window.location.href = "/library.html") : null))
  .catch(() => {});

switchBtn.addEventListener("click", () => {
  mode = mode === "login" ? "signup" : "login";
  applyMode();
  errorBanner.classList.remove("show");
});

function showError(msg) {
  errorBanner.textContent = msg;
  errorBanner.classList.add("show");
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  errorBanner.classList.remove("show");

  const email = document.getElementById("email").value.trim();
  const password = document.getElementById("password").value;

  submitBtn.disabled = true;
  submitBtn.textContent = mode === "login" ? "Logging in..." : "Signing up...";

  try {
    const res = await fetch(`/api/auth/${mode}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ email, password }),
    });
    const data = await res.json();

    if (!res.ok) {
      showError(data.error || "Something went wrong");
      return;
    }
    window.location.href = "/library.html";
  } catch (err) {
    showError("Could not reach the server. Please try again.");
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = mode === "login" ? "Log in" : "Sign up";
  }
});
