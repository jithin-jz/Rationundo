const searchInput = document.getElementById('search-input');
const suggestions = document.getElementById('suggestions');
const resultsSection = document.getElementById('results');
const emptyState = document.getElementById('empty-state');

let debounceTimer;

searchInput.addEventListener('input', () => {
    clearTimeout(debounceTimer);
    const q = searchInput.value.trim();
    if (q.length < 2) {
        suggestions.classList.add('hidden');
        return;
    }
    debounceTimer = setTimeout(() => fetchAutocomplete(q), 200);
});

async function fetchAutocomplete(q) {
    const resp = await fetch(`/api/autocomplete?q=${encodeURIComponent(q)}`);
    if (!resp.ok) return;
    const data = await resp.json();
    renderSuggestions(data);
}

function renderSuggestions(items, target = suggestions) {
    if (!items.length) {
        target.innerHTML = `<div class="px-5 py-4 text-sm text-gray-400 malayalam">ഫലങ്ങൾ ഒന്നും കണ്ടെത്തിയില്ല</div>`;
        target.classList.remove('hidden');
        return;
    }
    target.innerHTML = items.map(item => {
        const icon = item.type === 'shop'
            ? `<svg class="w-4 h-4 text-kerala-gold shrink-0" fill="currentColor" viewBox="0 0 20 20"><path d="M4 3a2 2 0 100 4h12a2 2 0 100-4H4z"/><path fill-rule="evenodd" d="M3 8h14v7a2 2 0 01-2 2H5a2 2 0 01-2-2V8zm5 3a1 1 0 011-1h2a1 1 0 110 2H9a1 1 0 01-1-1z" clip-rule="evenodd"/></svg>`
            : `<svg class="w-4 h-4 text-kerala-green shrink-0" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M5.05 4.05a7 7 0 119.9 9.9L10 18.9l-4.95-4.95a7 7 0 010-9.9zM10 11a2 2 0 100-4 2 2 0 000 4z" clip-rule="evenodd"/></svg>`;
        const badge = item.type === 'shop'
            ? `<span class="shrink-0 text-[10px] font-semibold bg-kerala-gold/10 text-kerala-gold px-2 py-0.5 rounded malayalam">കട</span>`
            : `<span class="shrink-0 text-[10px] font-semibold bg-kerala-green/5 text-kerala-green px-2 py-0.5 rounded malayalam">സ്ഥലം</span>`;
        return `
        <button class="suggestion-item w-full text-left px-4 py-3 transition-colors border-b border-gray-50 last:border-0 flex items-center gap-3"
                onclick="selectItem('${item.type}', ${item.id})">
            ${icon}
            <div class="min-w-0 flex-1">
                <div class="font-semibold text-gray-800 text-[15px] truncate">${item.label}</div>
                <div class="text-xs text-gray-400 truncate">${item.sublabel}</div>
            </div>
            ${badge}
        </button>`;
    }).join('');
    suggestions.classList.remove('hidden');
}

async function selectItem(type, id) {
    history.replaceState(null, '', `?${type}=${id}`);
    suggestions.classList.add('hidden');
    document.getElementById('owner-suggestions')?.classList.add('hidden');
    emptyState.classList.add('hidden');
    resultsSection.innerHTML = `
        <div class="text-center py-16">
            <div class="inline-block w-8 h-8 border-[3px] border-kerala-green/20 border-t-kerala-green rounded-full animate-spin"></div>
            <p class="mt-4 text-sm text-gray-500 malayalam">ഡാറ്റ ലോഡ് ചെയ്യുന്നു...</p>
        </div>`;
    resultsSection.classList.remove('hidden');

    const endpoint = type === 'shop' ? `/api/shop/${id}` : `/api/status/${id}`;
    const resp = await fetch(endpoint);
    if (!resp.ok) {
        resultsSection.innerHTML = `<div class="text-center py-8 text-red-500 malayalam">ഡാറ്റ ലോഡ് ചെയ്യുന്നതിൽ പിശക്</div>`;
        return;
    }
    const data = await resp.json();
    renderResults(data);
}

