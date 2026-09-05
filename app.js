/* =========================================================
   CRUISENEXT ITINERARY STUDIO PLUS
   MULTI SCREENSHOT + NCL LOOKUP FRONT END
========================================================= */


const NCL_SHIPS = [
    "Norwegian Aqua",
    "Norwegian Aura",
    "Norwegian Bliss",
    "Norwegian Breakaway",
    "Norwegian Dawn",
    "Norwegian Encore",
    "Norwegian Epic",
    "Norwegian Escape",
    "Norwegian Gem",
    "Norwegian Getaway",
    "Norwegian Jade",
    "Norwegian Jewel",
    "Norwegian Joy",
    "Norwegian Luna",
    "Norwegian Pearl",
    "Norwegian Prima",
    "Norwegian Sky",
    "Norwegian Spirit",
    "Norwegian Star",
    "Norwegian Sun",
    "Norwegian Viva",
    "Pride of America"
];


const MAX_FILES = 10;

const MAX_FILE_SIZE =
    15 * 1024 * 1024;


const miniSlots =
    document.getElementById("miniSlots");


for (let index = 1; index < MAX_FILES; index += 1) {

    const number =
        String(index + 1).padStart(2, "0");

    const slot =
        document.createElement("div");

    slot.className =
        "slot-card mini-slot";

    slot.dataset.slot =
        String(index);

    slot.tabIndex = 0;

    slot.innerHTML = `

        <input
            type="file"
            id="image${index + 1}"
            class="slot-input"
            accept="image/png,image/jpeg,image/webp"
        >

        <label
            for="image${index + 1}"
            class="slot-label"
        >

            <div class="slot-number">
                ${number}
            </div>

            <div class="slot-empty">

                <div class="mini-plus">
                    +
                </div>

                <div class="mini-title">
                    Screenshot ${index + 1}
                </div>

                <div class="mini-hint">
                    CLICK OR DROP
                </div>

            </div>

            <img
                class="slot-preview"
                alt="Screenshot ${index + 1} preview"
            >

            <div class="change-chip">
                CHANGE
            </div>

        </label>

        <button
            type="button"
            class="remove-slot"
            data-slot="${index}"
        >
            REMOVE
        </button>

    `;

    miniSlots.appendChild(slot);

}


const slotInputs =
    Array.from(
        document.querySelectorAll(".slot-input")
    );

const slotCards =
    Array.from(
        document.querySelectorAll(".slot-card")
    );

const removeButtons =
    Array.from(
        document.querySelectorAll(".remove-slot")
    );

const selectedCount =
    document.getElementById("selectedCount");

const analyzeButton =
    document.getElementById("analyzeButton");

const nclButton =
    document.getElementById("nclButton");

const status =
    document.getElementById("status");

const results =
    document.getElementById("results");

const detectedCount =
    document.getElementById("detectedCount");

const copyButton =
    document.getElementById("copyButton");

const shipNameInput =
    document.getElementById("shipName");

const sailMonthInput =
    document.getElementById("sailMonth");

const sailYearInput =
    document.getElementById("sailYear");

const nclUrlInput =
    document.getElementById("nclUrl");

const nclShipsList =
    document.getElementById("nclShips");


NCL_SHIPS.forEach(name => {

    const option =
        document.createElement("option");

    option.value = name;

    nclShipsList.appendChild(option);

});


const currentYear =
    new Date().getFullYear();

for (let year = currentYear; year <= currentYear + 3; year += 1) {

    const option =
        document.createElement("option");

    option.value = String(year);

    option.textContent = String(year);

    if (year === currentYear + 1) {
        option.selected = true;
    }

    sailYearInput.appendChild(option);

}


let filesBySlot =
    Array.from(
        { length: MAX_FILES },
        () => null
    );

let previewUrls =
    Array.from(
        { length: MAX_FILES },
        () => null
    );


let currentGroups = [];

let nclItineraries = [];

let activeSlotIndex = 0;

const HAS_LOCAL_API = !["file:", "null"].includes(location.protocol);


function showLocalServerNeeded(action) {
    const message = HAS_LOCAL_API
        ? `${action} failed. The local Python server is not running. In the unzipped folder run: python3 server.py`
        : `${action} failed because this page was opened as a file. Unzip the folder and run python3 server.py (Windows: START.bat), then open http://localhost:3333`;
    throw new Error(message);
}


