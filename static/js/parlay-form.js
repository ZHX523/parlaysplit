/**

 * Parlay form: live payout + dynamic legs (vanilla JS — no Alpine dependency).

 */

(function () {

  function parseWager(str) {

    if (str == null || str === "") return null;

    const n = parseFloat(String(str).replace(/[$,\s]/g, ""));

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



  function calcPayout(wager, odds) {

    const w = typeof wager === "number" ? wager : parseWager(wager);

    const o = parseInt(odds, 10);

    if (!w || w <= 0 || !o || o === 0 || Number.isNaN(o)) {

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

    const hostEl = root.querySelector("[data-split-host-pct]");

    if (!friendsEl || !hostEl) return;

    const split = splitRawValueFromRoot(root);

    if (split == null) {

      friendsEl.textContent = "—";

      hostEl.textContent = "—";

      return;

    }

    const friendsPct = Math.round(split);

    const hostPct = Math.round(100 - split);

    friendsEl.textContent = friendsPct + "%";

    hostEl.textContent = hostPct + "%";

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

      if (n != null) el.value = n.toFixed(2);

    });



    el.addEventListener("blur", formatIfValid);



    if (onInput) el.addEventListener("input", onInput);

  }



  function bindWagerField(el, root) {

    if (!el) return;

    bindCurrencyField(el, () => updatePayout(root));

  }



  function bindContributionField(el) {

    bindCurrencyField(el);

  }



  function formatContributionFields(root) {

    root.querySelectorAll("[data-format-contribution]").forEach((el) => {

      const n = parseWager(el.value);

      el.value = n != null ? formatWager(n) : "";

    });

  }



  function initJoinForm(root) {

    if (!root) return;

    formatContributionFields(root);

    root.querySelectorAll("[data-format-contribution]").forEach(bindContributionField);



    const form = root.matches("[data-join-form]") ? root : root.querySelector("[data-join-form]");

    if (!form || form._joinSubmitBound) return;

    form._joinSubmitBound = true;



    form.addEventListener("submit", () => {

      const el = form.querySelector("[data-format-contribution]");

      if (!el) return;

      const n = parseWager(el.value);

      el.value = n != null ? n.toFixed(2) : "";

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

    if (document.body._splitSliderDelegation) return;

    document.body._splitSliderDelegation = true;



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

    const wager = root.querySelector('[name="wager_amount"]');

    const split = root.querySelector('[name="split_offered_percent"]');

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

    root.querySelectorAll("[data-leg-row]").forEach((row) => {

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

    const rows = root.querySelectorAll("[data-leg-row]");

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

    root.querySelectorAll("[data-leg-row]").forEach((row, i) => {

      const label = row.querySelector("[data-leg-label]");

      if (label) label.textContent = "Leg " + (i + 1);

    });

  }



  function updateAddButton(root, maxLegs) {

    const btn = root.querySelector("[data-add-leg]");

    const count = root.querySelectorAll("[data-leg-row]").length;

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



  function initParlayForm(root) {

    const maxLegs = parseInt(root.dataset.maxLegs || "20", 10);

    const legsReady = root._parlayLegsReady;



    setupLegTypeHintListeners(root);



    if (!legsReady) {

      root._parlayLegsReady = true;

      root.querySelectorAll("[data-leg-row]").forEach((row) => bindLegRow(row, root, maxLegs));

    }



    syncAllLegDescriptionPlaceholders(root);



    const odds = root.querySelector('[name="odds_american"]');

    const wager = root.querySelector('[name="wager_amount"]');

    const split = root.querySelector('[name="split_offered_percent"]');



    bindWagerField(wager, root);

    bindSplitField(split, root);

    initSplitSliders(root);

    bindFormSubmit(root);



    if (odds && !odds._oddsBound) {

      odds._oddsBound = true;

      odds.addEventListener("input", () => updatePayout(root));

    }



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



  function initAll() {

    setupSplitSliderDelegation();

    document.querySelectorAll("[data-parlay-form]").forEach(initParlayForm);

    document.querySelectorAll("[data-join-form]").forEach(initJoinForm);

  }



  window.initParlayForms = initAll;



  setupSplitSliderDelegation();



  if (document.readyState === "loading") {

    document.addEventListener("DOMContentLoaded", initAll);

  } else {

    initAll();

  }



  document.body.addEventListener("htmx:afterSwap", initAll);

})();


