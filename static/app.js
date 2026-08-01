// ===== Minimal app.js — HTMX handles most interactions =====

const searchInput = document.getElementById('search-input');
const ownerInput = document.getElementById('owner-input');
const suggestions = document.getElementById('suggestions');
const ownerSuggestions = document.getElementById('owner-suggestions');
const districtSelect = document.getElementById('sel-district');
const talukSelect = document.getElementById('sel-taluk');
const talukWrap = document.getElementById('taluk-wrap');

const debounce = (fn, delay = 200) => {
    let timer;
    return (...args) => {
        clearTimeout(timer);
        timer = setTimeout(() => fn(...args), delay);
    };
};

// ===== Near me: browser geolocation -> htmx.ajax =====
const nearMeBtn = document.getElementById('near-me-btn');
const resultsSection = document.getElementById('results');
const emptyState = document.getElementById('empty-state');

function getPosition(options) {
    return new Promise((resolve, reject) => {
        navigator.geolocation.getCurrentPosition(resolve, reject, options);
    });
}

async function getPositionWithFallback() {
    try {
        return await getPosition({ enableHighAccuracy: true, timeout: 12000, maximumAge: 0 });
    } catch (err) {
        if (err.code === err.PERMISSION_DENIED) throw err;
        return getPosition({ enableHighAccuracy: false, timeout: 20000, maximumAge: 300000 });
    }
}

function locationErrorText(err) {
    if (err?.code === err?.PERMISSION_DENIED) {
        return ['ലൊക്കേഷൻ അനുമതി നിഷേധിച്ചു', 'ബ്രൗസർ/ഫോൺ സെറ്റിംഗ്സിൽ ലൊക്കേഷൻ അനുമതി നൽകണം.'];
    }
    if (err?.code === err?.POSITION_UNAVAILABLE) {
        return ['ലൊക്കേഷൻ കണ്ടെത്താൻ കഴിഞ്ഞില്ല', 'GPS അല്ലെങ്കിൽ നെറ്റ്‌വർക്ക് ലൊക്കേഷൻ ഇപ്പോൾ ലഭ്യമല്ല.'];
    }
    if (err?.code === err?.TIMEOUT) {
        return ['ലൊക്കേഷൻ കണ്ടെത്താൻ കൂടുതൽ സമയം എടുക്കുന്നു', 'വീണ്ടും ശ്രമിക്കുക, അല്ലെങ്കിൽ സ്ഥലപ്പേര് ഉപയോഗിച്ച് തിരയുക.'];
    }
    return ['ലൊക്കേഷൻ ലഭ്യമല്ല', 'വീണ്ടും ശ്രമിക്കുക, അല്ലെങ്കിൽ സ്ഥലപ്പേര് ഉപയോഗിച്ച് തിരയുക.'];
}

function showNearMeError(title, detail = '') {
    emptyState.classList.add('hidden');
    resultsSection.innerHTML = `
        <div class="text-center py-10 bg-white rounded-2xl shadow-sm border border-gray-100">
            <p class="font-semibold text-red-600 malayalam">${title}</p>
            ${detail ? `<p class="mt-1 text-sm text-gray-500 malayalam">${detail}</p>` : ''}
        </div>`;
    resultsSection.classList.remove('hidden');
}