// Commodity name translations
const commodityMl = {
    'Fort.RR': 'ഫോർട്ടിഫൈഡ് റോ റൈസ്',
    'Fort.BR': 'ഫോർട്ടിഫൈഡ് ബോയിൽഡ് റൈസ്',
    'Fort.CMR': 'ഫോർട്ടിഫൈഡ് CMR',
    'Wheat': 'ഗോതമ്പ്',
    'Atta': 'ആട്ട',
    'Sugar': 'പഞ്ചസാര',
    'Matta rice': 'മട്ട അരി',
    'Kerosene': 'മണ്ണെണ്ണ',
};

function renderResults(data) {
    if (!data.shops.length) {
        resultsSection.innerHTML = `
            <div class="text-center py-16 bg-white rounded-2xl shadow-sm border border-gray-100">
                <div class="w-16 h-16 mx-auto bg-gray-50 rounded-full flex items-center justify-center">
                    <svg class="w-8 h-8 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
                    </svg>
                </div>
                <p class="mt-4 text-gray-600 font-medium malayalam">ഈ പ്രദേശത്തെ ഡാറ്റ ഉടൻ ലഭ്യമാകും</p>
                <p class="text-sm text-gray-400 mt-1">Data for this area will be available soon</p>
            </div>`;
        return;
    }

    const stateOf = s => s.delivery_state || (s.is_stock_delivered ? 'full' : 'none');
    const total = data.shops.length;
    const delivered = data.shops.filter(s => stateOf(s) === 'full').length;
    const partial = data.shops.filter(s => stateOf(s) === 'partial').length;
    const percentage = Math.round((delivered / total) * 100);
    const partialNote = partial ? ` · ${partial} ഭാഗികം` : '';

    let html = `
        <!-- Summary Header -->
        <div class="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 sm:p-5 mb-4">
            <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                    <h2 class="text-base sm:text-lg font-bold text-gray-900 break-words">${data.post_office_name}</h2>
                    <p class="text-xs sm:text-sm text-gray-500 mt-0.5">📍 ${data.pincode} · ${total} കടകൾ</p>
                </div>
                <div class="text-right shrink-0">
                    <div class="text-2xl sm:text-3xl font-extrabold ${percentage > 70 ? 'text-kerala-green' : percentage > 30 ? 'text-amber-500' : 'text-red-500'}">${percentage}%</div>
                    <div class="text-[11px] sm:text-xs text-gray-500 mt-0.5">${delivered}/${total} സ്റ്റോക്ക് എത്തി${partialNote}</div>
                </div>
            </div>
            <!-- Progress bar -->
            <div class="mt-3 h-2 bg-gray-100 rounded-full overflow-hidden">
                <div class="h-full rounded-full transition-all duration-500 ${percentage > 70 ? 'bg-kerala-green' : percentage > 30 ? 'bg-amber-400' : 'bg-red-400'}" style="width: ${percentage}%"></div>
            </div>
        </div>
    `;

    // Sort: full delivered first, then partial, then none
    const rank = { full: 0, partial: 1, none: 2 };
    const sorted = [...data.shops].sort((a, b) => rank[stateOf(a)] - rank[stateOf(b)]);

    html += `<div id="feed" class="space-y-3"></div><div id="feed-sentinel" class="h-px"></div>`;
    resultsSection.innerHTML = html;
    startFeed(sorted);
}

// ===== Instagram-like infinite scroll feed =====
let feedState = null;
let feedObserver = null;

function startFeed(shops) {
    feedState = { shops, rendered: 0, batch: 10, el: document.getElementById('feed') };
    appendBatch();
    if (feedObserver) feedObserver.disconnect();
    feedObserver = new IntersectionObserver((e) => { if (e[0].isIntersecting) appendBatch(); }, { rootMargin: '300px' });
    feedObserver.observe(document.getElementById('feed-sentinel'));
}

