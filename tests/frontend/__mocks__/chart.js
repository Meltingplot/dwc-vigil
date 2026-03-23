// Mock Chart.js for Jest — chart.js is provided by DWC at build time
function Chart() {
    this.config = { data: { labels: [], datasets: [{ data: [] }] }, options: {} }
    this.update = function () {}
    this.destroy = function () {}
}

module.exports = Chart
module.exports.default = Chart
