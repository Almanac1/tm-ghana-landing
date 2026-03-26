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
const heroVideoUrl = 'https://www.youtube.com/embed/7ysWTw9Y0TM?autoplay=1&rel=0';

if (watchVideoBtn && heroVideoModal && closeHeroVideoBtn && heroVideoFrame) {
  let lastFocusedElement = null;

  const setHeroVideoOpenState = (isOpen) => {
    heroVideoModal.classList.toggle('is-open', isOpen);
    heroVideoModal.setAttribute('aria-hidden', String(!isOpen));
    document.body.classList.toggle('hero-video-open', isOpen);

    if (isOpen) {
      heroVideoFrame.src = heroVideoUrl;
      window.setTimeout(() => closeHeroVideoBtn.focus(), 0);
    } else {
      heroVideoFrame.src = '';
      lastFocusedElement?.focus?.();
    }
  };

  watchVideoBtn.addEventListener('click', () => {
    lastFocusedElement = document.activeElement;
    setHeroVideoOpenState(true);
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
const reservationDateLabelMap = {
  physical: {
    nov5: 'Wednesday, November 5',
    nov12: 'Wednesday, November 12',
    nov19: 'Wednesday, November 19',
    nov25: 'Wednesday, November 25'
  },
  online: {
    nov5: 'Saturday, November 5',
    nov12: 'Saturday, November 15',
    nov19: 'Saturday, November 22',
    nov25: 'Saturday, November 29'
  }
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

const applyReservationSessionMode = (value) => {
  if (!reservationToggleInputs.length || !value) return;
  const matchedInput = Array.from(reservationToggleInputs).find(input => input.value === value);
  if (!matchedInput) return;
  matchedInput.checked = true;
  if (reservationSessionType) {
    reservationSessionType.value = value;
  }
  if (reservationDateOptions) {
    const labelsByDate = reservationDateLabelMap[value] || reservationDateLabelMap.physical;
    reservationDateOptions.querySelectorAll('.radio-option').forEach(option => {
      const input = option.querySelector('input[type="radio"]');
      const label = option.querySelector('span');
      if (!input || !label) return;
      label.textContent = labelsByDate[input.value] || label.textContent;
    });
  }
  syncReservationPills();
};

reservationToggleInputs.forEach(input => {
  input.addEventListener('change', () => {
    syncReservationPills();
    if (reservationSessionType) {
      reservationSessionType.value = input.value;
    }
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
  applyReservationSessionMode(reservationSessionType.value);
}

if (reservationFormCard && reservationLockShell) {
  const leadComplete = reservationFormCard.dataset.leadComplete === 'true';
  setReservationLockedState(!leadComplete);
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
const faqItems = document.querySelectorAll('.faq-item');
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
});

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
