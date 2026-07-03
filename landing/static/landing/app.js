window.dataLayer = window.dataLayer || [];

function pushDataLayerEvent(eventName, params = {}) {
  window.dataLayer.push({
    event: eventName,
    ...params
  });
}

const getSectionName = (element) => {
  const section = element?.closest?.('section');
  if (section?.id) return section.id;
  if (element?.closest?.('.header')) return 'navigation';
  if (element?.closest?.('.footer')) return 'footer';
  return 'unknown';
};

const getReservationAnalyticsState = () => ({
  selected_class_type: document.getElementById('reservation-session-type')?.value || undefined,
  selected_session_date: document.getElementById('reservationDateOptions')?.dataset.selectedDate || undefined
});

const getSessionStorageItem = (key) => {
  try {
    return window.sessionStorage?.getItem(key);
  } catch (error) {
    return null;
  }
};

const setSessionStorageItem = (key, value) => {
  try {
    window.sessionStorage?.setItem(key, value);
  } catch (error) {
    // Analytics dedupe should never block the site if storage is unavailable.
  }
};

const observeElementOnce = (element, threshold, callback) => {
  if (!element) return;

  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver((entries, observerInstance) => {
      entries.forEach(entry => {
        if (entry.isIntersecting && entry.intersectionRatio >= threshold) {
          callback();
          observerInstance.disconnect();
        }
      });
    }, { threshold: [threshold] });

    observer.observe(element);
    return;
  }

  callback();
};

// Mobile Menu Toggle
const header = document.querySelector('.header');
const mobileMenuBtn = document.getElementById('mobileMenuBtn');
const mobileNav = document.getElementById('mobileNav');
const logoImage = document.querySelector('.logo-image');
const defaultLogo = logoImage?.dataset.defaultLogo || logoImage?.getAttribute('src') || '';
const hoverLogo = logoImage?.dataset.hoverLogo || '';
let scrollResetTimer = null;
let hoverLogoAvailable = Boolean(hoverLogo);
let isNavbarHovered = false;
let isScrolling = false;

if (hoverLogo) {
  const hoverLogoProbe = new Image();
  hoverLogoProbe.onload = () => {
    hoverLogoAvailable = true;
  };
  hoverLogoProbe.onerror = () => {
    hoverLogoAvailable = false;
    if (logoImage?.getAttribute('src') === hoverLogo) {
      logoImage.setAttribute('src', defaultLogo);
    }
  };
  hoverLogoProbe.src = hoverLogo;
}

const setNavbarHighlighted = (isHighlighted) => {
  if (!header) return;
  header.classList.toggle('navbar-highlighted', isHighlighted);
};

const isAwayFromTop = () => window.scrollY > 4;

const updateNavbarState = () => {
  if (!header) return;
  const shouldHighlight =
    isNavbarHovered ||
    isScrolling ||
    isAwayFromTop() ||
    header.classList.contains('menu-open');

  setNavbarHighlighted(shouldHighlight);
  syncLogoState();
};

const syncLogoState = () => {
  if (!logoImage) return;
  const shouldUseHoverLogo =
    header?.classList.contains('navbar-highlighted') ||
    header?.classList.contains('menu-open');
  logoImage.setAttribute('src', shouldUseHoverLogo && hoverLogoAvailable ? hoverLogo : defaultLogo);
};

const scheduleScrollStopCheck = () => {
  if (!header) return;
  if (scrollResetTimer) {
    window.clearTimeout(scrollResetTimer);
  }

  scrollResetTimer = window.setTimeout(() => {
    isScrolling = false;
    updateNavbarState();
  }, 200);
};

if (header && logoImage) {
  header.addEventListener('mouseenter', () => {
    isNavbarHovered = true;
    updateNavbarState();
  });

  header.addEventListener('mouseleave', () => {
    isNavbarHovered = false;
    updateNavbarState();
  });

  header.addEventListener('focusin', () => {
    isNavbarHovered = true;
    updateNavbarState();
  });

  header.addEventListener('focusout', () => {
    isNavbarHovered = header.matches(':hover');
    updateNavbarState();
  });

  updateNavbarState();
}