function isValidImage(file) {

    if (!file) {
        return false;
    }

    const allowedTypes = [
        "image/png",
        "image/jpeg",
        "image/webp"
    ];

    if (!allowedTypes.includes(file.type)) {

        alert("Please use PNG, JPG, or WEBP.");

        return false;
    }

    if (file.size > MAX_FILE_SIZE) {

        alert("Each screenshot must be smaller than 15 MB.");

        return false;
    }

    return true;
}


function setFileForSlot(index, file) {

    if (!isValidImage(file)) {
        return;
    }

    if (previewUrls[index]) {
        URL.revokeObjectURL(previewUrls[index]);
    }

    filesBySlot[index] = file;

    previewUrls[index] =
        URL.createObjectURL(file);

    const preview =
        slotCards[index].querySelector(".slot-preview");

    preview.src = previewUrls[index];

    slotCards[index].classList.add("has-image");

    activeSlotIndex = index;

    updateSelectedCount();
}


slotInputs.forEach((input, index) => {

    input.addEventListener("change", () => {

        const file = input.files[0];

        if (!file) {
            return;
        }

        setFileForSlot(index, file);

    });

});


slotCards.forEach((card, index) => {

    card.addEventListener("click", () => {
        activeSlotIndex = index;
    });

    ["dragenter", "dragover"].forEach(eventName => {

        card.addEventListener(eventName, event => {

            event.preventDefault();
            event.stopPropagation();

            activeSlotIndex = index;

            card.classList.add("drag-over");

        });

    });

    ["dragleave", "drop"].forEach(eventName => {

        card.addEventListener(eventName, event => {

            event.preventDefault();
            event.stopPropagation();

            card.classList.remove("drag-over");

        });

    });

    card.addEventListener("drop", event => {

        const files =
            Array.from(event.dataTransfer.files);

        const imageFile =
            files.find(file => file.type.startsWith("image/"));

        if (!imageFile) {

            alert("Please drop an image.");

            return;
        }

        setFileForSlot(index, imageFile);

    });

});


document.addEventListener("paste", event => {

    const items =
        Array.from(event.clipboardData?.items || []);

    const imageItem =
        items.find(item => item.type.startsWith("image/"));

    if (!imageItem) {
        return;
    }

    event.preventDefault();

    const file = imageItem.getAsFile();

    if (!file) {
        return;
    }

    let targetIndex = activeSlotIndex;

    if (filesBySlot[targetIndex]) {

        const emptyIndex =
            filesBySlot.findIndex(item => !item);

        if (emptyIndex !== -1) {
            targetIndex = emptyIndex;
        }

    }

    setFileForSlot(targetIndex, file);

});


removeButtons.forEach(button => {

    button.addEventListener("click", event => {

        event.preventDefault();
        event.stopPropagation();

        const index =
            Number(button.dataset.slot);

        if (previewUrls[index]) {
            URL.revokeObjectURL(previewUrls[index]);
        }

        filesBySlot[index] = null;
        previewUrls[index] = null;
        slotInputs[index].value = "";

        const preview =
            slotCards[index].querySelector(".slot-preview");

        preview.removeAttribute("src");

        slotCards[index].classList.remove("has-image");

        activeSlotIndex = index;

        updateSelectedCount();

    });

});


function updateSelectedCount() {

    const count =
        filesBySlot.filter(Boolean).length;

    selectedCount.textContent =
        `${count} / ${MAX_FILES}`;

    selectedCount.classList.toggle("active", count > 0);
}


function showProcessing(title, copy) {

    results.innerHTML = `

        <div class="processing">

            <div class="loader"></div>

            <div class="processing-title">
                ${escapeHtml(title)}
            </div>

            <div class="processing-copy">
                ${escapeHtml(copy)}
            </div>

        </div>

    `;

}


function applyItineraries(itineraries, sourceLabel) {

    if (!itineraries.length) {
        throw new Error("No itineraries were detected.");
    }

    currentGroups =
        groupItineraries(itineraries);

    detectedCount.textContent =
        `${itineraries.length} detected • ${currentGroups.length} result${
            currentGroups.length === 1 ? "" : "s"
        }${sourceLabel ? " • " + sourceLabel : ""}`;

    renderGroups(currentGroups);

    status.className = "status success";

    status.textContent = "Analysis complete.";
}


