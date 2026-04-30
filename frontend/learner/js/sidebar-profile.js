/**
 * Shared learner sidebar profile hydration.
 * Renders cached learner data immediately, then refreshes from the API.
 */

import Auth from './auth.js';
import Storage from './storage.js';
import { learnerProfileAPI } from './api.js?v=api-host-3';
import { getInitials } from './utils.js';

function pickProfileName(profile, user) {
  return profile?.display_name || profile?.full_name || user?.email?.split('@')[0] || 'Learner';
}

function pickAvatarUrl(profile) {
  return profile?.avatar_url || profile?.profile_image || profile?.profile_picture_url || '';
}

function renderSidebarProfile(profile = {}, user = Auth.getCurrentUser() || {}) {
  const name = pickProfileName(profile, user);
  const nameEl = document.getElementById('sidebar-username');
  const avatarEl = document.getElementById('sidebar-avatar');

  if (nameEl) nameEl.textContent = name;
  if (!avatarEl) return;

  const avatarUrl = pickAvatarUrl(profile);
  const initials = getInitials(name);
  avatarEl.textContent = initials;

  if (avatarUrl) {
    avatarEl.innerHTML = `<img src="${avatarUrl}" alt="${name}" style="width:100%;height:100%;border-radius:50%;object-fit:cover;" onerror="this.onerror=null; this.parentElement.textContent='${initials}';">`;
  }
}

export async function initLearnerSidebarProfile() {
  const user = Auth.getCurrentUser() || {};
  const cachedProfile = Auth.getLearnerProfile() || {};
  renderSidebarProfile(cachedProfile, user);

  try {
    const freshProfile = await learnerProfileAPI.getProfile();
    if (freshProfile && typeof freshProfile === 'object') {
      Storage.setLearnerProfile(freshProfile);
      renderSidebarProfile(freshProfile, user);
    }
  } catch {
    // Keep cached/initials fallback; sidebar should never block page rendering.
  }
}

export default initLearnerSidebarProfile;