if (mobileMenuBtn) {
  mobileMenuBtn.addEventListener('click', () => {
    mobileMenuBtn.classList.toggle('active');
    mobileNav.classList.toggle('active');
    mobileMenuBtn.setAttribute('aria-expanded', String(mobileNav.classList.contains('active')));
    header?.classList.toggle('menu-open', mobileNav.classList.contains('active'));
    updateNavbarState();
  });

  // Close menu when clicking on a link
  const mobileLinks = mobileNav.querySelectorAll('a');
  mobileLinks.forEach(link => {
    link.addEventListener('click', () => {
      mobileMenuBtn.classList.remove('active');
      mobileNav.classList.remove('active');
      mobileMenuBtn.setAttribute('aria-expanded', 'false');
      header?.classList.remove('menu-open');
      updateNavbarState();
    });
  });
}

if (header) {
  const syncHeaderState = () => {
    header.classList.toggle('is-scrolled', window.scrollY > 24);
    isScrolling = true;
    updateNavbarState();
    scheduleScrollStopCheck();
  };

  window.addEventListener('scroll', syncHeaderState, { passive: true });
  updateNavbarState();
}

// Hero video modal
const watchVideoBtn = document.getElementById('watchVideoBtn');
const heroVideoModal = document.getElementById('heroVideoModal');
const closeHeroVideoBtn = document.getElementById('closeHeroVideo');
const heroVideoFrame = document.getElementById('heroVideoFrame');
const heroVideoFallback = document.getElementById('heroVideoFallback');
const heroVideoUrl = watchVideoBtn?.dataset.videoUrl || 'https://www.youtube.com/embed/AL_c-sV9zXc?enablejsapi=1';