analyzeButton.addEventListener("click", async () => {

    const files =
        filesBySlot.filter(Boolean);

    if (!files.length && !nclItineraries.length) {

        alert("Upload at least 1 screenshot or pull sailings from NCL.com first.");

        return;
    }

    analyzeButton.disabled = true;

    status.className = "status";

    status.textContent =
        files.length
            ? `Reading ${files.length} screenshot${files.length === 1 ? "" : "s"}...`
            : "Formatting NCL sailings...";

    showProcessing(
        "Analyzing itineraries",
        "Reading dates, ports and itinerary differences."
    );

    detectedCount.textContent = "";

    try {

        let screenshotItineraries = [];

        if (files.length) {

            const formData = new FormData();

            filesBySlot.forEach(file => {

                if (file) {
                    formData.append("images", file);
                }

            });

            if (!HAS_LOCAL_API) {
                showLocalServerNeeded("Screenshot analysis");
            }

            let response;
            try {
                response = await fetch("/api/extract", {
                    method: "POST",
                    body: formData
                });
            } catch (networkError) {
                showLocalServerNeeded("Screenshot analysis");
            }

            const contentType =
                response.headers.get("content-type") || "";

            if (!contentType.includes("application/json")) {
                throw new Error("The server returned an unexpected response.");
            }

            const data = await response.json();

            if (!response.ok) {
                throw new Error(
                    data.error || "Could not process itineraries."
                );
            }

            screenshotItineraries =
                Array.isArray(data.itineraries)
                    ? data.itineraries
                    : [];
        }

        const itineraries = [
            ...screenshotItineraries,
            ...nclItineraries
        ];

        const sourceBits = [];

        if (screenshotItineraries.length) {
            sourceBits.push("screenshots");
        }

        if (nclItineraries.length) {
            sourceBits.push("NCL.com");
        }

        applyItineraries(
            itineraries,
            sourceBits.join(" + ")
        );

    } catch (error) {

        console.error(error);

        results.innerHTML = `

            <div class="error-result">
                ${escapeHtml(error.message)}
            </div>

        `;

        status.className = "status error";

        status.textContent = error.message;

    } finally {

        analyzeButton.disabled = false;

    }

});


nclButton.addEventListener("click", async () => {

    const shipName =
        shipNameInput.value.trim();

    const month =
        sailMonthInput.value;

    const year =
        sailYearInput.value;

    const nclUrl =
        nclUrlInput.value.trim();

    if (!shipName && !nclUrl) {

        alert("Enter a ship name or paste an NCL itinerary URL.");

        return;
    }

    nclButton.disabled = true;
    analyzeButton.disabled = true;

    status.className = "status";
    status.textContent = "Searching NCL.com...";

    showProcessing(
        "Pulling NCL sailings",
        "Reading public itinerary pages and converting them into studio templates."
    );

    detectedCount.textContent = "";

    try {

        let response;
        try {
            response = await fetch("/api/ncl-lookup", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    shipName,
                    month: month ? Number(month) : null,
                    year: year ? Number(year) : null,
                    url: nclUrl
                })
            });
        } catch (networkError) {
            const clientResult = await lookupNclInBrowser({
                shipName,
                month: month ? Number(month) : null,
                year: year ? Number(year) : null,
                url: nclUrl
            });
            nclItineraries = clientResult;
            if (!nclItineraries.length) {
                showLocalServerNeeded("NCL lookup");
            }
            applyItineraries(nclItineraries, "NCL.com");
            status.textContent =
                `Pulled ${nclItineraries.length} sailing${nclItineraries.length === 1 ? "" : "s"} from NCL.com.`;
            return;
        }

        const contentType =
            response.headers.get("content-type") || "";

        if (!contentType.includes("application/json")) {
            throw new Error("The NCL lookup returned an unexpected response.");
        }

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.error || "Could not pull sailings from NCL.com."
            );
        }

        nclItineraries =
            Array.isArray(data.itineraries)
                ? data.itineraries
                : [];

        if (!nclItineraries.length) {
            throw new Error(
                data.message || "No matching NCL sailings were found for that ship and date."
            );
        }

        applyItineraries(
            nclItineraries,
            "NCL.com"
        );

        status.textContent =
            `Pulled ${nclItineraries.length} sailing${nclItineraries.length === 1 ? "" : "s"} from NCL.com.`;

    } catch (error) {

        console.error(error);

        results.innerHTML = `

            <div class="error-result">
                ${escapeHtml(error.message)}
            </div>

        `;

        status.className = "status error";

        status.textContent = error.message;

    } finally {

        nclButton.disabled = false;
        analyzeButton.disabled = false;

    }

});


