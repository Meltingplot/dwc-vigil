// Stand-in for chart.js under Jest: the DWC 3.6 build vendors the real one
// (scripts/stage-dwc36.mjs), but jsdom has no canvas for it to draw on.
function Chart(canvas, config) {
    this.canvas = canvas
    this.config = config
    this.data = config && config.data
    this.options = config && config.options
    this.update = function () {}
    this.destroy = function () {}
}

module.exports = Chart
module.exports.default = Chart
