/** @odoo-module **/
/* global Chart */

import {
    Component,
    onMounted,
    onWillStart,
    onWillUnmount,
    useRef,
    useState,
} from "@odoo/owl";
import {loadBundle} from "@web/core/assets";
import {rpc} from "@web/core/network/rpc";
import {registry} from "@web/core/registry";
import {standardFieldProps} from "@web/views/fields/standard_field_props";

export class ServerMonitorDashboard extends Component {
    static template = "cetmix_tower_server_monitor.Dashboard";
    static props = {...standardFieldProps};

    setup() {
        this.state = useState({
            selectedKey: "cpu",
            loading: true,
            current: {
                cpu: 0,
                ram_used: 0,
                ram_total: 0,
                disk_used: 0,
                disk_total: 0,
            },
            history: {
                labels: [],
                cpu: [],
                ram: [],
                disk: [],
            },
            last_update: false,
            monitoring_mode: false,
            monitor_push_status: "none",
            monitor_interval: 1,
            cpu_cores: 0,
        });

        this.canvasRef = useRef("canvas");
        this.chart = null;
        this.timer = null;

        onWillStart(async () => {
            await loadBundle("web.chartjs_lib");
        });

        onMounted(() => {
            this.fetchData();
            // Start the polling loop
            this.startTimer();
        });

        onWillUnmount(() => {
            this.stopTimer();
            if (this.chart) {
                this.chart.destroy();
            }
        });
    }

    startTimer() {
        this.stopTimer();
        let intervalMs = this.state.monitor_interval || 1;
        if (this.state.monitoring_mode === "push") {
            intervalMs *= 1000;
        } else {
            intervalMs = intervalMs * 60 * 1000;
        }
        console.log(
            `Starting dashboard timer with interval: ${intervalMs}ms (${this.state.monitoring_mode} mode)`
        );
        this.timer = setInterval(async () => {
            // If in Pull mode and tab is visible, we can trigger a pull to get "Live" feel
            if (
                this.state.monitoring_mode === "pull" &&
                document.visibilityState === "visible"
            ) {
                console.log("Auto-Pulling metrics for Live mode...");
                // Silent refresh
                await this.refreshData(true);
            } else {
                await this.fetchData();
            }
        }, intervalMs);
    }

    stopTimer() {
        if (this.timer) {
            clearInterval(this.timer);
            this.timer = null;
        }
    }

    async fetchData() {
        try {
            console.log("Fetching dashboard data for record:", this.props.record);
            const serverId = this.props.record.resId || this.props.record.data.id;
            if (!serverId) {
                console.warn("No server ID found in record props");
                return;
            }
            const result = await rpc(
                `/cetmix_tower/server/${serverId}/metrics/dashboard`
            );
            console.log("Dashboard RPC result:", result);
            if (result.status === "success" && result.data) {
                const oldInterval = this.state.monitor_interval;
                const oldMode = this.state.monitoring_mode;

                Object.assign(this.state, result.data);
                this.state.loading = false;

                // Restart timer if interval or mode changed (crucial for initial load)
                if (
                    oldInterval !== this.state.monitor_interval ||
                    oldMode !== this.state.monitoring_mode
                ) {
                    this.startTimer();
                }

                this.renderChart();
            } else {
                this.state.loading = false;
                this.state.last_update = false;
            }
        } catch (error) {
            console.error("Failed to fetch dashboard data:", error);
            this.state.loading = false;
        }
    }

    async refreshData(silent = false) {
        const serverId = this.props.record.resId || this.props.record.data.id;
        if (!serverId) {
            console.error("No server ID found to refresh");
            return;
        }
        if (!silent) this.state.loading = true;
        // In Odoo 18, we can use the backend action to trigger a pull
        // then refresh the dashboard
        try {
            await this.props.record.model.orm.call(
                "cx.tower.server",
                "action_server_monitor_pull",
                [[serverId]]
            );
        } catch (error) {
            console.error("Action Refresh Failed:", error);
        }
        await this.fetchData();
    }

    selectMetric(key) {
        this.state.selectedKey = key;
        this.renderChart();
    }

    get selectedTitle() {
        const titles = {
            cpu: "CPU Usage History (%)",
            ram: "RAM Usage History (%)",
            disk: "Disk Usage History (%)",
        };
        return titles[this.state.selectedKey];
    }

    renderChart() {
        if (!this.canvasRef.el || this.state.loading) {
            return;
        }

        const labels = this.state.history.labels;
        const data = this.state.history[this.state.selectedKey];
        const colors = {
            cpu: {line: "#00a39b", fill: "rgba(0, 163, 155, 0.1)"},
            ram: {line: "#6a62d2", fill: "rgba(106, 98, 210, 0.1)"},
            disk: {line: "#f39c12", fill: "rgba(243, 156, 18, 0.1)"},
        };
        const color = colors[this.state.selectedKey];

        if (this.chart) {
            this.chart.data.labels = labels;
            this.chart.data.datasets[0].label = this.selectedTitle;
            this.chart.data.datasets[0].data = data;
            this.chart.data.datasets[0].borderColor = color.line;
            this.chart.data.datasets[0].backgroundColor = color.fill;
            this.chart.update();
        } else {
            const ctx = this.canvasRef.el.getContext("2d");
            this.chart = new Chart(ctx, {
                type: "line",
                data: {
                    labels: labels,
                    datasets: [
                        {
                            label: this.selectedTitle,
                            data: data,
                            borderColor: color.line,
                            backgroundColor: color.fill,
                            fill: true,
                            tension: 0.4,
                            borderWidth: 3,
                            pointRadius: 2,
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {display: false},
                        tooltip: {mode: "index", intersect: false},
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            max: 100,
                            ticks: {callback: (value) => value + "%"},
                        },
                        x: {
                            ticks: {maxRotation: 0, autoSkip: true, maxTicksLimit: 10},
                        },
                    },
                },
            });
        }
    }

    formatMB(mb) {
        if (!mb) return "0.0 GB";
        return (mb / 1024).toFixed(1) + " GB";
    }
}

export const serverMonitorDashboard = {
    component: ServerMonitorDashboard,
};

registry
    .category("fields")
    .add("cx_tower_server_monitor_dashboard", serverMonitorDashboard);