function parseISODate(value) {

    const text =
        String(value || "").trim();

    if (!/^\d{4}-\d{2}-\d{2}$/.test(text)) {
        return null;
    }

    const [year, month, day] =
        text.split("-").map(Number);

    const date =
        new Date(Date.UTC(year, month - 1, day));

    if (
        date.getUTCFullYear() !== year ||
        date.getUTCMonth() !== month - 1 ||
        date.getUTCDate() !== day
    ) {
        return null;
    }

    return date;
}


function diffCalendarDays(startDate, endDate) {

    const start = parseISODate(startDate);
    const end = parseISODate(endDate);

    if (!start || !end) {
        return null;
    }

    return Math.round(
        (end.getTime() - start.getTime()) / 86400000
    );
}


function addDaysISO(isoDate, amount) {

    const original = parseISODate(isoDate);

    if (!original) {
        return "";
    }

    const date = new Date(original.getTime());

    date.setUTCDate(date.getUTCDate() + amount);

    return [
        date.getUTCFullYear(),
        String(date.getUTCMonth() + 1).padStart(2, "0"),
        String(date.getUTCDate()).padStart(2, "0")
    ].join("-");
}


function getCruiseLength(itinerary) {

    const calculated =
        diffCalendarDays(
            itinerary.start_date,
            itinerary.end_date
        );

    if (Number.isInteger(calculated) && calculated > 0) {
        return calculated;
    }

    const serverLength =
        Number(itinerary.cruise_length);

    if (Number.isInteger(serverLength) && serverLength > 0) {
        return serverLength;
    }

    const dayNumbers =
        (itinerary.days || [])
            .map(item => Number(item.day))
            .filter(value => Number.isInteger(value));

    if (dayNumbers.length) {
        return Math.max(...dayNumbers);
    }

    return 1;
}


function getPlaceForDay(itinerary, dayNumber) {

    const numbered =
        (itinerary.days || []).find(
            item => Number(item.day) === Number(dayNumber)
        );

    if (numbered?.place) {
        return numbered.place;
    }

    const targetDate =
        addDaysISO(itinerary.start_date, dayNumber - 1);

    const dated =
        (itinerary.days || []).find(
            item => item.date === targetDate
        );

    return dated?.place || "—";
}


function isSeaDay(place) {
    return normalize(place) === "sea day";
}


function groupItineraries(itineraries) {

    const sorted = [...itineraries].sort(
        (a, b) =>
            String(a.start_date).localeCompare(String(b.start_date))
    );

    const groups = [];

    for (const itinerary of sorted) {

        let match = null;

        for (const group of groups) {

            if (canJoinGroup(group, itinerary)) {
                match = group;
                break;
            }

        }

        if (match) {
            match.members.push(itinerary);
        } else {
            groups.push({
                members: [itinerary]
            });
        }

    }

    return groups;
}


function canJoinGroup(group, candidate) {

    const first = group.members[0];

    if (normalizeShip(first.ship_name) !== normalizeShip(candidate.ship_name)) {
        return false;
    }

    if (getCruiseLength(first) !== getCruiseLength(candidate)) {
        return false;
    }

    if (normalize(first.embark) !== normalize(candidate.embark)) {
        return false;
    }

    if (normalize(first.disembark) !== normalize(candidate.disembark)) {
        return false;
    }

    const variable =
        getVariableDays([
            ...group.members,
            candidate
        ]);

    return variable.length <= 2;
}


function getVariableDays(members) {

    if (!members.length) {
        return [];
    }

    const length = getCruiseLength(members[0]);
    const variable = [];

    for (let day = 2; day <= length; day += 1) {

        const values = new Set();

        members.forEach(itinerary => {

            values.add(
                normalize(
                    getPlaceForDay(itinerary, day)
                )
            );

        });

        if (values.size > 1) {
            variable.push(day);
        }

    }

    return variable;
}


function renderGroups(groups) {

    results.innerHTML = "";

    groups.forEach((group, index) => {
        results.appendChild(renderGroup(group, index));
    });
}


