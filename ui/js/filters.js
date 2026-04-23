/**
 * filters.js
 * Manages sidebar filter controls.
 * Collects values and sends { action: "apply_filters", ...filters } via WS.
 * Listens to "asterix:loaded" to populate controls from file metadata.
 */

const Filters = (() => {
  let autoApplyTimer = null;
  const rangeState = {
    time: { min: null, max: null, start: null, end: null },
    fl: { min: null, max: null, start: null, end: null },
  };
  const rangeBindingState = {
    time: false,
    fl: false,
  };
  const activeRangeDrag = {
    kind: null,
    handle: null,
    pointerId: null,
  };

  const rangeConfig = {
    time: {
      trackId: "f-time-range-track",
      fillId: "f-time-range-fill",
      startThumbId: "f-time-start-thumb",
      endThumbId: "f-time-end-thumb",
      valuesId: "f-time-range-values",
      formatValue: secondsToTimeValue,
      parseValue: parseTimeToSeconds,
      uiPadding: 1,
    },
    fl: {
      trackId: "f-fl-range-track",
      fillId: "f-fl-range-fill",
      startThumbId: "f-fl-min-thumb",
      endThumbId: "f-fl-max-thumb",
      valuesId: "f-fl-range-values",
      formatValue: formatFl,
      parseValue: Number,
      uiPadding: 1,
    },
  };

  function collect() {
    const categorySelection = getChecked("f-categories", { keepEmpty: true });
    const timeRange = isTimeRangeNarrowed() ? getTimeRangeSelection() : null;
    const flRange = isFlRangeNarrowed() ? getFlRangeSelection() : null;

    return {
      time_start: timeRange?.start ?? null,
      time_end: timeRange?.end ?? null,
      fl_min: flRange?.start ?? null,
      fl_max: flRange?.end ?? null,
      fl_keep_null: keepFlNullFilterValue(),
      categories: normalizeCategorySelection(categorySelection),
      target_identifications: getTargetSelection(),
      on_ground: onGroundFilterValue(),
      pure_white: pureWhiteFilterValue(),
    };
  }

  function getActive() {
    return collect();
  }

  function applyFilters() {
    const raw = collect();
    const payload = { action: "apply_filters" };

    Object.entries(raw).forEach(([k, v]) => {
      if (v !== null && v !== undefined) payload[k] = v;
    });

    if (!WS.send(payload)) {
      console.warn("[Filters] WS not ready.");
    }
  }

  function scheduleApplyFilters(delayMs = 180) {
    if (autoApplyTimer) clearTimeout(autoApplyTimer);
    autoApplyTimer = setTimeout(() => applyFilters(), delayMs);
  }

  function resetFilters({ apply = true } = {}) {
    resetTimeRangeToFull();
    resetFlRangeToFull();

    const onGround = document.getElementById("f-on-ground");
    if (onGround) onGround.checked = true;

    const pureWhite = document.getElementById("f-pure-white");
    if (pureWhite) pureWhite.checked = false;

    const keepFlNull = document.getElementById("f-fl-keep-null");
    if (keepFlNull) keepFlNull.checked = true;

    const targetIdentificationAll = document.getElementById("f-target-identification-all");
    if (targetIdentificationAll) targetIdentificationAll.checked = true;

    const fixAll = document.getElementById("f-fix-transponder-all");
    if (fixAll) fixAll.checked = true;

    document.querySelectorAll('[data-filter-group="f-categories"]').forEach(cb => {
      cb.checked = true;
    });
    document.querySelectorAll('[data-filter-group="f-target-identification"]').forEach(cb => {
      cb.checked = true;
    });

    syncAllTargetGroupStates();
    syncSectionMasterToggle("target-identification");
    syncSectionMasterToggle("fix-transponder");
    updateBadge();

    if (apply) {
      scheduleApplyFilters();
    }
  }

  function onDataLoaded(meta) {
    setupTimeRange(meta.time_start, meta.time_end);
    setupFlRange(meta.altitude_min, meta.altitude_max);

    updateCategorySectionVisibility(meta);
    renderCategoryFilter(meta.category_filter_options || ["CAT021", "CAT048"]);
    renderTargetFilters(meta.target_identification_filter || { groups: [], all_values: [] });

    updateBadge();
  }

  function updateCategorySectionVisibility(meta) {
    const section = document.getElementById("f-categories-section");
    if (!section) return;

    const unique = Array.isArray(meta?.unique_categories) ? meta.unique_categories : [];
    const normalized = unique.map(v => String(v || "").trim().toUpperCase());
    const hasBoth = normalized.includes("CAT021") && normalized.includes("CAT048");

    section.style.display = hasBoth ? "" : "none";
  }

  function onSessionCleared() {
    const section = document.getElementById("f-categories-section");
    if (section) section.style.display = "none";
  }

  function renderCategoryFilter(options) {
    const container = document.getElementById("f-categories-container");
    if (!container) return;

    const normalized = Array.isArray(options) && options.length ? options : ["CAT021", "CAT048"];

    container.innerHTML = "";
    normalized.forEach(cat => {
      const label = cat === "CAT021" ? "CAT021 - ADS-B" : cat === "CAT048" ? "CAT048 - Monoradar" : cat;
      container.insertAdjacentHTML(
        "beforeend",
        `<label class="filter-check-item"><input type="checkbox" data-filter-group="f-categories" value="${cat}" checked><span class="filter-check-label">${label}</span></label>`
      );
    });
  }

  function renderTargetFilters(targetFilter) {
    const groups = Array.isArray(targetFilter?.groups) ? targetFilter.groups : [];
    const targetIdentificationGroups = groups.filter(group => group.group_id !== "INDEPENDIENTES");
    const groupedTargetIdentificationGroups = targetIdentificationGroups.filter(group => group.display_mode !== "flat");
    const flatTargetIdentificationGroups = targetIdentificationGroups.filter(group => group.display_mode === "flat");
    const flatTargetMembers = [];
    const targetMemberRows = {};
    flatTargetIdentificationGroups.forEach(group => {
      const members = Array.isArray(group.members) ? group.members : [];
      const rows = group?.member_rows && typeof group.member_rows === "object" ? group.member_rows : {};
      members.forEach(member => {
        flatTargetMembers.push(member);
        const rowCount = Number(rows[member]);
        if (Number.isFinite(rowCount)) targetMemberRows[member] = rowCount;
      });
    });

    const uniqueFlatTargetMembers = [...new Set(flatTargetMembers)];
    const independent = groups.find(group => group.group_id === "INDEPENDIENTES");
    const fixMembers = Array.isArray(independent?.members) ? independent.members : [];
    const fixMemberRows = independent?.member_rows && typeof independent.member_rows === "object"
      ? independent.member_rows
      : {};

    const targetSectionHasFlatMembers = uniqueFlatTargetMembers.length > 0;
    const targetSectionHasGroupedMembers = groupedTargetIdentificationGroups.length > 0;

    renderTargetGroupCollection("f-target-identification-container", groupedTargetIdentificationGroups, "target-identification", "No target identifications detected.", {
      suppressEmptyHint: targetSectionHasFlatMembers,
    });

    renderTargetFlatCollection("f-target-identification-container", uniqueFlatTargetMembers, "target-identification", "No target identifications detected.", {
      append: targetSectionHasGroupedMembers,
      suppressEmptyHint: targetSectionHasGroupedMembers,
      memberRows: targetMemberRows,
    });

    renderTargetFlatCollection("f-fix-transponder-container", fixMembers, "fix-transponder", "No FIX TRANSPONDER targets detected.", {
      memberRows: fixMemberRows,
    });

    bindTargetGroupHandlers();
    bindTargetGroupToggles();
    bindSectionMasterToggles();
    syncAllTargetGroupStates();
    syncSectionMasterToggle("target-identification");
    syncSectionMasterToggle("fix-transponder");
  }

  function renderTargetGroupCollection(containerId, groups, scope, emptyText, options = {}) {
    const { append = false, suppressEmptyHint = false } = options;
    const container = document.getElementById(containerId);
    if (!container) return;

    if (!append) {
      container.innerHTML = "";
    }

    if (!groups.length) {
      if (!append && !suppressEmptyHint) {
        container.innerHTML = `<p class="filter-hint">${emptyText}</p>`;
      }
      return;
    }

    groups.forEach(group => {
      const groupId = safeGroupId(group.group_id || "GROUP");
      const groupLabel = group.group_label || group.group_id || "Group";
      const members = Array.isArray(group.members) ? group.members : [];
      const rows = group?.member_rows && typeof group.member_rows === "object" ? group.member_rows : {};
      const memberCount = Number.isFinite(Number(group.member_count))
        ? Number(group.member_count)
        : members.length;

      const wrapper = document.createElement("div");
      wrapper.className = "target-group-block";
      wrapper.classList.add("collapsed");
      wrapper.dataset.targetGroupId = groupId;
      wrapper.innerHTML = `
        <div class="target-group-head-row">
          <button type="button" class="target-group-toggle" data-target-group-toggle="${groupId}" aria-label="Toggle ${groupLabel}">&#9660;</button>
          <label class="filter-check-item target-group-header">
            <input type="checkbox" data-target-group-checkbox="${groupId}" data-target-scope="${scope}" checked>
            <span class="filter-check-label">${groupLabel} (${memberCount})</span>
          </label>
        </div>
        <div class="target-group-members" id="target-members-${groupId}"></div>
      `;

      const membersContainer = wrapper.querySelector(`#target-members-${groupId}`);
      members.forEach(member => {
        const memberLabel = member === "__NOT_IDENTIFIED__" ? "NOT IDENTIFIED" : member;
        const rowCount = Number(rows[member]);
        const rowLabel = Number.isFinite(rowCount) ? ` (${rowCount})` : "";
        membersContainer.insertAdjacentHTML(
          "beforeend",
          `<label class="filter-check-item target-member-item"><input type="checkbox" data-filter-group="f-target-identification" data-target-member-group="${groupId}" data-target-scope="${scope}" value="${member}" checked><span class="filter-check-label">${memberLabel}${rowLabel}</span></label>`
        );
      });

      container.appendChild(wrapper);
    });
  }

  function renderTargetFlatCollection(containerId, members, scope, emptyText, options = {}) {
    const { append = false, suppressEmptyHint = false, memberRows = {} } = options;
    const container = document.getElementById(containerId);
    if (!container) return;

    if (!append) {
      container.innerHTML = "";
    }

    if (!members.length) {
      if (!append && !suppressEmptyHint) {
        container.innerHTML = `<p class="filter-hint">${emptyText}</p>`;
      }
      return;
    }

    members.forEach(member => {
      const memberLabel = member === "__NOT_IDENTIFIED__" ? "NOT IDENTIFIED" : member;
      const rowCount = Number(memberRows[member]);
      const rowLabel = Number.isFinite(rowCount) ? ` (${rowCount})` : "";
      container.insertAdjacentHTML(
        "beforeend",
        `<label class="filter-check-item target-member-item"><input type="checkbox" data-filter-group="f-target-identification" data-target-scope="${scope}" value="${member}" checked><span class="filter-check-label">${memberLabel}${rowLabel}</span></label>`
      );
    });
  }

  function safeGroupId(raw) {
    return String(raw).replace(/[^a-zA-Z0-9_-]/g, "_");
  }

  function bindTargetGroupHandlers() {
    document.querySelectorAll("[data-target-group-checkbox]").forEach(groupCheckbox => {
      groupCheckbox.onchange = () => {
        const groupId = groupCheckbox.dataset.targetGroupCheckbox;
        const scope = groupCheckbox.dataset.targetScope;
        const members = document.querySelectorAll(`[data-target-member-group="${groupId}"]`);
        members.forEach(memberCb => {
          memberCb.checked = groupCheckbox.checked;
        });
        syncGroupState(groupId);
        if (scope) syncSectionMasterToggle(scope);
        updateBadge();
        scheduleApplyFilters();
      };
    });

    document.querySelectorAll("[data-target-member-group]").forEach(memberCheckbox => {
      memberCheckbox.onchange = () => {
        const groupId = memberCheckbox.dataset.targetMemberGroup;
        const scope = memberCheckbox.dataset.targetScope;
        if (groupId) syncGroupState(groupId);
        if (scope) syncSectionMasterToggle(scope);
        updateBadge();
        scheduleApplyFilters();
      };
    });
  }

  function bindTargetGroupToggles() {
    document.querySelectorAll("[data-target-group-toggle]").forEach(toggle => {
      toggle.onclick = e => {
        e.preventDefault();
        e.stopPropagation();
        const groupId = toggle.dataset.targetGroupToggle;
        if (!groupId) return;
        const wrapper = document.querySelector(`[data-target-group-id="${groupId}"]`);
        if (!wrapper) return;
        wrapper.classList.toggle("collapsed");
      };
    });
  }

  function bindSectionMasterToggles() {
    const sections = [
      { checkboxId: "f-target-identification-all", scope: "target-identification" },
      { checkboxId: "f-fix-transponder-all", scope: "fix-transponder" },
    ];

    sections.forEach(({ checkboxId, scope }) => {
      const master = document.getElementById(checkboxId);
      if (!master) return;

      master.onchange = () => {
        const members = document.querySelectorAll(`[data-filter-group="f-target-identification"][data-target-scope="${scope}"]`);
        const groups = document.querySelectorAll(`[data-target-group-checkbox][data-target-scope="${scope}"]`);

        members.forEach(cb => {
          cb.checked = master.checked;
        });

        groups.forEach(cb => {
          cb.checked = master.checked;
          cb.indeterminate = false;
        });

        syncAllTargetGroupStates();
        syncSectionMasterToggle(scope);
        updateBadge();
        scheduleApplyFilters();
      };
    });
  }

  function syncSectionMasterToggle(scope) {
    const checkboxId = scope === "target-identification" ? "f-target-identification-all" : "f-fix-transponder-all";
    const master = document.getElementById(checkboxId);
    if (!master) return;

    const members = [...document.querySelectorAll(`[data-filter-group="f-target-identification"][data-target-scope="${scope}"]`)];
    if (!members.length) {
      master.checked = true;
      master.indeterminate = false;
      return;
    }

    const selected = members.filter(cb => cb.checked).length;
    if (selected === 0) {
      master.checked = false;
      master.indeterminate = false;
      return;
    }

    if (selected === members.length) {
      master.checked = true;
      master.indeterminate = false;
      return;
    }

    master.checked = false;
    master.indeterminate = true;
  }

  function syncAllTargetGroupStates() {
    document.querySelectorAll("[data-target-group-checkbox]").forEach(groupCheckbox => {
      syncGroupState(groupCheckbox.dataset.targetGroupCheckbox);
    });
  }

  function syncGroupState(groupId) {
    const groupCheckbox = document.querySelector(`[data-target-group-checkbox="${groupId}"]`);
    if (!groupCheckbox) return;

    const members = [...document.querySelectorAll(`[data-target-member-group="${groupId}"]`)];
    if (!members.length) {
      groupCheckbox.indeterminate = false;
      groupCheckbox.checked = false;
      return;
    }

    const selectedCount = members.filter(member => member.checked).length;
    if (selectedCount === 0) {
      groupCheckbox.checked = false;
      groupCheckbox.indeterminate = false;
      return;
    }

    if (selectedCount === members.length) {
      groupCheckbox.checked = true;
      groupCheckbox.indeterminate = false;
      return;
    }

    groupCheckbox.checked = false;
    groupCheckbox.indeterminate = true;
  }

  function updateResetButtonState() {
    const f = collect();
    const resetBtn = document.getElementById("btn-reset-filters");
    if (!resetBtn) return;

    const dirty = isTimeRangeNarrowed()
      || isFlRangeNarrowed()
      || f.fl_keep_null === false
      || f.on_ground === false
      || f.pure_white === true
      || Array.isArray(f.categories)
      || Array.isArray(f.target_identifications);

    resetBtn.disabled = !dirty;
  }

  function updateBadge() {
    updateResetButtonState();
  }

  function initSections() {
    document.querySelectorAll(".filter-header-marker input").forEach(input => {
      input.addEventListener("click", e => e.stopPropagation());
      input.addEventListener("change", e => e.stopPropagation());
    });

    document.querySelectorAll(".filter-header-marker").forEach(label => {
      label.addEventListener("click", e => e.stopPropagation());
    });

    document.querySelectorAll(".sidebar-section-header").forEach(h => {
      if (h.classList.contains("static")) return;
      h.addEventListener("click", () => h.closest(".sidebar-section").classList.toggle("collapsed"));
    });
  }

  const val = id => document.getElementById(id)?.value?.trim() ?? "";

  function getChecked(group, { keepEmpty = false } = {}) {
    const v = [...document.querySelectorAll(`[data-filter-group="${group}"]:checked`)].map(c => c.value);
    if (v.length) return v;
    return keepEmpty ? [] : null;
  }

  function normalizeCategorySelection(selected) {
    const total = document.querySelectorAll('[data-filter-group="f-categories"]').length;
    if (!Array.isArray(selected)) return null;
    if (selected.length === 0) return [];
    if (total > 0 && selected.length === total) return null;
    return selected;
  }

  function getTargetSelection() {
    const all = [...document.querySelectorAll('[data-filter-group="f-target-identification"]')];
    if (!all.length) return null;

    const selected = all.filter(cb => cb.checked).map(cb => cb.value);
    if (selected.length === 0) return [];
    if (selected.length === all.length) return null;
    return selected;
  }

  function onGroundFilterValue() {
    const onGround = document.getElementById("f-on-ground");
    if (!onGround) return null;
    return onGround.checked ? null : false;
  }

  function pureWhiteFilterValue() {
    const pureWhite = document.getElementById("f-pure-white");
    if (!pureWhite) return null;
    return pureWhite.checked ? true : null;
  }

  function keepFlNullFilterValue() {
    const keepFlNull = document.getElementById("f-fl-keep-null");
    if (!keepFlNull) return true;
    return keepFlNull.checked;
  }

  function parseSquawks(raw) {
    if (!raw) return null;
    const v = raw.split(",").map(s => s.trim()).filter(Boolean);
    return v.length ? v : null;
  }

  function bindRangeControls() {
    Object.keys(rangeConfig).forEach(kind => {
      if (rangeBindingState[kind]) return;
      const config = rangeConfig[kind];
      const track = document.getElementById(config.trackId);
      const startThumb = document.getElementById(config.startThumbId);
      const endThumb = document.getElementById(config.endThumbId);

      if (!track || !startThumb || !endThumb) return;

      const onThumbDown = (handle, event) => {
        if (event.button !== 0) return;
        event.preventDefault();
        startRangeDrag(kind, handle, event);
      };

      track.addEventListener("pointerdown", event => {
        if (event.target.closest(".range-thumb")) return;
        if (event.button !== 0) return;
        event.preventDefault();

        const value = rangeValueFromPointer(kind, event);
        if (!Number.isFinite(value)) return;

        const state = rangeState[kind];
        const handle = Math.abs(value - state.start) <= Math.abs(value - state.end) ? "start" : "end";
        startRangeDrag(kind, handle, event, value);
      });

      startThumb.addEventListener("pointerdown", event => onThumbDown("start", event));
      endThumb.addEventListener("pointerdown", event => onThumbDown("end", event));

      startThumb.addEventListener("keydown", event => handleRangeKeydown(kind, "start", event));
      endThumb.addEventListener("keydown", event => handleRangeKeydown(kind, "end", event));

      rangeBindingState[kind] = true;
    });

    window.addEventListener("pointermove", handleRangePointerMove);
    window.addEventListener("pointerup", endRangeDrag);
    window.addEventListener("pointercancel", endRangeDrag);
  }

  function setupRange(kind, minValue, maxValue) {
    const state = rangeState[kind];
    const config = rangeConfig[kind];
    const padding = Number(config?.uiPadding ?? 0);
    const min = kind === "time"
      ? normalizeRangeMin(parseTimeToSeconds(minValue), 0)
      : normalizeRangeMin(minValue, 0);
    const max = kind === "time"
      ? normalizeRangeMax(parseTimeToSeconds(maxValue), min)
      : normalizeRangeMax(maxValue, min);

    const paddedMin = kind === "time"
      ? Math.max(0, min - padding)
      : (min - padding);
    const paddedMax = max + padding;

    state.min = paddedMin;
    state.max = paddedMax;
    state.start = paddedMin;
    state.end = paddedMax;
    renderRangeControl(kind);
  }

  function setupTimeRange(minValue, maxValue) {
    setupRange("time", minValue, maxValue);
  }

  function setupFlRange(minValue, maxValue) {
    setupRange("fl", minValue, maxValue);
  }

  function getTimeRangeSelection() {
    return getRangeSelection("time");
  }

  function getFlRangeSelection() {
    return getRangeSelection("fl");
  }

  function resetTimeRangeToFull() {
    resetRangeToFull("time");
  }

  function resetFlRangeToFull() {
    resetRangeToFull("fl");
  }

  function isTimeRangeNarrowed() {
    const selected = getTimeRangeSelection();
    if (!selected) return false;
    const min = rangeState.time.min;
    const max = rangeState.time.max;
    if (!Number.isFinite(min) || !Number.isFinite(max)) return false;
    return selected.start > (min + 0.5) || selected.end < (max - 0.5);
  }

  function isFlRangeNarrowed() {
    const selected = getFlRangeSelection();
    if (!selected) return false;
    const min = rangeState.fl.min;
    const max = rangeState.fl.max;
    if (!Number.isFinite(min) || !Number.isFinite(max)) return false;
    return selected.start > min || selected.end < max;
  }

  function getRangeSelection(kind) {
    const state = rangeState[kind];
    if (!state) return null;
    if (!Number.isFinite(state.start) || !Number.isFinite(state.end)) return null;
    return { start: state.start, end: state.end };
  }

  function resetRangeToFull(kind) {
    const state = rangeState[kind];
    if (!state || !Number.isFinite(state.min) || !Number.isFinite(state.max)) return;
    state.start = state.min;
    state.end = state.max;
    renderRangeControl(kind);
  }

  function renderRangeControl(kind) {
    const state = rangeState[kind];
    const config = rangeConfig[kind];
    if (!state || !config) return;
    updateRangeVisual(
      config.fillId,
      state.min,
      state.max,
      state.start,
      state.end,
      {
        kind,
        startThumbId: config.startThumbId,
        endThumbId: config.endThumbId,
        valuesId: config.valuesId,
      }
    );
  }

  function clampRangeValue(value, min, max) {
    if (!Number.isFinite(value)) return min;
    return Math.min(max, Math.max(min, value));
  }

  function setRangeSelection(kind, startValue, endValue, lockHandle = null) {
    const state = rangeState[kind];
    if (!state || !Number.isFinite(state.min) || !Number.isFinite(state.max)) return null;

    let start = clampRangeValue(Math.round(Number(startValue)), state.min, state.max);
    let end = clampRangeValue(Math.round(Number(endValue)), state.min, state.max);

    if (lockHandle === "start") {
      start = Math.min(start, end);
    } else if (lockHandle === "end") {
      end = Math.max(start, end);
    } else if (start > end) {
      [start, end] = [end, start];
    }

    state.start = start;
    state.end = end;
    renderRangeControl(kind);
    return { start, end };
  }

  function rangeValueFromPointer(kind, event) {
    const state = rangeState[kind];
    const config = rangeConfig[kind];
    const track = document.getElementById(config.trackId);
    if (!state || !track || !Number.isFinite(state.min) || !Number.isFinite(state.max)) return NaN;

    const rect = track.getBoundingClientRect();
    if (rect.width <= 0) return NaN;

    const pct = Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width));
    return state.min + ((state.max - state.min) * pct);
  }

  function startRangeDrag(kind, handle, event, valueOverride = null) {
    const state = rangeState[kind];
    if (!state) return;

    const config = rangeConfig[kind];
    const thumbId = handle === "start" ? config.startThumbId : config.endThumbId;
    document.getElementById(thumbId)?.focus({ preventScroll: true });

    const dragTarget = event.currentTarget;
    if (dragTarget && typeof dragTarget.setPointerCapture === "function") {
      try {
        dragTarget.setPointerCapture(event.pointerId);
      } catch {
        // Ignore capture failures; the window listeners still keep the drag usable.
      }
    }

    activeRangeDrag.kind = kind;
    activeRangeDrag.handle = handle;
    activeRangeDrag.pointerId = event.pointerId;
    document.body.classList.add("range-dragging");

    if (valueOverride !== null) {
      if (handle === "start") {
        setRangeSelection(kind, valueOverride, state.end, "start");
      } else {
        setRangeSelection(kind, state.start, valueOverride, "end");
      }
      updateBadge();
      scheduleApplyFilters();
      return;
    }

    handleRangePointerMove(event);
  }

  function handleRangePointerMove(event) {
    if (!activeRangeDrag.kind || event.pointerId !== activeRangeDrag.pointerId) return;

    const kind = activeRangeDrag.kind;
    const state = rangeState[kind];
    if (!state) return;

    const value = rangeValueFromPointer(kind, event);
    if (!Number.isFinite(value)) return;

    if (activeRangeDrag.handle === "start") {
      setRangeSelection(kind, value, state.end, "start");
    } else {
      setRangeSelection(kind, state.start, value, "end");
    }

    updateBadge();
    scheduleApplyFilters();
  }

  function endRangeDrag(event) {
    if (!activeRangeDrag.kind || event.pointerId !== activeRangeDrag.pointerId) return;
    activeRangeDrag.kind = null;
    activeRangeDrag.handle = null;
    activeRangeDrag.pointerId = null;
    document.body.classList.remove("range-dragging");
  }

  function handleRangeKeydown(kind, handle, event) {
    const state = rangeState[kind];
    if (!state || !Number.isFinite(state.min) || !Number.isFinite(state.max)) return;

    let delta = 0;
    if (event.key === "ArrowLeft" || event.key === "ArrowDown") {
      delta = -1;
    } else if (event.key === "ArrowRight" || event.key === "ArrowUp") {
      delta = 1;
    } else if (event.key === "Home") {
      event.preventDefault();
      if (handle === "start") {
        setRangeSelection(kind, state.min, state.end, "start");
      } else {
        setRangeSelection(kind, state.start, state.min, "end");
      }
      updateBadge();
      scheduleApplyFilters();
      return;
    } else if (event.key === "End") {
      event.preventDefault();
      if (handle === "start") {
        setRangeSelection(kind, state.max, state.end, "start");
      } else {
        setRangeSelection(kind, state.start, state.max, "end");
      }
      updateBadge();
      scheduleApplyFilters();
      return;
    } else {
      return;
    }

    if (event.shiftKey) {
      delta *= 10;
    }

    event.preventDefault();

    if (handle === "start") {
      setRangeSelection(kind, state.start + delta, state.end, "start");
    } else {
      setRangeSelection(kind, state.start, state.end + delta, "end");
    }

    updateBadge();
    scheduleApplyFilters();
  }

  function formatFl(value) {
    return `FL ${Math.round(Number(value))}`;
  }

  function secondsToTimeValue(totalSeconds) {
    const sec = Math.max(0, Math.floor(Number(totalSeconds) || 0)) % 86400;
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = sec % 60;
    const pad = n => String(n).padStart(2, "0");
    return `${pad(h)}:${pad(m)}:${pad(s)}`;
  }

  function parseTimeToSeconds(value) {
    if (!value) return NaN;
    if (typeof value === "number" && Number.isFinite(value)) {
      return Math.max(0, Math.floor(value));
    }

    const text = String(value).trim();

    const m = text.match(/^(\d{1,2}):(\d{2})(?::(\d{2}))?(?::\d{1,3})?$/);
    if (!m) return NaN;

    const h = Number(m[1]);
    const min = Number(m[2]);
    const sec = Number(m[3] ?? "0");
    if (!Number.isFinite(h) || !Number.isFinite(min) || !Number.isFinite(sec)) return NaN;
    if (h < 0 || h > 23 || min < 0 || min > 59 || sec < 0 || sec > 59) return NaN;

    return (h * 3600) + (min * 60) + sec;
  }

  function updateRangeVisual(fillId, absoluteMin, absoluteMax, selectedMin, selectedMax, options = {}) {
    const fill = document.getElementById(fillId);
    if (!fill) return;

    const startThumb = options.startThumbId ? document.getElementById(options.startThumbId) : null;
    const endThumb = options.endThumbId ? document.getElementById(options.endThumbId) : null;
    const valuesEl = options.valuesId ? document.getElementById(options.valuesId) : null;
    const kind = options.kind ?? null;

    const min = Number(absoluteMin);
    const max = Number(absoluteMax);
    const start = Number(selectedMin);
    const end = Number(selectedMax);
    if (!Number.isFinite(min) || !Number.isFinite(max) || !Number.isFinite(start) || !Number.isFinite(end) || max <= min) {
      fill.style.left = "0%";
      fill.style.width = "100%";

      if (valuesEl && Number.isFinite(start) && Number.isFinite(end)) {
        valuesEl.textContent = kind === "time"
          ? `${secondsToTimeValue(start)}  -  ${secondsToTimeValue(end)}`
          : `${formatFl(start)}  -  ${formatFl(end)}`;
      }

      return;
    }

    const leftPct = ((Math.max(min, Math.min(start, max)) - min) / (max - min)) * 100;
    const rightPct = ((Math.max(min, Math.min(end, max)) - min) / (max - min)) * 100;
    const widthPct = Math.max(0, rightPct - leftPct);

    fill.style.left = `${leftPct}%`;
    fill.style.width = `${widthPct}%`;

    if (startThumb) {
      startThumb.style.left = `${leftPct}%`;
      startThumb.setAttribute("aria-valuemin", String(min));
      startThumb.setAttribute("aria-valuemax", String(max));
      startThumb.setAttribute("aria-valuenow", String(Math.round(Math.max(min, Math.min(start, max)))));
      startThumb.setAttribute(
        "aria-valuetext",
        kind === "time" ? secondsToTimeValue(start) : formatFl(start)
      );
    }

    if (endThumb) {
      endThumb.style.left = `${rightPct}%`;
      endThumb.setAttribute("aria-valuemin", String(min));
      endThumb.setAttribute("aria-valuemax", String(max));
      endThumb.setAttribute("aria-valuenow", String(Math.round(Math.max(min, Math.min(end, max)))));
      endThumb.setAttribute(
        "aria-valuetext",
        kind === "time" ? secondsToTimeValue(end) : formatFl(end)
      );
    }

    if (valuesEl) {
      valuesEl.textContent = kind === "time"
        ? `${secondsToTimeValue(start)}  -  ${secondsToTimeValue(end)}`
        : `${formatFl(start)}  -  ${formatFl(end)}`;
    }
  }

  function normalizeRangeMin(value, fallback) {
    const n = Number(value);
    return Number.isFinite(n) ? n : fallback;
  }

  function normalizeRangeMax(value, minValue) {
    const n = Number(value);
    if (!Number.isFinite(n)) return minValue;
    return Math.max(minValue, n);
  }

  function init() {
    initSections();
    bindRangeControls();

    document.getElementById("btn-reset-filters")?.addEventListener("click", resetFilters);

    document.getElementById("sidebar")?.addEventListener("change", () => {
      updateBadge();
      scheduleApplyFilters();
    });

    document.getElementById("sidebar")?.addEventListener("input", () => {
      updateBadge();
      scheduleApplyFilters();
    });

    window.addEventListener("asterix:loaded", e => onDataLoaded(e.detail));
    window.addEventListener("asterix:session-cleared", onSessionCleared);

    WS.on("apply_filters_result", payload => {
      window.dispatchEvent(new CustomEvent("asterix:filters-applied", {
        detail: payload?.data || {},
      }));
    });

    updateBadge();
  }

  return { init, getActive, applyFilters, resetFilters };
})();

document.addEventListener("DOMContentLoaded", () => Filters.init());
