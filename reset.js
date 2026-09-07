(function () {
    if (document.getElementById("resetStudioButton")) {
        return;
    }
    const panel = document.querySelector(".ncl-panel");
    if (!panel) {
        return;
    }
    const wrap = document.createElement("div");
    wrap.id = "resetStudioWrap";
    wrap.style.cssText = "margin-top:16px;display:flex;align-items:center;gap:12px;flex-wrap:wrap;";
    wrap.innerHTML =
        '<button type="button" id="resetStudioButton" class="ncl-button" style="background:transparent;border:1px solid rgba(127,227,196,.35);color:#7fe3c4;">CLEAR SEARCH & RESULTS</button>' +
        '<span style="color:#9fb3ad;font-size:13px;">Clears the ship box, itinerary box, dates, and results. Screenshots stay unless you remove them.</span>';
    panel.appendChild(wrap);

    document.getElementById("resetStudioButton").addEventListener("click", function () {
        ["shipName", "nclUrl", "itineraryName"].forEach(function (id) {
            const el = document.getElementById(id);
            if (el) el.value = "";
        });
        ["sailMonth", "sailYear", "itineraryMonth", "itineraryYear", "destination"].forEach(function (id) {
            const el = document.getElementById(id);
            if (!el) return;
            el.value = "";
            if (el.tagName === "SELECT" && el.options.length) el.selectedIndex = 0;
        });
        const results = document.getElementById("results");
        if (results) results.innerHTML = "";
        const status = document.getElementById("status");
        if (status) {
            status.className = "status";
            status.textContent = "Search cleared.";
        }
        const detected = document.getElementById("detectedCount");
        if (detected) detected.textContent = "";
        const processing = document.getElementById("processing") || document.querySelector(".processing");
        if (processing) processing.style.display = "none";
    });
})();