function renderGroup(group, index) {

    const members = [...group.members].sort(
        (a, b) =>
            String(a.start_date).localeCompare(String(b.start_date))
    );

    const first = members[0];
    const length = getCruiseLength(first);
    const variableDays = getVariableDays(members);

    const container = document.createElement("div");
    container.className = "itinerary-group";

    if (currentGroups.length > 1) {

        const label = document.createElement("div");
        label.className = "group-label";
        label.textContent =
            `ITINERARY ${String(index + 1).padStart(2, "0")}`;

        container.appendChild(label);

    }

    const title = document.createElement("div");
    title.className = "cruise-title";
    title.textContent =
        `${length}-Day ${shortenShipName(first.ship_name)}`;

    container.appendChild(title);

    const dates = document.createElement("div");
    dates.className = "cruise-dates";
    dates.innerHTML =
        formatCombinedDates(
            members.map(item => item.start_date)
        );

    container.appendChild(dates);

    const table = document.createElement("table");
    table.className = "result-table";

    table.appendChild(
        createSimpleRow("Embark", first.embark)
    );

    let day = 2;

    while (day <= length) {

        if (variableDays.includes(day)) {

            table.appendChild(
                createVariableRow(day, members)
            );

            day += 1;
            continue;
        }

        const currentPlace =
            getPlaceForDay(first, day);

        if (isSeaDay(currentPlace)) {

            let endDay = day;

            while (endDay + 1 <= length) {

                const nextDay = endDay + 1;

                if (variableDays.includes(nextDay)) {
                    break;
                }

                const nextPlace =
                    getPlaceForDay(first, nextDay);

                if (!isSeaDay(nextPlace)) {
                    break;
                }

                endDay = nextDay;
            }

            if (endDay > day) {

                table.appendChild(
                    createSimpleRow(
                        `Day ${day} - ${endDay}`,
                        "Sea Days"
                    )
                );

                day = endDay + 1;
                continue;
            }

        }

        table.appendChild(
            createSimpleRow(`Day ${day}`, currentPlace)
        );

        day += 1;
    }

    table.appendChild(
        createSimpleRow("Disemb", first.disembark)
    );

    container.appendChild(table);

    if (variableDays.length) {

        const note = document.createElement("div");
        note.className = "variation-note";
        note.textContent =
            `${variableDays.length} changed port day${
                variableDays.length === 1 ? "" : "s"
            } highlighted.`;

        container.appendChild(note);

    }

    return container;
}


function createSimpleRow(label, place) {

    const row = document.createElement("tr");
    const left = document.createElement("td");
    const right = document.createElement("td");

    left.textContent = label;
    right.textContent = place || "—";

    row.append(left, right);

    return row;
}


function createVariableRow(day, members) {

    const row = document.createElement("tr");
    row.className = "variable-row";

    const left = document.createElement("td");
    const right = document.createElement("td");

    left.textContent = `Day ${day}`;

    const uniquePlaces = new Map();

    members.forEach(itinerary => {

        const place = getPlaceForDay(itinerary, day);
        const key = normalize(place);

        if (!uniquePlaces.has(key)) {
            uniquePlaces.set(key, place);
        }

    });

    right.innerHTML =
        [...uniquePlaces.values()]
            .map(place => `<strong>${escapeHtml(place)}</strong>`)
            .join(` <span class="variant-divider">/</span> `);

    row.append(left, right);

    return row;
}


function formatCombinedDates(dates) {

    const grouped = new Map();

    const uniqueDates =
        [...new Set(dates.filter(Boolean))].sort();

    uniqueDates.forEach(dateText => {

        const date = parseISODate(dateText);

        if (!date) {
            return;
        }

        const year = String(date.getUTCFullYear());

        if (!grouped.has(year)) {
            grouped.set(year, []);
        }

        grouped.get(year).push(formatMonthDay(dateText));

    });

    return [...grouped]
        .map(([year, values]) =>
            `<div>${escapeHtml(`${year}: ${values.join(", ")}`)}</div>`
        )
        .join("");
}


function formatMonthDay(isoDate) {

    const date = parseISODate(isoDate);

    if (!date) {
        return isoDate;
    }

    const months = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
    ];

    return `${months[date.getUTCMonth()]} ${date.getUTCDate()}`;
}


function shortenShipName(name) {

    return String(name || "").replace(/^Norwegian\s+/i, "N. ");
}


