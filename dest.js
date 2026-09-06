(function () {
    if (document.getElementById("itineraryPanel")) {
        return;
    }

    const fields = document.querySelector(".ncl-fields");
    const shipButton = document.getElementById("nclButton");
    if (!fields || !shipButton) {
        return;
    }

    const oldDest = document.getElementById("destination");
    const oldName = document.getElementById("itineraryName");
    if (oldDest && oldDest.closest(".field-block")) oldDest.closest(".field-block").remove();
    if (oldName && oldName.closest(".field-block")) oldName.closest(".field-block").remove();

    const title = document.querySelector(".ncl-panel-head h3");
    if (title) title.textContent = "Two ways to pull sailings. Fill one box, then tap that box's button.";

    const shipHint = document.createElement("div");
    shipHint.className = "section-kicker";
    shipHint.style.margin = "0 0 8px";
    shipHint.textContent = "OPTION 1 — SEARCH BY SHIP";
    fields.parentNode.insertBefore(shipHint, fields);

    const shipHelp = document.createElement("p");
    shipHelp.style.cssText = "margin:0 0 10px;color:#9fb3ad;font-size:13px;max-width:720px;";
    shipHelp.textContent = "Use this if you know the ship. Example: Pride of America + May + 2027.";
    fields.parentNode.insertBefore(shipHelp, fields);

    shipButton.textContent = "PULL BY SHIP →";
    const freshShip = shipButton.cloneNode(true);
    shipButton.parentNode.replaceChild(freshShip, shipButton);

    const yearSource = document.getElementById("sailYear");
    const yearOptions = yearSource ? yearSource.innerHTML : '<option value="">Any</option>';

    const panel = document.createElement("div");
    panel.id = "itineraryPanel";
    panel.style.cssText = "margin-top:22px;padding-top:18px;border-top:1px solid rgba(127,227,196,.16);";
    panel.innerHTML =
        '<div class="section-kicker">OPTION 2 — SEARCH BY ITINERARY</div>' +
        '<p style="margin:8px 0 12px;color:#9fb3ad;font-size:13px;max-width:720px;">Type the trip name, pick THAT row\'s month and year, then tap PULL BY ITINERARY. Example: Baltic Capitals + May + 2027.</p>' +
        '<div class="ncl-fields">' +
            '<div class="field-block" style="flex:1.4;">' +
                '<label for="itineraryName">ITINERARY NAME</label>' +
                '<input id="itineraryName" list="nclItineraries" placeholder="Baltic Capitals, Caribbean, Alaska..." autocomplete="off">' +
                '<datalist id="nclItineraries">' +
                    '<option value="Baltic Capitals"></option>' +
                    '<option value="Caribbean"></option>' +
                    '<option value="Alaska"></option>' +
                    '<option value="Greek Isles"></option>' +
                    '<option value="Hawaii"></option>' +
                    '<option value="Bermuda"></option>' +
                    '<option value="Panama Canal"></option>' +
                    '<option value="Mexican Riviera"></option>' +
                    '<option value="Canada & New England"></option>' +
                    '<option value="Transatlantic"></option>' +
                    '<option value="Norwegian Fjords"></option>' +
                    '<option value="Bahamas"></option>' +
                    '<option value="Mediterranean"></option>' +
                '</datalist>' +
            '</div>' +
            '<div class="field-block">' +
                '<label for="itineraryMonth">MONTH</label>' +
                '<select id="itineraryMonth">' +
                    '<option value="">Month</option>' +
                    '<option value="1">January</option>' +
                    '<option value="2">February</option>' +
                    '<option value="3">March</option>' +
                    '<option value="4">April</option>' +
                    '<option value="5">May</option>' +
                    '<option value="6">June</option>' +
                    '<option value="7">July</option>' +
                    '<option value="8">August</option>' +
                    '<option value="9">September</option>' +
                    '<option value="10">October</option>' +
                    '<option value="11">November</option>' +
                    '<option value="12">December</option>' +
                '</select>' +
            '</div>' +
            '<div class="field-block">' +
                '<label for="itineraryYear">YEAR</label>' +
                '<select id="itineraryYear">' + yearOptions + '</select>' +
            '</div>' +
            '<button type="button" id="itineraryButton" class="ncl-button">PULL BY ITINERARY →</button>' +
        '</div>';

    const urlRow = document.querySelector(".ncl-url-row");
    (urlRow || fields).insertAdjacentElement("afterend", panel);

    const regions = {
        africa: "AFRICA", alaska: "ALASKA", asia: "ASIA", australia: "AUSTRALIA",
        bahamas: "BAHAMAS", bermuda: "BERMUDA", caribbean: "CARIBBEAN",
        hawaii: "HAWAII", mediterranean: "MEDITERRANEAN",
        "greek isles": "GREEK_ISLES", "mexican riviera": "MEXICAN_RIVIERA",
        "northern europe": "NORTHERN_EUROPE", "panama canal": "PANAMA_CANAL",
        "south pacific": "SOUTH_PACIFIC", transatlantic: "TRANSATLANTIC",
        "canada & new england": "CANADA_NEW_ENGL"
    };

    async function pullFromNcl(payload, buttonEl) {
        buttonEl.disabled = true;
        const analyzeButton = document.getElementById("analyzeButton");
        if (analyzeButton) analyzeButton.disabled = true;
        const status = document.getElementById("status");
        if (status) {
            status.className = "status";
            status.textContent = "Searching NCL.com...";
        }
        let lastError;
        for (let attempt = 0; attempt < 2; attempt += 1) {
            try {
                const response = await fetch("/api/ncl-lookup", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });
                const data = await response.json();
                if (!response.ok) throw new Error(data.error || "Could not pull sailings from NCL.com.");
                const rows = Array.isArray(data.itineraries) ? data.itineraries : [];
                if (!rows.length) throw new Error("No matching NCL sailings were found.");
                if (typeof applyItineraries === "function") applyItineraries(rows, "NCL.com");
                if (status) {
                    status.className = "status success";
                    status.textContent = "Pulled " + rows.length + " sailing" + (rows.length === 1 ? "" : "s") + " from NCL.com.";
                }
                lastError = null;
                break;
            } catch (error) {
                lastError = error;
                if (attempt === 0) await new Promise(function (ok) { setTimeout(ok, 1200); });
            }
        }
        if (lastError) {
            let message = lastError.message || "Could not pull sailings from NCL.com.";
            if (/failed to fetch|networkerror|load failed/i.test(message)) {
                message = "The itinerary search dropped. Pick a month AND year in Option 2, then tap PULL BY ITINERARY once.";
            }
            const results = document.getElementById("results");
            if (results) {
                results.innerHTML = '<div class="error-result"></div>';
                results.firstChild.textContent = message;
            }
            if (status) {
                status.className = "status error";
                status.textContent = message;
            }
        }
        buttonEl.disabled = false;
        if (analyzeButton) analyzeButton.disabled = false;
    }

    freshShip.addEventListener("click", function () {
        const shipName = (document.getElementById("shipName") || {}).value.trim();
        const month = (document.getElementById("sailMonth") || {}).value;
        const year = (document.getElementById("sailYear") || {}).value;
        const nclUrl = (document.getElementById("nclUrl") || {}).value.trim();
        if (!shipName && !nclUrl) {
            alert("Option 1: type a ship name, pick month and year, then tap PULL BY SHIP.");
            return;
        }
        pullFromNcl({
            shipName: shipName,
            month: month ? Number(month) : null,
            year: year ? Number(year) : null,
            url: nclUrl,
            destination: "",
            query: ""
        }, freshShip);
    });

    const itineraryButton = document.getElementById("itineraryButton");
    itineraryButton.addEventListener("click", function () {
        const itineraryName = (document.getElementById("itineraryName") || {}).value.trim();
        const month = (document.getElementById("itineraryMonth") || {}).value;
        const year = (document.getElementById("itineraryYear") || {}).value;
        if (!itineraryName) {
            alert("Option 2: type an itinerary name first.");
            return;
        }
        if (!month || !year) {
            alert("Option 2 needs its own month AND year next to the itinerary name.");
            return;
        }
        const region = regions[itineraryName.toLowerCase()] || "";
        pullFromNcl({
            shipName: "",
            month: Number(month),
            year: Number(year),
            url: "",
            destination: region,
            query: region ? "" : itineraryName
        }, itineraryButton);
    });
})();