function appendBatch() {
    if (!feedState) return;
    const { shops, rendered, batch, el } = feedState;
    const slice = shops.slice(rendered, rendered + batch);
    el.insertAdjacentHTML('beforeend', slice.map((shop, k) => renderShopCard(shop, k)).join(''));
    feedState.rendered += slice.length;
    if (feedState.rendered >= shops.length) {
        feedObserver?.disconnect();
        document.getElementById('feed-sentinel')?.remove();
    }
}

function renderShopCard(shop, i) {
        const state = shop.delivery_state || (shop.is_stock_delivered ? 'full' : 'none');
        const cardClass = state === 'full' ? 'card-delivered' : state === 'partial' ? 'card-partial' : 'card-pending';

        const statusHtml = state === 'full'
            ? `<div class="shrink-0 flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-green-50">
                    <div class="w-2.5 h-2.5 rounded-full bg-green-500"></div>
                    <span class="text-xs sm:text-sm font-semibold text-green-800 malayalam whitespace-nowrap">സ്റ്റോക്ക് എത്തി ✓</span>
               </div>`
            : state === 'partial'
            ? `<div class="shrink-0 flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-amber-50">
                    <div class="w-2.5 h-2.5 rounded-full bg-amber-500"></div>
                    <span class="text-xs sm:text-sm font-semibold text-amber-800 malayalam whitespace-nowrap">ഭാഗികമായി എത്തി</span>
               </div>`
            : `<div class="shrink-0 flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-amber-50">
                    <div class="w-2.5 h-2.5 rounded-full bg-amber-500 animate-pulse"></div>
                    <span class="text-xs sm:text-sm font-semibold text-amber-800 malayalam whitespace-nowrap">എത്തിയിട്ടില്ല</span>
               </div>`;

        const itemsHtml = shop.items.length ? `
            <div class="mt-3 pt-3 border-t border-gray-100">
                <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 malayalam">സാധനങ്ങളുടെ വിശദാംശങ്ങൾ</p>
                <div class="space-y-1.5">
                    ${shop.items.map(item => {
                        const pct = item.allocated_quantity > 0 ? Math.round((item.received_quantity / item.allocated_quantity) * 100) : 0;
                        const mlName = commodityMl[item.commodity_name] || item.commodity_name;
                        return `
                        <div class="flex items-center gap-3 py-1.5">
                            <div class="flex-1 min-w-0">
                                <div class="flex items-center justify-between mb-1">
                                    <span class="text-sm font-medium text-gray-800">${item.commodity_name} <span class="text-xs text-gray-400 malayalam">${mlName !== item.commodity_name ? mlName : ''}</span></span>
                                    <span class="text-xs font-semibold ${item.received_quantity > 0 ? 'text-kerala-green' : 'text-gray-400'}">${item.received_quantity.toLocaleString()} / ${item.allocated_quantity.toLocaleString()}</span>
                                </div>
                                <div class="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                                    <div class="h-full rounded-full ${pct >= 80 ? 'bg-kerala-green' : pct > 0 ? 'bg-amber-400' : 'bg-gray-200'}" style="width: ${Math.min(pct, 100)}%"></div>
                                </div>
                            </div>
                        </div>`;
                    }).join('')}
                </div>
            </div>
        ` : `<div class="mt-3 pt-3 border-t border-gray-100">
                <p class="text-sm text-gray-400 malayalam">വിശദാംശങ്ങൾ ലഭ്യമല്ല</p>
             </div>`;

        const lastChecked = shop.last_checked
            ? new Date(shop.last_checked).toLocaleString('ml-IN', {timeZone: 'Asia/Kolkata', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit'})
            : '';

        return `
            <div class="${cardClass} rounded-xl shadow-sm border border-gray-100 p-4 animate-slide-up" style="animation-delay: ${i * 40}ms; opacity: 0">
                <div class="flex items-start justify-between gap-3">
                    <div class="min-w-0">
                        <p class="font-bold text-gray-900">കട നം. ${shop.ard_number}</p>
                        <p class="text-xs text-gray-500 mt-0.5">${shop.dealer_name || ''} · ${shop.local_place ? `${shop.local_place}, ` : ''}${shop.district} · ${shop.month_cycle}${shop.distance_km != null ? ` · 📍 ${shop.distance_km} km` : ''}</p>
                    </div>
                    ${statusHtml}
                </div>
                ${itemsHtml}
                ${lastChecked ? `<p class="mt-2 text-[11px] text-gray-400">അവസാന അപ്‌ഡേറ്റ്: ${lastChecked}</p>` : ''}
            </div>
        `;
}

// ===== Near me: browser geolocation -> /api/nearby =====
const nearMeBtn = document.getElementById('near-me-btn');
nearMeBtn?.addEventListener('click', () => {
    if (!navigator.geolocation) {
        alert('ലൊക്കേഷൻ ലഭ്യമല്ല');
        return;
    }
    const label = nearMeBtn.innerHTML;
    nearMeBtn.disabled = true;
    nearMeBtn.innerHTML = 'ലൊക്കേഷൻ കണ്ടെത്തുന്നു...';
    navigator.geolocation.getCurrentPosition(
        async (pos) => {
            nearMeBtn.innerHTML = label;
            nearMeBtn.disabled = false;
            suggestions.classList.add('hidden');
            emptyState.classList.add('hidden');
            resultsSection.innerHTML = `<div class="text-center py-16"><div class="inline-block w-8 h-8 border-[3px] border-kerala-green/20 border-t-kerala-green rounded-full animate-spin"></div></div>`;
            resultsSection.classList.remove('hidden');
            const { latitude, longitude } = pos.coords;
            const resp = await fetch(`/api/nearby?lat=${latitude}&lon=${longitude}`);
            if (!resp.ok) {
                resultsSection.innerHTML = `<div class="text-center py-8 text-red-500 malayalam">പിശക്</div>`;
                return;
            }
            renderResults(await resp.json());
        },
        () => {
            nearMeBtn.innerHTML = label;
            nearMeBtn.disabled = false;
            alert('ലൊക്കേഷൻ അനുമതി നിഷേധിച്ചു');
        },
        { enableHighAccuracy: true, timeout: 10000 }
    );
});

// ===== Owner name search (separate box) =====
const ownerInput = document.getElementById('owner-input');
const ownerSuggestions = document.getElementById('owner-suggestions');
let ownerDebounce;

ownerInput?.addEventListener('input', () => {
    clearTimeout(ownerDebounce);
    const q = ownerInput.value.trim();
    if (q.length < 2) {
        ownerSuggestions.classList.add('hidden');
        return;
    }
    ownerDebounce = setTimeout(async () => {
        const resp = await fetch(`/api/owners?q=${encodeURIComponent(q)}`);
        if (!resp.ok) return;
        renderSuggestions(await resp.json(), ownerSuggestions);
    }, 200);
});

ownerInput?.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') ownerSuggestions.classList.add('hidden');
});