nearMeBtn?.addEventListener('click', async () => {
    if (!navigator.geolocation) {
        showNearMeError('ലൊക്കേഷൻ ലഭ്യമല്ല', 'ഈ ബ്രൗസറിൽ ലൊക്കേഷൻ പിന്തുണയില്ല.');
        return;
    }
    if (!window.isSecureContext) {
        showNearMeError('ലൊക്കേഷൻ ലഭ്യമല്ല', 'ലൊക്കേഷൻ ഉപയോഗിക്കാൻ HTTPS ആവശ്യമാണ്.');
        return;
    }

    const label = nearMeBtn.innerHTML;
    nearMeBtn.disabled = true;
    nearMeBtn.innerHTML = 'ലൊക്കേഷൻ കണ്ടെത്തുന്നു...';
    emptyState.classList.add('hidden');
    resultsSection.innerHTML = '<div class="text-center py-16"><div class="inline-block w-8 h-8 border-[3px] border-kerala-green/20 border-t-kerala-green rounded-full animate-spin"></div></div>';
    resultsSection.classList.remove('hidden');

    try {
        const pos = await getPositionWithFallback();
        const { latitude, longitude } = pos.coords;

        // Use htmx.ajax to fetch and swap the results
        htmx.ajax('GET', `/htmx/nearby?lat=${latitude}&lon=${longitude}`, {
            target: '#results',
            swap: 'innerHTML'
        });
    } catch (err) {
        const [title, detail] = locationErrorText(err);
        showNearMeError(title, detail);
    } finally {
        nearMeBtn.innerHTML = label;
        nearMeBtn.disabled = false;
    }
});


// ===== Search autocomplete =====
async function loadSuggestions(input, target, endpoint) {
    const q = input.value.trim();
    if (q.length < 2) {
        target.innerHTML = '';
        target.classList.add('hidden');
        input.setAttribute('aria-expanded', 'false');
        input.removeAttribute('aria-activedescendant');
        return;
    }

    let response;
    try {
        response = await fetch(`${endpoint}?q=${encodeURIComponent(q)}`, {
            headers: {'HX-Request': 'true'}
        });
    } catch {
        return; // network blip — keep the last suggestions rather than flashing an error
    }
    if (!response.ok) return;

    target.innerHTML = await response.text();
    target.classList.remove('hidden');
    input.setAttribute('aria-expanded', 'true');
    input.removeAttribute('aria-activedescendant');
}

// ===== Keyboard navigation for autocomplete (a11y) =====
function wireKeyboardNav(input, target) {
    if (!input || !target) return;
    input.addEventListener('keydown', (e) => {
        const options = Array.from(target.querySelectorAll('[role="option"]'));
        if (!options.length || target.classList.contains('hidden')) {
            if (e.key === 'Escape') target.classList.add('hidden');
            return;
        }
        let active = options.findIndex((o) => o.getAttribute('aria-selected') === 'true');

        const setActive = (idx) => {
            options.forEach((o) => o.setAttribute('aria-selected', 'false'));
            options.forEach((o) => o.classList.remove('bg-gray-50'));
            if (idx >= 0 && idx < options.length) {
                const opt = options[idx];
                opt.setAttribute('aria-selected', 'true');
                opt.classList.add('bg-gray-50');
                opt.scrollIntoView({block: 'nearest'});
                input.setAttribute('aria-activedescendant', opt.id);
            }
        };

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            setActive((active + 1) % options.length);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            setActive((active - 1 + options.length) % options.length);
        } else if (e.key === 'Enter' && active >= 0) {
            e.preventDefault();
            options[active].click();
        } else if (e.key === 'Escape') {
            target.classList.add('hidden');
            input.setAttribute('aria-expanded', 'false');
            input.removeAttribute('aria-activedescendant');
        }
    });
}

searchInput?.addEventListener('input', debounce(() => {
    loadSuggestions(searchInput, suggestions, '/htmx/autocomplete');
}));

ownerInput?.addEventListener('input', debounce(() => {
    loadSuggestions(ownerInput, ownerSuggestions, '/htmx/owners');
}));

wireKeyboardNav(searchInput, suggestions);
wireKeyboardNav(ownerInput, ownerSuggestions);