if (heroVideoModal && closeHeroVideoBtn && heroVideoFrame) {
  let lastFocusedElement = null;
  let activeFallbackUrl = 'https://www.youtube.com/watch?v=AL_c-sV9zXc';
  let activeVideoAnalytics = null;
  let activeYouTubePlayer = null;
  let videoProgressTimer = null;
  let videoPlayerSession = 0;

  if (heroVideoModal.parentElement !== document.body) {
    document.body.appendChild(heroVideoModal);
  }

  const loadYouTubeIframeApi = () => {
    if (window.YT?.Player) {
      return Promise.resolve(window.YT);
    }

    if (window.tmYouTubeIframeApiPromise) {
      return window.tmYouTubeIframeApiPromise;
    }

    window.tmYouTubeIframeApiPromise = new Promise((resolve, reject) => {
      const previousCallback = window.onYouTubeIframeAPIReady;
      const timeoutId = window.setTimeout(() => {
        reject(new Error('YouTube IFrame API timed out'));
      }, 10000);

      window.onYouTubeIframeAPIReady = () => {
        window.clearTimeout(timeoutId);
        try {
          previousCallback?.();
        } finally {
          resolve(window.YT);
        }
      };

      const existingScript = document.querySelector('script[src="https://www.youtube.com/iframe_api"]');
      if (!existingScript) {
        const script = document.createElement('script');
        script.src = 'https://www.youtube.com/iframe_api';
        script.async = true;
        script.addEventListener('error', () => {
          window.clearTimeout(timeoutId);
          reject(new Error('YouTube IFrame API failed to load'));
        }, { once: true });
        document.head.appendChild(script);
      } else {
        existingScript.addEventListener('error', () => {
          window.clearTimeout(timeoutId);
          reject(new Error('YouTube IFrame API failed to load'));
        }, { once: true });
      }
    });

    return window.tmYouTubeIframeApiPromise;
  };

  const getYouTubeVideoId = (videoUrl) => {
    try {
      const url = new URL(videoUrl, window.location.href);
      if (url.hostname.includes('youtu.be')) {
        return url.pathname.split('/').filter(Boolean)[0] || '';
      }
      if (url.pathname.startsWith('/embed/')) {
        return url.pathname.split('/').filter(Boolean)[1] || '';
      }
      return url.searchParams.get('v') || '';
    } catch (error) {
      return '';
    }
  };

  const buildYouTubeEmbedUrl = (videoUrl) => {
    const videoId = getYouTubeVideoId(videoUrl);
    const params = new URLSearchParams({
      autoplay: '1',
      rel: '0',
      enablejsapi: '1',
      modestbranding: '1',
      playsinline: '1',
      origin: window.location.origin,
      widget_referrer: window.location.href
    });

    try {
      const url = new URL(videoUrl, window.location.href);
      url.searchParams.forEach((value, key) => {
        params.set(key, value);
      });
    } catch (error) {
      // Fall back to the required YouTube embed format below.
    }

    params.set('enablejsapi', '1');
    return `https://www.youtube.com/embed/${videoId || 'AL_c-sV9zXc'}?${params.toString()}`;
  };

  const buildYouTubeWatchUrl = (videoUrl) => {
    const videoId = getYouTubeVideoId(videoUrl) || 'AL_c-sV9zXc';
    return `https://www.youtube.com/watch?v=${encodeURIComponent(videoId)}`;
  };

  const setVideoFallbackState = (isVisible, fallbackUrl = buildYouTubeWatchUrl(heroVideoUrl)) => {
    if (!heroVideoFallback) return;
    heroVideoFallback.href = fallbackUrl;
    heroVideoFallback.hidden = !isVisible;
  };

  const resetVideoAnalytics = () => {
    videoPlayerSession += 1;

    if (videoProgressTimer) {
      window.clearInterval(videoProgressTimer);
      videoProgressTimer = null;
    }

    activeVideoAnalytics = null;
    activeYouTubePlayer = null;
  };

  const getVideoPlaybackParams = () => {
    if (!activeYouTubePlayer) return {};

    const duration = Number(activeYouTubePlayer.getDuration?.() || 0);
    const currentTime = Number(activeYouTubePlayer.getCurrentTime?.() || 0);
    const watchedSeconds = Number(activeVideoAnalytics?.watchedSeconds || 0);

    return {
      video_duration: duration ? Math.round(duration) : undefined,
      video_current_time: currentTime ? Math.round(currentTime) : 0,
      video_watched_seconds: Math.round(watchedSeconds),
      video_percent: duration
        ? Math.min(100, Math.floor((currentTime / duration) * 100))
        : undefined,
      video_watch_percent: duration
        ? Math.min(100, Math.floor((watchedSeconds / duration) * 100))
        : undefined
    };
  };

  const buildVideoAnalyticsParams = (params = {}) => {
    if (!activeVideoAnalytics) return params;

    return {
      video_provider: 'youtube',
      video_id: activeVideoAnalytics.video_id,
      video_url: activeVideoAnalytics.video_url,
      video_type: activeVideoAnalytics.video_type,
      testimonial_name: activeVideoAnalytics.testimonial_name || undefined,
      video_title: activeVideoAnalytics.video_title || undefined,
      ...getVideoPlaybackParams(),
      ...params
    };
  };

  const getVideoEventName = (action) => {
    if (!activeVideoAnalytics?.video_type) return '';
    return `${activeVideoAnalytics.video_type}_video_${action}`;
  };

  const pushVideoEvent = (action, params = {}) => {
    const eventName = getVideoEventName(action);
    if (!eventName) return;

    pushDataLayerEvent(eventName, buildVideoAnalyticsParams(params));
  };

  const pushVideoComplete = () => {
    if (!activeVideoAnalytics || activeVideoAnalytics.completed) return;
    activeVideoAnalytics.completed = true;
    pushVideoEvent('complete', {
      video_percent: 100
    });
  };

  const trackVideoProgress = () => {
    if (!activeYouTubePlayer || !activeVideoAnalytics) return;

    const duration = Number(activeYouTubePlayer.getDuration?.() || 0);
    if (!duration) return;

    const now = performance.now();
    if (activeVideoAnalytics.isPlaying && activeVideoAnalytics.lastProgressTimestamp) {
      const elapsedSeconds = Math.min(
        2,
        Math.max(0, (now - activeVideoAnalytics.lastProgressTimestamp) / 1000)
      );
      activeVideoAnalytics.watchedSeconds = Math.min(
        duration,
        activeVideoAnalytics.watchedSeconds + elapsedSeconds
      );
    }
    activeVideoAnalytics.lastProgressTimestamp = now;

    const watchedPercent = Math.floor((activeVideoAnalytics.watchedSeconds / duration) * 100);
    [25, 50, 75, 90].forEach(percent => {
      if (watchedPercent >= percent && !activeVideoAnalytics.progressFired.has(percent)) {
        activeVideoAnalytics.progressFired.add(percent);
        pushVideoEvent('progress', {
          video_percent: percent
        });
      }
    });
  };

  const initializeVideoPlayer = () => {
    if (!activeVideoAnalytics) return;
    const playerSession = videoPlayerSession;

    loadYouTubeIframeApi().then(YT => {
      if (
        playerSession !== videoPlayerSession ||
        !activeVideoAnalytics ||
        !heroVideoFrame.src
      ) return;

      activeYouTubePlayer = new YT.Player(heroVideoFrame, {
        events: {
          onStateChange: event => {
            if (event.data === YT.PlayerState.PLAYING) {
              if (!activeVideoAnalytics.isPlaying) {
                activeVideoAnalytics.isPlaying = true;
                activeVideoAnalytics.lastProgressTimestamp = performance.now();
              }

              if (!activeVideoAnalytics.started) {
                activeVideoAnalytics.started = true;
                pushVideoEvent('start');
              }

              if (!videoProgressTimer) {
                videoProgressTimer = window.setInterval(trackVideoProgress, 1000);
              }
            }

            if (event.data === YT.PlayerState.PAUSED && activeVideoAnalytics.started) {
              trackVideoProgress();
              activeVideoAnalytics.isPlaying = false;
              pushVideoEvent('pause');
            }

            if (event.data === YT.PlayerState.BUFFERING) {
              trackVideoProgress();
              activeVideoAnalytics.isPlaying = false;
            }

            if (event.data === YT.PlayerState.ENDED) {
              trackVideoProgress();
              activeVideoAnalytics.isPlaying = false;
              pushVideoComplete();
            }
          },
          onError: event => {
            pushVideoEvent('error', {
              video_error_code: event.data
            });
            setVideoFallbackState(true, activeFallbackUrl);
          }
        }
      });
    }).catch(error => {
      if (playerSession !== videoPlayerSession || !activeVideoAnalytics) return;
      pushVideoEvent('error', {
        video_error_message: error.message
      });
      setVideoFallbackState(true, activeFallbackUrl);
    });
  };

  const setHeroVideoOpenState = (isOpen, videoUrl = heroVideoUrl, analytics = null) => {
    heroVideoModal.classList.toggle('is-open', isOpen);
    heroVideoModal.setAttribute('aria-hidden', String(!isOpen));
    document.body.classList.toggle('hero-video-open', isOpen);

    if (isOpen) {
      resetVideoAnalytics();
      const embedUrl = buildYouTubeEmbedUrl(videoUrl);
      const fallbackUrl = buildYouTubeWatchUrl(embedUrl);
      const videoId = getYouTubeVideoId(embedUrl);
      activeFallbackUrl = fallbackUrl;
      setVideoFallbackState(false, fallbackUrl);
      heroVideoFrame.src = embedUrl;
      activeVideoAnalytics = analytics
        ? {
            ...analytics,
            video_id: videoId,
            video_url: fallbackUrl,
            started: false,
            completed: false,
            progressFired: new Set(),
            watchedSeconds: 0,
            lastProgressTimestamp: null,
            isPlaying: false
          }
        : null;
      pushVideoEvent('open', {
        section: activeVideoAnalytics?.section || undefined
      });
      initializeVideoPlayer();
      window.setTimeout(() => closeHeroVideoBtn.focus(), 0);
    } else {
      resetVideoAnalytics();
      heroVideoFrame.src = '';
      setVideoFallbackState(false);
      lastFocusedElement?.focus?.();
    }
  };

  heroVideoFrame.addEventListener('error', () => {
    setVideoFallbackState(true, activeFallbackUrl);
  });

  if (watchVideoBtn) {
    watchVideoBtn.addEventListener('click', (event) => {
      event.preventDefault();
      lastFocusedElement = document.activeElement;
      setHeroVideoOpenState(true, watchVideoBtn.dataset.videoUrl || heroVideoUrl, {
        video_type: 'hero',
        video_title: heroVideoFrame.title || watchVideoBtn.textContent?.trim() || undefined,
        section: 'hero'
      });
    });
  }

  document.querySelectorAll('.testimonial-card[data-video-url]').forEach(card => {
    const openTestimonialVideo = () => {
      lastFocusedElement = document.activeElement;
      const videoUrl = card.dataset.videoUrl || heroVideoUrl;
      setHeroVideoOpenState(true, videoUrl, {
        video_type: 'testimonial',
        testimonial_name: card.dataset.testimonialName || card.querySelector('img')?.alt || undefined,
        video_title: card.dataset.videoTitle || card.getAttribute('aria-label') || undefined,
        section: 'testimonials'
      });
    };

    card.addEventListener('click', (event) => {
      event.preventDefault();
      openTestimonialVideo();
    });
    card.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        openTestimonialVideo();
      }
    });
  });

  closeHeroVideoBtn.addEventListener('click', () => {
    setHeroVideoOpenState(false);
  });

  heroVideoModal.addEventListener('click', (event) => {
    if (event.target instanceof HTMLElement && event.target.dataset.videoClose === 'true') {
      setHeroVideoOpenState(false);
    }
  });

  window.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && heroVideoModal.classList.contains('is-open')) {
      setHeroVideoOpenState(false);
    }
  });
}