// Close suggestions on outside click
document.addEventListener('click', (e) => {
    if (!e.target.closest('#search-container')) {
        suggestions.classList.add('hidden');
    }
    if (!e.target.closest('#owner-container')) {
        ownerSuggestions?.classList.add('hidden');
    }
});

searchInput.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') suggestions.classList.add('hidden');
});

// Rotating placeholder examples
const placeholders = [
    "കടയുടെ നമ്പർ (ഉദാ. 1736083)...",
    "പിൻകോഡ് (ഉദാ. 683101)...",
    "സ്ഥലപ്പേര് (ഉദാ. Aluva)...",
];
let phIndex = 0;
setInterval(() => {
    if (document.activeElement === searchInput || searchInput.value) return;
    phIndex = (phIndex + 1) % placeholders.length;
    searchInput.placeholder = placeholders[phIndex];
}, 2500);

// ===== Browse: District -> Taluk -> Shops =====
const selDistrict = document.getElementById('sel-district');
const selTaluk = document.getElementById('sel-taluk');
const talukWrap = document.getElementById('taluk-wrap');

// Load districts on page load
(async () => {
    const resp = await fetch('/api/districts');
    if (!resp.ok) return;
    const districts = await resp.json();
    districts.forEach(d => {
        const opt = document.createElement('option');
        opt.value = d;
        opt.textContent = d;
        selDistrict.appendChild(opt);
    });
})();

