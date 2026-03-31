// ===== TRADEWISE AUTH LOGIC =====
// Handles: Google OAuth, Email/Password Sign Up, Login, Forgot Password
// Connected to Flask backend API

// ===== API BASE URL =====
const API_BASE = window.TW_API_BASE_URL || 'http://localhost:5000/api';

// ===== DOM ELEMENTS =====
const views = document.querySelectorAll('.auth-view');
const toggleLinks = document.querySelectorAll('.auth-toggle-link');

// Sign Up
const signupForm = document.getElementById('signup-form');
const signupMessage = document.getElementById('signup-message');
const googleSignupBtn = document.getElementById('google-signup-btn');

// Login
const loginForm = document.getElementById('login-form');
const loginMessage = document.getElementById('login-message');
const googleLoginBtn = document.getElementById('google-login-btn');
const forgotPasswordLink = document.getElementById('forgot-password-link');

// Forgot Password
const forgotForm = document.getElementById('forgot-form');
const forgotMessage = document.getElementById('forgot-message');

// Password toggles
const passwordToggles = document.querySelectorAll('.password-toggle');

// Submit buttons (for ready state tracking)
const signupSubmit = document.getElementById('signup-submit');
const loginSubmit = document.getElementById('login-submit');

// ===== CHECK IF ALREADY LOGGED IN =====
// If a session token already exists, forward to role-select which handles
// already-onboarded users by routing them straight to the right dashboard.
(function checkSession() {
    const token = localStorage.getItem('tw_jwt_token');
    if (token) {
        window.location.href = 'role-select.html';
    }
})();

// ===== VIEW TOGGLING =====
toggleLinks.forEach(link => {
    link.addEventListener('click', (e) => {
        e.preventDefault();
        const targetId = link.dataset.target;
        switchView(targetId);
    });
});

// Forgot password link
forgotPasswordLink.addEventListener('click', (e) => {
    e.preventDefault();
    switchView('forgot-view');
});

function switchView(targetId) {
    views.forEach(view => {
        view.classList.remove('active');
    });
    document.getElementById(targetId).classList.add('active');

    // Update page title
    const titles = {
        'signup-view': 'TradeWise — Sign Up',
        'login-view': 'TradeWise — Log In',
        'forgot-view': 'TradeWise — Reset Password'
    };
    document.title = titles[targetId] || 'TradeWise — Auth';

    // Clear messages
    clearMessages();
}

// ===== PASSWORD VISIBILITY TOGGLE =====
passwordToggles.forEach(toggle => {
    toggle.addEventListener('click', () => {
        const inputId = toggle.dataset.target;
        const input = document.getElementById(inputId);
        const eyeIcon = toggle.querySelector('.eye-icon');
        const eyeOffIcon = toggle.querySelector('.eye-off-icon');

        if (input.type === 'password') {
            input.type = 'text';
            eyeIcon.style.display = 'none';
            eyeOffIcon.style.display = 'block';
        } else {
            input.type = 'password';
            eyeIcon.style.display = 'block';
            eyeOffIcon.style.display = 'none';
        }
    });
});

// ===== VALIDATION HELPERS =====
const EMAIL_REGEX = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;

function validateEmail(email) {
    if (!email) return 'Email is required.';
    if (!EMAIL_REGEX.test(email)) return 'Please enter a valid email address.';
    return '';
}