// Session Toggle
const toggleBtns = document.querySelectorAll('.toggle-btn');
const reservationToggleInputs = document.querySelectorAll('.reservation-session-control input[type="radio"]');
const reservationTogglePills = document.querySelectorAll('.reservation-session-control .toggle-pill');
const reservationSessionType = document.getElementById('reservation-session-type');
const reservationFormCard = document.getElementById('reservationForm');
const reservationMeasuredHeight = document.getElementById('reservationMeasuredHeight');
const reservationLockShell = document.getElementById('reservationLockShell');
const reservationSessionControl = document.getElementById('reservationSessionControl');
const reservationDateOptions = document.getElementById('reservationDateOptions');
const reservationSubmitBtn = document.getElementById('reservationSubmitBtn');
const reservationUnlockNote = document.getElementById('reservationUnlockNote');
let reservationFormStarted = false;
const getReservationDateOptionsByMode = () => {
  const script = document.getElementById('reservationDateOptionsData');
  if (!script?.textContent) return null;

  try {
    const parsedOptions = JSON.parse(script.textContent);
    if (parsedOptions && typeof parsedOptions === 'object') {
      return parsedOptions;
    }
  } catch (error) {
    return null;
  }

  return null;
};
const reservationDateOptionsByMode = getReservationDateOptionsByMode() || {
  physical: [
    { value: '2026-07-04', label: 'Saturday, July 4' },
    { value: '2026-07-11', label: 'Saturday, July 11' },
    { value: '2026-07-18', label: 'Saturday, July 18' },
    { value: '2026-07-25', label: 'Saturday, July 25' }
  ],
  online: [
    { value: '2026-07-01', label: 'Wednesday, July 1' },
    { value: '2026-07-08', label: 'Wednesday, July 8' },
    { value: '2026-07-15', label: 'Wednesday, July 15' },
    { value: '2026-07-22', label: 'Wednesday, July 22' },
    { value: '2026-07-29', label: 'Wednesday, July 29' }
  ]
};
const reservationInteractiveControls = reservationFormCard
  ? Array.from(
      reservationFormCard.querySelectorAll(
        'input:not([type="hidden"]), select, textarea, button[type="submit"]'
      )
    )
  : [];

