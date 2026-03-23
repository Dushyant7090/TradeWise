// ===== TRADEWISE AUTH LOGIC =====
// Handles: Google OAuth, Email/Password Sign Up, Login, Forgot Password
// Connected to Supabase Auth + Resend (SMTP)

import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';

// Initialize Supabase client (config values from config.js loaded before this module)
const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

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
(async function checkSession() {
    const { data: { session } } = await supabase.auth.getSession();
    if (session) {
        // User is already logged in, route them appropriately
        await routeUser(session.user.id);
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
async function signInWithGoogle() {
    const { data, error } = await supabase.auth.signInWithOAuth({
        provider: 'google',
        options: {
            redirectTo: window.location.origin + '/pages/role-select.html'
        }
    });

    if (error) {
        showMessage(loginMessage, error.message, 'error');
        showMessage(signupMessage, error.message, 'error');
    }
    // If successful, browser will redirect to Google
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

    const { data, error } = await supabase.auth.signUp({
        email,
        password,
        options: {
            data: {
                full_name: fullName
            },
            emailRedirectTo: window.location.origin + '/pages/role-select.html'
        }
    });

    setLoading(signupSubmit, false);

    if (error) {
        showMessage(signupMessage, error.message, 'error');
        return;
    }

    // Check if email confirmation is required
    if (data.user && data.user.identities && data.user.identities.length === 0) {
        showMessage(signupMessage, 'An account with this email already exists. Try logging in.', 'error');
    } else if (data.session) {
        // Auto-confirmed (if email confirmation is disabled)
        await createProfile(data.user.id, fullName, email);
        window.location.href = 'role-select.html';
    } else {
        // Email confirmation sent
        showMessage(signupMessage, '✓ Check your email! We sent you a confirmation link.', 'success');
        signupForm.reset();
        signupSubmit.classList.remove('ready');
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

    const { data, error } = await supabase.auth.signInWithPassword({
        email,
        password
    });

    setLoading(loginSubmit, false);

    if (error) {
        showMessage(loginMessage, error.message, 'error');
        return;
    }

    // Success — route user based on profile status
    await routeUser(data.user.id);
});

// ===== FORGOT PASSWORD =====
forgotForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearMessages();

    const email = document.getElementById('forgot-email').value.trim();
    const forgotSubmit = document.getElementById('forgot-submit');

    setLoading(forgotSubmit, true);

    const { error } = await supabase.auth.resetPasswordForEmail(email, {
        redirectTo: window.location.origin + '/pages/auth.html'
    });

    setLoading(forgotSubmit, false);

    if (error) {
        showMessage(forgotMessage, error.message, 'error');
        return;
    }

    showMessage(forgotMessage, '✓ Password reset link sent! Check your email.', 'success');
    forgotForm.reset();
});

// ===== CREATE PROFILE IN DB =====
async function createProfile(userId, fullName, email) {
    const { error } = await supabase.from('profiles').upsert({
        id: userId,
        full_name: fullName,
        role: 'public_trader',
        credits: 7
    });

    if (error) {
        console.error('Failed to create profile:', error);
    }
}

// ===== AUTH STATE LISTENER =====
supabase.auth.onAuthStateChange(async (event, session) => {
    if (event === 'SIGNED_IN' && session) {
        // Check if profile exists, create if not
        const { data: profile } = await supabase
            .from('profiles')
            .select('id')
            .eq('id', session.user.id)
            .single();

        if (!profile) {
            const fullName = session.user.user_metadata?.full_name ||
                session.user.user_metadata?.name ||
                session.user.email?.split('@')[0] || 'Trader';
            await createProfile(session.user.id, fullName, session.user.email);
        }

        // Route user based on profile status
        await routeUser(session.user.id);
    }
});

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

// ===== SMART ROUTING =====
async function routeUser(userId) {
    const { data: profile } = await supabase
        .from('profiles')
        .select('role, disclaimer_accepted')
        .eq('id', userId)
        .single();

    if (!profile) {
        // No profile at all — go to role select
        window.location.href = 'role-select.html';
    } else if (profile.role === 'pro_trader') {
        // Pro-traders go to coming soon page (onboarding not built yet)
        if (profile.disclaimer_accepted) {
            window.location.href = 'dashboard.html';
        } else {
            window.location.href = 'pro-trader-coming-soon.html';
        }
    } else if (!profile.disclaimer_accepted) {
        // Public trader — onboarding incomplete
        window.location.href = 'role-select.html';
    } else {
        // Onboarding complete, go to dashboard
        window.location.href = 'dashboard.html';
    }
}