// ===== Animated stat counters with real counts =====
function animateCount(el, target) {
    const duration = 1200;
    const start = performance.now();
    function tick(now) {
        const progress = Math.min((now - start) / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
        el.textContent = Math.round(target * eased).toLocaleString('en-IN');
        if (progress < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
}

(async () => {
    try {
        const resp = await fetch('/api/stats');
        if (!resp.ok) return;
        const s = await resp.json();
        const map = {
            'stat-districts': s.districts,
            'stat-shops': s.shops,
            'stat-pincodes': s.pincodes,
            'stat-delivered': s.delivered,
        };
        for (const [id, val] of Object.entries(map)) {
            const el = document.getElementById(id);
            if (el) animateCount(el, val);
        }
        const lu = document.getElementById('last-updated');
        if (lu && s.last_updated) {
            const d = new Date(s.last_updated);
            lu.textContent = 'അവസാന അപ്ഡേറ്റ്: ' + d.toLocaleString('ml-IN', {timeZone: 'Asia/Kolkata', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit'});
        }
    } catch (e) {}
})();

selDistrict.addEventListener('change', async () => {
    selTaluk.innerHTML = '<option value="">— താലൂക്ക് —</option>';
    talukWrap.classList.add('hidden');
    resultsSection.classList.add('hidden');
    if (!selDistrict.value) return;

    const resp = await fetch(`/api/taluks?district=${encodeURIComponent(selDistrict.value)}`);
    if (!resp.ok) return;
    const taluks = await resp.json();
    taluks.forEach(t => {
        const opt = document.createElement('option');
        opt.value = t.tso_code;
        opt.textContent = t.name;
        selTaluk.appendChild(opt);
    });
    talukWrap.classList.remove('hidden');
});

selTaluk.addEventListener('change', async () => {
    if (!selTaluk.value) {
        resultsSection.classList.add('hidden');
        return;
    }
    emptyState.classList.add('hidden');
    resultsSection.innerHTML = `
        <div class="text-center py-16">
            <div class="inline-block w-8 h-8 border-[3px] border-kerala-green/20 border-t-kerala-green rounded-full animate-spin"></div>
            <p class="mt-4 text-sm text-gray-500 malayalam">കടകൾ ലോഡ് ചെയ്യുന്നു...</p>
        </div>`;
    resultsSection.classList.remove('hidden');

    const talukName = selTaluk.options[selTaluk.selectedIndex].textContent;
    const resp = await fetch(`/api/shops?tso_code=${encodeURIComponent(selTaluk.value)}`);
    if (!resp.ok) {
        resultsSection.innerHTML = `<div class="text-center py-8 text-red-500 malayalam">പിശക്</div>`;
        return;
    }
    const shops = await resp.json();
    renderResults({ post_office_name: talukName, pincode: selDistrict.value, shops });
});

// Deep link: open ?shop=ID or ?place=ID directly on page load
(() => {
    const p = new URLSearchParams(location.search);
    const shopId = p.get('shop'), placeId = p.get('place');
    if (shopId) selectItem('shop', shopId);
    else if (placeId) selectItem('place', placeId);
})();