const setReservationLockedState = (isLocked) => {
  if (!reservationFormCard || !reservationLockShell) return;

  reservationFormCard.classList.toggle('is-locked', isLocked);
  reservationFormCard.setAttribute('aria-disabled', String(isLocked));
  reservationLockShell.classList.toggle('is-locked', isLocked);
  reservationLockShell.disabled = isLocked;

  if (isLocked) {
    reservationLockShell.setAttribute('aria-describedby', 'reservationGateNote');
  } else {
    reservationLockShell.removeAttribute('aria-describedby');
  }

  if (reservationSessionControl) {
    reservationSessionControl.classList.toggle('is-locked', isLocked);
    reservationSessionControl.setAttribute('aria-disabled', String(isLocked));
  }

  if (reservationDateOptions) {
    reservationDateOptions.classList.toggle('is-locked', isLocked);
    reservationDateOptions.setAttribute('aria-disabled', String(isLocked));
    reservationDateOptions.querySelectorAll('.radio-option').forEach(option => {
      option.classList.toggle('is-disabled', isLocked);
    });
    reservationDateOptions.querySelectorAll('input[type="radio"]').forEach(input => {
      input.disabled = isLocked;
    });
  }

  reservationInteractiveControls.forEach(control => {
    if (!(control instanceof HTMLInputElement || control instanceof HTMLSelectElement || control instanceof HTMLTextAreaElement || control instanceof HTMLButtonElement)) {
      return;
    }

    control.disabled = isLocked;

    if (control instanceof HTMLButtonElement) {
      control.setAttribute('aria-disabled', String(isLocked));
    }
  });

  if (reservationUnlockNote) {
    reservationUnlockNote.classList.toggle('is-visible', isLocked);
  }
};

const syncReservationPills = () => {
  document.querySelectorAll('.reservation-session-control .toggle-pill').forEach(pill => {
    pill.classList.toggle('active', pill.querySelector('input')?.checked);
  });
};