function normalizeShip(name) {

    return normalize(
        String(name || "")
            .replace(/^Norwegian\s+/i, "")
            .replace(/^N\.\s*/i, "")
    );
}


function normalize(value) {

    return String(value || "")
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, " ")
        .trim();
}


function escapeHtml(text) {

    return String(text ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}


copyButton.addEventListener("click", async () => {

    if (!currentGroups.length) {

        alert("Analyze screenshots or pull from NCL first.");

        return;
    }

    const copyArea = results.cloneNode(true);

    copyArea
        .querySelectorAll(".group-label, .variation-note")
        .forEach(element => element.remove());

    copyArea
        .querySelectorAll(".itinerary-group")
        .forEach(element => {

            element.style.background = "#FFFFFF";
            element.style.border = "none";
            element.style.boxShadow = "none";
            element.style.padding = "0";
            element.style.width = "auto";
            element.style.marginBottom = "18pt";

        });

    copyArea
        .querySelectorAll(".itinerary-group, .itinerary-group *")
        .forEach(element => {

            element.style.fontFamily =
                "'Century Gothic', CenturyGothic, Arial, sans-serif";

            element.style.fontSize = "9pt";
            element.style.color = "#000000";

        });

    copyArea
        .querySelectorAll(".result-table")
        .forEach(table => {

            table.style.borderCollapse = "collapse";
            table.style.width = "100%";
            table.style.fontFamily =
                "'Century Gothic', CenturyGothic, Arial, sans-serif";
            table.style.fontSize = "9pt";

        });

    copyArea
        .querySelectorAll(".result-table td:first-child")
        .forEach(cell => {

            cell.style.width = "85px";
            cell.style.whiteSpace = "nowrap";
            cell.style.fontFamily =
                "'Century Gothic', CenturyGothic, Arial, sans-serif";
            cell.style.fontSize = "9pt";
            cell.style.color = "#000000";

        });

    copyArea
        .querySelectorAll(".result-table td:last-child")
        .forEach(cell => {

            cell.style.fontFamily =
                "'Century Gothic', CenturyGothic, Arial, sans-serif";
            cell.style.fontSize = "9pt";
            cell.style.color = "#000000";

        });

    copyArea
        .querySelectorAll(".variable-row strong")
        .forEach(element => {

            element.style.fontFamily =
                "'Century Gothic', CenturyGothic, Arial, sans-serif";

            element.style.fontSize = "9pt";
            element.style.fontWeight = "700";
            element.style.color = "#000000";

        });

    const html = `

<div style="
font-family:'Century Gothic',CenturyGothic,Arial,sans-serif;
font-size:9pt;
color:#000000;
">

${copyArea.innerHTML}

</div>

`;

    const plain = copyArea.innerText;

    try {

        await navigator.clipboard.write([

            new ClipboardItem({

                "text/html": new Blob([html], { type: "text/html" }),
                "text/plain": new Blob([plain], { type: "text/plain" })

            })

        ]);

        status.className = "status success";
        status.textContent = "Formatted itineraries copied.";

    } catch {

        await navigator.clipboard.writeText(plain);

        status.className = "status success";
        status.textContent = "Itineraries copied.";

    }

});


updateSelectedCount();


async function fetchTextViaProxy(url) {
    const proxies = [
        target => `https://api.allorigins.win/raw?url=${encodeURIComponent(target)}`,
        target => `https://corsproxy.io/?${encodeURIComponent(target)}`
    ];
    let lastError = null;
    for (const build of proxies) {
        try {
            const response = await fetch(build(url), { method: "GET" });
            if (!response.ok) {
                throw new Error(`proxy ${response.status}`);
            }
            return await response.text();
        } catch (error) {
            lastError = error;
        }
    }
    throw lastError || new Error("Could not reach NCL.com from the browser.");
}


function decodeHtmlEntities(value) {
    return String(value || "")
        .replace(/&amp;/g, "&")
        .replace(/&quot;/g, '"')
        .replace(/&#39;/g, "'")
        .replace(/&lt;/g, "<")
        .replace(/&gt;/g, ">");
}


function cleanExtractedUrl(value) {
    let url = decodeHtmlEntities(value).replace(/\\u002F/g, "/").replace(/\\+/g, "");
    url = url.split("&")[0].split("#")[0];
    if (url.startsWith("//")) {
        url = "https:" + url;
    }
    return url;
}


function isAllowedNclUrl(value) {
    try {
        const parsed = new URL(value);
        const host = parsed.hostname.replace(/^www\./, "");
        return host === "ncl.com" && parsed.pathname.includes("/cruises/");
    } catch {
        return false;
    }
}


function normalizeNclUrl(value) {
    const parsed = new URL(value);
    let path = parsed.pathname || "/";
    if (path.startsWith("/cruises/") && !path.startsWith("/ca/en/")) {
        path = "/ca/en" + path;
    }
    return `https://www.ncl.com${path}${parsed.search || ""}`;
}


async function lookupNclInBrowser({ shipName, month, year, url }) {
    const pages = [];
    if (url && isAllowedNclUrl(url)) {
        pages.push(normalizeNclUrl(url));
    } else if (shipName) {
        const query = ["site:ncl.com/cruises", `"${shipName}"`, "itinerary"];
        if (month) {
            query.push(new Date(2000, month - 1, 1).toLocaleString("en", { month: "long" }));
        }
        if (year) {
            query.push(String(year));
        }
        const duck = "https://html.duckduckgo.com/html/?q=" + encodeURIComponent(query.join(" "));
        const html = await fetchTextViaProxy(duck);
        const found = html.match(/https?:\/\/(?:www\.)?ncl\.com[^"'\\\s<>]*/gi) || [];
        const unique = [];
        for (const raw of found) {
            const cleaned = cleanExtractedUrl(raw);
            if (!isAllowedNclUrl(cleaned)) {
                continue;
            }
            const normalized = normalizeNclUrl(cleaned);
            if (!unique.includes(normalized)) {
                unique.push(normalized);
            }
            if (unique.length >= 6) {
                break;
            }
        }
        pages.push(...unique);
    }

    const itineraries = [];
    for (const pageUrl of pages) {
        try {
            itineraries.push(...parseNclHtml(await fetchTextViaProxy(pageUrl), shipName, month, year, pageUrl));
        } catch {
            continue;
        }
    }
    return itineraries;
}


function parseNclHtml(html, fallbackShip, month, year, pageUrl) {
    const titleMatch = html.match(/<title>(.*?)<\/title>/i);
    let ship = fallbackShip || "Norwegian";
    const title = titleMatch ? titleMatch[1].replace(/\s+/g, " ") : "";
    const shipMatch = title.match(/Norwegian\s+[A-Za-z]+/i);
    if (shipMatch) {
        ship = shipMatch[0];
    }

    const events = [];
    const eventRegex = /"dayNumber"\s*:\s*(\d+)[\s\S]{0,400}?"portName"\s*:\s*"([^"]+)"/g;
    let match;
    while ((match = eventRegex.exec(html))) {
        events.push({
            dayNumber: Number(match[1]),
            portName: match[2].replace(/\\u0026/g, "&")
        });
    }

    const ports = [];
    const seen = new Set();
    for (const event of events) {
        const port = event.portName;
        if (!port || seen.has(port.toLowerCase())) {
            continue;
        }
        seen.add(port.toLowerCase());
        ports.push(port);
    }

    const lengthMatch = html.match(/(\d+)\s*[- ]\s*Day/i);
    const length = lengthMatch ? Number(lengthMatch[1]) : Math.max(...events.map(item => item.dayNumber), 0);

    const dates = [];
    const dateRegex = /20\d{2}-\d{2}-\d{2}/g;
    let dateMatch;
    while ((dateMatch = dateRegex.exec(html))) {
        const iso = dateMatch[0];
        const parsed = new Date(iso + "T00:00:00Z");
        if (Number.isNaN(parsed.getTime())) {
            continue;
        }
        if (month && parsed.getUTCMonth() + 1 !== Number(month)) {
            continue;
        }
        if (year && parsed.getUTCFullYear() !== Number(year)) {
            continue;
        }
        if (!dates.includes(iso)) {
            dates.push(iso);
        }
    }

    if (!ports.length || !dates.length) {
        return [];
    }

    const startPort = ports[0];
    const returnPort = ports[ports.length - 1];
    const destination = ports.filter((port, index) => index > 0 && index < ports.length - 1).join(" / ") || startPort;

    return [{
        source: "ncl.com",
        sourceUrl: pageUrl,
        ship,
        startPort,
        returnPort,
        destination,
        cruiseLength: length || null,
        dates,
        ports
    }];
}