document.addEventListener('click', async (e) => {
    const button = e.target.closest(
        '#suggestions button[data-select-url], #owner-suggestions button[data-select-url]'
    );
    if (!button) return;

    e.preventDefault();
    const url = button.dataset.selectUrl;
    let response;
    try {
        response = await fetch(url, {headers: {'HX-Request': 'true'}});
    } catch {
        showNearMeError('ഡാറ്റ ലോഡ് ചെയ്യാൻ കഴിഞ്ഞില്ല', 'നെറ്റ്‌വർക്ക് പരിശോധിച്ച് വീണ്ടും ശ്രമിക്കുക.');
        return;
    }
    if (!response.ok) {
        showNearMeError('ഡാറ്റ ലോഡ് ചെയ്യാൻ കഴിഞ്ഞില്ല', 'വീണ്ടും ശ്രമിക്കുക.');
        return;
    }

    resultsSection.innerHTML = await response.text();
    resultsSection.classList.remove('hidden');
    emptyState.classList.add('hidden');
    suggestions?.classList.add('hidden');
    ownerSuggestions?.classList.add('hidden');

    const params = new URLSearchParams(url.split('?')[1] || '');
    const type = params.get('type');
    const id = params.get('id');
    if ((type === 'shop' || type === 'place') && id) {
        history.replaceState(null, '', `?${type}=${encodeURIComponent(id)}`);
    }
});


// ===== Browse: District -> Taluk -> Shops =====
function showResultsLoading(message) {
    emptyState.classList.add('hidden');
    resultsSection.classList.remove('hidden');
    resultsSection.innerHTML = `
        <div class="text-center py-16">
            <div class="inline-block w-8 h-8 border-[3px] border-kerala-green/20 border-t-kerala-green rounded-full animate-spin"></div>
            <p class="mt-4 text-sm text-gray-500 malayalam">${message}</p>
        </div>`;
}

async function loadDistricts() {
    if (!districtSelect) return;
    const response = await fetch('/htmx/districts', {headers: {'HX-Request': 'true'}});
    if (!response.ok) return;
    districtSelect.insertAdjacentHTML('beforeend', await response.text());
}

districtSelect?.addEventListener('change', async () => {
    resultsSection.classList.add('hidden');
    resultsSection.innerHTML = '';
    talukSelect.innerHTML = '<option value="">— താലൂക്ക് —</option>';

    if (!districtSelect.value) {
        talukWrap.classList.add('hidden');
        return;
    }

    talukWrap.classList.remove('hidden');
    const url = `/htmx/taluks?district=${encodeURIComponent(districtSelect.value)}`;
    const response = await fetch(url, {headers: {'HX-Request': 'true'}});
    if (!response.ok) return;
    talukSelect.insertAdjacentHTML('beforeend', await response.text());
});

talukSelect?.addEventListener('change', async () => {
    if (!talukSelect.value) {
        resultsSection.classList.add('hidden');
        resultsSection.innerHTML = '';
        return;
    }

    showResultsLoading('കടകൾ ലോഡ് ചെയ്യുന്നു...');
    const params = new URLSearchParams({
        tso_code: talukSelect.value,
        district: districtSelect.value
    });
    let response;
    try {
        response = await fetch(`/htmx/shops?${params}`, {headers: {'HX-Request': 'true'}});
    } catch {
        showNearMeError('കടകൾ ലോഡ് ചെയ്യാൻ കഴിഞ്ഞില്ല', 'നെറ്റ്‌വർക്ക് പരിശോധിച്ച് വീണ്ടും ശ്രമിക്കുക.');
        return;
    }
    if (!response.ok) {
        showNearMeError('കടകൾ ലോഡ് ചെയ്യാൻ കഴിഞ്ഞില്ല', 'വീണ്ടും ശ്രമിക്കുക.');
        return;
    }
    resultsSection.innerHTML = await response.text();
});

loadDistricts();


// ===== Close suggestions on outside click =====
document.addEventListener('click', (e) => {
    if (!e.target.closest('#search-container')) {
        suggestions?.classList.add('hidden');
    }
    if (!e.target.closest('#owner-container')) {
        ownerSuggestions?.classList.add('hidden');
    }
});