const renderReservationDateOptions = (sessionMode, clearSelection = false) => {
  if (reservationDateOptions) {
    const normalizedMode = sessionMode === 'online' ? 'online' : 'physical';
    const options = reservationDateOptionsByMode[normalizedMode] || reservationDateOptionsByMode.physical;
    const fieldName = reservationDateOptions.dataset.dateFieldName || 'reservation-session_date';
    const isLocked = reservationLockShell?.disabled ?? false;
    const selectedDate = clearSelection ? '' : (reservationDateOptions.dataset.selectedDate || '');
    reservationDateOptions.dataset.sessionMode = normalizedMode;

    reservationDateOptions.innerHTML = '';
    options.forEach((option, index) => {
      const optionId = `reservation-session-date-${normalizedMode}-${index}`;

      const label = document.createElement('label');
      label.className = `radio-option${isLocked ? ' is-disabled' : ''}`;

      const input = document.createElement('input');
      input.type = 'radio';
      input.name = fieldName;
      input.value = option.value;
      input.id = optionId;
      input.checked = selectedDate === option.value;
      input.disabled = isLocked;

      const text = document.createElement('span');
      text.textContent = option.label;

      label.appendChild(input);
      label.appendChild(text);
      reservationDateOptions.appendChild(label);
    });

    if (clearSelection) {
      reservationDateOptions.dataset.selectedDate = '';
    }
  }
};

const applyReservationSessionMode = (value, clearSelection = false) => {
  if (!reservationToggleInputs.length || !value) return;
  const matchedInput = Array.from(reservationToggleInputs).find(input => input.value === value);
  if (!matchedInput) return;
  matchedInput.checked = true;
  if (reservationSessionType) {
    reservationSessionType.value = value;
  }
  renderReservationDateOptions(value, clearSelection);
  syncReservationPills();
};

if (reservationDateOptions) {
  reservationDateOptions.addEventListener('change', (event) => {
    const target = event.target;
    if (!(target instanceof HTMLInputElement) || target.type !== 'radio') return;
    reservationDateOptions.dataset.selectedDate = target.value;
    pushDataLayerEvent('date_selection', {
      selected_session_date: target.value,
      selected_class_type: reservationSessionType?.value || reservationDateOptions.dataset.sessionMode || undefined
    });
  });
}

reservationToggleInputs.forEach(input => {
  input.addEventListener('change', () => {
    applyReservationSessionMode(input.value, true);
  });
});

reservationTogglePills.forEach(pill => {
  pill.addEventListener('click', () => {
    const input = pill.querySelector('input');
    if (!input) return;
    input.checked = true;
    input.dispatchEvent(new Event('change', { bubbles: true }));
  });
});

if (reservationSessionType && !reservationSessionType.value) {
  reservationSessionType.value = 'physical';
}

if (reservationSessionType && reservationToggleInputs.length) {
  const activeMode = reservationDateOptions?.dataset.sessionMode || reservationSessionType.value;
  applyReservationSessionMode(activeMode, false);
} else if (reservationDateOptions) {
  renderReservationDateOptions('physical', false);
}

if (reservationFormCard && reservationLockShell) {
  const leadComplete = reservationFormCard.dataset.leadComplete === 'true';
  setReservationLockedState(!leadComplete);
}

observeElementOnce(reservationFormCard, 0.5, () => {
  pushDataLayerEvent('reserve_form_visible', {
    section: 'reserve_form'
  });
});

if (reservationFormCard) {
  const pushFormStartEvent = (event) => {
    if (reservationFormStarted) return;
    const target = event.target;
    if (!(target instanceof HTMLInputElement || target instanceof HTMLSelectElement || target instanceof HTMLTextAreaElement || target instanceof HTMLButtonElement)) {
      return;
    }
    if (target.disabled || target.type === 'hidden' || target.type === 'submit') {
      return;
    }

    reservationFormStarted = true;
    pushDataLayerEvent('form_start', {
      form_name: 'reserve_your_spot',
      ...getReservationAnalyticsState()
    });
  };

  reservationFormCard.addEventListener('focusin', pushFormStartEvent);
  reservationFormCard.addEventListener('change', pushFormStartEvent);
  reservationFormCard.addEventListener('input', pushFormStartEvent);
}

if (reservationFormCard?.dataset.analyticsSuccess === 'true') {
  const submissionId = reservationFormCard.dataset.analyticsSubmissionId || [
    reservationFormCard.dataset.analyticsSessionType,
    reservationFormCard.dataset.analyticsSessionDate
  ].filter(Boolean).join(':');
  const storageKey = `tmnigeria_form_submit_${submissionId}`;

  if (submissionId && getSessionStorageItem(storageKey) !== 'true') {
    pushDataLayerEvent('form_submit', {
      form_name: 'reserve_your_spot',
      selected_class_type: reservationFormCard.dataset.analyticsSessionType || undefined,
      selected_session_date: reservationFormCard.dataset.analyticsSessionDate || undefined
    });
    setSessionStorageItem(storageKey, 'true');
  }
}

