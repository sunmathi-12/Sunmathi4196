(function () {

    const form = document.getElementById("planner-form");

    if (!form) {
        return;
    }

    const results = document.getElementById("results");


    const value = (id) => {

        const element = document.getElementById(id);

        return element ? element.value : "";
    };


    function escapeHtml(value) {

        return String(value)
            .replace(
                /[&<>'"]/g,
                function (character) {

                    const map = {
                        "&": "&amp;",
                        "<": "&lt;",
                        ">": "&gt;",
                        "'": "&#39;",
                        '"': "&quot;"
                    };

                    return map[character];
                }
            );
    }


    function showResults(data) {

        const allocations = (
            data.allocations || []
        )
            .map(function (item) {

                const budget = Number(
                    item.budget || 0
                ).toLocaleString(
                    "en-IN"
                );

                const category =
                    escapeHtml(
                        item.category
                    );

                const platform =
                    escapeHtml(
                        item.platform
                    );

                const searchUrl =
                    escapeHtml(
                        item.search_url || "#"
                    );

                return `
                    <div class="alloc">

                        <div>

                            <b>
                                ${category}
                            </b>

                            <small>
                                ${platform}
                            </small>

                        </div>

                        <div class="allocation-right">

                            <strong>
                                ₹${budget}
                            </strong>

                            <a
                                href="${searchUrl}"
                                target="_blank"
                                rel="noopener noreferrer"
                            >
                                Search
                            </a>

                        </div>

                    </div>
                `;

            })
            .join("");


        const tips = (
            data.tips || []
        )
            .map(function (tip) {

                return `
                    <div class="result-tip">
                        ${escapeHtml(tip)}
                    </div>
                `;

            })
            .join("");


        results.innerHTML = `

            <div class="result-card">

                <span class="eyebrow">
                    AI BUDGET PLAN
                </span>

                <h2>
                    ${escapeHtml(
                        data.title ||
                        "Recommendations"
                    )}
                </h2>

                <p>
                    ${escapeHtml(
                        data.summary || ""
                    )}
                </p>

                ${allocations}

                <h3>
                    Planning tips
                </h3>

                ${tips}

            </div>
        `;
    }


    form.addEventListener(
        "submit",
        async function (event) {

            event.preventDefault();


            results.innerHTML = `

                <div class="result-placeholder">

                    <h3>
                        Building your plan…
                    </h3>

                    <p>
                        Processing your budget
                        and preferences.
                    </p>

                </div>

            `;


            try {

                let response;


                if (
                    window.PLANNER === "home"
                ) {

                    const body = {

                        total_budget:
                            Number(
                                value(
                                    "total_budget"
                                )
                            ),

                        room_type:
                            value(
                                "room_type"
                            ),

                        lights:
                            Number(
                                value("lights")
                            ),

                        fans:
                            Number(
                                value("fans")
                            ),

                        tables:
                            Number(
                                value("tables")
                            ),

                        style:
                            value("style")
                    };


                    response = await fetch(
                        "/generate-home",
                        {
                            method: "POST",

                            headers: {
                                "Content-Type":
                                    "application/json"
                            },

                            body:
                                JSON.stringify(body)
                        }
                    );
                }


                if (
                    window.PLANNER === "party"
                ) {

                    const body = {

                        total_budget:
                            Number(
                                value(
                                    "total_budget"
                                )
                            ),

                        num_guests:
                            Number(
                                value(
                                    "num_guests"
                                )
                            ),

                        party_type:
                            value(
                                "party_type"
                            ),

                        venue_preference:
                            value(
                                "venue_preference"
                            ),

                        food_preference:
                            value(
                                "food_preference"
                            )
                    };


                    response = await fetch(
                        "/generate-party",
                        {
                            method: "POST",

                            headers: {
                                "Content-Type":
                                    "application/json"
                            },

                            body:
                                JSON.stringify(body)
                        }
                    );
                }


                if (
                    window.PLANNER === "jewelry"
                ) {

                    const formData =
                        new FormData();


                    const payload = {

                        total_budget:
                            Number(
                                value(
                                    "total_budget"
                                )
                            ),

                        occasion:
                            value(
                                "occasion"
                            ),

                        style:
                            value(
                                "style"
                            ),

                        outfit_color:
                            value(
                                "outfit_color"
                            )
                    };


                    formData.append(
                        "payload",
                        JSON.stringify(payload)
                    );


                    const image =
                        document.getElementById(
                            "outfit_image"
                        );


                    if (
                        image &&
                        image.files &&
                        image.files.length > 0
                    ) {

                        formData.append(
                            "outfit_image",
                            image.files[0]
                        );
                    }


                    response = await fetch(
                        "/generate-jewelry",
                        {
                            method: "POST",
                            body: formData
                        }
                    );
                }


                if (!response) {

                    throw new Error(
                        "Unknown planner type."
                    );
                }


                const data =
                    await response.json();


                if (!response.ok) {

                    throw new Error(
                        data.detail ||
                        "Request failed."
                    );
                }


                showResults(data);

            }

            catch (error) {

                results.innerHTML = `

                    <div class="alert">

                        ${escapeHtml(
                            error.message
                        )}

                    </div>

                `;
            }

        }
    );

})();