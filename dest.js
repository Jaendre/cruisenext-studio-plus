(function () {
    if (document.getElementById("destination")) {
        return;
    }
    const fields = document.querySelector(".ncl-fields");
    const button = document.getElementById("nclButton");
    if (!fields || !button) {
        return;
    }
    const destBlock = document.createElement("div");
    destBlock.className = "field-block";
    destBlock.innerHTML = '<label for="destination">DESTINATION</label><select id="destination"><option value="">Any</option><option value="AFRICA">Africa</option><option value="ALASKA">Alaska</option><option value="ASIA">Asia</option><option value="AUSTRALIA">Australia & New Zealand</option><option value="BAHAMAS">Bahamas</option><option value="BERMUDA">Bermuda</option><option value="CANADA_NEW_ENGL">Canada & New England</option><option value="CARIBBEAN">Caribbean</option><option value="EXTRAORDINARY_JOURNEYS">Extraordinary Journeys</option><option value="GREEK_ISLES">Greek Isles</option><option value="HAWAII">Hawaii</option><option value="MEDITERRANEAN">Mediterranean</option><option value="MEXICAN_RIVIERA">Mexican Riviera</option><option value="NORTHERN_EUROPE">Northern Europe</option><option value="PACIFIC_COASTAL">Pacific Coastal</option><option value="PANAMA_CANAL">Panama Canal</option><option value="SOUTH_AMERICA">South America</option><option value="SOUTH_PACIFIC">South Pacific</option><option value="TRANSATLANTIC">Transatlantic</option><option value="WEEKEND">Weekend</option></select>';
    const nameBlock = document.createElement("div");
    nameBlock.className = "field-block";
    nameBlock.innerHTML = '<label for="itineraryName">ITINERARY NAME</label><input id="itineraryName" list="nclItineraries" placeholder="Baltic Capitals, Caribbean..." autocomplete="off"><datalist id="nclItineraries"><option value="Baltic Capitals"></option><option value="Caribbean"></option><option value="Alaska"></option><option value="Greek Isles"></option><option value="Hawaii"></option><option value="Bermuda"></option><option value="Panama Canal"></option><option value="Mexican Riviera"></option><option value="Canada & New England"></option><option value="Transatlantic"></option><option value="Norwegian Fjords"></option></datalist>';
    fields.insertBefore(destBlock, button);
    fields.insertBefore(nameBlock, button);
    const title = document.querySelector(".ncl-panel-head h3");
    if (title) title.textContent = "Pull sailings by ship, destination, itinerary or date";
    const fresh = button.cloneNode(true);
    button.parentNode.replaceChild(fresh, button);
    fresh.addEventListener("click", async () => {
        const shipName = (document.getElementById("shipName") || {}).value.trim();
        const month = (document.getElementById("sailMonth") || {}).value;
        const year = (document.getElementById("sailYear") || {}).value;
        const nclUrl = (document.getElementById("nclUrl") || {}).value.trim();
        const destination = (document.getElementById("destination") || {}).value.trim();
        const itineraryName = (document.getElementById("itineraryName") || {}).value.trim();
        if (!shipName && !nclUrl && !destination && !itineraryName) {
            alert("Enter a ship, destination, itinerary name, or NCL URL.");
            return;
        }
        fresh.disabled = true;
        const analyzeButton = document.getElementById("analyzeButton");
        if (analyzeButton) analyzeButton.disabled = true;
        try {
            const response = await fetch("/api/ncl-lookup", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    shipName,
                    month: month ? Number(month) : null,
                    year: year ? Number(year) : null,
                    url: nclUrl,
                    destination,
                    query: itineraryName
                })
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || "Could not pull sailings from NCL.com.");
            const rows = Array.isArray(data.itineraries) ? data.itineraries : [];
            if (!rows.length) throw new Error("No matching NCL sailings were found.");
            if (typeof applyItineraries === "function") applyItineraries(rows, "NCL.com");
            const status = document.getElementById("status");
            if (status) {
                status.className = "status success";
                status.textContent = "Pulled " + rows.length + " sailing" + (rows.length === 1 ? "" : "s") + " from NCL.com.";
            }
        } catch (error) {
            const results = document.getElementById("results");
            if (results) {
                results.innerHTML = '<div class="error-result"></div>';
                results.firstChild.textContent = error.message;
            }
            const status = document.getElementById("status");
            if (status) {
                status.className = "status error";
                status.textContent = error.message;
            }
        } finally {
            fresh.disabled = false;
            if (analyzeButton) analyzeButton.disabled = false;
        }
    });
})();