if (reservationFormCard && reservationMeasuredHeight) {
  reservationFormCard.addEventListener('submit', (event) => {
    const submitter = event.submitter;
    if (submitter instanceof HTMLButtonElement && submitter.name === 'ui_action') {
      return;
    }

    reservationMeasuredHeight.value = String(Math.ceil(reservationFormCard.getBoundingClientRect().height));
  });
}

// Lead Form Country Code Sync
const leadCountry = document.getElementById('lead-country');
const leadPhone = document.getElementById('lead-phone');
const phonePrefix = document.getElementById('phonePrefix');
const callingCodes = {
  GH: '+233',
  NG: '+234'
};

const syncPhonePrefix = () => {
  if (!leadCountry || !phonePrefix) return;
  phonePrefix.textContent = callingCodes[leadCountry.value] || '+233';
};

if (leadCountry && leadPhone && phonePrefix) {
  leadCountry.addEventListener('change', syncPhonePrefix);

  leadPhone.addEventListener('input', () => {
    leadPhone.value = leadPhone.value.replace(/\D/g, '');
  });

  syncPhonePrefix();
}

document.addEventListener('click', (event) => {
  const cta = event.target instanceof Element
    ? event.target.closest('a, button')
    : null;
  if (!cta) return;

  const buttonText = (cta.textContent || '').replace(/\s+/g, ' ').trim();
  if (!/(reserve|learn tm|free intro|book)/i.test(buttonText)) return;

  const destination = cta instanceof HTMLAnchorElement
    ? cta.getAttribute('href') || ''
    : cta.dataset.videoUrl || cta.getAttribute('formaction') || cta.closest('form')?.getAttribute('action') || window.location.pathname;

  pushDataLayerEvent('reserve_cta_click', {
    button_text: buttonText,
    section: getSectionName(cta),
    destination
  });
});

document.addEventListener('click', (event) => {
  const link = event.target instanceof Element
    ? event.target.closest('a[href]')
    : null;
  if (!(link instanceof HTMLAnchorElement)) return;

  const href = link.getAttribute('href') || '';
  if (!href || href.startsWith('#') || href.startsWith('mailto:') || href.startsWith('tel:')) return;

  const linkUrl = new URL(href, window.location.href);
  if (link.classList.contains('social-link')) {
    pushDataLayerEvent('social_click', {
      social_network: link.dataset.socialNetwork || link.getAttribute('aria-label')?.replace(/^Visit\s+/i, '').replace(/\s+profile$/i, '').toLowerCase() || undefined,
      link_url: linkUrl.href
    });
    return;
  }

  const isOutbound = linkUrl.hostname && !/(^|\.)tmnigeria\.com$/i.test(linkUrl.hostname);
  if (!isOutbound) return;

  pushDataLayerEvent('outbound_click', {
    link_url: linkUrl.href,
    link_text: (link.textContent || '').replace(/\s+/g, ' ').trim() || link.getAttribute('aria-label') || undefined
  });
});

const scrollDepthThresholds = [25, 50, 75, 90];
const firedScrollDepths = new Set();

const handleScrollDepth = () => {
  const scrollableHeight = document.documentElement.scrollHeight - window.innerHeight;
  if (scrollableHeight <= 0) return;

  const currentDepth = Math.min(100, Math.round((window.scrollY / scrollableHeight) * 100));
  scrollDepthThresholds.forEach(depth => {
    if (currentDepth >= depth && !firedScrollDepths.has(depth)) {
      firedScrollDepths.add(depth);
      pushDataLayerEvent('scroll_depth', {
        scroll_depth: depth
      });
    }
  });

  if (firedScrollDepths.size === scrollDepthThresholds.length) {
    window.removeEventListener('scroll', handleScrollDepth);
  }
};

window.addEventListener('scroll', handleScrollDepth, { passive: true });
handleScrollDepth();

// Smooth scroll for navigation links
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
  anchor.addEventListener('click', function (e) {
    const href = this.getAttribute('href');
    if (href !== '#' && document.querySelector(href)) {
      e.preventDefault();
      const target = document.querySelector(href);
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  });
});

// FAQ Accordion Enhancement
const faqSection = document.querySelector('.faq-section');
const faqItems = document.querySelectorAll('.faq-item');