function validatePassword(password) {
    if (!password) return 'Password is required.';
    if (password.length < 8) return 'Password must be at least 8 characters.';
    if (!/[A-Z]/.test(password)) return 'Password needs at least one uppercase letter.';
    if (!/[a-z]/.test(password)) return 'Password needs at least one lowercase letter.';
    if (!/[0-9]/.test(password)) return 'Password needs at least one number.';
    if (!/[!@#$%^&*()_+\-={}\[\]|;:'",.<>?/`~]/.test(password)) return 'Password needs at least one special character.';
    return '';
}

function validateFullName(name) {
    if (!name) return 'Full name is required.';
    if (name.length < 2) return 'Name must be at least 2 characters.';
    return '';
}

function showFieldError(inputId, errorId, message) {
    const input = document.getElementById(inputId);
    const error = document.getElementById(errorId);
    if (message) {
        input.classList.add('input-error');
        input.classList.remove('input-success');
        if (error) error.textContent = message;
    } else {
        input.classList.remove('input-error');
        input.classList.add('input-success');
        if (error) error.textContent = '';
    }
}

function clearFieldState(inputId, errorId) {
    const input = document.getElementById(inputId);
    const error = document.getElementById(errorId);
    input.classList.remove('input-error', 'input-success');
    if (error) error.textContent = '';
}

// ===== PASSWORD STRENGTH METER =====
const signupPasswordInput = document.getElementById('signup-password');
const strengthContainer = document.getElementById('password-strength');
const strengthFill = document.getElementById('strength-fill');
const strengthHint = document.getElementById('strength-hint');

function updatePasswordStrength(password) {
    if (!password) {
        strengthFill.style.width = '0%';
        strengthHint.textContent = 'Need: 8+ chars, uppercase, lowercase, number';
        strengthHint.style.color = '';
        return;
    }

    // Check requirements
    const missing = [];
    if (password.length < 8) missing.push('8+ chars');
    if (!/[A-Z]/.test(password)) missing.push('uppercase');
    if (!/[a-z]/.test(password)) missing.push('lowercase');
    if (!/[0-9]/.test(password)) missing.push('number');
    if (!/[!@#$%^&*()_+\-={}\[\]|;:'",.<>?/`~]/.test(password)) missing.push('special char');

    const total = 5;
    const score = total - missing.length;
    const pct = (score / total) * 100;

    // Colors
    const colorMap = ['#EF4444', '#EF4444', '#F59E0B', '#3B82F6', '#3B82F6', '#10B981'];
    const hintColorMap = ['#FCA5A5', '#FCA5A5', '#FCD34D', '#93C5FD', '#93C5FD', '#6EE7B7'];

    strengthFill.style.width = pct + '%';
    strengthFill.style.background = colorMap[score] || '#EF4444';

    if (missing.length > 0) {
        strengthHint.textContent = 'Need: ' + missing.join(', ');
        strengthHint.style.color = hintColorMap[score] || '#FCA5A5';
    } else {
        strengthHint.textContent = '✓ Strong password';
        strengthHint.style.color = '#6EE7B7';
    }
}

signupPasswordInput.addEventListener('input', () => {
    updatePasswordStrength(signupPasswordInput.value);
    validateStep();
});

signupPasswordInput.addEventListener('focus', () => {
    strengthContainer.classList.add('visible');
    updatePasswordStrength(signupPasswordInput.value);
});

signupPasswordInput.addEventListener('blur', () => {
    strengthContainer.classList.remove('visible');
    const msg = validatePassword(signupPasswordInput.value);
    showFieldError('signup-password', 'signup-password-error', msg);
});

// ===== REAL-TIME VALIDATION ON BLUR =====
document.getElementById('signup-fullname').addEventListener('blur', (e) => {
    const msg = validateFullName(e.target.value.trim());
    showFieldError('signup-fullname', 'signup-fullname-error', msg);
});

document.getElementById('signup-email').addEventListener('blur', (e) => {
    const msg = validateEmail(e.target.value.trim());
    showFieldError('signup-email', 'signup-email-error', msg);
});


// Login field validation on blur
document.getElementById('login-email').addEventListener('blur', (e) => {
    const val = e.target.value.trim();
    if (val && !EMAIL_REGEX.test(val)) {
        e.target.classList.add('input-error');
    } else if (val) {
        e.target.classList.remove('input-error');
        e.target.classList.add('input-success');
    }
});

// ===== INPUT VALIDATION — BUTTON READY STATE =====
function validateStep() {
    const fullName = document.getElementById('signup-fullname').value.trim();
    const email = document.getElementById('signup-email').value.trim();
    const password = signupPasswordInput.value;

    const nameValid = !validateFullName(fullName);
    const emailValid = !validateEmail(email);
    const passValid = !validatePassword(password);

    if (nameValid && emailValid && passValid) {
        signupSubmit.classList.add('ready');
    } else {
        signupSubmit.classList.remove('ready');
    }
}

// Track all signup inputs
['signup-fullname', 'signup-email', 'signup-password'].forEach(id => {
    document.getElementById(id).addEventListener('input', validateStep);
});

// Track login inputs
function trackLoginReady() {
    const email = document.getElementById('login-email').value.trim();
    const password = document.getElementById('login-password').value;
    if (email && password) {
        loginSubmit.classList.add('ready');
    } else {
        loginSubmit.classList.remove('ready');
    }
}

document.getElementById('login-email').addEventListener('input', trackLoginReady);
document.getElementById('login-password').addEventListener('input', trackLoginReady);

// ===== GOOGLE OAUTH =====
function signInWithGoogle() {
    showMessage(loginMessage, 'Google sign-in is not available at the moment. Please use email/password.', 'error');
    showMessage(signupMessage, 'Google sign-up is not available at the moment. Please use email/password.', 'error');
}

googleSignupBtn.addEventListener('click', signInWithGoogle);
googleLoginBtn.addEventListener('click', signInWithGoogle);

// ===== EMAIL/PASSWORD SIGN UP =====
signupForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearMessages();

    const fullName = document.getElementById('signup-fullname').value.trim();
    const email = document.getElementById('signup-email').value.trim();
    const password = document.getElementById('signup-password').value;

    // Validation
    const nameError = validateFullName(fullName);
    if (nameError) {
        showFieldError('signup-fullname', 'signup-fullname-error', nameError);
        return;
    }

    const emailError = validateEmail(email);
    if (emailError) {
        showFieldError('signup-email', 'signup-email-error', emailError);
        return;
    }

    const passError = validatePassword(password);
    if (passError) {
        showFieldError('signup-password', 'signup-password-error', passError);
        return;
    }

    setLoading(signupSubmit, true);

    try {
        const response = await fetch(`${API_BASE}/auth/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            // Sign-up via this page creates public_trader accounts.
            // Pro-trader registration uses a separate onboarding flow.
            body: JSON.stringify({ email, password, display_name: fullName, role: 'public_trader' })
        });

        const data = await response.json();
        setLoading(signupSubmit, false);

        if (!response.ok) {
            showMessage(signupMessage, data.error || 'Registration failed. Please try again.', 'error');
            return;
        }

        // Store tokens
        _storeSession(data);
        // Redirect to role selection — new users choose their role there
        window.location.href = 'role-select.html';
    } catch {
        setLoading(signupSubmit, false);
        showMessage(signupMessage, 'Network error. Please check your connection.', 'error');
    }
});

// ===== EMAIL/PASSWORD LOGIN =====
loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearMessages();

    const email = document.getElementById('login-email').value.trim();
    const password = document.getElementById('login-password').value;

    // Validate email format
    if (!email) {
        showMessage(loginMessage, 'Please enter your email address.', 'error');
        return;
    }
    if (!EMAIL_REGEX.test(email)) {
        showMessage(loginMessage, 'Please enter a valid email address.', 'error');
        return;
    }
    if (!password) {
        showMessage(loginMessage, 'Please enter your password.', 'error');
        return;
    }

    setLoading(loginSubmit, true);

    try {
        const response = await fetch(`${API_BASE}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });

        const data = await response.json();
        setLoading(loginSubmit, false);

        if (!response.ok) {
            showMessage(loginMessage, data.error || 'Login failed. Please try again.', 'error');
            return;
        }

        // Store tokens and route via role selection
        _storeSession(data);
        window.location.href = 'role-select.html';
    } catch {
        setLoading(loginSubmit, false);
        showMessage(loginMessage, 'Network error. Please check your connection.', 'error');
    }
});

// ===== FORGOT PASSWORD =====
forgotForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearMessages();

    const email = document.getElementById('forgot-email').value.trim();
    const forgotSubmit = document.getElementById('forgot-submit');

    if (!email || !EMAIL_REGEX.test(email)) {
        showMessage(forgotMessage, 'Please enter a valid email address.', 'error');
        return;
    }

    setLoading(forgotSubmit, true);

    try {
        const response = await fetch(`${API_BASE}/auth/forgot-password`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email })
        });

        setLoading(forgotSubmit, false);

        // Always show success to prevent email enumeration
        showMessage(forgotMessage, '✓ If that email is registered, a password reset link has been sent.', 'success');
        forgotForm.reset();
    } catch {
        setLoading(forgotSubmit, false);
        showMessage(forgotMessage, '✓ If that email is registered, a password reset link has been sent.', 'success');
        forgotForm.reset();
    }
});

// ===== SESSION STORAGE HELPER =====
function _storeSession(data) {
    if (data.access_token) localStorage.setItem('tw_jwt_token', data.access_token);
    if (data.refresh_token) localStorage.setItem('tw_refresh_token', data.refresh_token);
    if (data.user) localStorage.setItem('tw_user_data', JSON.stringify(data.user));
    if (data.profile) localStorage.setItem('tw_profile', JSON.stringify(data.profile));
}

// ===== UTILITIES =====
function showMessage(element, message, type) {
    element.textContent = message;
    element.className = `auth-message ${type}`;
}

function clearMessages() {
    [signupMessage, loginMessage, forgotMessage].forEach(el => {
        el.textContent = '';
        el.className = 'auth-message';
    });
}

function setLoading(button, isLoading) {
    const btnText = button.querySelector('.btn-text');
    const btnLoader = button.querySelector('.btn-loader');
    if (isLoading) {
        btnText.style.display = 'none';
        btnLoader.style.display = 'flex';
        button.disabled = true;
        button.style.opacity = '0.7';
    } else {
        btnText.style.display = 'inline';
        btnLoader.style.display = 'none';
        button.disabled = false;
        button.style.opacity = '1';
    }
}
