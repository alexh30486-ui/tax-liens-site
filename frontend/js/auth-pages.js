/** Shared logic for signup.html and login.html */
import { login, signup } from "./api.js";

function showError(el, message) {
  if (!el) return;
  el.textContent = message;
  el.classList.add('is-visible');
}

function clearError(el) {
  if (!el) return;
  el.classList.remove('is-visible');
}

function wireAuthForm({ mode }) {
  const form = document.getElementById('authForm');
  if (!form) return;

  const emailInput = document.getElementById('email');
  const passwordInput = document.getElementById('password');
  const emailError = document.getElementById('emailError');
  const passwordError = document.getElementById('passwordError');
  const formError = document.getElementById('formError');
  const submitBtn = document.getElementById('submitBtn');

  emailInput.addEventListener('input', () => clearError(emailError));
  passwordInput.addEventListener('input', () => clearError(passwordError));

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    clearError(emailError);
    clearError(passwordError);
    clearError(formError);

    const email = emailInput.value.trim();
    const password = passwordInput.value;
    let hasError = false;

    if (!email || !email.includes('@')) {
      showError(emailError, 'Enter a valid email address.');
      hasError = true;
    }
    if (mode === 'signup' && password.length < 8) {
      showError(passwordError, 'Password needs to be at least 8 characters.');
      hasError = true;
    }
    if (!password) {
      showError(passwordError, 'Enter your password.');
      hasError = true;
    }
    if (hasError) return;

    submitBtn.disabled = true;
    const original = submitBtn.textContent;
    submitBtn.textContent = mode === 'signup' ? 'Creating account…' : 'Signing in…';

    try {
      if (mode === 'signup') {
        await signup(email, password);
      } else {
        await login(email, password);
      }
      window.location.href = 'app.html';
    } catch (err) {
      if (err.status === 409) {
        showError(formError, 'An account with that email already exists.');
      } else if (err.status === 401) {
        showError(formError, 'Incorrect email or password.');
      } else {
        showError(
          formError,
          err.message || 'Something went wrong. Check that the API is running.'
        );
      }
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = original;
    }
  });
}

document.addEventListener('DOMContentLoaded', () => {
  const mode = document.body.dataset.authMode;
  if (mode) wireAuthForm({ mode });
});