observeElementOnce(faqSection, 0.5, () => {
  pushDataLayerEvent('faq_section_view', {
    section: 'faq'
  });
});

faqItems.forEach(item => {
  const summary = item.querySelector('.faq-question');
  summary.addEventListener('click', () => {
    // Close other open FAQs
    faqItems.forEach(otherItem => {
      if (otherItem !== item && otherItem.hasAttribute('open')) {
        otherItem.removeAttribute('open');
      }
    });
  });

  item.addEventListener('toggle', () => {
    if (!item.open) return;
    const questionText = (summary?.textContent || '').replace(/\+/g, '').replace(/\s+/g, ' ').trim();
    pushDataLayerEvent('faq_open', {
      question_text: questionText
    });
  });
});

const instructorSection = document.querySelector('.instructor-section');
const instructorName = instructorSection?.dataset.instructorName || undefined;

observeElementOnce(instructorSection, 0.5, () => {
  pushDataLayerEvent('bio_view', {
    section: 'bio',
    instructor_name: instructorName
  });
});

if (instructorSection) {
  instructorSection.addEventListener('click', (event) => {
    if (event.target instanceof Element && event.target.closest('.social-link')) return;
    pushDataLayerEvent('bio_click', {
      instructor_name: instructorName,
      section: 'bio'
    });
  });
}

// Testimonials Carousel Controls
const testimonialsCarousel = document.getElementById('testimonialsCarousel');
const prevTestimonialsBtn = document.querySelector('.carousel-control-prev');
const nextTestimonialsBtn = document.querySelector('.carousel-control-next');
const testimonialsDots = document.getElementById('testimonialsDots');

if (testimonialsCarousel && prevTestimonialsBtn && nextTestimonialsBtn) {
  const testimonialCards = Array.from(testimonialsCarousel.querySelectorAll('.testimonial-card'));

  const getScrollAmount = () => {
    const firstCard = testimonialsCarousel.querySelector('.testimonial-card');
    if (!firstCard) return 0;

    const carouselStyles = window.getComputedStyle(testimonialsCarousel);
    const cardGap = parseFloat(carouselStyles.columnGap || carouselStyles.gap || 0);
    return firstCard.getBoundingClientRect().width + cardGap;
  };

  const getActiveIndex = () => {
    const scrollAmount = getScrollAmount();
    if (!scrollAmount) return 0;
    return Math.round(testimonialsCarousel.scrollLeft / scrollAmount);
  };

  const setActiveDot = () => {
    if (!testimonialsDots) return;
    const activeIndex = getActiveIndex();
    testimonialsDots.querySelectorAll('.carousel-dot').forEach((dot, index) => {
      dot.classList.toggle('is-active', index === activeIndex);
      dot.setAttribute('aria-current', index === activeIndex ? 'true' : 'false');
    });
  };

  if (testimonialsDots && testimonialCards.length) {
    testimonialsDots.innerHTML = testimonialCards.map((_, index) =>
      `<button type="button" class="carousel-dot${index === 0 ? ' is-active' : ''}" data-index="${index}" aria-label="Go to testimonial ${index + 1}" aria-current="${index === 0 ? 'true' : 'false'}"></button>`
    ).join('');

    testimonialsDots.querySelectorAll('.carousel-dot').forEach(dot => {
      dot.addEventListener('click', () => {
        const index = Number(dot.dataset.index || 0);
        testimonialsCarousel.scrollTo({
          left: getScrollAmount() * index,
          behavior: 'smooth'
        });
      });
    });
  }

  prevTestimonialsBtn.addEventListener('click', () => {
    testimonialsCarousel.scrollBy({
      left: -getScrollAmount(),
      behavior: 'smooth'
    });
  });

  nextTestimonialsBtn.addEventListener('click', () => {
    testimonialsCarousel.scrollBy({
      left: getScrollAmount(),
      behavior: 'smooth'
    });
  });

  testimonialsCarousel.addEventListener('scroll', setActiveDot, { passive: true });
  window.addEventListener('resize', setActiveDot);
  setActiveDot();
}

// Add animation on scroll
const observerOptions = {
  threshold: 0.1,
  rootMargin: '0px 0px -50px 0px'
};

const observer = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      entry.target.style.opacity = '1';
      entry.target.style.transform = 'translateY(0)';
    }
  });
}, observerOptions);

// Observe elements for animation
document.querySelectorAll('.form-card, .benefit-item, .testimonial-card').forEach(el => {
  el.style.opacity = '0';
  el.style.transform = 'translateY(20px)';
  el.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
  observer.observe(el);
});
