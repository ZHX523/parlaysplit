/**

 * Parlay form: live payout + dynamic legs (vanilla JS — no Alpine dependency).

 */

(function () {

  function sanitizeWagerInput(value) {

    let s = String(value).replace(/[^\d.]/g, "");

    const dot = s.indexOf(".");

    if (dot !== -1) {

      s = s.slice(0, dot + 1) + s.slice(dot + 1).replace(/\./g, "");

    }

    return s;

  }



  function parseWager(str) {

    if (str == null || str === "") return null;

    const raw = sanitizeWagerInput(String(str).replace(/[$,\s]/g, ""));

    if (!raw || !/^\d*\.?\d*$/.test(raw)) return null;

    const n = parseFloat(raw);

    return Number.isFinite(n) && n > 0 ? n : null;

  }



  function formatDollars(n) {

    if (n == null || !Number.isFinite(n)) return "";

    const negative = n < 0;

    const fixed = Math.abs(n).toFixed(2);

    const parts = fixed.split(".");

    const whole = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ",");

    const frac = parts[1] || "00";

    return (negative ? "-$" : "$") + whole + "." + frac;

  }



  function formatWager(n) {

    if (n == null || n <= 0) return "";

    return formatDollars(n);

  }



  function parsePercent(str) {

    if (str == null || str === "") return null;

    const n = parseFloat(String(str).replace(/%/g, "").trim());

    if (!Number.isFinite(n) || n < 1 || n > 100) return null;

    return n;

  }



  function formatPercent(n) {

    if (n == null || n < 1 || n > 100) return "";

    const whole = Math.round(n);

    return whole + "%";

  }



  function wagerRawValue(el) {

    if (!el) return null;

    return parseWager(el.value);

  }



  function splitRawValue(el) {

    if (!el) return null;

    return parsePercent(el.value);

  }



  function getSplitSlider(root) {

    return root.querySelector("[data-split-slider]");

  }



  function splitRawValueFromRoot(root) {

    const field = root.querySelector('[name="split_offered_percent"]');

    const fromField = field ? parsePercent(field.value) : null;

    if (fromField != null) return fromField;

    const slider = getSplitSlider(root);

    if (!slider) return null;

    const n = parseInt(slider.value, 10);

    return Number.isFinite(n) && n >= 1 && n <= 100 ? n : null;

  }



  function syncSliderFromField(root) {

    const slider = getSplitSlider(root);

    const field = root.querySelector('[name="split_offered_percent"]');

    if (!slider || !field) return;

    const n = parsePercent(field.value);

    if (n != null) {

      slider.value = String(Math.round(n));

      updateSplitSliderFill(slider);

    }

  }



  function setSplitFieldFromSlider(root) {

    const field = root.querySelector('[name="split_offered_percent"]');

    const slider = getSplitSlider(root);

    if (!field || !slider) return;

    const n = parseInt(slider.value, 10);

    if (!Number.isFinite(n)) return;

    field.value = formatPercent(n);

    updateSplitSliderFill(slider);

  }



  function updateSplitSliderFill(slider) {

    if (!slider) return;

    const n = parseInt(slider.value, 10);

    if (!Number.isFinite(n)) return;

    const min = Number(slider.min) || 1;

    const max = Number(slider.max) || 100;

    const pct = ((n - min) / (max - min)) * 100;

    slider.style.setProperty("--split-progress", pct + "%");

  }



  function parseAmericanOdds(str) {

    if (str == null || str === "") return null;

    const raw = String(str).trim();

    if (!/^[-+]?\d+$/.test(raw)) return null;

    const n = parseInt(raw, 10);

    if (!Number.isFinite(n) || n === 0) return null;

    return n;

  }



  function formatAmericanOddsLive(str) {

    let s = String(str).replace(/[^\d+-]/g, "");

    if (!s) return "";

    const digits = s.replace(/[^\d]/g, "");

    const negative = s.includes("-");

    if (!digits) {

      return negative ? "-" : s.includes("+") ? "+" : "";

    }

    if (negative) {

      return "-" + digits;

    }

    return "+" + digits;

  }



  function formatAmericanOddsBlur(el) {

    el.value = formatAmericanOddsLive(el.value);

  }



  function bindOddsField(el, root) {

    if (!el || el._oddsBound) return;

    el._oddsBound = true;



    el.addEventListener("input", () => updatePayout(root));

    el.addEventListener("blur", () => {

      formatAmericanOddsBlur(el);

      updatePayout(root);

    });

    el.addEventListener("change", () => {

      formatAmericanOddsBlur(el);

      updatePayout(root);

    });



    if (el.value) formatAmericanOddsBlur(el);

  }



  function calcPayout(wager, odds) {

    const w = typeof wager === "number" ? wager : parseWager(wager);

    const o = typeof odds === "number" ? odds : parseAmericanOdds(odds);

    if (!w || w <= 0 || o == null) {

      return null;

    }

    const profit = o > 0 ? w * (o / 100) : w * (100 / Math.abs(o));

    return (w + profit).toFixed(2);

  }



  function updatePayout(root) {

    const display = root.querySelector("[data-payout-display]");

    if (!display) return;

    const odds = root.querySelector('[name="odds_american"]');

    const wager = root.querySelector('[name="wager_amount"]');

    const total = calcPayout(wagerRawValue(wager), odds?.value);

    const payout = total ? parseFloat(total) : null;

    display.textContent =

      payout != null && payout > 0 ? formatDollars(payout) : "$ —";

    updateSplitHint(root);

  }



  function updateSplitHint(root) {

    const friendsEl = root.querySelector("[data-split-friends-pct]");

    if (!friendsEl) return;

    const split = splitRawValueFromRoot(root);

    if (split == null) {

      friendsEl.textContent = "—";

      return;

    }

    friendsEl.textContent = Math.round(split) + "%";

  }



  function bindCurrencyField(el, onInput) {

    if (!el || el._currencyBound) return;

    el._currencyBound = true;



    const formatIfValid = () => {

      const n = parseWager(el.value);

      if (n != null) {

        el.value = formatWager(n);

      }

    };



    el.addEventListener("focus", () => {

      const n = parseWager(el.value);

      if (n != null) el.value = sanitizeWagerInput(n.toFixed(2));

    });



    el.addEventListener("blur", formatIfValid);



    el.addEventListener("input", () => {

      el.value = sanitizeWagerInput(el.value);

      if (onInput) onInput();

    });

  }



  function bindWagerField(el, root) {

    if (!el) return;

    bindCurrencyField(el, () => updatePayout(root));

  }



  function parseContributionAmount(str) {

    if (str == null || str === "") return null;

    const raw = sanitizeWagerInput(String(str).replace(/[$,\s]/g, ""));

    if (!raw || !/^\d*\.?\d*$/.test(raw)) return null;

    const n = parseFloat(raw);

    return Number.isFinite(n) && n >= 0 ? n : null;

  }



  function formatContributionLive(str) {

    let s = String(str).replace(/[$,\s]/g, "");

    s = sanitizeWagerInput(s);

    if (!s) return "";

    const dot = s.indexOf(".");

    let whole = dot === -1 ? s : s.slice(0, dot);

    let frac = dot === -1 ? "" : s.slice(dot + 1);

    if (!whole && dot === -1) return "";

    if (!whole) whole = "0";

    whole = whole.replace(/^0+(?=\d)/, "") || "0";

    const wholeFmt = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",");

    if (dot === -1) return "$" + wholeFmt;

    return "$" + wholeFmt + "." + frac.slice(0, 2);

  }



  function formatContributionBlur(el) {

    const digits = String(el.value).replace(/[^\d.]/g, "");

    if (!digits) {

      el.value = "";

      return;

    }

    const n = parseContributionAmount(el.value);

    el.value = n != null ? formatDollars(n) : formatContributionLive(el.value);

  }



  function bindContributionField(el) {

    if (!el || el._contributionBound) return;

    el._contributionBound = true;



    el.addEventListener("input", () => {

      const raw = String(el.value).replace(/[^\d.,$]/g, "");

      if (raw !== el.value) el.value = raw;

    });

    el.addEventListener("blur", () => formatContributionBlur(el));

    el.addEventListener("change", () => formatContributionBlur(el));



    if (el.value) formatContributionBlur(el);

  }



  function bindContributionFields(root) {

    const scope = root && root.querySelectorAll ? root : document;

    scope.querySelectorAll("[data-format-contribution]").forEach(bindContributionField);

  }



  function setupContributionFormatting() {

    bindContributionFields(document);

  }



  const JOIN_DRAFT_PREFIX = "parlaysplit_join_draft:";

  const FOOTER_REV_PREFIX = "parlaysplit_footer_rev:";



  function joinDraftKey(form) {

    const parlayId = form?.dataset?.parlayId || location.pathname;

    return JOIN_DRAFT_PREFIX + parlayId;

  }



  function footerRevStorageKey() {

    const form = document.querySelector("[data-join-form]");

    const parlayId = form?.dataset?.parlayId || location.pathname;

    return FOOTER_REV_PREFIX + parlayId;

  }



  function syncFooterRevisionFromDom() {

    const sync = document.getElementById("ownership-sync");

    const rev = sync?.dataset?.footerRevision;

    if (rev != null) sessionStorage.setItem(footerRevStorageKey(), rev);

  }



  function readJoinDraft(form) {

    try {

      const raw = sessionStorage.getItem(joinDraftKey(form));

      return raw ? JSON.parse(raw) : null;

    } catch {

      return null;

    }

  }



  function saveJoinDraft(form) {

    const nickname = (form.querySelector('[name="nickname"]')?.value ?? "").trim();

    const contribution = form.querySelector('[name="contribution_amount"]')?.value ?? "";

    if (!nickname && !contribution) {

      try {

        sessionStorage.removeItem(joinDraftKey(form));

      } catch (_err) {

        /* private mode */

      }

      setOwnershipPollPaused(false);

      return;

    }

    try {

      sessionStorage.setItem(

        joinDraftKey(form),

        JSON.stringify({ nickname, contribution }),

      );

    } catch (_err) {

      return;

    }

    setOwnershipPollPaused(true);

  }



  function restoreJoinDraft(form) {

    const draft = readJoinDraft(form);

    if (!draft) return;

    const contrib = form.querySelector("[data-format-contribution]");

    if (form.dataset.joinMode === "top-up") {

      if (contrib && draft.contribution != null) {

        contrib.value = draft.contribution;

        formatContributionBlur(contrib);

      }

      return;

    }

    const nick = form.querySelector('[name="nickname"]');

    if (nick && draft.nickname != null) nick.value = draft.nickname;

    if (contrib && draft.contribution != null) {

      contrib.value = draft.contribution;

      formatContributionBlur(contrib);

    }

  }



  function clearJoinDraft(form) {

    sessionStorage.removeItem(joinDraftKey(form));

    setOwnershipPollPaused(false);

  }



  function setOwnershipPollPaused(paused) {

    const sync = document.getElementById("ownership-sync");

    if (!sync) return;

    if (paused) {

      if (!sync.dataset.pollTriggerSaved) {

        sync.dataset.pollTriggerSaved = sync.getAttribute("hx-trigger") || "every 5s";

      }

      sync.removeAttribute("hx-trigger");

    } else if (sync.dataset.pollTriggerSaved) {

      sync.setAttribute("hx-trigger", sync.dataset.pollTriggerSaved);

    }

  }



  function setupJoinDraftPreservation() {

    if (window._joinDraftBound) return;

    window._joinDraftBound = true;



    document.addEventListener("input", (e) => {

      const form = e.target.closest("[data-join-form]");

      if (form) saveJoinDraft(form);

    });



    document.addEventListener("htmx:beforeSwap", () => {

      document.querySelectorAll("[data-join-form]").forEach(saveJoinDraft);

    });



    document.addEventListener("htmx:afterSwap", (e) => {

      if (e.detail.target?.id === "ownership-sync") maybeRefreshJoinFooter();

      if (e.detail.target?.id === "ownership-footer") {

        document.querySelectorAll("[data-join-form]").forEach((form) => {

          restoreJoinDraft(form);

          initJoinForm(form);

        });

        return;

      }

    });

  }



  let footerRefreshTimer = null;

  let footerRefreshInFlight = false;



  function maybeRefreshJoinFooter() {

    const sync = document.getElementById("ownership-sync");

    if (!sync) return;

    const rev = sync.dataset.footerRevision;

    if (rev == null) return;

    const storageKey = footerRevStorageKey();

    const prev = sessionStorage.getItem(storageKey);

    if (rev === prev) return;

    if (footerRefreshTimer) clearTimeout(footerRefreshTimer);

    footerRefreshTimer = setTimeout(() => {

      footerRefreshTimer = null;

      runJoinFooterRefresh(sync, rev, storageKey, prev);

    }, 120);

  }



  function runJoinFooterRefresh(sync, rev, storageKey, prev) {

    if (rev === sessionStorage.getItem(storageKey)) return;

    if (footerRefreshInFlight) return;

    const form = document.querySelector("[data-join-form]");

    const draft = form && readJoinDraft(form);

    const wasJoin = form?.dataset.joinMode === "join";

    const parts = rev.split("|");

    const approvedNow = parts[0] === "1" && parts[2] !== "";

    if (draft && wasJoin && approvedNow) clearJoinDraft(form);

    try {

      sessionStorage.setItem(storageKey, rev);

    } catch (_err) {

      /* ignore */

    }

    const url = sync.dataset.joinFooterUrl;

    if (!url || typeof htmx === "undefined") return;

    const keepDraft = draft && wasJoin && !approvedNow;

    footerRefreshInFlight = true;

    htmx.ajax("GET", url, { target: "#ownership-footer", swap: "outerHTML" }).then(() => {

      document.querySelectorAll("[data-join-form]").forEach((f) => {

        if (keepDraft) restoreJoinDraft(f);

        else initJoinForm(f);

      });

    }).finally(() => {

      footerRefreshInFlight = false;

    });

  }



  function initJoinForm(root) {

    if (!root) return;

    const form = root.matches("[data-join-form]") ? root : root.querySelector("[data-join-form]");

    if (!form) return;

    restoreJoinDraft(form);

    bindContributionFields(form);



    if (form._joinSubmitBound) return;

    form._joinSubmitBound = true;



    form.addEventListener("submit", () => {

      clearJoinDraft(form);

      const el = form.querySelector("[data-format-contribution]");

      if (!el) return;

      const n = parseContributionAmount(el.value);

      el.value = n != null && n > 0 ? n.toFixed(2) : "";

    });

  }



  function bindSplitField(el, root) {

    if (!el || el._splitBound) return;

    el._splitBound = true;



    const formatIfValid = () => {

      const n = parsePercent(el.value);

      if (n != null) el.value = formatPercent(n);

    };



    el.addEventListener("focus", () => {

      const n = parsePercent(el.value);

      if (n != null) el.value = String(Math.round(n));

    });



    el.addEventListener("blur", () => {

      formatIfValid();

      syncSliderFromField(root);

    });



    el.addEventListener("input", () => {

      syncSliderFromField(root);

      updateSplitHint(root);

      updatePayout(root);

    });

  }



  function initSplitSliders(root) {

    root.querySelectorAll("[data-split-slider]").forEach(updateSplitSliderFill);

  }



  function setupSplitSliderDelegation() {

    if (window._splitSliderDelegation) return;

    window._splitSliderDelegation = true;



    function onSliderActivity(slider) {

      const root = slider.closest("[data-parlay-form]");

      if (!root) return;

      setSplitFieldFromSlider(root);

      updateSplitHint(root);

    }



    document.addEventListener(

      "input",

      (e) => {

        if (e.target.matches("[data-split-slider]")) onSliderActivity(e.target);

      },

      true,

    );



    document.addEventListener(

      "change",

      (e) => {

        if (e.target.matches("[data-split-slider]")) onSliderActivity(e.target);

      },

      true,

    );

  }



  function normalizeFormValues(root) {

    const wager = root.querySelector('[name="wager_amount"]');

    const split = root.querySelector('[name="split_offered_percent"]');

    if (wager) {

      const n = parseWager(wager.value);

      wager.value = n != null ? n.toFixed(2) : "";

    }

    if (split) {

      let n = parsePercent(split.value);

      if (n == null) {

        const slider = getSplitSlider(root);

        if (slider) n = parseInt(slider.value, 10);

      }

      split.value = n != null ? String(Math.round(n)) : "";

    }

  }



  function bindFormSubmit(root) {

    const form = root.closest("form");

    if (!form || form._parlaySubmitBound) return;

    form._parlaySubmitBound = true;

    form.addEventListener("submit", () => normalizeFormValues(root));

  }



  function formatInitialFields(root) {

    const odds = root.querySelector('[name="odds_american"]');

    const wager = root.querySelector('[name="wager_amount"]');

    const split = root.querySelector('[name="split_offered_percent"]');

    if (odds && odds.value) formatAmericanOddsBlur(odds);

    if (wager) {

      const w = parseWager(wager.value);

      wager.value = w != null ? formatWager(w) : "";

    }

    if (split) {

      const s = parsePercent(split.value);

      split.value = s != null ? formatPercent(s) : "";

    }

  }



  function legTypeHintsFor(root) {

    try {

      return JSON.parse(root.dataset.legTypeHints || "{}");

    } catch {

      return {};

    }

  }



  function updateLegDescriptionPlaceholder(row, root) {

    if (!row) return;

    const select = row.querySelector('[name="leg_type"]');

    const input = row.querySelector("[data-leg-description]");

    if (!select || !input) return;

    const hints = legTypeHintsFor(root);

    input.placeholder = hints[select.value] || "";

  }



  function syncAllLegDescriptionPlaceholders(root) {

    legRowsInContainer(root).forEach((row) => {

      updateLegDescriptionPlaceholder(row, root);

    });

  }



  function setupLegTypeHintListeners(root) {

    if (root._legHintsBound) return;

    root._legHintsBound = true;

    root.addEventListener("change", (e) => {

      if (e.target.matches('[name="leg_type"]')) {

        updateLegDescriptionPlaceholder(

          e.target.closest("[data-leg-row]"),

          root,

        );

      }

    });

  }



  function updateRemoveButtons(root) {

    const rows = legRowsInContainer(root);

    rows.forEach((row) => {

      const btn = row.querySelector("[data-remove-leg]");

      if (btn) btn.style.visibility = rows.length > 1 ? "visible" : "hidden";

    });

  }



  function bindLegRow(row, root, maxLegs) {

    const removeBtn = row.querySelector("[data-remove-leg]");

    if (removeBtn) {

      removeBtn.addEventListener("click", () => {

        const container = root.querySelector("[data-legs-container]");

        if (container.querySelectorAll("[data-leg-row]").length > 1) {

          row.remove();

          renumberLegs(root);

          updateAddButton(root, maxLegs);

          updateRemoveButtons(root);

        }

      });

    }



    updateLegDescriptionPlaceholder(row, root);

  }



  function renumberLegs(root) {

    legRowsInContainer(root).forEach((row, i) => {

      const label = row.querySelector("[data-leg-label]");

      if (label) label.textContent = "Leg " + (i + 1);

    });

  }



  function updateAddButton(root, maxLegs) {

    const btn = root.querySelector("[data-add-leg]");

    const count = legRowsInContainer(root).length;

    if (btn) btn.style.display = count >= maxLegs ? "none" : "";

  }



  function addLeg(root, maxLegs) {

    const template = root.querySelector("[data-leg-template]");

    const container = root.querySelector("[data-legs-container]");

    if (!template || !container) return;

    if (container.querySelectorAll("[data-leg-row]").length >= maxLegs) return;



    const clone = template.content.cloneNode(true);

    container.appendChild(clone);

    const added = container.lastElementChild;

    if (added) bindLegRow(added, root, maxLegs);

    renumberLegs(root);

    updateAddButton(root, maxLegs);

    updateRemoveButtons(root);

    updateLegDescriptionPlaceholder(added, root);

  }



  function legRowsInContainer(root) {
    const container = root.querySelector("[data-legs-container]");
    return container ? container.querySelectorAll("[data-leg-row]") : [];
  }

  function hydrateOcrLegs(root) {
    const scriptId = root.dataset.ocrHydrateLegs;
    if (!scriptId) return false;

    const el = document.getElementById(scriptId);
    const container = root.querySelector("[data-legs-container]");
    const template = root.querySelector("[data-leg-template]");
    if (!el || !container || !template) return false;

    let legs;
    try {
      legs = JSON.parse(el.textContent);
    } catch {
      return false;
    }
    if (!Array.isArray(legs) || legs.length === 0) return false;

    const maxLegs = parseInt(root.dataset.maxLegs || "20", 10);
    container.replaceChildren();

    legs.forEach((leg) => {
      const clone = template.content.cloneNode(true);
      container.appendChild(clone);
      const row = container.lastElementChild;
      if (!row) return;
      const sel = row.querySelector('[name="leg_type"]');
      const inp = row.querySelector("[data-leg-description]");
      const highlight = root.hasAttribute("data-parlay-form-review");
      if (sel && leg.leg_type) sel.value = leg.leg_type;
      if (inp) inp.value = leg.description || "";
      if (highlight) {
        if (sel) sel.classList.add("ocr-field-uncertain");
        if (inp) inp.classList.add("ocr-field-uncertain");
      }
      bindLegRow(row, root, maxLegs);
      updateLegDescriptionPlaceholder(row, root);
    });

    renumberLegs(root);
    updateAddButton(root, maxLegs);
    updateRemoveButtons(root);
    root._parlayLegsReady = true;
    return true;
  }

  function initParlayForm(root) {

    const maxLegs = parseInt(root.dataset.maxLegs || "20", 10);

    const legsReady = root._parlayLegsReady;



    setupLegTypeHintListeners(root);



    const ocrHydrated = hydrateOcrLegs(root);

    if (!ocrHydrated && !legsReady) {

      root._parlayLegsReady = true;

      legRowsInContainer(root).forEach((row) => bindLegRow(row, root, maxLegs));

    }



    syncAllLegDescriptionPlaceholders(root);



    const odds = root.querySelector('[name="odds_american"]');

    const wager = root.querySelector('[name="wager_amount"]');

    const split = root.querySelector('[name="split_offered_percent"]');



    bindOddsField(odds, root);

    bindWagerField(wager, root);

    bindSplitField(split, root);

    initSplitSliders(root);

    bindFormSubmit(root);



    const addBtn = root.querySelector("[data-add-leg]");

    if (addBtn && !addBtn._addLegBound) {

      addBtn._addLegBound = true;

      addBtn.addEventListener("click", () => addLeg(root, maxLegs));

    }



    formatInitialFields(root);

    syncSliderFromField(root);

    updateSplitHint(root);

    updatePayout(root);

    updateAddButton(root, maxLegs);

    updateRemoveButtons(root);

  }



  function initOcrUploadForm(root) {
    const scope = root && root.querySelector ? root : document;
    const form = scope.querySelector("[data-ocr-upload-form]");
    if (!form || form._ocrUploadBound) return;
    form._ocrUploadBound = true;

    const fileInput = form.querySelector('input[type="file"][name="image"]');
    const btn = form.querySelector("#ocr-scan-btn");
    const uploadZone = form.querySelector("#ocr-upload-zone");
    const pasteZone = form.querySelector("#ocr-paste-zone");
    const uploadStatus = form.querySelector("#ocr-upload-status");
    const pasteStatus = form.querySelector("#ocr-paste-status");
    const uploadHint = form.querySelector("#ocr-upload-hint");
    const uploadPreview = form.querySelector("#ocr-upload-preview");
    const pasteHint = form.querySelector("#ocr-paste-hint");
    const pastePreview = form.querySelector("#ocr-paste-preview");
    const pasteChangeHint = form.querySelector("#ocr-paste-change");
    const requiredMsg = form.querySelector("#ocr-image-required");
    let previewUrl = null;
    let activeSource = null;

    function revokePreview() {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
        previewUrl = null;
      }
    }

    function setFieldStatus(el, message, tone) {
      if (!el) return;
      if (!message) {
        el.textContent = "";
        el.classList.add("hidden");
        el.classList.remove("is-success", "is-error");
        return;
      }
      el.textContent = message;
      el.classList.remove("hidden", "is-success", "is-error");
      if (tone === "success") el.classList.add("is-success");
      if (tone === "error") el.classList.add("is-error");
    }

    function hideRequiredMsg() {
      if (!requiredMsg) return;
      requiredMsg.textContent = "";
      requiredMsg.classList.add("hidden");
    }

    function showRequiredMsg(message) {
      if (!requiredMsg) return;
      requiredMsg.textContent = message;
      requiredMsg.classList.remove("hidden");
    }

    function hideZonePreview(zone, previewEl) {
      if (previewEl) {
        previewEl.classList.remove("is-visible");
        previewEl.removeAttribute("src");
      }
      if (zone) zone.classList.remove("has-file", "has-preview");
    }

    function resetUploadUi() {
      hideZonePreview(uploadZone, uploadPreview);
      if (uploadHint) uploadHint.classList.remove("hidden");
      setFieldStatus(uploadStatus, "", "");
    }

    function restorePasteZoneChildren() {
      if (!pasteZone || !pasteHint || !pastePreview) return;
      pasteZone.textContent = "";
      pasteZone.appendChild(pasteHint);
      pasteZone.appendChild(pastePreview);
    }

    function resetPasteUi() {
      hideZonePreview(pasteZone, pastePreview);
      restorePasteZoneChildren();
      if (pasteZone) {
        pasteZone.contentEditable = "true";
      }
      if (pasteHint) pasteHint.classList.remove("hidden");
      if (pasteChangeHint) pasteChangeHint.classList.add("hidden");
      setFieldStatus(pasteStatus, "", "");
    }

    function clearAll() {
      revokePreview();
      hideRequiredMsg();
      activeSource = null;
      resetUploadUi();
      resetPasteUi();
      if (fileInput) fileInput.value = "";
    }

    function showZonePreview(zone, previewEl, file) {
      if (!file.type.startsWith("image/") || !previewEl || !zone) return;
      revokePreview();
      previewUrl = URL.createObjectURL(file);
      previewEl.src = previewUrl;
      previewEl.classList.add("is-visible");
      zone.classList.add("has-file");
    }

    function displaySelectedFile(file, source) {
      if (!file || !fileInput) return;

      const dt = new DataTransfer();
      dt.items.add(file);
      fileInput.files = dt.files;
      activeSource = source;
      hideRequiredMsg();

      if (source === "upload") {
        resetPasteUi();
        showZonePreview(uploadZone, uploadPreview, file);
        if (uploadHint) uploadHint.classList.add("hidden");
        setFieldStatus(uploadStatus, "", "");
      } else {
        resetUploadUi();
        restorePasteZoneChildren();
        if (pasteZone) {
          pasteZone.classList.add("has-preview");
          if (pasteHint) pasteHint.classList.add("hidden");
        }
        if (pasteChangeHint) pasteChangeHint.classList.remove("hidden");
        showZonePreview(pasteZone, pastePreview, file);
        setFieldStatus(pasteStatus, "", "");
      }
    }

    function fileFromClipboardData(dataTransfer) {
      const items = dataTransfer && dataTransfer.items;
      if (items) {
        for (let i = 0; i < items.length; i += 1) {
          const item = items[i];
          if (item.kind === "file" && item.type.startsWith("image/")) {
            const blob = item.getAsFile();
            if (blob) {
              const ext = (blob.type.split("/")[1] || "png").replace("jpeg", "jpg");
              return new File([blob], "pasted-screenshot." + ext, { type: blob.type });
            }
          }
        }
      }
      const files = dataTransfer && dataTransfer.files;
      if (files) {
        for (let j = 0; j < files.length; j += 1) {
          if (files[j].type.startsWith("image/")) return files[j];
        }
      }
      return null;
    }

    function isFormVisible() {
      return form.offsetParent !== null;
    }

    function pasteFocusActive() {
      const active = document.activeElement;
      return pasteZone && active && (active === pasteZone || pasteZone.contains(active));
    }

    function handlePasteEvent(event) {
      if (!isFormVisible() || !pasteZone) return;
      const inPasteField =
        event.target === pasteZone ||
        pasteZone.contains(event.target) ||
        pasteFocusActive();
      if (!inPasteField) return;

      const file = fileFromClipboardData(event.clipboardData);
      if (!file) {
        setFieldStatus(
          pasteStatus,
          "No image on clipboard — copy your screenshot, tap here, then paste.",
          "error"
        );
        return;
      }
      event.preventDefault();
      displaySelectedFile(file, "paste");
    }

    async function readClipboardImage() {
      if (!navigator.clipboard || !navigator.clipboard.read) return null;
      try {
        const items = await navigator.clipboard.read();
        for (const item of items) {
          const type = item.types.find((t) => t.startsWith("image/"));
          if (!type) continue;
          const blob = await item.getType(type);
          const ext = (type.split("/")[1] || "png").replace("jpeg", "jpg");
          return new File([blob], "pasted-screenshot." + ext, { type });
        }
      } catch {
        return null;
      }
      return null;
    }

    function handleUploadDrop(event) {
      if (!isFormVisible()) return;
      const file = event.dataTransfer && event.dataTransfer.files && event.dataTransfer.files[0];
      if (!file || !file.type.startsWith("image/")) return;
      event.preventDefault();
      displaySelectedFile(file, "upload");
    }

    if (fileInput) {
      fileInput.addEventListener("change", function () {
        const file = fileInput.files && fileInput.files[0];
        if (!file) {
          clearAll();
          return;
        }
        displaySelectedFile(file, "upload");
      });
    }

    if (pasteZone) {
      pasteZone.addEventListener("paste", handlePasteEvent);
      pasteZone.addEventListener("keydown", function (event) {
        if (event.key === "Tab" || event.key === "Escape") return;
        if (event.ctrlKey || event.metaKey) return;
        if (
          (event.key === "Backspace" || event.key === "Delete") &&
          pasteZone.classList.contains("has-preview")
        ) {
          event.preventDefault();
          resetPasteUi();
          pasteZone.focus();
          return;
        }
        if (pasteZone.classList.contains("has-preview")) {
          event.preventDefault();
          return;
        }
        if (event.key.length === 1) {
          event.preventDefault();
        }
      });
      pasteZone.addEventListener("click", function () {
        if (!pasteZone.classList.contains("has-preview")) return;
        resetPasteUi();
        pasteZone.focus();
      });
    }

    if (uploadZone) {
      uploadZone.addEventListener("dragover", function (e) {
        if (!isFormVisible()) return;
        e.preventDefault();
        uploadZone.classList.add("ocr-upload-zone-dragover");
      });
      uploadZone.addEventListener("dragleave", function (e) {
        if (!e.currentTarget.contains(e.relatedTarget)) {
          uploadZone.classList.remove("ocr-upload-zone-dragover");
        }
      });
      uploadZone.addEventListener("drop", function (e) {
        uploadZone.classList.remove("ocr-upload-zone-dragover");
        handleUploadDrop(e);
      });
    }

    function startScanningLabel() {
      if (!btn) return;
      btn.disabled = true;
      btn.setAttribute("aria-busy", "true");
      btn.classList.add("is-scanning");
    }

    form.addEventListener("submit", async function (event) {
      event.preventDefault();
      hideRequiredMsg();
      setFieldStatus(pasteStatus, "", "");

      let hasFile = fileInput && fileInput.files && fileInput.files.length > 0;
      if (!hasFile) {
        const pasted = await readClipboardImage();
        if (pasted) {
          displaySelectedFile(pasted, "paste");
          hasFile = true;
        }
      }

      if (!hasFile) {
        showRequiredMsg(
          "Upload a screenshot, paste into the box above, or copy an image to your clipboard — then tap Scan."
        );
        if (pasteZone) pasteZone.focus();
        return;
      }

      startScanningLabel();
      form.submit();
    });
  }

  function initAll(evt) {

    setupSplitSliderDelegation();

    setupContributionFormatting();

    setupJoinDraftPreservation();

    syncFooterRevisionFromDom();

    initOcrUploadForm(document);

    document.querySelectorAll("[data-parlay-form]").forEach(initParlayForm);

    const swapRoot = evt?.detail?.target || document;

    swapRoot.querySelectorAll("[data-join-form]").forEach(initJoinForm);

    bindContributionFields(document);

    document.querySelectorAll("[data-join-form]").forEach((form) => {

      if (readJoinDraft(form)) setOwnershipPollPaused(true);

    });

  }



  window.initParlayForms = initAll;



  function bootstrapParlayForm() {

    setupSplitSliderDelegation();

    setupContributionFormatting();

    setupJoinDraftPreservation();

    initAll();

  }



  if (document.readyState === "loading") {

    document.addEventListener("DOMContentLoaded", bootstrapParlayForm);

  } else {

    bootstrapParlayForm();

  }



  document.addEventListener("htmx:afterSwap", initAll);

})();


