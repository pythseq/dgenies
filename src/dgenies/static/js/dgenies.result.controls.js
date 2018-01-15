if (!dgenies || !dgenies.result) {
    throw "dgenies.result wasn't included!"
}
dgenies.result.controls = {};

dgenies.result.controls.init = function () {
    $("#sort-contigs").click(dgenies.result.controls.launch_sort_contigs);
    $("#hide-noise").click(dgenies.result.controls.launch_hide_noise);
    $("#summary").click(dgenies.result.controls.summary);
    $("form#select-zone input.submit").click(dgenies.result.controls.select_zone);
    $("form#export select").change(dgenies.result.export.export);
};

dgenies.result.controls.summary = function () {
    dgenies.show_loading("Building...");
    window.setTimeout(() => {
        dgenies.post(`/summary/${dgenies.result.id_res}`,
            {},
            function (data) {
                dgenies.hide_loading();
                if (data["success"]) {
                    dgenies.result.summary.show(data["percents"]);
                }
                else {
                    dgenies.notify(data["message"] || "An error occurred! Please contact us to report the bug", "danger");
                }
            })
    }, 0);
};

dgenies.result.controls.launch_sort_contigs = function () {
    d3.boxplot.zoom.reset_scale();
    window.setTimeout(() => {
        dgenies.show_loading("Building...");
        window.setTimeout(() => {
            dgenies.post(`/sort/${dgenies.result.id_res}`,
                {},
                function (data) {
                    if (data["success"]) {
                        dgenies.reset_loading_message();
                        window.setTimeout(() => {
                            d3.boxplot.launch(data, true);
                        }, 0);
                    }
                    else {
                        dgenies.hide_loading();
                        dgenies.notify(data["message"] || "An error occurred! Please contact us to report the bug", "danger");
                    }
                }
            );
        }, 0);
    }, 0);
};

dgenies.result.controls.launch_reverse_contig = function () {
    if (d3.boxplot.query_selected !== null) {
        d3.boxplot.zoom.reset_scale();
        window.setTimeout(() => {
            dgenies.show_loading("Building...");
            window.setTimeout(() => {
                dgenies.post(`/reverse-contig/${dgenies.result.id_res}`,
                    {"contig": d3.boxplot.query_selected},
                    function (data) {
                        if (data["success"]) {
                            dgenies.reset_loading_message();
                            window.setTimeout(() => {
                                d3.boxplot.launch(data, true);
                            }, 0);
                        }
                        else {
                            dgenies.hide_loading();
                            dgenies.notify(data["message"] || "An error occurred! Please contact us to report the bug", "danger");
                        }
                    }
                );
            }, 0);
        }, 0);
    }
    else {
        dgenies.notify("Error: no query selected. Please contact us to report the bug", "danger");
    }
};

dgenies.result.controls.launch_hide_noise = function () {
    d3.boxplot.zoom.reset_scale();
    window.setTimeout(() => {
        dgenies.show_loading("Building...");
        window.setTimeout(() => {
            dgenies.post(`/freenoise/${dgenies.result.id_res}`,
                {noise: dgenies.noise ? 0 : 1},
                function (data) {
                    if (data["success"]) {
                        dgenies.noise = !dgenies.noise;
                        $("#hide-noise").val(dgenies.noise ? "Hide noise" : "Show noise");
                        dgenies.reset_loading_message();
                        window.setTimeout(() => {
                            d3.boxplot.launch(data, true);
                        }, 0);
                    }
                    else {
                        dgenies.hide_loading();
                        dgenies.notify(data["message"] || "An error occurred! Please contact us to report the bug", "danger");
                    }
                }
            );
        }, 0);
    }, 0);
};

dgenies.result.controls.select_zone = function() {
    let contig_select = $("#select-contig").find(":selected");
    let target_select = $("#select-target").find(":selected");
    if (contig_select.val() !== "###NONE###" && target_select.val() !== "###NONE###") {
        d3.boxplot.select_zone(null, null, target_select.val(), contig_select.val(), true);
    }
    else {
        dgenies.notify("Please select zones into zoom!", "danger", 2000);
    }
};