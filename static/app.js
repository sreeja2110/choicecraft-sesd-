
(() => {

    const criteriaHost = document.getElementById("criteria-list");
    const alternativesHost = document.getElementById("alternatives-list");

    // Run only on the comparison builder page
    if (!criteriaHost || !alternativesHost) return;

    const initial = window.CHOICECRAFT_INITIAL;

    let criteria = initial
        ? initial.criteria.map(c => ({ ...c }))
        : [
            { name: "Price", weight: 40, kind: "cost" },
            { name: "Quality", weight: 35, kind: "benefit" },
            { name: "Performance", weight: 25, kind: "benefit" }
        ];

    let alternatives = initial
        ? initial.alternatives.map(a => ({
            name: a.name,
            values: [...a.values]
        }))
        : [
            { name: "Option A", values: [500, 7, 8] },
            { name: "Option B", values: [650, 9, 9] }
        ];

    const titleInput = document.getElementById("comparison-title");

    if (initial) {
        titleInput.value = initial.title;
    }

    function escapeHtml(value) {
        return String(value).replace(/[&<>"']/g, ch => ({
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#39;"
        }[ch]));
    }

    function showMessage(text, isError = true) {
        const node = document.getElementById("form-message");
        node.textContent = text;
        node.className = isError ? "error-text" : "success-text";
    }

    function render() {

        // Render criteria
        criteriaHost.innerHTML = "";

        criteria.forEach((criterion, i) => {

            const row = document.createElement("div");
            row.className = "criterion-row";

            row.innerHTML = `
                <label>
                    Criterion
                    <input
                        data-ci="${i}"
                        data-field="name"
                        value="${escapeHtml(criterion.name)}"
                        maxlength="40"
                    >
                </label>

                <label>
                    Weight
                    <input
                        data-ci="${i}"
                        data-field="weight"
                        type="number"
                        min="0.01"
                        step="any"
                        value="${criterion.weight}"
                    >
                </label>

                <label>
                    Type
                    <select data-ci="${i}" data-field="kind">
                        <option value="benefit">Benefit ↑</option>
                        <option value="cost">Cost ↓</option>
                    </select>
                </label>

                <button
                    class="icon-button remove-criterion"
                    data-index="${i}"
                    type="button"
                    aria-label="Remove criterion"
                >×</button>
            `;

            row.querySelector("select").value = criterion.kind;
            criteriaHost.appendChild(row);

        });

        // Render alternatives
        alternativesHost.innerHTML = "";

        alternatives.forEach((alternative, i) => {

            const card = document.createElement("div");
            card.className = "alternative-editor";

            card.innerHTML = `
                <div class="alternative-editor-head">

                    <label>
                        Alternative Name

                        <input
                            data-ai="${i}"
                            data-field="name"
                            value="${escapeHtml(alternative.name)}"
                            maxlength="50"
                        >
                    </label>

                    <button
                        class="text-button remove-alternative"
                        data-index="${i}"
                        type="button"
                    >
                        Remove
                    </button>

                </div>

                <div class="value-grid">

                    ${criteria.map((criterion, j) => `

                        <label>
                            ${escapeHtml(criterion.name || `Criterion ${j + 1}`)}

                            <input
                                data-ai="${i}"
                                data-vi="${j}"
                                type="number"
                                min="0"
                                step="any"
                                value="${alternative.values[j] ?? ""}"
                                placeholder="Enter value"
                            >
                        </label>

                    `).join("")}

                </div>
            `;

            alternativesHost.appendChild(card);

        });

    }

    // Update criterion values
    criteriaHost.addEventListener("input", event => {

        const element = event.target;
        const i = Number(element.dataset.ci);

        if (Number.isNaN(i) || !element.dataset.field) return;

        criteria[i][element.dataset.field] = element.value;

        // Update the alternative input labels when a criterion is renamed
        if (element.dataset.field === "name") {
            alternativesHost.querySelectorAll(".value-grid").forEach(grid => {
                const label = grid.children[i];
                if (label) {
                    label.firstChild.textContent =
                        element.value || `Criterion ${i + 1}`;
                }
            });
        }

    });

    criteriaHost.addEventListener("change", event => {

        const element = event.target;
        const i = Number(element.dataset.ci);

        if (!Number.isNaN(i) && element.dataset.field) {
            criteria[i][element.dataset.field] = element.value;
        }

    });

    // Update alternative values
    alternativesHost.addEventListener("input", event => {

        const element = event.target;
        const i = Number(element.dataset.ai);

        if (Number.isNaN(i)) return;

        if (element.dataset.field === "name") {
            alternatives[i].name = element.value;
        }

        if (element.dataset.vi !== undefined) {
            alternatives[i].values[Number(element.dataset.vi)] =
                element.value;
        }

    });

    // Add criterion
    document.getElementById("add-criterion").addEventListener("click", () => {

        if (criteria.length >= 8) {
            return showMessage("Maximum 8 criteria allowed.");
        }

        criteria.push({
            name: "New criterion",
            weight: 10,
            kind: "benefit"
        });

        alternatives.forEach(a => a.values.push(""));

        render();

    });

    // Add alternative
    document.getElementById("add-alternative").addEventListener("click", () => {

        if (alternatives.length >= 10) {
            return showMessage("Maximum 10 alternatives allowed.");
        }

        alternatives.push({
            name: `Option ${String.fromCharCode(65 + alternatives.length)}`,
            values: criteria.map(() => "")
        });

        render();

    });

    // Remove criterion
    criteriaHost.addEventListener("click", event => {

        const button = event.target.closest(".remove-criterion");

        if (!button) return;

        if (criteria.length <= 2) {
            return showMessage("Keep at least 2 criteria.");
        }

        const index = Number(button.dataset.index);

        criteria.splice(index, 1);

        alternatives.forEach(a => {
            a.values.splice(index, 1);
        });

        render();

    });

    // Remove alternative
    alternativesHost.addEventListener("click", event => {

        const button = event.target.closest(".remove-alternative");

        if (!button) return;

        if (alternatives.length <= 2) {
            return showMessage("Keep at least 2 alternatives.");
        }

        alternatives.splice(Number(button.dataset.index), 1);

        render();

    });

    // Load example
    document.getElementById("load-sample").addEventListener("click", () => {

        titleInput.value = "Best Laptop for College";

        criteria = [
            { name: "Price (₹)", weight: 35, kind: "cost" },
            { name: "RAM (GB)", weight: 25, kind: "benefit" },
            { name: "Battery Life (hours)", weight: 25, kind: "benefit" },
            { name: "Customer Rating", weight: 15, kind: "benefit" }
        ];

        alternatives = [
            { name: "Laptop A", values: [55000, 16, 8, 4.2] },
            { name: "Laptop B", values: [65000, 16, 10, 4.7] },
            { name: "Laptop C", values: [48000, 8, 6, 4.0] }
        ];

        render();

        showMessage(
            "Example data loaded. You can edit it before calculating.",
            false
        );

    });

    // Calculate and save
    document.getElementById("calculate-save").addEventListener("click", async () => {

        const button = document.getElementById("calculate-save");

        button.disabled = true;
        button.textContent = "Calculating...";

        const payload = {
            id: initial?.id,
            title: titleInput.value,
            criteria: criteria,
            alternatives: alternatives
        };

        try {

            const response = await fetch("/comparison/save", {

                method: "POST",

                headers: {
                    "Content-Type": "application/json"
                },

                body: JSON.stringify(payload)

            });

            const result = await response.json();

            if (!response.ok || !result.ok) {
                throw new Error(result.error || "Could not save comparison.");
            }

            window.location.href = result.redirect;

        } catch (error) {

            showMessage(error.message);

            button.disabled = false;
            button.textContent = "Calculate and Save";

        }

    });

    render();

})();