// Close on Escape
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        suggestions?.classList.add('hidden');
        ownerSuggestions?.classList.add('hidden');
    }
});


// ===== Rotating placeholder =====
const placeholders = ["കടയുടെ നമ്പർ...", "സ്ഥലപ്പേര്..."];
let phIndex = 0;
setInterval(() => {
    if (document.activeElement === searchInput || searchInput.value) return;
    phIndex = (phIndex + 1) % placeholders.length;
    searchInput.placeholder = placeholders[phIndex];
}, 2500);


// ===== Animated stat counters (triggered after HTMX loads stats) =====
function animateCount(el, target) {
    const duration = 1200;
    const start = performance.now();
    function tick(now) {
        const progress = Math.min((now - start) / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3);
        el.textContent = Math.round(target * eased).toLocaleString('en-IN');
        if (progress < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
}

document.addEventListener('htmx:afterSwap', (e) => {
    // Animate stat counters when stats partial is loaded
    if (e.detail.target?.id === 'empty-state') {
        e.detail.target.querySelectorAll('[data-count-target]').forEach(el => {
            const target = parseInt(el.dataset.countTarget, 10);
            if (target > 0) animateCount(el, target);
        });
    }

    // Show results section when results are loaded
    if (e.detail.target?.id === 'results') {
        resultsSection.classList.remove('hidden');
        emptyState.classList.add('hidden');
    }
});


// ===== Deep link: open ?shop=ID or ?place=ID directly on page load =====
(() => {
    const p = new URLSearchParams(location.search);
    const shopId = p.get('shop'), placeId = p.get('place');
    if (shopId) {
        emptyState.classList.add('hidden');
        resultsSection.classList.remove('hidden');
        resultsSection.innerHTML = '<div class="text-center py-16"><div class="inline-block w-8 h-8 border-[3px] border-kerala-green/20 border-t-kerala-green rounded-full animate-spin"></div><p class="mt-4 text-sm text-gray-500 malayalam">ഡാറ്റ ലോഡ് ചെയ്യുന്നു...</p></div>';
        htmx.ajax('GET', `/htmx/select?type=shop&id=${encodeURIComponent(shopId)}`, {target: '#results', swap: 'innerHTML'});
    } else if (placeId) {
        emptyState.classList.add('hidden');
        resultsSection.classList.remove('hidden');
        resultsSection.innerHTML = '<div class="text-center py-16"><div class="inline-block w-8 h-8 border-[3px] border-kerala-green/20 border-t-kerala-green rounded-full animate-spin"></div><p class="mt-4 text-sm text-gray-500 malayalam">ഡാറ്റ ലോഡ് ചെയ്യുന്നു...</p></div>';
        htmx.ajax('GET', `/htmx/select?type=place&id=${encodeURIComponent(placeId)}`, {target: '#results', swap: 'innerHTML'});
    }
})();


// ===== ⭐ Favorites (localStorage) =====
const FAV_KEY = 'rationundo_favs';
const savedShopsSection = document.getElementById('saved-shops');
const savedShopsList = document.getElementById('saved-shops-list');
const clearFavsBtn = document.getElementById('clear-favs-btn');

function getFavs() {
    try { return JSON.parse(localStorage.getItem(FAV_KEY) || '[]'); } catch { return []; }
}

function saveFavs(favs) {
    localStorage.setItem(FAV_KEY, JSON.stringify(favs));
}

function isFav(ard) {
    return getFavs().some(f => f.ard === ard);
}

function toggleFav(ard, name, district) {
    let favs = getFavs();
    const idx = favs.findIndex(f => f.ard === ard);
    if (idx >= 0) {
        favs.splice(idx, 1);
    } else {
        favs.unshift({ ard, name, district, url: `/?shop=${encodeURIComponent(ard)}` });
    }
    saveFavs(favs);
    renderSavedShops();
    syncFavButtons();
}

function renderSavedShops() {
    const favs = getFavs();
    if (!savedShopsSection || !savedShopsList) return;
    if (!favs.length) {
        savedShopsSection.classList.add('hidden');
        return;
    }
    savedShopsSection.classList.remove('hidden');
    savedShopsList.innerHTML = favs.map(f => `
        <button class="fav-chip inline-flex items-center gap-1.5 px-3 py-1.5 bg-amber-50 hover:bg-amber-100 border border-amber-200 text-amber-900 rounded-lg text-xs font-semibold transition-colors"
                data-fav-ard="${f.ard}" title="കട നം. ${f.ard}">
            <svg class="w-3 h-3 text-amber-400 shrink-0" fill="currentColor" viewBox="0 0 24 24"><path d="M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.563.563 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.563.563 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z"/></svg>
            <span>കട ${f.ard}${f.name ? ' · ' + f.name.split(' ')[0] : ''}</span>
        </button>
    `).join('');
}

function syncFavButtons() {
    document.querySelectorAll('[data-shop-ard]').forEach(card => {
        const ard = card.dataset.shopArd;
        const btn = card.querySelector('.btn-fav svg');
        if (!btn) return;
        if (isFav(ard)) {
            btn.style.color = '#FBBF24'; // amber-400
        } else {
            btn.style.color = '';
        }
    });
}

// Tap a saved chip → load that shop
savedShopsList?.addEventListener('click', (e) => {
    const chip = e.target.closest('.fav-chip');
    if (!chip) return;
    const ard = chip.dataset.favArd;
    emptyState.classList.add('hidden');
    resultsSection.classList.remove('hidden');
    resultsSection.innerHTML = '<div class="text-center py-16"><div class="inline-block w-8 h-8 border-[3px] border-kerala-green/20 border-t-kerala-green rounded-full animate-spin"></div></div>';
    htmx.ajax('GET', `/htmx/select?type=shop&id=${encodeURIComponent(ard)}`, {target: '#results', swap: 'innerHTML'});
    history.replaceState(null, '', `?shop=${encodeURIComponent(ard)}`);
});

// Clear all favorites
clearFavsBtn?.addEventListener('click', () => {
    saveFavs([]);
    renderSavedShops();
    syncFavButtons();
});

// Tap the ⭐ button on a shop card
document.addEventListener('click', (e) => {
    const btn = e.target.closest('.btn-fav');
    if (!btn) return;
    const card = btn.closest('[data-shop-ard]');
    if (!card) return;
    toggleFav(card.dataset.shopArd, card.dataset.shopName, card.dataset.shopDistrict);
});

// Re-sync after every HTMX swap
document.addEventListener('htmx:afterSwap', syncFavButtons);

// Initial render on page load
renderSavedShops();


// ===== 📲 Share =====
async function handleShare(ard, name, district) {
    const shopLabel = name ? `${name} (${district})` : `${district}`;
    const url = `${location.origin}/?shop=${encodeURIComponent(ard)}`;
    const text = `കട നം. ${ard} — ${shopLabel}\nറേഷൻ ഉണ്ടോ? സ്റ്റോക്ക് സ്റ്റാറ്റസ് ഇവിടെ കാണാം:\n${url}`;

    if (navigator.share) {
        try {
            await navigator.share({ title: `കട നം. ${ard} | റേഷൻ ഉണ്ടോ?`, text, url });
            return;
        } catch (err) {
            if (err.name === 'AbortError') return; // user cancelled — don't fallback
        }
    }
    // WhatsApp fallback
    window.open(`https://api.whatsapp.com/send?text=${encodeURIComponent(text)}`, '_blank', 'noopener');
}

document.addEventListener('click', (e) => {
    const btn = e.target.closest('.btn-share');
    if (!btn) return;
    const card = btn.closest('[data-shop-ard]');
    if (!card) return;
    handleShare(card.dataset.shopArd, card.dataset.shopName, card.dataset.shopDistrict);
});
